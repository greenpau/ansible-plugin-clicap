# ansible-plugin-clicap

[![CircleCI](https://circleci.com/gh/greenpau/ansible-plugin-clicap.svg?style=svg)](https://circleci.com/gh/greenpau/ansible-plugin-clicap)
[![PyPI version](https://badge.fury.io/py/ansible-plugin-clicap.png)](https://badge.fury.io/py/ansible-plugin-clicap)
[![Documentation Status](https://readthedocs.org/projects/ansible-plugin-clicap/badge/?version=latest)](http://ansible-plugin-clicap.readthedocs.io/en/latest/?badge=latest)

Network automation plugin for Ansible.

## Overview

The plugin collects (captures) command-line (cli) output from and interacts with network equipment.

The intended audience of this plugin are system and network administrators and engineers.

The plugin ***will*** (in near future) work on both Windows and Linux operating systems.

The plugin's data abstraction format is [YAML](http://yaml.org/).

The plugin requires the presence of two binaries: `ssh` and `expect`.


## Workflow Diagram


[![Plugin Workflow](https://raw.githubusercontent.com/greenpau/ansible-plugin-clicap/master/docs/_static/images/ansible.plugin.clicap.png "Network Automation Workflow")](https://raw.githubusercontent.com/greenpau/ansible-plugin-clicap/master/docs/_static/images/ansible.plugin.clicap.png)


## Getting Started

It is as simple as:

```
pip install ansible-clicap-plugin
```

Then, use the plugin in Ansible playbooks, e.g. `playbooks/collect_all.yml`:

```
---
- hosts:
  - ny-fw01
  gather_facts: no
  vars:
    ansible_connection: local
  vars_files:
    - "~/.clicap.vault.yml"
  tasks:
  - name: collect the output of all relevant operating system commands
    action: clicap output=/tmp/data no_host_key_check=yes on_error=continue
```

Finally, run the playbook:

```
ansible-playbook -i hosts playbooks/collect_all.yml --vault-password-file ~/.vault.passwd -vvv
```

## Documentation

Please read the plugin's documentation for more information at [Read the Docs](http://ansible-plugin-clicap.readthedocs.io/en/latest/)
and review the plugin's [Demo](https://github.com/greenpau/ansible-plugin-clicap/tree/master/demo/firewall) directory.

## Questions

Please open issues and ask questions in [Github Issues](https://github.com/greenpau/ansible-plugin-clicap/issues).

## Contribution

Please contribute using the following [Guidelines](https://github.com/greenpau/ansible-plugin-clicap/tree/master/CONTRIBUTING.md).
