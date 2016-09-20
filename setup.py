from setuptools import setup;
from setuptools.command.install import install;
from codecs import open;
from os import path;
import unittest;
import os;
import sys;
import re;
import stat;

pkg_name = 'ansible-plugin-clicap';
pkg_ver = '0.6';

def _load_test_suite():
    test_loader = unittest.TestLoader();
    test_suite = test_loader.discover(path.join(pkg_dir, pkg_name, 'tests'), pattern='test_*.py');
    return test_suite;

class InstallAddons(install):
    '''
    Creates custom symlink to ansible site-packages directory
    '''

    def run(self):
        errors = False;
        if not self._find_utility('ssh'):
            print('FAIL: ssh client is not found');
            errors = True;
        if not self._find_utility('expect'):
            print('FAIL: expect utility is not found');
            errors = True;
        if errors:
            print('aborted install');
            return;
        install.run(self);
        '''
        Find current plugin directory
        '''
        ansible_dir = self._find_py_package('ansible');
        if not ansible_dir:
            print('FAIL: ansible is not found');
            return;
        '''
        Find this plugin's directory
        '''
        plugin_dir = self._find_py_package(pkg_name);
        if not plugin_dir:
            print('FAIL: ' + pkg_name + ' is not found');
            return;
        '''
        Create a symlink, i.e. `ln -s TARGET LINK_NAME`
        '''

        for i in ['action', 'callback']:
            symlink_target = os.path.join(plugin_dir, 'plugins/' + i + '/clicap.py');
            symlink_name = os.path.join(ansible_dir, 'plugins/' + i + '/clicap.py');
            try:
                if os.path.exists(symlink_name):
                    os.unlink(symlink_name);
                os.symlink(symlink_target, symlink_name);
                os.chmod(symlink_name, stat.S_IRUSR | stat.S_IWUSR);
            except:
                print('FAIL: an attempt to create a symlink for an ' + i + ' plugin failed');
                return;

    @staticmethod
    def _find_utility(name):
        x = any(os.access(os.path.join(path, name), os.X_OK) for path in os.environ["PATH"].split(os.pathsep));
        return x;

    @staticmethod
    def _find_py_package(name):
        for path in sys.path:
            if not re.search('site-packages', path):
                continue;
            for d in os.listdir(path):
                if os.path.isdir(os.path.join(path, d)):
                    if d != name:
                        continue;
                    return os.path.join(path, d);
        return None;

pkg_dir = path.abspath(path.dirname(__file__));
pkg_license='OSI Approved :: GNU Affero General Public License v3';
pkg_description = 'Ansible plugin for collecting (capturing) command-line (cli) ' + \
              'output from and interacting with network devices.';
pkg_url = 'https://github.com/greenpau/' + pkg_name;
pkg_download_url = 'http://pypi.python.org/packages/source/' + pkg_name[0] + '/' + pkg_name + '/' + pkg_name + '-' + pkg_ver + '.tar.gz';
pkg_author = 'Paul Greenberg';
pkg_author_email = 'paul@greenberg.pro';
pkg_packages = [pkg_name.lower()];
pkg_requires = ['ansible>=2.0'];
pkg_data=[
    '*.yml',
    '*.j2',
    'plugins/callback/*.py',
    'plugins/action/*.py',
    'plugins/action/*.j2',
    'plugins/action/*.yml',
    'plugins/action/files/cli/os/*.yml',
    'README.rst',
];
pkg_platforms='any';
pkg_classifiers=[
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Information Technology',
    'Intended Audience :: System Administrators',
    'Intended Audience :: Telecommunications Industry',
    'License :: ' + pkg_license,
    'Programming Language :: Python',
    'Operating System :: POSIX :: Linux',
    'Topic :: Utilities',
    'Topic :: System :: Networking',
    'Topic :: System :: Networking :: Monitoring',
    'Topic :: System :: Systems Administration',
];
pkg_keywords=['ansible', 'network', 'ssh', 'telnet', 'automation'];
pkg_test_suite='setup._load_test_suite';

pkg_long_description=pkg_description;
with open(path.join(pkg_dir, pkg_name, 'README.rst'), encoding='utf-8') as f:
    pkg_long_description = f.read();

setup(
    name=pkg_name,
    version=pkg_ver,
    description=pkg_description,
    long_description=pkg_long_description,
    url=pkg_url,
    download_url=pkg_download_url,
    author=pkg_author,
    author_email=pkg_author_email,
    license=pkg_license,
    platforms=pkg_platforms,
    classifiers=pkg_classifiers,
    packages=pkg_packages,
    package_data= {
        pkg_name.lower() : pkg_data,
    },
    keywords=pkg_keywords,
    install_requires=pkg_requires,
    test_suite=pkg_test_suite,
    cmdclass={
        'install': InstallAddons,
        'bdist_wheel': InstallAddons,
    },
);
