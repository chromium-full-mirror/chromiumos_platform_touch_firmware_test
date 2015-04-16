# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import math
import os
import sys
import time

from device_spec import DeviceSpec
from fingertip import Fingertip, LoadFingertips
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

  # Constants for the finger actuators
  FINGER_NUMBERS = [1, 2]
  FINGER_CURRENT_LIMIT_MA = 550
  FINGER_HOME_OFFSET = 2500
  FINGER_CONTACT_CURRENT = 250
  DEFAULT_MAX_EXTENSION = 1500
  DEFAULT_CALIBRATION_EXTENSION = DEFAULT_MAX_EXTENSION * 0.95
  MIN_FINGER_SPACING = 12
  FINGER_ACCEL_MM_S_S = 500
  FINGER_DECEL_MM_S_S = 2000

  def __init__(self, ip_address=TOUCHBOT_IP_ADDR, port=TOUCHBOT_PORT):
    self.speed_stack = []
    self.finger_speed_stack = []
    self.comm = TouchbotComm(ip_address, port)

    # Load all the fingertip locations from disk
    self.fingertips = LoadFingertips('nest_locations')

    # Center the wrist to prevent it starting twisted
    self._CenterWrist()

    # Initialize the fingers
    for finger_number in Touchbot.FINGER_NUMBERS:
      self._InitializeFinger(finger_number)

    # Set everything to a sane speed
    self._PushSpeed(Touchbot.SPEED_MEDIUM)
    self._PushFingerSpeed_mm_per_s(1000)

  def __del__(self):
    """ Move the robot arm up and disable the fingers before quitting. """
    if self.comm:
      self._SetCartesian(self._AddSafetyClearance(self._GetCurrentPosition()))
      for finger_number in Touchbot.FINGER_NUMBERS:
        self._DisableFinger(finger_number)

  def _CenterWrist(self):
    """ Rotate the wrist (axis 4) to it's middle point.
    This should be done intermittently to make sure it doesn't drift too far.
    The joint can only wrap around so many times before it's stuck, so this is
    a safe place to start a gesture from.
    """
    self._PushSpeed(Touchbot.SPEED_MEDIUM)
    pos = self._GetCurrentPosition()
    pos.ax_4 = 0
    err, _ = self._SetAngles(pos)
    self._PopSpeed()
    if err:
      print 'ERROR: unable to center the wrist.'

  def _InitializeFinger(self, finger_number):
    """ Do all the setup for a finger
    This function sets the current limit for the finger controller and sets
    the Zero point for the fingers
    """
    self.comm.SendFingerCmd('%dDI' % finger_number)
    time.sleep(0.5)
    self._SetFingerCurrentLimit_mA(finger_number,
                                   Touchbot.FINGER_CURRENT_LIMIT_MA)
    self._SetFingerAcceleration(Touchbot.FINGER_ACCEL_MM_S_S)
    self._SetFingerDeceleration(Touchbot.FINGER_DECEL_MM_S_S)

    # Track to roughly the middle of the range and call that Zero
    self.comm.SendFingerCmd('%dAPL0' % finger_number) # Disable range limiting
    self._EnableFinger(finger_number)
    self._ExtendFingerUntilContact(finger_number)
    self._SetFingerZeroPoint(finger_number)
    self._MoveFingerRelative(finger_number, -Touchbot.FINGER_HOME_OFFSET)
    self._SetFingerZeroPoint(finger_number)

  def _PushFingerSpeed_mm_per_s(self, speed):
    self.finger_speed_stack.append(self._GetFingerSpeed())
    self._SetFingerSpeed(speed)

  def _PopFingerSpeed(self):
    if len(self.finger_speed_stack) >= 1:
      self._SetFingerSpeed(self.finger_speed_stack.pop())

  def _GetFingerSpeed(self):
    return int(self.comm.SendFingerCmd('1GSP'))

  def _SetFingerSpeed(self, speed):
    self.comm.SendFingerCmd('SP%d' % speed)

  def _SetFingerAcceleration(self, speed):
    self.comm.SendFingerCmd('AC%d' % speed)

  def _SetFingerDeceleration(self, speed):
    self.comm.SendFingerCmd('DEC%d' % speed)

  def _SetFingerStates(self, finger1_extended, finger2_extended):
    """ Extend or retract the fingers.
    Note this code looks a bit funny since it doesn't use else at all.  This is
    to make sure that the finger are always extended in the order 1, 2 and that
    they are always retracted in the reverse order of 2, 1 to keep the dual
    finger tips from binding
    """
    if not finger1_extended and not finger2_extended:
      self._MoveBothFingersAbsolute(0, 0)
      return
    if not finger2_extended:
      self._MoveFingerAbsolute(2, 0)
    if not finger1_extended:
      self._MoveFingerAbsolute(1, 0)
    if finger1_extended:
      self._ExtendFingerUntilContact(1, Touchbot.DEFAULT_MAX_EXTENSION)
    if finger2_extended:
      self._ExtendFingerUntilContact(2, Touchbot.DEFAULT_MAX_EXTENSION)

  def _ExtendFingerUntilContact(self, finger_number, speed=1, cutoff=None):
    """ Extend the specified finger slowly until it touches something.
    This is done by telling the finger to extend slowly and polling the
    amount of current the actuator is drawing.  As soon as it meets some
    resistance the current will jump, indicating that it has made contact.
    """
    if finger_number not in (1, 2):
      print 'ERROR: illegal finger_number (%d)' % finger_number
      return None

    # Start the finger moving at the specified velocity
    self._SetFingerVelocity_mm_s(finger_number, speed)

    # Now poll the finger's position and current to know when to stop
    while True:
      pos = self._GetFingerPos(finger_number)

      # If we've passed a cutoff point, stop
      if cutoff is not None and pos >= cutoff:
        break

      # If the current is spiking, stop
      current = self._GetFingerCurrent_mA(finger_number)
      if current >= Touchbot.FINGER_CONTACT_CURRENT:
        break

    self._SetFingerVelocity_mm_s(finger_number, 0)
    return pos

  def _SetFingerVelocity_mm_s(self, finger_number, speed):
    """ Set the specified finger's velocity (as opposed to position) """
    self.comm.SendFingerCmd('%dV%d' % (finger_number, speed))

  def _GetFingerCurrent_mA(self, finger_number):
    """ Get the current for a specified finger in mA """
    return int(self.comm.SendFingerCmd('%dGRC' % finger_number))

  def _SetFingerZeroPoint(self, finger_number):
    """ Set Home (position 0) for the given finger to where it is right now """
    self.comm.SendFingerCmd('%dHO' % finger_number)

  def _SetFingerCurrentLimit_mA(self, finger_number, current):
    """ Set the maximum current that this finger can draw in mA """
    self.comm.SendFingerCmd('%dLCC%d' % (finger_number, current))

  def _EnableFinger(self, finger_number):
    """ Enable the finger, it can now move when given movement commands """
    self.comm.SendFingerCmd('%dEN' % finger_number)

  def _GetFingerPos(self, finger_number):
    """ Get the current position of the finger """
    return int(self.comm.SendFingerCmd('%dPOS' % finger_number))

  def _GetFingerTargetPos(self, finger_number):
    """ Get the position that this finger is currently trying to go to """
    return int(self.comm.SendFingerCmd('%dTPOS' % finger_number))

  def _ExecuteFingerMove(self, finger_number, blocking):
    """ Tell the finger to execute a pending move.
    If blocking is set to True then this will poll the finger until the
    true location of the finger and the target location are sufficiently
    close together.
    """
    CORRIDOR = 1
    if finger_number is not None:
      self.comm.SendFingerCmd('%dM' % finger_number)
    else:
      self.comm.SendFingerCmd('1M')
      self.comm.SendFingerCmd('2M')

    if blocking:
      required_fingers = [1, 2] if finger_number is None else [finger_number]
      while True:
        completed_fingers = 0
        for finger in required_fingers:
          if finger_number is None or finger_number == finger:
            target = self._GetFingerTargetPos(finger)
            current = self._GetFingerPos(finger)
            if abs(target - current) <= CORRIDOR:
              completed_fingers += 1
        if completed_fingers == len(required_fingers):
          return

  def _MoveFingerRelative(self, finger_number, distance, blocking=True):
    """ Move the finger a certain amount relative to its current position. """
    self.comm.SendFingerCmd('%dLR%d' % (finger_number, distance))
    self._ExecuteFingerMove(finger_number, blocking)

  def _MoveFingerAbsolute(self, finger_number, position, blocking=True):
    """ Move the finger to an absolute position. """
    self.comm.SendFingerCmd('%dLA%d' % (finger_number, position))
    self._ExecuteFingerMove(finger_number, blocking)

  def _MoveBothFingersAbsolute(self, position1, position2, blocking=True):
    """ Move both fingers simultaineously to absolute positions """
    self.comm.SendFingerCmd('1LA%d' % position1)
    self.comm.SendFingerCmd('2LA%d' % position2)
    self._ExecuteFingerMove(None, blocking)

  def _DisableFinger(self, finger_number):
    self._MoveFingerAbsolute(finger_number, 0.9 * Touchbot.FINGER_HOME_OFFSET)
    self.comm.SendFingerCmd('%dDI' % finger_number)

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

  def _SetAngles(self, pos, blocking=True):
    """ Move the robot to pos by the raw joint angles.
    Generally speaking _SetCartesian() is preferable to this function, so
    only use this function if you need to control the axes directly.
    """
    response = self.comm.SendCmd('movej', pos.ax_1, pos.ax_2, pos.ax_3,
                                 pos.ax_4, pos.ax_5)
    if blocking:
      self._Wait()
    return response

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

  def _ExtendRequiredFingers(self, finger_number):
    """ Extend the finger(s) indicated.
    If finger_number is None, this indicates that BOTH fingers are needed,
    otherwise the number indicates which finger to extend.
    """
    if finger_number is None:
      pos1 = self._ExtendFingerUntilContact(1)
      pos2 = self._ExtendFingerUntilContact(2)
      return pos1, pos2
    elif finger_number == 1:
      pos = self._ExtendFingerUntilContact(1)
      return pos, 0
    else:
      pos = self._ExtendFingerUntilContact(2)
      return 0, pos

  def _GetFingertip(self, fingertip):
    """ Retrieve the specified fingertip from the nest. """
    self._SetFingerStates(False, False)
    self._SetAngles(fingertip.above_pos)

    self._PushSpeed(Touchbot.SPEED_VERY_SLOW)

    self._MoveBothFingersAbsolute(fingertip.extension1, fingertip.extension2)
    self._SetCartesian(fingertip.slide_pos)

    self._PopSpeed()

    self._PushFingerSpeed_mm_per_s(1 if fingertip.IsHeavy() else 20)
    self._SetFingerStates(False, False)
    self._PopFingerSpeed()

  def _DropFingertip(self, fingertip):
    """ Drop off the specified fingertip at its place in the nest. """
    self._SetFingerStates(False, False)
    self._SetCartesian(fingertip.slide_pos)

    self._PushSpeed(Touchbot.SPEED_VERY_SLOW)
    self._PushFingerSpeed_mm_per_s(1 if fingertip.IsHeavy() else 20)

    self._MoveBothFingersAbsolute(fingertip.extension1, fingertip.extension2)
    self._SetCartesian(fingertip.above_pos)

    self._PopSpeed()
    self._PopFingerSpeed()
    self._SetFingerStates(False, False)

  def _CenterAroundSingleFinger(self, finger_number, pos):
    """ Offset the coordinates so that finger 1 is centered at the point given,
    not the point directly between the two fingers.
    """
    # Shift the x and y accordingly for both points in the line
    angle = math.radians(pos.yaw - 90)
    pos.x += math.cos(angle) * (pos.ax_5 + Touchbot.MIN_FINGER_SPACING) / 2.0
    pos.y += math.sin(angle) * (pos.ax_5 + Touchbot.MIN_FINGER_SPACING) / 2.0
    return pos

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

    self._ExtendFingerUntilContact(1, Touchbot.DEFAULT_CALIBRATION_EXTENSION)
    self._ExtendFingerUntilContact(2, Touchbot.DEFAULT_CALIBRATION_EXTENSION)

    # Prompt the user to calibrate each corner of the device
    CORNER_NAMES = ['top right', 'top left', 'bottom left', 'bottom right']
    corners = []
    for corner in CORNER_NAMES:
        print 'Position the fingers in the %s corner of the device' % corner
        print 'and keep the hand as aligned with the touchpad as possible'
        corners.append(self._CalibratePosition())

    self._SetFingerStates(False, False)
    self._PopSpeed()

    # Build a DeviceSpec and save to disk if a filename was specified
    device_spec = DeviceSpec(*corners)
    if filename:
      device_spec.SaveToDisk(filename)

    return device_spec

  def Tap(self, device_spec, tap_location, touch_time_s=None):
    """ This tells the robot to perform a tap gesture at the specified
    location on the device.
    If a touch_time_s is specified (in seconds) the robot will leave
    its finger in contact with the touch sensor for that long, otherwise it
    will simply perform a quick tap.
    """
    abs_pos = device_spec.RelativePosToAbsolutePos(tap_location)
    abs_pos = self._CenterAroundSingleFinger(1, abs_pos)

    # Get into position
    self._SetFingerStates(False, False)
    self._SetCartesian(abs_pos, finger_distance=abs_pos.ax_5)

    # Touch the pad then lift the finger back up to tap
    self._ExtendFingerUntilContact(1, speed=1000,
                                   cutoff=Touchbot.DEFAULT_MAX_EXTENSION)
    if touch_time_s:
      time.sleep(touch_time_s)
    self._MoveFingerAbsolute(1, 0)
