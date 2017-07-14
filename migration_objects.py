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

    def __init__(self, identifier, name, owner, parents, created_time, last_modified_time, last_modified_by, mime_type):
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
