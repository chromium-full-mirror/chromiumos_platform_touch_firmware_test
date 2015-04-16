# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This is a module containing functions that allow the test suite to
determine the specifics of the gesture and execute them on the touchbot.
In essence, you use this class to go from a Test object to the robot
actually performing the correct gesture on the pad.
"""

from threading import Thread

import colorama as color

import tests
from touchbot import Touchbot


BUFFER_SIZE = 0.1
LEFT = BUFFER_SIZE
RIGHT = 1.0 - BUFFER_SIZE
TOP = BUFFER_SIZE
BOTTOM = 1.0 - BUFFER_SIZE
CENTER = 0.5

LOCATION_COORDINATES = {
    tests.GV.TL: (LEFT, TOP),
    tests.GV.TR: (RIGHT, TOP),
    tests.GV.BL: (LEFT, BOTTOM),
    tests.GV.BR: (RIGHT, BOTTOM),
    tests.GV.TS: (CENTER, TOP),
    tests.GV.BS: (CENTER, BOTTOM),
    tests.GV.LS: (LEFT, CENTER),
    tests.GV.RS: (RIGHT, CENTER),
    tests.GV.CENTER: (CENTER, CENTER),
}


def PerformCorrespondingGesture(test, variation_number, robot, device_spec):
  variation = test.variations[variation_number]
  fn = None
  if test.name == tests.NOISE_STATIONARY:
    fn = lambda: _PerformStationaryNoiseTest(variation, robot, device_spec)

  if fn is None:
    print color.Fore.RED + 'Error: Robot unable to perform gesture!'
    return None

  return Thread(target=fn)

def _PerformStationaryNoiseTest(variation, robot, device_spec):
  frequency, amplitude, waveform, location = variation
  robot.Tap(device_spec, LOCATION_COORDINATES[location], touch_time_s=4)
