# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Validators to verify if events conform to specified criteria."""


import math
import numpy as np
import sys

import fuzzy

from inspect import isfunction
from result import Result

from minicircle import minicircle


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

  def _DistanceMm(self, p1, p2):
    p1_mm_x, p1_mm_y = BaseValidator._device.PxToMm((p1.x, p1.y))
    p2_mm_x, p2_mm_y = BaseValidator._device.PxToMm((p2.x, p2.y))
    return math.sqrt((p1_mm_x - p2_mm_x) ** 2 + (p1_mm_y - p2_mm_y) ** 2)

  def _SegmentPath(self, path, start_and_end_percentage=0.1):
    """ Assuming that the path takes a roughly straight line, this function
    segments the fingers that are in the extreme ends of the line (by
    distance, not time or position in the array)  It then returns the three
    sectioned off segments (start, middle, end)
    """
    start = path[0]
    end = path[-1]
    total_distance = self._Distance(start, end)
    trim_distance = start_and_end_percentage * total_distance
    lo = hi = None
    for i, finger in enumerate(path):
      # If we haven't found the first finger yet, check if it's far enough away
      # from the start to not get trimmed.
      if lo is None:
        if self._Distance(finger, start) > trim_distance:
          lo = i
      # Otherwise see if this finger is too close to the end
      elif hi is None:
        if self._Distance(finger, end) < trim_distance:
          hi = i

    return path[:lo], path[lo:hi], path[hi:]

  def _SeparatePaths(self, snapshots):
    """ Given all the snapshots of some gesture, separate the fingers into
    paths of contiguous events.  This takes in a list of MtbSnapshots and
    outputs list of "paths" which are themselves a list of MtFingers (in order).

    Note: Tracking IDs can be re-used if there is a gap between the events
    so it is not valid to simply separate events based on TID.  You have to
    check the order of events.
    """
    paths = []
    paths_in_progress = {}
    for snapshot in snapshots:
      for finger in snapshot.fingers:
        # Append this finger onto the right path and start a new path if needed
        if finger.tid not in paths_in_progress:
          paths_in_progress[finger.tid] = []
        paths_in_progress[finger.tid].append(finger)

      # Remove any terminated paths from the in-progress dicttionary
      tids = set([(finger.tid) for finger in snapshot.fingers])
      for tid, path in paths_in_progress.items():
        if tid not in tids:
          paths.append(path)
          del paths_in_progress[tid]

    # Make sure that the last finger(s) to leave the pad get counted, too
    for path in paths_in_progress.values():
      paths.append(path)
    return paths

  def _PathOfNthFinger(self, finger_num, paths):
    """ Return the path of the nth finger to touch the pad """
    if len(paths) <= finger_num:
      return []
    ordered_paths = sorted(paths, key=lambda path:path[0].syn_time)
    return [ordered_paths[finger_num]]

  def Validate(self, snapshots):
    raise NotImplementedError('Not implemented in subclass.')


class FingerCountValidator(BaseValidator):
  """ Validator to check the number of fingers observed.

  Example:
      To verify if there is exactly one finger observed:
        FingerCountValidator('== 1')
  """
  def __init__(self, criteria_str, mf=None):
    name = self.__class__.__name__
    super(FingerCountValidator, self).__init__(criteria_str, mf, name)

  def Validate(self, snapshots):
    paths = self._SeparatePaths(snapshots)
    observed_fingers = len(paths)

    result = Result()
    result.name = self.name
    result.units = '#'
    result.criteria = self.criteria_str
    result.observed = observed_fingers
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
    paths = self._SeparatePaths(snapshots)

    # If a finger isn't moving, its report rate may drop due to the MTB delta
    # compression.  Any time the finger's x/y isn't changing much between two
    # fingers, we should ignore that time delta.
    moving_segments = []
    for path in paths:
      start = 0
      for i, finger in enumerate(path):
        if i == 0:
          continue
        distance_moved = self._Distance(finger, path[i - 1])
        if distance_moved >  ReportRateValidator.MIN_MOVING_DISTANCE_PX:
          continue
        if start != i - 1:
          moving_segments.append(path[start:i])
        start = i
      moving_segments.append(path[start:])

    # Compute the time deltas between consecutive readings for each finger
    deltas = []
    for segment in moving_segments:
      times = [finger.syn_time for finger in segment]
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
    result.units = 'Hz'
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
      for finger in snapshot.fingers:
        min_x = min(min_x, finger.x)
        max_x = max(max_x, finger.x)
        min_y = min(min_y, finger.y)
        max_y = max(max_y, finger.y)

    # Convert those values to mm
    max_x_mm = BaseValidator._device.PxToMm_X(max_x)
    min_x_mm = BaseValidator._device.PxToMm_X(min_x)
    max_y_mm = BaseValidator._device.PxToMm_Y(max_y)
    min_y_mm = BaseValidator._device.PxToMm_Y(min_y)

    # Also convert the touch sensors dimensions to mm
    dev_min_x, dev_max_x = BaseValidator._device.RangeX()
    dev_min_y, dev_max_y = BaseValidator._device.RangeY()
    dev_min_x_mm = BaseValidator._device.PxToMm_X(dev_min_x)
    dev_max_x_mm = BaseValidator._device.PxToMm_X(dev_max_x)
    dev_min_y_mm = BaseValidator._device.PxToMm_Y(dev_min_y)
    dev_max_y_mm = BaseValidator._device.PxToMm_Y(dev_max_y)

    # We should be able to guess the direction based on which edge was close
    right_gap = dev_max_x_mm - max_x_mm
    left_gap = min_x_mm - dev_min_x_mm
    bottom_gap = dev_max_y_mm - max_y_mm
    top_gap = min_y_mm - dev_min_y_mm
    min_gap = float('inf')
    detected_direction = None
    for gap, direction in [(left_gap, 'Left'), (top_gap, 'Top'),
                           (right_gap, 'Right'), (bottom_gap, 'Bottom')]:
      if abs(gap) < abs(min_gap):
        min_gap = gap
        detected_direction = direction

    # Finally package up the result and return it for the closest edge
    result = Result()
    result.units = 'mm'
    result.criteria = self.criteria_str
    result.observed = min_gap
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

    paths = self._SeparatePaths(snapshots)
    largest_gap_ratio = float('-inf')

    for path in paths:
      gaps = [self._Distance(path[i], path[i + 1])
              for i in range(len(path) - 1)]

      for i in range(1, len(gaps) - 1):
        prev_gap = max(gaps[i - 1], 1)
        curr_gap = gaps[i]
        next_gap = max(gaps[i + 1], 1)
        gap_ratio_with_prev = curr_gap / prev_gap
        gap_ratio_with_next = curr_gap / next_gap
        if (curr_gap >= GAP_LOWER_BOUND and
            gap_ratio_with_next > RATIO_THRESHOLD_CURR_GAP_TO_NEXT_GAP):
          largest_gap_ratio = max(largest_gap_ratio, gap_ratio_with_prev)
        else:
          largest_gap_ratio = max(largest_gap_ratio, 1.0)

    result = Result()
    result.name = self.name
    result.units = '*ratio*'
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
    """ Check if the fingers conform to specified criteria. """
    paths = self._SeparatePaths(snapshots)
    if self.finger is not None:
      paths = self._PathOfNthFinger(self.finger, paths)

    max_err_mm = float('-inf')
    for path in paths:
      start, middle, end = self._SegmentPath(path)
      path = middle

      xs_mm = [BaseValidator._device.PxToMm_X(finger.x) for finger in path]
      ys_mm = [BaseValidator._device.PxToMm_Y(finger.y) for finger in path]
      times = [finger.syn_time for finger in path]

      max_err_x_mm, rms_err_x_mm = self._ErrorsForSingleAxis(times, xs_mm)
      max_err_mm = max(max_err_mm, max_err_x_mm)

      max_err_y_mm, rms_err_y_mm = self._ErrorsForSingleAxis(times, ys_mm)
      max_err_mm = max(max_err_mm, max_err_y_mm)

    result = Result()
    result.name = self.name
    result.units = 'mm'
    result.criteria = self.criteria_str
    if max_err_mm < 0:
      max_err_mm = float('inf')
      if not paths and self.finger is not None:
        result.error = ('There was no finger #%d as far as we can tell.' %
                        self.finger)
      else:
        result.error = ('Unable to compute linearity.  Perhaps there were '
                        'not enough events collected.')
    result.observed = max_err_mm
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
    paths = self._SeparatePaths(snapshots)
    if self.finger is not None:
      paths = self._PathOfNthFinger(self.finger, paths)

    max_distance = float('-inf')
    for path in paths:
      for p1 in path:
        for p2 in path:
          max_distance = max(max_distance, self._DistanceMm(p1, p2))

    result = Result()
    result.name = self.name
    result.units = 'mm'
    result.criteria = self.criteria_str
    if max_distance < 0:
      max_distance = float('inf')
      if not paths:
        if self.finger is None:
          result.error = ('There were not enough events recorded.')
        else:
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
    To verify that there is no more than 5mm of reversed motion for the first
    finger on the pad:
      NoReversedMotionValidator('<= 5', finger=0)
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
    # Measure the x/y gaps between finger readings
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
      x_reversed_gaps = left_gaps if left_to_right_ratio < 1.0 else right_gaps
      x_reversed_gaps_mm = [BaseValidator._device.PxToMm_X(gap)
                            for gap in x_reversed_gaps]
      reversed_gaps.extend(x_reversed_gaps_mm)
    if y_moving:
      y_reversed_gaps = up_gaps if up_to_down_ratio < 1.0 else down_gaps
      y_reversed_gaps_mm = [BaseValidator._device.PxToMm_Y(gap)
                            for gap in y_reversed_gaps]
      reversed_gaps.extend(y_reversed_gaps_mm)

    return reversed_gaps

  def Validate(self, snapshots):
    """ All X/Y values should be monotonic in the selected section of line. """
    # First, find the paths for each of the fingers we are supposed to check
    paths = self._SeparatePaths(snapshots)
    if self.finger is not None:
      paths = self._PathOfNthFinger(self.finger, paths)

    # For each finger, compute the total reversed distance and sum them
    reversed_total = 0
    for path in paths:
      sections_to_process = [path]
      if self.section:
        start, middle, end = self._SegmentPath(path)
        if self.section == self.MIDDLE:
          sections_to_process = [middle]
        elif self.section == self.ENDS:
          sections_to_process = [start, end]

      for section_to_process in sections_to_process:
        reversed_gaps = self._GetReversedGaps(section_to_process)
        reversed_total += sum([abs(gap) for gap in reversed_gaps])

    # Build a result object and return the results of the validator
    result = Result()
    result.name = self.name
    result.units = 'mm'
    result.criteria = self.criteria_str
    if not paths:
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
  """ Validator to check that there is a sufficient number of readings for
  each finger that is seen.

  Example:
      To verify if there are at least 3 readings for each finger:
        CountPacketsValidator('>= 3, ~ -3')
  """

  def __init__(self, criteria_str, mf=None):
    name = self.__class__.__name__
    super(CountPacketsValidator, self).__init__(criteria_str, mf, name)

  def Validate(self, snapshots):
    """ Check the number of readings for each finger """
    # Find how many readings arrived for each tracking ID
    paths = self._SeparatePaths(snapshots)
    reading_counts = [len(path) for path in paths]

    # Build a result object and return the results of the validator
    # Use whichever finger had the *least* readings as the result
    result = Result()
    result.name = self.name
    result.units = '#'
    result.criteria = self.criteria_str
    if not reading_counts:
      result.observed = float(0)
      result.score = self.fc.mf.grade(result.observed)
      result.error = 'No events were collected for ANY fingers.'
    else:
      result.observed = min(reading_counts)
      result.score = self.fc.mf.grade(result.observed)
    return result


class PinchValidator(BaseValidator):
  """ Validator to check that a pinch zoomed in/out.

  Example:
    To verify that the two fingers' relative distances changes by at least 15mm
        PinchValidator('>= 15, ~ -5')
  """

  def __init__(self, criteria_str, mf=None, device=None):
    name = self.__class__.__name__
    super(PinchValidator, self).__init__(criteria_str, mf, name)

  def Validate(self, snapshots):
    """ Check the relative direction of two fingers """
    paths = self._SeparatePaths(snapshots)
    if len(paths) > 2:
      # If more than 2 fingers are observed, use the two with the most readings.
      # It's likely that the extras are stray touches
      paths = sorted(paths, key=lambda x:len(x))[-2:]

    relative_motion = 0
    if len(paths) == 2:
      starting_distance = self._DistanceMm(paths[0][0], paths[1][0])
      ending_distance = self._DistanceMm(paths[0][-1], paths[1][-1])
      relative_motion = ending_distance - starting_distance

    result = Result()
    result.name = self.name
    result.units = 'mm'
    result.criteria = self.criteria_str
    result.observed = abs(relative_motion)
    result.score = self.fc.mf.grade(result.observed)
    if len(paths) < 2:
      result.error = 'Not enough fingers seen.  Must have 2 for a pinch/zoom.'
    elif len(paths) > 2:
      result.error = 'Too many fingers seen.  Must have 2 for a pinch/zoom.'
    return result


class DrumrollValidator(BaseValidator):
  """ Validator to check that two fingers are separated during a drumroll
  All points from the same finger should be within 2 circles of a given radius

  Essentially the issue this is checking for is that when two fingers are
  tapping in quick succession, it's not uncommon for the pad to give them the
  same tracking ID.  Worse yet, some pads will actually interpolate a few
  points in between the fingers to make up for the movement it "missed."

  Example:
      To verify that the max radius of all minimal enclosing circles generated
      by alternately tapping the index and middle fingers is within 2.0 mm.
        DrumrollValidator('<= 2.0')
  """

  def __init__(self, criteria_str, mf=None):
    name = self.__class__.__name__
    super(DrumrollValidator, self).__init__(criteria_str, mf, name)

  def _GetTwoFarthestPoints(self, fingers):
    """ Find the two points that are farthest apart in the readings """
    if len(fingers) <= 1:
      return None, None

    max_distance = float('-inf')
    two_farthest_points = (None, None)

    for p1 in fingers:
      for p2 in fingers:
        distance = self._Distance(p1, p2)
        if distance > max_distance:
          two_farthest_points = (p1, p2)
          max_distance = distance

    return two_farthest_points


  def _FindTwoFarthestClusters(self, fingers):
    """ Separate all the points where these fingers are into two separated
    clusters.  This is done by finding the two farthest apart points, then
    grouping the remaining points based on their proximity to those two.
    """
    p1, p2 = self._GetTwoFarthestPoints(fingers)
    if p1 is None or p2 is None:
      return [], []

    cluster1 = set([f for f in fingers
                    if self._Distance(f, p1) < self._Distance(f, p2)])
    cluster2 = set([f for f in fingers
                    if self._Distance(f, p1) >= self._Distance(f, p2)])
    return cluster1, cluster2

  def _MinimumEnclosingRadius(self, fingers):
    """ Compute the radius (in mm) of the smallest circle that can surround all
    the points where the fingers are.
    """
    if len(fingers) <= 1:
      return 0
    fingers_mm = [BaseValidator._device.PxToMm((f.x, f.y)) for f in fingers]
    circle = minicircle(fingers_mm)
    return circle.radius

  def Validate(self, snapshots):
    """ For each tracking ID, the events should all be able to be enclosed in
    a circle with a radius which is scored by this validator.
    """
    paths = self._SeparatePaths(snapshots)
    radii = []
    # for each finger, see how big the two radii are and store them all
    for path in paths:
      clusters = self._FindTwoFarthestClusters(path)
      radii += [self._MinimumEnclosingRadius(cluster) for cluster in clusters]

    result = Result()
    result.name = self.name
    result.units = 'mm'
    result.criteria = self.criteria_str
    if radii:
      # The biggest radius is the value we will be scoring
      result.observed = max(radii)
    else:
      result.observed = float('inf')
      result.error = ('Unable to determine radii.  Perhaps not enough '
                      'events were collected.')
    result.score = self.fc.mf.grade(result.observed)
    return result


class PhysicalClickValidator(BaseValidator):
  """ Validator to check for the number of physical clicks with a given number
  of fingers.

  Example:
      To verify that the gesture included a single, 1-finger physical click
        PhysicalClickValidator('== 1', fingers=1)
  """

  def __init__(self, criteria_str, fingers, mf=None):
    name = self.__class__.__name__
    self.fingers = fingers
    super(PhysicalClickValidator, self).__init__(criteria_str, mf, name)

  def _CountClicks(self, snapshots):
    """ Count how many clicks there were for each number of fingers.  To be
    counted a the button must go down and up, and the number of fingers is
    considered to be the number of fingers seen while the button was initially
    pressed down.  This is a slight simplification of the actual gestures
    library, but is correct in the vast majority of cases, and should always
    work with an ideal touch pad.

    This returns a dictionary mapping the number of finger->number of clicks
    eg {1: 2} would indicate there were 2, 1-finger clicks
       {2: 1, 1: 3} would indicate there were 3 1-finger and 1 2-finger clicks
    """
    clicks = {}
    button_pressed = False
    fingers_down = 0
    for snapshot in snapshots:
      # If the button just got pressed (rising edge)
      if snapshot.button_pressed and not button_pressed:
        button_pressed = True
        fingers_down = len(snapshot.fingers)

      # If the button just got released (falling edge)
      elif button_pressed and not snapshot.button_pressed:
        clicks[fingers_down] = clicks.get(fingers_down, 0) + 1
        button_pressed = False
    return clicks

  def Validate(self, snapshots):
    """ Check the how many physical clicks were seen with the # of fingers """
    clicks = self._CountClicks(snapshots)

    result = Result()
    result.name = self.name
    result.units = '#'
    result.criteria = self.criteria_str
    result.observed = clicks.get(self.fingers, 0)
    result.score = self.fc.mf.grade(result.observed)
    return result


class HysteresisValidator(BaseValidator):
  """ Validator to check if the finger position jumps initially when it starts
  moving.

  This is to check for the issue of too much "movement hysteresis" being
  applied in the FW.  Some touch devices try to prevent jitter by imposing a
  minimum distance a finger must move before it starts reporting the movements.
  This works really well, but it makes it impossible to make fine (single
  pixel) adjustments to the cursor position with the touchpad if this value is
  set too high.

  When the movement hysteresis is too high, you can tell because there will
  be a large gap (relative to the other events' spacings) between the first
  two positions of the finger.  This Validator computes the distance between
  the first and second locations the finger reports as well as the distance
  between the second and third locations and computes the ratio of those
  values.  If this ratio is skewed, then we know there was a high movement
  hysteresis that would have resulted in a cursor jump.

  Example:
    To make sure the first gap is no more than 2x the size of the next gap:
    HysteresisValidator('<= 2.0')
  """

  def __init__(self, criteria_str, mf=None):
    name = self.__class__.__name__
    super(HysteresisValidator, self).__init__(criteria_str, mf, name)

  def _FindNextDistinctLocation(self, path, start_location):
    for i in range(start_location, len(path)):
      if self._Distance(path[i], path[start_location]) > 0.0:
        return i, path[i]
    return None, None

  def Validate(self, snapshots):
    """ Check for a large jump at the beginning of the finger's path. """
    error = None

    try:
     # First find the finger to test.  This will be whichever tracking id
     # has the most events, so it's easy to tell.
     paths = self._SeparatePaths(snapshots)
     path = sorted(paths, key=lambda x: -len(x))[0]

     # Find the first packet and the next two that moved.  they may not be the
     # adjacent packets if the x/y locations stayed the same, but pressure or
     # some other values changed.
     point0 = path[0]
     point1_idx, point1 = self._FindNextDistinctLocation(path, 0)
     _, point2 = self._FindNextDistinctLocation(path, point1_idx)

     # Find the distances between these points
     distance1 = self._Distance(point0, point1)
     distance2 = self._Distance(point1, point2)

     # Compute the ratio between them to see if there was a jump
     ratio = distance1 / distance2
    except:
      # If something fails (eg: not enough points) set the ratio to infinity
      ratio = float('inf')
      error = 'Not enough distinct events seen'

    result = Result()
    result.name = self.name
    result.units = '*ratio*'
    result.criteria = self.criteria_str
    result.observed = ratio
    result.score = self.fc.mf.grade(result.observed)
    if error:
      result.error = error
    return result


class DiscardInitialSecondsValidatorWrapper(BaseValidator):
  """ This validator wraps another validator and run that validator on the
  gesture, but with the first bit of time removed.

  This is used to more accureately match our spec for noise immunity.  The spec
  allows for a bit of time before the touch device needs to return to normal
  funtionality after electrical noise increases.  Using this validator you can
  do things like check the linearity of a line "after the first 2 seconds."
  """
  def __init__(self, validator, mf=None, initial_seconds_to_discard=1):
    self.validator = validator
    self.initial_seconds_to_discard = initial_seconds_to_discard
    name = self.__class__.__name__
    super(DiscardInitialSecondsValidatorWrapper, self).__init__(
                                              validator.criteria_str, mf, name)
  def Validate(self, snapshots):
    """ Remove the first few snapshots from the list then pass them on to the
    sub-validator for validation.
    """
    if len(snapshots) > 0:
      # Use the timestamp of the first event, then add the amount of time being
      # discarded to compute a cutoff time.
      start_time = snapshots[0].syn_time
      new_start_time = start_time + self.initial_seconds_to_discard

      # Filter out any events that occurred before the cutoff
      trimmed_snapshots = [s for s in snapshots if s.syn_time >= new_start_time]

      # Finally pass the trimmed snapshots on to the sub-validator
      result = self.validator.Validate(trimmed_snapshots)
    else:
      result = self.validator.Validate([])

    # Modifying the result's name to indicate some values were trimmed.
    result.name = 'Noisy%s' % result.name
    return result
