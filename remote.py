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
 3. Repeatedly call NextEvent(), which will block until another MT event
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
import time
from subprocess import PIPE, Popen, STDOUT

import mt
from mt.input import linux_input


class RemoteTouchDevice:
  not_implemented_msg = 'Must be implemented by a subclass.'

  # Unfortunately the device names are not very standardized on Android.
  # For android devices you may need to check /proc/bus/input/devices
  # and add the correct device name to this list.
  touchscreen_device_names = [
    'touchscreen',
    'max1187x_touchscreen_0',
    'synaptics_dsx_i2c',
    'mtk-tpd',
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

    # Determine the ranges/resolutions of the various attributes of fingers
    x, y, p = self._GetDimensions()
    self.x_min, self.x_max, self.x_res = x['min'], x['max'], x['resolution']
    self.y_min, self.y_max, self.y_res = y['min'], y['max'], y['resolution']
    self.p_min, self.p_max = p['min'], p['max']

    # Determine with protocol the device uses: MTA or MTB
    self.protocol = self._GetMtProtocol()

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

  def _GetMtProtocol(self):
    """ This function determines the Multitouch protocol used by this device.
    For most devices mtb is used, but for a few devices mta has been
    encountered.

    This function is called for all devices in the constructor and needs to
    be implimented by the subclass.  If a particular class of devices will
    always use one protocol this function can simply return that value without
    contacting the device at all
    """
    raise NotImplementedError(RemoteTouchDevice.not_implemented_msg)

  def _GetDimensions(self):
    """ Reach out to the DUT and determine the dimensions of the sensor, the
    x/y resolution, and the range of pressure values it reports.

    This function should return three dictionaries of the following form:
      (x, y, p)
    where x and why have 'min' 'max' and 'resolution' defined, and p has only
    'min' and 'max.

    This is called automatically in the constructor to set the ranges for all
    of the various dimensions of the device.
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
    return (self.PxToMm_X(self.x_max - self.x_min),
            self.PxToMm_Y(self.y_max - self.y_min))

  def _ParseMtEvent(self, line):
    """ Specifies how to parse a line of output into an MtEvent object
    This function should take in a single line of output from stdout and
    return None in the case the input does not contain an MT event or
    the MtEvent object that it represents.
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
    """ Wait for and capture the next MT event
    Once a connection has been initiated with BeginEventStream() this
    function can be called to block until another MT event arrives
    from the DUT.  If the subprocess has stopped, None is returned,
    otherwise a string with the MT event is returned.
    """
    event = None
    while not event:
      if not self.event_stream_process:
        return None

      line = self._GetNextLine(timeout)
      if not line:
        return None

      event = self._ParseMtEvent(line)
    return event

  def _GetNextLine(self, timeout=None):
    if timeout:
      inputs = [self.event_stream_process.stdout]
      readable, _, _, = select.select(inputs, [], [], timeout)
      if inputs[0] not in readable:
        return None

    line = self.event_stream_process.stdout.readline()

    # If the event_stream_process had been terminated, just return None.
    if self.event_stream_process is None:
      return None

    if line == '' and self.event_stream_process.poll() != None:
      self.event_steam_process = None
      return None
    return line

  def EndEventStream(self):
    """ Stops the stream of events

    There are two steps.
    Step 1: Kill the remote process; otherwise, it becomes a zombie process.
    Step 2: Kill the local ssh/adb subprocess.
            This terminates the subprocess that's maintaining the connection
            with the DUT and returns its return code.
    """
    # Step 1: kill the remote process; otherwise, it becomes a zombie process.
    self._RunRemoteCmd(self.kill_remote_process_cmd)
    time.sleep(0.2)

    # Step 2: Kill the local ssh/adb subprocess.
    # If self.event_stream_process has been terminated, its value is None.
    if self.event_stream_process is None:
      return None

    # Kill the subprocess if it is still alive with return_code as None.
    return_code = self.event_stream_process.poll()
    if return_code is None:
      self.event_stream_process.terminate()
      return_code = self.event_stream_process.wait()
      if return_code is None:
        print 'Error in killing the event_stream_process!'
    self.event_stream_process = None
    return return_code

  def _GetDeviceNumber(self, is_touchscreen):
    """ Collects the device ID for the touchpad/screen we're connecting to
    This is so when we try to start streaming events we can make sure we're
    connected to the right device on the DUT.
    """
    def GetAllDeviceNumberMappings():
      # This file contains the mappings so we can determine which event file
      output = self._RunRemoteCmd('cat /proc/bus/input/devices').stdout.read()

      # Build up a dictionary mapping device names -> device numbers
      mappings = {}
      current_name = None
      for line in output.split('\n'):
        line = str.replace(line, '\r', '')
        matches = re.match('^N:\s+Name="(.+)"\s*$', line)
        if matches:
          current_name = matches.group(1)
        matches = re.match('^H:\s+Handlers=.*event(\d+).*$', line, re.M)
        if matches:
          mappings[int(matches.group(1))] = current_name

      return mappings

    # First find all the device names/numbers on the DUT
    device_names_by_number = GetAllDeviceNumberMappings()

    # Determine the list of known names for touchpads/touchscreens
    name_strings = RemoteTouchDevice.touchpad_device_names
    if is_touchscreen:
      name_strings = RemoteTouchDevice.touchscreen_device_names

    # If we found one that matches already just return it
    for name_string in name_strings:
      for device_number, device_name in device_names_by_number.items():
        if name_string in device_name.lower():
          return device_number

    # If we haven't found it yet, we'll have to ask the user to pick it
    # from the list for us, because we can't tell which device it is.
    print ('Sorry, we were unable to autodetect the %s device.' %
           'touchscreen' if is_touchscreen else 'touchpad')
    print 'Please select the correct device from the list below'
    sorted_devices = sorted(device_names_by_number.items(), key=lambda x:x[0])
    for device_number, device_name in sorted_devices:
      print '%d: "%s"' % (device_number, device_name)

    # Loop until the user makes a valid device selection for us.
    selection = None
    while selection not in device_names_by_number:
      if selection:
        print 'Error: That is not a legal device number'

      selection = raw_input('Enter the device number you wish to test: ')
      try:
        selection = int(selection)
      except:
        pass

    return selection


class AndroidTouchDevice(RemoteTouchDevice):
  def __init__(self, addr, is_touchscreen=False):
    self.begin_event_stream_cmd = 'getevent -tv /dev/input/event%d'
    self.kill_remote_process_cmd = (
        'for f in `ls /proc/`; do'
        '  grep getevent /proc/$f/cmdline &>/dev/null;'
        '  if [ "$?" == "0" -a "$f" != "self" ]; then'
        '    kill $f;'
        '  fi;'
        'done')
    RemoteTouchDevice.__init__(self, addr, is_touchscreen)

  def _GetMtProtocol(self):
    """ Android devices usually use mtb, but for some devices they still use
    mta.  You can tell the difference by looking at the events that the touch
    device will emit.  If they use the BTN_TOUCH key, you know it is mta, as
    that is the event that is used to indicate a finger touching the pad for
    mta only, whereas mtb uses tracking ids to do this.

    Devices that use mta will have an entry when querying the touch device
    with "getevent" like the line below.

      KEY (0001): 014a

    Note that 014a is the code for BTN_TOUCH.  If we see that we know it's an
    mta Android device.  If not, then it's mtb.
    """
    cmd = 'getevent -p /dev/input/event%d' % self.device_num
    output = self._RunRemoteCmd(cmd).stdout.read()
    for line in output.split('\n'):
      if re.match('^.*KEY\s+\(\d+\):.*\s+014a.*$', line):
        return mt.MTA
    return mt.MTB

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
    device will return, so this checks the range for X/Y positions and
    pressure and returns them.

    Running "getevent -p" on Android will output the details for the values
    the device will output as shown below.  The first number is a code that
    specifies which parameter it is describing, then it has other information
    about it such as min/max/etc.
      ...
      0035  : value 0, min 0, max 1080, fuzz 0, flat 0, resolution 0
      0036  : value 0, min 0, max 1920, fuzz 0, flat 0, resolution 0
      003a  : value 0, min 0, max 181, fuzz 0, flat 0, resolution 0
      ...
    This function finds the line for X, Y, and pressure values and parses them
    out to get their ranges.

    Note: Android doesn't seem to report the X/Y resolution in the typical
    fashion here, so it is computed in the function _GetResolution() as a
    separate step before returning.  To see how we compute resolution
    information for Android, look in that function.
    """
    x = y = p = None
    cmd = 'getevent -p /dev/input/event%d' % self.device_num
    output = self._RunRemoteCmd(cmd).stdout.read()
    for line in output.split('\n'):
      pattern = '^.*([0-9a-f]{4})\s+:\s+.*min (\d*),\s+max (\d*),.*$'
      matches = re.match(pattern, line, re.M)
      if not matches:
        continue
      code = int(matches.group(1), 16)
      min_value = int(matches.group(2))
      max_value = int(matches.group(3))
      if code in [linux_input.ABS_MT_POSITION_X, linux_input.ABS_X]:
        x = {'min': min_value, 'max': max_value}
      elif code in [linux_input.ABS_MT_POSITION_Y, linux_input.ABS_Y]:
        y = {'min': min_value, 'max': max_value}
      elif code in [linux_input.ABS_MT_PRESSURE, linux_input.ABS_PRESSURE]:
        p = {'min': min_value, 'max': max_value}

    resolution = self._GetResolution()
    x['resolution'] = resolution
    y['resolution'] = resolution
    return x, y, p

  def _ToSignedInt(self, x, bits):
    return x if x & (1 << (bits - 1)) == 0 else x - (1 << bits)

  def _ParseMtEvent(self, line):
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

    return mt.MtEvent(timestamp, event_type, event_code, value)

  def _RunRemoteCmd(self, cmd):
    """ Run a command on the shell of a remote Android DUT """
    args = ['adb', 'shell', cmd]
    if self.addr:
      args = ['adb', '-s', self.addr, 'shell', cmd]
    return Popen(args, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)


class ChromeOSTouchDevice(RemoteTouchDevice):
  def __init__(self, addr, is_touchscreen=False):
    self.begin_event_stream_cmd = 'evtest --grab /dev/input/event%d'
    self.kill_remote_process_cmd = 'killall evtest'
    RemoteTouchDevice.__init__(self, addr, is_touchscreen)

  def _GetMtProtocol(self):
    """ ChromeOS devices always use mtb, so we can simply return that. """
    return mt.MTB

  def _GetDimensions(self):
    """ Evtest simply outputs the legal ranges of values for X/Y/etc at
    the beginning of its output.  So instead of issuing a new remote
    command to figure out the dimensions, this function simply consumes
    the first few lines of output (before actual events are reported)
    and parses out the ranges.

    The first thing that evtest outputs is a bunch of information about
    the values the device will produce.  Among that information are blocks
    that looks like this describing the range of x/y/etc values.
      ...
      Event code 53 (ABS_MT_POSITION_X)
        Value      0
        Min        0
        Max     3029
        Resolution      31
      ...
    This function finds them and parses out the max values and resolutions for
    both X and Y values, in addition to the maximum value for pressure.
    """
    def _GetDimensions_Aux(required_attributes):
      """ This helper function parses out the ranges for a single dimension """
      dim = {}
      while not all([(attrib in dim) for attrib in required_attributes]):
        line = self._GetNextLine()
        matches = re.match('^\s*(\S+)\s*(\d+).*$', line)
        if matches:
          attribute = matches.group(1).lower()
          value = int(matches.group(2))
          if attribute in required_attributes:
            dim[attribute] = value
      return dim

    # Compute the dimensions by reading the first few lines
    self.BeginEventStream()

    x = y = p = None
    while not all([x, y, p]):
      line = self._GetNextLine()
      if 'Event code 53 (ABS_MT_POSITION_X)' in line:
        x = _GetDimensions_Aux(['min', 'max', 'resolution'])
      elif 'Event code 54 (ABS_MT_POSITION_Y)' in line:
        y = _GetDimensions_Aux(['min', 'max', 'resolution'])
      elif 'Event code 58 (ABS_MT_PRESSURE)' in line:
        p = _GetDimensions_Aux(['min', 'max'])

    self.EndEventStream()
    return x, y, p

  def _ParseMtEvent(self, line):
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
      return mt.MtEvent(timestamp, linux_input.EV_SYN, linux_input.SYN_REPORT)
    pattern = '^.*type (\d+) .*, code (\d+) .*, value (-?\d+).*$'
    matches = re.match(pattern, contents)
    event_type = int(matches.group(1))
    event_code = int(matches.group(2))
    value = int(matches.group(3))

    return mt.MtEvent(timestamp, event_type, event_code, value)

  def _RunRemoteCmd(self, cmd):
    """ Run a command on the shell of a remote ChromeOS DUT """
    args = ['ssh', 'root@%s' % self.addr,
            '-i', './data/testing_rsa',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
            cmd]
    return Popen(args, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
