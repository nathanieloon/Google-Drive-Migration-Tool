# Imports
from __future__ import print_function

import httplib2
import os
import sys
import logging
import xml.etree.ElementTree as eTree

from apiclient import discovery, errors
from oauth2client import client, tools
from oauth2client.file import Storage


# Global variables
SCOPES = 'https://www.googleapis.com/auth/drive'    # Scope for Google Drive authentication
CLIENT_SECRET_FILE = 'client_secret.json'           # Client secret
APPLICATION_NAME = 'Drive Migration Tool'           # App name
PATH_ROOT = 'D:'                                    # Root drive (set this to whatever you want)
UPDATE_OWNER = False                                # Option for updating the owner of the file to a new domain
UPDATE_PERMISSIONS = False                          # Update file/folder permissions
NEW_DOMAIN = None                                   # New domain to migrate to
ROOT_FOLDER = PATH_ROOT                             # Root folder to start in for migration
FLAGS = None                                        # Flags for Google credentials


def get_credentials(src, reset=False):
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    if src == 'src':
        credential_path = os.path.join(credential_dir, 'src-drive-migration-tool.json')
    else:
        credential_path = os.path.join(credential_dir, 'dest-drive-migration-tool.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid or reset:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store, FLAGS)
        logging.info('Storing credentials to ' + credential_path)

    return credentials


def connect_to_drive(source, build=True, reset_cred=False):
    """ Function to connect to a drive

    Return:
        drive
    """
    credentials = get_credentials(source, reset_cred)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)
    drive = Drive(source, service)

    if build:
        drive.build_drive()

    return drive


def print_wrapper(root, drive, verbose, printtofile=False, generate_xml=False):
    """ Wrapper to print a drive
    """
    # Open a file for output
    file = open(printtofile, 'w') if printtofile else sys.stdout

    # Choose a print method
    if generate_xml:
        xml_log = logging.getLogger('xml-gen')
        output = drive.generate_xml(xml_log, root)
        tree = eTree.ElementTree(output)
        tree.write(generate_xml)
    else:
        drive.print_drive(root, verbose=verbose, output_file=file)

    # Close the file
    if printtofile or generate_xml:
        logging.info("Directory of {0} has been output to {1}".format(drive.name, printtofile if printtofile else generate_xml))
        file.close()


class Drive(object):
    """ Google Drive representation class

    Class for representing a Google Drive. Has children of Folders and Files.

    Args:
        name    (str)           Name of the Drive
        service (discovery)     Discovery service from the Drive API

    Attributes:
        name    (str)           Name of the Drive
        folders (set(Folder))   Set of folders inside the Drive
        files   (set(File))     Set of files inside the Drive
        users   (set(User))     Set of users inside the Drive
        service (discovery)     Discovery service from the Drive API

    Notes:
        The list of users is NOT a directory of users. It is only users who
            have some sort of permission/interaction with a file/folder inside
            the Drive (eg Last Modifying User, Owner, etc)
        When an instance of Drive is initiated, it executes two functions:
            build_drive() creates the objects within the Drive (eg Folders)
            generate_paths() creates the paths of every file/folder in
                the Drive (eg D:/Hello-world)

    """

    @staticmethod
    def build_path_string(path_objects):
        """ Build the path string from a given list of path_objects

        Args:
            path_objects ([File/Folders]): List of File and/or Folder
                objects

        Returns:
            str: Path string (eg D:/Hello-world)

        """
        path_string = PATH_ROOT
        end_index = len(path_objects) - 1

        for index, obj in enumerate(path_objects):
            if index == end_index:
                path_string = path_string + obj.name
            else:
                path_string = path_string + obj.name + "/"

        return path_string

    @staticmethod
    def convert_to_new_domain(email, new_domain):
        """ Convert a given email to a new domain

        Args:
            email (str): User email
            new_domain (str): New domain to transform to (eg "hello-world.com")

        Returns:
            str: Email address with new domain

        """
        return email.split('@')[0] + '@' + new_domain

    def __init__(self, name, service):
        self.name = name
        self.folders = set()
        self.root = None
        self.owner = None
        self.files = set()
        self.users = set()
        self.service = service

    def build_drive(self):
        """ Wrapper for building the drive
        """
        # Initialise the drive
        build_logger = logging.getLogger('build-drive')
        self._build_drive(build_logger)
        build_logger.debug("Generating paths for <{0}>.".format(self.name))
        self._generate_paths()  # This is expensive, optimise if possible
        build_logger.info("Finished generating paths for <{0}>. Drive has been built.".format(self.name))

    def get_credentials(self):
        """ Return the drive credentials being used for this drive

        Returns:
            owner (User): Owner of the Drive
        """
        # Return the owner if the drive is built, if not then grab it
        if self.owner:
            return self.owner

        # Get the user
        response = self.service.about().get(fields="user").execute()

        # Make a new user object
        owner = User(name=response['user']['displayName'],
                     email=response['user']['emailAddress'])

        return owner

    def add_folder(self, folder):
        """ Add a folder to the drive
        """
        self.folders.add(folder)

    def add_file(self, file):
        """ Add a file to the drive
        """
        self.files.add(file)

    def parse_path(self, path, logger):
        """ Parse a given file path, returning an ordered list of path objects

        Args:
            path (str): Path to file/folder

        Returns:
            [Folder/File]: Ordered list of folders/file objects

        """
        if PATH_ROOT not in path:
            logger.error("Invalid path <{0}>.".format(path))
            return None

        if path == PATH_ROOT:
            # We're looking at root
            return [self.root]

        # Strip out the prefix
        path = path.replace(PATH_ROOT, '')
        path_list = path.split('/')

        # Build the list of path objects
        path_objects = []
        curr_item = self.root
        for item in path_list:
            # Check the folders for matches
            for folder in self.folders:
                if curr_item.id in folder.parents and folder.name == item:
                    # Add the object to the list
                    # Set the current folder
                    curr_item = folder

                    # Add it to the list
                    path_objects.append(curr_item)

                    # Hope there aren't duplicates
                    break

            # Check the files for matches
            for file in self.files:
                if curr_item.id in file.parents and file.name == item:
                    # Set the current file
                    curr_item = file

                    # Add the object to the list
                    path_objects.append(curr_item)

                    # Hope there aren't duplicates
                    break

        if not any(obj.name == path_list[-1] for obj in path_objects) or len(path_objects) == 0:
            logger.error("Path <{0}> could not be found. Only found: <{1}>".format(
                PATH_ROOT + path, path_objects))
            return None

        # Return the path objects
        return path_objects

    def generate_xml(self, logger, base_folder_path=ROOT_FOLDER, curr_folder=None, curr_node=None, tree=None):
        """ Save the structure to an XML file type

        Args:
            base_folder_path (str, optional): Base folder path, defaults to
                the root folder
            curr_folder (Folder, optional): Current folder being printed

        """
        # If we're looking at the base folder, set it as the current folder
        if not curr_folder:
            path_objects = self.parse_path(base_folder_path, logger)
            if not path_objects:
                # Will already have thrown error message
                sys.exit()
            else:
                curr_folder = path_objects[-1]

                tree = eTree.Element('folder')
                tree.attrib['name'] = curr_folder.name
                curr_node = tree

        # Print child folder(s)
        for folder in self.folders:
            if folder.parents:
                if curr_folder.id in folder.parents:
                    curr_node = eTree.SubElement(curr_node, 'folder')
                    curr_node.attrib['name'] = folder.name
                    curr_node.attrib['owner'] = folder.owner.name
                    curr_node.attrib['created_time'] = folder.created_time
                    curr_node.attrib['last_modified_time'] = folder.last_modified_time
                    if folder.last_modified_by:
                        curr_node.attrib['last_modified_by'] = folder.last_modified_by.name

                    self.generate_xml(curr_folder=folder, logger=logger, curr_node=curr_node, tree=tree)

        # Print file(s)
        for file in self.files:
            if curr_folder.id in file.parents:
                node = eTree.SubElement(curr_node, 'file')
                node.attrib['name'] = file.name
                node.attrib['owner'] = file.owner.name
                node.attrib['created_time'] = file.created_time
                node.attrib['last_modified_time'] = file.last_modified_time
                if file.last_modified_by:
                    node.attrib['last_modified_by'] = file.last_modified_by.name

        return tree

    def print_drive(self, logger, base_folder_path=ROOT_FOLDER, verbose=False, curr_folder=None, prefix="", output_file=None):
        """ Print the drive structure from the given root folder

        Args:
            base_folder_path (str, optional): Base folder path, defaults to
                the root folder
            verbose (bool, optional): Verbose printing on/off, defaults to off
            curr_folder (Folder, optional): Current folder being printed
            prefix (str, optional): Prefix for indenting/formatting the
                printing

        """
        # If we're looking at the base folder, set it as the current folder
        if not curr_folder:
            path_objects = self.parse_path(base_folder_path, logger)
            if not path_objects:
                # Will already have thrown error message
                sys.exit()
            else:
                curr_folder = path_objects[-1]

        # Print the current folder
        if curr_folder is self.root:
            if verbose:
                print (prefix + curr_folder.id, end='', file=output_file)
            else:
                print (prefix, end='', file=output_file)

            print(curr_folder.name +
                  " (" + curr_folder.owner.name + ")", file=output_file)
        elif verbose:
            print(prefix + curr_folder.name +
                  " (" + curr_folder.owner.name + ")" +
                  " (" + curr_folder.last_modified_time + ")", end='', file=output_file)

            if curr_folder.last_modified_by:
                print(" (" + curr_folder.last_modified_by.email + ")", file=output_file)
        else:
            print(prefix + curr_folder.name, file=output_file)

        # Print file(s)
        for file in self.files:
            if curr_folder.id in file.parents:
                if verbose:
                    print(prefix + "\t" + file.name +
                          " (" + file.owner.name + ")" +
                          " (" + file.last_modified_time + ")", end='', file=output_file)
                    if file.last_modified_by:
                        print(" (" + file.last_modified_by.email + ")", file=output_file)
                else:
                    print(prefix + "\t" + file.path, file=output_file)

        # Print child folder(s)
        for folder in self.folders:
            if folder.parents:
                if curr_folder.id in folder.parents:
                    self.print_drive(
                        verbose=verbose, logger=logger, curr_folder=folder, prefix=prefix + "\t", output_file=output_file)

    def get_user_emails(self):
        """ Get all user emails
        """
        emails = set()
        for user in self.users:
            emails.add(user.email)
        return emails

    def add_user(self, user):
        """ Add a user to the drive
        """
        # Only add the user if they don't already exist
        if user.email not in self.get_user_emails():
            self.users.add(user)

    def update_drive(self, src_drive, logger, base_folder_path=None, parent=None, curr_folder=None):
        """ Update the owner and last known modified date for a file/folder

        Args:
            src_drive (Drive): Source Drive instance
            base_folder_path (str, optional): Base folder to start the update
                in, defaults to root
            parent (Folder, optional): Parent folder object
            curr_folder (Folder, optional): Current folder object being
                looked at

        """
        # If we don't have a current folder, get one
        if not curr_folder:
            if not base_folder_path or base_folder_path == src_drive.root.path:
                curr_folder = src_drive.root
            else:
                curr_folder = src_drive.get_folder_via_path(base_folder_path, logger)
                # If we can't find the root path, bail out
                if not curr_folder:
                    sys.exit()

        # Update files in current folder
        file_count = 0
        for file in src_drive.files:
            if file.path:
                if curr_folder.id in file.parents:
                    file_result = self.update_info(src_drive=src_drive, path=file.path, logger=logger)
                    if file_result:
                        logger.info(file_result)
                    file_count += 1

        # Update the current folder
        folder_result = self.update_info(src_drive=src_drive,
                                         logger=logger,
                                         path=curr_folder.path,
                                         is_file=False)
        if folder_result:
            logger.info(folder_result)

        logger.info("Updated <{0}> files in folder <{1}> in <{2}> drive.".format(
            file_count, curr_folder.name, self.name))

        # Update sub-folders
        for folder in src_drive.folders:
            if curr_folder.id in folder.parents:
                self.update_drive(src_drive=src_drive,
                                  parent=curr_folder,
                                  logger=logger,
                                  curr_folder=folder)

    def get_file_via_path(self, path, logger):
        """ Get a file via its path
        """
        for file in self.files:
            if file.path == path:
                return file

        if logger:
            logger.error("Could not find file at <{0}> in <{1}>.".format(path, self.name))
        return None

    def get_folder_via_path(self, path, logger):
        """ Get a folder via its path
        """
        for folder in self.folders:
            if folder.path == path:
                return folder

        logger.error("Could not find folder at <{0}> in <{1}>.".format(
            path, self.name))

    def update_info(self, src_drive, path, logger, is_file=True):
        """ Update the supplied drive item with the last known modified
            date and owner for a given file

        Args:
            src_drive (Drive): Source Drive instance
            path (str): Path of file/folder being updated
            is_file (bool, optional): Is the path a file, defaults
                to True

        """
        if path != self.root.path:
            if is_file:
                src_item = src_drive.get_file_via_path(path, logger)
                dest_item = self.get_file_via_path(path, logger)
            else:
                src_item = src_drive.get_folder_via_path(path, logger)
                dest_item = self.get_folder_via_path(path, logger)

            # Make sure both the source and destination files can be found
            if not src_item:
                logger.error("Item <{0}> could not be found in <{1}>. Skipping.".format(path, src_drive.name))
                return
            if not dest_item:
                logger.error("Item <{0}> could not be found in <{1}>. Skipping.".format(path, self.name))
                return

            if UPDATE_PERMISSIONS:
                # Update the permissions for a given item
                try:
                    results = src_drive.service.permissions().list(fileId=src_item.id,
                                                                   fields='permissions(id, emailAddress, displayName, role, type)'
                                                                   ).execute()

                    permissions = results.get('permissions', [])

                    permission_failures = []

                    for permission in permissions:
                        if permission['type'] == 'user' and permission['role'] != 'owner':
                            # Get the new user email
                            if NEW_DOMAIN is not None:
                                new_user = self.convert_to_new_domain(permission['emailAddress'], NEW_DOMAIN)

                            # Build the updated payload
                            user_body = {'emailAddress': new_user,
                                         'role': permission['role'],
                                         'type': 'user'}

                            # Send the file back
                            try:
                                perm_response = self.service.permissions().create(fileId=dest_item.id,
                                                                                  body=user_body,
                                                                                  sendNotificationEmail=False,
                                                                                  transferOwnership=False
                                                                                  ).execute()
                            except errors.HttpError:
                                # Store the failure
                                permission_failures.append(new_user)

                            if len(permission_failures) > 0:
                                logger.warning("Failed to update permission on item <{0}>. The user(s) <{1}> may not exist in the new Drive.".format(src_item.name, permission_failures))

                except errors.HttpError as err:
                    logger.warning("Failed to update permission on item <{0}>. Message: {1}".format(src_item.name, err))

            if UPDATE_OWNER:
                try:
                    results = src_drive.service.permissions().list(fileId=src_item.id,
                                                                   fields='permissions(emailAddress, role, type)'
                                                                   ).execute()
                    permissions = results.get('permissions', [])

                    for permission in permissions:
                        if permission['type'] == 'user' and permission['role'] == 'owner':
                            curr_owner = permission['emailAddress']

                    if curr_owner != src_drive.owner.email:
                        # Get the new user email
                        new_owner = self.convert_to_new_domain(src_item.owner.email, NEW_DOMAIN)

                        # Build the updated payload
                        user_body = {'emailAddress': new_owner,
                                     'role': 'owner',
                                     'type': 'user'}

                        # Send the file back
                        try:
                            user_response = self.service.permissions().create(fileId=dest_item.id,
                                                                              body=user_body,
                                                                              sendNotificationEmail=True,
                                                                              transferOwnership=True
                                                                              ).execute()
                        except errors.HttpError:
                            logger.warning("Failed to update owner of item <{0}>. The user <{1}> may not exist in the new Drive.".format(src_item.name, new_owner))
                except errors.HttpError as err:
                    logger.warning("Failed to update permission on item <{0}>. Message: {1}".format(src_item.name, err))

            # Build the updated payload
            time_body = {'modifiedTime': src_item.last_modified_time}

            # Send the file back
            try:
                time_response = self.service.files().update(fileId=dest_item.id,
                                                            body=time_body
                                                            ).execute()
            except errors.HttpError:
                logger.warning("Failed to update the last modified time for file <{0}>".format(src_item.name))

        return "Successfully updated <{0}> in drive <{1}>.".format(dest_item.name, self.name)

    def _generate_paths(self, curr_item=None, curr_path=None):
        """ Generate all the paths for every file and folder in the drive - expensive

        Builds all the paths for every item in the Drive. Stores them in the
            path attribute for each item.

        Args:
            curr_item (File/Folder, optional): Current item being looked at
            curr_path (List): Current path to item being looked at

        """
        # Start in root
        if not curr_item:
            curr_item = self.root

        # Build folders first
        if not curr_path:
            curr_path = []

        for file in self.files:
            path_objects = list(curr_path)

            if curr_path:
                curr_item = path_objects[-1]

            if not file.path and curr_item.id in file.parents:
                # Build the path string
                path_string = curr_item.path + "/" + file.name

                # Set the file path string
                file.set_path(path_string)

        for folder in self.folders:
            # Reset to the current path
            path_objects = list(curr_path)
            if curr_path:
                curr_item = path_objects[-1]

            if not folder.path and curr_item.id in folder.parents:
                # Build the path string
                path_string = curr_item.path + "/" + folder.name

                # Set the folder path string
                folder.set_path(path_string)

                # Generate children
                self._generate_paths(folder, path_objects)

    def _build_drive(self, logger):
        """ Build the Google Drive for the given service

        Build the Drive objects from the provided API point.

        """
        page_token = None
        page_no = 1
        logger.info("Retrieving drive data for <{0}>...".format(self.name))

        # Get the root "My Drive" folder first
        response = self.service.files().get(fileId='root',
                                            fields="id, mimeType, name, owners").execute()
        # Set the owner
        owner = User(name=response['owners'][0]['displayName'],
                     email=response['owners'][0]['emailAddress'])
        self.owner = owner
        # Set the root
        root_folder = Folder(identifier=response['id'],
                             name=response['name'],
                             owner=owner,
                             parents=None,
                             last_modified_time=None,
                             last_modified_by=None,
                             path=PATH_ROOT)
        self.root = root_folder
        logger.debug("root_folder: {0}, root_owner: {1} ".format(root_folder, owner))

        # Get the rest of the drive
        while True:
            # Get entire folder structure, we'll work down from here
            response = self.service.files().list(q="trashed = false",
                                                 pageSize=1000,
                                                 pageToken=page_token,
                                                 fields="nextPageToken, files(id, mimeType, name, owners, parents, modifiedTime, lastModifyingUser, createdTime)").execute()
            results = response.get('files', [])

            # Build folder structure in memory
            for result in results:
                # Create owner
                owner = User(name=result['owners'][0]['displayName'],
                             email=result['owners'][0]['emailAddress'])
                self.add_user(owner)

                # Save last modifying user, if it exists
                if 'lastModifyingUser' in result and 'emailAddress' in result['lastModifyingUser']:
                    modified_by = User(name=result['lastModifyingUser']['displayName'],
                                       email=result['lastModifyingUser']['emailAddress'])
                    self.add_user(modified_by)
                else:
                    modified_by = None

                # Check if it's a root folder
                if 'parents' in result:
                    parents = result['parents']
                else:
                    parents = 'root'

                # Create drive item
                if result['mimeType'] == 'application/vnd.google-apps.folder':
                    folder = Folder(identifier=result['id'],
                                    name=result['name'],
                                    owner=owner,
                                    parents=parents,
                                    created_time=result['createdTime'],
                                    last_modified_time=result['modifiedTime'],
                                    last_modified_by=modified_by)
                    self.add_folder(folder)
                    logger.debug("folder: {0}, owner: {1}".format(folder, owner))
                else:
                    file = File(identifier=result['id'],
                                name=result['name'],
                                owner=owner,
                                parents=parents,
                                created_time=result['createdTime'],
                                last_modified_time=result['modifiedTime'],
                                last_modified_by=modified_by,
                                mime_type=result['mimeType'])
                    self.add_file(file)
                    logger.debug("file: {0}, owner: {1}".format(file, owner))

            # Look for more pages of results
            page_token = response.get('nextPageToken', None)
            page_no += 1
            if page_token is None:
                break

        logger.info("Found <{0}> pages of results for <{1}>. Building Drive...".format(page_no, self.name))


class User(object):
    """ User representation class

    Args:
        name (str): Name of the user
        email (str): Email of the user

    Attributes:
        name (str): Name of the user
        email (str): Email of the user

    """

    def __init__(self, name, email):
        self.name = name
        self.email = email

    def __repr__(self):
        return "<user: {0}>".format(self.email)


class File(object):
    """ File representation class

    Args:
        identifier (str): Google Drive ID of the file
        name (str): Name of the file
        owner (User.User): Owner of the file
        parents ([str]): List of parent IDs
        created_time (str): Time/date created
        last_modified_time (str): "Last modified time"
        last_modified_by (User.User): "Last modified by" user
        mime_type (str): MIME Type of the file

    Attributes:
        id (str): Google Drive ID of the file
        name (str): Name of the file
        owner (User.User): Owner of the file
        parents ([str]): List of parent IDs
        created_time (str): Time/date created
        last_modified_time (str): "Last modified time"
        last_modified_by (User.User): "Last modified by" user
        mime_type (str): MIME Type of the file
        path (str): Path to the file within the Drive

    """

    def __init__(self,
                 identifier,
                 name,
                 owner,
                 parents,
                 created_time,
                 last_modified_time,
                 last_modified_by,
                 mime_type):
        self.id = identifier
        self.name = name
        self.parents = parents
        self.owner = owner
        self.created_time = created_time
        self.last_modified_time = last_modified_time
        self.last_modified_by = last_modified_by
        self.mime_type = mime_type

        self.path = None

    def __repr__(self):
        return "<file: {0}>".format(self.name)

    def set_path(self, path):
        """ Set the file path string
        """
        self.path = path


class Folder(object):
    """ Folder representation class

    Args:
        identifier (str): Google Drive ID of the folder
        name (str): Name of the folder
        owner (User.User): Owner of the folder
        parents ([str], optional): List of parent IDs
        created_time (str): Time/date created
        last_modified_time (str, optional): "Last modified time"
        last_modified_by (User.User, optional): "Last modified by" user
        path (str, optional): Path to the folder within the Drive

    Attributes:
        id (str): Google Drive ID of the folder
        name (str): Name of the folder
        owner (User.User): Owner of the folder
        parents ([str]): List of parent IDs
        created_time (str): Time/date created
        last_modified_time (str): "Last modified time"
        last_modified_by (User.User): "Last modified by" user
        path (str): Path to the folder within the Drive

    """

    def __init__(self,
                 identifier,
                 name,
                 owner,
                 parents=None,
                 created_time=None,
                 last_modified_time=None,
                 last_modified_by=None,
                 path=None):
        self.id = identifier
        self.name = name
        self.parents = parents
        self.owner = owner
        self.created_time = created_time
        self.last_modified_time = last_modified_time
        self.last_modified_by = last_modified_by

        self.path = path

    def __repr__(self):
        return "<folder: {0}>".format(self.name)

    def set_path(self, path):
        """ Set the folder path string
        """
        self.path = path
