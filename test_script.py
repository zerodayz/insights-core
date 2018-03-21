#!/usr/bin/env python
import logging

from insights import run
from insights.core.scripts import load

logging.basicConfig(level=logging.INFO)

path = "example.sh"
with open(path, "U") as f:
    component = load(path, f.read())
    run(component, print_summary=True)
