# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from input.linux_input import *

class MtEvent(object):
  """ Class that holds the a single MT event """

  LEAVING_TRACKING_ID = -1

  def __init__(self, timestamp, event_type=EV_SYN, event_code=None, value=None):
    self.timestamp = timestamp
    self.event_type = event_type
    self.event_code = event_code
    self.value = value

  def is_ABS_MT_TRACKING_ID(self):
    """ Is this event ABS_MT_TRACKING_ID? """
    return self.event_type == EV_ABS and self.event_code == ABS_MT_TRACKING_ID

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

  def is_ABS_MT_TOUCH_MAJOR(self):
    """ Is this event ABS_MT_TOUCH_MAJOR? """
    return self.event_type == EV_ABS and self.event_code == ABS_MT_TOUCH_MAJOR

  def _is_EV_KEY(self):
    """ Is this an EV_KEY event? """
    return self.event_type == EV_KEY

  def is_BTN_LEFT(self):
    """ Is this event BTN_LEFT? """
    return self._is_EV_KEY() and self.event_code == BTN_LEFT

  def is_SYN_MT_REPORT(self):
    """ is this event is SYN_REPORT? """
    return self.event_type == EV_SYN and self.event_code == SYN_MT_REPORT

  def is_SYN_REPORT(self):
    """ is this event is SYN_REPORT? """
    return self.event_type == EV_SYN and self.event_code == SYN_REPORT

  def __str__(self):
    if self.is_SYN_REPORT():
      return '%0.5f\t-- SYN --' % self.timestamp
    return '%0.5f\t%s\t%s\t%d' % (self.timestamp, EV_TYPES[self.event_type],
                                  EV_STRINGS[self.event_type][self.event_code],
                                  self.value)
