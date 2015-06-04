# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pickle
import sys

from position import Position


class DeviceSpec:
  """ This is a class to represent the details of a given device
  that the robot will interact with.
  """
  @staticmethod
  def LoadFromDisk(filename):
    device_spec = None
    with open(filename, 'rb') as fo:
      device_spec = pickle.load(fo)
    return device_spec

  def SaveToDisk(self, filename):
    with open(filename, 'wb') as fo:
      pickle.dump(self, fo)

  def __init__(self, tr, tl, bl, br):
    self.tr, self.tl = tr, tl
    self.bl, self.br = bl, br

  def __str__(self):
    s = 'Top Right: %s\n' % str(self.tr)
    s += 'Top Left: %s\n' % str(self.tl)
    s += 'Bottom Left: %s\n' % str(self.bl)
    s += 'Bottom Right: %s\n' % str(self.br)
    return s

  def __InterpolateValue(self, v1, v2, ratio):
    """ Linearly interpolate between v1 and v2 """
    return (1.0 - ratio) * v1 + ratio * v2

  def __InterpolatePosition(self, p1, p2, ratio):
    """ Linearly interpolate all values in two positions """
    return Position(self.__InterpolateValue(p1.x, p2.x, ratio),
            self.__InterpolateValue(p1.y, p2.y, ratio),
            self.__InterpolateValue(p1.z, p2.z, ratio),
            self.__InterpolateValue(p1.roll, p2.roll, ratio),
            self.__InterpolateValue(p1.pitch, p2.pitch, ratio),
            self.__InterpolateValue(p1.yaw, p2.yaw, ratio),
            self.__InterpolateValue(p1.ax_1, p2.ax_1, ratio),
            self.__InterpolateValue(p1.ax_2, p2.ax_2, ratio),
            self.__InterpolateValue(p1.ax_3, p2.ax_3, ratio),
            self.__InterpolateValue(p1.ax_4, p2.ax_4, ratio),
            self.__InterpolateValue(p1.ax_5, p2.ax_5, ratio))

  def __ScaleForMaxDiagonalDistance(self, max_diagonal_distance):
    # If there's no limit to the size, then there's no need to scale
    if not max_diagonal_distance:
      return self.tl, self.tr, self.bl, self.br

    # If the limit on the size is bigger than the device, then we're done.
    width = self.br.x - self.tl.x
    height = self.tl.y - self.br.y
    diagonal_distance = (width ** 2 + height ** 2) ** 0.5
    if diagonal_distance <= max_diagonal_distance:
      return self.tl, self.tr, self.bl, self.br

    # Otherwise we have to scale it down
    shrink_ratio = max_diagonal_distance / diagonal_distance
    center = self.RelativePosToAbsolutePos((0.5, 0.5))
    tl = self.__InterpolatePosition(self.tl, center, shrink_ratio)
    tr = self.__InterpolatePosition(self.tr, center, shrink_ratio)
    bl = self.__InterpolatePosition(self.bl, center, shrink_ratio)
    br = self.__InterpolatePosition(self.br, center, shrink_ratio)
    return tl, tr, bl, br


  def RelativePosToAbsolutePos(self, rel_p, angle=None,
                               max_diagonal_distance=None):
    """ Convert from relative (0.0->1.0 scaled) coordinates to absolute
    values for this device.

    If a max_diagonal_distance is supplied the area will be
    scaled down to a section in the center of the device small
    enough that all points in it are within that distance of each
    other.
    """
    rel_x, rel_y = rel_p
    tl, tr, bl, br = self.__ScaleForMaxDiagonalDistance(max_diagonal_distance)

    ptop = self.__InterpolatePosition(tl, tr, rel_x)
    pbot = self.__InterpolatePosition(bl, br, rel_x)
    abs_p = self.__InterpolatePosition(ptop, pbot, rel_y)
    if angle is not None:
      abs_p.yaw += angle
    return abs_p

  def __Distance(self, pos1, pos2):
    dx = pos1.x - pos2.x
    dy = pos1.y - pos2.y
    return (dx * dx + dy * dy) ** 0.5

  def Height(self):
    heights = [];
    for x in [0.0, 1.0]:
      p1 = self.RelativePosToAbsolutePos((x, 0.0))
      p2 = self.RelativePosToAbsolutePos((x, 1.0))
      heights.append(self.__Distance(p1, p2))
    return (heights[0] + heights[1]) / 2.0

  def Width(self):
    widths = [];
    for y in [0.0, 1.0]:
      p1 = self.RelativePosToAbsolutePos((0.0, y))
      p2 = self.RelativePosToAbsolutePos((1.0, y))
      widths.append(self.__Distance(p1, p2))
    return (widths[0] + widths[1]) / 2.0

if __name__ == '__main__':
  try:
    device = DeviceSpec.LoadFromDisk(sys.argv[1])
  except:
    print 'Usage: %s device_spec.p' % __file__
    sys.exit(1)

  print device_spec.Height(), device_spec.Width()
