#!/usr/bin/env bash

# maybe have type: datasource as well
# type: rule

# requires: hosts
# requires: ethtool

# multiple on a line means "at least of these" - must be comma delimited
# requires: redhat_release, uname

# optional: lsblk

# messages can be sent to the logger for this plugin by writing to stderr
echo "this is a warning!" >&2

# simple files or commands are in files whose names are in environment variables
# named the same as the dependency

un=`cat $uname`
rhr=`cat $redhat_release`

# either build up some json to return, or return "key: value" lines where each line
# will split on the first colon to determine key and the rest of the line is the value.
error_key is required

echo error_key: example
echo uname: $un
echo release: $rhr

# names of multiple files or command outputs are separated by a semi-colon
IFS=';' read -ra etho <<< "$ethtool"
for eth in "${etho[@]}"; do
    cat $eth | ag "Settings for|Link detected" >&2
    echo >&2
done
