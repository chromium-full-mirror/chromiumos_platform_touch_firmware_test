# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Define the actual tests that will be run in the touch FW test suite

Here all the actual definition of the tests takes place.  Things such as
test names, variations, and which validators to use for which test are
all set up in this file.  If you want to add or modify a test, this is
the place to do it.
"""

from constants import GV
from test import Test
from validator import *


# All the test names
NOISE_LINE = 'noise_line'
NOISE_STATIONARY = 'noise_stationary'
ONE_FINGER_TRACKING = 'one_finger_tracking'
ONE_FINGER_TO_EDGE = 'one_finger_to_edge'
TWO_FINGER_TRACKING = 'two_finger_tracking'
FINGER_CROSSING = 'finger_crossing'
ONE_FINGER_SWIPE = 'one_finger_swipe'
TWO_FINGER_SWIPE = 'two_finger_swipe'
PINCH_TO_ZOOM = 'pinch_to_zoom'
ONE_FINGER_TAP = 'one_finger_tap'
TWO_FINGER_TAP = 'two_finger_tap'
ONE_FINGER_PHYSICAL_CLICK = 'one_finger_physical_click'
TWO_FINGER_PHYSICAL_CLICK = 'two_fingers_physical_click'
STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS = \
        'stationary_finger_not_affected_by_2nd_finger_taps'
FAT_FINGER_MOVE_WITH_RESTING_FINGER = 'fat_finger_move_with_resting_finger'
DRAG_EDGE_THUMB = 'drag_edge_thumb'
TWO_CLOSE_FINGERS_TRACKING = 'two_close_fingers_tracking'
RESTING_FINGER_PLUS_2ND_FINGER_MOVE = 'resting_finger_plus_2nd_finger_move'
TWO_FAT_FINGERS_TRACKING = 'two_fat_fingers_tracking'
FIRST_FINGER_TRACKING_AND_SECOND_FINGER_TAPS = \
        'first_finger_tracking_and_second_finger_taps'
DRUMROLL = 'drumroll'
RAPID_TAPS = 'rapid_taps_20'
ONE_FINGER_TRACKING_FROM_CENTER = 'one_finger_tracking_from_center'

# Basic tests are ones that require no special hardware to perform
BASIC_TESTS = [ONE_FINGER_TRACKING, ONE_FINGER_TO_EDGE, TWO_FINGER_TRACKING,
  FINGER_CROSSING, ONE_FINGER_SWIPE, TWO_FINGER_SWIPE, PINCH_TO_ZOOM,
  ONE_FINGER_TAP, TWO_FINGER_TAP, ONE_FINGER_PHYSICAL_CLICK,
  TWO_FINGER_PHYSICAL_CLICK,
  STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS,
  FAT_FINGER_MOVE_WITH_RESTING_FINGER, DRAG_EDGE_THUMB,
  TWO_CLOSE_FINGERS_TRACKING, RESTING_FINGER_PLUS_2ND_FINGER_MOVE,
  TWO_FAT_FINGERS_TRACKING, FIRST_FINGER_TRACKING_AND_SECOND_FINGER_TAPS,
  DRUMROLL, RAPID_TAPS, ONE_FINGER_TRACKING_FROM_CENTER
]
# These tests require a function generator connected to a probe so the
# test suite can simulate electrical noise conditions.
FN_GEN_TESTS = [NOISE_LINE, NOISE_STATIONARY]


# Define the pass/fail criteria for the various validators
NO_GAP_CRITERIA = '<= 1.8, ~ +1.0'
RANGE_CRITERIA = '<= 0.01, ~ +0.07'
REPORT_RATE_CRITERIA = '>= 60'
LINEARITY_CRITERIA = '<= 0.8, ~ +2.4'
RELAXED_LINEARITY_CRITERIA = '<= 1.5, ~ +3.0'
STATIONARY_FINGER_CRITERIA = '<= 1.0'


# Definitions for the test specifics
tests_dict = {
  NOISE_STATIONARY:
  Test(
    name=NOISE_STATIONARY,
    variations=((GV.LOW_FREQUENCY, GV.MED_FREQUENCY, GV.HIGH_FREQUENCY),
                (GV.HALF_AMPLITUDE, GV.MAX_AMPLITUDE),
                (GV.SQUARE_WAVE,),
                (GV.TL, GV.TR, GV.BL, GV.BR, GV.TS, GV.BS, GV.LS, GV.RS,
                 GV.CENTER),
    ),
    prompt='Hold one finger on the {3} of the touch surface with a '
           '{0} {1} {2} in noise.',
    subprompt={
        GV.TL: ('top left corner',),
        GV.TR: ('top right corner',),
        GV.BL: ('bottom left corner',),
        GV.BR: ('bottom right corner',),
        GV.TS: ('top edge',),
        GV.BS: ('bottom side',),
        GV.LS: ('left hand side',),
        GV.RS: ('right hand side',),
        GV.CENTER: ('center',),
        GV.LOW_FREQUENCY: ('5kHz',),
        GV.MED_FREQUENCY: ('500kHz',),
        GV.HIGH_FREQUENCY: ('1MHz',),
        GV.HALF_AMPLITUDE: ('10Vpp',),
        GV.MAX_AMPLITUDE: ('20Vpp',),
        GV.SQUARE_WAVE: ('square wave',),
    },
    validators=(
      CountTrackingIDValidator('== 1'),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA),
    ),
  ),
  NOISE_LINE:
  Test(
    name=NOISE_LINE,
    variations=((GV.LOW_FREQUENCY, GV.MED_FREQUENCY, GV.HIGH_FREQUENCY),
                (GV.HALF_AMPLITUDE, GV.MAX_AMPLITUDE),
                (GV.SQUARE_WAVE,),
                (GV.BLTR,),
                (GV.NORMAL,),
    ),
    prompt='Draw a straight line from {3} with a {0} {1} {2} in noise.',
    subprompt={
      GV.LOW_FREQUENCY: ('5kHz',),
      GV.MED_FREQUENCY: ('500kHz',),
      GV.HIGH_FREQUENCY: ('1MHz',),
      GV.HALF_AMPLITUDE: ('10Vpp',),
      GV.MAX_AMPLITUDE: ('20Vpp',),
      GV.SQUARE_WAVE: ('square wave',),
      GV.NORMAL: ('',),
      GV.BLTR: ('bottom left to top right',),
    },
    validators=(
      CountTrackingIDValidator('== 1'),
      LinearityValidator(LINEARITY_CRITERIA),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),
  ONE_FINGER_TRACKING:
  Test(
    name=ONE_FINGER_TRACKING,
    variations=((GV.LR, GV.RL, GV.TB, GV.BT, GV.BLTR, GV.TRBL),
                (GV.SLOW, GV.NORMAL),
    ),
    prompt='Take {2} to draw a straight, {0} line {1} using a ruler.',
    subprompt={
      GV.LR: ('horizontal', 'from left to right',),
      GV.RL: ('horizontal', 'from right to left',),
      GV.TB: ('vertical', 'from top to bottom',),
      GV.BT: ('vertical', 'from bottom to top',),
      GV.BLTR: ('diagonal', 'from bottom left to top right',),
      GV.TRBL: ('diagonal', 'from top right to bottom left',),
      GV.SLOW: ('3 seconds',),
      GV.NORMAL: ('1 second',),
    },
    validators=(
      CountTrackingIDValidator('== 1'),
      LinearityValidator(LINEARITY_CRITERIA),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),

  ONE_FINGER_TO_EDGE:
  Test(
    name=ONE_FINGER_TO_EDGE,
    variations=((GV.CL, GV.CR, GV.CT, GV.CB),
                (GV.SLOW,),
    ),
    prompt='Take {2} to draw a striaght {0} line {1}.',
    subprompt={
      GV.CL: ('horizontal', 'from the center off left edge',),
      GV.CR: ('horizontal', 'from the center off right edge',),
      GV.CT: ('vertical', 'from the center  off top edge',),
      GV.CB: ('vertical', 'from the center off bottom edge',),
      GV.SLOW: ('2 seconds',),
    },
    validators=(
      CountTrackingIDValidator('== 1'),
      LinearityValidator(LINEARITY_CRITERIA),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
      RangeValidator(RANGE_CRITERIA),
    ),
  ),

  TWO_FINGER_TRACKING:
  Test(
    name=TWO_FINGER_TRACKING,
    variations=((GV.LR, GV.RL, GV.TB, GV.BT, GV.BLTR, GV.TRBL),
                (GV.SLOW, GV.NORMAL),
    ),
    prompt='Take {2} to draw a {0} line {1} using a ruler '
           'with TWO fingers at the same time.',
    subprompt={
      GV.LR: ('horizontal', 'from left to right',),
      GV.RL: ('horizontal', 'from right to left',),
      GV.TB: ('vertical', 'from top to bottom',),
      GV.BT: ('vertical', 'from bottom to top',),
      GV.BLTR: ('diagonal', 'from bottom left to top right',),
      GV.TRBL: ('diagonal', 'from top right to bottom left',),
      GV.SLOW: ('3 seconds',),
      GV.NORMAL: ('1 second',),
    },
    validators=(
      CountTrackingIDValidator('== 2'),
      LinearityValidator(LINEARITY_CRITERIA, finger=0),
      LinearityValidator(LINEARITY_CRITERIA, finger=1),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),

  FINGER_CROSSING:
  Test(
    # also covers stationary_finger_not_affected_by_2nd_moving_finger
    name=FINGER_CROSSING,
    variations=((GV.LR, GV.RL, GV.TB, GV.BT, GV.BLTR, GV.TRBL),
                (GV.SLOW, GV.NORMAL),
    ),
    prompt='Place one stationary finger near the center of the '
           'touch surface, then take {2} to draw a straight line '
           '{0} {1} with a second finger',
    subprompt={
      GV.LR: ('from left to right', 'above the stationary finger'),
      GV.RL: ('from right to left', 'below the stationary finger'),
      GV.TB: ('from top to bottom',
              'on the right to the stationary finger'),
      GV.BT: ('from bottom to top',
              'on the left to the stationary finger'),
      GV.BLTR: ('from the bottom left to the top right',
                'above the stationary finger',),
      GV.TRBL: ('from the top right to the bottom left',
                'below the stationary finger'),
      GV.SLOW: ('3 seconds',),
      GV.NORMAL: ('1 second',),
    },
    validators=(
      CountTrackingIDValidator('== 2'),
      LinearityValidator(LINEARITY_CRITERIA, finger=1),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA, finger=0),
    ),
  ),

  ONE_FINGER_SWIPE:
  Test(
    name=ONE_FINGER_SWIPE,
    variations=(GV.BLTR, GV.TRBL),
    prompt='Use ONE finger to quickly swipe {0}.',
    subprompt={
      GV.BLTR: ('from the bottom left to the top right',),
      GV.TRBL: ('from the top right to the bottom left',),
    },
    validators=(
      CountTrackingIDValidator('== 1'),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),

  TWO_FINGER_SWIPE:
  Test(
    name=TWO_FINGER_SWIPE,
    variations=(GV.TB, GV.BT),
    prompt='Use TWO fingers to quickly swipe {0}.',
    subprompt={ GV.TB: ('from top to bottom',),
      GV.BT: ('from bottom to top',),
    },
    validators=(
      CountTrackingIDValidator('== 2'),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),

  PINCH_TO_ZOOM:
  Test(
    name=PINCH_TO_ZOOM,
    variations=(GV.ZOOM_IN, GV.ZOOM_OUT),
    prompt='Using two fingers, preform a "{0}" pinch by bringing'
           'your fingers {1}.',
    subprompt={
      GV.ZOOM_IN: ('zoom in', 'farther apart'),
      GV.ZOOM_OUT: ('zoom out', 'closer together'),
    },
    validators=(
      CountTrackingIDValidator('== 2'),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),

  ONE_FINGER_TAP:
  Test(
    name=ONE_FINGER_TAP,
    variations=(GV.TL, GV.TR, GV.BL, GV.BR, GV.TS, GV.BS, GV.LS, GV.RS,
                GV.CENTER),
    prompt='Use one finger to tap on the {0} of the touch surface.',
    subprompt={
      GV.TL: ('top left corner',),
      GV.TR: ('top right corner',),
      GV.BL: ('bottom left corner',),
      GV.BR: ('bottom right corner',),
      GV.TS: ('top edge',),
      GV.BS: ('bottom side',),
      GV.LS: ('left hand side',),
      GV.RS: ('right hand side',),
      GV.CENTER: ('center',),
    },
    validators=(
      CountTrackingIDValidator('== 1'),
      StationaryTapValidator(STATIONARY_FINGER_CRITERIA),
    ),
  ),

  TWO_FINGER_TAP:
  Test(
    name=TWO_FINGER_TAP,
    variations=(GV.HORIZONTAL, GV.VERTICAL, GV.DIAGONAL),
    prompt='Use two fingers aligned {0} to tap the center of the '
           'touch surface.',
    subprompt={
      GV.HORIZONTAL: ('horizontally',),
      GV.VERTICAL: ('vertically',),
      GV.DIAGONAL: ('diagonally',),
    },
    validators=(
      CountTrackingIDValidator('== 2'),
      StationaryTapValidator(STATIONARY_FINGER_CRITERIA),
    ),
  ),

  ONE_FINGER_PHYSICAL_CLICK:
  Test(
    name=ONE_FINGER_PHYSICAL_CLICK,
    variations=(GV.CENTER, GV.BL, GV.BS, GV.BR),
    prompt='Use one finger to physically click the {0} of the '
           'touch surface.',
    subprompt={
      GV.CENTER: ('center',),
      GV.BL: ('bottom left corner',),
      GV.BS: ('bottom side',),
      GV.BR: ('bottom right corner',),
    },
    validators=(
      CountTrackingIDValidator('== 1'),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA),
    ),
  ),

  TWO_FINGER_PHYSICAL_CLICK:
  Test(
    name=TWO_FINGER_PHYSICAL_CLICK,
    variations=None,
    prompt='Use two fingers physically click the center of the '
           'touch surface.',
    subprompt=None,
    validators=(
      CountTrackingIDValidator('== 2'),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA),
    ),
  ),

  STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS:
  Test(
    name=STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS,
    variations=None,
    prompt='Place your one stationary finger in the middle of the '
           'touch surface, and use a second finger to tap '
           'all around it many times (50)',
    subprompt=None,
    validators=(
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA, finger=0),
    ),
  ),

  FAT_FINGER_MOVE_WITH_RESTING_FINGER:
  Test(
    name=FAT_FINGER_MOVE_WITH_RESTING_FINGER,
    variations=(GV.LR, GV.RL, GV.TB, GV.BT),
    prompt='With a stationary finger on the {0} of the touch surface, '
           'draw a straight line with a FAT finger {1} {2} it.',
    subprompt={
      GV.LR: ('center', 'from left to right', 'below'),
      GV.RL: ('bottom edge', 'from right to left', 'above'),
      GV.TB: ('center', 'from top to bottom', 'on the right to'),
      GV.BT: ('center', 'from bottom to top', 'on the left to'),
    },
    validators=(
      CountTrackingIDValidator('== 2'),
      LinearityValidator(RELAXED_LINEARITY_CRITERIA, finger=1),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA, finger=0),
    ),
  ),

  DRAG_EDGE_THUMB:
  Test(
    name=DRAG_EDGE_THUMB,
    variations=(GV.LR, GV.RL, GV.TB, GV.BT),
    prompt='Drag the edge of your thumb {0} in a straight line '
           'across the touch surface',
    subprompt={
      GV.LR: ('horizontally from left to right',),
      GV.RL: ('horizontally from right to left',),
      GV.TB: ('vertically from top to bottom',),
      GV.BT: ('vertically from bottom to top',),
    },
    validators=(
      CountTrackingIDValidator('== 1'),
      LinearityValidator(RELAXED_LINEARITY_CRITERIA),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),

  TWO_CLOSE_FINGERS_TRACKING:
  Test(
    name=TWO_CLOSE_FINGERS_TRACKING,
    variations=(GV.LR, GV.TB, GV.TLBR),
    prompt='With two fingers close together (lightly touching each '
           'other) in a two finger scrolling gesture, draw a {0} '
           'line {1}.',
    subprompt={
      GV.LR: ('horizontal', 'from left to right',),
      GV.TB: ('vertical', 'from top to bottom',),
      GV.TLBR: ('diagonal', 'from the top left to the bottom right',),
    },
    validators=(
      CountTrackingIDValidator('== 2'),
      LinearityValidator(RELAXED_LINEARITY_CRITERIA, finger=0),
      LinearityValidator(RELAXED_LINEARITY_CRITERIA, finger=1),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),

  RESTING_FINGER_PLUS_2ND_FINGER_MOVE:
  Test(
    name=RESTING_FINGER_PLUS_2ND_FINGER_MOVE,
    variations=((GV.TLBR, GV.BRTL),
                (GV.SLOW,),
    ),
    prompt='With a stationary finger in the bottom left corner, take '
           '{1} to draw a straight line {0} with a second finger.',
    subprompt={
      GV.TLBR: ('from the top left to the bottom right',),
      GV.BRTL: ('from the bottom right to the top left',),
      GV.SLOW: ('3 seconds',),
    },
    validators=(
      CountTrackingIDValidator('== 2'),
      LinearityValidator(LINEARITY_CRITERIA, finger=1),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA, finger=0),
    ),
  ),

  TWO_FAT_FINGERS_TRACKING:
  Test(
    name=TWO_FAT_FINGERS_TRACKING,
    variations=(GV.LR, GV.RL),
    prompt='Use two FAT fingers separated by about 1cm to draw '
           'a straight line {0}.',
    subprompt={
      GV.LR: ('from left to right',),
      GV.RL: ('from right to left',),
    },
    validators=(
      CountTrackingIDValidator('== 2'),
      LinearityValidator(RELAXED_LINEARITY_CRITERIA, finger=0),
      LinearityValidator(RELAXED_LINEARITY_CRITERIA, finger=1),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),

  FIRST_FINGER_TRACKING_AND_SECOND_FINGER_TAPS:
  Test(
    name=FIRST_FINGER_TRACKING_AND_SECOND_FINGER_TAPS,
    variations=(GV.TLBR, GV.BRTL),
    prompt='While drawing a straight line {0} slowly (~3 seconds), '
           'tap the bottom left corner with a second finger '
           'gently 3 times.',
    subprompt={
      GV.TLBR: ('from top left to bottom right',),
      GV.BRTL: ('from bottom right to top left',),
    },
    validators=(
      CountTrackingIDValidator('== 4'),
      LinearityValidator(LINEARITY_CRITERIA, finger=0),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),

  DRUMROLL:
  Test(
    name=DRUMROLL,
    variations=(GV.FAST, ),
    prompt='Use the index and middle finger of one hand to make a '
           '"drum roll" {0} by alternately tapping each finger '
           'for 5 seconds.',
    subprompt={
      GV.FAST: ('as fast as possible',),
    },
    validators=(),
    timeout = 2,
  ),

  RAPID_TAPS:
  Test(
    name=RAPID_TAPS,
    variations=(GV.TL, GV.BR, GV.CENTER),
    prompt='Tap the {0} of the touch surface 20 times quickly',
    subprompt={
      GV.TL: ('top left corner',),
      GV.TS: ('top edge',),
      GV.TR: ('top right corner',),
      GV.LS: ('left edge',),
      GV.CENTER: ('center',),
      GV.RS: ('right edge',),
      GV.BL: ('bottom left corner',),
      GV.BS: ('bottom edge',),
      GV.BR: ('bottom right corner',),
    },
    validators=(
      CountTrackingIDValidator('== 20'),
      StationaryTapValidator(STATIONARY_FINGER_CRITERIA),
    ),
    timeout = 2,
  ),

  ONE_FINGER_TRACKING_FROM_CENTER:
  Test(
    name=ONE_FINGER_TRACKING_FROM_CENTER,
    variations=((GV.CR, GV.CT, GV.CUL, GV.CLL),
                (GV.SLOW, GV.NORMAL),
    ),
    prompt='Place a stationary finger on the center of the touch '
           'surface for about 1 second, and then take {2} to draw a '
           '{0} line {1}.',
    subprompt={
      GV.CR: ('horizontal', 'to the right',),
      GV.CT: ('vertical', 'to the top',),
      GV.CUL: ('diagonal', 'to the upper left',),
      GV.CLL: ('diagonal', 'to the lower left',),
      GV.SLOW: ('2 seconds',),
      GV.NORMAL: ('1 second',),
    },
    validators=(
      CountTrackingIDValidator('== 1'),
      LinearityValidator(LINEARITY_CRITERIA),
      NoGapValidator(NO_GAP_CRITERIA),
      ReportRateValidator(REPORT_RATE_CRITERIA),
    ),
  ),
}


def generate_test_list(options):
  """ Returns a list of all the legal Test objects, given the options """
  test_names = BASIC_TESTS
  if options.has_fn_gen:
    test_names.extend(FN_GEN_TESTS)
  return [tests_dict[test_name] for test_name in test_names]
