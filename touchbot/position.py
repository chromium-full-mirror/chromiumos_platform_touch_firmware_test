# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import pickle


class Position:
  """ Representation of a robot position

  The robot position is represented in two ways:
    Cartesian: x, y, z, yaw, pitch, roll
    Joint: ax_1, ax_2, ax_3, ax_4, ax_5

  This class stores all the variables in one cohesive object
  to be used for any method that works on robot positions
  """

  def __init__(self, x, y, z, yaw, pitch, roll, ax_1, ax_2, ax_3, ax_4, ax_5):
    self.x = x
    self.y = y
    self.z = z
    self.yaw = yaw
    self.pitch = pitch
    self.roll = roll
    self.ax_1 = ax_1
    self.ax_2 = ax_2
    self.ax_3 = ax_3
    self.ax_4 = ax_4
    self.ax_5 = ax_5

  @staticmethod
  def FromTouchbotResponse(touchbot_response):
    """ Parse a response from the touchbot and build a Position object """
    values = [float(v) for v in touchbot_response.split()]
    if len(values) != 11:
      return None
    x, y, z = values[0:3]
    yaw, pitch, roll = values[3:6]
    ax_1, ax_2, ax_3, ax_4, ax_5 = values[6:]
    return Position(x, y, z, yaw, pitch, roll, ax_1, ax_2, ax_3, ax_4, ax_5)

  def __str__(self):
    """ Print the position in the format the robot expects """
    return '%f %f %f %f %f %f %f %f %f %f %f' % (self.x, self.y, self.z,
          self.yaw, self.pitch, self.roll, self.ax_1,
          self.ax_2, self.ax_3, self.ax_4, self.ax_5)

  def CartesianDistanceFrom(self, other):
    return ((self.x - other.x) ** 2 +
        (self.y - other.y) ** 2 +
        (self.z - other.z) ** 2) ** 0.5

  def SaveToPickledFile(self, filename):
    with open(filename, 'wb') as fo:
      pickle.dump(self, fo)

  @staticmethod
  def FromPickledFile(filename):
    this_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(this_dir, filename)
    with open(filename, 'rb') as fo:
      return pickle.load(fo)
