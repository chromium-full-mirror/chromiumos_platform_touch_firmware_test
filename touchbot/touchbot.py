# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy

from device_spec import DeviceSpec
from numpy import clip
from position import Position
from profile import Profile
from touchbotcomm import TouchbotComm

class Touchbot:
  """ High level Touchbot control class

  This class hides the internals of communicating with the robot and
  offers high level robot control commands.

  A touchbot object is initialized and then its member functions can
  be called to execute various gestures
  """
  # Network connection parameters for the robot
  TOUCHBOT_IP_ADDR = '192.168.0.1'
  TOUCHBOT_PORT = 10100

  # How high above to approach from to be safe
  SAFETY_CLEARANCE = 220

  # Useful speeds for movement
  SPEED_VERY_SLOW = 1.0
  SPEED_SLOW = 10.0
  SPEED_MEDIUM = 25.0
  SPEED_FAST = 50.0
  SPEED_VERY_FAST = 75.0
  MAX_SPEED = 100.0

  # Limits on how far the robot hand can move the fingers in and out
  MIN_FINGER_DISTANCE = 0.5
  MAX_FINGER_DISTANCE = 140

  def __init__(self, ip_address=TOUCHBOT_IP_ADDR, port=TOUCHBOT_PORT):
    self.speed_stack = []
    self.comm = TouchbotComm(ip_address, port)

  def _CalibratePosition(self):
    """ Make the robot go limp and record its position after the operator
    moves it into the desired configuration.
    Returns a Position object of the recorded posisition.
    """
    successful = True
    response = self._FreeAxes()
    if not response or response[0] != 0:
      print 'There was an error entering free mode.'
      return None

    print 'Move the robot CAREFULLY to where you want it.'
    raw_input('Press "enter" to record that position.')

    response = self._UnFreeAxes()
    if not response or response[0] != 0:
      print 'There was an error leaving free mode.'
      return None

    return self._GetCurrentPosition()

  def _SetSpeed(self, speed):
    prof = self._GetCurrentProfile()
    prof.speed = speed
    self._SetProfileData(prof)

  def _GetSpeed(self):
    prof = self._GetCurrentProfile()
    return prof.speed

  def _FreeAxes(self):
    """ Set all axis into free mode, ie: make them go limp. """
    return self.comm.SendCmd('freemode', 0)

  def _UnFreeAxes(self):
    """ Return all axes to computer control. """
    return self.comm.SendCmd('freemode', -1)

  def _GetCurrentPosition(self):
    """ Record the current position as a Position object. """
    response = self.comm.SendCmd('where')
    if not response:
      return None
    error_code, data = response
    if error_code != 0:
      return None
    return Position.FromTouchbotResponse(data)

  def _GetCurrentProfile(self):
    """ Get a copy of the current movement profile. """
    error_code, data = self.comm.SendCmd('profile')
    return Profile.FromTouchbotResponse(data)

  def _SetProfileData(self, profile):
    """ Replace the robot's current profile with this one. """
    return self.comm.SendCmd('profile', str(profile))

  def _SetCartesian(self, pos, finger_distance=None, blocking=True):
    """ Move the robot to pos by Cartesian coordinates. """
    # If a finger spacing has been specified add that to the movement
    # command.  The finger spacing motors were added as an additional axis
    # so are not controlled by the 'movec' command by default.  They must
    # be specified before with the 'moveExtraAxis' command, and then are
    # moved when the robot receives the next 'movec.'
    if finger_distance is not None:
      finger_distance = clip(finger_distance,
                   Touchbot.MIN_FINGER_DISTANCE,
                   Touchbot.MAX_FINGER_DISTANCE)
      self.comm.SendCmd('moveExtraAxis', finger_distance)

    response = self.comm.SendCmd('movec', pos.x, pos.y, pos.z,
                   pos.yaw, pos.pitch, pos.roll)
    if blocking:
      self._Wait()
    return response

  def _Wait(self):
    return self.comm.SendCmd('waitForEom')

  def _AddSafetyClearance(self, pos):
    new_pos = copy.deepcopy(pos)
    new_pos.ax_1 = Touchbot.SAFETY_CLEARANCE
    new_pos.z = Touchbot.SAFETY_CLEARANCE
    return new_pos

  def _PushSpeed(self, new_speed):
    self.speed_stack.append(self._GetSpeed())
    self._SetSpeed(new_speed)

  def _PopSpeed(self):
    if len(self.speed_stack) >= 1:
      self._SetSpeed(self.speed_stack.pop())


################################################################################
#                    Actual gestures after this point                          #
################################################################################

  def CalibrateDevice(self, filename=None):
    self._PushSpeed(Touchbot.SPEED_FAST)

    # First, lift the arm up and clear of any obstructions with the fingers as
    # close together as they can to allow for easy centering
    pos = self._GetCurrentPosition()
    pos = self._AddSafetyClearance(pos)
    self._SetCartesian(pos, finger_distance=0, blocking=True)

    # Prompt the user to calibrate each corner of the device
    CORNER_NAMES = ['top right', 'top left', 'bottom left', 'bottom right']
    corners = []
    for corner in CORNER_NAMES:
        print 'Position the fingers in the %s corner of the device' % corner
        print 'and keep the hand as aligned with the touchpad as possible'
        corners.append(self._CalibratePosition())

    # Build a DeviceSpec and save to disk if a filename was specified
    device_spec = DeviceSpec(*corners)
    if filename:
      device_spec.SaveToDisk(filename)

    self._PopSpeed()
