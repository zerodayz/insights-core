#!/usr/bin/env python
import logging

from insights import run

# activate the importer and loader
from insights.core import scripts  # noqa: F401
from scripts.test import my_test
from scripts.nested.test2 import report

logging.basicConfig(level=logging.INFO)
run([my_test, report], print_summary=True)
