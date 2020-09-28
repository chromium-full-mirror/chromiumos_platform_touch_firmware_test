# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Remote classes for heatmap devices on full DUTs being tested.

This module includes RemoteHeatMapDevice. It can be used to call remote command
on DUT. RemoteHeatMapDevice use hetamap_tool(device specific driver) as backend.
RemoteHeatMapDevice.NextEvent will get the next heatmap event from remote
device. Currently, it only support heatmap from profile sensor. The heatmap
event is array of x sensor reading or y sensor reading.
"""

from __future__ import print_function
import inspect
import os
import select
import stat
import sys
import json
from subprocess import PIPE, Popen

class HeatMapEvent(object):
  """Container class for heatmap event."""

  def __init__(self, sensor, data):
    self.sensor = sensor
    self.data = data

  def ToJson(self):
    return json.dumps({'sensor':self.sensor, 'data':self.data})


class RemoteHeatMapDevice(object):
  """This class represents a remote heatmap device.

  Connect to a remote device by creating an instance with addr. Then call
  NextEvent will get the next heatmap event.
  """

  def __init__(self, addr):
    self.pole = 0
    self.restart_flag = False
    self.addr = addr
    self.begin_event_stream_cmd = 'heatmap_tool --action dump --pole %s'
    self.kill_remote_process_cmd = 'heatmap_tool --action reset_device'
    self.event_stream_process = None

    # Spawn the event gathering subprocess
    self._InitializeEventGatheringSubprocess()
    self._RunRemoteCmd('stop powerd')

  def SetPole(self, pole):
    if self.pole != pole:
      self.pole = pole
      self.restart_flag = True

  def Restart(self):
    self._StopStreamOfEvents()
    self._InitializeEventGatheringSubprocess()
    self.restart_flag = False

  def _InitializeEventGatheringSubprocess(self):
    # Initiate the streaming connection
    print('Run dump heatmap with pole %s' % self.pole)
    self.event_stream_process = self._RunRemoteCmd(
        self.begin_event_stream_cmd % self.pole)

    # Check to make sure it didn't terminate immediately
    ret_code = self.event_stream_process.poll()
    if ret_code is not None:
      print('ERROR: streaming terminated unexpectedly (%d)' % ret_code)
      return False

    # Block until there's *something* to read, indicating everything is ready
    readable, _, _, = select.select([self.event_stream_process.stdout], [], [])
    return self.event_stream_process.stdout in readable

  def NextEvent(self, timeout=None):
    """Wait for and capture the next heatmap event."""
    if self.restart_flag:
      self.Restart()

    event = None
    while not event:
      if not self.event_stream_process:
        return None

      line = self._GetNextLine(timeout)
      if not line:
        return None

      event = self._ParseHeatMap(line)
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
      self.event_stream_process = None
      return None
    return line

  def _ParseHeatMap(self, line):
    """Parse the heatmap event.

    HeatMap look like this:
    x 2704.52347057 3439.14661528 3213.1087246 3043.58030659
    """
    items = line.split()
    if len(items) < 1 or (items[0] != 'x' and items[0] != 'y'):
      return None
    data = list(map(float, items[1:]))
    return HeatMapEvent(items[0], data)

  def _RunRemoteCmd(self, cmd):
    """Run a command on the shell of a remote ChromeOS DUT."""
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

  def _StopStreamOfEvents(self):
    """Stops the stream of events.

    There are two steps.
    Step 1: Kill the remote process; otherwise, it becomes a zombie process.
    Step 2: Kill the local ssh subprocess.
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

  def __del__(self):
    self._StopStreamOfEvents()
