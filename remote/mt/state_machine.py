# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from collections import namedtuple
from .event import MtEvent, EV_ABS, ABS_MT_TRACKING_ID, MT_TOOL_PALM

MtFinger = namedtuple('MtFinger', ['tid', 'syn_time', 'x', 'y', 'pressure',\
                                   'tilt_x', 'tilt_y', 'touch_major',\
                                   'touch_minor'])
MtSnapshot = namedtuple('MtSnapshot', ['syn_time', 'button_pressed',
                                       'fingers', 'raw_events'])

class MtStateMachine(object):
  """ This is an abstract base class that defines the interface of a multitouch
  state machine.  This class should never be instantiated directly, but rather
  any actual state machines should derive from this class to guarantee that it
  conforms to the same interfaces.
  """
  PRESSURE_FROM_MT_PRESSURE = 'from_mt_pressure'
  PRESSURE_FROM_MT_TOUCH_MAJOR = 'from_mt_touch_major'
  PRESSURE_FROM_NOWHERE = 'from_nowhere'
  PRESSURE_SOURCES = [PRESSURE_FROM_MT_PRESSURE, PRESSURE_FROM_MT_TOUCH_MAJOR,
                      PRESSURE_FROM_NOWHERE]

  def __init__(self, pressure_src):
    """ Setup the parts of the state machine that are uniform across all MT
    protocol state machines.

    Currently this is only one option: pressure source.  This tells the state
    machine where to get the "pressure" readings from.  While, the default
    way is to use MT_PRESSURE messages, some touchpads/screens use the
    MT_TOUCH_MAJOR message instead or do not report it at all.  This parameter
    allows you to specify which you want the state machine to use.
    """
    if pressure_src not in MtStateMachine.PRESSURE_SOURCES:
      raise ValueError('The pressure source "%s" is not valid.')
    self.pressure_src = pressure_src

  def add_event(self, event):
    raise NotImplementedError('Error: add_event() not implemented.')

  def get_current_snapshot(self, request_data_ready=True):
    raise NotImplementedError('Error: get_current_snapshot() not implemented.')


class MtaStateMachine(MtStateMachine):
  """ The state machine for MTA events

  This class accepts MtEvents via the add_event() member function and maintains
  the state that an MTA system would.  MTA is slightly different than MTB, but
  uses similar events.  Without delta compression, MTA can get rid of the
  concept of slots, since all the finger data is reported before each SYN_REPORT
  and the fingers themselves are separated byt SYN_MT_REPORTS instead of a
  new SLOT.

  Note that because our system expects new fingers to have new TIDs and in MTA
  this is not the case (they reuse TIDs all the time) the MtaStateMachine
  keeps track of which TIDs have already been used and remaps them when
  it detects a repeated TID to an unused value to maintain transparency
  between MTB and MTA.
  """
  def __init__(self, pressure_src=MtStateMachine.PRESSURE_FROM_MT_PRESSURE):
    # This dictionary maps the raw (non-unique) tids reported in the events to
    # new (unique) tids so we can easily differentiate any two fingers even if
    # there is a gap of time inbetween them.
    self.tid_mappings = {}
    self.next_unique_tid = 0

    self.button_pressed = False
    self.last_snapshot = None

    self._clear()

    MtStateMachine.__init__(self, pressure_src)

  def _clear(self):
    # Clear out the state for the current fingers
    self.fingers_data = []
    self.raw_events_since_last_syn = []
    self.tid = self.x = self.y = self.pressure = self.touch_major \
        = self.touch_minor = None

  def add_event(self, event):
    self.raw_events_since_last_syn.append(event)

    # If this is the end of the information for all the fingers for this report
    if event.is_SYN_REPORT():
      # First build up the snapshot
      fingers = []
      for tid, x, y, p, touch_major, touch_minor in self.fingers_data:
        mapped_tid = self.tid_mappings[tid]
        fingers.append(MtFinger(mapped_tid, event.timestamp, x, y,
                                p, 0, 0, touch_major, touch_minor))
      self.last_snapshot = MtSnapshot(event.timestamp, self.button_pressed,
                                      fingers, self.raw_events_since_last_syn)

      # Delete the tid mappings for any leaving fingers
      # Find all the raw tids that have currently been reported
      raw_tids_used = set([raw_tid for raw_tid, _, _, _ in self.fingers_data])
      # Detect any mappings that are for fingers no longer on the pad
      leaving_raw_tids = [raw_tid for raw_tid in self.tid_mappings
                          if raw_tid not in raw_tids_used]
      # Remove those out-dated mappings from the mapping dictionary
      for raw_tid in leaving_raw_tids:
        del self.tid_mappings[raw_tid]

      # Then clear out the fingers_data since this starts a new snapshot
      self._clear()

    # If this is the end of a finger's information stash all the data about it
    # until the end of the data for all the fingers
    elif event.is_SYN_MT_REPORT():
      if self.pressure_src == MtStateMachine.PRESSURE_FROM_MT_TOUCH_MAJOR:
        pressure = self.touch_major
      elif self.pressure_src == MtStateMachine.PRESSURE_FROM_NOWHERE:
        pressure = 1
      else:
        pressure = self.pressure

      if all([v is not None for v in (self.tid, self.x, self.y, pressure)]):
        touch_major = 0
        touch_minor = 0
        if self.touch_major is not None:
          touch_major = self.touch_major
        if self.touch_minor is not None:
          touch_minor = self.touch_minor
        self.fingers_data.append((self.tid, self.x, self.y, pressure,\
                                  touch_major, touch_minor))

    # Otherwise, check what information it's giving us and store it
    elif event.is_ABS_MT_TRACKING_ID():
      self.tid = event.value
      if self.tid not in self.tid_mappings:
        self.tid_mappings[self.tid] = self.next_unique_tid
        self.next_unique_tid += 1
    elif event.is_ABS_MT_POSITION_X():
      self.x = event.value
    elif event.is_ABS_MT_POSITION_Y():
      self.y = event.value
    elif event.is_ABS_MT_PRESSURE():
      self.pressure = event.value
    elif event.is_ABS_MT_TOUCH_MAJOR():
      self.touch_major = event.value
    elif event.is_ABS_MT_TOUCH_MINOR():
      self.touch_minor = event.value
    elif event.is_BTN_LEFT():
      self.button_pressed = (event.value == 1)

  def get_current_snapshot(self, request_data_ready=True):
    return self.last_snapshot


class MtbStateMachine(MtStateMachine):
  """ The state machine for MTB events.

  It traces the slots, tracking IDs, x coordinates, y coordinates, etc. If
  these values are not changed explicitly, the values are kept across events.

  Note that the kernel driver only reports what is changed. Due to its
  internal state machine, it is possible that either x or y in
  self.point[tid] is None initially even though the instance has been created.
  """
  DUMMY_TRACKING_ID = 999999

  def __init__(self, pressure_src=MtStateMachine.PRESSURE_FROM_MT_PRESSURE):
    # Set the default slot to 0 as it may not be displayed in the MT events
    #
    # Some abnormal event files may not display the tracking ID in the
    # beginning. To handle this situation, we need to initialize
    # the following variables:  slot_to_tid, point
    #
    # As an example, refer to the following event file which is one of
    # the golden samples with this problem.
    #   tests/data/stationary_finger_shift_with_2nd_finger_tap.dat
    self.slot = 0
    self.slots_in_use = set()
    self.tid = {}
    self.x = {}
    self.y = {}
    self.distance = {}
    self.pressure = {}
    self.touch_major = {}
    self.touch_minor = {}
    self.tool_type = {}
    self.palm_tids = set()
    self.syn_time = None
    self.leaving_slots = []
    self.button_pressed = False
    self.raw_events_since_last_syn = []
    self.last_snapshot = None
    self.is_first_event = True

    MtStateMachine.__init__(self, pressure_src)

  def add_event(self, event):
    """ Update the internal states with the input MtEvent  """
    if self.is_first_event and not event.is_ABS_MT_TRACKING_ID():
      self.add_event(MtEvent(event.timestamp,
                             EV_ABS, ABS_MT_TRACKING_ID,
                             MtbStateMachine.DUMMY_TRACKING_ID))
    self.is_first_event = False


    self.raw_events_since_last_syn.append(event)

    # Note: The physical click button is not associated with any finger/slot
    if event.is_BTN_LEFT():
      self.button_pressed = (event.value == 1)

    # Handle all the finger-related updates below here
    # Switch the slot.
    elif event.is_ABS_MT_SLOT():
      self.slot = event.value

    # Update tracking ID, noting if the slot is no longer used
    elif event.is_ABS_MT_TRACKING_ID():
      self.tid[self.slot] = event.value
      if event.value == MtEvent.LEAVING_TRACKING_ID:
        self.slots_in_use.discard(self.slot)
      else:
        self.slots_in_use.add(self.slot)

    # Update the x, y, pressure, etc values for a given slot
    elif event.is_ABS_MT_POSITION_X():
      self.x[self.slot] = event.value
    elif event.is_ABS_MT_POSITION_Y():
      self.y[self.slot] = event.value
    elif event.is_ABS_MT_PRESSURE():
      self.pressure[self.slot] = event.value
    elif event.is_ABS_MT_TOUCH_MAJOR():
      self.touch_major[self.slot] = event.value
    elif event.is_ABS_MT_TOUCH_MINOR():
      self.touch_minor[self.slot] = event.value
    elif event.is_ABS_MT_DISTANCE():
      self.distance[self.slot] = event.value
    elif event.is_ABS_MT_TOOL_TYPE():
      self.tool_type[self.slot] = event.value

    # Use the SYN_REPORT time as the snapshot time
    elif event.is_SYN_REPORT():
      self.syn_time = event.timestamp
      self.last_snapshot = self._build_current_snapshot()
      self.raw_events_since_last_syn = []

  def _build_current_snapshot(self):
    """Build current packet's data including x, y, pressure, and
    the syn_time for all tids.
    """
    current_fingers = []
    for slot in self.slots_in_use:
      tid = self.tid.get(slot, None)
      x = self.x.get(slot, None)
      y = self.y.get(slot, None)
      distance = self.distance.get(slot, None)
      major = self.touch_major.get(slot, 0)
      minor = self.touch_minor.get(slot, 0)
      tool_type = self.tool_type.get(slot, 0)

      # Skip any fingers that are hovering (they have a distance)
      if distance:
        continue

      # Skip any palm touches. A touch is considered as a palm if it has ever
      # been marked with TOOL_TYPE=MT_TOOL_PALM.
      if tool_type == MT_TOOL_PALM:
        self.palm_tids.add(tid)
        continue
      elif tid in self.palm_tids:
        continue

      if self.pressure_src == MtStateMachine.PRESSURE_FROM_MT_TOUCH_MAJOR:
        pressure = self.touch_major.get(slot, None)
      elif self.pressure_src == MtStateMachine.PRESSURE_FROM_NOWHERE:
        pressure = 1
      else:
        pressure = self.pressure.get(slot, None)

      data_ready = all([v is not None for v in
                        (x, y, pressure, tid, self.syn_time)])
      if data_ready:
        finger = MtFinger(tid, self.syn_time, x, y, pressure, 0, 0,
                          major, minor)
        current_fingers.append(finger)

    current_snapshot = MtSnapshot(self.syn_time, self.button_pressed,
                                  current_fingers,
                                  self.raw_events_since_last_syn)
    return current_snapshot

  def get_current_snapshot(self):
    return self.last_snapshot


class StylusStateMachine(MtStateMachine):
  """ State machine for parsing simplified stylus protocol.
  This only supports a single stylus, and ignores any hovering reports, just
  reporting snapshots when the stylus is touching the surface.
  """
  def __init__(self, pressure_src):
    self.x = self.y = self.p = self.last_snapshot = None
    self.tilt_x = self.tilt_y = None
    self.btn_touch = self.btn_tool_pen = self.is_hovering = False
    self.raw_events_since_last_syn = []
    self.last_report_was_empty = True
    MtStateMachine.__init__(self, pressure_src)

  def __update_hover_state(self):
      self.is_hovering = not self.btn_touch and self.btn_tool_pen

  def add_event(self, event):
    self.raw_events_since_last_syn.append(event)

    if event.is_ABS_X():
      self.x = event.value
    elif event.is_ABS_Y():
      self.y = event.value
    elif event.is_ABS_TILT_X():
      self.tilt_x = event.value
    elif event.is_ABS_TILT_Y():
      self.tilt_y = event.value
    elif event.is_ABS_PRESSURE():
      self.p = event.value
    elif event.is_BTN_TOUCH():
      self.btn_touch = (event.value == 1)
      self.__update_hover_state()
    elif event.is_BTN_TOOL_PEN():
      self.btn_tool_pen = (event.value == 1)
      self.__update_hover_state()
      if event.value == 0:
        self.x = self.y = self.p = None

    elif event.is_SYN_REPORT():
      current_fingers = None
      if self.btn_touch:
        current_fingers = [MtFinger(0, event.timestamp, self.x, self.y, self.p,
                                    self.tilt_x, self.tilt_y, 0, 0)]
        self.last_report_was_empty = False
      elif not self.last_report_was_empty:
        current_fingers = []
        self.last_report_was_empty = True

      if current_fingers is not None:
        self.last_snapshot = MtSnapshot(event.timestamp, False, current_fingers,
                                        self.raw_events_since_last_syn)
        self.raw_events_since_last_syn = []
      else:
        self.last_snapshot = None

  def get_current_snapshot(self, request_data_ready=True):
    return self.last_snapshot
