from __future__ import print_function
import httplib2
import os

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

class Folder():
    def __init__(self, id, name, owner, parent=None):# last_modified_time, last_modified_by):
        self.id = id
        self.name = name
        self.parent = parent
        self.owner = owner
        # self.last_modified_time = last_modified_time
        # self.last_modified_by = last_modified_by

        # Set of children
        self.children = set()

    def __repr__(self):
        return "<folder: {0}>".format(self.name)

    def add_children(self, service):
        results = service.files().list(q="'"+self.id+"' in parents and mimeType = 'application/vnd.google-apps.folder'",
        pageSize=100,fields="nextPageToken, files(id, name, lastModifyingUser, modifiedTime, owners, parents)").execute()
        folders = results.get('files', [])
        for folder in folders:
            f = Folder(id=folder['id'], name=folder['name'], owner=folder['owners'][0]['emailAddress'])
            self.add_child(f)
            f.add_children(service)

    def get_children(self):
        return self.children

    def print_tree(self, prefix=""):
        print (prefix + self.name)
        for child in self.children:
            child.print_tree(prefix+"\t")

    def add_child(self, child):
        self.children.add(child)

    def remove_child(self, child):
        self.children.remove(child)

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

    results = service.files().list(q="'0B5w31e16GyAGa1RaaVNGaVNUWGs' in parents and mimeType = 'application/vnd.google-apps.folder'",
        pageSize=100,fields="nextPageToken, files(id, name, lastModifyingUser, modifiedTime, owners, parents)").execute()
    items = results.get('files', [])
    root_folders = set()
    if not items:
        print('No files found.')
    else:
        print('Files:')
        for item in items:
            # print('{0}: {1} ({2}) - {3}'.format(item['name'], item['lastModifyingUser']['displayName'], item['modifiedTime'], item['owners'][0]['displayName']))
            folder = Folder(id=item['id'], name=item['name'], owner=item['owners'][0]['emailAddress'])
            folder.add_children(service)
            root_folders.add(folder)

    print (root_folders)
    for folder in root_folders:
        folder.print_tree()

if __name__ == '__main__':
    main()
