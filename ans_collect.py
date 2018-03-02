#!/usr/bin/env python
from __future__ import print_function
import logging

from collections import namedtuple

from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager

from ans_ctx import AnsibleContext

from insights.core import dr

dr.load_components("ans_specs")
dr.load_components("insights.parsers")
dr.load_components("insights.combiners")


logging.basicConfig(level=logging.WARN)
logging.getLogger("ansible").setLevel(logging.DEBUG)


fields = ["connection", "ssh_args", "retries", "private_key_file", "verbosity", "module_path", "forks", "become", "become_method", "become_user", "check", "diff"]
Options = namedtuple("Options", fields)


def create_context(host="localhost", port=None, options=None):
    loader = DataLoader()
    inventory = InventoryManager(loader=loader)
    inventory.add_host(host, port=port)

    con_type = "local" if host == "localhost" else "smart"

    ssh_args = "-o ControlMaster=auto -o ControlPersist=30m",
    if not options:
        options = Options(connection=con_type,
                          ssh_args=ssh_args,
                          retries=10,
                          private_key_file="~/.ssh/id_rsa",
                          verbosity=4,
                          module_path="",
                          forks=1,
                          become=None,
                          become_method=None,
                          become_user=None,
                          check=False,
                          diff=False)

    return AnsibleContext(inventory, loader, options, {"vault_pass": "secret"}, host)


if __name__ == "__main__":
    import sys
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    ctx = create_context(host)
    broker = dr.Broker()
    broker[AnsibleContext] = ctx
    broker = dr.run(dr.COMPONENTS[dr.GROUPS.single], broker=broker)
    broker.describe(show_missing=False, show_tracebacks=True)
