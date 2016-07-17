# ansible-plugin-clicap

Ansible plugin for collecting (capturing) command-line (cli) output from
and interacting with network devices.

## Overview

This plugin runs on a master controller and does not copy files to a remote
device. It acts as a wrapper to openssh client.

## Accessing Network Devices

The following command instructs `ansible` to login to `ny-fw01` and
collect running configuration from it.

```
ansible-playbook playbooks/collect_configuration.yml --ask-vault
```

Alternatively, a user may collect the output of all relevant operating
system commands:

```
ansible-playbook playbooks/collect_all.yml --ask-vault
```

Additionally, this plugin supports Check Mode ("Dry Mode"). In this mode,
the plugin will not attempt to login to network devices.

```
ansible-playbook playbooks/collect_configuration.yml --ask-vault --check
```

Also, a user could pass a password file for the vault:

```
ansible-playbook playbooks/collect_all.yml --vault-password-file ~/.vault.passwd
```

Another way to use the plugin is to configure network devices:

```
ansible-playbook playbooks/configure_acl.yml --vault-password-file ~/.vault.passwd --check -vvv
ansible-playbook playbooks/configure_acl.yml --vault-password-file ~/.vault.passwd -vvv
```

## Authentication and Autorization

### Ansible Vault

This plugin handles user authentication by way of using user credentials located in
Ansible Vault files. By default, the plugin looks up user credentials in
`.ansible.vault.yml` file.

A user creates the file with `ansible-vault create ~/.ansible.vault.yml` command.
Upon the creation of the file, the Ansible Vault prompts the user of a password.
This password is used to decrypt the content of the vault.

The encrypted file is a plain text file. The first line of the file contains a header.
The header specifies the version of Ansible Vault, encryption type, and looks like this.

```
$ANSIBLE_VAULT;1.1;AES256
```

A user edits the file with `ansible-vault edit ~/.ansible.vault.yml` command.

### Storing Credentials

The expected way to store access credentials is in YAML format. The data structure
used is a list of hashes, where each hash represents a single credentials set.

Each hash in the list contains a subset of the following fields:

- `regex` (regular expression): if the regular expression in this field in a hash
  matches the FQDN or short name of a device, then the hash is preferred over any
  any other hash having the same or higher priority. However, if there is no match,
  then the hash is not used.
- `priority` (numeric): the field prioritizes the use of credentials. The entry with
  lower priority is preferred over the entry with higher priority when multiple entries
  match a regular expression pattern.
- `default` (boolean): if this field is present and it is set to `yes`, then this
  credential will be used in the absense of a `regex` match.
- `description` (text, optional): it provides an explanation about an entry.
- `username`
- `password`
- `enable`: this credential is used when prompted to provide enable password.
  currently, there is no distinction between enable levels.

In the below example a user entered two sets of credentials. The first entry is used
for a specific device, i.e. `ny-fw01`. The second entry is used by default when there
is no regular expression matching network device host name.

```
---
credentials:
- regex: ny-fw01
  username: admin
  password: 'NX23nKz!'
  password_enable: '3nKz!NX2'
  priority: 1
  description: NY-FW01 password
- default: yes
  username: greenpau
  password: 'My#DefaultPass'
  password_enable: 'Enabled#By$Default'
  priority: 1
  description: my default password
```

Considerations:

* There should be no `default` credential with the same `priority` level.
* There should be no credential with both `regex` and `default` fields present

### Using Credentials

The Ansible Vault credentials file can be used by this plugin via `vars_files`
directive in Ansible Playbook file, e.g.:

```
  vars_files:
    - "~/.ansible.vault.yml"
```


## Available Commands

This plugin uses the following approach when determining which commands are
availble to run on a remote device.

First, each device must carry `clicap_os` attribute. Based on the value of
the attribute, the plugin performs a lookup in `files/cli/os/` directory
the plugin's directory inside Python's `site-packages`directory.

For example, Cisco ASA firewall must have `clicap_os=cisco_asa` attribute.
The plugin will try to locate `files/cli/os/cisco_asa.yml` file. Once
located, the plugin will read it and collect all of the cli commands
associated with Cisco ASA operating system.

It will also record which commands show configuration and version
information, and which commands should be used to disable paging or
switch to automation mode.

