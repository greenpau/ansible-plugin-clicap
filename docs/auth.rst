.. index::
   single: Access Credentials

==================
Access Credentials
==================

.. include:: localtoc.rst

Ansible Vault
-------------

This plugin handles user authentication by way of using user credentials located in
Ansible Vault files. By default, the plugin looks up user credentials in
``.ansible.vault.yml`` file.

A user creates the file with ``ansible-vault create ~/.ansible.vault.yml`` command.
Upon the creation of the file, the Ansible Vault prompts the user of a password.
This password is used to decrypt the content of the vault.

The encrypted file is a plain text file. The first line of the file contains a header.
The header specifies the version of Ansible Vault, encryption type, and looks like this.

.. code-block:: text

   $ANSIBLE_VAULT;1.1;AES256

A user edits the file with ``ansible-vault edit ~/.ansible.vault.yml`` command.

Credentials Structure and Format
--------------------------------

The expected way to store access credentials is in YAML format. The data structure
used is a list of hashes, where each hash represents a single credentials set.

Each hash in the list contains a subset of the following fields:

- ``regex`` (regular expression): if the regular expression in this field in a hash
  matches the FQDN or short name of a device, then the hash is preferred over any
  any other hash having the same or higher priority. However, if there is no match,
  then the hash is not used.
- ``priority`` (numeric): the field prioritizes the use of credentials. The entry with
  lower priority is preferred over the entry with higher priority when multiple entries
  match a regular expression pattern.
- ``default`` (boolean): if this field is present and it is set to `yes`, then this
  credential will be used in the absense of a `regex` match.
- ``description`` (text, optional): it provides an explanation about an entry.
- ``username``
- ``password``
- ``enable``: this credential is used when prompted to provide enable password.
  currently, there is no distinction between enable levels.

In the below example a user entered two sets of credentials. The first entry is used
for a specific device, i.e. ``ny-fw01``. The second entry is used by default when there
is no regular expression matching network device host name.

.. code-block:: yaml

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

Considerations:

- There should be no ``default`` credential with the same ``priority`` level.
- There should be no credential with both ``regex`` and ``default`` fields present

Using Credentials
-----------------

The Ansible Vault credentials file can be used by this plugin via ``vars_files``
directive in Ansible Playbook file, e.g.:

.. code-block:: yaml

      vars_files:
      - "~/.ansible.vault.yml"
