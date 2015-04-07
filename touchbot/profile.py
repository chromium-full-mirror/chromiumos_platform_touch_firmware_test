# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class Profile:
  """ Container class storing all the movement settings for the robot.

  These are the values that control how fast the robot moves, accelerates,
  etc.  Profiles can be loaded from the robot, altered and then uploaded
  back onto the robot to change how it will move later.
  """

  def __init__(self, profidx, speed, speed2, accel, decel, accelRamp,
         decelRamp, inRange, straight):
    self.profidx = profidx
    self.speed = speed
    self.speed2 = speed2
    self.accel = accel
    self.decel = decel
    self.accelRamp = accelRamp
    self.decelRamp = decelRamp
    self.inRange = inRange
    self.straight = straight

  @staticmethod
  def FromTouchbotResponse(touchbot_response):
    """ Parses a Profile object from the touchbot's response """
    values = touchbot_response.split()
    if len(values) != 9:
      return None
    profidx = int(values[0])
    speed = float(values[1])
    speed2 = float(values[2])
    accel = float(values[3])
    decel = float(values[4])
    accelRamp = float(values[5])
    decelRamp = float(values[6])
    inRange = int(values[7])
    straight = int(values[8])
    return Profile(profidx, speed, speed2, accel, decel, accelRamp,
             decelRamp, inRange, straight)

  def __str__(self):
    return "%d %f %f %f %f %f %f %d %d" % (self.profidx, self.speed,
          self.speed2, self.accel, self.decel, self.accelRamp,
          self.decelRamp, self.inRange, self.straight)
