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
main_list = os.environ['MAIN_LIST'] # For most lists, the parent list is 'main'

# Protect the main group.

if unified_list == main_list:
    print('ERROR: You cannot use %s as your unified list.' % main_list)
    sys.exit()

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

# Find all subgroups which match the list suffix, this restricts modification to
# a certain namespace of lists (e.g., can't modify membership of sensitive lists)

more_subgroups = True
next_page_token = 0
groupsio_subgroups = set()

while more_subgroups:
    subgroups_page = session.post(
            'https://groups.io/api/v1/getsubgroups?group_name=%s&limit=100&page_token=%s' %
                (group_name.replace('+','%2B'), next_page_token),
            cookies=cookie).json()

    if subgroups_page and 'data' in subgroups_page:
        for subgroup in subgroups_page['data']:
            if subgroup['name'].endswith(list_suffix) and not subgroup['name'].endswith(unified_list):
                groupsio_subgroups.add(subgroup['name'])

        next_page_token = subgroups_page['next_page_token']

    if next_page_token == 0:
        more_subgroups = False

# Bail out if there aren't any matching subgroups in the group

if not groupsio_subgroups:
    sys.exit()

### Compare local subgroup membership against groups.io, resolve deltas ###

all_local_valid_members = dict()

# Open the local .yml file with subgroup definitions

with open (subgroup_membership_filename,'r') as subgroup_membership_file:
    local_subgroups_and_members = yaml.full_load(subgroup_membership_file)

if not local_subgroups_and_members:
    print('WARN: No lists defined. Exiting')
    sys.exit()

# Walk through definitions

for local_subgroup, local_members in local_subgroups_and_members.items():

    # Protect main and the unified list

    if local_subgroup in [main_list,unified_list]:
        print('INFO: You cannot modify %s. Ignoring.' % local_subgroup)
        continue

    local_valid_members = dict()

    # Walk through the members and extract the valid entries.  Note that if no
    # local member definitions are found, any non-mod/non-admin group members
    # will be removed.  This is one way to clear a subgroup.

    if local_members:
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

    # Add users who aren't moderators to the comparison list. Users who are mods
    # are added to a protected list.

    more_members = True
    next_page_token = 0

    permission_to_modify = True

    groupsio_members = set()
    groupsio_mods = set()

    while more_members:

        groupsio_subgroup_members_page = session.post(
                'https://groups.io/api/v1/getmembers?group_name=%s&limit=100&page_token=%s' %
                    (calculated_subgroup_name.replace('+','%2B'), next_page_token),
                cookies=cookie).json()

        if groupsio_subgroup_members_page['object'] == 'error':
            print('Something went wrong: %s | %s' %
                    (calculated_subgroup_name, groupsio_subgroup_members_page['type']))
            more_members = False
            permission_to_modify = False
            continue

        if groupsio_subgroup_members_page and 'data' in groupsio_subgroup_members_page:
            for subgroup_member in groupsio_subgroup_members_page['data']:
                if 'email' in subgroup_member:

                    if subgroup_member['mod_status'] == 'sub_modstatus_none':
                        groupsio_members.add(subgroup_member['email'].lower())
                    else:
                        groupsio_mods.add(subgroup_member['email'].lower())

            next_page_token = groupsio_subgroup_members_page['next_page_token']

        if next_page_token == 0:
            more_members = False

    # Calculate the differences between the local file and Groups.io

    local_members_to_add = set()
    groupsio_members_to_remove = set()

    if permission_to_modify:

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

            if add_members['object'] == 'error':
                print('Something went wrong: %s | %s' %
                        (calculated_subgroup_name, add_members['type']))
                continue

        # Prune members which are not in the local file

        pruned_emails = '\n'.join(groupsio_members_to_remove).replace('+','%2B')

        if pruned_emails:
            remove_members = session.post(
                    'https://groups.io/api/v1/bulkremovemembers?group_name=%s&emails=%s&csrf=%s' %
                    (calculated_subgroup_name.replace('+','%2B'),pruned_emails,csrf),
                    cookies=cookie).json()

            if remove_members['object'] == 'error':
                print('Something went wrong: %s | %s' %
                        (calculated_subgroup_name, remove_members['type']))
                continue

        # Add local members to meta list

        all_local_valid_members.update(local_valid_members)

### Manage the unified list, if defined ###

permission_to_modify = True

if unified_list:

    calculated_unified_name = '%s+%s' % (group_name,unified_list)

    # Add users who aren't moderators to the comparison list. Users who are mods
    # are added to a protected list.

    more_members = True
    next_page_token = 0

    groupsio_unified_members = set()
    groupsio_unified_mods = set()

    while more_members:

        groupsio_unified_subgroup_members_page = session.post(
                'https://groups.io/api/v1/getmembers?group_name=%s&limit=100&page_token=%s' %
                    (calculated_unified_name.replace('+','%2B'),next_page_token),
                cookies=cookie).json()

        if groupsio_unified_subgroup_members_page['object'] == 'error':
            print('Something went wrong: %s | %s' %
                    (calculated_unified_name, groupsio_unified_subgroup_members_page['type']))
            permission_to_modify = False
            more_members = False
            continue

        if groupsio_unified_subgroup_members_page and 'data' in groupsio_unified_subgroup_members_page:
            for subgroup_member in groupsio_unified_subgroup_members_page['data']:
                if 'email' in subgroup_member:

                    if subgroup_member['mod_status'] == 'sub_modstatus_none':
                        groupsio_unified_members.add(subgroup_member['email'].lower())
                    else:
                        groupsio_unified_mods.add(subgroup_member['email'].lower())

            next_page_token = groupsio_unified_subgroup_members_page['next_page_token']

        if next_page_token == 0:
            more_members = False

    # Calculate the differences between the local file and Groups.io

    local_members_to_add = set(all_local_valid_members.keys()) - groupsio_unified_members - groupsio_unified_mods
    groupsio_members_to_remove = groupsio_unified_members - set(all_local_valid_members.keys())

    # Add missing members to groups.io

    for new_member in local_members_to_add:

        if not permission_to_modify:
            continue

        new_email = new_member

        # Add a name if one was provided

        if all_local_valid_members[new_member]:
            new_email = '%s <%s>' % (all_local_valid_members[new_member], new_member)

        add_members = session.post(
                'https://groups.io/api/v1/directadd?group_name=%s&subgroupnames=%s&emails=%s&csrf=%s' %
                (group_name,calculated_unified_name.replace('+','%2B'),new_email.replace('+','%2B'),csrf),
                cookies=cookie).json()

        if add_members['object'] == 'error':
            print('Something went wrong: %s | %s' %
                    (calculated_subgroup_name, add_members['type']))
            permission_to_modify = False
            continue

    # Prune members which are not in the local file

    pruned_emails = '\n'.join(groupsio_members_to_remove).replace('+','%2B')

    remove_members = session.post(
            'https://groups.io/api/v1/bulkremovemembers?group_name=%s&emails=%s&csrf=%s' %
            (calculated_unified_name.replace('+','%2B'),pruned_emails,csrf),
            cookies=cookie).json()

    if remove_members['object'] == 'error':
        print('Something went wrong: %s | %s' %
                (calculated_unified_name, remove_members['type']))
