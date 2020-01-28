# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

class RemoteTouchDevice:
  """ An abstract base class to define access to touch events on remote devices

  To enable running touch device firmware testing on devices of various types
  of platforms this module introduces a RemoteTouchDevice interface.  One can
  create subclasses that fill out how to stream touch events from a remote
  touch device and then they can be substituted seamlessly, leveraging the test
  suite's common code.

  The basic work flow for a RemoteTouchDevice is this:
   1. Create the device (specifics may vary depending on DUT type)
   2. Call the device's FlushSnapshotBuffer() method to consume any events
    that occurred since the last time you called NextSnapshot() or created
    the connection.  This needs only to get called if you want to flush the
    buffer of events.
   3. Repeatedly call NextSnapshot(), which will block until another MtSnapshot
    arrives.  These are little structures defined in mt/state_machine.py and
    contain finger data from one SYN event.

  For example, you would instantiate objects for various types then use them
  exactly the same way:

    # Initialize your remote touch devices depending on what the DUT is
    touch_dev = ChromeOSTouchDevice(addr='192.168.0.3', is_touchscreen=False)
    touch_dev = AndroidTouchDevice(addr=None, is_touchscreen=True)

    # Do some work here...

    # Flush any events that are buffered and print the next 100 snapshots
    touch_dev.FlushSnapshotBuffer()()
    for i in range(100):
      print touch_dev.NextSnapshot()
  """
  not_implemented_msg = 'Must be implemented by a subclass.'

  def __init__(self):
    self.warnings = []

  def Warn(self, message):
    """ Display a warning on stdout as well as storing it in a member variable
    for later use.
    """
    print('\033[1;31mWARNING (remote touch device): %s\033[0m' % message)
    self.warnings.append(message)

  def FlushSnapshotBuffer(self, wait_until_no_fingers_present=False):
    while True:
      snapshot = self.NextSnapshot(timeout=self.flush_timeout)
      while snapshot:
        snapshot = self.NextSnapshot(timeout=self.flush_timeout)

      if not wait_until_no_fingers_present:
        return
      elif (not self.most_recent_snapshot or
            len(self.most_recent_snapshot.fingers) == 0):
        return

  def NextSnapshot(self, timeout=None):
    """ Consume MtEvents from the touch device until a complete snapshot has
    come in.  This maintains the state machine and returns the next MtSnapshot
    or None in the case that connection is lost.

    If it ever has to wait more than the specified timeout (in seconds) for
    the next MtEvent it will return None instead of a MtSnapshot.  The default
    timeout value of None indicates that it should wait forever.
    """
    event = self._NextEvent(timeout)
    while event:
      self.state_machine.add_event(event)
      if event.is_SYN_REPORT():
        self.most_recent_snapshot = self.state_machine.get_current_snapshot()
        if self.most_recent_snapshot:
          return self.most_recent_snapshot
      event = self._NextEvent(timeout)
    return None

  def ResolutionX(self):
    return self._x_res

  def ResolutionY(self):
    return self._y_res

  def RangeX(self):
    return self._x_min, self._x_max

  def RangeY(self):
    return self._y_min, self._y_max

  def RangeP(self):
    return self._p_min, self._p_max

  def RangeTiltX(self):
    return self._tilt_x_min, self._tilt_x_max

  def RangeTiltY(self):
    return self._tilt_y_min, self._tilt_y_max

  def RangeMajor(self):
    return self._major_min, self._major_max

  def RangeMinor(self):
    return self._minor_min, self._minor_max

  def _GetDimensions(self):
    """ Ask the device for the dimensions, the x/y resolution, and the range
    of pressure values should be reported.
    if the device doesn't report the lower bound, the lower bound zero should
    be reported.

    This function should return three dictionaries of the following form:
      (x, y, p)
    where x and why have 'min' 'max' and 'resolution' defined, and p has only
    'min' and 'max.

    This is called automatically in the constructor to set the ranges for all
    of the various dimensions of the device.
    """
    raise NotImplementedError(RemoteTouchDevice.not_implemented_msg)

  # Below are functions common to all RemoteTouchDevices and do not need to
  # be overridden by subclasses
  def PxToMm_X(self, x):
    return float(x) / float(self.ResolutionX())

  def PxToMm_Y(self, x):
    return float(x) / float(self.ResolutionY())

  def PxToMm(self, point):
    (x, y) = point
    return self.PxToMm_X(x), self.PxToMm_Y(y)
