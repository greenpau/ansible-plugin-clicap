#
# Author: (c) 2016 Paul Greenberg @greenpau
#

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.callback import CallbackBase;

try:
    from __main__ import display;
except ImportError:
    from ansible.utils.display import Display;
    display = Display();

import uuid;

class CallbackModule(CallbackBase):

    '''
    This Ansible callback plugin creates a unique identifier for the entire
    playbook play run and consolidates reporting of issues at the end of it.
    '''

    CALLBACK_VERSION = 2.0;
    CALLBACK_TYPE = 'notification';
    CALLBACK_NAME = 'clicap';
    CALLBACK_NEEDS_WHITELIST = False;

    def __init__(self):
        super(CallbackModule, self).__init__();

    def playbook_on_play_start(self, name):
        self._clicap_upid = str(uuid.uuid1());
        pass;

    def v2_playbook_on_play_start(self, play):
        self._clicap_upid = str(uuid.uuid1());
        pass;

    def playbook_on_task_start(self, name, conditional):
        self._clicap_upid = str(uuid.uuid1());
        task.args['upid'] = self._clicap_upid;
        pass;

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._clicap_upid = str(uuid.uuid1());
        task.args['upid'] = self._clicap_upid;
        pass;
