# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from event import MtbEvent
from state_machine import MtbStateMachine, MtbFinger, MtbSnapshot


def process(events):
  """ Given a list of raw MtbEvents, process them and return a list of
  MtbSnapshots.

  When raw MtbEvents are collected from the device, they're hard to work with.
  This function uses an MtbStateMachine to turn them into snapshot. This
  works by tracking the fingers' tracking ids, slots, x, y, pressure and noting
  each finger's state at the time of a SYN.  Essentially it takes a snapshot
  of the state of the pad at the time of each SYN event.
  """
  snapshots = []

  # initialize the state machine
  sm = MtbStateMachine()

  # Add the events as input to the state machine one after another
  for event in events:
    sm.add_event(event)

    # if it's not a SYN_REPORT, just keep going.  Each snapshot ends with SYN
    if not event.is_SYN_REPORT():
      continue

    snapshot = sm.get_current_snapshot()
    if snapshot:
      snapshots.append(snapshot)

  return snapshots


class SnapshotStream(object):
  """ This class bundles events into a snapshot stream in a real-time manner.
  """

  def __init__(self, device):
    self.sm = MtbStateMachine()
    self.device = device

  def Get(self):
    """ Get one snapshot at a time and its related events and leaving_slots. """
    events = []
    while True:
      event = self.device.NextEvent()
      events.append(str(event))
      self.sm.add_event(event)

      # Output the snapshot if a SYN_REPORT event is seen.
      if event.is_SYN_REPORT():
        leaving_slots = self.sm.leaving_slots
        snapshot = self.sm.get_current_snapshot()
        return (snapshot, events, leaving_slots)
