# Google-Drive-Migration-Tool

This script was developed to help users migrate between a source and destination
Google Drive. The script is designed to be used alongside a cloud transfer
service such as [Multcloud](https://www.multcloud.com/home).

The script takes a source and destination Drive, and clones the:
* Last Modifying User
* Last Modified Date
* Owner
* Permissions (TODO)

from the source to destination Drive.

Instructions on the authentication setup for the Drive API can be found 
[here](https://developers.google.com/drive/v3/web/quickstart/python).

### Notes
* The source and destination drives must have identical hierarchies for this script to work
* If there are duplicate files (ie same name, same path) then only one of the files will be updated
* The same users must exist in the destination directory (eg `john.smith` must exist in both `@source.com`, and `@dest.com`)
