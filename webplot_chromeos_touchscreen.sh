#! /bin/bash
#
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
#
# This is a simple helper script that runs webplot for you with the
# correct commandline parameters to plot the touch events on a
# remote ChromeOS touchscreen.
#
# You simply supply it an IP address and it does the rest, starting it
# up and opening a browser for you automatically
#
# Example Usage:
#    ./webplot_chromeos_touchscreen.sh 192.168.0.4

if [ "$#" -ne 1 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ];
then
  echo "Usage: $0 IP_ADDRESS"
  echo "Example: $0 192.168.0.4"
fi

python webplot/webplot.py -t chromeos -d "$1" -p 8080 \
                          --is_touchscreen \
                          --automatically_start_browser
