"""
Sample Rule Template
====================

Copy this template to create your own rule to evaluate data collected
from a host or an archive.
"""
from __future__ import print_function

from insights import make_fail, make_pass, rule
from insights.combiners.redhat_release import RedHatRelease

# Error key used in make_response
ERROR_KEY = "TIME_TO_UPGRADE_RHEL"
SUCCESS_KEY = "GOOD_RHEL_VERSION"

# Jinja2 template displayed for make_response results
# Use this to format your rule output when running from
# the command line with insights-run.  This will not be
# used in the Insights user interface.
CONTENT = {
    ERROR_KEY: "This system is running an older version of RHEL: {{redhat}}",
    SUCCESS_KEY: "This system has a more recent version of RHEL: {{redhat}}"
}


# Pattern for rule decorator
# @rule(required, required, ... , [at least one required from list], optional=[not required, will be None if not present])
@rule(RedHatRelease)
def report(rhr):
    """
    Rule args match the args in the @rule decorator.
    Args are parser objects so use methods provided by the
    parsers.

    If spec is multioutput parameter is set in insights/specs/__init__.py
    then arg will be a list of parsers that the rule will need to loop over.

    Whether a rule returns a make_fail or a make_pass or both is strictly up
    to the rule developer.
    """
    if rhr.major == 5:
        return make_fail(ERROR_KEY, redhat=rhr.version)
    # else:
    #    return make_pass("NOT_TOO_OLD", redhat=rhr.version)
