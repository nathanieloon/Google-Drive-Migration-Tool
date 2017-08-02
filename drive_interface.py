# Imports
from __future__ import print_function

import httplib2
import os
import sys
import logging

from apiclient import discovery
from oauth2client import client, tools
from oauth2client.file import Storage


def _get_credentials(reset=False, flags=None):
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
    credential_path = os.path.join(credential_dir, 'src-drive-migration-tool.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid or reset:
        flow = client.flow_from_clientsecrets('client_secret.json',
                                              'https://www.googleapis.com/auth/drive')
        flow.user_agent = 'Drive Migration Tool'
        credentials = tools.run_flow(flow, store, flags)
        logging.info('Storing credentials to ' + credential_path)
    return credentials


class Drive(object):
    """ Google Drive representation class

    Class for representing a Google Drive. Has children of Folders and Files.

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

    def __init__(self, root_path, reset_cred=True, flags=None):
        self.name = 'Source'
        self.folders = set()
        self.root = None
        self._owner = None
        self.files = set()
        self.users = set()
        self._root_path = root_path

        self._credentials = _get_credentials(reset=reset_cred, flags=flags)
        http = self._credentials.authorize(httplib2.Http())
        self.service = discovery.build('drive', 'v3', http=http)

        # Initialise the drive
        build_logger = logging.getLogger('build-drive')
        self._build_drive(build_logger)
        build_logger.debug("Generating paths for <{0}>.".format(self.name))
        self._generate_paths()  # This is expensive, optimise if possible
        build_logger.info("Finished generating paths for <{0}>. Drive has been built.".format(self.name))

    @property
    def owner(self):
        if not self._owner:
            response = self.service.about().get(fields="user").execute()
            self._owner = self.create_or_retrieve_user(user_email=response['user']['emailAddress'],
                                                       user_name=response['user']['displayName'])
        return self._owner

    def parse_path(self, path, logger):
        """ Parse a given file path, returning an ordered list of path objects

        Args:
            path   (str)    Path to file/folder
            logger (logger) Object to which to write all logging

        Returns:
            [Folder/File]: Ordered list of folders/file objects

        """
        if self._root_path not in path:
            logger.error("Invalid path <{0}>.".format(path))
            return None

        if path == self._root_path:
            # We're looking at root
            return [self.root]

        # Strip out the prefix
        path = path.replace(self._root_path, '')
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

        if logger and (not any(obj.name == path_list[-1] for obj in path_objects) or len(path_objects) == 0):
            logger.error("Path <{0}> could not be found. Only found: <{1}>".format(
                self._root_path + path, path_objects))
            return None

        # Return the path objects
        return path_objects

    def print_drive(self, base_folder_path, logger=None, verbose=False, curr_folder=None, prefix="", output_file=None):
        """ Print the drive structure from the given root folder

        Args:
            base_folder_path (str, optional): Base folder path, defaults to the root folder
            verbose (bool, optional): Verbose printing on/off, defaults to off
            curr_folder (Folder, optional): Current folder being printed
            prefix (str, optional): Prefix for indenting/formatting the printing
            logger (logger): Object to which to write all logging
            output_file (file, optional): File to write the structure to

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
                print(prefix + curr_folder.id, end='', file=output_file)
            else:
                print(prefix, end='', file=output_file)

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
        prefix = prefix + "\t"
        for file in self.files:
            if curr_folder.id in file.parents:
                if verbose:
                    print(prefix + file.name +
                          " (" + file.owner.name + ")" +
                          " (" + file.last_modified_time + ")", end='', file=output_file)
                    if file.last_modified_by:
                        print(" (" + file.last_modified_by.email + ")", file=output_file)
                else:
                    print(prefix + file.name, file=output_file)

        # Print child folder(s)
        for folder in self.folders:
            if folder.parents:
                if curr_folder.id in folder.parents:
                    self.print_drive(verbose=verbose,
                                     logger=logger,
                                     base_folder_path=self._root_path,
                                     curr_folder=folder,
                                     prefix=prefix,
                                     output_file=output_file)

    def create_or_retrieve_user(self, user_email, user_name):
        """Get a user by their email if they exist, otherwise add them
        """

        for user in self.users:
            if user.email == user_email:
                return user
        new_user = DriveUser(user_name, user_email)
        self.users.add(new_user)
        return new_user

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
            
        if logger:
            logger.error("Could not find folder at <{0}> in <{1}>.".format(path, self.name))
        return None

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
        logger.info("Retrieving drive data for <{0}>...".format(self.name))

        # Get the root "My Drive" folder first
        response = self.service.files().get(fileId='root',
                                            fields="id, mimeType, name, owners").execute()
        # Set the owner
        self._owner = self.create_or_retrieve_user(response['owners'][0]['emailAddress'],
                                                   response['owners'][0]['displayName'])
        # Set the root
        root_folder = DriveFolder(identifier=response['id'],
                                  name=response['name'],
                                  owner=self._owner,
                                  parents=None,
                                  last_modified_time=None,
                                  last_modified_by=None,
                                  path=self._root_path)
        self.root = root_folder
        logger.debug("root_folder: {0}, root_owner: {1} ".format(root_folder, self._owner))

        page_token = None
        page_no = 1

        # Get the rest of the drive
        while True:
            # Get entire folder structure, we'll work down from here
            response = self.service.files().list(q="trashed = false",
                                                 pageSize=1000,
                                                 pageToken=page_token,
                                                 fields="nextPageToken, \
                                                         files(id, \
                                                               mimeType, \
                                                               name, \
                                                               owners, \
                                                               parents, \
                                                               modifiedTime, \
                                                               lastModifyingUser, \
                                                               createdTime)").execute()
            results = response.get('files', [])

            # Build folder structure in memory
            for result in results:
                # Create owner
                owner = self.create_or_retrieve_user(result['owners'][0]['emailAddress'],
                                                     result['owners'][0]['displayName'])

                # Save last modifying user, if it exists
                if 'lastModifyingUser' in result and 'emailAddress' in result['lastModifyingUser']:
                    modified_by = self.create_or_retrieve_user(result['owners'][0]['emailAddress'],
                                                               result['owners'][0]['displayName'])
                else:
                    # Set the last modifier to be the file owner if no last modified exists
                    modified_by = owner

                # Check if it's a root folder
                if 'parents' in result:
                    parents = result['parents']
                else:
                    parents = [self.root.id]

                # Create drive item
                if result['mimeType'] == 'application/vnd.google-apps.folder':
                    folder = DriveFolder(identifier=result['id'],
                                         name=result['name'],
                                         owner=owner,
                                         parents=parents,
                                         created_time=result['createdTime'],
                                         last_modified_time=result['modifiedTime'],
                                         last_modified_by=modified_by)
                    self.folders.add(folder)
                    logger.debug("folder: {0}, owner: {1}".format(folder, owner))
                else:
                    file = DriveFile(identifier=result['id'],
                                     name=result['name'],
                                     owner=owner,
                                     parents=parents,
                                     created_time=result['createdTime'],
                                     last_modified_time=result['modifiedTime'],
                                     last_modified_by=modified_by,
                                     mime_type=result['mimeType'])
                    if file.mime_type == 'application/vnd.google-apps.document'\
                            and not file.name.lower().endswith('.docx')\
                            and not file.name.lower().endswith('.doc')\
                            and not file.name.lower().endswith('.txt'):
                        file.name = file.name + '.docx'
                    elif file.mime_type == 'application/vnd.google-apps.spreadsheet'\
                            and not file.name.lower().endswith('.xlsx')\
                            and not file.name.lower().endswith('.xls'):
                        file.name = file.name + '.xlsx'
                    elif file.mime_type == 'application/vnd.google-apps.presentation'\
                            and not file.name.lower().endswith('.pptx')\
                            and not file.name.lower().endswith('.ppt'):
                        file.name = file.name + '.pptx'
                    self.files.add(file)
                    logger.debug("file: {0}, owner: {1}".format(file, owner))

            # Look for more pages of results
            page_token = response.get('nextPageToken', None)
            page_no += 1
            if page_token is None:
                break

        logger.info("Found <{0}> pages of results for <{1}>. Building Drive...".format(page_no, self.name))


class DriveUser(object):
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


class DriveFile(object):
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


class DriveFolder(object):
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
