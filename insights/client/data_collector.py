"""
Collect all the interesting data for analysis
"""
from __future__ import absolute_import
import os
import errno
import json
from . import archive
import logging
import copy
import glob
from subprocess import Popen, PIPE, STDOUT
from tempfile import NamedTemporaryFile

from ..contrib.soscleaner import SOSCleaner
from .utilities import _expand_paths
from .constants import InsightsConstants as constants
from .insights_spec import InsightsFile, InsightsCommand
from .config import InsightsConfig

APP_NAME = constants.app_name
logger = logging.getLogger(__name__)
# python 2.7
SOSCLEANER_LOGGER = logging.getLogger('soscleaner')
SOSCLEANER_LOGGER.setLevel(logging.ERROR)
# python 2.6
SOSCLEANER_LOGGER = logging.getLogger('insights-client.soscleaner')
SOSCLEANER_LOGGER.setLevel(logging.ERROR)


class DataCollector(object):
    '''
    Run commands and collect files
    '''

    def __init__(self, config, upload_conf, rm_conf, branch_info=None, archive_=None, mountpoint=None):
        self.config = config
        self.upload_conf = upload_conf
        self.rm_conf = rm_conf
        self.branch_info = branch_info
        self.archive = archive_ if archive_ else archive.InsightsArchive()
        self.mountpoint = '/'
        if mountpoint:
            self.mountpoint = mountpoint

    def _write_branch_info(self):
        logger.debug("Writing branch information to archive...")
        self.archive.add_metadata_to_archive(
            json.dumps(self.branch_info), '/branch_info')

    def _run_pre_command(self, pre_cmd):
        '''
        Run a pre command to get external args for a command
        '''
        logger.debug('Executing pre-command: %s', pre_cmd)
        try:
            pre_proc = Popen(pre_cmd, stdout=PIPE, stderr=STDOUT, shell=True)
        except OSError as err:
            if err.errno == errno.ENOENT:
                logger.debug('Command %s not found', pre_cmd)
            return
        stdout, stderr = pre_proc.communicate()
        the_return_code = pre_proc.poll()
        logger.debug("Pre-command results:")
        logger.debug("STDOUT: %s", stdout)
        logger.debug("STDERR: %s", stderr)
        logger.debug("Return Code: %s", the_return_code)
        if the_return_code != 0:
            return []
        return stdout.splitlines()

    def _parse_file_spec(self, spec):
        '''
        Separate wildcard specs into more specs
        '''
        # separate wildcard specs into more specs
        if '*' in spec['file']:
            expanded_paths = _expand_paths(spec['file'])
            if not expanded_paths:
                return []
            expanded_specs = []
            for p in expanded_paths:
                _spec = copy.copy(spec)
                _spec['file'] = p
                expanded_specs.append(_spec)
            return expanded_specs

        else:
            return [spec]

    def _parse_glob_spec(self, spec):
        '''
        Grab globs of things
        '''
        some_globs = glob.glob(spec['glob'])
        if not some_globs:
            return []
        el_globs = []
        for g in some_globs:
            _spec = copy.copy(spec)
            _spec['file'] = g
            el_globs.append(_spec)
        return el_globs

    def _parse_command_spec(self, spec, precmds):
        '''
        Run pre_commands
        '''
        if 'pre_command' in spec:
            precmd_alias = spec['pre_command']
            try:
                precmd = precmds[precmd_alias]
                args = self._run_pre_command(precmd)
                logger.debug('Pre-command results: %s', args)

                expanded_specs = []
                for arg in args:
                    _spec = copy.copy(spec)
                    _spec['command'] = _spec['command'] + ' ' + arg
                    expanded_specs.append(_spec)
                return expanded_specs
            except LookupError:
                logger.debug('Pre-command %s not found. Skipping %s...',
                             precmd_alias, spec['command'])
                return []
        else:
            return [spec]

    def run_specific_specs(self, metadata_spec, conf, rm_conf, exclude, branch_info):
        '''
        Running metadata collection for specific environment
        '''
        logger.debug('Beginning to run collection spec for %s...', metadata_spec)
        if metadata_spec in conf:
            for spec in conf[metadata_spec]:
                if 'file' in spec:
                    spec['archive_file_name'] = spec['file']
                    if rm_conf and 'files' in rm_conf and spec['file'] in rm_conf['files']:
                        logger.warn("WARNING: Skipping file %s", spec['file'])
                        continue
                    else:
                        file_specs = self._parse_file_spec(spec)
                        for s in file_specs:
                            file_spec = InsightsFile(s, exclude, self.mountpoint, self.target_name)
                            self.archive.add_to_archive(file_spec)
                elif 'glob' in spec:
                    glob_specs = self._parse_glob_spec(spec)
                    for g in glob_specs:
                        if rm_conf and 'files' in rm_conf and g['file'] in rm_conf['files']:
                            logger.warn("WARNING: Skipping file %s", g)
                            continue
                        else:
                            glob_spec = InsightsFile(g, exclude, self.mountpoint, self.target_name)
                            self.archive.add_to_archive(glob_spec)
                elif 'command' in spec:
                    if rm_conf and 'commands' in rm_conf and spec['command'] in rm_conf['commands']:
                        logger.warn("WARNING: Skipping command %s", spec['command'])
                        continue
                    else:
                        cmd_specs = self._parse_command_spec(spec, conf['pre_commands'])
                        for s in cmd_specs:
                            cmd_spec = InsightsCommand(s, exclude, self.mountpoint, self.target_name)
                            self.archive.add_to_archive(cmd_spec)
        else:
            logger.debug('Spec metadata type "%s" not found in spec.', metadata_spec)
        logger.debug('Spec metadata collection finished.')

    def run_collection(self, output=True):
        '''
        Run specs and collect all the data
        '''
        if self.rm_conf is None:
            self.rm_conf = {}
        logger.debug('Beginning to run collection spec...')
        exclude = None
        if self.rm_conf:
            try:
                exclude = self.rm_conf['patterns']
            except LookupError:
                logger.debug('Could not parse remove.conf. Ignoring...')

        if self.config['run_specific_specs'] is not None:
            logger.debug('Running specific specs %s', self.config['run_specific_specs'])
            for specific_spec in self.config['run_specific_specs'].split(','):
                logger.debug('Running specific spec %s', specific_spec)
                self.run_specific_specs(specific_spec, conf, self.rm_conf, exclude, branch_info)
                logger.debug('Finished running specific spec %s', specific_spec)
            return

        for c in self.upload_conf['commands']:
            if c['command'] in self.rm_conf.get('commands', []):
                logger.warn("WARNING: Skipping command %s", c['command'])
            elif self.mountpoint == "/" or c.get("image"):
                cmd_specs = self._parse_command_spec(c, self.upload_conf['pre_commands'])
                for s in cmd_specs:
                    cmd_spec = InsightsCommand(self.config, s, exclude, self.mountpoint)
                    if output:
                        self.archive.add_to_archive(cmd_spec)
                    else:
                        print(cmd_spec.command)
        for f in self.upload_conf['files']:
            if f['file'] in self.rm_conf.get('files', []):
                logger.warn("WARNING: Skipping file %s", f['file'])
            else:
                file_specs = self._parse_file_spec(f)
                for s in file_specs:
                    file_spec = InsightsFile(s, exclude, self.mountpoint)
                    if output:
                        self.archive.add_to_archive(file_spec)
                    else:
                        print(file_spec.real_path)
        if 'globs' in self.upload_conf:
            for g in self.upload_conf['globs']:
                glob_specs = self._parse_glob_spec(g)
                for g in glob_specs:
                    if g['file'] in self.rm_conf.get('files', []):
                        logger.warn("WARNING: Skipping file %s", g)
                    else:
                        glob_spec = InsightsFile(g, exclude, self.mountpoint)
                        if output:
                            self.archive.add_to_archive(glob_spec)
                        else:
                            print(glob_spec.real_path)
        logger.debug('Spec collection finished.')

        # collect metadata
        logger.debug('Collecting metadata...')
        self._write_branch_info()
        logger.debug('Metadata collection finished.')

    def done(self, conf):
        """
        Do finalization stuff
        """
        if self.config["obfuscate"]:
            cleaner = SOSCleaner(quiet=True)
            clean_opts = CleanOptions(self.archive.tmp_dir, self.rm_conf)
            fresh = cleaner.clean_report(clean_opts, self.archive.archive_dir)
            if clean_opts.keyword_file is not None:
                os.remove(clean_opts.keyword_file.name)
            return fresh[0]
        return self.archive.create_tar_file()


class CleanOptions(object):
    """
    Options for soscleaner
    """
    def __init__(self, tmp_dir, rm_conf):
        self.report_dir = tmp_dir
        self.domains = []
        self.files = []
        self.quiet = True
        self.keyword_file = None
        self.keywords = None

        if rm_conf:
            try:
                keywords = rm_conf['keywords']
                self.keyword_file = NamedTemporaryFile(delete=False)
                self.keyword_file.write("\n".join(keywords))
                self.keyword_file.flush()
                self.keyword_file.close()
                self.keywords = [self.keyword_file.name]
                logger.debug("Attmpting keyword obfuscation")
            except LookupError:
                pass

        if config["obfuscate_hostname"]:
            self.hostname_path = "insights_commands/hostname"
        else:
            self.hostname_path = None

if __name__ == '__main__':
    from .config import InsightsConfig
    from .collection_rules import InsightsUploadConf
    from .connection import InsightsConnection
    conf = InsightsConfig(auto_config=False, gpg=False)
    conn = InsightsConnection(conf)
    ul_conf, rm_conf = InsightsUploadConf(conf, conn).get_conf(True)
    dc = DataCollector(conf, ul_conf, rm_conf)
    dc.run_collection(output=False)
