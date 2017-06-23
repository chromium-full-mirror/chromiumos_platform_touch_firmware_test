#!/bin/sh

# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script is deployed directly onto Chromebooks, and is only intended
# to be run from a ChromeOS device. It is a wrapper for heatmapplot.py that
# makes it simpler to run heatmapplot on the DUT itself.  If you are attempting
# to plot heatmap on a remote DUT (such as one connected to your computer via
# ssh) this script is NOT what you want, you should look into running
# heatmapplot.py directly.

PROG="heatmapplot.py"

# A local die function to print the message and then exit
die() {
  echo -e "$@"
  exit 1
}

FLAGS_HELP="USAGE: $PROG [flags]"

# Search the heatmapplot directory.
# Stop at the first found heatmapplot directory. Priority is given to /usr/lib*.
DIRS="/usr/lib* /usr/local/lib*"
for d in $DIRS; do
  PROG_FILE="$(find $d -name $PROG -type f -print -quit)"
  if [ -n "$PROG_FILE" ]; then
    break
  fi
done

if [ -z "$PROG_FILE" ]; then
  die "Fail to find the path of $PROG."
fi

# Must run heatmapplot as root as it needs to access system device nodes.
if [ $USER != root ]; then
  die "Please run $PROG as root."
fi

# Tell the user to type URL in chrome as there is no reliable way to
# launch a chrome tab from command line in chrome os.
echo "Please type \"localhost\" in the browser."
echo "Please Press ctrl-c to terminate the heatmapplot server."

echo "Start $PROG server..."
[ "$FLAGS_grab" = "$FLAGS_FALSE" ] && grab_option="--nograb"
exec python "${PROG_FILE}" --behind_firewall
