.. index::
   single: Frequently Asked Questions

==========================
Frequently Asked Questions
==========================

.. include:: localtoc.rst

Builtin Commands
----------------

This plugin uses the following approach when determining which commands are
availble to run on a remote device.

- First, each device must carry ``clicap_os`` attribute. Based on the value of
  the attribute, the plugin performs a lookup in ``files/cli/os/`` directory
  the plugin's directory inside Python's ``site-packages`` directory.
  For example, Cisco ASA firewall must have ``clicap_os=cisco_asa`` attribute.

- Then, the plugin will try to locate ``files/cli/os/cisco_asa.yml`` file. Once
  located, the plugin will read it and collect all of the cli commands
  associated with Cisco ASA operating system.

Please note, based on the information, the plugin will also record which
commands show configuration and version information, and which commands should
be used to disable paging or switch to automation mode.

Supported Platforms
-------------------

The plugin currently supports connectivity to the following target operating systems:

- Arista EOS
- Cisco IOS
- Cisco NX-OS
- Cisco IOS-XE
- Cisco IronPort
- Cisco ASA
- Cisco ACS
- Citrix Netscaler OS
- Juniper SRX
- Juniper QFX
- Linux
- PaloAlto PAN-OS

Pending development:

- F5 BIG-IP
- Fortinet FortiGate
