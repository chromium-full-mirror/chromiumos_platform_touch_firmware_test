# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
""" Remote classes for touch devices on DUTs being tested.

To enable running touch device firmware testing on devices of various types
of platforms this module introduces a RemoteTouchDevice interface.  One can
create subclasses that fill out how to stream touch events from a remote
DUT and then they can be substituted seamlessly, leveraging the test suite's
common code.

The basic work flow for a RemoteTouchDevice is this:
 1. Create the device with an address (may vary depending on DUT type) and
  a boolean to indicate if you want a touchscreen or touchpad.
 2. Call the device's BeginEventStream() method to initiate a connection
  and do any setup work that platform might require.
 3. Repeatedly call NextEvent(), which will block until another MTB event
  arrives.  Note: These are raw MTB events, it does not wait for SYN events
  but instead returns each event as they arrive.
 4. Close/cleanup the connection by running EndEventStream()

For example, you can instantiate objects for various DUT types then use them
exactly the same way:

  touch_dev = ChromeOSTouchDevice(addr='192.168.0.3', is_touchscreen=False)
  touch_dev = ChromeOSTouchDevice(addr='192.168.0.3', is_touchscreen=True)
  touch_dev = AndroidTouchDevice(addr=None, is_touchscreen=True)

  touch_dev.BeginEventStream()
  for i in range(100):
    print touch_dev.NextEvent()
  touch_dev.EndEventStream()
"""

import re
import select
from subprocess import PIPE, Popen, STDOUT
from mtb import MtbEvent
from mtb.input import linux_input


class RemoteTouchDevice:
  not_implemented_msg = 'Must be implemented by a subclass.'

  # Unfortunately the device names are not very standardized on Android.
  # For android devices you may need to check /proc/bus/input/devices
  # and add the correct device name to this list.
  touchscreen_device_names = [
    'touchscreen',
    'max1187x_touchscreen_0',
    'synaptics_dsx_i2c',
  ]
  touchpad_device_names = [
    'touchpad',
    'trackpad',
  ]

  def __init__(self, addr, is_touchscreen=False):
    self.addr = addr
    self.is_touchscreen = is_touchscreen
    self.event_stream_process = None
    self.begin_event_stream_cmd = self.begin_event_stream_cmd or ''

    # Probe to find out which device we want to connect to on the DUT
    self.device_num = self._GetDeviceNumber(self.is_touchscreen)
    if not self.device_num:
      print 'ERROR: Unable to determind the device number!'

    self.width, self.height, self.x_res, self.y_res = self._GetDimensions()

  def BeginEventStream(self):
    """ Initiate a stream of MTB events from the DUT
    This function starts up an ongoing connection over which we can
    receive MTB events on stdout.  After calling this, repeated calls to
    NextEvent() will return each event as they arrive.
    Returns True on success, False it something went wrong
    """
    # Initiate the streaming connection
    self.event_stream_process =  self._RunRemoteCmd(
                        self.begin_event_stream_cmd % self.device_num)

    # Check to make sure it didn't terminate immediately
    ret_code = self.event_stream_process.poll()
    if ret_code is not None:
      print 'ERROR: streaming terminated unexpectedly (%d)' % ret_code
      return False

    # Block until there's *something* to read, indicating everything is ready
    readable, _, _, = select.select([self.event_stream_process.stdout], [], [])
    return self.event_stream_process.stdout in readable


  def _GetDimensions(self):
    """ Read out to the DUT and determine the dimensions of the sensor and the
    x/y resolution.
    This function should return (width, height, x_res, y_res) and is called
    automatically in the constructor to set self.width, self.height, self.x_res
    and self.y_res.
    """
    raise NotImplementedError(RemoteTouchDevice.not_implemented_msg)

  def PxToMm_X(self, x):
    return float(x) / float(self.x_res)

  def PxToMm_Y(self, x):
    return float(x) / float(self.x_res)

  def PxToMm(self, (x, y)):
    return self.PxToMm_X(x), self.PxToMm_Y(y)

  def DimensionsInMm(self):
    """ Convert width/height into mm """
    return self.PxToMm_X(self.width), self.PxToMm_Y(self.height)

  def _ParseMtbEvent(self, line):
    """ Specifies how to parse a line of output into an MtbEvent object
    This function should take in a single line of output from stdout and
    return None in the case the input does not contain an MTB event or
    the MtbEvent object that it represents.
    """
    raise NotImplementedError(RemoteTouchDevice.not_implemented_msg)

  def _RunRemoteCmd(self, cmd):
    """ This function should run cmd on the remote device.
    Depending on the device type this may be implemented different ways.
    For instance, on ChromeOS devices this would use SSH but on Android
    it might used adb instead.
    """
    raise NotImplementedError(RemoteTouchDevice.not_implemented_msg)

  def NextEvent(self, timeout=None):
    """ Wait for and capture the next MTB event
    Once a connection has been initiated with BeginEventStream() this
    function can be called to block until another MTB event arrives
    from the DUT.  If the subprocess has stopped, None is returned,
    otherwise a string with the MTB event is returned.
    """
    event = None
    while not event:
      if not self.event_stream_process:
        return None

      line = self._GetNextLine(timeout)
      if not line:
        return None

      event = self._ParseMtbEvent(line)
    return event

  def _GetNextLine(self, timeout=None):
    if timeout:
      inputs = [self.event_stream_process.stdout]
      readable, _, _, = select.select(inputs, [], [], timeout)
      if inputs[0] not in readable:
        return None

    line = self.event_stream_process.stdout.readline()
    if line == '' and self.event_stream_process.poll() != None:
      self.event_steam_process = None
      return None
    return line

  def EndEventStream(self):
    """ Stops the stream of events
    This terminates the subprocess that's maintaining the connection
    with the DUT and returns its return code.
    """
    if not self.event_stream_process:
      return None
    self.event_stream_process.terminate()
    return_code = self.event_stream_process.wait()
    self.event_stream_process = None
    return return_code

  def _GetDeviceNumber(self, is_touchscreen):
    """ Collects the device ID for the touchpad/screen we're connecting to
    This is so when we try to start streaming events we can make sure we're
    connected to the right device on the DUT.
    """
    # This file contains the mapping so we can determine which event file
    output = self._RunRemoteCmd('cat /proc/bus/input/devices').stdout.read()

    # Parse out the ID for the touchscreen/touchpad
    name_strings = RemoteTouchDevice.touchpad_device_names
    if is_touchscreen:
      name_strings = RemoteTouchDevice.touchscreen_device_names

    found = False
    for line in output.split('\n'):
      line = str.replace(line, '\r', '')
      if any([re.match('^N: Name=".*%s.*"$' % name, line, re.I | re.M)
              for name in name_strings]):
        found = True
      if found:
        matches = re.match('^H: Handlers=.*event(\d+).*$', line, re.M)
        if matches:
          return int(matches.group(1))
    return None


class AndroidTouchDevice(RemoteTouchDevice):
  def __init__(self, addr, is_touchscreen=False):
    self.begin_event_stream_cmd = 'getevent -tv /dev/input/event%d'
    RemoteTouchDevice.__init__(self, addr, is_touchscreen)


  def _GetResolution(self):
    """ Android devices don't report their touchscreen resolution to the
    kernel, but instead have their resolution tied to the LCD resolution.
    To determine this we can pull down their LCD resolution and convert
    from px/in to px/mm to remain consistent with other devices.

    The output of Android's "getprop" command outputs a list of properties
    that look like this:
      ...
      [ro.setupwizard.mode]: [OPTIONAL]
      [ro.sf.lcd_density]: [320]
      [ro.somc.customerid]: [110]
      ...
    We simply run that command on the DUT and then look for the line that
    contains the "lcd_density" and parse out the value.
    """
    MM_PER_INCH_CONVERSION = 25.4
    cmd = 'getprop'
    pattern = '^.*\[ro.sf.lcd_density\]:\s*\[(\d*)\].*$'

    output = self._RunRemoteCmd(cmd).stdout.read()
    for line in output.split('\n'):
      matches = re.match(pattern, line, re.M)
      if matches:
        return float(matches.group(1)) / MM_PER_INCH_CONVERSION

    return None

  def _GetDimensions(self):
    """ Get the dimensions of the touch device by using the getevent -p
    tool.  This program prints the range of each value that the touch
    device will return, so this checks the range for X and Y positions
    and returns them.

    Running "getevent -p" on Android will output the details for the values
    the device will output as shown below.  The first number is a code that
    specifies which parameter it is describing, then it has other information
    about it such as min/max/etc.
      ...
      0035  : value 0, min 0, max 1080, fuzz 0, flat 0, resolution 0
      0036  : value 0, min 0, max 1920, fuzz 0, flat 0, resolution 0
      ...
    This function finds the line for the X and Y values and parses them out
    and gets their ranges.

    Note: Android doesn't seem to report the resolution in the typical
    fashion here, so it is computed in the function _GetResolution() as a
    separate step before returning.  To see how we compute resolution
    information for Android, look in that function.
    """
    width = height = None
    cmd = 'getevent -p /dev/input/event%d' % self.device_num
    output = self._RunRemoteCmd(cmd).stdout.read()
    for line in output.split('\n'):
      pattern = '^.*([0-9a-f]{4})\s+:\s+.*max (\d*),.*$'
      matches = re.match(pattern, line, re.M)
      if not matches:
        continue
      code = int(matches.group(1), 16)
      max_value = int(matches.group(2))
      if code == linux_input.ABS_MT_POSITION_X:
        width = max_value
      elif code == linux_input.ABS_MT_POSITION_Y:
        height = max_value

    resolution = self._GetResolution()
    return width, height, resolution, resolution

  def _ToSignedInt(self, x, bits):
    return x if x & (1 << (bits - 1)) == 0 else x - (1 << bits)

  def _ParseMtbEvent(self, line):
    """ How to parse out the Android-specific event format

    Android events look like this:
        [  583187.983948] 0003 003a 00000080
            timestamp     type code  value

    Note: Some versions of Android will include the device name as well:
        [  124555.734127] /dev/input/event2: 0003 0036 0000024d
    """
    pattern = ('^\[\s*(\d+.\d+)\](.+):?' +
           '([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s*$')
    matches = re.match(pattern, line, re.M | re.I)
    if not matches:
      return None
    if ('event' in matches.group(2) and
      'event%d' % self.device_num not in matches.group(2)):
      return None
    timestamp = float(matches.group(1))
    event_type = int(matches.group(3), 16)
    event_code = int(matches.group(4), 16)
    value = self._ToSignedInt(int(matches.group(5), 16), bits=32)

    return MtbEvent(timestamp, event_type, event_code, value)

  def _RunRemoteCmd(self, cmd):
    """ Run a command on the shell of a remote Android DUT """
    args = ['adb', 'shell', cmd]
    if self.addr:
      args = ['adb', '-s', self.addr, 'shell', cmd]
    return Popen(args, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)


class ChromeOSTouchDevice(RemoteTouchDevice):
  def __init__(self, addr, is_touchscreen=False):
    self.begin_event_stream_cmd = 'evtest /dev/input/event%d'
    RemoteTouchDevice.__init__(self, addr, is_touchscreen)

  def _GetDimensions(self):
    """ Evtest simply outputs the legal ranges of values for X and Y at
    the beginning of its output.  So instead of issuing a new remote
    command to figure out the dimensions, this function simply consumes
    the first few lines of output (before actual events are reported)
    and parses out the ranges.

    The first thing that evtest outputs is a bunch of information about
    the values the device will produce.  Among that information are blocks
    that looks like this describing the range of x & y values.
      ...
      Event code 53 (ABS_MT_POSITION_X)
        Value      0
        Min        0
        Max     3029
        Resolution      31
      ...
    This function finds them and parses out the max values and resolutions for
    both X and Y values.
    """
    # Compute the dimensions by reading the first few lines
    self.BeginEventStream()

    ready_for_x = False
    ready_for_y = False
    width = height = None
    x_resolution = y_resolution = None
    while not all([width, height, x_resolution, y_resolution]):
      line = self._GetNextLine()
      if 'Event code 53 (ABS_MT_POSITION_X)' in line:
        ready_for_x = True
      elif 'Event code 54 (ABS_MT_POSITION_Y)' in line:
        ready_for_y = True
      elif ready_for_x or ready_for_y:
        matches = re.match('^\s*(\S+)\s*(\d+).*$', line)
        if matches:
          attribute = matches.group(1)
          value = int(matches.group(2))

          if attribute == 'Max' and ready_for_x:
            width = value
          elif attribute == 'Max' and ready_for_y:
            height = value
          elif attribute == 'Resolution' and ready_for_x:
            x_resolution = value
            ready_for_x = False
          elif attribute == 'Resolution' and ready_for_y:
            y_resolution = value
            ready_for_y = False

    self.EndEventStream()
    return width, height, x_resolution, y_resolution

  def _ParseMtbEvent(self, line):
    """ How to parse out the ChromeOS-specific event format

    ChromeOS events look like this:
    Event: time 1416420362.444933, type 3 (EV_ABS), code 1 (ABS_Y), value 599
    Event: time 1416420362.425098, -------------- SYN_REPORT ------------
    """
    matches = re.match('^Event: time (\d+.\d+), (.*)$', line)
    if matches:
      timestamp = float(matches.group(1))
      contents = matches.group(2)
    else:
      return None

    if 'SYN_REPORT' in contents:
      return MtbEvent(timestamp)
    pattern = '^.*type (\d+) .*, code (\d+) .*, value (-?\d+).*$'
    matches = re.match(pattern, contents)
    event_type = int(matches.group(1))
    event_code = int(matches.group(2))
    value = int(matches.group(3))

    return MtbEvent(timestamp, event_type, event_code, value)

  def _RunRemoteCmd(self, cmd):
    """ Run a command on the shell of a remote ChromeOS DUT """
    args = ['ssh', 'root@%s' % self.addr,
            '-i', './data/testing_rsa',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
            cmd]
    return Popen(args, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
