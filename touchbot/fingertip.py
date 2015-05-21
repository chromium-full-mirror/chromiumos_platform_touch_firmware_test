# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import os
import pickle
import position
import re

class Fingertip:
  """ This is a class that describes a single fingertip used by the robot. """
  def __init__(self, fingertip_name, finger_number):
    self.name = fingertip_name
    self.finger_number = finger_number
    self.above_pos = self.slide_pos = None
    self.extension1 = self.extension2 = 0

  def SaveToPickledFile(self, filename):
    with open(filename, 'wb') as fo:
      pickle.dump(self, fo)

  @staticmethod
  def FromPickledFile(filename):
    this_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(this_dir, filename)
    with open(filename, 'rb') as fo:
      return pickle.load(fo)

  def IsLarge(self):
    """ Returns True if the fingertip is especially large.  In this case
    the robot needs to move more slowly to prevent knocking it off the magnets.
    These fingertips are also thicker than the others, so they need to be offset
    to contact the pad.
    """
    return 'fingers' in self.name

  def diameter(self):
    """ Returns the diameter in mm if this is a round tip, otherwise None
    Round fingertips are named like "$FINGERNUMBERround_$DIAMETERmm"
    """
    matches = re.match('^.*_(\d*)mm.*$', self.name)
    if matches:
      return int(matches.group(1))
    return None


def LoadFingertips(directory):
  fingertips = {}
  this_dir = os.path.dirname(os.path.abspath(__file__))
  full_path = os.path.join(this_dir, directory)
  pattern = os.path.join(full_path, '*.p')
  for filename in glob.glob(pattern):
    fingertip = Fingertip.FromPickledFile(filename)
    if isinstance(fingertip, Fingertip):
      fingertip_name, extension = os.path.splitext(os.path.basename(filename))
      fingertips[fingertip_name] = fingertip
  return fingertips

