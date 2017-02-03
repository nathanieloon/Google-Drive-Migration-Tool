from __future__ import print_function
import httplib2
import os
import sys

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/drive-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/drive.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Drive Migration Tool'

ROOT_FOLDER = 'root'

class Drive():
    """ Google Drive representation class
    """
    def __init__(self, name, folders=set(), files=set()):
        self.name = name
        self.folders = folders
        self.files = files
        self.users = set()

    def add_folder(self, folder):
        """ Add a folder to the drive
        """
        self.folders.add(folder)

    def add_file(self, file):
        """ Add a file to the drive
        """
        self.files.add(file)

    def get_folder(self, name=None, id=None):
        """ Get a folder by name or id
        """
        for folder in self.folders:
            if folder.id == id or folder.name == name:
                return folder

    def get_file(self, name=None, id=None):
        """ Get a file by name or id
        """
        for file in self.files:
            if file.id == id or file.name == name:
                return file

    def print_drive(self, root='root', curr_folder=None, prefix=""):
        """ Print the drive structure from the given root folder
        """
        if not curr_folder:
            # Print the root folder(s)
            print (root)

            # Print file(s)
            for file in self.files:
                if self.get_folder(name=root).id in file.parents:
                    print (prefix + file.name)

            # Print child folder(s)
            for folder in self.folders:
                if self.get_folder(name=root).id in folder.parents:
                    self.print_drive(curr_folder=folder, prefix=prefix+"\t")

        else:
            # Print the rest of the hierarchy
            print (prefix + curr_folder.name)

            # Print file(s)
            for file in self.files:
                if curr_folder.id in file.parents:
                    print (prefix + file.name)

            # Print child folder(s)
            for folder in self.folders:
                if curr_folder.id in folder.parents:
                    self.print_drive(curr_folder=folder, prefix=prefix+"\t")

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
        if user.email not in self.get_user_emails():
            self.users.add(user)


class User():
    """ User representation class
    """
    def __init__(self, name, email):
        self.name = name
        self.email = email

class File():
    """ File representation class
    """
    def __init__(self, id, name, owner, last_modified_time, last_modified_by, parents):
        self.id = id
        self.name = name
        self.parents = parents
        self.owner = owner
        self.last_modified_time = last_modified_time
        self.last_modified_by = last_modified_by

    def __repr__(self):
        return "<file: {0}>".format(self.name)

class Folder():
    """ Folder representation class
    """
    def __init__(self, id, name, owner, last_modified_time, last_modified_by, parents):
        self.id = id
        self.name = name
        self.parents = parents
        self.owner = owner
        self.last_modified_time = last_modified_time
        self.last_modified_by = last_modified_by

    def __repr__(self):
        return "<folder: {0}>".format(self.name)

def get_credentials():
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
    credential_path = os.path.join(credential_dir,
                                   'drive-migration-tool.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def main():
    """Shows basic usage of the Google Drive API.

    Creates a Google Drive API service object and outputs the names and IDs
    for up to 10 files.
    """
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    page_token = None
    drive = Drive("backup drive")
    page_no = 1
    while True:
        # Get entire folder structure, we'll work down from here
        response = service.files().list(q="",
                                        pageSize=1000,
                                        pageToken=page_token,
                                        fields="nextPageToken, files(id, mimeType, name, owners, parents, modifiedTime, lastModifyingUser)").execute()
        results = response.get('files', [])

        # Build folder structure in memory
        for result in results:
            # Create owner
            owner = User(name=result['owners'][0]['displayName'], email=result['owners'][0]['emailAddress'])

            # Save user
            drive.add_user(owner)

            # Check if it's a root folder
            if 'parents' in result:
                parents = result['parents']
            else:
                parents = 'root'

            # Create drive item
            if result['mimeType'] == 'application/vnd.google-apps.folder':
                folder = Folder(id=result['id'], 
                                name=result['name'], 
                                owner=owner, 
                                parents=parents,
                                last_modified_time=result['modifiedTime'],
                                last_modified_by=result['lastModifyingUser'])
                drive.add_folder(folder)
            else:
                file = File(id=result['id'], 
                            name=result['name'], 
                            owner=owner, 
                            parents=parents,
                            last_modified_time=result['modifiedTime'],
                            last_modified_by=result['lastModifyingUser'])
                drive.add_file(file)

        # Look for more pages of results
        page_token = response.get('nextPageToken', None)
        page_no += 1
        if page_token is None:
            break;

    print ("Found {0} pages of results.".format(page_no))

    # Print the drive structure

    sys.exit()

    # Get the root folder id
    if ROOT_FOLDER != 'root':
        results = service.files().list(q="name = '"+ROOT_FOLDER+"' and mimeType = 'application/vnd.google-apps.folder'",
            pageSize=1000,fields="nextPageToken, files(id)").execute()
        items = results.get('files', [])

        if not items:
            print('Root folder not found...')
            sys.exit()

        root_folder_id = items[0]['id']
    else:
        root_folder_id = 'root'

    # Get the folder structure under the root folder
    results = service.files().list(q="'"+root_folder_id+"' in parents and mimeType = 'application/vnd.google-apps.folder'",
        pageSize=1000,fields="nextPageToken, files(id, name, owners, parents)").execute()
    items = results.get('files', [])
    base_folders = set()
    if not items:
        print('No files found under root folder, exiting...')
        sys.exit()
    else:
        print('Building folder structure...')
        # Build folder structure
        for item in items:
            # print('{0}: {1} ({2}) - {3}'.format(item['name'], item['lastModifyingUser']['displayName'], item['modifiedTime'], item['owners'][0]['displayName']))
            folder = Folder(id=item['id'], name=item['name'], owner=item['owners'][0]['emailAddress'])
            folder.add_children(service)
            base_folders.add(folder)

    for folder in base_folders:
        folder.print_tree()

if __name__ == '__main__':
    main()
