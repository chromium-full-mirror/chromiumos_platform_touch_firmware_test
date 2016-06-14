# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import math
import os
import sys
import time

import numpy as np

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
  SPEED_SLOW = 20.0
  SPEED_MEDIUM = 40.0
  SPEED_FAST = 75.0
  SPEED_VERY_FAST = 85.0
  MAX_SPEED = 100.0

  # How much area around the edge should be avoided for quickstep
  QUICKSTEP_BUFFER = 0.1

  # Limits on how far the robot hand can move the fingers in and out
  MIN_FINGER_DISTANCE = 0.5
  MAX_FINGER_DISTANCE = 140
  MIN_CENTER_TO_CENTER_DISTANCE_MM = 10.0

  # Settings for how to interpolate movement between two points
  STRAIGHT_INTERPOLATION = -1
  JOINT_INTERPOLATION = 0
  INTERPOLATION_TYPES = [STRAIGHT_INTERPOLATION, JOINT_INTERPOLATION]

  # Setting for movement blending on the robot.  These set how the robot
  # blends consecutive movement commands
  BLEND_MOVEMENTS = -1
  PRECISE_MOVEMENTS = 0
  SMOOTHING_TYPES = [BLEND_MOVEMENTS, PRECISE_MOVEMENTS]

  # Constants for the finger actuators
  FINGER_NUMBERS = [1, 2]
  FINGER_CONTINUOUS_CURRENT_LIMIT_MA = 500
  FINGER_PEAK_CURRENT_LIMIT_MA = 700
  FINGER_HOME_OFFSET = 2500
  CALIBRATION_EXTENSION = 1500
  MIN_FINGER_SPACING = 12
  DEFAULT_FINGER_SPACING = 20
  DRUMROLL_SPACING = 8
  FINGER_ACCEL_MM_S_S = 500
  FINGER_DECEL_MM_S_S = 2000
  FINGER_PD_CONTROLLER_P = 20
  FINGER_PD_CONTROLLER_D = 10
  CALIBRATION_FINGERTIP1 = '1round_8mm'
  CALIBRATION_FINGERTIP2 = '2round_8mm'
  LARGE_FINGERTIP_VERTICAL_OFFSET = 2000
  TAP_LIFT_DISTANCE = 500
  CLICK_CURRENT_MA = 500
  PHYSICAL_CLICK_SPEED_MM_S = 5

  NO_RESPONSES = 0
  REQUIRE_RESPONSES = 2
  FINGER_RESPONSE_LEVELS = [NO_RESPONSES, REQUIRE_RESPONSES]

  # The parameter number of the robot's name in the controller's memory
  TOUCHBOT_NAME_PARAM_NUM = 2002

  def __init__(self, ip_address=TOUCHBOT_IP_ADDR, port=TOUCHBOT_PORT):
    self.speed_stack = []
    self.finger_speed_stack = []
    self.comm = TouchbotComm(ip_address, port)

    # Load all the fingertip locations from disk
    robot_name = self._GetRobotName()
    print 'Robot name "%s" detected.' % robot_name
    self.nest_locations_dir = 'nest_locations/%s' % robot_name
    self.fingertips = LoadFingertips(self.nest_locations_dir)
    if not self.fingertips:
      print 'ERROR: Unable to load fingertip locations for that robot!'
    self.attached_fingertips = set()

    # Lift up and center the wrist to prevent it starting twisted
    self._SetCartesian(self._AddSafetyClearance(self._GetCurrentPosition()))
    self._CenterWrist()

    # Initialize the fingers
    self._InitializeFingers()

    # Set everything to a sane speed
    self.PushSpeed(Touchbot.SPEED_MEDIUM)
    self._PushFingerSpeed_mm_per_s(1000)

    # By default we want the robot to use linear movement interpolation
    self._SetInterpolation(Touchbot.STRAIGHT_INTERPOLATION)

    # By default the robot should be set to not blend consecutive move commands
    # to produce more precise motions, at the cost of pauses between them.
    self._SetSmoothing(Touchbot.PRECISE_MOVEMENTS)

  def __del__(self):
    """ Return all fingertips and disable the fingers before quitting. """
    if self.comm:
      self._RequireFingertips(None, [], should_end_over_dut=False)
      self._SetCartesian(self._AddSafetyClearance(self._GetCurrentPosition()))
      for finger_number in Touchbot.FINGER_NUMBERS:
        self._DisableFinger(finger_number)

  def _CenterWrist(self):
    """ Rotate the wrist (axis 4) to it's middle point.
    This should be done intermittently to make sure it doesn't drift too far.
    The joint can only wrap around so many times before it's stuck, so this is
    a safe place to start a gesture from.
    """
    self.PushSpeed(Touchbot.SPEED_MEDIUM)
    pos = self._GetCurrentPosition()
    pos.ax_4 = 0
    pos.ax_5 = self._SuggestSpacing(self.attached_fingertips)
    err, _ = self._SetAngles(pos)
    self.PopSpeed()
    if err:
      print 'ERROR: unable to center the wrist.'

  def _InitializeFingers(self):
    # First turn on the fingers, and and lift them up as high as they go
    for finger_number in Touchbot.FINGER_NUMBERS:
      self._TurnOnFinger(finger_number)

    # Move the robot's hand over a known, flat surface to "zero" them on
    self._MoveToNest()
    zeroing_file = os.path.join(self.nest_locations_dir, 'zeroing_position.p')
    zeroing_pos= Position.FromPickledFile(zeroing_file)
    self._SetCartesian(zeroing_pos, finger_distance=5)

    # Now lower the fingers slowly until they hit the surface.  This will
    # allow us to make sure they are perfectly zeroed
    for finger_number in Touchbot.FINGER_NUMBERS:
      self._ZeroFinger(finger_number)

  def _ZeroFinger(self, finger_number):
    self._ExtendFingerUntilContact(finger_number, speed=10)
    self._SetFingerZeroPoint(finger_number)

  def _TurnOnFinger(self, finger_number):
    """ Do all the setup for a finger
    This function sets the current limit for the finger controller and sets
    the Zero point for the fingers
    """
    self._SetFingerResponseLevel(Touchbot.REQUIRE_RESPONSES)
    self._SendFingerCmd('%dDI' % finger_number)
    time.sleep(0.5)
    self._SetFingerContinuousCurrentLimit_mA(
        finger_number, Touchbot.FINGER_CONTINUOUS_CURRENT_LIMIT_MA)
    self._SetFingerPeakCurrentLimit_mA(
        finger_number, Touchbot.FINGER_PEAK_CURRENT_LIMIT_MA)

    self._SetFingerAcceleration(finger_number, Touchbot.FINGER_ACCEL_MM_S_S)
    self._SetFingerDeceleration(finger_number, Touchbot.FINGER_DECEL_MM_S_S)
    self._SetFingerPDParameters(finger_number,
                                Touchbot.FINGER_PD_CONTROLLER_P,
                                Touchbot.FINGER_PD_CONTROLLER_D)

    # Track to roughly the middle of the range and call that Zero
    self._SendFingerCmd('%dAPL0' % finger_number) # Disable range limiting
    self._EnableFinger(finger_number)
    self._ExtendFingerUntilContact(finger_number, speed=-30)
    self._SetFingerZeroPoint(finger_number)
    self._MoveFingerAbsolute(finger_number, 500)

  def _PushFingerSpeed_mm_per_s(self, speed):
    self.finger_speed_stack.append(self._GetFingerSpeed())
    self._SetFingerSpeed(speed)

  def _PopFingerSpeed(self):
    if len(self.finger_speed_stack) >= 1:
      self._SetFingerSpeed(self.finger_speed_stack.pop())

  def _GetFingerSpeed(self):
    return int(self._SendFingerCmd('1GSP'))

  def _SetFingerSpeed(self, speed):
    self._SendFingerCmd('1SP%d' % speed)
    self._SendFingerCmd('2SP%d' % speed)

  def _SetFingerPDParameters(self, finger_number, p, d):
    """ Configure the P and D parameters for the PD controller used to servo
    the finger positions.
    """
    self._SendFingerCmd('%dPP%d' % (finger_number, p))
    self._SendFingerCmd('%dPD%d' % (finger_number, d))

  def _SetFingerAcceleration(self, finger_number, speed):
    self._SendFingerCmd('%dAC%d' % (finger_number, speed))

  def _SetFingerDeceleration(self, finger_number, speed):
    self._SendFingerCmd('%dDEC%d' % (finger_number, speed))

  def _ExtendFingerUntilContact(self, finger_number, speed=30,
                                contact_current_ma=400):
    """ Extend the specified finger(s) slowly until it touches something.
    This is done by telling the finger to extend slowly and polling the
    amount of current the actuator is drawing.  As soon as it meets some
    resistance the current will jump, indicating that it has made contact.
    """
    if finger_number not in Touchbot.FINGER_NUMBERS + [None]:
      print 'ERROR: illegal finger_number (%d)' % finger_number
      return None
    fingers_to_extend = (set(Touchbot.FINGER_NUMBERS) if finger_number is None
                         else set([finger_number]))

    # First stop any fingertip motion and wait to let the current
    # drop for a little while to make sure they aren't going to
    # immediately trigger the current spike value.  This can occur if
    # the servo mechanism in the finger is still oscilating around its
    # target position.
    for finger in fingers_to_extend:
      self._SetFingerVelocity_mm_s(finger, 0)

    # Start the finger(s) moving at the specified velocity
    for finger in fingers_to_extend:
      self._SetFingerVelocity_mm_s(finger, speed)

    # Now poll the fingers' positions and current to know when to stop
    while len(fingers_to_extend) > 0:
      for finger in list(fingers_to_extend):
        current = self._GetFingerCurrent_mA(finger)

        # If the current spikes, we know we've touched something
        if (current >= contact_current_ma):
          self._SetFingerVelocity_mm_s(finger, 0)
          fingers_to_extend.remove(finger)

    return self._GetFingerPos(finger)


  def _SetFingerVelocity_mm_s(self, finger_number, speed):
    """ Set the specified finger's velocity (as opposed to position) """
    self._SendFingerCmd('%dV%d' % (finger_number, speed))

  def _GetFingerCurrent_mA(self, finger_number):
    """ Get the current for a specified finger in mA """
    return int(self._SendFingerCmd('%dGRC' % finger_number))

  def _SetFingerZeroPoint(self, finger_number):
    """ Set Home (position 0) for the given finger to where it is right now """
    self._SendFingerCmd('%dHO' % finger_number)

  def _SetFingerContinuousCurrentLimit_mA(self, finger_number, current):
    """ Set the maximum continuous current that this finger can draw in mA """
    self._SendFingerCmd('%dLCC%d' % (finger_number, current))

  def _SetFingerPeakCurrentLimit_mA(self, finger_number, current):
    """ Set the maximum Peak current that this finger can draw in mA """
    self._SendFingerCmd('%dLCC%d' % (finger_number, current))

  def _EnableFinger(self, finger_number):
    """ Enable the finger, it can now move when given movement commands """
    self._SendFingerCmd('%dEN' % finger_number)

  def _GetFingerPos(self, finger_number):
    """ Get the current position of the finger """
    return int(self._SendFingerCmd('%dPOS' % finger_number))

  def _GetFingerTargetPos(self, finger_number):
    """ Get the position that this finger is currently trying to go to """
    return int(self._SendFingerCmd('%dTPOS' % finger_number))

  def _SetFingerResponseLevel(self, response_level):
    if response_level not in Touchbot.FINGER_RESPONSE_LEVELS:
      print 'ERROR: Unknown finger response level "%s"!' % str(response_level)
      return
    self.finger_response_level = response_level
    for finger in Touchbot.FINGER_NUMBERS:
      self._SendFingerCmd('%dANSW%d' % (finger, response_level))

  def _SendFingerCmd(self, cmd):
    # Messages not beginning in a finger number (1 or 2) are broadcast to
    # both fingers, and can cause collisions on the serial bus if they both
    # respond at the same time.
    if (self.finger_response_level != Touchbot.NO_RESPONSES and
        cmd[0] not in ('1', '2')):
      print ('WARNING: broadcast commands are dangerous to use when '
             'the fingertips are configured to respond!')

    return self.comm.SendFingerCmd(cmd)

  def _ExecuteFingerMove(self, finger_number, must_sync, blocking):
    """ Tell the finger to execute a pending move.
    If blocking is set to True then this will poll the finger until the
    true location of the finger and the target location are sufficiently
    close together.
    """
    CORRIDOR = 20

    if finger_number in Touchbot.FINGER_NUMBERS:
      required_fingers = [finger_number]
      self._SendFingerCmd('%dM' % finger_number)
    else:
      required_fingers = Touchbot.FINGER_NUMBERS

      if must_sync:
        # Briefly disable responses so we can send a broacast "Move" instruction
        # to both fingers simultaneously.  If they don't move perfectly in sync
        # with eachother, they can't stay aligned with the magnets in the two
        # finger probes, which makes them liable to fall off.
        # Note: This is slow, it takes the fingers several seconds to do this
        self._SetFingerResponseLevel(Touchbot.NO_RESPONSES)
        self._SendFingerCmd('M')
        self._SetFingerResponseLevel(Touchbot.REQUIRE_RESPONSES)
      else:
        for finger in required_fingers:
          self._SendFingerCmd('%dM' % finger)

    if blocking:
      targets = {}
      for finger in required_fingers:
        targets[finger] = self._GetFingerTargetPos(finger)

      while True:
        completed_fingers = set()
        for finger in required_fingers:
          if finger not in completed_fingers:
            current = self._GetFingerPos(finger)
            if abs(targets[finger] - current) <= CORRIDOR:
              completed_fingers.add(finger)
        if len(completed_fingers) == len(required_fingers):
          return

  def _MoveFingerAbsolute(self, finger_number, position, blocking=True):
    """ Move the finger to an absolute position. """
    self._SendFingerCmd('%dLA%d' % (finger_number, position))
    self._ExecuteFingerMove(finger_number, False, blocking)

  def _MoveFingerRelative(self, finger_number, delta, blocking=True):
    """ Move the finger to an relative position. """
    self._SendFingerCmd('%dLR%d' % (finger_number, delta))
    self._ExecuteFingerMove(finger_number, False, blocking)

  def _MoveBothFingersAbsolute(self, position1, position2,
                               must_sync=False, blocking=True):
    """ Move both fingers to absolute positions.
    The must_sync parameter allows you to indicate that the fingers must
    move totally in sync (as is the case for two-finger fingertips).  This
    incurs a delay, so it's better not to specify it unless you need to.
    For most situations, they do not need to be perfectly synced.
    """
    self._SendFingerCmd('1LA%d' % position1)
    self._SendFingerCmd('2LA%d' % position2)
    self._ExecuteFingerMove(None, must_sync, blocking)

  def _MoveBothFingersRelative(self, delta1, delta2,
                               must_sync=False, blocking=True):
    """ Move both fingers to relative positions.
    This uses the same arguments as _MoveBothFingersAbsolute, but
    uses relative position values instead of absolute.
    """
    self._SendFingerCmd('1LR%d' % delta1)
    self._SendFingerCmd('2LR%d' % delta2)
    self._ExecuteFingerMove(None, must_sync, blocking)

  def _DisableFinger(self, finger_number):
    self._MoveFingerAbsolute(finger_number, 0.9 * Touchbot.FINGER_HOME_OFFSET)
    self._SendFingerCmd('%dDI' % finger_number)

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

  def _SetInterpolation(self, interpolation_type):
    if interpolation_type not in Touchbot.INTERPOLATION_TYPES:
      print 'ERROR: Invalid interpolation type (%d).' % interpolation_type
      return
    prof = self._GetCurrentProfile()
    prof.straight = interpolation_type
    self._SetProfileData(prof)

  def _SetSmoothing(self, smoothing_type):
    if smoothing_type not in Touchbot.SMOOTHING_TYPES:
      print 'ERROR: Invalid smoothing type (%d).' % smoothing_type
      return
    prof = self._GetCurrentProfile()
    prof.inRange = smoothing_type
    self._SetProfileData(prof)

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

  def _GetRobotName(self):
    """ Query the robot for its name.  This value is used to determine which
    set of trained nest positions to use. """
    error, name = self.comm.SendCmd('pd', Touchbot.TOUCHBOT_NAME_PARAM_NUM)
    if error:
      return ''
    # Remove the carrage return at the end, to get a cleaner string
    return name.rstrip()

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

  def PushSpeed(self, new_speed):
    self.speed_stack.append(self._GetSpeed())
    self._SetSpeed(new_speed)

  def PopSpeed(self):
    if len(self.speed_stack) >= 1:
      self._SetSpeed(self.speed_stack.pop())

  def _GetFingertip(self, fingertip):
    """ Retrieve the specified fingertip from the nest. """
    self._MoveBothFingersAbsolute(0, 0)
    self._SetCartesian(fingertip.above_pos,
                       finger_distance=fingertip.above_pos.ax_5)

    self.PushSpeed(Touchbot.SPEED_MEDIUM)

    self._MoveBothFingersAbsolute(fingertip.extension1, fingertip.extension2)
    self._SetCartesian(fingertip.slide_pos,
                       finger_distance=fingertip.slide_pos.ax_5)

    self.PopSpeed()

    self._PushFingerSpeed_mm_per_s(10 if fingertip.IsLarge() else 20)
    is_dual_fingertip = (fingertip.finger_number is None)
    self._MoveBothFingersAbsolute(0, 0, must_sync=is_dual_fingertip)
    self._PopFingerSpeed()

    self.attached_fingertips.add(fingertip)

  def _DropFingertip(self, fingertip):
    """ Drop off the specified fingertip at its place in the nest. """
    is_dual_fingertip = (fingertip.finger_number is None)

    self._PushFingerSpeed_mm_per_s(10 if fingertip.IsLarge() else 50)

    self._MoveBothFingersAbsolute(0, 0, must_sync=is_dual_fingertip)
    self._SetCartesian(self._AddSafetyClearance(fingertip.slide_pos),
                       finger_distance=fingertip.slide_pos.ax_5)

    self.PushSpeed(Touchbot.SPEED_MEDIUM)
    self._SetCartesian(fingertip.slide_pos,
                       finger_distance=fingertip.slide_pos.ax_5)

    self._MoveBothFingersAbsolute(fingertip.extension1, fingertip.extension2,
                                  must_sync=is_dual_fingertip)
    self._SetCartesian(fingertip.above_pos,
                       finger_distance=fingertip.above_pos.ax_5)

    self.PopSpeed()
    self._PopFingerSpeed()
    self._MoveBothFingersAbsolute(0, 0)

    self.attached_fingertips.remove(fingertip)

  def _MoveToNest(self):
    """ Safely move the robot from over the DUT to over the nest """
    # Find a position just over the current spot, to avoid hitting anything
    curr_pos = self._GetCurrentPosition()
    above_curr_pos = self._AddSafetyClearance(curr_pos)

    # Find a spot over the nest
    nest_pos = None
    for fingertip in self.fingertips.values():
      if nest_pos is None:
        nest_pos = copy.deepcopy(fingertip.above_pos)
      else:
        nest_pos.x += fingertip.above_pos.x
        nest_pos.y += fingertip.above_pos.y
    nest_pos.x /= len(self.fingertips)
    nest_pos.y /= len(self.fingertips)
    above_nest = self._AddSafetyClearance(nest_pos)

    # Compute an intermediate step to prevent the hand colliding with the
    # body of the robot.
    intermediate_pos = copy.deepcopy(above_nest)
    intermediate_pos.x = above_curr_pos.x

    # Actually execute the moves
    self._SetCartesian(above_curr_pos, blocking=True)
    self._SetCartesian(intermediate_pos, blocking=True)
    self._SetCartesian(above_nest, blocking=True)

  def _CenterOverDevice(self, device_spec):
    """ Safely move the robot from over the nest to over the DUT """
    # Find a position just over the current spot, to avoid hitting anything
    curr_pos = self._GetCurrentPosition()
    above_curr_pos = self._AddSafetyClearance(curr_pos)

    # Move over the center of the DUT
    center = device_spec.RelativePosToAbsolutePos((0.5, 0.5))
    above_dut = self._AddSafetyClearance(center)

    # Compute an intermediate step to prevent collisions
    intermediate_pos = copy.deepcopy(above_curr_pos)
    intermediate_pos.x = above_dut.x

    # Finally, execute the moves
    self.PushSpeed(Touchbot.SPEED_FAST)
    self._SetCartesian(above_curr_pos, blocking=True)
    self._SetCartesian(intermediate_pos, blocking=True)
    self._SetCartesian(above_dut, blocking=True)
    self.PopSpeed()

  def _RequireFingertips(self, device_spec, required_fingertips,
                         should_end_over_dut=True):
    """ Swap out fingertips as needed to have the specified ones equipped.
    If they are already attached, this will do nothing, but otherwise will
    put away any incorrect fingertips that are currenlty attached and will
    attach the requested tips from the nest.
    """
    self.PushSpeed(Touchbot.SPEED_MEDIUM)

    # This function starts assuming the robot is over the dut and ready to
    # perform gestures
    is_over_dut = True

    # Remove any unneeded fingertips
    if not self.attached_fingertips.issubset(set(required_fingertips)):
      self._MoveToNest()
      is_over_dut = False
      for fingertip in list(self.attached_fingertips):
        if fingertip not in required_fingertips:
          self._DropFingertip(fingertip)

    # Attach the required ones that are not already attached
    if not set(required_fingertips).issubset(self.attached_fingertips):
      if is_over_dut:
        self._MoveToNest()
        is_over_dut = False
      for fingertip in required_fingertips:
        if fingertip not in self.attached_fingertips:
          self._GetFingertip(fingertip)

    # Finally move the robot back over the DUT if we had to move it to
    # the nest to do some fingertip swaps
    if should_end_over_dut and not is_over_dut:
      self._CenterOverDevice(device_spec)

    self._CenterWrist()
    self.PopSpeed()


  def _CenterForFingertip(self, fingertip, pos):
    """ Offset the coordinates so that  is centered at the point given,
    not the point directly between the two fingers.
    """
    # Two-finger tips are already centered
    if fingertip.finger_number not in Touchbot.FINGER_NUMBERS:
      return pos

    # Shift the x and y accordingly for both points in the line
    angle_deg = pos.yaw + (-90 if fingertip.finger_number == 1 else 90)
    angle_rad = math.radians(angle_deg)
    pos.x += math.cos(angle_rad) * (pos.ax_5 + Touchbot.MIN_FINGER_SPACING) / 2.0
    pos.y += math.sin(angle_rad) * (pos.ax_5 + Touchbot.MIN_FINGER_SPACING) / 2.0
    return pos

  def _IntermediatePoints(self, start, end, steps=15):
    """ Compute a number of intermediate points between the given
    coordinates.

    This function returns a list of coordinate tuples, linearly interpolating
    between start and end.
    """
    x1, y1 = start
    x2, y2 = end
    return [(x1 * (1.0 - alpha) + x2 * alpha, y1 * (1.0 - alpha) + y2 * alpha)
            for alpha in np.linspace(0.0, 1.0, num=steps)]

  def _SuggestSpacing(self, fingertips):
    # Guess how far apart to space the fingers for a gesture using these tips
    for fingertip in fingertips:
      if fingertip.finger_number is None:
        return fingertip.above_pos.ax_5
    return Touchbot.DEFAULT_FINGER_SPACING


################################################################################
#                    Actual gestures after this point                          #
################################################################################

  def CalibrateDevice(self, filename=None):
    fingertips = [self.fingertips[Touchbot.CALIBRATION_FINGERTIP1],
                  self.fingertips[Touchbot.CALIBRATION_FINGERTIP2]]
    self._RequireFingertips(None, fingertips, should_end_over_dut=False)
    self.PushSpeed(Touchbot.SPEED_FAST)

    # First, lift the arm up and clear of any obstructions with the fingers as
    # close together as they can to allow for easy centering
    pos = self._GetCurrentPosition()
    pos = self._AddSafetyClearance(pos)
    self._SetCartesian(pos, finger_distance=4, blocking=True)

    self._MoveBothFingersAbsolute(Touchbot.CALIBRATION_EXTENSION,
                                  Touchbot.CALIBRATION_EXTENSION)

    # Prompt the user to calibrate each corner of the device
    CORNER_NAMES = ['top right', 'top left', 'bottom left', 'bottom right']
    corners = []
    for corner in CORNER_NAMES:
        print 'Position the fingers in the %s corner of the device' % corner
        print 'and keep the hand as aligned with the touchpad as possible'
        corners.append(self._CalibratePosition())

    self._MoveBothFingersAbsolute(0, 0)

    pos = self._GetCurrentPosition()
    pos = self._AddSafetyClearance(pos)
    self._SetCartesian(pos)
    self.PopSpeed()

    # Build a DeviceSpec and save to disk if a filename was specified
    device_spec = DeviceSpec(*corners)
    if filename:
      device_spec.SaveToDisk(filename)

    return device_spec

  def Tap(self, device_spec, fingertips, tap_location,
          touch_time_s=None, angle=0, vertical_offset=0, num_taps=1):
    """ This tells the robot to perform a tap gesture at the specified
    location on the device.
    If a touch_time_s is specified (in seconds) the robot will leave
    its finger in contact with the touch sensor for that long, otherwise it
    will simply perform a quick tap.
    """
    self._RequireFingertips(device_spec, fingertips)

    is_dual_fingertip = False
    abs_pos = device_spec.RelativePosToAbsolutePos(tap_location, angle=angle)
    abs_pos.ax_5 = self._SuggestSpacing(fingertips)
    if len(fingertips) == 1:
      abs_pos = self._CenterForFingertip(fingertips[0], abs_pos)
      is_dual_fingertip = (fingertips[0].finger_number is None)

    # Get into position
    self._MoveBothFingersAbsolute(-vertical_offset, -vertical_offset,
                                  must_sync=is_dual_fingertip)
    self._SetCartesian(abs_pos, finger_distance=abs_pos.ax_5)

    # Precomputing tap parameters based on the fingertip
    finger_number = None
    if len(fingertips) == 1:
      finger_number = fingertips[0].finger_number
    speed = 5000 if not fingertips[0].IsLarge() else 10

    self._PushFingerSpeed_mm_per_s(speed)
    for tap in range(num_taps):
      # Touch the pad
      self._ExtendFingerUntilContact(finger_number, speed=speed)
      if touch_time_s:
        time.sleep(touch_time_s)

      # Then lift up
      if finger_number is not None:
        self._MoveFingerRelative(finger_number, -Touchbot.TAP_LIFT_DISTANCE)
      else:
        self._MoveBothFingersRelative(-Touchbot.TAP_LIFT_DISTANCE,
                                      -Touchbot.TAP_LIFT_DISTANCE,
                                      must_sync=is_dual_fingertip)

    self._MoveBothFingersAbsolute(-vertical_offset, -vertical_offset,
                                  must_sync=is_dual_fingertip)
    self._PopFingerSpeed()

  def Line(self, device_spec, fingertips, start_location, end_location,
           fingertip_angle=0, fingertip_spacing=None, pause_s=0, swipe=False):
    """ Draw a line on the pad
    This gesture will:
      1. Center the specified fingertip(s) over the start location
      2. Touch down
      3. Optionally pause for the specified number of seconds
      4. Move to the end location
      5. Lift up
    """
    self._RequireFingertips(device_spec, fingertips)

    # Compute how far apart the fingers should be spread
    if fingertip_spacing is None:
      fingertip_spacing = self._SuggestSpacing(fingertips)
    # Note which fingers are in play
    fingers_to_extend = fingertips[0].finger_number
    if len(fingertips) > 1:
      fingers_to_extend = None

    # Raise up both fingers
    self._MoveBothFingersAbsolute(0, 0)

    # Move into position
    self.PushSpeed(Touchbot.SPEED_MEDIUM)
    start_abs = device_spec.RelativePosToAbsolutePos(start_location)
    start_abs.yaw += fingertip_angle
    start_abs.ax_5 = fingertip_spacing
    if len(fingertips) == 1:
      start_abs = self._CenterForFingertip(fingertips[0], start_abs)
    self._SetCartesian(start_abs, finger_distance=start_abs.ax_5)
    self.PopSpeed()

    # If this is NOT a swipe, extend the fingers now (before anything moves)
    if not swipe:
      self._ExtendFingerUntilContact(fingers_to_extend, speed=10)
      time.sleep(pause_s)

    # Move to the end position
    end_abs = device_spec.RelativePosToAbsolutePos(end_location)
    end_abs.yaw += fingertip_angle
    end_abs.ax_5 = fingertip_spacing
    if len(fingertips) == 1:
      end_abs = self._CenterForFingertip(fingertips[0], end_abs)
    self._SetCartesian(end_abs, finger_distance=end_abs.ax_5,
                       blocking=(not swipe))

    # If this IS a swipe, extend the fingers now (after they're already moving)
    if swipe:
      self._ExtendFingerUntilContact(fingers_to_extend, speed=200)

    # Then lift up
    self._MoveBothFingersAbsolute(0, 0)

    # Make sure nothing exits until all the moves have completed, just in case
    self._Wait()

  def LineWithStationaryFinger(self, device_spec, stationary_fingertip,
                               moving_fingertip, start_location, end_location,
                               stationary_location):

    self._RequireFingertips(device_spec,
                            [stationary_fingertip, moving_fingertip])

    stationary_abs = device_spec.RelativePosToAbsolutePos(stationary_location,
                          max_diagonal_distance=Touchbot.MAX_FINGER_DISTANCE)
    sx, sy = stationary_abs.x, stationary_abs.y

    positions = []
    for moving_relative in self._IntermediatePoints(start_location,
                                                    end_location):
      # Convert into the absolute space, using the device spec
      moving_abs = device_spec.RelativePosToAbsolutePos(moving_relative,
                          max_diagonal_distance=Touchbot.MAX_FINGER_DISTANCE)
      mx, my = moving_abs.x, moving_abs.y

      # Find the center point between the two fingers
      cx = (mx + sx) / 2.0
      cy = (my + sy) / 2.0

      # Compute the angle between the two fingers
      dx = mx - sx
      dy = my - sy
      angle = math.degrees(math.atan2(dy, dx)) + 90

      # Compute the distance between the fingers
      d = (dx ** 2 + dy ** 2) ** 0.5
      d -= Touchbot.MIN_CENTER_TO_CENTER_DISTANCE_MM

      # Issue the movement command.  Start with a known good location on the
      # sensor and then modify the coordinates to fit the gesture.
      pos = moving_abs
      pos.x = cx
      pos.y = cy
      pos.yaw = angle
      pos.ax_5 = d
      positions.append(pos)

    # Move the robot into position
    self._SetCartesian(positions[0], finger_distance=positions[0].ax_5,
                       blocking=True)
    self._ExtendFingerUntilContact(stationary_fingertip.finger_number)
    self._ExtendFingerUntilContact(moving_fingertip.finger_number)

    # Perform the gesture
    self._SetSmoothing(Touchbot.BLEND_MOVEMENTS)
    for pos in positions:
      self._SetCartesian(pos, finger_distance=pos.ax_5, blocking=False)
    self._SetSmoothing(Touchbot.PRECISE_MOVEMENTS)
    self._Wait()

    # Lift off the pad
    self._MoveBothFingersAbsolute(0, 0)

  def Pinch(self, device_spec, fingertips, center, angle, start_distance,
            end_distance):
    self._RequireFingertips(device_spec, fingertips)
    pos = device_spec.RelativePosToAbsolutePos(center, angle=angle)
    self._SetCartesian(pos, finger_distance=start_distance, blocking=True)
    self._ExtendFingerUntilContact(None)
    self._SetCartesian(pos, finger_distance=end_distance, blocking=True)
    self._MoveBothFingersAbsolute(0, 0)

  def Click(self, device_spec, fingertips, tap_location):
    """ This tells the robot to perform a PHYSICAL click gesture at the
    specified location on the device.  This means it will press down
    hard, to make sure that when the touchpad is physically clicked down
    the dome switch reports a click.
    """
    self._RequireFingertips(device_spec, fingertips)

    finger_number = None
    abs_pos = device_spec.RelativePosToAbsolutePos(tap_location)
    abs_pos.ax_5 = self._SuggestSpacing(fingertips)
    if len(fingertips) == 1:
      finger_number = fingertips[0].finger_number
      abs_pos = self._CenterForFingertip(fingertips[0], abs_pos)

    # Get into position
    self._MoveBothFingersAbsolute(0, 0)
    self._SetCartesian(abs_pos, finger_distance=abs_pos.ax_5)

    # Exert some force on the pad to cause a click
    self._ExtendFingerUntilContact(finger_number,
                                   speed=Touchbot.PHYSICAL_CLICK_SPEED_MM_S,
                                   contact_current_ma=Touchbot.CLICK_CURRENT_MA)

    # Lift up
    self._MoveBothFingersAbsolute(0, 0)

  def Drumroll(self, device_spec, fingertips, location, num_taps=20):
    """ This gesture performs a 'drumroll' at the specified location by tapping
    with two fingertips alternating quickly.
    """
    self._RequireFingertips(device_spec, fingertips)
    if len(fingertips) != 2:
        print 'WARNING, a drumroll should always use TWO fingertips'

    # Get into position
    abs_pos = device_spec.RelativePosToAbsolutePos(location)
    abs_pos.ax_5 = Touchbot.DRUMROLL_SPACING
    self._MoveBothFingersAbsolute(0, 0)
    self._SetCartesian(abs_pos, finger_distance=abs_pos.ax_5)

    # Increasing the accelleration and speed temporarily on the fingertips
    for finger in Touchbot.FINGER_NUMBERS:
      self._SetFingerAcceleration(finger, 3 * Touchbot.FINGER_ACCEL_MM_S_S)
      self._SetFingerDeceleration(finger, 3 * Touchbot.FINGER_DECEL_MM_S_S)
    self._PushFingerSpeed_mm_per_s(2000)

    # Actually perform the taps
    # Start with finger 1 down, and then alternate
    distance_to_pad = self._ExtendFingerUntilContact(1)
    for tap in range(num_taps):
      self._MoveFingerAbsolute(2, distance_to_pad, blocking=False)
      self._MoveFingerRelative(1, -Touchbot.TAP_LIFT_DISTANCE, blocking=True)
      self._MoveFingerAbsolute(1, distance_to_pad, blocking=False)
      self._MoveFingerRelative(2, -Touchbot.TAP_LIFT_DISTANCE, blocking=True)

    # Slowing everything back down to normal before continuing
    for finger in Touchbot.FINGER_NUMBERS:
      self._SetFingerAcceleration(finger, Touchbot.FINGER_ACCEL_MM_S_S)
      self._SetFingerDeceleration(finger, Touchbot.FINGER_DECEL_MM_S_S)
    self._PopFingerSpeed()

    # Lift up both fingers before finishing, to end in a known state
    self._MoveBothFingersAbsolute(0, 0)

  def Quickstep(self, device_spec, fingertips, num_passes, speed):
    """ Move a finger back and forth vertically on the touch device as it
    slowly works it's way down, covering the whole area in vertical lines at
    a constant speed.  This is used by the Quickstep latency measurement
    device, which needs a finger to cross a laser beam repeatedly at a fixed
    speed to measure the drag latency on a touch sensor.
    """
    # Prepare for the gesture, by getting the required fingertips
    self._RequireFingertips(device_spec, fingertips)

    # First, move the robot into position over the top left corner
    init_abs_pos = device_spec.RelativePosToAbsolutePos(
        (self.QUICKSTEP_BUFFER, self.QUICKSTEP_BUFFER))
    init_abs_pos.ax_5 = self._SuggestSpacing(fingertips)
    init_abs_pos = self._CenterForFingertip(fingertips[0], init_abs_pos)
    self.PushSpeed(self.SPEED_SLOW)
    self._MoveBothFingersAbsolute(0, 0)
    self._SetCartesian(init_abs_pos, finger_distance=init_abs_pos.ax_5)
    self.PopSpeed()
    self.PushSpeed(speed)
    self._ExtendFingerUntilContact(1)

    # Then draw a series of vertical lines evenly spaced over the sensor
    for i in xrange(num_passes):
      # Draw a down stroke
      downstroke_x = ((float(i) / float(num_passes)) *
                      (1.0 - self.QUICKSTEP_BUFFER * 2) + self.QUICKSTEP_BUFFER)
      downstroke_start = (downstroke_x, self.QUICKSTEP_BUFFER)
      downstroke_start_abs_pos = device_spec.RelativePosToAbsolutePos(
                                                downstroke_start)
      downstroke_start_abs_pos.ax_5 = self._SuggestSpacing(fingertips)
      downstroke_start_abs_pos = self._CenterForFingertip(
                                         fingertips[0],
                                         downstroke_start_abs_pos)
      self._SetCartesian(downstroke_start_abs_pos,
                         finger_distance=downstroke_start_abs_pos.ax_5)

      downstroke_end = (downstroke_x, 1.0 - self.QUICKSTEP_BUFFER)
      downstroke_end_abs_pos = device_spec.RelativePosToAbsolutePos(
                                               downstroke_end)
      downstroke_end_abs_pos.ax_5 = self._SuggestSpacing(fingertips)
      downstroke_end_abs_pos = self._CenterForFingertip(
                                       fingertips[0],
                                       downstroke_end_abs_pos)
      self._SetCartesian(downstroke_end_abs_pos,
                         finger_distance=downstroke_end_abs_pos.ax_5)

      # Draw an upstroke
      upstroke_x = ((float(i + 0.5) / float(num_passes)) *
                    (1.0 - self.QUICKSTEP_BUFFER * 2) + self.QUICKSTEP_BUFFER)
      upstroke_start = (upstroke_x, 1.0 - self.QUICKSTEP_BUFFER)
      upstroke_start_abs_pos = device_spec.RelativePosToAbsolutePos(
                                              upstroke_start)
      upstroke_start_abs_pos.ax_5 = self._SuggestSpacing(fingertips)
      upstroke_start_abs_pos = self._CenterForFingertip(
                                       fingertips[0],
                                       upstroke_start_abs_pos)
      self._SetCartesian(upstroke_start_abs_pos,
                         finger_distance=upstroke_start_abs_pos.ax_5)

      upstroke_end = (upstroke_x, self.QUICKSTEP_BUFFER)
      upstroke_end_abs_pos = device_spec.RelativePosToAbsolutePos(upstroke_end)
      upstroke_end_abs_pos.ax_5 = self._SuggestSpacing(fingertips)
      upstroke_end_abs_pos = self._CenterForFingertip(fingertips[0],
                                                      upstroke_end_abs_pos)
      self._SetCartesian(upstroke_end_abs_pos,
                         finger_distance=upstroke_end_abs_pos.ax_5)

    # Lift the fingers both up and return the robot to its original speed
    self._MoveBothFingersAbsolute(0, 0)
    self.PopSpeed()

  def Draw45DegreeLineSegment(self, device_spec, fingertips, location):
    """ Draw a short line segment 45 degrees off from the x axis of
    the touch device.  This gesture is slightly different than the others,
    in that it uses real measurements instead of reletive to the dimensions
    of the sensor.  This is to allow us to test and see if the resolution
    of the touch device is configured squarely.  ie: if the robot draws
    what we know is a 45 degree angle, and the touchpad reports it as
    45, then we know the resolution is configured correctly, otherwise
    motion is being compressed on one of the axes.
    """
    LINE_LENGTH_MM = 10
    # Prepare for the gesture, by getting the required fingertips
    self._RequireFingertips(device_spec, fingertips)

    # Compute the positions of the corners of the square
    center = device_spec.RelativePosToAbsolutePos(location)
    center.ax_5 = self._SuggestSpacing(fingertips)
    center = self._CenterForFingertip(fingertips[0], center)

    start = copy.copy(center)
    start.x -= LINE_LENGTH_MM // 2
    start.y -= LINE_LENGTH_MM // 2

    end = copy.copy(center)
    end.x += LINE_LENGTH_MM // 2
    end.y += LINE_LENGTH_MM // 2

    # Get the robot into position, touching the starting position
    self.PushSpeed(self.SPEED_MEDIUM)
    self._SetCartesian(start, finger_distance=start.ax_5)
    self._ExtendFingerUntilContact(1)
    self.PopSpeed()

    # Have the robot trace slowly between the computer points
    self.PushSpeed(self.SPEED_SLOW)
    self._SetCartesian(end, finger_distance=end.ax_5)
    self.PopSpeed()
    self._MoveBothFingersAbsolute(0, 0)
