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
ROOT_FOLDER = PATH_ROOT                             # Root folder to start in for migration
FLAGS = None                                        # Flags for Google credentials


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

    parser.add_argument('-r', '--root', type=str, default=ROOT_FOLDER,
                        help='Path to folder to start in (eg "D:/test"). Defaults to root Drive directory')
    parser.add_argument('-f', '--prefix', type=str,
                        help='Prefix letter for the drive (eg "D")')
    parser.add_argument('-l', '--log-level', type=str, default=logging.INFO,
                        help='Logging level for output')

    # Function group
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-p', '--printsrc', action='store_true',
                       help='Print the source Drive')
    group.add_argument('-P', '--printdest', action='store_true',
                       help='Print the destination Drive')
    group.add_argument('-u', '--updatedrive', action='store_true',
                       help='Update the destination Drive using the meta data from the source Drive')
    group.add_argument('-s', '--status', action='store_true',
                       help='Display the current logins for the Drives')
    group.add_argument('-S', '--setup', action='store_true',
                       help='Setup the logins for the Drives')

    # Verbose printing
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose printing of the tree')
    parser.add_argument('-F', '--printtofile', type=str,
                        help='Save the tree to a file instead of stdout. Must be used with one of the print Drive options.')
    parser.add_argument('-x', '--generate-xml', type=str,
                        help='Output the tree to an XML file. Must be used with one of the print Drive options.')

    # Updating permission options
    parser.add_argument('-uo', '--updateowner', action='store_true',
                        help='Flag for updating the owner to the new domain')
    parser.add_argument('-d', '--newdomain', type=str,
                        help='Destination domain (eg "test.com")')
    parser.add_argument('-up', '--updateperm', action='store_true',
                        help='Flag for updating the permissions for the file to the new domain')

    return parser


def main():
    # Args parsing
    parser = build_arg_parser()
    args = parser.parse_args()
    global FLAGS
    FLAGS = args

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

    if args.prefix:
        # Set the Drive prefix
        global PATH_ROOT
        PATH_ROOT = args.prefix + ":"

    if args.root:
        # Set the root folder
        if PATH_ROOT not in args.root:
            log_arg.info("Error: The Drive prefix {0} is not in the supplied path.".format(PATH_ROOT))
            sys.exit()

        global ROOT_FOLDER
        ROOT_FOLDER = args.root

    if (args.printtofile or args.generate_xml) and not (args.printsrc or args.printdest):
        parser.error("Error: The --printsrc or --printdest options must be used with the --printtofile and --generate-xml options.")
        sys.exit()

    if args.setup:
        # Source account credentials
        src_drive = drive_interface.connect_to_drive('src', build=False, reset_cred=True)

        # Destination account credentials
        dest_drive = drive_interface.connect_to_drive('dest', build=False, reset_cred=True)

        src_owner = src_drive.get_credentials()
        dest_owner = dest_drive.get_credentials()

        logging.info("The <{0}> Drive is logged into <{1} ({2})>".format(src_drive.name, src_owner.name, src_owner.email))
        logging.info("The <{0}> Drive is logged into <{1} ({2})>".format(dest_drive.name, dest_owner.name, dest_owner.email))

    if args.status:
        # Source account credentials
        src_drive = drive_interface.connect_to_drive('src', build=False)

        # Destination account credentials
        dest_drive = drive_interface.connect_to_drive('dest', build=False)

        src_owner = src_drive.get_credentials()
        dest_owner = dest_drive.get_credentials()

        logging.info("The <{0}> Drive is logged into <{1} ({2})>".format(src_drive.name, src_owner.name, src_owner.email))
        logging.info("The <{0}> Drive is logged into <{1} ({2})>".format(dest_drive.name, dest_owner.name, dest_owner.email))

    if args.printsrc:
        # Source account credentials
        src_drive = drive_interface.connect_to_drive('src')
        drive_interface.print_wrapper(args.root, src_drive, args.verbose, args.printtofile, args.generate_xml)

    if args.printdest:
        # Destination account credentials
        dest_drive = drive_interface.connect_to_drive('dest')
        drive_interface.print_wrapper(args.root, dest_drive, args.verbose, args.printtofile, args.generate_xml)

    if args.updatedrive:
        update_log = logging.getLogger('update')
        # Check --newdomain is set
        if (args.updateowner or args.updateperm) and args.newdomain is None:
            parser.error("--updateuser and --updateperm require --newdomain")

        update_log.info("Updating...")

        # Source account credentials
        src_drive = drive_interface.connect_to_drive('src')

        # Destination account credentials
        dest_drive = drive_interface.connect_to_drive('dest')

        # Check if we're updating the user
        if (args.updateowner or args.updateperm) and args.newdomain:
            global NEW_DOMAIN, UPDATE_OWNER, UPDATE_PERMISSIONS
            NEW_DOMAIN = args.newdomain
            UPDATE_OWNER = args.updateowner
            UPDATE_PERMISSIONS = args.updateperm

        # Update the drive
        dest_drive.update_drive(src_drive, update_log, base_folder_path=args.root)


def move_metadata(drive_files, box_files):
    for drive_file in drive_files:
        for box_file in box_files:
            if drive_file.path == box_file.path and drive_file.user.email == box_file.user.email:
                return


if __name__ == '__main__':
    drive_map = drive_interface.connect_to_drive(source='src',
                                                 build=True,
                                                 reset_cred=False)

    box_interface.apply_metadata(drive_map)
