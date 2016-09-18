#
# ansible-plugin-clicap - ansible plugin for collecting (capturing)
# command-line (cli) output from and interacting with network devices.
#
# Author: (c) 2016 Paul Greenberg @greenpau
#

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os;
import re;
import tempfile;
import hashlib;
import pprint;
import traceback;
import yaml;
import datetime;
import errno;
import stat;
from collections import OrderedDict;
from ansible.errors import AnsibleError;
from ansible.plugins.action import ActionBase;
from ansible.utils.boolean import boolean;
from datetime import date;
import shlex;
import jinja2;
import json;
import time;
import uuid;

try:
    from __main__ import display;
except ImportError:
    from ansible.utils.display import Display;
    display = Display();


class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):
        ''' handler of interraction with network devices via expect wrapper for ssh/telnet '''

        self.plugin_file = str(__file__).rstrip('c');
        if os.path.islink(self.plugin_file):
            self.plugin_root = '/'.join(os.path.realpath(self.plugin_file).split('/')[:-1]);
        else:
            self.plugin_root = '/'.join(os.path.abspath(__file__).split('/')[:-1]);
        self.plugin_name = os.path.splitext(os.path.basename(__file__))[0];
        self.plugin_j2 = os.path.join(self.plugin_root, self.plugin_name) + '.j2';
        self.plugin_conf = os.path.join(self.plugin_root, self.plugin_name) + '.yml';

        self.errors = [];
        self.conf = dict();
        self.info = dict();
        epoch = time.time();
        ts = time.gmtime(epoch);
        self.refs = OrderedDict({
            'H': 'hostname',
            'U': os.path.split(os.path.expanduser('~'))[-1],
            'Y': str(ts.tm_year),
            'm': str(ts.tm_mon),
            'd': str(ts.tm_mday),
            'H': str(ts.tm_hour),
            'M': str(ts.tm_min),
            'S': str(ts.tm_sec),
            'E': str(int(epoch)),
        });
        self.conf['time_start'] = int(round(time.time() * 1000));
        self.info['return_code'] = 0;
        self.info['return_status'] = 'pending';
        self.conf['cliset_last_id'] = 0;
        self.conf['abort'] = False;

        if task_vars is None:
            task_vars = dict();

        result = super(ActionModule, self).run(tmp, task_vars);

        self.conf['output_dir'] = self._task.args.get('output_dir', None);
        if self.conf['output_dir'] is None:
            self.conf['output_dir'] = self._task.args.get('output', None);
        if self.conf['output_dir'] is not None:
            self.conf['output_dir'] = self._decode_ref(self.conf['output_dir']);

        self.ansible_root = task_vars.get('inventory_dir', None);
        if self.ansible_root is None:
            raise AnsibleError('failed to identify \'inventory_dir\'');

        '''
        The following two variables instruct the plugin to store output of the
        running configuration of a device in a file called "configuration", and
        its version information in a file called "version." This provides uniformity
        when it comes to storing the above information. Regardless which cli command
        was used to retrieve running configuration of a device, it could be always
        found in "configuration" file.
        '''

        self.conf['gather_config'] = boolean(self._task.args.get('gather_config'));
        self.conf['gather_version'] = boolean(self._task.args.get('gather_version'));
        for i in ['prompt', 'error']:
            self.conf['on_' + i] = self._task.args.get('on_' + i, 'abort');
            if self.conf['on_' + i] not in ['abort', 'continue']:
                self.errors.append('the \'' + str(self.conf['on_' + i]) + '\' is not a valid option for \'' + self.plugin_name + '\' plugin');
                return dict(msg='\n'.join(self.errors), failed=True);
        self.conf['disable_defaults'] = boolean(self._task.args.get('disable_defaults'));
        self.conf['no_host_key_check'] = boolean(self._task.args.get('no_host_key_check'));
        self.conf['identity'] = self._task.args.get('identity', 'short');
        if self.conf['identity'] == 'fqdn':
            self.info['host'] = task_vars.get('inventory_hostname', None);
        elif self.conf['identity'] == 'short':
            self.info['host'] = task_vars.get('inventory_hostname_short', None);
        else:
            self.info['host'] = task_vars.get('inventory_hostname_short', None);
            self.errors.append('"identity" task argument contains invalid value: "' + str(self.conf['identity']) + '"');
        self.refs['H'] = self.info['host'];
        self.info['fqdn'] = task_vars.get('inventory_hostname', None);
        self.info['hostname'] = task_vars.get('inventory_hostname_short', None);
        for i in ['os', 'capabilities', 'host_overwrite', 'host_port', 'host_protocol', 'ssh_proxy', 'ssh_proxy_user']:
            self.info[i] = task_vars.get(self.plugin_name + '_' + i, None);
            if self.info[i] is None and i in ['os']:
                self.errors.append('\'' + self.plugin_name + '_' + i + '\' inventory attribute must be associated with ' + self.info['host']);
                return dict(msg='\n'.join(self.errors), failed=True);

        '''
        Load plugin configuration file and exceptions.
        '''

        self._load_conf();
        self.conf['cliset_exc'] = self._task.args.get('cliset_exc', os.path.join(self.ansible_root, 'files', self.plugin_name, 'exceptions.yml'));
        self._load_exceptions();

        '''
        Check for operating system support.
        '''

        if self.info['os'] not in self.conf['allowed_os']:
            self.errors.append('the ' + self.info['os'] + ' operating system is unsupported');
            return dict(msg='\n'.join(self.errors), failed=True);

        '''
        os_cliset_dir parameter is optional. it points to the directory containing references
        to cli commands to run on a particular operating system or device. The directory
        path defaults to ansible files/clicap directory inside ansible inventory directory.
        '''

        self.conf['cliset_os_default_dir'] = os.path.join(self.plugin_root, 'files/cli/os');
        self.conf['cliset_os_dir'] = self._task.args.get('os_cliset_dir', os.path.join(self.ansible_root, 'files', self.plugin_name, 'os'));
        self.conf['cliset_host_dir'] = self._task.args.get('host_cliset_dir', os.path.join(self.ansible_root, 'files', self.plugin_name, 'host'));
        if not self.conf['disable_defaults']:
            for i in ['os_default', 'os', 'host']:
                if i in ['os_default']:
                    filename = self.info['os'] + '.yml';
                else:
                    filename = self.info[i] + '.yml';
                self.conf['cliset_' + i] = os.path.join(self.conf['cliset_' + i + '_dir'], filename);
                self._load_cliset(self.conf['cliset_' + i], i);
        else:
            self.conf['cliset_os_default'] = os.path.join(self.conf['cliset_os_default_dir'], self.info['os'] + '.yml');
            self._load_cliset(self.conf['cliset_os_default'], 'os_default', commit=False);
            self.conf['cliset_spec'] = self._task.args.get('cliset_spec', None);
            if self.conf['cliset_spec']:
                if re.match(r'/', self.conf['cliset_spec']):
                    self._load_cliset(self.conf['cliset_spec'], 'spec');
                else:
                    self._load_cliset(os.path.join(self.ansible_root, self.conf['cliset_spec']), 'spec');

        if self.errors:
            return dict(msg='\n'.join(self.errors), failed=True);

        '''
        Create a temporary directory for command-line output.
        '''

        self.conf['temp_dir'] = os.path.join(os.getenv("HOME"), '.ansible', 'tmp', self.plugin_name, datetime.datetime.now().strftime("%Y/%m/%d"), str(os.getppid()), self.info['host']);
        try:
            os.makedirs(self.conf['temp_dir']);
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise AnsibleError('failed to create temporary directory: ' + traceback.format_exc());

        self.conf['timestamp'] = datetime.datetime.now().strftime(".%H%M%S");
        self.file_prefix = self.info['host'] + '.';
        for i in ['log', 'stdout', 'exp', 'dbg']:
            self.conf[i] = os.path.join(self.conf['temp_dir'], self.file_prefix + i);
        if self._play_context.check_mode:
            display.vvv('running in check mode', host=self.info['host']);
        display.vvv('plugin name: ' + self.plugin_j2, host=self.info['host']);
        display.vvv('plugin temp dir: ' + self.conf['temp_dir'], host=self.info['host']);
        display.vvv('temporary log file: ' + self.conf['log'], host=self.info['host']);

        '''
        Next, the plugin load the list of user credentials to access the host associated with the task.
        '''

        credentials = task_vars.get('credentials', None);
        if not credentials:
            if self._play_context.check_mode:
                for c in ['username', 'password', 'password_enable']:
                    self.conf[c] = 'check_mode';
            else:
                raise AnsibleError(self.plugin_name + ' failed to locate access credentials for remote devices, try --ask-vault');
        else:
            credentials = self._load_credentials(credentials);
            if self.errors:
                return dict(msg='\n'.join(self.errors), failed=True);
            j = 0;
            for c in credentials:
                for k in c:
                    if k not in ['password', 'password_enable']:
                        display.vvv('credentials (' + str(j)  + '): ' + str(k) + ': ' + str(c[k]), host=self.info['host']);
                j += 1;
            primary_credentials = credentials.pop(0);
            for c in ['username', 'password', 'password_enable']:
                self.conf[c] = primary_credentials[c];

        '''
        Create network connection string via either ssh or telnet.
        '''

        self._get_network_connectivity_details();

        display.vvv('host information:\n' + json.dumps(self.info, indent=4, sort_keys=True), host=self.info['host']);
        display.vvv('plugin configuration:\n' + json.dumps(self.conf, indent=4, sort_keys=True), host=self.info['host']);

        if not self.errors:
            if self.conf['cliset_last_id'] == 0:
                display.display('<' + self.info['host'] + '> no cli commands found', color='yellow');
                self.info['return_status'] = 'failed';
            else:
                self._remote_play();

        if self.errors:
            if self.info['return_code'] == 0:
                self.info['return_code'] = 1;
                self.info['return_status'] = 'failed';

        if self.errors:
            display.display('<' + self.info['host'] + '> review "' + self.conf['temp_dir'] + '" directory for details', color='red');
            result = dict(msg='\n'.join(self.errors), failed=True);
        elif self.info['return_status'] == 'unreachable':
            if 'return_msg' in self.info:
                result = dict(msg=self.info['return_msg'], unreachable=True);
            else:
                result = dict(unreachable=True);
        elif self.info['return_status'] == 'failed':
            display.display('<' + self.info['host'] + '> review "' + self.conf['temp_dir'] + '" directory for details', color='red');
            if 'return_msg' in self.info:
                result = dict(msg=self.info['return_msg'], failed=True);
            else:
                result = dict(failed=True);
        else:
            _failed_cli = [];
            for _id in self.conf['cliset']:
                if 'status' in self.conf['cliset'][_id]:
                    if self.conf['cliset'][_id]['status'] == 'failed':
                        _failed_cli.append(self.conf['cliset'][_id]['cli']);
            result = dict({});
            if _failed_cli:
                display.display('<' + self.info['host'] + '> review "' + self.conf['temp_dir'] + '" directory for details', color='red');
                result['msg'] = 'failed ' + ','.join(_failed_cli);
                result['failed'] = True;
            else:
                if 'output_dir' in self.conf:
                    self._commit();
                else:
                    display.display('<' + self.info['host'] + '> review "' + self.conf['temp_dir'] + '" directory for details', color='green');
                if 'changed' in self.info:
                    result['changed'] = True;
                result['ok'] = True;

        self.conf['time_end'] = int(round(time.time() * 1000));
        display.vvv('plugin configuration:\n' + json.dumps(self.conf, indent=4, sort_keys=True), host=self.info['host']);
        self._report();
        return result;


    def _get_network_connectivity_details(self):

        '''
        Create network connection string via either ssh or telnet.
        '''

        self.conf['args'] = 'ssh';
        clicap_proto = 'ssh';
        clicap_proxy = None;
        if self.info['host_protocol'] is not None:
            if self.info['host_protocol'] == 'telnet':
                self.conf['args'] = 'telnet';
                clicap_proto = 'telnet';

        if self.info['ssh_proxy'] is not None:
            clicap_proxy = str(self.info['ssh_proxy']);
            if 'ssh_proxy_user' in self.info:
                clicap_proxy = str(self.info['ssh_proxy_user']) + '@' + clicap_proxy;
            if self.conf['no_host_key_check']:
                clicap_proxy = "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -tt " + clicap_proxy;
            else:
                clicap_proxy = "ssh -tt " + clicap_proxy;

        if clicap_proto == 'ssh':
            if clicap_proxy:
                self.conf['args'] = clicap_proxy + ' ' + self.conf['args'];
            if self.conf['no_host_key_check']:
                self.conf['args'] += ' -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no';
            '''
            The below line is a workaround for older versions of OpenSSH server.
            It is advisable to do it in ~/.ssh/config file
                self.conf['args'] += ' -o KexAlgorithms=+diffie-hellman-group1-sha1';
            '''
            if self.info['host_port'] is not None:
                self.conf['args'] += ' -p ' + self.info['host_port']
            self.conf['args'] += ' -tt ' + self.conf['username'] + '@';
            if self.info['host_overwrite'] is not None:
                self.conf['args'] += self.info['host_overwrite'];
            else:
                self.conf['args'] += self.info['host'];
        elif clicap_proto == 'telnet':
            if clicap_proxy:
                self.conf['args'] = clicap_proxy + ' ' + self.conf['args'];
            if self.info['host_overwrite'] is not None:
                self.conf['args'] += ' ' + self.info['host_overwrite'];
            else:
                self.conf['args'] += ' ' + self.info['host'];
            if self.info['host_port'] is not None:
                self.conf['args'] += ' ' + self.info['host_port'];
        else:
            raise AnsibleError(str(clicap_proto) + ' protocol is unsupported by ' + self.plugin_name + ' plugin');
        self.conf['args'] = shlex.split(self.conf['args']);
        self.info['host_protocol'] = clicap_proto;
        if self.info['host_port'] is None:
            if self.info['host_protocol'] == 'telnet':
                self.info['host_port'] = 23;
            elif self.info['host_protocol'] == 'ssh':
                self.info['host_port'] = 22;
            else:
                pass;
        return;


    def _remote_play(self):
        '''
        This function is a wrapper for ssh and telnet commands via expect.
        '''

        '''
        Build expect template to handle interraction with a remote device.
        '''

        j2env = jinja2.Environment(loader=jinja2.FileSystemLoader(self.plugin_root));
        j2tmpl = j2env.get_template(self.plugin_name + '.j2');
        j2conf = {
            'host': self.info['host'],
            'operating_system': self.info['os'],
            'controller': 'master',
            'plugin': self.plugin_name,
            'uid': str(uuid.uuid1()),
            'connection_string': ' '.join(self.conf['args']),
            'stdout_file_name': self.conf['stdout'],
            'log_dir': self.conf['temp_dir'],
            'log_file_name': self.conf['log'],
            'dbg_file_name': self.conf['dbg'],
            'on_prompt': self.conf['on_prompt'],
        };
        j2rc = {
            0:  {'status': 'ok'},
            1:  {'status': 'failed'},
            64: {'msg': 'connection timeout', 'status': 'unreachable'},
            65: {'msg': 'connection failed', 'status': 'unreachable'},
            66: {'msg': 'dns resolution failed', 'status': 'unreachable'},
            67: {'msg': 'authentication failed', 'status': 'failed'},
            68: {'msg': 'hostname detection failed', 'status': 'failed'},
            69: {'msg': 'prompt detection failed', 'status': 'failed'},
            70: {'msg': 'disabling paging failed', 'status': 'failed'},
            71: {'msg': 'local subprocess communication failed', 'status': 'failed'},
            72: {'msg': 'enabling automation mode failed', 'status': 'failed'},
            73: {'msg': 'no spawned process found when terminating session', 'status': 'failed'},
            74: {'msg': 'received unknown ssh fingerprint', 'status': 'failed'},
        };

        for i in ['paging', 'scripting']:
            if i in self.conf:
                j2conf[i + '_mode_on'] = 1;
                j2conf[i + '_mode_cli'] = self.conf[i];
            else:
                j2conf[i + '_mode_on'] = 0;

        j2exp = j2tmpl.render(j2conf);
        try:
            os.chmod(self.conf['temp_dir'], stat.S_IRWXU);
            for i in ['log', 'stdout', 'exp', 'dbg']:
                with open(self.conf[i], 'a') as fh:
                    os.utime(fh.name, None);
                    os.chmod(fh.name, stat.S_IRUSR | stat.S_IWUSR);
        except:
            self.errors.append('<' + self.info['host'] + '> an attempt by ' + self.plugin_name + ' plugin to secure temporary directory \'' + self.conf['temp_dir'] + '\' failed.');
            self.errors.append('<' + self.info['host'] + '> ' + traceback.format_exc());
            return;

        with open(self.conf['log'], 'a') as fh_log:
            fh_log.write(str(datetime.datetime.now()) + ': ' + self.info['host'] + ': invoking \'' + ' '.join(self.conf['args']) + '\'\n');

        with open(self.conf['exp'], 'a') as fh_exp:
            fh_exp.write(j2exp);

        try:
            '''
            Create pipes for IPC:
              * pr - Parent Read
              * pw - Parent Write
              * cr - Child Read
              * cw - Child Write
            '''
            remote_session_stdin_pr, remote_session_stdout_cw = os.pipe();
            remote_session_stdin_cr, remote_session_stdout_pw = os.pipe();
        except:
            self.errors.append('<' + self.info['host'] + '> an attempt by ' + self.plugin_name + ' plugin to create a Pipe for the purpose of communicating to a child process script failed.');
            self.errors.append('<' + self.info['host'] + '> ' + traceback.format_exc());
            return;

        try:
            remote_session_pid = os.fork();
            if remote_session_pid != 0:
                ''' the following code is processed by parent process '''
                os.close(remote_session_stdin_cr);
                os.close(remote_session_stdout_cw);
                remote_session_stdout_pw = os.fdopen(remote_session_stdout_pw, 'w');
                display.vvv('remote_session_pid: "' + str(remote_session_pid) + '"', host=self.info['host']);
            else:
                ''' the following code is processed by child process '''
                os.close(remote_session_stdin_pr);
                os.close(remote_session_stdout_pw);
                os.dup2(remote_session_stdin_cr, 0);
                os.dup2(remote_session_stdout_cw, 1);
                os.dup2(remote_session_stdout_cw, 2);
                if self._play_context.check_mode:
                    os.execvp('expect', ['expect', '-v']);
                else:
                    os.execvp('expect', ['expect', '-f', self.conf['exp']]);
        except:
            self.errors.append('<' + self.info['host'] + '> an attempt by ' + self.plugin_name + ' plugin to create a child process for its expect script failed.');
            self.errors.append('<' + self.info['host'] + '> ' + traceback.format_exc());
            return;

        if remote_session_pid != 0:
            try:
                _break = False;
                clitask = None;
                clifile = None;
                climode = None;
                while True:
                    remote_session_stdin = '';
                    while True:
                        inc = os.read(remote_session_stdin_pr, 1);
                        if inc == '':
                           _break = True;
                           break;
                        elif inc == '\n':
                           break;
                        else:
                           remote_session_stdin += inc;
                    _prompted = False;
                    for prompt in ['username', 'password', 'password_enable']:
                        if re.search(prompt + ':', remote_session_stdin):
                            _prompted = True;
                            display.vvv('detected "' + prompt + '" prompt, sending response', host=self.info['host']);
                            os.write(remote_session_stdout_pw.fileno(), self.conf[prompt] + "\n");
                    if not _prompted:
                        if str(remote_session_stdin) == "":
                            pass;
                        elif re.search('clitask:', remote_session_stdin):
                            _prompted = True;
                            '''
                            if the plugin previously sent a command to a remote device,
                            check the result of the command's execution by looking at the
                            command's output.
                            '''

                            if self.conf['cliset_last_eid'] > 0 and self.conf['cliset_last_eid'] in self.conf['cliset']:
                                filepath = os.path.join(self.conf['temp_dir'], self.conf['cliset'][self.conf['cliset_last_eid']]['filename']);
                                self.conf['cliset'][self.conf['cliset_last_eid']]['time_end'] = int(round(time.time() * 1000));
                                if self.conf['cliset'][self.conf['cliset_last_eid']]['status'] == 'skipped':
                                    display.display('<' + self.info['host'] + '> skipped "' + self.conf['cliset'][self.conf['cliset_last_eid']]['cli'] + \
                                                    '" command: skip', color='yellow');
                                else:
                                    _is_failed = self._parse_cli_output(filepath, self.conf['cliset_last_eid']);
                                    if _is_failed:
                                        self.conf['cliset'][self.conf['cliset_last_eid']]['status'] = 'failed';
                                        if self.conf['on_error'] == 'abort':
                                            self.conf['abort'] = True;
                                        display.display('<' + self.info['host'] + '> completed running "' + self.conf['cliset'][self.conf['cliset_last_eid']]['cli'] + \
                                                        '" command: fail', color='red');
                                    else:
                                        display.display('<' + self.info['host'] + '> completed running "' + self.conf['cliset'][self.conf['cliset_last_eid']]['cli'] + \
                                                        '" command: ok', color='green');
                                        if self.conf['cliset'][self.conf['cliset_last_eid']]['mode'] == 'analytics':
                                            self.conf['cliset'][self.conf['cliset_last_eid']]['sha1'] = self._get_sha1_hash(filepath);
                                            self.conf['cliset'][self.conf['cliset_last_eid']]['path'] = filepath;

                            '''
                            check for the commands pending execution on a remote device.
                            '''
                            clitask = self._get_cli_task('task');
                            display.vvv('prompted for cli task, sending: ' + clitask, host=self.info['host']);
                            os.write(remote_session_stdout_pw.fileno(), clitask + "\n");
                        elif re.search('clifile:', remote_session_stdin):
                            _prompted = True;
                            clifile = self._get_cli_task('file');
                            display.vvv('prompted for cli output filename, sending: ' + clifile, host=self.info['host']);
                            os.write(remote_session_stdout_pw.fileno(), clifile + "\n");
                        elif re.search('climode:', remote_session_stdin):
                            '''
                            A command may be for analytics purposes, e.g. `show ip route`, or it
                            may be a part of a deployment job. If it is a deployment job, any error
                            is a signal to abort the job.
                            '''
                            _prompted = True;
                            climode = self._get_cli_task('mode');
                            display.vvv('prompted for cli output mode, sending: ' + climode, host=self.info['host']);
                            if self.conf['cliset_last_eid'] in self.conf['cliset']:
                                self.conf['cliset'][self.conf['cliset_last_eid']]['time_start'] = int(round(time.time() * 1000));
                            os.write(remote_session_stdout_pw.fileno(), climode + "\n");
                        else:
                            display.vvv('received unsupported prompt: "' + str(remote_session_stdin) + '"', host=self.info['host']);
                            pass;
                    if _break:
                        break;
                remote_session_rst = os.waitpid(remote_session_pid, 0);
                remote_session_rc = remote_session_rst[1];
                remote_session_rc = remote_session_rc >> 8;
                display.vvv('child process exited with: ' + str(remote_session_rc) + ' (' + str(type(remote_session_rc)) + ')', host=self.info['host']);
                if remote_session_rc in j2rc:
                    self.info['return_code'] = remote_session_rc;
                    self.info['return_status'] = j2rc[remote_session_rc]['status'];
                    if 'msg' in j2rc[remote_session_rc]:
                        display.vvv(j2rc[remote_session_rc]['status'] + ': ' + j2rc[remote_session_rc]['msg'], host=self.info['host']);
                        self.info['return_msg'] = j2rc[remote_session_rc]['msg'];
                    else:
                        display.vvv(j2rc[remote_session_rc]['status'], host=self.info['host']);
                else:
                    self.info['return_code'] = 1;
                    self.info['return_status'] = 'failed';
                    display.vvv('child process exited with unsupported return code ' + str(remote_session_rc) + ' (' + str(type(remote_session_rc)) + ')', host=self.info['host']);
                    self.errors.append('<' + self.info['host'] + '> ' + 'child process exited with unsupported return code ' + str(remote_session_rc) + ' (' + str(type(remote_session_rc)) + ')');
            except:
                self.errors.append('<' + self.info['host'] + '> an attempt by ' + self.plugin_name + ' plugin to communicate to its child process failed.');
                self.errors.append('<' + self.info['host'] + '> ' + traceback.format_exc());
        return;


    def _get_cli_task(self, item):
        ''' This function responds with either task or file name '''
        if 'cliset_last_eid' not in self.conf:
            return 'eol';
        if item == 'task':
            self.conf['cliset_last_eid'] += 1;
        if self.conf['cliset_last_eid'] not in self.conf['cliset']:
            return 'eol';
        if self.conf['abort']:
            return 'eol';
        if item == 'task':
            return self.conf['cliset'][self.conf['cliset_last_eid']]['cli'];
        elif item == 'file':
            return self.conf['cliset'][self.conf['cliset_last_eid']]['filename'];
        elif item == 'mode':
            return self.conf['cliset'][self.conf['cliset_last_eid']]['mode'];
        else:
            pass;
        return 'eol';


    def _parse_cli_output(self, fn, cli_id):
        cli = self.conf['cliset'][cli_id]['cli'];
        self._remove_non_ascii(fn);
        self.conf['cliset'][cli_id]['lines'] = self._remove_ltr_blanks(fn);
        if self.conf['cliset'][cli_id]['lines'] == 0 and self.conf['cliset'][cli_id]['allow_empty_response'] == True:
            return False;
        fc = None;
        lines = [];
        with open(fn) as f:
            fc = [x.rstrip() for x in f.readlines()];
        if not fc:
            if self.conf['cliset'][cli_id]['allow_empty_response'] == True:
                return False;
            if self.conf['cliset'][cli_id]['mode'] == 'configure':
                return False;
            self.errors.append('the \'' + str(cli) + '\' command produced no output');
            self.conf['cliset'][cli_id]['status'] = 'failed';
            return True;
        '''
        Secure captured cli output.
        '''
        try:
            os.chmod(fn, stat.S_IRUSR | stat.S_IWUSR);
        except:
            self.conf['cliset'][cli_id]['status'] = 'failed';
            self.conf['cliset'][cli_id]['error_msg'] = traceback.format_exc();
            self.errors.append('<' + self.info['host'] + '> ' + traceback.format_exc());
            return True;
        '''
        Parse for errors and filter output prior to saving it.
        '''
        for line in fc:
            if not lines and re.match('^\s*$', line):
                continue;
            if not lines and re.match('show\s', line):
                continue;
            for err in self.conf['output_errors']:
                for rgx in err['regex']:
                    if re.search(rgx, line):
                        _is_exempt = False;
                        if 'exception' in err:
                            for exc in err['exception']:
                                if re.search(exc, str(cli)):
                                    _is_exempt = True;
                        if not _is_exempt:
                            self.errors.append('\'' + str(cli) + '\' command failed due to ' + err['msg']);
                            if 'error_msg' not in self.conf['cliset'][cli_id]:
                                self.conf['cliset'][cli_id]['error_msg'] = [];
                            self.conf['cliset'][cli_id]['status'] = 'failed';
                            self.conf['cliset'][cli_id]['error_msg'].append(fc);
                            return True;
            _is_removed = False;
            for flt in self.conf['output_filter_remove']:
                if 'tags' not in self.conf['cliset'][cli_id]:
                    break;
                if 'configuration' not in self.conf['cliset'][cli_id]['tags']:
                    break;
                if re.match(flt, line):
                    _is_removed = True;
                    break;
            for flt in self.conf['output_filter_replace']:
                if 'tags' not in self.conf['cliset'][cli_id]:
                    break;
                if 'configuration' not in self.conf['cliset'][cli_id]['tags']:
                    break;
                for rgx in flt['regex']:
                    if re.search(rgx, line):
                        line = re.sub(rgx, flt['replace'], line);
            if not lines and line == '':
                continue;
            if not _is_removed:
                lines.append(line);
        with open(fn, 'w') as f:
            f.write('\n'.join(lines) + '\n');
        if self.conf['cliset'][cli_id]['mode'] == 'configure':
            self.conf['cliset'][cli_id]['status_msg'] = '\n'.join(lines) + '\n';
        return False;


    @staticmethod
    def _remove_non_ascii(fn):
        with open(fn, "r+") as f:
            data = f.read();
            buffer = [];
            for c in data:
                if (ord(c) > 31 and ord(c) < 127) or ord(c) in [10]:
                    buffer.append(c);
            f.seek(0);
            f.write(''.join(buffer));
            f.truncate();
        return;


    @staticmethod
    def _remove_ltr_blanks(fn):
        '''
        This function removes leading and trailing blank lines from a file.
        Additionally, it returns the number of lines in the file.
        The count does not include the leading or trailing blank lines.
        '''
        lc = 0;
        lines = None;
        with open(fn, 'r') as f:
            lines = f.readlines();
        if not lines:
            return lc;
        empty_lines = [];
        for i in [(0, len(lines), 1), (len(lines)-1, -1, -1)]:
            for j in xrange(i[0], i[1], i[2]):
                if re.match('^\s*$', lines[j]):
                    empty_lines.append(j);
                else:
                    break;
        if empty_lines:
            empty_lines = list(reversed(sorted(empty_lines)));
            for empty_line in empty_lines:
                lines.pop(empty_line);
        if not lines:
            return lc;
        with open(fn, 'w') as f:
            f.write(''.join(lines));
        return lc;


    def _decode_ref(self, s):
        '''
        This function translates references to special codes in string variables:
        - `%H`: Hostname
        - `%Y`: Year with century as a decimal number
        - `%m`: Month as a zero-padded decimal number
        - `%d`: Day of the month as a zero-padded decimal number
        - `%H`: Hour (24-hour clock) as a zero-padded decimal number
        - `%M`: Minute as a zero-padded decimal number
        - `%S`: Second as a zero-padded decimal number
        - `%E`: Epoch
        '''
        for i in self.refs:
            s = s.replace('%' + i, self.refs[i]);
        s = s.replace('%', '');
        return s;


    def _load_conf(self):
        '''
        This function loads the configuration of this plugin.
        '''
        fc = None;
        try:
            with open(self.plugin_conf) as f:
                fc = yaml.load(f);
        except:
            self.errors.append('<' + self.info['host'] + '> an attempt to read ' + self.plugin_name + ' configuration data from ' + str(fn) + ' failed.');
            self.errors.append('<' + self.info['host'] + '> ' + traceback.format_exc());
            return;
        for i in ['allowed_os', 'output_filter_remove', 'output_filter_replace', 'output_errors']:
            if i in fc:
                self.conf[i] = fc[i];
        return;


    def _load_exceptions(self):
        '''
        This function loads the exceptions for cli sets of this plugin.
        '''
        fc = None;
        try:
            with open(self.conf['cliset_exc']) as f:
                fc = yaml.load(f);
        except:
            return;
        if 'exceptions' not in fc:
            return;
        for r in fc['exceptions']:
            if 'exceptions' not in self.conf:
                self.conf['exceptions'] = [];
            for i in ['hosts', 'cli']:
                if i not in r:
                    raise AnsibleError('cli exceptions file "' + str(self.conf['cliset_exc']) + '" is missing "' + i + '" mandatory field');
                if not isinstance(r[i], str):
                    raise AnsibleError('the "' + i + '" mandatory field in cli exceptions file "' + str(self.conf['cliset_exc']) + '" must be a string with a valid regular expression');
            self.conf['exceptions'].append(r);


    def _load_credentials(self, db=dict()):
        '''
        Load access credentials from Ansible Vault file.
        '''
        credentials = [];
        rgx_credentials = {};
        dft_credentials = {};
        for c in db:
            for k in c.keys():
                if k not in ['regex', 'username', 'password', 'password_enable', 'priority', 'description', 'default']:
                    self.errors.append('access credentials dictionary contains invalid key: ' + k);
            required_keys = ['username', 'password', 'priority'];
            for k in required_keys:
                if k not in c.keys():
                    self.errors.append('the "' + str(c) + '" access credentials entry is missing mandatory key "' + k + '"');
                    return None;
            if 'regex' not in c and 'default' not in c:
                self.errors.append('access credentials dictionary has neither regex nor default keys: ' + str(c));
                return None;
            elif 'regex' in c and 'default' in c:
                if c['default'] is True:
                    self.errors.append('access credentials entry must have either \'regex\' key or \'default\' key must be set to \'True\': ' + str(c));
                    return None;
                else:
                    if re.match(c['regex'], self.info['host']):
                        if c['priority'] in rgx_credentials:
                            for k in ['password', 'password_enable']:
                                if k in c:
                                    del c[k];
                                if k in rgx_credentials[c['priority']]:
                                    del rgx_credentials[c['priority']][k];
                            self.errors.append('access credentials entry "' + str(c) + '" has the same priority as "' + str(rgx_credentials[c['priority']])  + '"');
                            return None;
                        rgx_credentials[c['priority']] = c.copy();
                        continue;
            elif 'regex' not in c and 'default' in c:
                if c['default'] is False:
                    self.errors.append('access credentials entry must have either \'regex\' key or \'default\' key must be set to \'True\': ' + str(c));
                    continue;
                else:
                    if c['priority'] in dft_credentials:
                        for k in ['password', 'password_enable']:
                            if k in c:
                                del c[k];
                            if k in rgx_credentials[c['priority']]:
                                del rgx_credentials[c['priority']][k];
                        self.errors.append('default access credentials entry "' + str(c) + '" has the same priority as "' + str(dft_credentials[c['priority']])  + '"');
                        return None;
                    dft_credentials[c['priority']] = c.copy();
                    continue;
            elif 'regex' in c and 'default' not in c:
                if re.match(c['regex'], self.info['host']):
                    if c['priority'] in rgx_credentials:
                        for k in ['password', 'password_enable']:
                            if k in c:
                                del c[k];
                            if k in rgx_credentials[c['priority']]:
                                del rgx_credentials[c['priority']][k];
                        self.errors.append('access credentials entry "' + str(c) + '" has the same priority as "' + str(rgx_credentials[c['priority']])  + '"');
                        return None;
                    rgx_credentials[c['priority']] = c.copy();
                    continue;
        if not rgx_credentials and not dft_credentials:
            self.errors.append('access credentials dictionary must have at least one default entry');
            return None;

        for c in sorted(rgx_credentials):
            if 'password_enable' not in rgx_credentials[c]:
                rgx_credentials[c]['password_enable'] = rgx_credentials[c]['password'];
            credentials.append(rgx_credentials[c]);
        for c in sorted(dft_credentials):
            if 'password_enable' not in dft_credentials[c]:
                dft_credentials[c]['password_enable'] = dft_credentials[c]['password'];
            credentials.append(dft_credentials[c]);
        return credentials;


    def _load_cliset(self, fn, src, commit=True):
        if not os.path.exists(fn):
            return;
        if not os.path.isfile(fn):
            self.errors.append(fn + ' is not a file');
            return;
        if not os.access(fn, os.R_OK):
            self.errors.append(fn + ' is not readable');
            return;
        fc = None;
        try:
            with open(fn) as f:
                fc = yaml.load(f);
        except:
            self.errors.append('an attempt to read ' + self.plugin_name + ' data from ' + str(fn) + ' failed.');
            self.errors.append(traceback.format_exc());
            return;
        if not fc:
            self.errors.append('an attempt to read ' + self.plugin_name + ' data from ' + str(f) + ' failed because no data was found.');
            return;
        if 'clicap' not in fc:
            self.errors.append('the ' + self.plugin_name + ' data from ' + str(f) + ' does not have reference to \'clicap\' list.');
            return;
        for entry in fc['clicap']:
            entry_tags = [];
            if not isinstance(entry, dict):
                self.errors.append('the ' + self.plugin_name + ' data from ' + str(f) + ' is not a list of dictionaries.');
                return;
            required_keys = ['cli'];
            optional_keys = ['capability', 'tags', 'paging', 'format', 'scripting', 'mode', 'pre', 'post', 'saveas'];
            for k in required_keys:
                if k not in entry:
                    self.errors.append('failed to find mandatory field  \'' + str(k) + '\' in ' + str(entry) + ' in ' + str(f));
                    continue;
            for k in entry:
                if k not in optional_keys and k not in required_keys:
                    self.errors.append('the \'' + str(k)  + '\' field in ' + str(entry) + ' in ' + str(f) + ' is unsupported');
                    continue;
                if k in ['paging', 'scripting']:
                    self.conf[k] = entry[k];
                elif k == 'tags':
                    if isinstance(entry[k], str):
                        entry_tags.append(entry[k]);
                    elif isinstance(entry[k], list):
                        for t in entry[k]:
                            entry_tags.append(t);
                    else:
                        self.errors.append('the handling of \'' + k  + '\' field of ' + str(type(entry[k])) + ' type in ' + str(entry) + ' in ' + str(f) + ' is unsupported');
                else:
                    pass;

            if not commit:
                continue;

            entry_mode = None;
            if 'mode' in entry:
                if entry['mode'] not in ['analytics', 'configure']:
                    self.errors.append('mode "' + str(entry['mode']) + '" is unsupported');
                entry_mode = str(entry['mode']);
            else:
                entry_mode = 'analytics';
            if self.errors:
                return;
            if 'cliset' not in self.conf:
                self.conf['cliset'] = OrderedDict();
                ''' sets last executed cli command id '''
                self.conf['cliset_last_eid'] = 0;
            _is_duplicate_cli = False;
            if entry_mode != 'configure':
                for c in self.conf['cliset']:
                    if 'cli' in self.conf['cliset'][c]:
                        if self.conf['cliset'][c]['cli'] == entry['cli']:
                            _is_duplicate_cli = True;
                            display.vv('duplicate cli command \'' + entry['cli'] + '\'', host=self.info['host']);
                        if self.conf['cliset'][c]['mode'] != entry_mode:
                            if entry_mode == 'noop' or self.conf['cliset'][c]['mode'] == 'noop':
                                continue;
                            self.errors.append('the plugin does not support the mixing of \'configure\' and \'analytics\' modes in the same run');
                            return;
            if _is_duplicate_cli:
                continue;

            if 'pre' in entry:
                entry_tasks_pre = filter(lambda x: len(x) > 0, entry['pre'].split('\n'));
                for entry_task in entry_tasks_pre:
                    if entry_task.strip() == '':
                        continue;
                    self.conf['cliset_last_id'] += 1;
                    self.conf['cliset'][self.conf['cliset_last_id']] = {
                        'format': 'txt',
                        'filename': 'response.' + str(self.conf['cliset_last_id']) + '.txt',
                        'source': 'src',
                        'cli': entry_task,
                        'mode': 'pre',
                        'status': 'unknown',
                        'allow_empty_response': True,
                    };

            entry_tasks = entry['cli'].split('\n');
            for entry_task in entry_tasks:
                if entry_task.strip() == "":
                    continue;
                self.conf['cliset_last_id'] += 1;
                self.conf['cliset'][self.conf['cliset_last_id']] = {};
                if 'format' in entry:
                    self.conf['cliset'][self.conf['cliset_last_id']]['format'] = entry['format'];
                else:
                    self.conf['cliset'][self.conf['cliset_last_id']]['format'] = 'txt';
                if 'saveas' in entry:
                    self.conf['cliset'][self.conf['cliset_last_id']]['filename'] = self._decode_ref(entry['saveas']);
                else:
                    if entry_mode == 'configure':
                        self.conf['cliset'][self.conf['cliset_last_id']]['filename'] = 'response.' + str(self.conf['cliset_last_id']) + '.txt';
                    else:
                        entry_filename = self._get_filename_from_cli(self.info['host'], entry_task, self.conf['cliset'][self.conf['cliset_last_id']]['format']);
                        self.conf['cliset'][self.conf['cliset_last_id']]['filename'] = entry_filename;
                self.conf['cliset'][self.conf['cliset_last_id']]['source'] = src;
                self.conf['cliset'][self.conf['cliset_last_id']]['cli'] = entry_task;
                self.conf['cliset'][self.conf['cliset_last_id']]['mode'] = entry_mode;
                self.conf['cliset'][self.conf['cliset_last_id']]['status'] = 'unknown';
                self.conf['cliset'][self.conf['cliset_last_id']]['allow_empty_response'] = False;
                if entry_tags:
                    self.conf['cliset'][self.conf['cliset_last_id']]['tags'] = entry_tags;
                if 'exceptions' in self.conf and entry_mode == 'analytics':
                    for r in self.conf['exceptions']:
                        if re.match(r['hosts'], self.info['host']) and re.match(r['cli'], entry_task):
                            self.conf['cliset'][self.conf['cliset_last_id']]['status'] = 'skipped';
                            self.conf['cliset'][self.conf['cliset_last_id']]['mode'] = 'noop';

            if 'post' in entry:
                entry_post_tasks = filter(lambda x: len(x) > 0, entry['post'].split('\n'));
                for entry_task in entry_post_tasks:
                    if entry_task.strip() == '':
                        continue;
                    self.conf['cliset_last_id'] += 1;
                    self.conf['cliset'][self.conf['cliset_last_id']] = {
                        'format': 'txt',
                        'filename': 'response.' + str(self.conf['cliset_last_id']) + '.txt',
                        'source': 'src',
                        'cli': entry_task,
                        'mode': 'post',
                        'status': 'unknown',
                        'allow_empty_response': True,
                    };

            for t in entry_tags:
                if t in ['version', 'configuration'] and 'cli' in entry:
                    self.conf[t] = entry['cli'];
        return;


    def _report(self):
        '''
        This function creates JUnit report for each of the hosts in a run.
        '''
        if 'cliset' not in self.conf:
            return;
        r = ['<?xml version="1.0" encoding="UTF-8"?>'];
        r.append('<testsuites>');
        j = {'errors': 0, 'skipped': 0, 'tests': 0, 'failures': 0};
        for _id in self.conf['cliset']:
            h = self.conf['cliset'][_id];
            j['tests'] += 1;
            if 'status' in h:
                if h['status'] == 'failed':
                    j['failures'] += 1;
                    continue;
                if h['status'] == 'skipped':
                    j['skipped'] += 1;
                    continue;
            if 'error_msg' in h:
                j['failures'] += 1;
                continue;
        jtime = (self.conf['time_end'] - self.conf['time_start']) / 1000;
        jts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(self.conf['time_start'] / 1000));
        r.append('  <testsuite name="' + self.info['host'] + '" errors="' + str(j['errors']) + '" skipped="' + str(j['skipped']) + \
                 '" tests="' + str(j['tests']) + '" failures="' + str(j['failures']) + '" time="' + str(jtime) + '" timestamp="' + jts + '">');
        r.append('    <properties>');
        for p in ['host', 'os']:
            r.append('      <property name="' + p + '" value="' + str(self.info[p]) + '" />');
        for p in ['output_dir', 'on_error', 'on_prompt']:
            r.append('      <property name="' + p + '" value="' + str(self.conf[p]) + '" />');
        r.append('    </properties>');
        for _id in self.conf['cliset']:
            h = self.conf['cliset'][_id];
            tc_name = h['cli'];
            if 'time_start' in h and 'time_end' in h:
                tc_time = (h['time_end'] - h['time_start']) / 1000;
            else:
                tc_time = '0';
            r.append('    <testcase name="' + tc_name  + '" time="' + str(tc_time) + '">');
            r.append('      <system-out>');
            r.append('        <![CDATA[');
            for p in ['mode', 'format', 'path', 'sha1', 'sha1_pre', 'source', 'tags', 'pre', 'post', 'saveas', 'lines']:
                if p in h:
                    #r.append('          ' + p + ': ' + str(h[p]));
                    r.append(p + ': ' + str(h[p]));
            r.append('        ]]>');
            r.append('      </system-out>');
            if 'error_msg' in h:
                r.append('      <system-err>');
                r.append('        <![CDATA[');
                for p in h['error_msg']:
                    if isinstance(p, str):
                        r.append(p);
                        #r.append('          ' + p);
                    elif isinstance(p, list):
                        for pi in p:
                            r.append(pi);
                            #r.append('          ' + pi);
                    else:
                        pass;
                r.append('        ]]>');
                r.append('      </system-err>');
            if 'status' in h:
                if h['status'] == 'failed':
                    r.append('      <failure />');
                elif h['status'] == 'skipped':
                    r.append('      <skipped />');
                else:
                    pass;
            r.append('    </testcase>');
        r.append('  </testsuite>');
        r.append('</testsuites>');
        with open(os.path.join(self.conf['temp_dir'], self.info['host'] + '.junit.xml'), 'w') as f:
            f.write('\n'.join(r));
        if self.conf['output_dir'] is not None:
            commit_dir = os.path.join(self.conf['output_dir'], self.info['host']);
            if not os.path.exists(commit_dir):
                try:
                    os.makedirs(commit_dir, mode=0700);
                except:
                    display.display('<' + self.info['host'] + '> ' + traceback.format_exc(), color='red');
                    return;
            with open(os.path.join(self.conf['output_dir'], self.info['host'], self.info['host'] + '.junit.xml'), 'w') as f:
                f.write('\n'.join(r));
        return;


    def _commit(self):
        '''
        This function writes the data collected during this run to
        output directory.
        '''
        if self.conf['output_dir'] is None:
            return;
        commit_dir = os.path.join(self.conf['output_dir'], self.info['host']);
        display.vv('commit directory: ' + commit_dir, host=self.info['host']);
        if not os.path.exists(commit_dir):
            try:
                os.makedirs(commit_dir, mode=0700);
            except:
                display.display('<' + self.info['host'] + '> ' + traceback.format_exc(), color='red');
                return;
        for _id in self.conf['cliset']:
            if 'path' not in self.conf['cliset'][_id]:
                continue;
            if 'filename' not in self.conf['cliset'][_id]:
                continue;
            if 'sha1' not in self.conf['cliset'][_id]:
                continue;
            fn = os.path.join(commit_dir, self.conf['cliset'][_id]['filename']);
            if 'sha1' in self.conf['cliset'][_id]:
                if os.path.exists(fn):
                    if os.path.isfile(fn):
                        if os.access(fn, os.R_OK):
                            self.conf['cliset'][_id]['sha1_pre'] = self._get_sha1_hash(fn);
                            if self.conf['cliset'][_id]['sha1_pre'] != self.conf['cliset'][_id]['sha1']:
                                self.info['changed'] = True;
            try:
                fc = None;
                with open(self.conf['cliset'][_id]['path'], 'r') as f:
                    fc = f.read();
                with open(os.path.join(commit_dir, self.conf['cliset'][_id]['filename']), 'w') as f:
                    f.write(fc);
            except:
                display.display('<' + self.info['host'] + '> ' + traceback.format_exc(), color='red');
                return;
        return;


    @staticmethod
    def _get_sha1_hash(fn):
        with open(fn, 'rb') as f:
            return hashlib.sha1(f.read()).hexdigest();


    @staticmethod
    def _get_filename_from_cli(host, cmd, suffix):
        cmd = cmd.replace('_', '_US_').replace('/', '_FS_').replace('|', '_PIPE_').replace('.', '_DOT_').replace(' ', '.');
        cmd = host + '.' + cmd + '.' + suffix;
        return cmd;
