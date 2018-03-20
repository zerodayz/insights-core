#!/usr/bin/env python
import logging

from insights import run
from insights.core.scripts import load

logging.basicConfig(level=logging.INFO)

path = "example.sh"
with open(path, "U") as f:
    load(path, f.read())

# import the script component we just loaded
from insights_scripts import example  # noqa: F401

run(example, print_summary=True)
