# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import webbrowser

import colorama as color

import gesture_interpreter
import tests
from webplot import Webplot
from report import Report
from touchbot import Touchbot, DeviceSpec


class TestSuite:
  """ This class represents a collection of tests and is used to run them

  A TestSuite object will set up a connection to the DUT, robot, etc, and
  determine which tests can be run.  Once the object is instantiated,
  RunNextTestAndVariation() can be run repeatedly to work your way through
  the entire suite.
  """
  FIRST_SNAPSHOT_TIMEOUT_S = 60
  MAX_EMPTY_SNAPSHOTS = 20
  WEBPLOT_ADDR = '0.0.0.0'
  WEBPLOT_PORT = 8080

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
        print color.Fore.RED + 'Error: Unable to connect to function generator!'
        sys.exit(1)

    # Connect to the robot if the operator says they have it
    self.robot = self.device_spec = None
    if options.has_robot:
      self.robot = Touchbot()
      if not self.robot.comm:
        print color.Fore.RED + 'Error: Unable to connect to robot!'
        sys.exit(1)
      # Load a copy of the device spec if it already exists or calibrate now
      device_spec_filename = './%s.p' % options.name
      if os.path.isfile(device_spec_filename):
        self.device_spec = DeviceSpec.LoadFromDisk(device_spec_filename)
      else:
        print color.Fore.YELLOW + 'No spec found (%s)' % device_spec_filename
        print (color.Fore.YELLOW + 'Please follow these instructions to '
               'calibrate for your "%s" device' % options.name)
        self.device_spec = self.robot.CalibrateDevice(device_spec_filename)

    # Start up the plotter
    self.plotter = Webplot(TestSuite.WEBPLOT_ADDR, TestSuite.WEBPLOT_PORT,
                           self.touch_dev)
    self.plotter.start()
    print color.Fore.YELLOW + 'Plots visible at "%s"' % self.plotter.Url()
    webbrowser.open(self.plotter.Url())

    # Compute the list of tests to run
    self.tests = tests.generate_test_list(options)
    if not self.tests:
        print color.Fore.RED + 'Warning: No tests selected!'
    self.curr_test = 0
    self.curr_variation = 0
    self.curr_iteration = 1

    # Create a new Report that will store all the test Results
    self.report = Report(title=self.options.title,
                         test_version=self.options.test_version)
    self.report.warnings = self.touch_dev.warnings

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

    # Start a new thread to perform the robot gesture (if applicable)
    robot_thread = None
    if self.robot:
      robot_thread = gesture_interpreter.PerformCorrespondingGesture(
                          test, self.curr_variation,
                          self.robot, self.device_spec)
      if robot_thread:
        robot_thread.start()
      else:
        next_test, next_var = self._Advance()
        return (next_test is not None)

    # Consume any stray events that happened since the last gesture
    print 'Waiting for all contacts to leave before recording the gesture...'
    self.touch_dev.FlushSnapshotBuffer()
    self.plotter.Clear()

    # Wait a long time for the first event, then have a much shorter
    # timeout on subsequent incoming events
    snapshots = []
    print 'Waiting for 1st snapshot...',
    snapshot = None
    finger_count = 0
    log = open('debug.log', 'w')
    num_empty_snapshots = 0
    if not robot_thread or not robot_thread.isAlive():
      snapshot = self.touch_dev.NextSnapshot(TestSuite.FIRST_SNAPSHOT_TIMEOUT_S)
      snapshots.append(snapshot)
      log.write('\n'.join([str(r) for r in snapshot.raw_events]) + '\n')
      log.flush()
      finger_count = len(snapshot.fingers)
      if not snapshot:
        print '\rNo MT snapshots collected before timeout!'
    while ((snapshot and num_empty_snapshots < TestSuite.MAX_EMPTY_SNAPSHOTS) or
           (robot_thread and robot_thread.isAlive()) or
           finger_count > 0):
      if snapshot:
        self.plotter.AddSnapshot(snapshot)
        snapshots.append(snapshot)
        log.write('\n'.join([str(r) for r in snapshot.raw_events]) + '\n')
        log.flush()
        finger_count = len(snapshot.fingers)
        print ('\rCollected %d MT snapshots (%d fingers on pad)' %
               (len(snapshots), finger_count)),

        if len(snapshot.fingers) == 0:
          num_empty_snapshots += 1
        else:
          num_empty_snapshots = 0
      snapshot = self.touch_dev.NextSnapshot(test.timeout)
    log.close()
    print

    # Cleanup the robot gesture thread, if it existed
    if robot_thread:
      robot_thread.join()

    # Run the validators on these events
    results = test.RunAllValidators(snapshots)
    for result in results:
      print result

    # Prompt to see if the gesture was performed acceptibly by the user before
    # continuing.  If the user is unsatisfied abort before advancing on to the
    # next test/variation, allowing the test suite to retry this variation.
    if not self.options.has_robot:
      CONFIRMATION_PROMPT = 'Accept Gesture? ([y]/n) '
      yorn = raw_input(CONFIRMATION_PROMPT).lower()
      while yorn not in ['y', 'n', 'yes', 'no', '']:
        print color.Fore.RED + 'Error: please enter "y" or "n" only'
        yorn = raw_input(CONFIRMATION_PROMPT).lower()
      if yorn in ['n', 'no']:
        print color.Fore.RED + 'Operator rejected the gesture.  Please retry...'
        return True

    # Save the image displayed by the plotter
    plot_image_png = self.plotter.Save()

    # Bundle the Validator results with some details of which gesture was used
    # during the test for easier debugging.
    test_result = tests.TestResult(test.variations[self.curr_variation],
                                   results, prompt, plot_image_png)

    # Add the results into our report (And have it print them to stdout, too)
    self.report.AddTestResult(test_result)

    # Advance the test suite to the next test and variation and return an
    # indicator as to whether this was the last thing to do or not.
    next_test, next_var = self._Advance()
    return (next_test is not None)

  def StopPlotter(self):
    self.plotter.Quit()

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
