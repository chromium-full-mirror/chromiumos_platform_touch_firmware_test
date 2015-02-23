# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import sys

import mt
import plotter

from remote import ChromeOSTouchDevice, AndroidTouchDevice
from report import Report
from test_suite import TestSuite


def parse_arguments():
  VALID_DUT_TYPES = ['chromeos', 'android', 'replay']
  VALID_MODES = ['performance', 'noise', 'full']
  VALID_PROTOCOLS = [mt.MTA, mt.MTB, 'auto']
  parser = optparse.OptionParser()

  # DUT specification information
  parser.add_option('-a', '--addr', dest='addr', default=None,
                    help=('The address of the DUT (ip for CrOS, Device ID '
                          'for Android, or a filename to replay old results).'))
  parser.add_option('-t', '--type', dest='dut_type', default=None,
                    help='The type of DUT (android, chromeos, or replay).')
  parser.add_option('--touchscreen', dest='is_touchscreen',
                    default=False, action='store_true',
                    help=('Use the touchscreen (instead of touchpad) on '
                          'the device.'))

  parser.add_option('--protocol', dest='protocol', default='auto',
                    help=('Manually specify the multitouch protocol for the '
                          'DUT.  This should be detected automatically, but '
                          'in the event that fails, you may specify "mtb" or '
                          '"mta" with this flag to over-ride it.'))

  # Lab equipment specification
  parser.add_option('-r', '--robot', dest='has_robot',
                    default=False, action='store_true',
                    help=('Indicate that you have a Google Touchbot that '
                          'will perform your gestures for you.'))
  parser.add_option('-f', '--fn_gen', dest='has_fn_gen',
                    default=False, action='store_true',
                    help=('Indicate that you have an HP 33120A function '
                          'generator to automate the electric noise tests.'))
  parser.add_option('-m', '--mode', dest='mode', default='performance',
                    help=('Which mode to run the test suite in. Options are '
                          '(performance, noise, or full) with performance as '
                          'the default selection.'))

  # Test suite settings
  parser.add_option('-i', '--iterations', dest='num_iterations', default=1,
                    type=int, help=('The number of test iterations to run.'))
  parser.add_option('--plot_only', dest='plot_only', default=False,
                    action='store_true',
                    help=('Only plot touch evets.  Do not run any tests.'))

  (options, args) = parser.parse_args()

  if options.dut_type not in VALID_DUT_TYPES:
    print 'ERROR: invalid dut type "%s"' % options.dut_type
    print 'valid dut types are: %s' % str(VALID_DUT_TYPES)
    sys.exit(1)
  if options.dut_type == 'chromeos' and not options.addr:
    print 'ERROR: You must supply an IP address for ChromeOS DUTs'
    sys.exit(1)
  if options.protocol not in VALID_PROTOCOLS:
    print 'ERROR: invalid protocol "%s"' % options.protocol
    print 'valid protocols are: %s' % str(VALID_PROTOCOLS)
    sys.exit(1)
  if options.mode not in VALID_MODES:
    print 'ERROR: invalid mode "%s"' % options.mode
    print 'valid modes are: %s' % str(VALID_MODES)
    sys.exit(1)

  return options, args


def initialize_touch_device(options):
  """ Using the supplied options connect to the DUT """
  # Open a connection to the device specified
  if options.dut_type == 'chromeos':
    touch_dev = ChromeOSTouchDevice(options.addr, options.is_touchscreen)
  elif options.dut_type == 'android':
    touch_dev = AndroidTouchDevice(options.addr, True)
  else:
    return None

  # If the user specified the device's mt protocol override it now
  if options.protocol != 'auto':
    touch_dev.protocol = options.protocol

  return touch_dev

def main():
  # Parse and validate the command line arguments
  options, args = parse_arguments()

  # Connect to the DUT
  touch_dev = initialize_touch_device(options)

  if options.plot_only:
    # Show the live events as they come in instead of running any tests
    print 'Displaying live touch events from your DUT.  Press Ctrl+C to stop.'
    plotter.live_display(touch_dev)
    return 0

  if options.dut_type != 'replay':
    # Create a test flow object that will run the test step by step
    test_suite = TestSuite(touch_dev, options, args)

    # Run through the entire test suite in turn
    while test_suite.RunNextTestAndVariation():
      pass

    # The test suite should have a fully populated Report object now, filled
    # with the results of all the test runs.
    report = test_suite.report

    # Save this report into a default location as a backup in case you want
    # to replay it later.
    report.SaveToDisk('last_report.p')
  else:
    # We are trying to replay an old report from a file on disk.  Load the Report
    # directly from the specified file instead of running the test over again.
    report = Report.FromFile(options.addr)

  # Generate an HTML version of the Report and write it to disk
  html_report = report.GenerateHtml()
  with open('report.html', 'w') as fo:
    fo.write(html_report)

  return 0


if __name__ == "__main__":
  sys.exit(main())
