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


STANDARD_FINGERTIP = '1round_9mm'

BUFFER_SIZE = 0.1
OVERSHOOT_DISTANCE = 0.05
LEFT = BUFFER_SIZE
OVER_LEFT = -OVERSHOOT_DISTANCE
RIGHT = 1.0 - BUFFER_SIZE
OVER_RIGHT = 1.0 + OVERSHOOT_DISTANCE
TOP = BUFFER_SIZE
OVER_TOP = -OVERSHOOT_DISTANCE
BOTTOM = 1.0 - BUFFER_SIZE
OVER_BOTTOM = 1.0 + OVERSHOOT_DISTANCE
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

LINE_DIRECTION_COORDINATES = {
    tests.GV.LR: ((LEFT, CENTER), (RIGHT, CENTER)),
    tests.GV.RL: ((RIGHT, CENTER), (LEFT, CENTER)),
    tests.GV.TB: ((CENTER, TOP), (CENTER, BOTTOM)),
    tests.GV.BT: ((CENTER, BOTTOM), (CENTER, TOP)),
    tests.GV.BLTR: ((LEFT, BOTTOM), (RIGHT, TOP)),
    tests.GV.BRTL: ((RIGHT, BOTTOM), (LEFT, TOP)),
    tests.GV.TRBL: ((RIGHT, TOP), (LEFT, BOTTOM)),
    tests.GV.TLBR: ((LEFT, TOP), (RIGHT, BOTTOM)),
    tests.GV.CL: ((CENTER, CENTER), (OVER_LEFT, CENTER)),
    tests.GV.CR: ((CENTER, CENTER), (OVER_RIGHT, CENTER)),
    tests.GV.CT: ((CENTER, CENTER), (CENTER, OVER_TOP)),
    tests.GV.CB: ((CENTER, CENTER), (CENTER, OVER_BOTTOM)),
    tests.GV.CUL: ((CENTER, CENTER), (OVER_LEFT, OVER_TOP)),
    tests.GV.CLL: ((CENTER, CENTER), (OVER_LEFT, OVER_BOTTOM)),
    tests.GV.CLR: ((CENTER, CENTER), (OVER_RIGHT, OVER_BOTTOM)),
}

SPEEDS = {
    tests.GV.NORMAL: Touchbot.SPEED_MEDIUM,
    tests.GV.SLOW: Touchbot.SPEED_SLOW,
}

SINGLE_FINGER_LINE_TESTS = [
    tests.ONE_FINGER_TO_EDGE,
    tests.ONE_FINGER_TRACKING,
    tests.ONE_FINGER_TRACKING_FROM_CENTER,
]


def PerformCorrespondingGesture(test, variation_number, robot, device_spec):
  variation = test.variations[variation_number]
  fn = None
  if test.name == tests.NOISE_STATIONARY:
    fn = lambda: _PerformStationaryNoiseTest(variation, robot, device_spec)
  elif test.name in SINGLE_FINGER_LINE_TESTS:
    pause = 1 if test.name == tests.ONE_FINGER_TRACKING_FROM_CENTER else 0
    fn = lambda: _PerformOneFingerLineTest(variation, robot, device_spec, pause)

  if fn is None:
    print color.Fore.RED + 'Error: Robot unable to perform gesture!'
    return None

  return Thread(target=fn)


def _PerformStationaryNoiseTest(variation, robot, device_spec):
  frequency, amplitude, waveform, location = variation
  tap_position = LOCATION_COORDINATES[location]
  fingertip = robot.fingertips[STANDARD_FINGERTIP]
  robot.SingleTipTap(device_spec, fingertip, tap_position, touch_time_s=4)


def _PerformOneFingerLineTest(variation, robot, device_spec, pause_time_s):
  direction, speed = variation
  start, end = LINE_DIRECTION_COORDINATES[direction]
  fingertip = robot.fingertips[STANDARD_FINGERTIP]

  robot.PushSpeed(SPEEDS[speed])
  robot.SingleTipLine(device_spec, fingertip, start, end, pause_time_s)
  robot.PopSpeed()
