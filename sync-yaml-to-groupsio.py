#!/usr/local/bin/python3

# Copyright Brian Warner
#
# SPDX-License-Identifier: MIT
#
# Latest version and configuration instructions at:
#     https://github.com/brianwarner/manage-groupsio-lists-from-github-action

import os
import sys
import requests
import json
import yaml
import re

from pprint import pprint

user = os.environ['GROUPSIO_USERNAME']
password = os.environ['GROUPSIO_PASSWORD']
group_name=os.environ['GROUP_NAME']
list_suffix = os.environ['LIST_SUFFIX']
unified_list = os.environ['UNIFIED_LIST'] # Optional, leave blank to disable
subgroup_membership_filename = os.environ['MEMBERSHIP_FILE']

### Set up regex patterns ###

email_pattern = re.compile("[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

### Groups.io: Get the relevant subgroups ###

# Authenticate and get the cookie

session = requests.Session()
login = session.post(
        'https://groups.io/api/v1/login',
        data={'email':user,'password':password}).json()
cookie = session.cookies

csrf = login['user']['csrf_token']

# Get subgroups as JSON

# TODO: Add support for >100 subgroups

all_subgroups = session.post(
        'https://groups.io/api/v1/getsubgroups?group_name=%s&limit=100' %
            group_name.replace('+','%2B'),
        cookies=cookie).json()

groupsio_subgroups = set()

# Find all subgroups which match the list suffix, this restricts modification to
# a certain namespace of lists (e.g., can't modify membership of sensitive lists)

if all_subgroups and 'data' in all_subgroups:
    for subgroup in all_subgroups['data']:
        if 'name' in subgroup:
            if subgroup['name'].endswith(list_suffix):

                groupsio_subgroups.add(subgroup['name'])

# Bail out if there aren't any matching subgroups in the group

if not groupsio_subgroups:
    sys.exit()

### Compare local subgroup membership against groups.io, resolve deltas ###

all_local_valid_members = dict()

# Open the local .yml file with subgroup definitions

with open (subgroup_membership_filename,'r') as subgroup_membership_file:
    local_subgroups_and_members = yaml.full_load(subgroup_membership_file)

# Walk through definitions

for local_subgroup, local_members in local_subgroups_and_members.items():

    local_valid_members = dict()

    # Make sure the subgroup has members defined, otherwise move on

    if not local_members:
        continue

    # Walk through the members and extract the valid entries.  Note that if no
    # local member definitions are found, any non-mod/non-admin group members
    # will be removed.  This is one way to clear a subgroup.

    for local_member in local_members:

        # Make sure an email entry exists before proceeding

        if not local_member['email']:
            continue

        local_member_email = email_pattern.findall(local_member['email'])

        # Make sure an email was defined before proceeding

        if not local_member_email:
            continue

        # Check if a name was defined (optional)

        local_member_name = ''

        if 'name' in local_member and local_member['name']:
            local_member_name = local_member['name'].strip()

        # Store the email with the name (if provided)

        local_valid_members[local_member_email[0].lower()] = local_member_name

    # Only proceed if there's a matching subgroup at Groups.io

    calculated_subgroup_name = '%s+%s%s' % (group_name,local_subgroup,list_suffix)

    if not calculated_subgroup_name in groupsio_subgroups:
        continue

    # Add local members to meta list

    all_local_valid_members.update(local_valid_members)

    # Get the members of the group

    # TODO: Support for >100 members

    groupsio_subgroup_members = session.post(
            'https://groups.io/api/v1/getmembers?group_name=%s&limit=100' %
                calculated_subgroup_name.replace('+','%2B'),
            cookies=cookie).json()

    groupsio_members = set()
    groupsio_mods = set()

    if groupsio_subgroup_members and 'data' in groupsio_subgroup_members:
        for subgroup_member in groupsio_subgroup_members['data']:
            if 'email' in subgroup_member:

                # Add users who aren't moderators to the comparison list. Users
                # who are mods are added to a protected list.

                if subgroup_member['mod_status'] == 'sub_modstatus_none':
                    groupsio_members.add(subgroup_member['email'].lower())
                else:
                    groupsio_mods.add(subgroup_member['email'].lower())

    # Calculate the differences between the local file and Groups.io

    local_members_to_add = set(local_valid_members.keys()) - groupsio_members - groupsio_mods
    groupsio_members_to_remove = groupsio_members - set(local_valid_members.keys())

    # Add missing members to groups.io

    for new_member in local_members_to_add:

        new_email = new_member

        # Add a name if one was provided

        if local_valid_members[new_member]:
            new_email = '%s <%s>' % (local_valid_members[new_member], new_member)

        add_members = session.post(
                'https://groups.io/api/v1/directadd?group_name=%s&subgroupnames=%s&emails=%s&csrf=%s' %
                (group_name,calculated_subgroup_name.replace('+','%2B'),new_email.replace('+','%2B'),csrf),
                cookies=cookie).json()

    # Prune members which are not in the local file

    pruned_emails = '\n'.join(groupsio_members_to_remove).replace('+','%2B')

    remove_members = session.post(
            'https://groups.io/api/v1/bulkremovemembers?group_name=%s&emails=%s&csrf=%s' %
            (calculated_subgroup_name.replace('+','%2B'),pruned_emails,csrf),
            cookies=cookie).json()

### Manage the unified list, if defined ###

if unified_list:

    calculated_unified_name = '%s+%s' % (group_name,unified_list)

    #TODO: Support for >100 members

    groupsio_unified_subgroup_members = session.post(
            'https://groups.io/api/v1/getmembers?group_name=%s&limit=100' %
                calculated_unified_name.replace('+','%2B'),
            cookies=cookie).json()

    groupsio_unified_members = set()
    groupsio_unified_mods = set()

    if groupsio_unified_subgroup_members and 'data' in groupsio_unified_subgroup_members:
        for subgroup_member in groupsio_unified_subgroup_members['data']:
            if 'email' in subgroup_member:

                # Add users who aren't moderators to the comparison list. Users
                # who are mods are added to a protected list.

                if subgroup_member['mod_status'] == 'sub_modstatus_none':
                    groupsio_unified_members.add(subgroup_member['email'].lower())
                else:
                    groupsio_unified_mods.add(subgroup_member['email'].lower())

    # Calculate the differences between the local file and Groups.io

    local_members_to_add = set(all_local_valid_members.keys()) - groupsio_unified_members - groupsio_unified_mods
    groupsio_members_to_remove = groupsio_unified_members - set(all_local_valid_members.keys())

    # Add missing members to groups.io

    for new_member in local_members_to_add:

        new_email = new_member

        # Add a name if one was provided

        if all_local_valid_members[new_member]:
            new_email = '%s <%s>' % (all_local_valid_members[new_member], new_member)

        add_members = session.post(
                'https://groups.io/api/v1/directadd?group_name=%s&subgroupnames=%s&emails=%s&csrf=%s' %
                (group_name,calculated_unified_name.replace('+','%2B'),new_email.replace('+','%2B'),csrf),
                cookies=cookie).json()

    # Prune members which are not in the local file

    pruned_emails = '\n'.join(groupsio_members_to_remove).replace('+','%2B')

    remove_members = session.post(
            'https://groups.io/api/v1/bulkremovemembers?group_name=%s&emails=%s&csrf=%s' %
            (calculated_unified_name.replace('+','%2B'),pruned_emails,csrf),
            cookies=cookie).json()
