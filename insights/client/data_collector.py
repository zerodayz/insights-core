"""
Collect all the interesting data for analysis
"""
from __future__ import absolute_import
import os
import json
from . import archive
import logging
import six
from tempfile import NamedTemporaryFile

from insights import collect
from ..contrib.soscleaner import SOSCleaner
from .utilities import generate_machine_id
from .constants import InsightsConstants as constants

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
    def __init__(self, config, archive_=None, mountpoint=None):
        self.config = config
        self.archive = archive_ if archive_ else archive.InsightsArchive()
        self.mountpoint = '/'
        if mountpoint:
            self.mountpoint = mountpoint
        self.rm_conf = self.get_rm_conf()

    def _write_branch_info(self, branch_info):
        logger.debug("Writing branch information to archive...")
        self.archive.add_metadata_to_archive(
            json.dumps(branch_info), '/branch_info')
        # temporary. probably not needed
        self.archive.add_metadata_to_archive(
            generate_machine_id(), '/etc/redhat-access-insights/machine-id')

    def get_rm_conf(self):
        """
        Get excluded files config from remove_file.
        """
        if not os.path.isfile(self.config.remove_file):
            return {}

        # Convert config object into dict
        parsedconfig = ConfigParser.RawConfigParser()
        parsedconfig.read(self.config.remove_file)
        rm_conf = {}

        for item, value in parsedconfig.items('remove'):
            if six.PY3:
                rm_conf[item] = value.strip().encode('utf-8').decode('unicode-escape').split(',')
            else:
                rm_conf[item] = value.strip().decode('string-escape').split(',')

        return rm_conf

    def run_collection(self, branch_info):
        '''
        Run specs and collect all the data
        '''
        if self.config.analyze_container:
            context_class = 'DockerImageContext'
        else:
            context_class = 'HostContext'
        manifest = {
            'version': 0,
            'context': {
                'class': 'insights.core.context.' + context_class,
                'args': {
                    'timeout': self.config.cmd_timeout,
                    'root': self.mountpoint
                }
            },
            'default_component_enabled': False,
            'blacklist': self.rm_conf,
            'packages': ['insights.specs.default'],
            'persist': [{
                'name': 'insights.specs.Specs',
                'enabled': True
            }],
            'configs': [{
                'name': 'insights.specs.Specs',
                'enabled': True
            }, {
                'name': 'insights.specs.default.DefaultSpecs',
                'enabled': True
            }, {
                'name': 'insights.parsers.hostname',
                'enabled': True
            }, {
                'name': 'insights.parsers.facter',
                'enabled': True
            }, {
                'name': 'insights.parsers.systemid',
                'enabled': True
            }, {
                'name': 'insights.combiners.hostname',
                'enabled': True
            }, {
                'name': 'insights.core.spec_factory',
                'enabled': True
            }]
        }
        collect.collect(manifest=manifest, tmp_path=self.archive.archive_dir)
        self._write_branch_info(branch_info)

    def done(self):
        """
        Do finalization stuff
        """
        if self.config.obfuscate:
            cleaner = SOSCleaner(quiet=True)
            clean_opts = CleanOptions(
                self.config, self.archive.tmp_dir, self.rm_conf)
            fresh = cleaner.clean_report(clean_opts, self.archive.archive_dir)
            if clean_opts.keyword_file is not None:
                os.remove(clean_opts.keyword_file.name)
            return fresh[0]
        return self.archive.create_tar_file()


class CleanOptions(object):
    """
    Options for soscleaner
    """
    def __init__(self, config, tmp_dir, rm_conf):
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

        if config.obfuscate_hostname:
            # default to its original location
            self.hostname_path = 'insights_commands/hostname'
        else:
            self.hostname_path = None
