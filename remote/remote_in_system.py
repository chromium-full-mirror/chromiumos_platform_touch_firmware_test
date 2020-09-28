# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Remote classes for touch devices on full DUTs being tested.

The subclasses in this file are groups as RemoteInSystemTouchDevices, which
use a lot of the same code.  The way these devices are accesses is by remotely
connecting to the laptop/tablet/phone/etc that the touchs device is part of
and using command line tools to query the events.  For instance, on ChromeOS
"ssh" is used to instigate the remote connection and "evtest" is run on the
remote device to query the touch events.

New device classes should be added as subclasses here if they are already
installed in a working computer system with an OS that offers a remote terminal.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import inspect
import os
import re
import select
import stat
from subprocess import PIPE, Popen

from . import mt
from .mt.input import linux_input
from .remote import RemoteTouchDevice


class RemoteInSystemTouchDevice(RemoteTouchDevice):
  """ This class impliments much of the shared functionality among in-system
  remote touch devices.  As such, specific implimentations should derive from
  this class.
  """
  FLUSH_TIMEOUT = 0.1

  def __init__(self, addr, is_touchscreen=False, protocol='auto',
               device_num=None):
    RemoteTouchDevice.__init__(self)

    self.addr = addr
    self.is_touchscreen = is_touchscreen
    self.event_stream_process = None
    self.begin_event_stream_cmd = self.begin_event_stream_cmd or ''
    self.most_recent_snapshot = None
    self.flush_timeout = self.FLUSH_TIMEOUT
    self.pressure_src = mt.MtStateMachine.PRESSURE_FROM_MT_PRESSURE

    # Probe to find out which device we want to connect to on the DUT
    self.device_num = device_num
    if self.device_num is None:
      self.device_num = self._GetDeviceNumber(self.is_touchscreen)
    if self.device_num is None:
      print('ERROR: Unable to determind the device number!')

    # Spawn the event gathering subprocess
    self._InitializeEventGatheringSubprocess()

    # Determine the ranges/resolutions of the various attributes of fingers
    x, y, p, tilt_x, tilt_y, major, minor = self._GetDimensions()
    self._x_min, self._x_max, self._x_res = x['min'], x['max'], x['resolution']
    self._y_min, self._y_max, self._y_res = y['min'], y['max'], y['resolution']
    self._p_min, self._p_max = p.get('min', None), p.get('max', None)
    self._tilt_x_min = tilt_x.get('min', 0);
    self._tilt_x_max = tilt_x.get('max', 0);
    self._tilt_y_min = tilt_y.get('min', 0);
    self._tilt_y_max = tilt_y.get('max', 0);
    self._major_min = major.get('min', 0);
    self._major_max = major.get('max', 0);
    self._minor_min = minor.get('min', 0);
    self._minor_max = minor.get('max', 0);


    # Determine which kind of state machine should be used with this device
    self.protocol = self._GetMtProtocol() if protocol == 'auto' else protocol
    if self.protocol == mt.MTA:
      self.state_machine = mt.MtaStateMachine(self.pressure_src)
    elif self.protocol == mt.MTB:
      self.state_machine = mt.MtbStateMachine(self.pressure_src)
    else:
      self.state_machine = mt.StylusStateMachine(self.pressure_src)


  def _CheckForAlternativePressureSources(self, p, touch_major):
    """ Given dimensional dictionaries for the min/max values for p and touch
    major, this function returns the best guess of what this touch device
    should use for "pressure."  If p is already known, simply return that,
    otherwise try to use the touch_major values instead, and finally as a last
    resort just assume a constant pressure of 1.
    """
    if p:
      return p

    if touch_major:
      self.Warn('This device does NOT report "pressure". Using the contact '
                'size (TOUCH_MAJOR) instead, so we can continue!')
      self.pressure_src = mt.MtStateMachine.PRESSURE_FROM_MT_TOUCH_MAJOR
      return touch_major

    self.Warn('This device does NOT report "pressure" and no substitue '
              'was found.  Using a constant value of 1 so we can continue!')
    self.pressure_src = mt.MtStateMachine.PRESSURE_FROM_NOWHERE
    return {'min': 0, 'max': 1}

  def _InitializeEventGatheringSubprocess(self):
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
      print('ERROR: streaming terminated unexpectedly (%d)' % ret_code)
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

  def _NextEvent(self, timeout=None):
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

    line = self.event_stream_process.stdout.readline().decode()

    # If the event_stream_process had been terminated, just return None.
    if self.event_stream_process is None:
      return None

    if line == '' and self.event_stream_process.poll() != None:
      self.event_steam_process = None
      return None
    return line

  def __del__(self):
    """ Stops the stream of events

    There are two steps.
    Step 1: Kill the remote process; otherwise, it becomes a zombie process.
    Step 2: Kill the local ssh/adb subprocess.
            This terminates the subprocess that's maintaining the connection
            with the DUT and returns its return code.
    """
    # Step 1: kill the remote process; otherwise, it becomes a zombie process.
    killing_process = self._RunRemoteCmd(self.kill_remote_process_cmd)
    killing_process.wait()

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
        print('Error in killing the event_stream_process!')
    self.event_stream_process = None
    return return_code

  def _GetDeviceNumber(self, is_touchscreen):
    """ Collects the device ID for the touchpad/screen we're connecting to
    This is so when we try to start streaming events we can make sure we're
    connected to the right device on the DUT.
    """
    def GetAllDeviceNumberMappings():
      # This file contains the mappings so we can determine which event file
      output = self._RunRemoteCmd('cat /proc/bus/input/devices').stdout.read().decode()

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

    # Ask the user to pick an input device from the list provided by evtest.
    # It's difficult/impossible to autodetect this reliably
    print('Please select the correct device from the list below')
    sorted_devices = sorted(device_names_by_number.items(), key=lambda x:x[0])
    for device_number, device_name in sorted_devices:
      print('%d: "%s"' % (device_number, device_name))

    # Loop until the user makes a valid device selection for us.
    selection = None
    while selection not in device_names_by_number:
      if selection:
        print('Error: That is not a legal device number')

      selection = input('Enter the device number you wish to test: ')
      try:
        selection = int(selection)
      except:
        pass

    return selection


class AndroidTouchDevice(RemoteInSystemTouchDevice):
  def __init__(self, addr, is_touchscreen=False, protocol='auto',
               device_num=None):
    self.begin_event_stream_cmd = 'getevent -tv /dev/input/event%d'
    self.kill_remote_process_cmd = (
        'for f in `ls /proc/`; do'
        '  grep getevent /proc/$f/cmdline &>/dev/null;'
        '  if [ "$?" == "0" -a "$f" != "self" ]; then'
        '    kill $f;'
        '  fi;'
        'done')
    RemoteInSystemTouchDevice.__init__(self, addr, is_touchscreen, protocol,
                                       device_num)

  def _GetMtProtocol(self):
    """ Android devices usually use mtb, but for some devices they still use
    mta.  You can tell the difference by looking at the events that the touch
    device emits.  MTA devices use SYN_MT_REPORT events to delimit finger data
    but that event isn't used at all in MTB.  By reading events from the device
    until a full frame has been read, we should be able to reliably determine
    which protocol is being used by the presence of these events.
    """
    print ('\033[1;32mPlease touch the screen so we may determine which '
           'protocol this Android device uses.\033[0m')

    # Discard events until the start of the next snapshot in case we started
    # in the middle of one
    while not self._NextEvent().is_SYN_REPORT:
      pass

    # Now check all the events of this next snapshot for the signs of MTA
    event = self._NextEvent()
    while not event.is_SYN_REPORT():
      if event.is_SYN_MT_REPORT():
        print('MTA selected by the presence of SYN_MT_REPORT events')
        return mt.MTA
      event = self._NextEvent()

    print('MTB selected by the absence of SYN_MT_REPORT events')
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
    touch_major = touch_minor = {}
    cmd = 'getevent -p /dev/input/event%d' % self.device_num
    output = self._RunRemoteCmd(cmd).stdout.read().decode()
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
      elif code is linux_input.ABS_MT_TOUCH_MAJOR:
        touch_major = {'min': min_value, 'max': max_value}
      elif code is linux_input.ABS_MT_TOUCH_MINOR:
        touch_minor = {'min': min_value, 'max': max_value}

    p = self._CheckForAlternativePressureSources(p, touch_major)

    resolution = self._GetResolution()
    x['resolution'] = resolution
    y['resolution'] = resolution
    return x, y, p, {'min':0, 'max':0}, {'min':0, 'max':0}, touch_major,\
        touch_minor

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
    args = ['adb', 'shell', '-t', '-t', cmd]
    if self.addr:
      args = ['adb', '-s', self.addr, 'shell', '-t', '-t', cmd]
    return Popen(args, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)


class ChromeOSTouchDevice(RemoteInSystemTouchDevice):
  def __init__(self, addr, is_touchscreen=False, protocol='auto', grab=True,
               device_num=None):
    program = 'evtest %s ' % ('--grab' if grab else '')
    self.begin_event_stream_cmd = program + '/dev/input/event%d'
    self.kill_remote_process_cmd = 'killall evtest'
    RemoteInSystemTouchDevice.__init__(self, addr, is_touchscreen, protocol,
                                       device_num)
    # Stop ChromeOS's power daemon to prevent the laptop going to sleep
    self._RunRemoteCmd('stop powerd')

  def _GetMtProtocol(self):
    """ ChromeOS devices generally use mtb, so we can simply return that. In
    the rare case where this is invalid, the operator will know and can
    specify the protocol manually. """
    print ('\033[1;32mAssuming MTB is used.  If this is a different kind, '
           'please rerun the script with --protocol to specify.\033[0m')
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
        matches = re.match('^\s*(\S+)\s*([-]?\d+).*$', line)
        if matches:
          attribute = matches.group(1).lower()
          value = int(matches.group(2))
          if attribute in required_attributes:
            dim[attribute] = value
      return dim

    x = y = p = tilt_x = tilt_y = None
    touch_major = touch_minor = {}
    while not all([x, y, p, tilt_x, tilt_y]):
      line = self._GetNextLine()
      if line is None or 'interrupt to exit' in line:
        break

      if '(ABS_MT_POSITION_X)' in line or '(ABS_X)' in line:
        x = _GetDimensions_Aux(['min', 'max', 'resolution'])
      elif '(ABS_MT_POSITION_Y)' in line or '(ABS_Y)' in line:
        y = _GetDimensions_Aux(['min', 'max', 'resolution'])
      elif '(ABS_MT_PRESSURE)' in line or '(ABS_PRESSURE)' in line:
        p = _GetDimensions_Aux(['min', 'max'])
      elif '(ABS_TILT_X)' in line:
        tilt_x = _GetDimensions_Aux(['min', 'max'])
      elif '(ABS_TILT_Y)' in line:
        tilt_y = _GetDimensions_Aux(['min', 'max'])
      elif 'Event code 48 (ABS_MT_TOUCH_MAJOR)' in line:
        touch_major = _GetDimensions_Aux(['min', 'max'])
      elif 'Event code 48 (ABS_MT_TOUCH_MINOR)' in line:
        touch_minor = _GetDimensions_Aux(['min', 'max'])



    p = self._CheckForAlternativePressureSources(p, touch_major)

    if not tilt_x:
        tilt_x = {'min':0, 'max':0}
    if not tilt_y:
        tilt_y = {'min':0, 'max':0}

    return x, y, p, tilt_x, tilt_y, touch_major, touch_minor

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

    pattern = '^.*type (\d+) .*, code (\d+) .*, value (-?[0-9a-fA-F]+).*$'
    matches = re.match(pattern, contents)
    if matches is None:
      print('ERROR: Unable to parse event!')
      print('\tline: (%s)' % line)
      print('\ttimestamp: (%f)' % timestamp)
      print('\tcontents: (%s)' % contents)

    event_type = int(matches.group(1))
    event_code = int(matches.group(2))

    # evtest reports all values in decimal except 2 events, which are in hex
    # Depending on the event type and code, parse using a different base
    value_base = 10
    if (event_type == linux_input.EV_MSC and
        event_code in [linux_input.MSC_RAW, linux_input.MSC_SCAN]):
      value_base = 16
    value = int(matches.group(3), value_base)

    return mt.MtEvent(timestamp, event_type, event_code, value)

  def _RunRemoteCmd(self, cmd):
    """ Run a command on the shell of a remote ChromeOS DUT """
    RSA_KEY_PATH = os.path.dirname(
        os.path.realpath(inspect.getfile(
        inspect.currentframe()))) + '/data/testing_rsa'
    if stat.S_IMODE(os.stat(RSA_KEY_PATH).st_mode) != 0o600:
      os.chmod(RSA_KEY_PATH, 0o600)

    args = ['ssh', 'root@%s' % self.addr,
            '-i', RSA_KEY_PATH,
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
            cmd]
    return Popen(args, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
