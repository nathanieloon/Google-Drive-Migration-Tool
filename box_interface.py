# coding: utf-8

from __future__ import print_function, unicode_literals

import bottle
import configparser
import webbrowser

from boxsdk import Client, OAuth2, exception
from threading import Thread, Event
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

REQUEST_COUNT = 200


def _create_items(item, parent, file_list):
    if item.type == 'file':
        box_file = BoxObject(item.id, item.name, parent)
        file_list.append(box_file)
    if item.type == 'folder':
        box_folder = BoxObject(item.id, item.name, parent)
        for sub_item in _retrieve_all_items(item):
            _create_items(sub_item, box_folder, file_list)


def _retrieve_all_items(parent_folder):
    offset = 0
    all_items = None
    while True:
        new_items = parent_folder.get_items(limit=REQUEST_COUNT, offset=offset)
        if all_items is None:
            all_items = new_items
        else:
            all_items = all_items + new_items
        if len(new_items) < REQUEST_COUNT:
            return all_items
        offset += REQUEST_COUNT


def _map_child_folders(parent_folder, all_folders):
    for folder in all_folders:
        if folder.parent_id == parent_folder.id:
            folder.set_parent(parent_folder)
            _map_child_folders(folder, all_folders)


class Box(object):
    def __init__(self, path_prefix, root_directory=None, oauth_class=OAuth2, reset_cred=False, build=True, debug=False):
        self.name = 'Destination'
        self.client = None
        self.files = []
        self.folders = []
        self._owner = None
        self.path_prefix = path_prefix

        class StoppableWSGIServer(bottle.ServerAdapter):
            def __init__(self, *args, **kwargs):
                super(StoppableWSGIServer, self).__init__(*args, **kwargs)
                self._server = None

            def run(self, app):
                server_cls = self.options.get('server_class', WSGIServer)
                handler_cls = self.options.get('handler_class', WSGIRequestHandler)
                self._server = make_server(self.host, self.port, app, server_cls, handler_cls)
                self._server.serve_forever()

            def stop(self):
                self._server.shutdown()

        # Config setup
        cfg = configparser.ConfigParser()
        cfg.read('fivium_temp.cfg')
        client_id = cfg['client_info']['client_id']
        client_secret = cfg['client_info']['client_secret']

        # Verify if there is a valid token already
        if 'app_info' in cfg and not reset_cred:
            access_token = cfg.get('app_info', 'access_token')
            refresh_token = cfg.get('app_info', 'refresh_token')

            self.client = Client(oauth_class(
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token,
                refresh_token=refresh_token))
        else:
            auth_code = {}
            auth_code_is_available = Event()

            local_oauth_redirect = bottle.Bottle()

            @local_oauth_redirect.get('/')
            def get_token():
                auth_code['auth_code'] = bottle.request.query.code
                auth_code['state'] = bottle.request.query.state
                auth_code_is_available.set()

            local_server = StoppableWSGIServer(host='localhost', port=8080)
            server_thread = Thread(target=lambda: local_oauth_redirect.run(server=local_server))
            server_thread.start()

            oauth = oauth_class(
                client_id=client_id,
                client_secret=client_secret,
            )
            auth_url, csrf_token = oauth.get_authorization_url('http://localhost:8080')
            webbrowser.open(auth_url)

            auth_code_is_available.wait()
            local_server.stop()
            assert auth_code['state'] == csrf_token
            access_token, refresh_token = oauth.authenticate(auth_code['auth_code'])

            if 'app_info' not in cfg:
                cfg['app_info'] = {}

            cfg['app_info']['access_token'] = access_token
            cfg['app_info']['refresh_token'] = refresh_token
            with open('fivium_temp.cfg', 'w') as configfile:
                cfg.write(configfile)

            self.client = Client(oauth)

        if build:
            '''
            root_item = self._get_root(root_directory)
            box_items = _retrieve_all_items(self.client.folder(folder_id=root_item.id))
            for item in box_items:
                _create_items(item, root_item, self.files)
            '''

            # Setup the root
            root_folder = self._get_root_folder(root_directory)
            if debug:
                print('root folder has id: {0}'.format(str(root_folder.object_id)))
            root_object = BoxObject(identifier=root_folder.object_id, name=self.path_prefix)
            raw_files = []
            raw_folders = [root_object]

            # Retrieve all descendant files of the root
            offset = 0
            while True:
                retrieved_files = self.client.search(query='a b c d e f g h i j k l m n o p q r s t u v w y z A B C D E F G H I J K L M N O P Q R S T U V W X Y Z 0 1 2 3 4 5 6 7 8 9',
                                                     limit=REQUEST_COUNT,
                                                     offset=offset,
                                                     result_type='file')

                if debug:
                    print('retreived files #{0} to #{1}'.format(str(offset + 1), str(offset + len(retrieved_files))))
                offset += REQUEST_COUNT

                for box_file in retrieved_files:
                    raw_files.append(BoxObject(identifier=box_file.id,
                                               name=box_file.name,
                                               parent_id=box_file.parent['id'] if box_file.parent else None))

                if len(retrieved_files) < REQUEST_COUNT:
                    # No more files
                    break

            # Retrieve all descendant folders of the root
            offset = 0
            while True:
                retrieved_folders = self.client.search(query='a b c d e f g h i j k l m n o p q r s t u v w y z A B C D E F G H I J K L M N O P Q R S T U V W X Y Z 0 1 2 3 4 5 6 7 8 9',
                                                       limit=REQUEST_COUNT,
                                                       offset=offset,
                                                       result_type='folder')

                if debug:
                    print('retreived folders #{0} to #{1}'.format(str(offset + 1),
                                                                  str(offset + len(retrieved_folders))))
                offset += REQUEST_COUNT

                for box_folder in retrieved_folders:
                    raw_folders.append(BoxObject(identifier=box_folder.id,
                                                 name=box_folder.name,
                                                 parent_id=box_folder.parent['id'] if box_folder.parent else None))

                if len(retrieved_folders) < REQUEST_COUNT:
                    # No more files
                    break

            # Map the parents
            _map_child_folders(root_object, raw_folders)
            for file in raw_files:
                for folder in raw_folders:
                    if file.parent_id == folder.id:
                        file.set_parent(folder)
                        break

            # omit files marked for deletion TODO: remove this for final migration
            for file in raw_files:
                if not (file.path and 'zz. Duplicates to be deleted' in file.path):
                    self.files.append(file)

            for folder in raw_folders:
                if not (folder.path and 'zz. Duplicates to be deleted' in folder.path):
                    self.folders.append(folder)

            if debug:
                print('Mapped {0} files and {1} folders'.format(str(len(self.files)), str(len(self.folders))))
                for folder in self.folders:
                    if folder.path is None:
                        print("Found an orphaned folder with name {0} and id {1}".format(folder.name, str(folder.id)))
                for file in self.files:
                    if file.path is None:
                        print("Found an orphaned file with name {0} and id {1}".format(file.name, str(file.id)))

    @property
    def owner(self):
        # TODO: make this return something useful
        return ''

    def _get_root(self, root_directory):
        root_box_folder = self._get_root_folder(root_directory)
        return BoxObject(root_box_folder.id, self.path_prefix, None)

    def _get_root_folder(self, root_directory):
        current_folder = self.client.folder('0')
        if root_directory is None:
            return current_folder
        paths = root_directory.split('/')
        for path_item in paths:
            box_items = _retrieve_all_items(current_folder)
            found_path = False
            for box_item in box_items:
                if box_item.type == 'folder' and box_item.name == path_item:
                    found_path = True
                    current_folder = box_item
                    break
            if not found_path:
                raise FileNotFoundError('Couldn\'t find the root folder <{0}> in box'.format(root_directory))
        return current_folder

    def apply_metadata(self, box_file, drive_file):
        metadata = self.client.file(box_file.id).metadata('enterprise', 'legacyData')
        try:
            if metadata.get() is None:
                metadata.create({'owner': drive_file.owner.name,
                                 'legacyCreatedDate': drive_file.created_time,
                                 'legacyLastModifyingUser': drive_file.last_modified_by.name,
                                 'legacyLastModifiedDate': drive_file.last_modified_time})
        except exception.BoxAPIException:
            metadata.create({'owner': drive_file.owner.name,
                             'legacyCreatedDate': drive_file.created_time,
                             'legacyLastModifyingUser': drive_file.last_modified_by.name,
                             'legacyLastModifiedDate': drive_file.last_modified_time})


class BoxObject(object):
    """ File representation class

    Args:
        identifier (str): Google Drive ID of the file
        name (str): Name of the file
        parent ([str]): List of parent IDs

    Attributes:
        id (str): Google Drive ID of the file
        name (str): Name of the file
        parent ([str]): List of parent IDs
        path (str): Path to the file within the Drive

    """

    def __init__(self,
                 identifier,
                 name,
                 parent=None,
                 parent_id=None):
        self.id = identifier
        self.name = name
        if '002f' in self.name:
            self.name = self.name.replace('002f', '/')
            self.name = self.name.replace(' - Modify', '')
        self.parent = parent
        self.parent_id = parent_id
        self.path = None

        if self.parent is not None:
            self.path = self.parent.path + '/' + self.name
        elif self.parent_id is None:
            self.path = name

    def __repr__(self):
        return "<file: {0}>".format(self.name)

    def set_parent(self, parent):
        self.parent = parent
        self.path = self.parent.path + '/' + self.name
