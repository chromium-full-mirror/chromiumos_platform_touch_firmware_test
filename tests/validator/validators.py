# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Validators to verify if events conform to specified criteria."""


import math
import sys

import fuzzy
import mtb

from result import Result
from inspect import isfunction


class BaseValidator(object):
  """ Base class for validators.
  This class defines the basic interface and functionality for a Validator.
  Any actual Validators should be have BaseValidator as a superclass and will
  be used with the following workflow:
      # TODO(charliemooney): Fill this in
  """
  _device = None

  def __init__(self, criteria, mf=None, name=None):
    self.criteria_str = criteria() if isfunction(criteria) else criteria
    self.fc = fuzzy.FuzzyCriteria(self.criteria_str, mf=mf)
    self.name = name

  def _distance(self, p1, p2):
    return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)

  def _SeparateByTid(self, snapshots):
    """ Given all the snapshots of some gesture, separate the packets by tid
    This takes in a list of snapshots (each is a list of packets from
    different fingers) and outputs a dictionary mapping tids to a list of
    only their packets (in order).
    """
    # First find all the TIDs that are present in the snapshots
    tids = set([])
    for packets in snapshots:
      tids = tids.union(set([(tid) for tid, _, _, _, _, _ in packets]))

    # Then separate the packets by TID
    paths = {}
    for tid in tids:
      path = []
      for packets in snapshots:
        for packet in packets:
          if packet.tid == tid:
            path.append(packet)
      paths[tid] = path

    return paths

    def validate(events):
      raise NotImplementedError('Not implemented in subclass.')


class CountTrackingIDValidator(BaseValidator):
  """ Validator to check the number of tracking IDs observed.

  Example:
      To verify if there is exactly one finger observed:
        CountTrackingIDValidator('== 1')
  """
  def __init__(self, criteria_str, mf=None):
    name = self.__class__.__name__
    super(CountTrackingIDValidator, self).__init__(criteria_str, mf, name)

  def validate(self, snapshots):
    paths_by_tid = self._SeparateByTid(snapshots)
    observed_num_tids = len(paths_by_tid)

    result = Result()
    result.name = self.name
    result.criteria = self.criteria_str
    result.observed = observed_num_tids
    result.score = self.fc.mf.grade(result.observed)
    return result


class ReportRateValidator(BaseValidator):
  """ Validator to check the report rate.

  Example:
      To verify that the report rate is around 80 Hz. It gets 0 points
      if the report rate drops below 60 Hz.
        ReportRateValidator('== 80 ~ -20')
  """
  MIN_MOVING_DISTANCE_PX = 4

  def __init__(self, criteria_str, mf=None):
    self.name = self.__class__.__name__
    super(ReportRateValidator, self).__init__(criteria_str, mf, self.name)

  def validate(self, snapshots):
    """ Check that during any period on movement each finger has a high
    enough report rate.
    """
    # First separate out each finger by itself.
    paths_by_tid = self._SeparateByTid(snapshots)

    # If a finger isn't moving, its report rate may drop due to the MTB delta
    # compression.  Any time the finger's x/y isn't changing much between two
    # packets, we should ignore that time delta.
    moving_segments = []
    for path in paths_by_tid.values():
      start = 0
      for i, packet in enumerate(path):
        if i == 0:
          continue
        distance_moved = self._distance(packet, path[i - 1])
        if distance_moved >  ReportRateValidator.MIN_MOVING_DISTANCE_PX:
          continue
        if start != i - 1:
          moving_segments.append(path[start:i])
        start = i
      moving_segments.append(path[start:])

    # Compute the time deltas between consecutive packets for each finger
    deltas = []
    for segment in moving_segments:
      times = [ts for tid, slot, ts, x, y, pressure in segment]
      deltas.extend([times[i] - times[i - 1] for i in range(1, len(times))])

    # The average time delta between events during moving periods can be used
    # to calculate an average report rate
    observed_report_rate = -1
    if deltas:
      avg_delta = sum(deltas) / len(deltas)
      observed_report_rate = 1.0 / avg_delta

    # Finally package up the result and return it for the closest edge
    result = Result()
    result.name = self.name
    result.criteria = self.criteria_str
    result.observed = observed_report_rate
    result.score = self.fc.mf.grade(result.observed)
    if result.observed == -1:
      result.error = ('No usable events were collected. ' +
                      'Make sure the finger is moving during the test.')
    return result


class RangeValidator(BaseValidator):
  """ A Validator to check the range of observed (x, y) positions.
  This Validator checks the ranges of the x and y positions reported and
  confirms that they all fall within the min/max values we expect.

  Example:
      To check the range of observed edge-to-edge positions:
        RangeValidator('<= 0.05, ~ +0.05')
  """

  def __init__(self, criteria_str, mf=None):
    self.name = self.__class__.__name__
    super(RangeValidator, self).__init__(criteria_str, mf, self.name)

  def validate(self, snapshots):
    """ Check to see the range of X/Y values reported and make sure they're
    within what we expect for this device.
    """
    # Find the extreme X/Y values that have been reported
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    for snapshot in snapshots:
      for packet in snapshot:
        tid, slot, ts, x, y, pressure = packet
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)

    # We should be able to guess the direction based on which edge was close
    right_gap = BaseValidator._device.width - max_x
    bottom_gap = BaseValidator._device.height - max_y
    min_gap = float('inf')
    detected_direction = None
    for gap, direction in [(min_x, 'Left'), (min_y, 'Top'),
                           (right_gap, 'Right'), (bottom_gap, 'Bottom')]:
      if abs(gap) < abs(min_gap):
        min_gap = gap
        detected_direction = direction

    # Finally package up the result and return it for the closest edge
    result = Result()
    result.observed = min_gap
    result.criteria = self.criteria_str
    result.score = self.fc.mf.grade(result.observed)

    if detected_direction:
      result.name = self.name + detected_direction
    else:
      result.name = self.name
      result.error = ('Unable to detect which edge was being tested.  ' +
                      'Probably not enough events were collected.')
    return result

class NoGapValidator(BaseValidator):
  """ Validator to make sure that there are no significant gaps in a line.

  Example:
      To verify that no gap is more than 5x the size of the previous one
        NoGapValidator('<= 5, ~ +5')
  """

  def __init__(self, criteria_str, mf=None):
    self.name = self.__class__.__name__
    super(NoGapValidator, self).__init__(criteria_str, mf, self.name)

  def validate(self, snapshots):
    """ Compute the ratio of the distances between events and grade that

    This function tries to find the largest gap ratio between two gaps
    with the restriction that next gap is somewhat smaller. The ratio threshold
    is used to prevent the gaps detected in a swipe. In a swipe, the gaps tend
    to become larger and larger.  If the next gap is smaller we can assume
    that this wasn't an accelerating finger, but rather that there was a
    glitch in the reports.
    """
    RATIO_THRESHOLD_CURR_GAP_TO_NEXT_GAP = 1.2
    GAP_LOWER_BOUND = 10

    paths_by_tid = self._SeparateByTid(snapshots)
    largest_gap_ratio = float('-inf')

    for path in paths_by_tid.values():
      gaps = [self._distance(path[i], path[i + 1])
              for i in range(len(path) - 1)]

    for i in range(1, len(gaps) - 1):
      prev_gap = max(gaps[i - 1], 1)
      curr_gap = gaps[i]
      next_gap = max(gaps[i + 1], 1)
      gap_ratio_with_prev = curr_gap / prev_gap
      gap_ratio_with_next = curr_gap / next_gap
      if (curr_gap >= GAP_LOWER_BOUND and
        gap_ratio_with_prev > largest_gap_ratio and
        gap_ratio_with_next > RATIO_THRESHOLD_CURR_GAP_TO_NEXT_GAP):
        largest_gap_ratio = gap_ratio_with_prev

    result = Result()
    result.name = self.name
    result.criteria = self.criteria_str
    result.observed = largest_gap_ratio
    result.score = self.fc.mf.grade(result.observed)
    return result
