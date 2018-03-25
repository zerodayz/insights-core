#!/usr/bin/env python

from insights import run
from scripts.ruby_script import my_ruby
from scripts.script1 import my_test
from scripts.nested.script2 import report

run([my_ruby, my_test, report], print_summary=True)
