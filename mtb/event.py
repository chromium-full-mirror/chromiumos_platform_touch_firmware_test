# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from input.linux_input import *

class MtbEvent:
  """ Class that holds the a single MTB event (Not a complete packet) """
  def __init__(self, timestamp, event_type=EV_SYN, event_code=None, value=None):
    self.timestamp = timestamp
    self.event_type = event_type
    self.event_code = event_code
    self.value = value

  def is_ABS_MT_TRACKING_ID(self):
    """ Is this event ABS_MT_TRACKING_ID? """
    return self.event_type == EV_ABS and self.event_code == ABS_MT_TRACKING_ID

  def is_new_contact(self):
    """ Is this event generating new contact (Tracking ID)? """
    return self.is_ABS_MT_TRACKING_ID() and self.value != -1

  def is_finger_leaving(self):
    """ Is the finger is leaving in this event? """
    return self.is_ABS_MT_TRACKING_ID() and self.value == -1

  def is_ABS_MT_SLOT(self):
    """ Is this event ABS_MT_SLOT? """
    return self.event_type == EV_ABS and self.event_code == ABS_MT_SLOT

  def is_ABS_MT_POSITION_X(self):
    """ Is this event ABS_MT_POSITION_X? """
    return self.event_type == EV_ABS and self.event_code == ABS_MT_POSITION_X

  def is_ABS_MT_POSITION_Y(self):
    """ Is this event ABS_MT_POSITION_Y? """
    return self.event_type == EV_ABS and self.event_code == ABS_MT_POSITION_Y

  def is_ABS_MT_PRESSURE(self):
    """ Is this event ABS_MT_PRESSURE? """
    return self.event_type == EV_ABS and self.event_code == ABS_MT_PRESSURE

  def is_finger_data(self):
    # TODO(charliemooney): This only lists the messages we've seen so far, it
    # would probably be good to include *all* the finger messages too for any
    # future platforms that might use things like ABS_MT_ORIENTATION, etc...
    return (self.is_ABS_MT_POSITION_X() or self.is_ABS_MT_POSITION_Y() or
            self.is_ABS_MT_PRESSURE())

  def _is_EV_KEY(self):
    """ Is this an EV_KEY event? """
    return self.event_type == EV_KEY

  def is_BTN_LEFT(self):
    """ Is this event BTN_LEFT? """
    return self._is_EV_KEY() and self.event_code == BTN_LEFT

  def is_BTN_LEFT_value(self, value):
    """ Is this event BTN_LEFT with value equal to the specified value? """
    return self.is_BTN_LEFT() and self.value == value

  def is_BTN_TOOL_FINGER(self):
    """ Is this event BTN_TOOL_FINGER? """
    return self._is_EV_KEY() and self.event_code == BTN_TOOL_FINGER

  def is_BTN_TOOL_DOUBLETAP(self):
    """ Is this event BTN_TOOL_DOUBLETAP? """
    return self._is_EV_KEY() and self.event_code == BTN_TOOL_DOUBLETAP

  def is_BTN_TOOL_TRIPLETAP(self):
    """ Is this event BTN_TOOL_TRIPLETAP? """
    return self._is_EV_KEY() and self.event_code == BTN_TOOL_TRIPLETAP

  def is_BTN_TOOL_QUADTAP(self):
    """ Is this event BTN_TOOL_QUADTAP? """
    return self._is_EV_KEY() and self.event_code == BTN_TOOL_QUADTAP

  def is_BTN_TOOL_QUINTTAP(self):
    """ Is this event BTN_TOOL_QUINTTAP? """
    return self._is_EV_KEY() and self.event_code == BTN_TOOL_QUINTTAP

  def is_BTN_TOUCH(self):
    """ Is this event BTN_TOUCH? """
    return self._is_EV_KEY() and self.event_code == BTN_TOUCH

  def is_SYN_REPORT(self):
    """ is this event is SYN_REPORT? """
    return self.event_type == EV_SYN

  def __str__(self):
    if self.is_SYN_REPORT():
      return '%0.5f\t-- SYN --' % self.timestamp
    return '%0.5f\t%s\t%s\t%d' % (self.timestamp, EV_TYPES[self.event_type],
                                  EV_STRINGS[self.event_type][self.event_code],
                                  self.value)
