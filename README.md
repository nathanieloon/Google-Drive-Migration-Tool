# Google Drive Migration Tool (GDMT)

This script was developed to help users migrate between a source and destination
Google Drive. The script is designed to be used alongside a cloud transfer
service such as [Multcloud](https://www.multcloud.com/home).

The script takes a source and destination Drive, and clones the:
* Last Modifying User
* Last Modified Date
* Owner
* Permissions
* Activity History (TODO)

from the source to destination Drive.

## Installation
Instructions on the authentication setup for the Drive API can be found 
[here](https://developers.google.com/drive/v3/web/quickstart/python).

This project was built for Python3, so you'll run into unicode errors in Python2.

Requirements can be installed with the command:
` pip install -r requirements.txt `

## Setup
To setup the tool first run `python3 drive-migration-tool.py -S`. The script will prompt you to login twice, the first login is the source drive, and the second is the destination drive. The script will then output the user/email of the accounts associated with the tool. You can use `python3 drive-migration-tool.py -s` to check the status of the tool.

## Usage
``` 
usage: drive-migration-tool.py [-h] [-r ROOT] [-f PREFIX]
                               (-p | -P | -u | -s | -S) [-v] [-F PRINTTOFILE]
                               [-x GENERATE_XML] [-uo] [-d NEWDOMAIN] [-up]

Google Drive Migration Tool.

optional arguments:
  -h, --help            show this help message and exit
  -r ROOT, --root ROOT  Path to folder to start in (eg "D:/test"). Defaults to
                        root Drive directory
  -f PREFIX, --prefix PREFIX
                        Prefix letter for the drive (eg "D")
  -p, --printsrc        Print the source Drive
  -P, --printdest       Print the destination Drive
  -u, --updatedrive     Update the destination Drive using the meta data from
                        the source Drive
  -s, --status          Display the current logins for the Drives
  -S, --setup           Setup the logins for the Drives
  -v, --verbose         Verbose printing of the tree
  -F PRINTTOFILE, --printtofile PRINTTOFILE
                        Save the tree to a file instead of stdout. Must be
                        used with one of the print Drive options.
  -x GENERATE_XML, --generate-xml GENERATE_XML
                        Output the tree to an XML file. Must be used with one
                        of the print Drive options.
  -uo, --updateowner    Flag for updating the owner to the new domain
  -d NEWDOMAIN, --newdomain NEWDOMAIN
                        Destination domain (eg "test.com")
  -up, --updateperm     Flag for updating the permissions for the file to the
                        new domain
```

## Notes
* The source and destination drives must have identical hierarchies for this script to work
* If there are duplicate files (ie same name, same path) then only one of the files will be updated
* The same users must exist in the destination directory (eg `john.smith` must exist in both `@source.com`, and `@dest.com`)
