from __future__ import print_function
import httplib2
import os
import sys

from apiclient import discovery, errors
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
SCOPES = 'https://www.googleapis.com/auth/drive.metadata'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Drive Migration Tool'


class Drive():
    """ Google Drive representation class
    """
    def __init__(self, name, service):
        self.name = name
        self.folders = set()
        self.files = set()
        self.users = set()
        self.service = service

        # Initialise the drive
        self.build_drive()

    def add_folder(self, folder):
        """ Add a folder to the drive
        """
        self.folders.add(folder)

    def add_file(self, file):
        """ Add a file to the drive
        """
        self.files.add(file)

    def get_folder(self, name=None, id=None, parent=None):
        """ Get a folder by name or id
        """
        for folder in self.folders:
            if parent:
                parent_folder = self.get_folder(name=parent)
                if (folder.id == id or folder.name == name) and parent_folder.id in folder.parents:
                    return folder
            else:
                if folder.id == id or folder.name == name:
                    return folder

        print ("Could not find the folder with name: <{0}>, id: <{1}>, and parent: <{2}>. Aborting.".format(name, id, parent))
        return None

    def get_folders(self, name=None, id=None, parent=None):
        """ Get a list of folders which have a certain name
        """
        folder_set = set()
        for folder in self.folders:
            if parent:
                parent_folder = self.get_folder(name=parent)
                if (folder.id == id or folder.name == name) and parent_folder.id in folder.parents:
                    folder_set.add(folder)
            else:
                if folder.id == id or folder.name == name:
                    folder_set.add(folder)

        if len(folder_set) > 0:
            return folder_set
        else:
            print ("Could not find a folder with name: <{0}>, id: <{1}>, and parent: <{2}>. Aborting.".format(name, id, parent))
            sys.exit()

    def get_file(self, name=None, id=None, parent=None):
        """ Get a file by name or id
        """
        for file in self.files:
            if parent:
                possible_folders = self.get_folders(name=parent)
                for parent_folder in possible_folders:
                    if (file.id == id or file.name == name) and parent_folder.id in file.parents:
                        # print ("Found file <{0} - {1}> in folder <{2} - {3}>".format(file.id, file.name, parent_folder.id, parent_folder.name))
                        return file
            else:
                if file.id == id or file.name == name:
                    return file

        print ("Could not find the file with name: <{0}>, id: <{1}>, and parent: <{2}> in <{3}>. Aborting.".format(name, id, parent, self.name))
        sys.exit()

    def print_drive(self, verbose=False, root='root', parent=None, curr_folder=None, prefix=""):
        """ Print the drive structure from the given root folder
        """
        # If we're looking at the root, set it as the current folder
        if not curr_folder:
            curr_folder = self.get_folder(name=root, parent=parent)

        # Print the current folder
        if verbose:
            print (prefix + curr_folder.id, curr_folder.name.encode('utf-8') + " ("+curr_folder.owner.name.encode('utf-8')+")" + " ("+curr_folder.last_modified_time.encode('utf-8')+")" + " ("+curr_folder.last_modified_by.email.encode('utf-8')+")")
        else:
            print (prefix + curr_folder.name.encode('utf-8'))

        # Print file(s)
        for file in self.files:
            if curr_folder.id in file.parents:
                if verbose:
                    print (prefix + "\t" + file.id, file.name.encode('utf-8') + " ("+file.owner.name.encode('utf-8')+")" + " ("+file.last_modified_time.encode('utf-8')+")" + " ("+file.last_modified_by.email.encode('utf-8')+")")
                else:
                    print (prefix + "\t" + file.name.encode('utf-8'))

        # Print child folder(s)
        for folder in self.folders:
            if curr_folder.id in folder.parents:
                self.print_drive(verbose=verbose, curr_folder=folder, prefix=prefix+"\t")

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

    def update_info(self, user):
        """ Update the owner and last known user for a file/folder
        """
        pass

    def update_last_modified_info(self, src_item, dest_item):
        """ Update the supplied drive item with the last known modified date and modifying user
        """
        try:
            # Build the updated payload
            body = {"modifiedTime": src_item.last_modified_time}

            # Send the file back
            response = self.service.files().update(fileId=dest_item.id, 
                                        body=body).execute()

            print (response)

            print ("Successfully updated <{0}> in drive <{1}>.".format(dest_item.name.encode('utf-8'), self.name))

        except errors.HttpError, error:
            print ("An error occurred: {0}".format(error))
            sys.exit()

    def build_drive(self):
        """ Build the Google drive for the given service
        """
        page_token = None
        page_no = 1
        print ("Retrieving drive data for <{0}>...".format(self.name))
        while True:
            # Get entire folder structure, we'll work down from here
            response = self.service.files().list(q="trashed = false",
                                            pageSize=1000,
                                            pageToken=page_token,
                                            fields="nextPageToken, files(id, mimeType, name, owners, parents, modifiedTime, lastModifyingUser)").execute()
            results = response.get('files', [])

            # Build folder structure in memory
            for result in results:
                # Create owner
                owner = User(name=result['owners'][0]['displayName'], email=result['owners'][0]['emailAddress'])
                self.add_user(owner)

                # Save last modifying user, if it exists
                if 'emailAddress' in result['lastModifyingUser']:
                    modified_by = User(name=result['lastModifyingUser']['displayName'], email=result['lastModifyingUser']['emailAddress'])
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
                    folder = Folder(id=result['id'], 
                                    name=result['name'], 
                                    owner=owner, 
                                    parents=parents,
                                    last_modified_time=result['modifiedTime'],
                                    last_modified_by=modified_by)
                    self.add_folder(folder)
                else:
                    file = File(id=result['id'], 
                                name=result['name'], 
                                owner=owner, 
                                parents=parents,
                                last_modified_time=result['modifiedTime'],
                                last_modified_by=modified_by,
                                mime_type=result['mimeType'])
                    self.add_file(file)

            # Look for more pages of results
            page_token = response.get('nextPageToken', None)
            page_no += 1
            if page_token is None:
                break;

        print ("Found <{0}> pages of results for <{1}>. Drive has been built.".format(page_no, self.name))

class User():
    """ User representation class
    """
    def __init__(self, name, email):
        self.name = name
        self.email = email

    def __repr__(self):
        return "<user: {0}>".format(self.email)

class File():
    """ File representation class
    """
    def __init__(self, id, name, owner, parents, last_modified_time, last_modified_by, mime_type):
        self.id = id
        self.name = name
        self.parents = parents
        self.owner = owner
        self.last_modified_time = last_modified_time
        self.last_modified_by = last_modified_by
        self.mime_type = mime_type

    def __repr__(self):
        return "<file: {0}>".format(self.name)

class Folder():
    """ Folder representation class
    """
    def __init__(self, id, name, owner, parents, last_modified_time, last_modified_by):
        self.id = id
        self.name = name
        self.parents = parents
        self.owner = owner
        self.last_modified_time = last_modified_time
        self.last_modified_by = last_modified_by

    def __repr__(self):
        return "<folder: {0}>".format(self.name)

def get_credentials(src):
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
        credential_path = os.path.join(credential_dir,
                                   'src-drive-migration-tool.json')
    else:
        credential_path = os.path.join(credential_dir,
                                   'dest-drive-migration-tool.json')

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
    # Source account credentials
    src_credentials = get_credentials('src')
    src_http = src_credentials.authorize(httplib2.Http())
    src_service = discovery.build('drive', 'v3', http=src_http)

    # Destination account credentials
    dest_credentials = get_credentials('dest')
    dest_http = dest_credentials.authorize(httplib2.Http())
    dest_service = discovery.build('drive', 'v3', http=dest_http)

    src_drive = Drive("source drive", src_service)
    dest_drive = Drive("destination drive", dest_service)

    # Print the drive structure
    # print ("Printing source drive structure.")
    # print ("Printing destination drive structure.")

    # Test updating file
    fname = 'cr53_cop_bug.pdf'
    parent = 'cr53_bugs'
    src_file = src_drive.get_file(name=fname, parent=parent)
    dest_file = dest_drive.get_file(name=fname, parent=parent)
    dest_drive.update_last_modified_info(src_file, dest_file)

if __name__ == '__main__':
    main()
