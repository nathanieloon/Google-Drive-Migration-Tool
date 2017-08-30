# -*- coding: utf-8 -*-
""" Google Drive Migration Tool

This script is designed to migrate metadata from Google Drive to Box.
The script is designed to be used alongside a cloud transfer service
such as Multcloud (https://www.multcloud.com/home).

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

    parser.add_argument('-r', '--rootdrive', type=str, default=None, metavar='PATHTOROOT',
                        help='Path to folder within Drive to start in (e.g. "folder/subfolder")')
    parser.add_argument('-R', '--rootbox', type=str, default=None, metavar='PATHTOROOT',
                        help='Path to folder within Box to start in (e.g. "folder/subfolder")')
    parser.add_argument('-l', '--loglevel', type=str, default=logging.INFO,
                        help='Logging level for output')

    # Function group
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-S', '--setup', action='store_true',
                       help='Setup connections to Drive and Box')
    group.add_argument('-s', '--status', action='store_true',
                       help='Check the status of the connections to Drive and Box')
    group.add_argument('-p', '--printdrive', action='store_true',
                       help='Print the source Drive')
    group.add_argument('-P', '--printbox', action='store_true',
                       help='Print the destination Box')
    group.add_argument('-u', '--update', action='store_true',
                       help='Update the destination Box using the metadata from the source Drive')
    group.add_argument('-t', '--testmigrate', action='store_true',
                       help='Test the migration only - don\'t write any metadata')
    group.add_argument('-k', '--checkmetadata', type=str, default=None, metavar='METADATANAME',
                       help='Check which files within a Box directory have metadata of the specified type')

    # Verbose printing
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose printing of the drive tree')
    parser.add_argument('-a', '--printall', action='store_true',
                        help='Print a list of matched files, missed files, and possible duplicates. \
                              Must be used with the update option')
    parser.add_argument('-f', '--printtofile', type=str, metavar='FILENAME',
                        help='Save any printed information to a file.')
    parser.add_argument('-c', '--credentials', action='store_true',
                        help='Force a reset of the drive/box web credentials')
    return parser


def migrate_metadata(box, drive, print_details=False, print_file=None, logger=None, test_only=True):
    """ Move the metadata from Drive to Box

    Args:
        box (Box): The box object for metadata to be migrated to
        drive (Drive): The drive object for metadata to be migrated from
        print_details (bool, optional): Whether to print details of matched, missed, and duplicate files
        print_file (file, optional): The file to which any logging should be printed
        logger (logger, optional): Logging file
        test_only (bool, optional): Whether to update the metadata in Box
    """

    if logger:
        logger.debug('Matching files between Drive:/{0} and Box:/{1}'.format(drive.root, box.path))

    matched_files = []
    existing_metadata_files = []
    box_missed_files = []
    drive_missed_files = []
    duplicate_files = []

    for box_file in box.files:
        if box_file.path:
            box_missed_files.append(box_file.path)

    for drive_file in drive.files:
        if drive_file.path:
            box_file = box.get_file_via_path(drive_file.path, logger=None)
            if box_file:
                if not test_only:
                    if box.apply_metadata(box_file, drive_file):
                        matched_files.append(drive_file.path)
                        if logger:
                            logger.debug('Wrote metadata at {0}'.format(drive_file.path))
                    else:
                        existing_metadata_files.append(drive_file.path)
                        if logger:
                            logger.debug('Metadata already exists at {0}'.format(drive_file.path))
                else:
                    matched_files.append(drive_file.path)
                    if logger:
                        logger.debug('Matched metadata at {0}'.format(drive_file.path))
                try:
                    box_missed_files.remove(box_file.path)
                except ValueError:
                    # Add to the duplicates list if we've already matched a file at this path
                    duplicate_files.append(box_file.path)
                    if logger:
                        logger.debug('Found a duplicate at {0}'.format(drive_file.path))

            else:
                drive_missed_files.append(drive_file.path)
                if logger:
                    logger.debug('Failed to match file at {0}'.format(drive_file.path))

    if print_details:
        if test_only:
            print_list(list_to_print=matched_files,
                       header_message='Matched paths for {0} Files:'.format(str(len(matched_files))),
                       print_file=print_file)

        else:
            print_list(list_to_print=existing_metadata_files,
                       header_message='Found existing metadata for {0} matched Files:'.format(str(len(existing_metadata_files))),
                       print_file=print_file)

            print_list(list_to_print=matched_files,
                       header_message='Added metadata for {0} matched Files:'.format(str(len(matched_files))),
                       print_file=print_file)

        print_list(list_to_print=drive_missed_files,
                   header_message='Failed to Match {0} File paths from Drive:'.format(str(len(drive_missed_files))),
                   print_file=print_file)

        print_list(list_to_print=box_missed_files,
                   header_message='Failed to Match {0} File pathss from Box:'.format(str(len(box_missed_files))),
                   print_file=print_file)

        print_list(list_to_print=duplicate_files,
                   header_message='Found {0} Duplicate Files:'.format(str(len(duplicate_files))),
                   print_file=print_file)


def check_metadata(box, metadata_name, print_file=None, logger=None):
    """ Check for metadata of the specified type on files in Box

    Args:
        box (Box): The list to be printed
        metadata_name (str): The name of the metadata to search for
        print_file (file, optional): The file to which any logging should be printed
        logger (logger, optional): Logging file
    """

    hits = []
    misses = []
    for file in box.files:
        if box.check_metadata(file, metadata_name):
            hits.append(file.path)
            if logger:
                logger.debug('Found metadata for {0}'.format(file.path))
        else:
            misses.append(file.path)
            if logger:
                logger.debug('Failed to find metadata for {0}'.format(file.path))

    print_list(list_to_print=hits,
               header_message='Found metadata for {0} File Paths:'.format(str(len(hits))),
               print_file=print_file)

    print_list(list_to_print=misses,
               header_message='Failed to find metadata for {0} File Paths:'.format(str(len(misses))),
               print_file=print_file)


def print_list(list_to_print, header_message=None, footer_message=None, prefix='\t', print_file=None):
    """ Sort and print out a list of strings, along with optional header and footer messages

    Args:
        list_to_print ([String]): The list to be printed
        prefix (String, optional): The prefix to put in front of each item in the list. Default is a tab
        print_file (file, optional): The file to which any logging should be printed
        header_message (String, optional): A message to be displayed before the list is printed
        footer_message (String, optional): A message to be displayed after the list is printed
    """

    list_to_print.sort()
    if header_message:
        print(header_message, file=print_file)
    for list_item in list_to_print:
        if list_item:
            print((prefix + list_item), file=print_file)
    if footer_message:
        print(footer_message, file=print_file)


if __name__ == '__main__':
    # Args parsing
    args = build_arg_parser().parse_args()

    # Setup logger
    timestr = time.strftime("%Y%m%d-%H%M%S")
    if not os.path.exists('logs'):
        os.makedirs('logs')
    logging.basicConfig(handlers=[logging.FileHandler('logs/'+timestr+'.log', 'w', 'utf-8')], level=logging.DEBUG)
    # Suppress all the google error messages
    logging.getLogger('googleapiclient').setLevel(logging.CRITICAL)
    logging.getLogger('oauth2client.transport').setLevel(logging.CRITICAL)
    logging.getLogger('oauth2client.client').setLevel(logging.CRITICAL)
    handler = logging.StreamHandler()
    handler.setLevel(args.loglevel)
    logging.getLogger().addHandler(handler)

    # Log args
    logging.info('Starting Google Drive Migration Tool')
    log_arg = logging.getLogger('args')
    log_arg.debug(args)

    output_file = None
    if args.printtofile:
        output_file = open(args.printtofile, 'w', encoding='utf-8')

    if args.setup:
        # Setup the connections
        logging.info("Setting up the connection to Drive...")
        drive_interface.print_credentials(force_reset=True, logger=logging, flags=args)
        logging.info("Setting up the connection to Box...")
        box_interface.print_credentials(force_reset=True, logger=logging)
        logging.info('Setup complete.')

    elif args.status:
        # Check the connections
        logging.info("Checking the connection to Drive...")
        drive_interface.print_credentials(force_reset=False, logger=logging, flags=args)
        logging.info("Checking the connection to Box...")
        box_interface.print_credentials(force_reset=False, logger=logging)
        logging.info('Checks complete.')

    elif args.printdrive:
        # Map and print the Drive
        logging.info("Mapping Drive at path: {0}".format(args.rootdrive if args.rootdrive else 'root'))
        src_drive = drive_interface.Drive(path_prefix=PATH_ROOT,
                                          root_path=args.rootdrive,
                                          reset_cred=args.credentials,
                                          flags=args,
                                          logger=logging)
        logging.info("Printing Drive...")
        src_drive.print_drive(output_file=output_file)
        logging.info('Printing complete.')

    elif args.printbox:
        # Map and print the Box
        logging.info("Mapping Box at path: {0}".format(args.rootbox if args.rootbox else 'root'))
        dest_box = box_interface.Box(path_prefix=PATH_ROOT,
                                     root_directory=args.rootbox,
                                     reset_cred=args.credentials,
                                     logger=logging)
        logging.info("Printing Box...")
        dest_box.print_box(output_file=output_file)
        logging.info('Printing complete.')

    elif args.update or args.testmigrate:
        # Source Drive
        logging.info("Mapping Drive at path: {0}".format(args.rootdrive if args.rootdrive else 'root'))
        src_drive = drive_interface.Drive(path_prefix=PATH_ROOT,
                                          root_path=args.rootdrive,
                                          reset_cred=args.credentials,
                                          flags=args,
                                          logger=logging)

        # Destination Box
        logging.info("Mapping Box at path: {0}".format(args.rootbox if args.rootbox else 'root'))
        dest_box = box_interface.Box(path_prefix=PATH_ROOT,
                                     root_directory=args.rootbox,
                                     reset_cred=args.credentials,
                                     logger=logging)

        # Update the metadata
        logging.info("Updating...")
        migrate_metadata(box=dest_box,
                         drive=src_drive,
                         print_details=args.printall,
                         print_file=output_file,
                         test_only=args.testmigrate)
        logging.info('Migration complete.')

    elif args.checkmetadata:
        # Map and print the Box
        if box_interface.check_metadata_exists(args.checkmetadata):
            logging.info("Mapping Box at path: {0}".format(args.rootbox if args.rootbox else 'root'))
            dest_box = box_interface.Box(path_prefix=PATH_ROOT,
                                         root_directory=args.rootbox,
                                         reset_cred=args.credentials,
                                         logger=logging)
            logging.info("Checking Box for Metadata of type: {0}".format(args.checkmetadata))
            check_metadata(box=dest_box,
                           metadata_name=args.checkmetadata,
                           print_file=output_file,
                           logger=logging)
            logging.info('Check complete.')
        else:
            logging.error("Error: metadata of type \'{0}\' does not exist in Box.".format(args.checkmetadata))

    if output_file:
        output_file.close()
    logging.info('Exiting Migration Tool.')
