#!/usr/bin/env tclsh

# type: rule
# name: my_tcl_rule
# requires: redhat_release
# requires: uname

set fp [open $::env(redhat_release) r]
set redhat_release [read $fp]
close $fp

set fp [open $::env(uname) r]
set uname [read $fp]
close $fp

puts "error_key: tcl_key"
puts "redhat_release: ${redhat_release}"
puts "uname: ${uname}"
