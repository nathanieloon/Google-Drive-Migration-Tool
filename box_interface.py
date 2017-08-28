# coding: utf-8

from __future__ import print_function, unicode_literals

import bottle
import configparser
import webbrowser

from boxsdk import Client, OAuth2, exception
from threading import Thread, Event
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

CONFIG_FILE = 'box_app.cfg'
REQUEST_COUNT = 200


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


def print_credentials(force_reset=False, logger=None):
    user_email = _authenticate(force_reset, logger).user(user_id='me').get().login
    if logger:
        logger.info('Logged into Box with username: {0}'.format(user_email))


def _authenticate(force_reset=False, logger=None):
    # Config setup
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)

    # Verify if there is a valid token already
    if 'app_info' in cfg and not force_reset:
        if logger:
            logger.info('Using existing credentials')
        client = Client(OAuth2(
            client_id=cfg['client_info']['client_id'],
            client_secret=cfg['client_info']['client_secret'],
            access_token=cfg['app_info']['access_token'],
            refresh_token=cfg['app_info']['refresh_token']))

        try:
            # Make a request to check it's authenticated
            if logger:
                logger.info('Testing existing connection')
            client.user(user_id='me').get()
        except exception.BoxOAuthException:
            if logger:
                logger.info('Resetting connection to Box')
            return _reset_authentication(cfg=cfg, logger=logger)

        return client

    return _reset_authentication(cfg=cfg, logger=logger)


def _reset_authentication(cfg, logger=None):
    if logger:
        logger.info('Fetching new credentials')
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

    oauth = OAuth2(
        client_id=cfg['client_info']['client_id'],
        client_secret=cfg['client_info']['client_secret'],
    )
    auth_url, csrf_token = oauth.get_authorization_url('http://localhost:8080')
    webbrowser.open(auth_url)

    auth_code_is_available.wait()
    local_server.stop()
    assert auth_code['state'] == csrf_token
    access_token, refresh_token = oauth.authenticate(auth_code['auth_code'])

    client = Client(oauth)

    try:
        # Make a request to check it's authenticated
        client.user(user_id='me').get()
    except exception.BoxOAuthException as err:
        if logger:
            logger.error("Failed to authenticate to Box: {0}".format(err))

    if 'app_info' not in cfg:
        cfg['app_info'] = {}

    cfg['app_info']['access_token'] = access_token
    cfg['app_info']['refresh_token'] = refresh_token
    with open(CONFIG_FILE, 'w') as configfile:
        cfg.write(configfile)

    return client


def _retrieve_all_items(parent_folder):
    """ Retrieve from the client all child items of a folder

    Args:
        parent_folder (item): the parent for which to get all children

    Returns:
        [item]: all items in Box which are children of parent_folder

    """

    offset = 0
    all_items = None
    while True:
        new_items = parent_folder.get_items(limit=REQUEST_COUNT, offset=offset)
        if all_items is None:
            all_items = new_items
        elif new_items:
            all_items = all_items + new_items

        if len(new_items) < REQUEST_COUNT:
            return all_items
        offset += REQUEST_COUNT


class Box(object):
    """ Representation of the entire file hierarchy within Box

    Args:
        path_prefix (str): The prefix to be added to each path
        root_directory (str, optional): The path within Box to treat as the root
        reset_cred (bool, optional): Whether to force a reset of the account credentials
        logger (logger, optional): Logging file

    Attributes:
        client (client): Client through which Box's API is interfaced
        files ([BoxObject]): All files in the Box
        folders([BoxObject]): All folders in the Box
        path_prefix (str): The prefix added to each path
    """

    def __init__(self, path_prefix, root_directory=None, reset_cred=False, logger=None):
        self.client = None
        self.files = []
        self.folders = []
        self.path_prefix = path_prefix
        self.root_directory = root_directory

        if logger:
            logger.info('Connecting to Box.com')

        self.client = _authenticate(reset_cred, logger)

        if logger:
            logger.info('Connection successful. Mapping Box.')

        # Build the Box:

        # Setup the root
        root_folder = self._get_root_folder(root_directory)
        if logger:
            logger.debug('root folder has id: {0}'.format(str(root_folder.object_id)))
        root_object = BoxObject(identifier=root_folder.object_id, name=self.path_prefix)
        self.files = []
        self.folders = [root_object]

        self._build_child_items(root_object)

        if logger:
            logger.debug('Mapped {0} files and {1} folders'.format(str(len(self.files)), str(len(self.folders))))
            for folder in self.folders:
                if folder.path is None:
                    logger.debug("Found an orphaned folder with name {0} and id {1}".format(folder.name,
                                                                                            str(folder.id)))
            for file in self.files:
                if file.path is None:
                    logger.debug("Found an orphaned file with name {0} and id {1}".format(file.name, str(file.id)))

        if logger:
            logger.info('Mapping complete.')

    def _get_root_folder(self, root_directory):
        """ Get the box object corresponding to the folder at a given root path

        Args:
            root_directory (str): The path at which to search. If none is specified, gives the overall root
        """
        current_folder = self.client.folder('0')
        if root_directory is None:
            return current_folder
        if root_directory.startswith(self.path_prefix):
            root_directory = root_directory.replace(self.path_prefix + '/', '')
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
                raise FileNotFoundError('Couldn\'t find the root folder <{0}> in Box'.format(root_directory))
        return current_folder

    def _build_child_items(self, parent_folder):
        children = _retrieve_all_items(self.client.folder(folder_id=parent_folder.id))
        for child in children:
            if child.type == 'folder':
                child_folder = BoxObject(identifier=child.object_id, name=child.name, parent=parent_folder)
                self.folders.append(child_folder)
                self._build_child_items(child_folder)
            else:
                child_file = BoxObject(identifier=child.object_id, name=child.name, parent=parent_folder)
                self.files.append(child_file)

    def apply_metadata(self, box_file, drive_file):
        """ Apply the metadata from a Drive file to a matched Box file, based on

        Args:
            box_file (BoxObject): File to which to apply the metadata
            drive_file (Drive.File): File from which to get the metadata
        """

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
            logger.error("Could not find file at <{0}> in Box.".format(path))
        return None

    def print_box(self, output_file=None):
        """ Print the Box, starting from a specified path

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


class BoxObject(object):
    """ File representation class

    Args:
        identifier (str): Box ID of the file
        name (str): Name of the file
        parent (BoxObject): List of parent IDs

    Attributes:
        id (str): ID of the file
        name (str): Name of the file
        parent (BoxObject): Parent object
        path (str): Path to the file within Box
    """

    def __init__(self,
                 identifier,
                 name,
                 parent=None):

        self.id = identifier
        self.name = name
        self.path = None

        # Accommodate for Box replacing '/' within file names for imported files
        if '002f' in self.name:
            self.name = self.name.replace('002f', '/')
            self.name = self.name.replace(' - Modify', '')

        self.parent = parent
        if self.parent:
            self.path = (self.parent.path if self.parent.path else self.parent.name) + '/' + self.name

    def __repr__(self):
        return "<file: {0}>".format(self.name)
