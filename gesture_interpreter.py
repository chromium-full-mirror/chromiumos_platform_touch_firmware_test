# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This is a module containing functions that allow the test suite to
determine the specifics of the gesture and execute them on the touchbot.
In essence, you use this class to go from a Test object to the robot
actually performing the correct gesture on the pad.
"""

import math
from threading import Thread

import colorama as color

import tests
from touchbot import Touchbot


STANDARD_FINGERTIP = '1round_9mm'
STANDARD_SECONDARY_FINGERTIP = '2round_9mm'
FAT_FINGERTIP = '1round_14mm'
FAT_SECONDARY_FINGERTIP = '2round_14mm'
NOISE_TESTING_FINGERTIP = '1round_12mm'
THREE_FINGER_FINGERTIP = 'three_fingers'
FOUR_FINGER_FINGERTIP = 'four_fingers'
FIVE_FINGER_FINGERTIP = 'five_fingers'

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

STATIONARY_FINGER_LOCATION = {
    tests.GV.LR: LOCATION_COORDINATES[tests.GV.TS],
    tests.GV.RL: LOCATION_COORDINATES[tests.GV.BS],
    tests.GV.TB: LOCATION_COORDINATES[tests.GV.LS],
    tests.GV.BT: LOCATION_COORDINATES[tests.GV.RS],
}

SPEEDS = {
    tests.GV.NORMAL: Touchbot.SPEED_MEDIUM,
    tests.GV.SLOW: Touchbot.SPEED_SLOW,
    tests.GV.FAST: Touchbot.SPEED_FAST,
}

ANGLES = {
    tests.GV.HORIZONTAL: 0,
    tests.GV.VERTICAL: 90,
    tests.GV.DIAGONAL: 45,
}

ONE_FINGERTIP_TAP_TESTS = [
  tests.ONE_FINGER_TAP,
  tests.REPEATED_TAPS,
  tests.THREE_FINGER_TAP,
  tests.FOUR_FINGER_TAP,
  tests.FIVE_FINGER_TAP,
]

TAP_TEST_FINGERTIPS = {
  tests.ONE_FINGER_TAP: STANDARD_FINGERTIP,
  tests.REPEATED_TAPS: STANDARD_FINGERTIP,
  tests.THREE_FINGER_TAP: THREE_FINGER_FINGERTIP,
  tests.FOUR_FINGER_TAP: FOUR_FINGER_FINGERTIP,
  tests.FIVE_FINGER_TAP: FIVE_FINGER_FINGERTIP,
}

SINGLE_FINGER_LINE_TESTS = [
    tests.ONE_FINGER_TO_EDGE,
    tests.ONE_FINGER_TRACKING,
    tests.ONE_FINGER_TRACKING_FROM_CENTER,
    tests.ONE_FINGER_SWIPE,
]

TWO_FINGER_LINE_TESTS = [
    tests.TWO_FINGER_TRACKING,
    tests.TWO_CLOSE_FINGERS_TRACKING,
    tests.TWO_FAT_FINGERS_TRACKING,
    tests.TWO_FINGER_SWIPE,
]

PHYSICAL_CLICK_TESTS = [
    tests.ONE_FINGER_PHYSICAL_CLICK,
    tests.TWO_FINGER_PHYSICAL_CLICK,
]


def _ComputePerpendicularAngle(start, end):
  """ Compute the fingertip angle to be perpendicular to the
  movement direction.

  The robot's X/Y axes are not in the same direction as the touch device's,
  they are flipped.

  DUT  x ---->      Robot  y ---->
      y                   x
      |                   |
      |                   |
      \/                  \/

  As a result the angle is computed in the DUT space, but then must have
  its sign flipped before being used in any commands to the robot or
  everything will be wrong since it's a clockwise angle instead of counter-
  clockwise.
  """
  x1, y1 = start
  x2, y2 = end
  dy = y2 - y1
  dx = x2 - x1
  return -1 * (math.degrees(math.atan2(y2 - y1, x2 - x1)) + 90)


def PerformCorrespondingGesture(test, variation_number, robot, device_spec):
  variation = test.variations[variation_number]
  fn = None

  if test.name == tests.NOISE_STATIONARY:
    fn = lambda: _PerformStationaryNoiseTest(variation, robot, device_spec)

  elif test.name == tests.NOISE_LINE:
    fn = lambda: _PerformLineNoiseTest(variation, robot, device_spec)

  elif test.name in ONE_FINGERTIP_TAP_TESTS:
    fingertip = robot.fingertips[TAP_TEST_FINGERTIPS[test.name]]
    num_taps = 20 if test.name == tests.REPEATED_TAPS else 1
    vertical_offset = 0
    if test.name != tests.ONE_FINGER_TAP:
      vertical_offset = robot.LARGE_FINGERTIP_VERTICAL_OFFSET
    fn = lambda: _PerformOneFingertipTapTest(
                      variation, robot, device_spec, fingertip,
                      vertical_offset, num_taps)

  elif test.name == tests.TWO_FINGER_TAP:
    fn = lambda: _PerformTwoFingerTapTest(variation, robot, device_spec)

  elif test.name in PHYSICAL_CLICK_TESTS:
    fingertips = [robot.fingertips[STANDARD_FINGERTIP]]
    if test.name == tests.TWO_FINGER_PHYSICAL_CLICK:
      fingertips.append(robot.fingertips[STANDARD_SECONDARY_FINGERTIP])
    fn = lambda: _PerformPhysicalClickTest(variation, robot, device_spec,
                                           fingertips)

  elif test.name == tests.DRUMROLL:
    fn = lambda: _PerformDrumroll(variation, robot, device_spec)

  elif test.name in SINGLE_FINGER_LINE_TESTS:
    pause = 1 if test.name == tests.ONE_FINGER_TRACKING_FROM_CENTER else 0
    is_swipe = (test.name == tests.ONE_FINGER_SWIPE)
    fn = lambda: _PerformOneFingerLineTest(variation, robot, device_spec,
                                           pause, is_swipe)

  elif test.name in TWO_FINGER_LINE_TESTS:
    spacing = 5
    fingertips = [robot.fingertips[STANDARD_FINGERTIP],
                  robot.fingertips[STANDARD_SECONDARY_FINGERTIP]]
    is_swipe = (test.name == tests.TWO_FINGER_SWIPE)
    if test.name == tests.TWO_CLOSE_FINGERS_TRACKING:
      spacing = 0
    elif test.name == tests.TWO_FAT_FINGERS_TRACKING:
      spacing = 10
      fingertips = [robot.fingertips[FAT_FINGERTIP],
                    robot.fingertips[FAT_SECONDARY_FINGERTIP]]
    fn = lambda: _PerformTwoFingerLineTest(variation, robot, device_spec,
                                           fingertips, spacing, is_swipe)

  elif test.name == tests.RESTING_FINGER_PLUS_2ND_FINGER_MOVE:
    moving_fingertip = robot.fingertips[STANDARD_SECONDARY_FINGERTIP]
    stationary_location = LOCATION_COORDINATES[tests.GV.BL]
    fn = lambda: _PerformRestingFingerTest(variation, robot, device_spec,
                                           moving_fingertip,
                                           stationary_location)

  elif test.name == tests.FAT_FINGER_MOVE_WITH_RESTING_FINGER:
    moving_fingertip = robot.fingertips[FAT_SECONDARY_FINGERTIP]
    direction, speed = variation
    stationary_location = STATIONARY_FINGER_LOCATION[direction]
    fn = lambda: _PerformRestingFingerTest(variation, robot, device_spec,
                                           moving_fingertip,
                                           stationary_location)

  elif test.name == tests.PINCH_TO_ZOOM:
    fn = lambda: _PerformPinchTest(variation, robot, device_spec)

  elif test.name == tests.DRAG_THUMB_EDGE:
    fn = lambda: _PerformThumbEdgeTest(variation, robot, device_spec)

  elif test.name == tests.SQUARE_RESOLUTION:
    fn = lambda: _PerformSquareResolutionTest(variation, robot, device_spec)

  if fn is None:
    print(color.Fore.RED + 'Robot unable to perform gesture! Skipping...')
    return None

  return Thread(target=fn)


def _PerformStationaryNoiseTest(variation, robot, device_spec):
  frequency, amplitude, waveform, location = variation
  tap_position = LOCATION_COORDINATES[location]
  fingertip = robot.fingertips[NOISE_TESTING_FINGERTIP]
  robot.Tap(device_spec, [fingertip], tap_position, touch_time_s=4)

def _PerformLineNoiseTest(variation, robot, device_spec):
  frequency, amplitude, waveform, direction = variation
  start, end = LINE_DIRECTION_COORDINATES[direction]
  fingertip = robot.fingertips[NOISE_TESTING_FINGERTIP]
  robot.Line(device_spec, [fingertip], start, end, pause_s=1, swipe=False)

def _PerformOneFingertipTapTest(variation, robot, device_spec, fingertip,
                                vertical_offset, num_taps):
  location, = variation
  tap_position = LOCATION_COORDINATES[location]
  robot.Tap(device_spec, [fingertip], tap_position,
            vertical_offset=vertical_offset, num_taps=num_taps)


def _PerformTwoFingerTapTest(variation, robot, device_spec):
  angle, = variation

  fingertip1 = robot.fingertips[STANDARD_FINGERTIP]
  fingertip2 = robot.fingertips[STANDARD_SECONDARY_FINGERTIP]
  fingertips = [fingertip1, fingertip2]

  robot.Tap(device_spec, fingertips, (CENTER, CENTER), angle=ANGLES[angle])


def _PerformOneFingerLineTest(variation, robot, device_spec, pause_time_s,
                              is_swipe):
  direction, speed = variation
  start, end = LINE_DIRECTION_COORDINATES[direction]
  fingertip = robot.fingertips[STANDARD_FINGERTIP]

  robot.PushSpeed(SPEEDS[speed])
  robot.Line(device_spec, [fingertip], start, end, pause_s=pause_time_s,
             swipe=is_swipe)
  robot.PopSpeed()


def _PerformTwoFingerLineTest(variation, robot, device_spec, fingertips,
                              spacing_mm, is_swipe):
  direction, speed = variation
  start, end = LINE_DIRECTION_COORDINATES[direction]
  angle = _ComputePerpendicularAngle(start, end)

  robot.PushSpeed(SPEEDS[speed])
  robot.Line(device_spec, fingertips, start, end, fingertip_spacing=spacing_mm,
             fingertip_angle=angle, swipe=is_swipe)
  robot.PopSpeed()


def _PerformRestingFingerTest(variation, robot, device_spec, moving_fingertip,
                              stationary_location):
  direction, speed = variation
  start, end = LINE_DIRECTION_COORDINATES[direction]

  stationary_fingertip = robot.fingertips[STANDARD_FINGERTIP]

  robot.PushSpeed(SPEEDS[speed])
  robot.LineWithStationaryFinger(device_spec, stationary_fingertip,
                                 moving_fingertip, start, end,
                                 stationary_location)
  robot.PopSpeed()

def _PerformPinchTest(variation, robot, device_spec):
  direction, angle = variation

  min_spread = 15
  max_spread = min(device_spec.Height(), device_spec.Width(),
                   robot.MAX_FINGER_DISTANCE)
  if direction == tests.GV.ZOOM_OUT:
    start_distance, end_distance = max_spread, min_spread
  else:
    start_distance, end_distance = min_spread, max_spread

  fingertips = [robot.fingertips[STANDARD_FINGERTIP],
                robot.fingertips[STANDARD_SECONDARY_FINGERTIP]]

  robot.PushSpeed(SPEEDS[tests.GV.NORMAL])
  robot.Pinch(device_spec, fingertips, (CENTER, CENTER), ANGLES[angle],
              start_distance, end_distance)
  robot.PopSpeed()

def _PerformThumbEdgeTest(variation, robot, device_spec):
  fingertip_type, direction = variation
  start, end = LINE_DIRECTION_COORDINATES[direction]
  angle = _ComputePerpendicularAngle(start, end)

  fingertip = robot.fingertips[fingertip_type]

  robot.PushSpeed(SPEEDS[tests.GV.NORMAL])
  robot.Line(device_spec, [fingertip], start, end, fingertip_angle=angle)
  robot.PopSpeed()

def _PerformPhysicalClickTest(variation, robot, device_spec, fingertips):
  location, = variation
  click_position = LOCATION_COORDINATES[location]
  robot.Click(device_spec, fingertips, click_position)

def _PerformDrumroll(variation, robot, device_spec):
  fingertips = [robot.fingertips[STANDARD_FINGERTIP],
                robot.fingertips[STANDARD_SECONDARY_FINGERTIP]]
  location = LOCATION_COORDINATES[tests.GV.CENTER]
  robot.Drumroll(device_spec, fingertips, location)

def _PerformSquareResolutionTest(variation, robot, device_spec):
  fingertip = robot.fingertips[STANDARD_FINGERTIP]
  location = LOCATION_COORDINATES[tests.GV.CENTER]
  robot.Draw45DegreeLineSegment(device_spec, [fingertip], location)
