#!/bin/sh

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script is deployed derectly onto Chromebooks, and is only inteded
# to be run from a ChromeOS device.  It is a wrapper for webplot.py that
# makes it simpler to run webplot on the DUT itself.  If you are attempting
# to plot touch events on a remote DUT (such as one connected to your
# computer via ssh) this script is NOT what you want, you should look into
# running webplot.py directly.

# This script may or may not come with a suffix.
# If this script is installed with emerge, the suffix has been removed.
# If this script is installed with scp, there still exists the suffix.
# Try to remove the suffix any way.
PROG="$(basename $0 .sh)"

# A local die function to print the message and then exit
die() {
  echo -e "$@"
  exit 1
}

# Read command flags
. /usr/share/misc/shflags
DEFINE_boolean grab true 'grab the touch device exclusively' 'g'
DEFINE_boolean kill false 'kill the existing webplot process' 'k'

FLAGS_HELP="USAGE: $PROG [flags]"

FLAGS "$@" || exit 1
eval set -- "${FLAGS_ARGV}"
set -e

get_webplot_process_status() {
  echo $(ps a | egrep "(ssh|python)\s.+${PROG}" | grep -v grep |\
         awk '{print $1}')
}

if [ "$FLAGS_kill" = "$FLAGS_TRUE" ]; then
  process=$(get_webplot_process_status)
  if [ -z "$process" ]; then
    echo 'No existing webplot process.'
  else
    for p in $process; do
      echo killing $p
      kill $p
    done
  fi
  exit 0
fi

# Search for the first python3 webplot directory.
# Priority is given to /usr/lib*.
PROG_DIR="$(find /usr/lib*/python3* /usr/local/lib*/python3* \
            -name "$PROG" -type d -print -quit 2> /dev/null || true)"
if [ -n "$PROG_DIR" ]; then
  echo "Found webplot path in $PROG_DIR"
fi

if [ -z "$PROG_DIR" ]; then
  die "Fail to find the path of $PROG."
fi

# Start webplot if not yet.
if [ -n "$(get_webplot_process_status)" ]; then
  echo "$PROG server has been started already."
else
  # Must run webplot as root as it needs to access system device nodes.
  if [ $USER != root ]; then
    die "Please run $PROG as root."
  fi

  # Tell the user to type URL in chrome as there is no reliable way to
  # launch a chrome tab from command line in chrome os.
  echo "Please type \"localhost\" in the browser."
  echo "Please Press ctrl-c to terminate the webplot server."

  echo "Start $PROG server..."
  [ "$FLAGS_grab" = "$FLAGS_FALSE" ] && grab_option="--nograb"
  exec python3 "${PROG_DIR}/${PROG}".py $grab_option --behind_firewall -p80
fi
