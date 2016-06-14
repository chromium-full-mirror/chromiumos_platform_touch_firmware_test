# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import sys
from touchbot import Touchbot, DeviceSpec

def parse_arguments():
  parser = optparse.OptionParser()
  parser.add_option('-n', '--name', dest='name', default='unknown_device',
                    help='The name of this DUT.  This is used by the robot to '
                         'store calibration info')
  parser.add_option('--num_passes', dest='num_passes', default=30, type=int,
                    help='How many passes to make over the laser')
  parser.add_option('-s', '--speed', dest='speed', default=60,
                    type=int, help='How fast to move the finger (0-100)')

  (options, args) = parser.parse_args()

  if options.speed > 100 or options.speed <= 0:
    print 'ERROR: Speed (%d) must be between 0 and 100!' % options.speed
    sys.exit(1)
  if options.num_passes <= 0:
    print ('ERROR: Meaningful test must use a positive number of passes, '
           'not %d.' % options.num_passes)
    sys.exit(1)

  return options, args


def main():
  # Parse and validate the command line arguments
  options, args = parse_arguments()

  # Connect to the robot
  robot = Touchbot()
  if not robot.comm:
    print 'Error: Unable to connect to the robot.'
    sys.exit(1)

  # Load the device spec (or calibrate a new spec if none is found)
  device_spec_filename = './%s.p' % options.name
  if os.path.isfile(device_spec_filename):
    print 'Precalibrated spec found at "%s".' % device_spec_filename
    print 'If this was unintended, delete that file or choose a new name.'
    device_spec = DeviceSpec.LoadFromDisk(device_spec_filename)
  else:
    print 'No spec found (%s)' % device_spec_filename
    print 'Please calibrate for %s, as instructed below.' % options.name
    device_spec = robot.CalibrateDevice(device_spec_filename)

  # Tell the robot to perform a Quickstep gesture
  fingertips = [robot.fingertips[Touchbot.CALIBRATION_FINGERTIP1]]
  robot.Quickstep(device_spec, fingertips, options.num_passes, options.speed)

  return 0


if __name__ == "__main__":
  sys.exit(main())
