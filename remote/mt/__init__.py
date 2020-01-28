# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from .event import MtEvent
from .state_machine import *


MTA = 'mta'
MTB = 'mtb'
STYLUS = 'stylus'


class SnapshotStream(object):
  """ This class bundles events into a snapshot stream in a real-time manner.
  """

  def __init__(self, device, protocol=MTB):
    self.sm = MtbStateMachine()
    if protocol == MTA:
        self.sm = MtaStateMachine()
    elif protocol == STYLUS:
        self.sm = StylusStateMachine()

    self.device = device

  def Get(self):
    """ Get one snapshot at a time and its related events and leaving_slots. """
    events = []
    while True:
      event = self.device.NextEvent()
      # If the event is None, it probably means that the event_stream_process
      # was terminated.
      if not event:
        return (None, events, None)
      events.append(str(event))
      self.sm.add_event(event)

      # Output the snapshot if a SYN_REPORT event is seen.
      if event.is_SYN_REPORT():
        leaving_slots = self.sm.leaving_slots
        snapshot = self.sm.get_current_snapshot()
        return (snapshot, events, leaving_slots)
