# Imports
from __future__ import print_function

import httplib2
import os

from apiclient import discovery
from oauth2client import client, tools
from oauth2client.file import Storage

CLIENT_KEY_FILE = 'client_secret.json'


def print_credentials(force_reset=False, logger=None):
    credentials = _get_credentials(reset=force_reset, logger=logger)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)
    about = service.about().get(fields="user").execute()
    if logger:
        logger.info('Logged into Drive with username: {0}'.format(about['user']['emailAddress']))


def _get_credentials(reset=False, flags=None, logger=None):
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
        flow = client.flow_from_clientsecrets(CLIENT_KEY_FILE,
                                              'https://www.googleapis.com/auth/drive')
        flow.user_agent = 'Drive Migration Tool'
        credentials = tools.run_flow(flow, store, flags)
        logger.info('Storing credentials to ' + credential_path)
    return credentials


class Drive(object):
    """Class for representing a Google Drive. Has children of Folders and Files.

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

    def __init__(self, path_prefix, root_path=None, reset_cred=True, flags=None, logger=None):
        self.name = 'Source'
        self.folders = []
        self.root = None
        self._owner = None
        self.files = []
        self.users = []
        self._path_prefix = path_prefix
        self._root_path = root_path

        self._credentials = _get_credentials(reset=reset_cred, flags=flags, logger=logger)
        http = self._credentials.authorize(httplib2.Http())
        self.service = discovery.build('drive', 'v3', http=http)

        # Initialise the drive
        raw_files, raw_folders = self._get_all_files(logger)

        self.root = self._create_root(self._root_path, raw_folders)
        logger.debug("Generating paths for <{0}>.".format(self.name))
        self._create_child_folders(self.root, raw_folders)
        self._create_files(raw_files)
        logger.info("Finished generating paths for <{0}>. Drive has been built.".format(self.name))

    def _parse_path(self, path, logger):
        """ Parse a given file path, returning an ordered list of path objects

        Args:
            path (str): Path to file/folder
            logger (logger): Logging file

        Returns:
            [Folder/File]: Ordered list of folders/file objects

        """
        if self._path_prefix not in path:
            logger.error("Invalid path <{0}>.".format(path))
            return None

        if path == self._path_prefix:
            # We're looking at root
            return [self.root]

        # Strip out the prefix
        path = path.replace(self._path_prefix, '')
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
                self._path_prefix + path, path_objects))
            return None

        # Return the path objects
        return path_objects

    def print_drive(self, output_file=None):
        """ Print the Drive, starting from a specified path

        Args:
            output_file (file, optional): File to which to print the structure
        """
        self._print_folder(folder=self.folders[0], output_file=output_file)

    def _print_folder(self, folder, prefix='', output_file=None):
        """ Print a folder, along with all files and subfolders

        Calls itself recursively on each subfolder it finds

        Args:
            folder (BoxObject): Folder to print out
            prefix (str): Padding prefix to format output neatly
            output_file (file, optional): File to which to print the structure
        """

        print(prefix + (folder.path if folder.path else folder.name), file=output_file)
        prefix = prefix + '  '
        for file in self.files:
            if file.parent == folder:
                print(prefix + (file.path if file.path else file.name), file=output_file)

        for subfolder in self.folders:
            if subfolder.parent == folder:
                self._print_folder(folder=subfolder, prefix=prefix, output_file=output_file)

    def get_file_via_path(self, path, logger=None):
        """ Get a file via its path

        Args:
            path (str): Path to the file
            logger (logger, optional): Logging file

        Returns:
            File: File at the specified path
        """
        for file in self.files:
            if file.path == path:
                return file

        if logger:
            logger.error("Could not find file at <{0}> in <{1}>.".format(path, self.name))
        return None

    def _create_or_retrieve_user(self, user_email, user_name):
        """Get a user by their email if they exist, otherwise add them

        Args:
            user_email (str): User's email address
            user_name (str): User's full name

        Returns:
            User: User object corresponding to the given email address
        """

        for user in self.users:
            if user.email == user_email:
                return user
        new_user = User(user_name, user_email)
        self.users.append(new_user)
        return new_user

    def _get_all_files(self, logger=None):
        """ Build the Google Drive for the given service

        Args:
            logger (logger, optional): Logging file
        """

        if logger:
            logger.info("Retrieving drive data for <{0}>...".format(self.name))

        # Get the root "My Drive" folder first
        response = self.service.files().get(fileId='root',
                                            fields="id, mimeType, name, owners").execute()

        raw_files = []
        raw_folders = [response]

        # Set the owner
        self._owner = self._create_or_retrieve_user(response['owners'][0]['emailAddress'],
                                                    response['owners'][0]['displayName'])
        # Set the root
        if logger:
            logger.debug("root_folder: {0}, root_owner: {1} ".format(response['name'],
                                                                     response['owners'][0]['displayName']))

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

            for result in results:
                if result['mimeType'] == 'application/vnd.google-apps.folder':
                    raw_folders.append(result)
                    if logger:
                        logger.debug("folder: {0}, owner: {1}".format(result['name'],
                                                                      result['owners'][0]['displayName']))
                else:
                    raw_files.append(result)
                    if logger:
                        logger.debug("file: {0}, owner: {1}".format(result['name'],
                                                                    result['owners'][0]['displayName']))

            # Look for more pages of results
            page_token = response.get('nextPageToken', None)
            page_no += 1
            if page_token is None:
                break
        if logger:
            logger.info("Found <{0}> pages of results for <{1}>. Building Drive...".format(page_no, self.name))

        for raw_folder in raw_folders:
            if 'parents' not in raw_folder:
                raw_folder['parents'] = raw_folders[0]['id']

        return raw_files, raw_folders

    def _create_root(self, root_directory, raw_folders):
        if root_directory and root_directory.startswith(self._path_prefix):
            root_directory = root_directory.replace(self._path_prefix + '/', '')

        current_folder = raw_folders[0]
        if root_directory and root_directory != '':
            paths = root_directory.split('/')
            for path in paths:
                found_path = False
                for folder in raw_folders:
                    if folder['name'] == path and 'parents' in folder and current_folder['id'] in folder['parents']:
                        found_path = True
                        current_folder = folder
                        break
                if not found_path:
                    raise FileNotFoundError('Couldn\'t find the root folder <{0}> in Drive'.format(root_directory))
        owner = self._create_or_retrieve_user(current_folder['owners'][0]['emailAddress'],
                                              current_folder['owners'][0]['displayName'])

        if 'lastModifyingUser' in current_folder and 'emailAddress' in current_folder['lastModifyingUser']:
            modified_by = self._create_or_retrieve_user(current_folder['lastModifyingUser']['emailAddress'],
                                                        current_folder['lastModifyingUser']['displayName'])
        else:
            # Set the last modifier to be the file owner if no last modified exists
            modified_by = owner

        created_time = current_folder['createdTime'] if 'createdTime' in current_folder else ''
        modified_time = current_folder['modifiedTime'] if 'modifiedTime' in current_folder else created_time

        root_folder = Folder(identifier=current_folder['id'],
                             name=self._path_prefix,
                             owner=owner,
                             parent=None,
                             created_time=created_time,
                             last_modified_time=modified_time,
                             last_modified_by=modified_by)

        self.folders.append(root_folder)
        return root_folder

    def _create_child_folders(self, parent_folder, all_folders):
        for raw_folder in all_folders:

            if parent_folder.id in raw_folder['parents'] and parent_folder.id != raw_folder['id']:
                owner = self._create_or_retrieve_user(raw_folder['owners'][0]['displayName'],
                                                      raw_folder['owners'][0]['emailAddress'])
                if 'lastModifyingUser' in raw_folder:
                    last_modifier = self._create_or_retrieve_user(raw_folder['lastModifyingUser']['displayName'],
                                                                  raw_folder['lastModifyingUser']['emailAddress'])
                else:
                    last_modifier = owner

                created_time = raw_folder['createdTime'] if 'createdTime' in raw_folder else ''
                modified_time = raw_folder['modifiedTime'] if 'modifiedTime' in raw_folder else created_time

                new_folder = Folder(identifier=raw_folder['id'],
                                    name=raw_folder['name'],
                                    owner=owner,
                                    parent=parent_folder,
                                    created_time=created_time,
                                    last_modified_time=modified_time,
                                    last_modified_by=last_modifier)
                self.folders.append(new_folder)
                self._create_child_folders(parent_folder=new_folder, all_folders=all_folders)

    def _create_files(self, raw_files):
        for raw_file in raw_files:
            if 'parents' in raw_file:
                for folder in self.folders:
                    if folder.id in raw_file['parents']:
                        filename = raw_file['name']
                        if raw_file['mimeType'] == 'application/vnd.google-apps.document'\
                                and not raw_file['name'].lower().endswith('.docx')\
                                and not raw_file['name'].lower().endswith('.doc')\
                                and not raw_file['name'].lower().endswith('.txt'):
                            filename = filename + '.docx'
                        elif raw_file['mimeType'] == 'application/vnd.google-apps.spreadsheet'\
                                and not raw_file['name'].lower().endswith('.xlsx')\
                                and not raw_file['name'].lower().endswith('.xls'):
                            filename = filename + '.xlsx'
                        elif raw_file['mimeType'] == 'application/vnd.google-apps.presentation'\
                                and not raw_file['name'].lower().endswith('.pptx')\
                                and not raw_file['name'].lower().endswith('.ppt'):
                            filename = filename + '.pptx'

                        owner = self._create_or_retrieve_user(raw_file['owners'][0]['displayName'],
                                                              raw_file['owners'][0]['emailAddress'])
                        if 'lastModifyingUser' in raw_file:
                            last_modifier = self._create_or_retrieve_user(
                                raw_file['lastModifyingUser']['displayName'],
                                raw_file['lastModifyingUser']['emailAddress'])
                        else:
                            last_modifier = owner

                        created_time = raw_file['createdTime'] if 'createdTime' in raw_file else ''
                        modified_time = raw_file['modifiedTime'] if 'modifiedTime' in raw_file else created_time

                        new_file = File(identifier=raw_file['id'],
                                        owner=owner,
                                        name=filename,
                                        parent=folder,
                                        created_time=created_time,
                                        last_modified_time=modified_time,
                                        last_modified_by=last_modifier,
                                        mime_type=raw_file['mimeType'])
                        self.files.append(new_file)


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
        parent (Folder, optional): List of parent IDs
        created_time (str): Time/date created
        last_modified_time (str): "Last modified time"
        last_modified_by (User.User): "Last modified by" user
        mime_type (str): MIME Type of the file

    Attributes:
        id (str): Google Drive ID of the file
        name (str): Name of the file
        owner (User.User): Owner of the file
        parent (Folder, optional): The parent folder
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
                 created_time,
                 last_modified_time,
                 last_modified_by,
                 mime_type,
                 parent=None):
        self.id = identifier
        self.name = name
        self.owner = owner
        self.created_time = created_time
        self.last_modified_time = last_modified_time
        self.last_modified_by = last_modified_by
        self.mime_type = mime_type
        self.parent = parent
        if self.parent:
            self.path = (parent.path if parent.path else parent.name) + '/' + self.name
        else:
            self.path = None

    def __repr__(self):
        return "<file: {0}>".format(self.name)


class Folder(object):
    """ Folder representation class

    Args:
        identifier (str): Google Drive ID of the folder
        name (str): Name of the folder
        owner (User.User): Owner of the folder
        parent ([Folder, optional): The object's parent folder
        created_time (str): Time/date created
        last_modified_time (str, optional): "Last modified time"
        last_modified_by (User.User, optional): "Last modified by" user

    Attributes:
        id (str): Google Drive ID of the folder
        name (str): Name of the folder
        owner (User.User): Owner of the folder
        created_time (str): Time/date created
        last_modified_time (str): "Last modified time"
        last_modified_by (User.User): "Last modified by" user
        path (str): Path to the folder within the Drive

    """

    def __init__(self,
                 identifier,
                 name,
                 owner,
                 parent=None,
                 created_time=None,
                 last_modified_time=None,
                 last_modified_by=None):
        self.id = identifier
        self.name = name
        self.owner = owner
        self.created_time = created_time
        self.last_modified_time = last_modified_time
        self.last_modified_by = last_modified_by
        self.parent = parent
        if self.parent:
            self.path = (parent.path if parent.path else parent.name) + '/' + self.name
        else:
            self.path = None

    def __repr__(self):
        return "<folder: {0}>".format(self.name)
