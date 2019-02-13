from insights.core.context import KubeContext

from insights.core.spec_factory import simple_command
from insights.specs import Specs, format_rpm

from functools import partial

simple_command = partial(simple_command, context=KubeContext)
rpm_format = format_rpm()


class KubernetesSpecs(Specs):
    hostname = simple_command("hostname")
    ps_aux = simple_command("/bin/ps aux")
    ps_auxcww = simple_command("/bin/ps auxcww")
    ps_auxww = simple_command("/bin/ps auxww")
    ps_ef = simple_command("/bin/ps -ef")
    ps_eo = simple_command("/usr/bin/ps -eo pid,ppid,comm")
    installed_rpms = simple_command("rpm -qa --qf '%s'" % rpm_format)
