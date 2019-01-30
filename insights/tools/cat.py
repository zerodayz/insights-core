#!/usr/bin/env python
"""
The cat module allows you to execute an insights datasource and write its
output to stdout. A string representation of the datasource is written to
stderr before the output.

>>> insights-cat hostname
CommandOutputProvider("/usr/bin/hostname -f")
alonzo

Pass -q if you want only the datasource information.

>>> insights-cat -q ethtool
CommandOutputProvider("/sbin/ethtool docker0")
CommandOutputProvider("/sbin/ethtool enp0s31f6")
CommandOutputProvider("/sbin/ethtool lo")
CommandOutputProvider("/sbin/ethtool tun0")
CommandOutputProvider("/sbin/ethtool virbr0")
CommandOutputProvider("/sbin/ethtool virbr0-nic")
CommandOutputProvider("/sbin/ethtool wlp3s0")
"""
from __future__ import print_function
import argparse
import logging
import os
import sys
import uuid
import yaml

from contextlib import contextmanager

import colorama as C
from insights import apply_configs, create_context, dr, extract, HostContext
from insights.core.spec_factory import ContentProvider

C.init()


def parse_args():
    p = argparse.ArgumentParser("Insights spec runner.")
    p.add_argument("-c", "--config", help="Configure components.")
    p.add_argument("-p", "--plugins", default="", help="Comma-separated list without spaces of package(s) or module(s) containing plugins.")
    p.add_argument("-q", "--quiet", action="store_true", help="Only show commands or paths.")
    p.add_argument("-m", "--machine", action="store_true", help="Only show commands or paths.")
    p.add_argument("-D", "--debug", action="store_true", help="Show debug level information.")
    p.add_argument("spec", nargs=1, help="Spec to dump.")
    p.add_argument("archive", nargs="?", help="Archive or directory to analyze.")
    return p.parse_args()


def configure_logging(debug):
    if debug:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)


def parse_plugins(raw):
    for path in raw.split(","):
        path = path.strip()
        if path.endswith(".py"):
            path, _ = os.path.splitext(path)
        path = path.rstrip("/").replace("/", ".")
        yield path


def load_default_plugins():
    for f in ["default", "insights_archive", "sos_archive", "jdr_archive"]:
        dr.load_components("insights.specs.%s" % f, continue_on_error=False)


def load_plugins(raw):
    if raw:
        for p in parse_plugins(raw):
            dr.load_components(p, continue_on_error=False)


def configure(config):
    if config:
        with open(config) as f:
            apply_configs(yaml.safe_load(f))


def get_spec(fqdn):
    if "." not in fqdn:
        fqdn = "insights.specs.Specs.%s" % fqdn
    return dr.get_component(fqdn)


@contextmanager
def create_broker(root=None):
    if not root:
        broker = dr.Broker()
        broker[HostContext] = HostContext()
        yield broker
    else:
        def from_dir(d):
            broker = dr.Broker()
            ctx = create_context(d, None)
            broker[ctx.__class__] = ctx
            return broker

        if os.path.isdir(root):
            yield from_dir(root)
        else:
            with extract(root) as ex:
                yield from_dir(ex.tmp_dir)


class Dumper(object):
    def __init__(self, quiet=False, machine=False):
        self.quiet = quiet
        self.machine = machine

    def dump_human(self, value):
        value = value if isinstance(value, list) else [value]
        for v in value:
            print(C.Fore.BLUE + str(v) + C.Style.RESET_ALL, file=sys.stderr)
            if not self.quiet:
                if isinstance(v, ContentProvider):
                    for d in v.stream():
                        print(d)

    def dump_one(self, value):
        print("One")
        if isinstance(value, ContentProvider):
            for d in value.stream():
                print(d)

    def dump_many(self, value):
        uid = uuid.uuid4()
        print("Many")
        for v in value:
            print(str(uid))
            for d in v.stream():
                print(d)

    def dump_machine(self, value):
        if isinstance(value, list):
            self.dump_many(value)
        else:
            self.dump_one(value)

    def dump_spec(self, value):
        if not value:
            return

        if self.machine:
            self.dump_machine(value)
        else:
            self.dump_human(value)

    def dump_error(self, spec, broker):
        if spec in broker.exceptions:
            for ex in broker.exceptions[spec]:
                print(broker.tracebacks[ex], file=sys.stderr)

        if spec in broker.missing_requirements:
            missing = broker.missing_requirements[spec]
            required = missing[0]
            at_least_one = missing[1]

            buf = sys.stderr

            print("Missing Dependencies:", file=buf)
            if required:
                print("    Requires:", file=buf)
                for d in required:
                    print("        %s" % dr.get_name(d), file=buf)
            if at_least_one:
                for alo in at_least_one:
                    print("    At Least One Of:", file=buf)
                    for d in alo:
                        print("        %s" % dr.get_name(d), file=buf)


def run(spec, archive, dumper):
    with create_broker(archive) as broker:
        value = dr.run(spec, broker=broker).get(spec)
        if value:
            dumper.dump_spec(value)
        else:
            dumper.dump_error(spec, broker)
            sys.exit(1)


def main():
    args = parse_args()
    configure_logging(args.debug)
    load_default_plugins()
    load_plugins(args.plugins)
    configure(args.config)
    spec = get_spec(args.spec[0])
    if not spec:
        print("Spec not found: %s" % args.spec[0], file=sys.stderr)
        sys.exit(1)
    dumper = Dumper(quiet=args.quiet, machine=args.machine)
    run(spec, args.archive, dumper)


if __name__ == "__main__":
    main()
