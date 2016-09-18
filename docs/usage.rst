.. index::
   single: Use Cases

=========
Use Cases
=========

.. include:: localtoc.rst

Basic Usage
-----------

The following command instructs Ansible to login to ``ny-fw01`` and
collect running configuration from it.

.. code-block:: shell

   ansible-playbook playbooks/collect_configuration.yml --ask-vault

Alternatively, a user may collect the output of all relevant operating
system commands:

.. code-block:: shell

   ansible-playbook playbooks/collect_all.yml --ask-vault

Additionally, this plugin supports Check Mode ("Dry Mode"). In this mode,
the plugin will not attempt to login to network devices.

.. code-block:: shell

   ansible-playbook playbooks/collect_configuration.yml --ask-vault --check

Also, a user could pass a password file for the vault:

.. code-block:: shell

   ansible-playbook playbooks/collect_all.yml --vault-password-file ~/.vault.passwd

Another way to use the plugin is to configure network devices:

.. code-block:: shell

   ansible-playbook playbooks/configure_acl.yml --vault-password-file ~/.vault.passwd --check -vvv
   ansible-playbook playbooks/configure_acl.yml --vault-password-file ~/.vault.passwd -vvv
