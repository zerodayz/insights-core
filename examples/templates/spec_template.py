"""
Sample Spec Template
====================

Copy this template to create your own specs to collect from a host.
"""
from __future__ import print_function

from insights.core.context import HostContext
from insights.core.spec_factory import SpecSet, simple_file, simple_command, glob_file
from insights.core.spec_factory import first_of, foreach_collect, foreach_execute
from insights.core.spec_factory import first_file, listdir


class Specs(SpecSet):
    """
    Choose the type of spec that matches your application.
    """
    hosts = simple_file("/etc/hosts")
    uptime = simple_command("/usr/bin/uptime")
    cpu_cores = glob_file("sys/devices/system/cpu/cpu[0-9]*/online")
    systemid = first_of([
        simple_file("/etc/sysconfig/rhn/systemid"),
        simple_file("/conf/rhn/sysconfig/rhn/systemid")
    ])
    httpd_pid = simple_command("/usr/bin/pgrep -o httpd")
    httpd_limits = foreach_collect(httpd_pid, "/proc/%s/limits")
    ethernet_interfaces = listdir("/sys/class/net", context=HostContext)
    ethtool = foreach_execute(ethernet_interfaces, "/sbin/ethtool %s")
    keystone_conf = first_file([
        "/var/lib/config-data/puppet-generated/keystone/etc/keystone/keystone.conf",
        "/etc/keystone/keystone.conf"
    ])





