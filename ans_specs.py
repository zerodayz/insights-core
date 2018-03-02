from functools import partial

from insights.specs import Specs
from insights.specs.default import format_rpm
from insights.core.spec_factory import foreach_execute, glob_file, listdir, simple_command, simple_file

from ans_ctx import AnsibleContext

foreach_execute = partial(foreach_execute, context=AnsibleContext)
glob_file = partial(glob_file, context=AnsibleContext)
listdir = partial(listdir, context=AnsibleContext)
simple_command = partial(simple_command, context=AnsibleContext)
simple_file = partial(simple_file, context=AnsibleContext)


class AnsibleSpecs(Specs):
    hosts = simple_file("/etc/hosts")
    ifcfg = glob_file("/etc/sysconfig/network-scripts/ifcfg-*")
    eth_dir = listdir("/sys/class/net")
    ethtool = foreach_execute(eth_dir, "/sbin/ethtool %s")
    installed_rpms = simple_command("/usr/bin/rpm -qa --qf '%s'" % format_rpm())
    hostname = simple_command("/usr/bin/hostname -f")
    uptime = simple_command("/usr/bin/uptime")
