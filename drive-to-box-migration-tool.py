# -*- coding: utf-8 -*-
""" Google Drive Migration Tool

This script is designed to help users migrate between a source and destination
Google Drive. The script is designed to be used alongside a cloud transfer
service such as Multcloud (https://www.multcloud.com/home).

"""

# Imports
from __future__ import print_function

import os
import sys
import argparse
import logging
import time
import drive_interface
import box_interface

from oauth2client import tools


# Global variables
PATH_ROOT = 'D:'                                    # Root drive (set this to whatever you want)
UPDATE_OWNER = False                                # Option for updating the owner of the file to a new domain
UPDATE_PERMISSIONS = False                          # Update file/folder permissions
NEW_DOMAIN = None                                   # New domain to migrate to


def build_arg_parser():
    """ Build and return an args parser

    Returns:
        argparse: Args parser
    """
    # Primary parser

    parser = argparse.ArgumentParser(
        description='Google Drive Migration Tool.', parents=[tools.argparser])

    # Hide all of the Google API options
    for action in parser._actions:
        if action.dest != 'help':
            action.help = argparse.SUPPRESS

    parser.add_argument('-r', '--rootdrive', type=str, default=None,
                        help='Path to folder within Drive to start in (eg "D:/test"). Defaults to root Drive directory')
    parser.add_argument('-R', '--rootbox', type=str, default=None,
                        help='Path to folder within Box to start in (eg "D:/test"). Defaults to root Drive directory')
    parser.add_argument('-l', '--log-level', type=str, default=logging.INFO,
                        help='Logging level for output')
    parser.add_argument('-c', '--credentials', type=str, default=logging.INFO,
                        help='Force a reset of the drive/box web credentials')

    # Function group
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--printdrive', action='store_true',
                       help='Print the source Drive')
    group.add_argument('-P', '--printbox', action='store_true',
                       help='Print the destination Box')
    group.add_argument('-u', '--updatedrive', action='store_true',
                       help='Update the destination Box using the metadata from the source Drive')

    # Verbose printing
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose printing of the tree')
    parser.add_argument('-M', '--match', action='store_true',
                        help='Print a list of matched files. Must be used with the update option')
    parser.add_argument('-m', '--miss', action='store_true',
                        help='Print a list of files which were not matched. Must be used with the update option')
    parser.add_argument('-f', '--printtofile', type=str,
                        help='Save any printed information to a file.')
    return parser


def migrate_metadata(box, drive, print_match=False, print_miss=False, printFile=None):
    matched_files = []
    missed_files = []
    for box_file in box.files:
        drive_file = drive.get_file_via_path(box_file.path, None)
        if drive_file:
            matched_files.append(box_file.path)
            box.apply_metadata(box_file, drive_file)
        else:
            missed_files.append(box_file.path)

    print('Matched {0} files; missed {1} files.'.format(str(len(matched_files)), str(len(missed_files))))

    if print_match:
        matched_files.sort()
        print("Matched {0} files:".format(str(len(matched_files))))
        for file_path in matched_files:
            print('\t' + file_path)

    if print_miss:
        print("Failed to match {0} files:".format(str(len(missed_files))))
        missed_files.sort()
        for file_path in missed_files:
            print('\t' + file_path)


def main():
    # Args parsing
    parser = build_arg_parser()
    args = parser.parse_args()

    # Setup logger
    timestr = time.strftime("%Y%m%d-%H%M%S")
    if not os.path.exists('logs'):
        os.makedirs('logs')
    logging.basicConfig(filename='logs/'+timestr+'.log', level=args.log_level)
    # Suppress all the google error messages
    logging.getLogger('googleapiclient').setLevel(logging.CRITICAL)
    logging.getLogger('oauth2client.transport').setLevel(logging.CRITICAL)
    logging.getLogger('oauth2client.client').setLevel(logging.CRITICAL)
    logging.getLogger().addHandler(logging.StreamHandler())

    # Log args
    logging.info('Starting Google Drive Migration Tool')
    log_arg = logging.getLogger('args')
    log_arg.debug(args)

    if args.printdrive:
        # Source account credentials
        src_drive = drive_interface.Drive(root_path=PATH_ROOT, reset_cred=True, flags=args)
        drive_interface.print_wrapper(args.root, src_drive, args.verbose, args.printtofile, args.generate_xml)
    elif args.printbox:
        # Destination account credentials
        dest_box = box_interface.Box(path_prefix=PATH_ROOT, root_directory=args.rootbox, reset_cred=True)
        drive_interface.print_wrapper(args.root, dest_box, args.verbose, args.printtofile, args.generate_xml)
    elif args.updatedrive:
        update_log = logging.getLogger('update')
        # Check --newdomain is set
        if (args.updateowner or args.updateperm) and args.newdomain is None:
            parser.error("--updateuser and --updateperm require --newdomain")

        update_log.info("Updating...")
        src_drive = drive_interface.Drive(root_path=PATH_ROOT, reset_cred=True, flags=args)

        # Destination account credentials
        dest_box = box_interface.Box(path_prefix=PATH_ROOT, root_directory=args.rootbox, reset_cred=True)

        # Update the drive
        migrate_metadata(box=dest_box, drive=src_drive)


if __name__ == '__main__':
    main()
