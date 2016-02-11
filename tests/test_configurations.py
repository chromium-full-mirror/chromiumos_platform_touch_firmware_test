# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Define the actual tests that will be run in the touch FW test suite

Here all the actual definition of the tests takes place.  Things such as
test names, variations, and which validators to use for which test are
all set up in this file.  If you want to add or modify a test, this is
the place to do it.
"""

import colorama as color
import sys

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
THREE_FINGER_TAP = 'three_finger_tap'
FOUR_FINGER_TAP = 'four_finger_tap'
FIVE_FINGER_TAP = 'five_finger_tap'
ONE_FINGER_PHYSICAL_CLICK = 'one_finger_physical_click'
TWO_FINGER_PHYSICAL_CLICK = 'two_fingers_physical_click'
STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS = \
        'stationary_finger_not_affected_by_2nd_finger_taps'
FAT_FINGER_MOVE_WITH_RESTING_FINGER = 'fat_finger_move_with_resting_finger'
DRAG_THUMB_EDGE = 'drag_thumb_edge'
TWO_CLOSE_FINGERS_TRACKING = 'two_close_fingers_tracking'
RESTING_FINGER_PLUS_2ND_FINGER_MOVE = 'resting_finger_plus_2nd_finger_move'
TWO_FAT_FINGERS_TRACKING = 'two_fat_fingers_tracking'
FIRST_FINGER_TRACKING_AND_SECOND_FINGER_TAPS = \
        'first_finger_tracking_and_second_finger_taps'
DRUMROLL = 'drumroll'
SQUARE_RESOLUTION = 'square_resolution'
REPEATED_TAPS = 'repeated_taps_20'
ONE_FINGER_TRACKING_FROM_CENTER = 'one_finger_tracking_from_center'

# Basic tests are ones that require no special hardware to perform
PERFORMANCE_TESTS = [ONE_FINGER_TRACKING, ONE_FINGER_TO_EDGE,
  TWO_FINGER_TRACKING, FINGER_CROSSING, ONE_FINGER_SWIPE, TWO_FINGER_SWIPE,
  PINCH_TO_ZOOM, ONE_FINGER_TAP, TWO_FINGER_TAP, THREE_FINGER_TAP,
  FOUR_FINGER_TAP, FIVE_FINGER_TAP, ONE_FINGER_PHYSICAL_CLICK,
  TWO_FINGER_PHYSICAL_CLICK, STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS,
  FAT_FINGER_MOVE_WITH_RESTING_FINGER, DRAG_THUMB_EDGE, SQUARE_RESOLUTION,
  TWO_CLOSE_FINGERS_TRACKING, RESTING_FINGER_PLUS_2ND_FINGER_MOVE,
  TWO_FAT_FINGERS_TRACKING, FIRST_FINGER_TRACKING_AND_SECOND_FINGER_TAPS,
  DRUMROLL, REPEATED_TAPS, ONE_FINGER_TRACKING_FROM_CENTER
]
# These tests require a function generator connected to a probe so the
# test suite can simulate electrical noise conditions.
NOISE_TESTS = [NOISE_STATIONARY, NOISE_LINE]
# These tests are only applicable to touchPADs and not touchSCREENS
TOUCHPAD_ONLY_TESTS = [ONE_FINGER_PHYSICAL_CLICK, TWO_FINGER_PHYSICAL_CLICK]


# Define the pass/fail criteria for the various validators
COUNT_PACKETS_CRITERIA = '>= 3, ~ -3'
DRUMROLL_CRITERIA_MM = '<= 2.0'
HYSTERESIS_CRITERIA_RATIO = '<= 2.0'
NO_GAP_CRITERIA_RATIO = '<= 1.8, ~ +1.0'
NO_REVERSED_MOTION_CRITERIA_MM = '<= 1, ~ +0.5'
RANGE_CRITERIA_MM = '<= 0.5, ~ +1.0'
REPORT_RATE_CRITERIA_HTZ = '>= 60'
LINEARITY_MAX_CRITERIA_MM = '<= 2, ~ +1.0'
LINEARITY_RMS_CRITERIA_MM = '<= 0.5, ~ +0.5'
RELAXED_LINEARITY_MAX_CRITERIA_MM = '<= 4, ~ +2.0'
RELAXED_LINEARITY_RMS_CRITERIA_MM = '<= 1.0, ~ +1.0'
PINCH_CRITERIA_MM = '>= 15, ~ -5'
RELAXED_LINEARITY_CRITERIA_MM = '<= 1.5, ~ +3.0'
STATIONARY_FINGER_CRITERIA_MM = '<= 1.0'
SQUARENESS_CRITERIA_RATIO = '~= 45.0, ~ +4'
RELAXED_STATIONARY_FINGER_CRITERIA_MM = '<= 3.0'
TAP_ACCURACY_CRITERIA_MM = '<= 0.5, ~ +0.5'


# Definitions for the test specifics
tests_dict = {
  SQUARE_RESOLUTION:
  Test(
    name=SQUARE_RESOLUTION,
    variations=(GV.CENTER,),
    prompt='Use one finger and a jig to draw ~2cm 45 degree line segment in '
           'the center of the pad. Make sure it is exactly 45 degrees away '
           'from the bottom edge of the sensor and keep all lines in the '
           'center of the pad -- lines drawn near/off edges can cause false '
           'negatives for this test.',
    subprompt={
      GV.CENTER: ('center',),
    },
    validators=(
      FingerCountValidator('== 1'),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
      LineAngleValidator(SQUARENESS_CRITERIA_RATIO),
    ),
  ),
  NOISE_STATIONARY:
  Test(
    name=NOISE_STATIONARY,
    variations=(tuple(GV.NOISE_FREQUENCIES),
                (GV.MAX_AMPLITUDE,),
                (GV.SQUARE_WAVE,),
                (GV.CENTER,),
    ),
    prompt='Hold one finger on the {3} of the touch surface with a '
           '{0} {1} {2} in noise.',
    subprompt={
        GV.CENTER: ('center',),
        GV.MAX_AMPLITUDE: ('%spp' % GV.MAX_AMPLITUDE,),
        GV.SQUARE_WAVE: ('square wave',),
    },
    validators=(
      DiscardInitialSecondsValidatorWrapper(FingerCountValidator('== 1')),
      DiscardInitialSecondsValidatorWrapper(
                StationaryFingerValidator(STATIONARY_FINGER_CRITERIA_MM)),
    ),
  ),
  NOISE_LINE:
  Test(
    name=NOISE_LINE,
    variations=(tuple(GV.NOISE_FREQUENCIES),
                (GV.MAX_AMPLITUDE,),
                (GV.SQUARE_WAVE,),
                (GV.BLTR,),
    ),
    prompt='Draw a straight line from {3} with a {0} {1} {2} in noise.',
    subprompt={
      GV.BLTR: ('bottom left to top right',),
      GV.MAX_AMPLITUDE: ('%spp' % GV.MAX_AMPLITUDE,),
      GV.SQUARE_WAVE: ('square wave',),
    },
    validators=(
      DiscardInitialSecondsValidatorWrapper(FingerCountValidator('== 1')),
      DiscardInitialSecondsValidatorWrapper(
              LinearityValidator(LINEARITY_RMS_CRITERIA_MM, is_rms=True)),
      DiscardInitialSecondsValidatorWrapper(
              LinearityValidator(LINEARITY_MAX_CRITERIA_MM, is_rms=False)),
      DiscardInitialSecondsValidatorWrapper(
              NoGapValidator(NO_GAP_CRITERIA_RATIO)),
      DiscardInitialSecondsValidatorWrapper(
              NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM)),
      DiscardInitialSecondsValidatorWrapper(
              NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM)),
      DiscardInitialSecondsValidatorWrapper(
              ReportRateValidator(REPORT_RATE_CRITERIA_HTZ)),
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
      FingerCountValidator('== 1'),
      LinearityValidator(LINEARITY_RMS_CRITERIA_MM, is_rms=True),
      LinearityValidator(LINEARITY_MAX_CRITERIA_MM, is_rms=False),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
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
      FingerCountValidator('== 1'),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
      RangeValidator(RANGE_CRITERIA_MM),
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
      FingerCountValidator('== 2'),
      LinearityValidator(LINEARITY_RMS_CRITERIA_MM, is_rms=True),
      LinearityValidator(LINEARITY_MAX_CRITERIA_MM, is_rms=False),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
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
      FingerCountValidator('== 2'),
      LinearityValidator(LINEARITY_RMS_CRITERIA_MM, is_rms=True),
      LinearityValidator(LINEARITY_MAX_CRITERIA_MM, is_rms=False),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM, finger=1),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM, finger=1),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA_MM, finger=0),
    ),
  ),

  ONE_FINGER_SWIPE:
  Test(
    name=ONE_FINGER_SWIPE,
    variations=((GV.BLTR, GV.TLBR, GV.TB, GV.LR), (GV.FAST,)),
    prompt='Use ONE finger to quickly swipe {0}.',
    subprompt={
      GV.BLTR: ('from the bottom left to the top right',),
      GV.TRBL: ('from the top right to the bottom left',),
    },
    validators=(
      CountPacketsValidator(COUNT_PACKETS_CRITERIA),
      FingerCountValidator('== 1'),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
    ),
  ),

  TWO_FINGER_SWIPE:
  Test(
    name=TWO_FINGER_SWIPE,
    variations=((GV.BLTR, GV.TLBR, GV.TB, GV.LR), (GV.FAST,)),
    prompt='Use TWO fingers to quickly swipe {0}.',
    subprompt={ GV.TB: ('from top to bottom',),
      GV.BT: ('from bottom to top',),
    },
    validators=(
      CountPacketsValidator(COUNT_PACKETS_CRITERIA),
      FingerCountValidator('== 2'),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
    ),
  ),

  PINCH_TO_ZOOM:
  Test(
    name=PINCH_TO_ZOOM,
    variations=((GV.ZOOM_IN, GV.ZOOM_OUT),
                (GV.HORIZONTAL, GV.VERTICAL, GV.DIAGONAL)),
    prompt='Using two fingers, preform a {2} "{0}" pinch by bringing'
           'your fingers {1}.',
    subprompt={
      GV.ZOOM_IN: ('zoom in', 'farther apart'),
      GV.ZOOM_OUT: ('zoom out', 'closer together'),
      GV.HORIZONTAL: ('horizontal',),
      GV.VERTICAL: ('vertical',),
      GV.DIAGONAL: ('diagonal',),
    },
    validators=(
      FingerCountValidator('== 2'),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      PinchValidator(PINCH_CRITERIA_MM),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
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
      FingerCountValidator('== 1'),
      StationaryTapValidator(STATIONARY_FINGER_CRITERIA_MM),
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
      FingerCountValidator('== 2'),
      StationaryTapValidator(STATIONARY_FINGER_CRITERIA_MM),
    ),
  ),

  THREE_FINGER_TAP:
  Test(
    name=THREE_FINGER_TAP,
    variations=(GV.CENTER,),
    prompt='Use three fingers to tap the {0} of the touch surface.',
    subprompt={GV.CENTER: ('center',)},
    validators=(
      FingerCountValidator('== 3'),
      StationaryTapValidator(RELAXED_STATIONARY_FINGER_CRITERIA_MM),
    ),
  ),

  FOUR_FINGER_TAP:
  Test(
    name=FOUR_FINGER_TAP,
    variations=(GV.CENTER,),
    prompt='Use four fingers to tap the {0} of the touch surface.',
    subprompt={GV.CENTER: ('center',)},
    validators=(
      FingerCountValidator('== 4'),
      StationaryTapValidator(RELAXED_STATIONARY_FINGER_CRITERIA_MM),
    ),
  ),


  FIVE_FINGER_TAP:
  Test(
    name=FIVE_FINGER_TAP,
    variations=(GV.CENTER,),
    prompt='Use five fingers to tap the {0} of the touch surface.',
    subprompt={GV.CENTER: ('center',)},
    validators=(
      FingerCountValidator('== 5'),
      StationaryTapValidator(RELAXED_STATIONARY_FINGER_CRITERIA_MM),
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
      FingerCountValidator('== 1'),
      PhysicalClickValidator('== 1', fingers=1),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA_MM),
    ),
  ),

  TWO_FINGER_PHYSICAL_CLICK:
  Test(
    name=TWO_FINGER_PHYSICAL_CLICK,
    variations=(GV.CENTER,),
    prompt='Use two fingers physically click the {0} of the '
           'touch surface.',
    subprompt={
      GV.CENTER: ('center',),
    },
    validators=(
      FingerCountValidator('== 2'),
      PhysicalClickValidator('== 1', fingers=2),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA_MM),
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
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA_MM, finger=0),
    ),
  ),

  FAT_FINGER_MOVE_WITH_RESTING_FINGER:
  Test(
    name=FAT_FINGER_MOVE_WITH_RESTING_FINGER,
    variations=((GV.LR, GV.RL, GV.TB, GV.BT),
                (GV.NORMAL,)),
    prompt='With a stationary finger on the {0} of the touch surface, '
           'draw a straight line with a FAT finger {1} {2} it.',
    subprompt={
      GV.LR: ('top edge', 'from left to right', 'below'),
      GV.RL: ('bottom edge', 'from right to left', 'above'),
      GV.TB: ('left edge', 'from top to bottom', 'on the right to'),
      GV.BT: ('right edge', 'from bottom to top', 'on the left to'),
    },
    validators=(
      FingerCountValidator('== 2'),
      LinearityValidator(RELAXED_LINEARITY_RMS_CRITERIA_MM, finger=1,
                         is_rms=True),
      LinearityValidator(RELAXED_LINEARITY_MAX_CRITERIA_MM, finger=1,
                         is_rms=False),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM, finger=1),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM, finger=1),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA_MM, finger=0),
    ),
  ),

  DRAG_THUMB_EDGE:
  Test(
    name=DRAG_THUMB_EDGE,
    variations=((GV.SMALL_THUMB, GV.LARGE_THUMB),
                (GV.LR, GV.RL, GV.TB, GV.BT)),
    prompt='Drag the edge of a {0} thumb {1} in a straight line '
           'across the touch surface.',
    subprompt={
      GV.LR: ('horizontally from left to right',),
      GV.RL: ('horizontally from right to left',),
      GV.TB: ('vertically from top to bottom',),
      GV.BT: ('vertically from bottom to top',),
      GV.SMALL_THUMB: ('small',),
      GV.LARGE_THUMB: ('large',),
    },
    validators=(
      FingerCountValidator('== 1'),
      LinearityValidator(RELAXED_LINEARITY_RMS_CRITERIA_MM, is_rms=True),
      LinearityValidator(RELAXED_LINEARITY_MAX_CRITERIA_MM, is_rms=False),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
    ),
  ),

  TWO_CLOSE_FINGERS_TRACKING:
  Test(
    name=TWO_CLOSE_FINGERS_TRACKING,
    variations=((GV.LR, GV.TB, GV.TLBR),
                (GV.SLOW, GV.NORMAL)),
    prompt='With two fingers close together (lightly touching each '
           'other) in a two finger scrolling gesture, take {2} to draw a {0} '
           'line {1}.',
    subprompt={
      GV.LR: ('horizontal', 'from left to right',),
      GV.TB: ('vertical', 'from top to bottom',),
      GV.TLBR: ('diagonal', 'from the top left to the bottom right',),
      GV.NORMAL: ('1 second',),
      GV.SLOW: ('3 seconds',),
    },
    validators=(
      FingerCountValidator('== 2'),
      LinearityValidator(RELAXED_LINEARITY_RMS_CRITERIA_MM, is_rms=True),
      LinearityValidator(RELAXED_LINEARITY_MAX_CRITERIA_MM, is_rms=False),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
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
      FingerCountValidator('== 2'),
      LinearityValidator(LINEARITY_RMS_CRITERIA_MM, finger=1, is_rms=True),
      LinearityValidator(LINEARITY_MAX_CRITERIA_MM, finger=1, is_rms=False),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM, finger=1),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM, finger=1),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
      StationaryFingerValidator(STATIONARY_FINGER_CRITERIA_MM, finger=0),
    ),
  ),

  TWO_FAT_FINGERS_TRACKING:
  Test(
    name=TWO_FAT_FINGERS_TRACKING,
    variations=((GV.LR, GV.TB, GV.TLBR),
                (GV.SLOW, GV.NORMAL)),
    prompt='Take {1} to draw a straight line {0} with two FAT fingers '
           'separated by about 1cm.',
    subprompt={
      GV.LR: ('from left to right',),
      GV.RL: ('from right to left',),
      GV.NORMAL: ('1 second',),
      GV.SLOW: ('3 seconds',),
    },
    validators=(
      FingerCountValidator('== 2'),
      LinearityValidator(RELAXED_LINEARITY_RMS_CRITERIA_MM, is_rms=True),
      LinearityValidator(RELAXED_LINEARITY_MAX_CRITERIA_MM, is_rms=False),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
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
      FingerCountValidator('== 4'),
      LinearityValidator(LINEARITY_RMS_CRITERIA_MM, finger=0, is_rms=True),
      LinearityValidator(LINEARITY_MAX_CRITERIA_MM, finger=0, is_rms=False),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM, finger=0),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM, finger=0),
      ReportRateValidator(REPORT_RATE_CRITERIA_HTZ),
    ),
  ),

  DRUMROLL:
  Test(
    name=DRUMROLL,
    variations=(GV.FAST, ),
    prompt='Use the index and middle finger of one hand to make a '
           '"drum roll" by alternately tapping both fingers {0} '
           'for 5 seconds.',
    subprompt={
      GV.FAST: ('as quickly as possible',),
    },
    validators=(
      FingerCountValidator('>= 10'),
      DrumrollValidator(DRUMROLL_CRITERIA_MM),
    ),
    timeout = 2,
  ),

  REPEATED_TAPS:
  Test(
    name=REPEATED_TAPS,
    variations=(GV.TL, GV.BR, GV.CENTER),
    prompt='Tap the same spot in the {0} of the touch surface 20 times.',
    subprompt={
      GV.TL: ('top left corner',),
      GV.CENTER: ('center',),
      GV.BR: ('bottom right corner',),
    },
    validators=(
      FingerCountValidator('== 20'),
      TapAccuracyValidator(TAP_ACCURACY_CRITERIA_MM),
      StationaryTapValidator(STATIONARY_FINGER_CRITERIA_MM),
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
      FingerCountValidator('== 1'),
      HysteresisValidator(HYSTERESIS_CRITERIA_RATIO),
      NoGapValidator(NO_GAP_CRITERIA_RATIO),
      NoReversedMotionMiddleValidator(NO_REVERSED_MOTION_CRITERIA_MM),
      NoReversedMotionEndsValidator(NO_REVERSED_MOTION_CRITERIA_MM),
    ),
  ),
}


def generate_test_list(options):
  """ Returns a list of all the legal Test objects, given the options. """
  test_names = []

  # Performance tests don't require any special equiptment, so for any mode
  # that includes them, they should always be run.
  if options.mode in ['full', 'performance']:
    test_names.extend(PERFORMANCE_TESTS)

  # Noise tests can only be run with a function generator, so we check that
  # they are both selected and that the function generator is present.
  if options.mode in ['full', 'noise']:
    if not options.has_fn_gen:
      print (color.Fore.RED + 'WARNING: To run noise tests, you need a '
             'function generator. Use -f to tell the test suite to look for '
             'one, otherwise all noise tests will be skipped!')
    else:
      if not options.has_robot:
        print (color.Fore.RED + 'WARNING: You have selected to run a noise '
               'test without a robot. This adds MANY HOURS of additional tests '
               'that you will have to do by hand!')
        choice = None
        while not choice or choice[0] not in ['n', 'y']:
          choice = raw_input('Do you REALLY want to do this? (y or n) ').lower()
        if choice[0] == 'n':
          sys.exit(1)

      test_names.extend(NOISE_TESTS)

  # Remove any tests that are for touchpads only if this is a touchscreen
  if options.is_touchscreen:
    test_names = [name for name in test_names
                  if name not in TOUCHPAD_ONLY_TESTS]

  # Take that generated list of names and lookup the actual Test objects.
  return [tests_dict[test_name] for test_name in test_names]
