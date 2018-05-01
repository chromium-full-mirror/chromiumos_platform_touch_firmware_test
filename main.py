# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import inspect
import optparse
import os
import sys
from subprocess import Popen, PIPE

import colorama as color

from remote import ChromeOSTouchDevice, AndroidTouchDevice, mt
from remote import ElanTouchScreenDevice, ElanTouchDevice, SynapticsTouchDevice
from report import Report
from test_suite import TestSuite

REPORT_LOCATION_FORMAT = '%s_report.html'

def parse_arguments():
  VALID_DUT_TYPES = ['chromeos', 'android', 'elan_i2c', 'elan_ts_i2c',
                     'synaptics_ts_i2c', 'replay']
  VALID_MODES = ['performance', 'noise', 'full']
  VALID_PROTOCOLS = [mt.MTA, mt.MTB, mt.STYLUS, 'auto']
  parser = optparse.OptionParser()

  # DUT specification information
  parser.add_option('-a', '--addr', dest='addr', default=None,
                    help=('The address of the DUT (ip for CrOS, Device ID '
                          'for Android, or a filename to replay old results).'))
  parser.add_option('-t', '--type', dest='dut_type', default=None,
                    help='The type of DUT (android, chromeos, or replay).')
  parser.add_option('-d', '--device_num', dest='device_num',
                    default=None, type=int,
                    help='The device number of the touch sensor if you know it')
  parser.add_option('--touchscreen', dest='is_touchscreen',
                    default=False, action='store_true',
                    help=('Use the touchscreen (instead of touchpad) on '
                          'the device.'))

  parser.add_option('--protocol', dest='protocol', default='auto',
                    help=('Manually specify the multitouch protocol for the '
                          'DUT.  This should be detected automatically, but '
                          'in the event that fails, you may specify "mtb", '
                          '"mta", or "stylus" with this flag to over-ride it.'))
  parser.add_option('-n', '--name', dest='name', default='unknown_device',
                    help='The name of this DUT.  This is used by the robot to '
                         'store calibration data and is only needed if you are '
                         'using the touchbot.  Simply keep the name consistent '
                         'across multiple tests on the same DUT to avoid '
                         'having to recalibrate the robot each time.')

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
  parser.add_option('--title', dest='title', default=None,
                    help='An optional title to put at the top of the report.')
  parser.add_option('--test_version', dest='test_version', default=None,
                    help=('An optionally overridden test version string.  This '
                          'string will appear at the top of the report.  If '
                          'left undefined the most recent git commit hash is '
                          'used by default.'))

  (options, args) = parser.parse_args()

  if options.dut_type not in VALID_DUT_TYPES:
    print 'ERROR: invalid dut type "%s"' % options.dut_type
    print 'valid dut types are: %s' % str(VALID_DUT_TYPES)
    sys.exit(1)
  elif options.dut_type == 'chromeos' and not options.addr:
    print 'ERROR: You must supply an IP address for ChromeOS DUTs'
    sys.exit(1)
  # Aardvark setup does not support the physical button
  elif options.dut_type in ['android', 'elan_ts_i2c',
                            'elan_i2c', 'synaptics_ts_i2c']:
    options.is_touchscreen = True

  if options.protocol not in VALID_PROTOCOLS:
    print 'ERROR: invalid protocol "%s"' % options.protocol
    print 'valid protocols are: %s' % str(VALID_PROTOCOLS)
    sys.exit(1)
  if options.mode not in VALID_MODES:
    print 'ERROR: invalid mode "%s"' % options.mode
    print 'valid modes are: %s' % str(VALID_MODES)
    sys.exit(1)

  # If they didn't manually specify a test_version string, generate the default
  # By looking up the most recent commit in the touch_firmware_test git repo.
  if options.test_version is None:
    src_file = inspect.getfile(inspect.currentframe())
    root_path = os.path.dirname(os.path.realpath(src_file))
    git_path = os.path.join(root_path, '.git')
    args = ['git', '--git-dir', git_path, 'log', '--oneline', '-n1']
    options.test_version = Popen(args, stdout=PIPE).communicate()[0]

  return options, args


def initialize_touch_device(options):
  """ Using the supplied options connect to the DUT """
  # Open a connection to the device specified
  print (color.Style.DIM + color.Fore.RED +
         'Please do not touch the device until the test starts!')
  print 'Connecting to remote touch device...'
  if options.dut_type == 'chromeos':
    touch_dev = ChromeOSTouchDevice(options.addr, options.is_touchscreen,
                                    options.protocol,
                                    device_num=options.device_num)
  elif options.dut_type == 'android':
    touch_dev = AndroidTouchDevice(options.addr, True, options.protocol,
                                   options.device_num)
  elif options.dut_type == 'elan_i2c':
    touch_dev = ElanTouchDevice(options.addr)
  elif options.dut_type == 'elan_ts_i2c':
    touch_dev = ElanTouchScreenDevice(options.addr)
  elif options.dut_type == 'synaptics_ts_i2c':
    touch_dev = SynapticsTouchDevice(options.addr)
  else:
    return None

  return touch_dev

def main():
  base_dir = os.getenv('TOUCH_REPORT_OUTPUT', '.')
  print base_dir
  color.init(autoreset=True)

  # Parse and validate the command line arguments
  options, args = parse_arguments()

  if options.dut_type != 'replay':
    # Connect to the DUT
    touch_dev = initialize_touch_device(options)

    # Create a test flow object that will run the test step by step
    test_suite = TestSuite(touch_dev, options, args)

    # Run through the entire test suite in turn
    while test_suite.RunNextTestAndVariation():
      pass
    test_suite.StopPlotter()

    # The test suite should have a fully populated Report object now, filled
    # with the results of all the test runs.
    report = test_suite.report

    # Save this report into a default location as a backup in case you want
    # to replay it later.
    report.SaveToDisk(base_dir + '/last_report.p')
  else:
    # We are trying to replay an old report from a file on disk.  Load it
    # directly from the specified file instead of running the test over again.
    report = Report.FromFile(options.addr)

  # Generate an HTML version of the Report and write it to disk
  report_filename = REPORT_LOCATION_FORMAT % options.mode
  report_path = base_dir + "/" + report_filename;
  print (color.Fore.MAGENTA + 'FW Testing Complete.  Report is being generated '
         'now, and will be stored on disk as "%s"' % report_path)
  html_report = report.GenerateHtml()
  with open(report_path, 'w') as fo:
    fo.write(html_report)

  return 0


if __name__ == "__main__":
  sys.exit(main())
