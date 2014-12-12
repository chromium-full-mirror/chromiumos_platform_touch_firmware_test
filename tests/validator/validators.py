# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Validators to verify if events conform to specified criteria."""


import math
import numpy as np
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

  def _Distance(self, p1, p2):
    return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)

  def _SegmentPath(self, path, start_and_end_percentage=0.1):
    """ Assuming that the path takes a roughly straight line, this function
    segments the packetss that are in the extreme ends of the line (by
    distance, not time or position in the array)  It then returns the three
    sectioned off segments (start, middle, end)
    """
    start = path[0]
    end = path[-1]
    total_distance = self._Distance(start, end)
    trim_distance = start_and_end_percentage * total_distance
    lo = hi = None
    for i, packet in enumerate(path):
      # If we haven't found the first packet yet, check if it's far enough away
      # from the start to not get trimmed.
      if lo is None:
        if self._Distance(packet, start) > trim_distance:
          lo = i
      # Otherwise see if this packet is too close to the end
      elif hi is None:
        if self._Distance(packet, end) < trim_distance:
          hi = i

    return path[:lo], path[lo:hi], path[hi:]

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

  def _TidOfNthFinger(self, finger_num, snapshots):
    """ Return the TID of the nth finger to touch the pad """
    tids_seen = set([])
    tids_to_check = []

    for snapshot in snapshots:
      for packet in snapshot:
        if packet.tid not in tids_seen:
          tids_seen.add(packet.tid)
          if len(tids_seen) > finger_num:
            return packet.tid

    # If there weren't enough fingers, return None
    return None

  def Validate(events):
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

  def Validate(self, snapshots):
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
    name = self.__class__.__name__
    super(ReportRateValidator, self).__init__(criteria_str, mf, name)

  def Validate(self, snapshots):
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
        distance_moved = self._Distance(packet, path[i - 1])
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
    name = self.__class__.__name__
    super(RangeValidator, self).__init__(criteria_str, mf, name)

  def Validate(self, snapshots):
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
    name = self.__class__.__name__
    super(NoGapValidator, self).__init__(criteria_str, mf, name)

  def Validate(self, snapshots):
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
      gaps = [self._Distance(path[i], path[i + 1])
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

    # If there were not enough gaps and we know nothing report an error
    if largest_gap_ratio < 0:
      largest_gap_ratio = float('inf')
      result.error = ('Error computing gap ratios.  Perhaps there were not '
                      'enough events collected.')
    result.observed = largest_gap_ratio
    result.score = self.fc.mf.grade(result.observed)
    return result


class LinearityValidator(BaseValidator):
  """ Validator to verify linearity based on x vs t and y vs t

  Example:
      To check the linearity of the line drawn by the first finger:
        LinearityValidator('<= 0.03, ~ +0.07', finger=0)
  """
  # Define the partial group size for calculating Mean Squared Error
  MSE_PARTIAL_GROUP_SIZE = 1

  def __init__(self, criteria_str, mf=None, finger=None):
    name = self.__class__.__name__
    name += ('Finger%d' % finger) if finger is not None else 'AllFingers'
    self.finger = finger
    super(LinearityValidator, self).__init__(criteria_str, mf, name)

  def _CalculateResiduals(self, line, times, values):
    """ Calculate the residuals for this time/value series against the line.

    @param line: The regression line of values vs time
    @param times: a list of times
    @param values: a list of the values corresponding to those times

    This method returns the list of residuals, where
        residual[i] = line[t_i] - v_i
    where t_i is an element in times and
          v_i is a corresponding element in values.

    We calculate the vertical distance (value distance) here because the
    horizontal axis (times) always represent the time instants, and the
    vertical axis (values) should be either the coordinates in x or y axis.
    """
    return [float(line(t) - v) for t, v in zip(times, values)]

  def _SimpleLinearRegression(self, times, values):
    """Calculate the simple linear regression line and returns the
    sum of squared residuals.

    @param times: the list of time instants
    @param values: the list of corresponding x or y coordinates

    It calculates the residuals (fitting errors) of the points at the
    specified segments against the computed simple linear regression line.

    Reference:
    - Simple linear regression:
      http://en.wikipedia.org/wiki/Simple_linear_regression
    - numpy.polyfit(): used to calculate the simple linear regression line.
      http://docs.scipy.org/doc/numpy/reference/generated/numpy.polyfit.html
    """
    # At least 2 points to determine a line.
    if len(times) < 2 or len(values) < 2:
      return []

    midsection_start = int(len(times) * 0.1)
    midsection_end = len(times) - midsection_start
    mid_segment_t = times[midsection_start:midsection_end]
    mid_segment_y = values[midsection_start:midsection_end]

    # Check to make sure there are enough samples to continue
    if len(mid_segment_t) <= 2 or len(mid_segment_y) <= 2:
      return []

    # Calculate the simple linear regression line.
    degree = 1
    regress_line = np.poly1d(np.polyfit(mid_segment_t, mid_segment_y, degree))

    # Compute the fitting errors of the specified segments.
    return self._CalculateResiduals(regress_line, mid_segment_t, mid_segment_y)

  def _ErrorsForSingleAxis(self, times, values):
    """ Calculate linearity errors for one set of data points vs time """
    # It is fine if axis-time is a horizontal line.
    errors_px = self._SimpleLinearRegression(times, values)
    if not errors_px:
      return (0, 0)

    # Calculate the max errors
    max_err_px = max(map(abs, errors_px))

    # Calculate the root mean square errors
    e2 = [e * e for e in errors_px]
    rms_err_px = (float(sum(e2)) / len(e2)) ** 0.5

    return (max_err_px, rms_err_px)

  def Validate(self, snapshots):
    """ Check if the packets conforms to specified criteria. """
    paths_by_tid = self._SeparateByTid(snapshots)
    tids_to_check = paths_by_tid.keys()
    if self.finger is not None:
      tid = self._TidOfNthFinger(self.finger, snapshots)
      tids_to_check = [tid] if tid is not None else []

    max_err = float('-inf')
    for tid in tids_to_check:
      start, middle, end = self._SegmentPath(paths_by_tid[tid])
      path = middle

      ys = [y for tid, slot, ts, x, y, pressure in path]
      xs = [x for tid, slot, ts, x, y, pressure in path]
      times = [ts for tid, slot, ts, x, y, pressure in path]

      max_err_x, rms_err_x = self._ErrorsForSingleAxis(times, xs)
      max_err = max(max_err, max_err_x)

      max_err_y, rms_err_y = self._ErrorsForSingleAxis(times, ys)
      max_err = max(max_err, max_err_y)

    result = Result()
    result.name = self.name
    result.criteria = self.criteria_str
    if max_err < 0:
      max_err = float('inf')
      if not tids_to_check and self.finger is not None:
        result.error = ('There was no finger #%d as far as we can tell.' %
                        self.finger)
      else:
        result.error = ('Unable to compute linearity.  Perhaps there were '
                        'not enough events collected.')
    result.observed = max_err
    result.score = self.fc.mf.grade(result.observed)
    return result


class StationaryValidator(BaseValidator):
  """ Validator to make sure a finger we expect to remain still didn't move.

  This class is inherited by both StationaryFingerValidator and
  StationaryTapValidator, and is not used directly as a validator.
  """
  def __init__(self, criteria, mf=None, finger=None):
    name = self.__class__.__name__
    super(StationaryValidator, self).__init__(criteria, mf, name)
    self.finger = finger

  def Validate(self, snapshots):
    """ Check the moving distance of the specified finger. """
    paths_by_tid = self._SeparateByTid(snapshots)
    tids_to_check = paths_by_tid.keys()
    if self.finger is not None:
      tid = self._TidOfNthFinger(self.finger, snapshots)
      tids_to_check = [tid] if tid is not None else []

    max_distance = float('-inf')
    for tid in tids_to_check:
      for p1 in paths_by_tid[tid]:
        for p2 in paths_by_tid[tid]:
          max_distance = max(max_distance, self._Distance(p1, p2))

    result = Result()
    result.name = self.name
    result.criteria = self.criteria_str
    if max_distance < 0:
      max_distance = float('inf')
      if not tids_to_check:
        result.error = ('There was no finger #%d as far as we can tell.' %
                        self.finger)
      else:
        result.error = ('Unable to compute distances.  Perhaps there were '
                        'not enough events collected.')
    result.observed = max_distance
    result.score = self.fc.mf.grade(result.observed)
    return result


class StationaryFingerValidator(StationaryValidator):
  """ Validator to check for "pulling" effects by another finger.

  Example:
      To verify if the specified stationary finger is not pulled away more
      than 1.0 mm by another finger.
        StationaryFingerValidator('<= 1.0')
  """
  pass


class StationaryTapValidator(StationaryValidator):
  """ Validator to check the wobble of taps and clicks.

  Example:
      To verify if the first tapping finger specified does not wobble larger
      than 1.0 mm.
        StationaryTapValidator('<= 1.0', finger=0)
  """
  pass


class NoReversedMotionValidator(BaseValidator):
  """ Validator to measure any reversed motion detected

  Example:
      To measure the reversed motion for the first finger:
      NoReversedMotionValidator('== 0, ~ +20', finger=0)
  """
  # We will want to check different portions of the line for reversed motions.
  # These values indication which section of the line we want to check
  MIDDLE = 'middle'
  ENDS = 'ends'

  RATIO_CUTOFF = 3.0

  def __init__(self, criteria_str, mf=None, finger=None, section=None):
    name = self.__class__.__name__
    super(NoReversedMotionValidator, self).__init__(criteria_str, mf, name)
    self.finger = finger
    self.section = section

  def _GetReversedGaps(self, path):
    """ Measure any reversed motion (opposed to the general direction) """
    # Measure the x/y gaps between packets
    dxs = [path[i + 1].x - path[i].x for i in range(len(path) - 1)]
    dys = [path[i + 1].y - path[i].y for i in range(len(path) - 1)]

    # Measure the gaps in all directions
    left_gaps = [gap for gap in dxs if gap < 0]
    right_gaps = [gap for gap in dxs if gap > 0]
    if len(right_gaps) > 0:
      left_to_right_ratio = float(len(left_gaps)) / float(len(right_gaps))
    else:
      left_to_right_ratio = float('inf')
    x_moving = (left_to_right_ratio > self.RATIO_CUTOFF or
                left_to_right_ratio < (1.0 / self.RATIO_CUTOFF))

    up_gaps = [gap for gap in dys if gap < 0]
    down_gaps = [gap for gap in dys if gap > 0]
    if len(down_gaps) > 0:
      up_to_down_ratio = float(len(up_gaps)) / float(len(down_gaps))
    else:
      up_to_down_ratio = float('inf')
    y_moving = (up_to_down_ratio > self.RATIO_CUTOFF or
                up_to_down_ratio < (1.0 / self.RATIO_CUTOFF))

    # Check which directions the line is drawing in.
    reversed_gaps = []
    if x_moving:
      reversed_gaps.extend(left_gaps if left_to_right_ratio < 1.0
                           else right_gaps)
    if y_moving:
      reversed_gaps.extend(up_gaps if up_to_down_ratio < 1.0 else down_gaps)

    return reversed_gaps

  def Validate(self, snapshots):
    """ All X/Y values should be monotonic in the selected section of line. """
    # First, find the paths for each of the fingers we are supposed to check
    paths_by_tid = self._SeparateByTid(snapshots)
    tids_to_check = paths_by_tid.keys()
    if self.finger is not None:
      tid = self._TidOfNthFinger(self.finger, snapshots)
      tids_to_check = [tid] if tid is not None else []

    # For each finger, compute the total reversed distance and sum them
    reversed_total = 0
    for tid in tids_to_check:
      paths = [paths_by_tid[tid]]
      if self.section:
        start, middle, end = self._SegmentPath(paths_by_tid[tid])
        if self.section == self.MIDDLE:
          paths = [middle]
        elif self.section == self.ENDS:
          paths = [start, end]

      for path in paths:
        reversed_gaps = self._GetReversedGaps(path)
        reversed_total += sum([abs(gap) for gap in reversed_gaps])

    # Build a result object and return the results of the validator
    result = Result()
    result.name = self.name
    result.criteria = self.criteria_str
    if not tids_to_check:
      reversed_total = float('inf')
      if len(snapshots) == 0 or not self.finger:
        result.error = 'No events were collected, unable to validate'
      else:
        result.error = ('There was no finger #%d as far as we can tell.' %
                        self.finger)
    result.observed = reversed_total
    result.score = self.fc.mf.grade(result.observed)
    return result


class NoReversedMotionMiddleValidator(NoReversedMotionValidator):
  def __init__(self, criteria_str, mf=None, finger=None):
    super(NoReversedMotionMiddleValidator, self).__init__(
                                          criteria_str, mf, finger, self.MIDDLE)

class NoReversedMotionEndsValidator(NoReversedMotionValidator):
  def __init__(self, criteria_str, mf=None, finger=None):
    super(NoReversedMotionEndsValidator, self).__init__(
                                          criteria_str, mf, finger, self.ENDS)
class CountPacketsValidator(BaseValidator):
  """ Validator to check that there is a sufficient number of packets for
  each finger that is seen.

  Example:
      To verify if there are at least 3 packets for each finger:
        CountPacketsValidator('>= 3, ~ -3')
  """

  def __init__(self, criteria_str, mf=None):
    name = self.__class__.__name__
    super(CountPacketsValidator, self).__init__(criteria_str, mf, name)

  def Validate(self, snapshots):
    """ Check the number of packets for each finger """
    # Find how many packets arrived for each tracking ID
    paths_by_tid = self._SeparateByTid(snapshots)
    packet_counts = [len(path) for path in paths_by_tid.values()]

    # Build a result object and return the results of the validator
    # Use whichever finger had the *least* packets as the result
    result = Result()
    result.name = self.name
    result.criteria = self.criteria_str
    if not packet_counts:
      result.observed = float(0)
      result.score = self.fc.mf.grade(result.observed)
      result.error = 'No events were collected for ANY fingers.'
    else:
      result.observed = min(packet_counts)
      result.score = self.fc.mf.grade(result.observed)
    return result
