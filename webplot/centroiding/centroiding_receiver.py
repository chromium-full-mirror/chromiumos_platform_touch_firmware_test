# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Centroiding receiver handles centroiding data stream from dut and forwards
to webplot module for data visualizing.
"""

import ctypes
import ctypes.util
import json
import os
import socket
import time
from builtins import range

# Pre-load librt.so for MonotonicTime()
librt_name = ctypes.util.find_library('rt')
librt = ctypes.cdll.LoadLibrary(librt_name)


class TimeSpec(ctypes.Structure):
  """A representation of struct timespec in C."""
  _fields_ = [
      ('tv_sec', ctypes.c_long),
      ('tv_nsec', ctypes.c_long),
  ]


clock_gettime = librt.clock_gettime
clock_gettime.argtypes = [ctypes.c_int, ctypes.POINTER(TimeSpec)]


def MonotonicTime():
  """Gets the raw monotonic time.

  This function opens librt.so with ctypes and call:
    int clock_gettime(clockid_t clk_id, struct timespec *tp);
  to get raw monotonic time.

  Returns:
    The system monotonic time in seconds.
  """
  CLOCK_MONOTONIC_RAW = 4
  t = TimeSpec()
  if clock_gettime(CLOCK_MONOTONIC_RAW, ctypes.pointer(t)) != 0:
    errno = ctypes.get_errno()
    raise OSError(errno, os.strerror(errno))
  return t.tv_sec + 1e-9 * t.tv_nsec


class FPSCounter(object):
  """The frame counter and frame rate calculator."""
  def __init__(self, frame_interval=200):
    """The init method of FPS counter.

    Args:
      frame_interval: FPS will be calculated and updated every # frames.
    """
    self.frame_interval = frame_interval
    self.fps = 0
    self.frame_counter = 0
    self.timestamp = MonotonicTime()

  def GetFPS(self):
    """Gets current FPS in string."""
    return '%.4f' % self.fps

  def Count(self):
    """Counts a new frame."""
    self.frame_counter += 1
    if self.frame_counter >= self.frame_interval:
      self._UpdateFPS()
      self.frame_counter = 0

  def _UpdateFPS(self):
    """Updates current FPS."""
    new_timestamp = MonotonicTime()
    time_interval = new_timestamp - self.timestamp
    instant_fps = float(self.frame_counter) / time_interval
    if self.fps == 0:
      self.fps = instant_fps
    else:
      self.fps = self.fps * 0.9 + instant_fps * 0.1
    self.timestamp = new_timestamp


class CentroidingDataReceiver(object):
  """The socket receiver of centroiding data."""
  _CHUNK_BYTE_SIZE = 1024
  _NULL_CHAR = '\x00'

  def __init__(self, server_address, server_port, webplot,
               save_data=None, plot_fps=0):
    """The init method of centroiding TCP client.

    Args:
      server_address: Address of TCP socket server from testing device.
      server_port: TCP socket server port.
      webplot: Webplot object for plotting snapshots.
      save_data: File name for saving received centroiding data. Set to None to
                 disable saving data.
      plot_fps: Target FPS for plotting snapshot. Flow control is managed by
                server and overflow raw data sockets will be skipped. Set 0 to
                disable flow control.
    """
    self.webplot = webplot
    self.is_saving = save_data is not None
    self.save_path = save_data if self.is_saving else '/dev/null'

    self.plot_time_interval = 1.0 / plot_fps if plot_fps else 0
    self.plot_time_target = 0
    self.fps_receiver = FPSCounter()
    self.fps_plot = FPSCounter()

    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.connect((server_address, server_port))

  def StartReceive(self):
    """Starts routine of receiving data and plotting."""
    try:
      with open(self.save_path, 'w') as f:
        chunk_buffer = ''
        while True:
          try:
            chunk = self.sock.recv(self._CHUNK_BYTE_SIZE)
            chunk_buffer += chunk
            if self._NULL_CHAR in chunk_buffer:
              chunk_buffer = self._ExtractSnapshots(chunk_buffer, f)
          except KeyboardInterrupt:
            print('Keyboard interrupt accepted!')
            print('Centroiding receiver is terminated...')
            print('Webplot server is terminated...')
            self.sock.close()
            self.webplot.Quit()
            break
    except IOError as e:
      print('Oops!! something wrong while saving data to %s: %s' % (
          self.save_path, str(e)))
      self.sock.close()
      self.webplot.Quit()

  def _ExtractSnapshots(self, chunk_buffer, save_file):
    """Extracts snapshot data from received chunk buffer.

    Args:
      chunk_buffer: Current received chunk string buffer.
      save_file: File object for saving received data.

    Returns:
      The residue on chunk buffer after snapshot extraction.
    """
    snapshots = chunk_buffer.split(self._NULL_CHAR)
    for i in range(len(snapshots)):
      if i == len(snapshots) - 1:
        return snapshots[i]
      if len(snapshots[i]) == 0:
        continue
      if self.is_saving:
        save_file.write(snapshots[i] + '\n')
        save_file.flush()
      self.fps_receiver.Count()
      if self._PlotWithFlowControl():
        self.fps_plot.Count()
        self._PlotSnapshot(snapshots[i])

  def _PlotWithFlowControl(self):
    """Determines whether to plot this snapshot with flow control.

    Returns:
      True to plot this snapshot; False otherwise.
    """
    if not self.plot_time_interval:
      return True
    current_time = MonotonicTime()
    if current_time > self.plot_time_target:
      self.plot_time_target = current_time + self.plot_time_interval
      return True
    return False

  def _PlotSnapshot(self, snapshot):
    """Plots snapshot data to webplot server.

    Args:
      snapshot: Snapshot data for centroiding in string.
    """
    try:
      snapshot_json = json.loads(snapshot.strip())
      snapshot_json.update(
          {"fps": [self.fps_receiver.GetFPS(), self.fps_plot.GetFPS()]})
      self.webplot.AddSnapshot(snapshot_json)
    except Exception as e:
      print('Exception while plotting snapshot = %r:' % snapshot, e)
