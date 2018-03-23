#!/usr/bin/env python
import logging

from insights import run

# activate the importer and loader
from insights.core import scripts  # noqa: F401
from scripts import test
from scripts.nested import test2

logging.basicConfig(level=logging.INFO)
run([test.report, test2.report], print_summary=True)
