#!/usr/bin/env ruby

# name: my_ruby
# type: rule
# requires: hostname

hostname = File.read(ENV["hostname"])
puts "error_key: my_ruby_rule"
puts "hostname: #{hostname}"
