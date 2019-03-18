"""
Sample Parser Template
======================

Copy this template to create your own parser to parse data collected
from a host or an archive.
"""
from __future__ import print_function
from collections import namedtuple

from insights import get_active_lines, parser, Parser
from insights.specs import Specs


@parser(Specs.hosts)
class HostParser(Parser):
    """
    Parses the results of the ``hosts`` Specs

    Parsers using the Parser base class must implement the
    parse_content(self, content) method.  The content
    attribute is a list containing the output of the spec.

    It is up to the parser developer to choose the appropriate
    attributes and methods to implement in the parser.  All
    attributes should be set in parse_content.

    Attributes:
        hosts (list): List of the namedtuple Host
            which are the contents of the hosts file
            including ``.ip``, ``.host``, and ``.aliases``.
    """
    Host = namedtuple("Host", ["ip", "host", "aliases"])

    def parse_content(self, content):
        """
        Method to parse the contents of file ``/etc/hosts``

        This method must be implemented by each parser.

        Arguments:
            content (list): List of strings that are the contents
                of the /etc/hosts file.
        """
        self.hosts = []
        for line in get_active_lines(content):
            # remove inline comments
            line = line.partition("#")[0].strip()

            # break the line into parts
            parts = line.split()
            ip, host = parts[:2]
            aliases = parts[2:]

            self.hosts.append(HostParser.Host(ip, host, aliases))

    def __repr__(self):
        """ str: Returns string representation of the class """
        me = self.__class__.__name__
        msg = "%s([" + ", ".join([str(d) for d in self.hosts]) + "])"
        return msg % me
