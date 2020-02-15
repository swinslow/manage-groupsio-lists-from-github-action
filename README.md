# Action: Manage Groups.io Lists From GitHub

This GitHub Action enables you to manage membership of Groups.io lists using a YAML file in a GitHub repo.

_**Note:** A Groups.io Premium or Enterprise subscription is required for this to work, as it uses the "Direct Add" functionality of Groups.io._

At a high level, this Action parses a YAML file containing Groups.io subgroup membership data.  It then updates each Groups.io subgroup appropriately, adding and removing list subscribers.

In order to manage a subgroup, you must add a moderator account to the group with certain permissions (more below).  To avoid undesirable outcomes, this Action can **only** manage subgroups which contain this moderator.

The YAML file uses a flexible and intuitive structure (see [SAMPLE.yml](SAMPLE.yml)):


```
subgroupname:
  - email: email@address.com
  - email: another@address.com
    name: Developer Q. Person
anothersubgroup:
  - email: more@emails.com
```

... and so on.  This script will keep group members' emails (with optional names) synced to the relevant subgroups.  Group members with Moderator or Owner status are ignored.

In addition, this Action can optionally create a separate meta list with all of the members.

You can also optionally define a required suffix (for example, `-wg`) for these groups.  This can help you keep things organized at Groups.io so you don't accidentally add or remove people directly.  This is because your changes will be wiped out the next time this file syncs.  If you choose to do this and used `-foo` as your suffix, a subgroup called `subgroupname` in the YAML file would correspond to a Groups.io subgroup called `subgroupname-foo`.  This is optional, though.

## How to make it work

There are a number of prerequisites:

### A Premium or Enterprise Groups.io subscription:

The Direct Add functionality is only available to Premium and Enterprise subscribers.  This Action won't work for free accounts.

### A groups.io account with moderator permissions:

You must have a groups.io account with sufficient permissions to add and remove members from the subgroups you plan to manage.
 
1. You should create a dummy account for this purpose (maybe turn off email delivery), because although the credentials are encrypted using GitHub Secrets, you shouldn't be saving *your* credentials to be used by GitHub Actions.  Here's an example (with email disabled): `Subgroup Moderator <youremail+moderator@yourdomain.org> nomail`

1. Once you've created this account, grant it the following permissions on the **main** group: `Invite Members` `Modify Group Settings` `View Member List`

1. Next, navigate to a Subgroup you want this Action to manage.  Use Direct Add to add the account, change it to a Moderator within the subgroup, and grant the following permissions: `Add Members` `Remove Members`

### The internal Group name:

Groups.io uses a special internal name for your group.  It is not the name which appears on the website, nor is it your URL.  You can find it by going to Settings &raquo; Export Group Data.  Select "Group Info" and wait for the download.  In the zip file, look for `group.json` and find the value of `name:`.  That is your group name.

### A .yml file with the subgroup configuration:

A sample is included.  The only mandatory parts are the subgroup's name and the `- email:` key.  You can optionally define `name:` on the next line, and it will be used when adding members (see [SAMPLE.yml](SAMPLE.yml)).

That's not all, though.  If you want to use this file as a central repository for user-contributed info, you can add whatever other keys you want (for example, `sponsor:` `twitter:` `pronouns:`).  These won't be used here, but you can reuse that single .yml file for other stuff, like autogenerating maintainer directories for your website.

That should be everything you need to get going.

## Contact info

If you have an issue and it is not security-related, please open an issue at [https://github.com/brianwarner/manage-groupsio-lists-from-github-action](https://github.com/brianwarner/manage-groupsio-lists-from-github-action).  If it is security-related, please contact me directly at <bwarner@linuxfoundation.org>.

---

**Brian Warner** | [The Linux Foundation](https://linuxfoundation.org) | <bwarner@linuxfoundation.org>, <brian@bdwarner.com> | [@realBrianWarner](https://twitter.com/realBrianWarner)