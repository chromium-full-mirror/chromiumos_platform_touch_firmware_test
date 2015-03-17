# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import colorama as color

import tests
from plotter import TouchPlotter
from report import Report


class TestSuite:
  """ This class represents a collection of tests and is used to run them

  A TestSuite object will set up a connection to the DUT, robot, etc, and
  determine which tests can be run.  Once the object is instantiated,
  RunNextTestAndVariation() can be run repeatedly to work your way through
  the entire suite.
  """

  NO_SNAPSHOT_DETECTED_TIMEOUT_MANUAL_S = 60
  NO_SNAPSHOT_DETECTED_TIMEOUT_ROBOT_S = 5

  def __init__(self, touch_dev, options, args):
    color.init(autoreset=True)

    self.options = options
    self.touch_dev = touch_dev
    tests.validator.BaseValidator._device = self.touch_dev

    # Connect to the function generator if the operator says they have one
    self.fn_generator = None
    if options.has_fn_gen:
      self.fn_generator = tests.noise.HP33120A()
      if not self.fn_generator.IsValid():
        self.fn_generator = None
        options.has_fn_gen = False
        print 'Error: Unable to connect to function generator!'

    # Compute the list of tests to run
    self.tests = tests.generate_test_list(options)
    if not self.tests:
        print color.Fore.RED + 'Warning: No tests selected!'
    self.curr_test = 0
    self.curr_variation = 0
    self.curr_iteration = 1

    self.no_snapshot_timeout = TestSuite.NO_SNAPSHOT_DETECTED_TIMEOUT_MANUAL_S
    if options.has_robot:
      self.no_snapshot_timeout = TestSuite.NO_SNAPSHOT_DETECTED_TIMEOUT_ROBOT_S

    # Create a new Report that will store all the test Results
    self.report = Report()

  def RunNextTestAndVariation(self):
    """ Run the next test.

    This function runs the next test/variation combination in the test suite
    and advances the internal state to the next one automatically.  When
    finished, this function return True if there are more tests to run, and
    False if the whole test suite is done.

    After a TestSuite is instantiated, this function should be called
    repeatedly until it returns False to go through all tests, variations,
    and iterations.
    """
    if self.curr_test >= len(self.tests):
        return False
    test = self.tests[self.curr_test]

    # Print the header for this new test and variation
    prompt = test.PromptForVariation(self.curr_variation)
    print color.Fore.WHITE + '-' * 80
    print color.Fore.BLUE + test.name
    print color.Fore.GREEN + prompt

    # Start the function generator (if applicable)
    if self.fn_generator:
      waveform = test.WaveformForVariation(self.curr_variation)
      if waveform:
        self.fn_generator.GenerateFunction(*waveform)
      else:
        self.fn_generator.Off()

    # Consume any stray events that happened since the last gesture
    print 'Waiting for all contacts to leave before recording the gesture...'
    self.touch_dev.FlushSnapshotBuffer()

    # Wait a long time for the first event, then have a much shorter
    # timeout on subsequent incoming events
    snapshots = []
    plotter = TouchPlotter(self.touch_dev, window_title=prompt)
    print 'Waiting for 1st snapshot...',
    snapshot = self.touch_dev.NextSnapshot(self.no_snapshot_timeout)
    if not snapshot:
      print ('\rNo MT snapshots collected before timeout (%d seconds)!' %
             self.no_snapshot_timeout),
    while snapshot:
      plotter.add_snapshot(snapshot)
      snapshots.append(snapshot)
      print '\rCollected %d MT snapshots' % len(snapshots),
      snapshot = self.touch_dev.NextSnapshot(test.timeout)
    print
    plot_image_png = plotter.end()

    # Run the validators on these events
    results = test.RunAllValidators(snapshots)

    # Bundle the Validator results with some details of which gesture was used
    # during the test for easier debugging.
    test_result = tests.TestResult(results, prompt, plot_image_png)

    # Add the results into our report (And have it print them to stdout, too)
    self.report.AddTestResult(test_result, verbose=True)

    # Advance the test suite to the next test and variation and return an
    # indicator as to whether this was the last thing to do or not.
    next_test, next_var = self._Advance()
    return (next_test is not None)

  def _Advance(self):
    """ Move on to the next test/variation pair

    This function increments all the interal counters, according to the
    number of tests, their variations, and the selected number of iterations
    and returns the test object and the variation number that should be
    done next.

    When the TestSuite is complete, this function will return None, None
    otherwise it will return the next Test object and the variation number
    the test suite is on.
    """
    if self.curr_test >= len(self.tests):
      return None, None
    test = self.tests[self.curr_test]

    if self.curr_variation >= len(test.variations):
      self.curr_test += 1
      self.curr_variation = 0
      self.curr_iteration = 0
      return self._Advance()

    if self.curr_iteration >= self.options.num_iterations:
      self.curr_variation += 1
      self.curr_iteration = 0
      return self._Advance()

    self.curr_iteration += 1
    return test, self.curr_variation
