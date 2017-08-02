# -*- coding: utf-8 -*-
""" Google Drive Migration Tool

This script is designed to help users migrate between a source and destination
Google Drive. The script is designed to be used alongside a cloud transfer
service such as Multcloud (https://www.multcloud.com/home).

"""

# Imports
from __future__ import print_function

import os
import argparse
import logging
import time
import drive_interface
import box_interface

from oauth2client import tools


# Global variables
PATH_ROOT = 'D:'  # Root drive (set this to whatever you want)


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
                        help='Path to folder within Drive to start in (e.g. "folder/subfolder")')
    parser.add_argument('-R', '--rootbox', type=str, default=None,
                        help='Path to folder within Box to start in (e.g. "folder/subfolder")')
    parser.add_argument('-l', '--log-level', type=str, default=logging.INFO,
                        help='Logging level for output')

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
                        help='Verbose printing of the drive tree')
    parser.add_argument('-M', '--match', action='store_true',
                        help='Print a list of matched files. Must be used with the update option')
    parser.add_argument('-m', '--miss', action='store_true',
                        help='Print a list of files which were not matched. Must be used with the update option')
    parser.add_argument('-f', '--printtofile', type=str,
                        help='Save any printed information to a file.')
    parser.add_argument('-c', '--credentials', action='store_true',
                        help='Force a reset of the drive/box web credentials')
    return parser


def migrate_metadata(box, drive, print_match=False, print_miss=False, print_file=None):
    """ Move the metadata from Drive to Box

    Args:
        box (Box): The box object for metadata to be migrated to
        drive (Drive): The drive object for metadata to be migrated from
        print_match (bool, optional): Whether to print matched files
        print_miss (bool, optional): Whether to print unmatched files
        print_file (file, optional): The file to which any logging should be printed
    """

    matched_files = []
    missed_files = []
    for box_file in box.files:
        drive_file = drive.get_file_via_path(box_file.path, None)
        if drive_file:
            matched_files.append(box_file.path)
            box.apply_metadata(box_file, drive_file)
        else:
            missed_files.append(box_file.path)

    print(('Matched {0} files; missed {1} files.'.format(str(len(matched_files)),
                                                         str(len(missed_files)))).encode('utf-8'),
          file=print_file)

    if print_match:
        matched_files.sort()
        for file_path in matched_files:
            print(('\t' + file_path).encode('utf-8'), file=print_file)

    if print_miss:
        missed_files.sort()
        for file_path in missed_files:
            print(('\t' + file_path).encode('utf-8'), file=print_file)


if __name__ == '__main__':
    # Args parsing
    args = build_arg_parser().parse_args()

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

    output_file = None
    if args.printtofile:
        output_file = open(args.printtofile, 'w', encoding='utf-8')

    if args.printdrive:
        # Map and print the Drive
        src_drive = drive_interface.Drive(root_path=PATH_ROOT, reset_cred=args.credentials, flags=args)
        src_drive.print_drive(base_folder_path=PATH_ROOT, logger=None, verbose=args.verbose, output_file=output_file)
    elif args.printbox:
        # Map and print the Box
        dest_box = box_interface.Box(path_prefix=PATH_ROOT, root_directory=args.rootbox, reset_cred=args.credentials)
        dest_box.print_box(base_folder_path=None, output_file=output_file)
    elif args.updatedrive:
        update_log = logging.getLogger('update')

        update_log.info("Updating...")

        # Source Drive
        src_drive = drive_interface.Drive(root_path=PATH_ROOT, reset_cred=args.credentials, flags=args)

        # Destination Box
        dest_box = box_interface.Box(path_prefix=PATH_ROOT, root_directory=args.rootbox, reset_cred=args.credentials)

        # Update the metadata
        migrate_metadata(box=dest_box,
                         drive=src_drive,
                         print_match=args.match,
                         print_miss=args.miss,
                         print_file=output_file)
    if output_file:
        output_file.close()
