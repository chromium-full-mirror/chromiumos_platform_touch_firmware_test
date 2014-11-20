# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import sys

from test_suite import TestSuite


def parse_arguments():
  VALID_DUT_TYPES = ['chromeos', 'android']

  parser = optparse.OptionParser()

  # DUT specification information
  parser.add_option('-a', '--addr', dest='addr', default=None,
                    help=('The address of the DUT (ip for CrOS, Device ID ' +
                          'for Android).'))
  parser.add_option('-t', '--type', dest='dut_type', default=None,
                    help='The type of DUT (android or chromeos).')
  parser.add_option('--touchscreen', dest='is_touchscreen',
                    default=False, action='store_true',
                    help=('Use the touchscreen (instead of touchpad) on ' +
                          'the device.'))

  # Lab equipment specification
  parser.add_option('-r', '--robot', dest='has_robot',
                    default=False, action='store_true',
                    help=('Indicate that you have a Google Touchbot that ' +
                          'will perform your gestures for you.'))
  parser.add_option('-f', '--fn_gen', dest='has_fn_gen',
                    default=False, action='store_true',
                    help=('Indicate that you have an HP 33120A function ' +
                          'generator to automate the electric noise tests.'))

  # Test suite settings
  parser.add_option('-i', '--iterations', dest='num_iterations', default=1,
                    type=int, help=('The number of test iterations to run.'))

  (options, args) = parser.parse_args()

  if options.dut_type not in VALID_DUT_TYPES:
      print 'ERROR: invalid dut type "%s"' % options.dut_type
      print 'valid dut types are: %s' % str(VALID_DUT_TYPES)
      sys.exit(1)
  if options.dut_type == 'chromeos' and not options.addr:
      print 'ERROR: You must supply an IP address for ChromeOS DUTs'
      sys.exit(1)

  return options, args


def main():
  # Parse and validate the command line arguments
  options, args = parse_arguments()

  # Create a test flow object that will run the test step by step
  test_suite = TestSuite(options, args)

  # Run through the entire test suite in turn
  while test_suite.RunNextTestAndVariation():
    pass

  return 0


if __name__ == "__main__":
  sys.exit(main())
