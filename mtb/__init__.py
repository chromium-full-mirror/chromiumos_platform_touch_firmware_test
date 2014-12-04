# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from event import MtbEvent
from state_machine import MtbStateMachine, MtbPacket


def packetize(events):
  """ Given a list of raw MtbEvents, packetize them and return the packets
  When raw MtbEvents are collected from the device, they're hard to work with.
  This function uses an MtbStateMachine to turn them into packets.  Packetizing
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

    # if it's not a SYN_REPORT, just keep going.  Each packet ends with SYN
    if not event.is_SYN_REPORT():
      continue

    snapshot = sm.get_current_data_for_all_tids()
    if snapshot:
      snapshots.append(snapshot)

  return snapshots
