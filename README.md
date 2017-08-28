# Google Drive Migration Tool (GDMT)

This script was developed to help users migrate from Google Drive to Box.
The script is designed to be used alongside a cloud transfer
service such as [Multcloud](https://www.multcloud.com/home).

The script takes a source and destination Drive, and clones the:
* Created Date
* Last Modified Date
* Last Modifying User
* Owner

from Drive to Box, storing them as custom metadata.

## Installation
Instructions on the authentication setup for the Drive API can be found
[here](https://developers.google.com/drive/v3/web/quickstart/python).

Instructions for the Box API can be found
[here](http://opensource.box.com/box-python-sdk/).

This project was built for Python3, so you'll run into unicode errors in Python2.

Requirements can be installed with the command:
` pip install -r requirements.txt `

## Setup
To setup the tool first run `python3 drive-migration-tool.py -S`.
The script will prompt you to login twice, the first login is
Google Drive, and the second is Box. The script will then output
the user/email of the accounts associated with the tool.

You can use `python3 drive-migration-tool.py -s`
to check the status of the tool.

## Usage
``` 
usage: drive-to-box-migration-tool.py [-h] [-r ROOTDRIVE] [-R ROOTBOX]
                                      [-l LOG_LEVEL]
                                      (-S | -s | -p | -P | -u | -t) [-v] [-a]
                                      [-f PRINTTOFILE] [-c]

Google Drive Migration Tool.

optional arguments:
  -h, --help            show this help message and exit
  -r ROOTDRIVE, --rootdrive ROOTDRIVE
                        Path to folder within Drive to start in (e.g.
                        "folder/subfolder")
  -R ROOTBOX, --rootbox ROOTBOX
                        Path to folder within Box to start in (e.g.
                        "folder/subfolder")
  -l LOG_LEVEL, --log-level LOG_LEVEL
                        Logging level for output
  -S, --setup           Setup connections to Drive and Box
  -s, --status          Check the status of the connections to Drive and Box
  -p, --printdrive      Print the source Drive
  -P, --printbox        Print the destination Box
  -u, --update          Update the destination Box using the metadata from the
                        source Drive
  -t, --testmigrate     Test the migration only - don't write any metadata
  -v, --verbose         Verbose printing of the drive tree
  -a, --printall        Print a list of matched files, missed files, and
                        possible duplicates. Must be used with the update
                        option
  -f PRINTTOFILE, --printtofile PRINTTOFILE
                        Save any printed information to a file.
  -c, --credentials     Force a reset of the drive/box web credentials


```

## Notes
* The source and destination drives must have identical hierarchies from
the specified subfolder onward for this script to work.
* If there are duplicate files (ie same name, same path) then only one
of the files will be updated. use the --printall option to see a list
of any duplicates that the migration detects