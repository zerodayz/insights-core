#!/usr/bin/env python

from insights import run
from scripts.script1 import my_test
from scripts.nested.script2 import report

run([my_test, report], print_summary=True)
