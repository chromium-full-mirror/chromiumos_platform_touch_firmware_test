# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

MtbPacket = namedtuple('MtbPacket',
                       ['tid', 'slot', 'syn_time', 'x', 'y', 'pressure'])

class MtbStateMachine:
  """The state machine for MTB events.

  It traces the slots, tracking IDs, x coordinates, y coordinates, etc. If
  these values are not changed explicitly, the values are kept across events.

  Note that the kernel driver only reports what is changed. Due to its
  internal state machine, it is possible that either x or y in
  self.point[tid] is None initially even though the instance has been created.
  """
  def __init__(self):
    # Set the default slot to 0 as it may not be displayed in the MTB events
    #
    # Some abnormal event files may not display the tracking ID in the
    # beginning. To handle this situation, we need to initialize
    # the following variables:  slot_to_tid, point
    #
    # As an example, refer to the following event file which is one of
    # the golden samples with this problem.
    #   tests/data/stationary_finger_shift_with_2nd_finger_tap.dat
    self.tid = None
    self.slot = 0
    self.slot_to_tid = {self.slot: self.tid}
    self.x = {self.tid: None}
    self.y = {self.tid: None}
    self.pressure = {self.tid: None}
    self.syn_time = None
    self.new_tid = False
    self.number_fingers = 0
    self.leaving_slots = []

  def _del_leaving_slots(self):
    """ Delete the slots and tracking IDs for any leaving fingers """
    for slot in self.leaving_slots:
      del self.slot_to_tid[slot]
      self.number_fingers -= 1
    self.leaving_slots = []

  def _add_new_tracking_id(self, tid):
    """ Add a new tracking ID and slot of an arriving finger """
    self.tid = tid
    self.slot_to_tid[self.slot] = self.tid
    self.new_tid = True
    self.x = {self.tid: None}
    self.y = {self.tid: None}
    self.pressure[self.tid] = None
    self.number_fingers += 1

  def add_event(self, event):
    """ Update the internal states with the input MtbEvent  """
    self.new_tid = False

    # Switch the slot.
    if event.is_ABS_MT_SLOT():
      self.slot = event.value

    # Get a new tracking ID.
    elif event.is_new_contact():
      self._add_new_tracking_id(event.value)

    # A slot is leaving.
    # Do not delete this slot until this last packet is reported.
    elif event.is_finger_leaving():
      self.leaving_slots.append(self.slot)

    else:
      # Gracefully handle the case where we weren't given a tracking id
      # by using a default value for these mystery fingers
      if (not self.slot in self.slot_to_tid and event.is_finger_data()):
        self._add_new_tracking_id(999999)

      # Update x value.
      if event.is_ABS_MT_POSITION_X():
        self.x[self.slot_to_tid[self.slot]] = event.value

      # Update y value.
      elif event.is_ABS_MT_POSITION_Y():
        self.y[self.slot_to_tid[self.slot]] = event.value

      # Update z value (pressure)
      elif event.is_ABS_MT_PRESSURE():
        self.pressure[self.slot_to_tid[self.slot]] = event.value

      # Use the SYN_REPORT time as the packet time
      elif event.is_SYN_REPORT():
        self.syn_time = event.timestamp

  def get_current_data_for_all_tids(self, request_data_ready=True):
    """Get current packet's data including x, y, pressure, and
    the syn_time for all tids.

    @param request_data_ready: if set to true, it will not output
            current_tid_data until all data including x, y, pressure,
            syn_time, etc. in the packet have been assigned.
    """
    current_tid_data = []
    for slot, tid in self.slot_to_tid.items():
      x = self.x.get(tid)
      y = self.y.get(tid)
      pressure = self.pressure.get(tid)
      # Check if all attributes are non-None values.
      # Note: we cannot use
      #           all([all(point.value()), pressure, self.syn_time])
      #       E.g., for a point = (0, 300), it will return False
      #       which is not what we want. We want it to return False
      #       only when there are None values.
      data_ready = all(map(lambda e: e is not None,
                       [x, y, pressure, self.syn_time]))

      if (not request_data_ready) or data_ready:
        packet = MtbPacket(tid, slot, self.syn_time, x, y, pressure)
        current_tid_data.append(packet)

    self._del_leaving_slots()

    return sorted(current_tid_data)
