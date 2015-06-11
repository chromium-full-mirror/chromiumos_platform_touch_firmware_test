# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Fingertip retrieval training script

This script it run manually by the operator to train the robot how to pick up
a single fingertip from the nest.  You can configure which tip it is by editing
the three constants BASENAME, FINGER, and ROW which are defined by the physical
properties of the fingertip in question.

Usage:
  1. Configure the constants to describe the fingertip in question
  2. Run the script "python train_fingertip.py"
  3. Follow the instructions presented on screen.

This will store a pickled fingertip object in nest_locations that will
automatically be picked up by the Touchbot class.
"""

import copy
import sys
import time

from touchbot import Touchbot
from touchbot.fingertip import Fingertip
from touchbot.position import Position


# Configure which fingertip you would like to train the position for here
BASENAME = 'round_8mm'   # The name of this fingertip
FINGER = 1               # Which finger it goes on (1, 2, or None for both)
ROW = 1                  # Which row of the nest the fingertip sits in


# Constants defined by the size/shape/location of the nest
ROW_ONE_SLIDE_OFFSET = -30
ROW_TWO_SLIDE_OFFSET = 60


def main():
  bot = Touchbot()
  bot.PushSpeed(Touchbot.SPEED_MEDIUM)

  name = ('%d%s' % (FINGER, BASENAME)) if FINGER else BASENAME

  # Build a new fingertip object
  fingertip = Fingertip(name, FINGER)

  # Prompt the user to align the robot's fingers over the tip and record the
  # location as the "above" position
  print 'Please align finger(s) above the tip "%s"' % name
  bot._MoveBothFingersAbsolute(0, 0)
  fingertip.above_pos = bot._CalibratePosition()

  # Extend the fingers into the probe and record their positions
  pos1 = pos2 = 0
  if FINGER is None:
    pos1 = bot._ExtendFingerUntilContact(1)
    pos2 = bot._ExtendFingerUntilContact(2)
  elif finger_number == 1:
    pos1 = bot._ExtendFingerUntilContact(1)
  else:
    pos2 = bot._ExtendFingerUntilContact(2)

  bot._MoveBothFingersAbsolute(0, 0)
  if FINGER in Touchbot.FINGER_NUMBERS:
    fingertip.extension1, fingertip.extension2 = pos1, pos2
  else:
    fingertip.extension1, fingertip.extension2 = pos1, pos1

  # Based on which row the tip is in, calculate the position that will slide
  # the tip out of the nest.
  fingertip.slide_pos = copy.deepcopy(fingertip.above_pos)
  if ROW == 1:
    fingertip.slide_pos.x += ROW_ONE_SLIDE_OFFSET
  elif ROW == 2:
    fingertip.slide_pos.x += ROW_TWO_SLIDE_OFFSET
  else:
    print 'ERROR: Unable to determine slide location.  Invalid ROW (%d)' % ROW
    sys.exit(1)

  # Now we have the robot try putting it in and taking it out repeatedly, to
  # allow the user to tune the fingertip height.  The tips should slide in/out
  # without any noise.  Keep tweaking this value until they move silently.
  orig_extension1 = fingertip.extension1
  orig_extension2 = fingertip.extension2
  while True:
    # Try applying a new offset
    extra_descent = int(raw_input('Type a guess for the extra descent needed: '))
    time.sleep(2)
    fingertip.extension1 = orig_extension1 + extra_descent
    fingertip.extension2 = orig_extension2 + extra_descent

    # Trying to get/drop the finger to see how well it works
    bot._GetFingertip(fingertip)
    time.sleep(1)
    bot._DropFingertip(fingertip)

    yorn = raw_input('Accept this path? (y/n)')
    if yorn == 'y':
      break

  # Finally, save the results
  fingertip.SaveToPickledFile('touchbot/nest_locations/%s.p' % name)

  bot.PopSpeed()


if __name__ == "__main__":
  main()
