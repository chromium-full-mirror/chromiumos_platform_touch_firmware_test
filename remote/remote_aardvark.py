# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Remote class for touch devices using Aardvark adapter.

At this moment, the only subclass implemented is ElanAardvarkTouchPad,
however, it is expected to add more vendors soon.
The class RemoteAardvarkTouchDevice should contain all the codes that will stay
the same for all touch devices.

New device classes should be added as subclasses here if they are not already
connected to the computer using an Ardvark i2c to USB adaptor.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import inspect
import os
try:
  import queue
except ImportError:
  import Queue as queue
import re
import select
import sys
from subprocess import PIPE, Popen
import time
from importlib import import_module

from . import mt
from .mt.input import linux_input
from .remote import RemoteTouchDevice

class RemoteAardvarkTouchDevice(RemoteTouchDevice):
  """ This class impliments much of the shared functionality among remote
  touch devices that are connected to the system with an Aardvark adapter.
  As such, specific implimentations should derive from this class.
  """

  # This flag indicates that 10 bit address is used
  I2C_NO_FLAGS = 0x00

  # Constants
  I2C_BITRATE = 400
  AARDVARK_FLUSH_TIMEOUT = 0.5

  def __init__(self, addr,
               pressure_src = mt.MtStateMachine.PRESSURE_FROM_MT_PRESSURE):
    try:
      self.adapter = import_module('aardvark_py')
    except ImportError:
      print('The files "aardvark_py.py" and "aardvark.so" are needed.')
      print('You can download these files from the following link.')
      print('https://www.totalphase.com/downloadable/download/sample/sample_id/16/')
      sys.exit()

    RemoteTouchDevice.__init__(self)

    self._addr = addr
    self.state_machine = mt.MtaStateMachine(pressure_src)
    self.flush_timeout = self.AARDVARK_FLUSH_TIMEOUT

    self._Initialize_Aardvark()

    self.adapter.aa_sleep_ms(200)
    self._Initialize_Device()

    # Determine the ranges/resolutions of the various attributes of fingers
    x, y, p = self._GetDimensions()
    self._x_min, self._x_max, self._x_res = x['min'], x['max'], x['resolution']
    self._y_min, self._y_max, self._y_res = y['min'], y['max'], y['resolution']
    self._p_min, self._p_max = p['min'], p['max']
    # Currently no Aardvark-compatible touch devices report tilt events, so
    # these are just set to 0.
    self._tx_min, self._tx_max = 0, 0
    self._ty_min, self._ty_max = 0, 0

  def __del__(self):
    # Turning off the device
    print('Turning off')
    self.adapter.aa_target_power(self._handle,
                                 self.adapter.AA_TARGET_POWER_NONE)

  def _Initialize_Aardvark(self):
    self._port = self._detect_port()
    handle = self.adapter.aa_open(self._port)
    self._handle = handle
    if handle <= 0:
      print('Unable to open Aardvark device on port')
      print('Error code = %d' % handle)
      sys.exit()
    # Ensure that the I2C subsystem is enabled
    self.adapter.aa_configure(handle,  self.adapter.AA_CONFIG_SPI_I2C)
    # Enable the I2C bus pullup resistors (2.2k resistors).
    self.adapter.aa_i2c_pullup(handle, self.adapter.AA_I2C_PULLUP_BOTH)
    # Enable the Aardvark adapter's power supply.
    self.adapter.aa_target_power(handle, self.adapter.AA_TARGET_POWER_BOTH)
    # Set the bitrate
    bitrate = self.adapter.aa_i2c_bitrate(handle, self.I2C_BITRATE)

  def _detect_port(self):
    (num, ports, unique_ids) = self.adapter.aa_find_devices_ext(16, 16)
    for port in ports:
      # Determine if the device is in-use
      if (port & self.adapter.AA_PORT_NOT_FREE):
        port &= ~self.adapter.AA_PORT_NOT_FREE
      return port
    print('No Aardvark devices found.')
    sys.exit()

  def _Initialize_Device(self):
    """ This function should initialize the TP or TS device.
    Depending on the device type this should be implemented different ways.
    It mainly depend on the protocols and the device firmware.
    """
    raise NotImplementedError(RemoteTouchDevice.not_implemented_msg)

  def _i2c_write(self, data):
    data_len = 4 if (data & 0xffff0000) else 2
    data_out = self.adapter.array_u08(data_len)
    for byte_num in range(data_len):
      data_out[byte_num] = (data & (0xff << 8 * byte_num)) >> (8 * byte_num)
    retVal = self.adapter.aa_i2c_write(self._handle,
                                       self._addr, self.I2C_NO_FLAGS, data_out)
    if retVal != data_len:
      print('Error: Number of bytes written: %d' % retVal)
      print('       Make sure that the peripheral address is correct')
      print('       Peripheral address: %d' % self._addr)
      sys.exit()
    else:
      return retVal

  def _cut_data(self, tmp_data, num_bytes):
    start_index = -1
    end_index = -1
    for i in xrange(num_bytes):
      if tmp_data[i] != 255:
        start_index = i
        break
    if start_index != -1:
      for i in xrange(num_bytes):
        if tmp_data[num_bytes - i - 1] != 255:
          end_index = num_bytes - i - 1
          break
    if end_index == -1:
      return 0, num_bytes - 1, tmp_data
    return start_index, end_index , tmp_data[start_index:end_index + 1]

  def _i2c_read(self, num_bytes):
    temp_len, tmp_data = self.adapter.aa_i2c_read(self._handle, self._addr,
                                    self.I2C_NO_FLAGS,
                                    self.adapter.array_u08(num_bytes))
    s, e, data = self._cut_data(tmp_data, num_bytes)
    if e == num_bytes - 1 and s != 0:
      temp_len, tmp_data = self.adapter.aa_i2c_read(self._handle, self._addr,
                                    self.I2C_NO_FLAGS,
                                    self.adapter.array_u08(num_bytes))
      s, e, data_extension = self._cut_data(tmp_data, num_bytes)
      return len(data) + len(data_extension), data + data_extension
    return len(data), data

class ElanTouchDevice(RemoteAardvarkTouchDevice):
  I2C_ETP_ADDRESS = 21

  RESET_CMD = 0x01000005
  DEVICE_DESC_CMD = 0x0001
  REPORT_DESC_CMD = 0x0002
  ABS_MODE_CMD = 0x00010300
  WAKE_UP_CMD = 0x80000005
  PRODUCT_ID_CMD = 0x0101
  FW_VERSION_CMD = 0x0102
  SM_VERSION_CMD = 0x0103
  IAP_VERSION_CMD = 0x0110
  X_MAX_CMD = 0x0106
  Y_MAX_CMD = 0x0107
  RESOLUTION_CMD = 0x0108
  I2C_XY_TRACENUM_CMD = 0x0105
  EVENT_LEN = 34

  REPORT_DESC_LEN = 158
  DEVICE_DESC_LEN = 30
  MAX_FINGERS = 5
  MAX_PRESSURE = 255
  FWIDTH_REDUCE = 90

  REPORT_ID = 0x5D
  BTN_CLICK_MASK = 0x01

  REPORT_ID_INDEX = 2
  TAP_INFO_INDEX = 3
  I2C_FINGER_DATA_OFFSET = 4
  FINGER_DATA_LEN = 5

  def __init__(self, addr):
    RemoteAardvarkTouchDevice.__init__(self, ElanTouchDevice.I2C_ETP_ADDRESS)
    self._eventQ = queue.Queue()
    
    self._last_event_time = time.time()
    self._event_started = False
  def _CheckReturnVal(self, val, expected, description):
    if val != expected:
      print('Error: The device does not reply to get', description, 'command.')
      sys.exit()

  def _Initialize_Device(self):
    # Elan RESET
    self._i2c_write(ElanTouchDevice.RESET_CMD)
    # Waiting for the device to return resets and sends the confirmation
    self.adapter.aa_sleep_ms(100)
    # Reset flag receive
    self._i2c_read(2)
    # Get device description
    self._i2c_write(ElanTouchDevice.DEVICE_DESC_CMD)
    desc_len, desc_data = self._i2c_read(ElanTouchDevice.DEVICE_DESC_LEN)
    self._CheckReturnVal(desc_len,
                         ElanTouchDevice.DEVICE_DESC_LEN, 'description')

    # Get report description
    self._i2c_write(ElanTouchDevice.REPORT_DESC_CMD)
    report_len, report_data = self._i2c_read(ElanTouchDevice.REPORT_DESC_LEN)
    # Absolute mode activation
    self._i2c_write(ElanTouchDevice.ABS_MODE_CMD)
    # Send wake up command
    self._i2c_write(ElanTouchDevice.WAKE_UP_CMD)
    # Get Product ID
    self._i2c_write(ElanTouchDevice.PRODUCT_ID_CMD)
    product_id_len, product_id = self._i2c_read(2)
    self._CheckReturnVal(product_id_len, 2, 'product ID')
    self._product_id = product_id[0]
    # Get FW version
    self._i2c_write(ElanTouchDevice.FW_VERSION_CMD)
    fw_len, fw_version = self._i2c_read(2)
    self._CheckReturnVal(fw_len, 2, 'FW version')
    self._fw_version = fw_version[0]
    # Get SM version
    self._i2c_write(ElanTouchDevice.SM_VERSION_CMD)
    sm_len, sm_version = self._i2c_read(2)
    self._CheckReturnVal(sm_len, 2, 'SM version')
    self._sm_version = sm_version[0]
    # Get IAP version
    self._i2c_write(ElanTouchDevice.IAP_VERSION_CMD)
    iap_len, iap_version = self._i2c_read(2)
    self._CheckReturnVal(iap_len, 2, 'IAP version')
    self._iap_version = iap_version[0]

  def _GetDimensions(self):
    self._i2c_write(ElanTouchDevice.I2C_XY_TRACENUM_CMD)
    data_len, data_val = self._i2c_read(2)
    self.trace_x = data_val[0] - 1
    self.trace_y = data_val[1] - 1

    # Get X min and max
    self._i2c_write(ElanTouchDevice.X_MAX_CMD)
    data_len, max_x = self._i2c_read(2)
    self._CheckReturnVal(data_len, 2, 'Max X')

    self._max_x = (0x0f & max_x[1]) << 8 | max_x[0]
    x = {'min': 0, 'max': self._max_x}

    # Get Y Min and Max
    self._i2c_write(ElanTouchDevice.Y_MAX_CMD)
    data_len, max_y = self._i2c_read(2)
    self._CheckReturnVal(data_len, 2, 'Max Y')

    self._max_y = (0x0f & max_y[1]) << 8 | max_y[0]
    y = {'min': 0, 'max': self._max_y}

    self._i2c_write(ElanTouchDevice.RESOLUTION_CMD)
    data_len, resolution = self._i2c_read(2)
    self._CheckReturnVal(data_len, 2, 'resolution')

    self._x_resolution = self._ConvertResolution(resolution[0])
    self._y_resolution = self._ConvertResolution(resolution[1])
    x['resolution'] = self._x_resolution
    y['resolution'] = self._y_resolution

    p = {'min': 0, 'max': ElanTouchDevice.MAX_PRESSURE}
    return x, y, p

  def _NextEvent(self, timeout=None):
    if not self._eventQ.empty():
      return self._eventQ.get()
    timestamp = time.time()
    self._event_started = False
    while True:
      input_len, data = self._i2c_read(ElanTouchDevice.EVENT_LEN)
      if input_len < ElanTouchDevice.EVENT_LEN:
        continue
      if data[ElanTouchDevice.REPORT_ID_INDEX] != ElanTouchDevice.REPORT_ID:
        print(' Incompatible format')
        print('        Maybe your device is not isolated and has noise')
      else:
        if time.time() - timestamp > timeout:
          timestamp = time.time()
          self._event_started = False
          return None
        tp_info = data[ElanTouchDevice.TAP_INFO_INDEX]
        # 5 most significant bits of tp_info are mapped to fingers
        if tp_info & 0xf8:
          break

    self._event_started = True
    tp_info = data[ElanTouchDevice.TAP_INFO_INDEX]
    btn_click = (tp_info & ElanTouchDevice.BTN_CLICK_MASK)
    finger_offset = ElanTouchDevice.I2C_FINGER_DATA_OFFSET

    for i in xrange(0, ElanTouchDevice.MAX_FINGERS):
      finger_on = (tp_info >> (3 + i)) & 0x01
      if finger_on:
        pos_x = (((data[0 + finger_offset] & 0xf0) << 4) |
                data[1 + finger_offset])
        pos_y = (((data[0 + finger_offset] & 0x0f) << 8) |
                data[2 + finger_offset])
        pos_y = self._max_y - pos_y
        mk_x = (data[3 + finger_offset] & 0x0f)
        mk_y = (data[3 + finger_offset] >> 4)
        pressure = data[4 + finger_offset]
        area_x = mk_x * ((self._max_x/self.trace_x)
                          - ElanTouchDevice.FWIDTH_REDUCE)
        area_y = mk_y * ((self._max_y/self.trace_y)
                          - ElanTouchDevice.FWIDTH_REDUCE)
        major = max(area_x, area_y)
        event_type = 3
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                         linux_input.ABS_MT_TRACKING_ID, i))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                    linux_input.ABS_MT_POSITION_X, pos_x))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                    linux_input.ABS_MT_POSITION_Y, pos_y))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                    linux_input.ABS_MT_PRESSURE, pressure))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                    linux_input.ABS_MT_TOUCH_MAJOR, major))
        finger_offset += ElanTouchDevice.FINGER_DATA_LEN
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_SYN,
                                    linux_input.SYN_MT_REPORT,0))
    self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_SYN,
                                linux_input.SYN_REPORT,0))
    return self._eventQ.get()

  def _ConvertResolution(self, val):
    # TODO(asimjour): This function looks a bit magical and it has to be fixed.
    # Unfortunately, exactly the same function appears in the driver.
    # So I don't have any explanation for these numbers at this time.
    if val & 0x80:
      val = ~val + 1
      res = (790 - val * 10) * 10 / 254
    else:
      res = (val * 10 + 790) * 10 / 254
    return res

class ElanTouchScreenDevice(RemoteAardvarkTouchDevice):
  I2C_ETS_ADDRESS = 0x10
  HEADER_SIZE = 4
  FW_HDR_TYPE = 0
  FW_HDR_LENGTH = 2
  FW_HDR_COUNT = 1

  MAX_RETRIES = 3
  PACKET_SIZE = 55
  MAX_PACKET_SIZE = 169
  FW_POS_WIDTH = 35
  FW_POS_PRESSURE = 45
  MAX_CONTACT_NUM = 10
  FW_POS_STATE = 1
  FW_POS_XY = 3

  QUEUE_HEADER_SINGLE = 0x62
  QUEUE_HEADER_NORMAL = 0X63
  QUEUE_HEADER_WAIT = 0x64

  RESET_CMD = 0x77777777
  FAST_BOOT_CMD = 0x6E69614D
  QUERY_FW_ID_CMD = 0x0100F053
  QUERY_FW_VERSION_CMD = 0x01000053
  QUERY_TEST_CMD = 0x0100E053
  QUERY_BC_VERSION_CMD = 0x01001053

  GET_RES_CMD = 0x00000000005B
  GET_OSR_CMD = 0x0100D653
  GET_PHYSICAL_SCAN_CMD = 0x0100D753
  GET_PHYSICAL_DRIVE_CMD = 0x0100D853

  CMD_HEADER_HELLO = 0x55
  CMD_HEADER_REK = 0x66
  CMD_HEADER_RESP = 0x52

  def __init__(self, addr):
    RemoteAardvarkTouchDevice.__init__(self,
                                       ElanTouchScreenDevice.I2C_ETS_ADDRESS)
    self.flush_timeout = self.AARDVARK_FLUSH_TIMEOUT
    self._eventQ = queue.Queue()
    self._last_event_time = time.time()
    self._event_started = False

  def _Initialize_Device(self):
    # Reset command
    self._i2c_write(self.RESET_CMD)
    # Fast boot
    self._i2c_write(self.FAST_BOOT_CMD)

    self.adapter.aa_sleep_ms(50)

    # Read the hello packet
    # Hello packet should be (0x55 0x55 0x55 0x55)
    hello_len, hello_packet = self._i2c_read(self.HEADER_SIZE)
    for i in xrange(4):
      if hello_packet[i] != 0x55:
        print('Failed to initialize the device.')
        print('Hello packaet does not have the correct format.')

    # Read FW Id
    self._i2c_repeat_cmd(self.QUERY_FW_ID_CMD)

    # Read FW version
    self._i2c_repeat_cmd(self.QUERY_FW_VERSION_CMD)

    # Query test
    self._i2c_repeat_cmd(self.QUERY_TEST_CMD)

    # Query bc version
    self._i2c_repeat_cmd(self.QUERY_BC_VERSION_CMD)

  def _GetDimensions(self):
    #TODO (asimjour): all templen values should be used for error checking
    templen, self._resolution = self._i2c_execute_cmd_size(self.GET_RES_CMD,
                                                           6, 17)

    row = self._resolution[2] + self._resolution[6] + self._resolution[10]
    col = self._resolution[3] + self._resolution[7] + self._resolution[11]

    # Interpolating  trace
    templen, osr_buf = self._i2c_execute_cmd(self.GET_OSR_CMD)
    osr = osr_buf[3]
    self._x_max = (row - 1) * osr
    self._y_max = (col - 1) * osr

    phy_x_len, phy_x_buf = self._i2c_execute_cmd(self.GET_PHYSICAL_SCAN_CMD)
    phy_y_len, phy_y_buf = self._i2c_execute_cmd(self.GET_PHYSICAL_DRIVE_CMD)
    phy_x = (phy_x_buf[2] << 8) | phy_x_buf[3]
    phy_y = (phy_y_buf[2] << 8) | phy_y_buf[3]
    x_res = self._x_max // phy_x
    y_res = self._y_max // phy_y
    x = {'min': 0, 'max': self._x_max, 'resolution': x_res}
    y = {'min': 0, 'max': self._y_max, 'resolution': y_res}
    p = {'min': 0, 'max': 255}
    return x, y, p

  def _i2c_execute_cmd_size(self, cmd, data_len, out_len):
    data_out = self.adapter.array_u08(data_len)
    for byte_num in range(data_len):
      data_out[byte_num] = (cmd & (0xff << 8 * byte_num)) >> (8 * byte_num)
    retVal = self.adapter.aa_i2c_write(self._handle, self._addr,
                                       self.I2C_NO_FLAGS, data_out)
    resp = self._i2c_read(out_len)
    return resp

  def _i2c_execute_cmd(self, cmd):
    data_len = 6 if cmd >> 32 else 4
    data_out = self.adapter.array_u08(data_len)
    for byte_num in range(data_len):
      data_out[byte_num] = (cmd & (0xff << 8 * byte_num)) >> (8 * byte_num)
    retVal = self.adapter.aa_i2c_write(self._handle, self._addr,
                                       self.I2C_NO_FLAGS, data_out)
    resp = self._i2c_read(data_len)
    return resp

  def _i2c_repeat_cmd(self, cmd):
    for i in xrange(1, self.MAX_RETRIES):
      resp = self._i2c_execute_cmd(cmd)
      if resp:
         return resp
    print('ERROR: exiting after %d retries to issue command %s' %
          (self.MAX_RETRIES, cmd))
    sys.exit()

  def _NextEvent(self, timeout=None):
    if not self._eventQ.empty():
      return self._eventQ.get()

    while True:
      timestamp = time.time()
      if (self._event_started and
          timestamp - self._last_event_time > self.AARDVARK_FLUSH_TIMEOUT):
        self._event_started = False
        return None
      input_len, data = self._i2c_read(self.MAX_PACKET_SIZE)
      if (data[self.FW_HDR_TYPE] == self.CMD_HEADER_HELLO or
          data[self.FW_HDR_TYPE] == self.CMD_HEADER_RESP or
          data[self.FW_HDR_TYPE] == self.CMD_HEADER_REK):
        continue
      if (data[self.FW_HDR_TYPE] == self.QUEUE_HEADER_WAIT):
        print('Waiting...')
        self.adapter.aa_sleep_ms(30)
        continue

      if (data[self.FW_HDR_TYPE] == self.QUEUE_HEADER_SINGLE):
        self._finger_report_parser(data, self.HEADER_SIZE, timestamp)
        if not self._eventQ.empty():
          return self._eventQ.get()
        continue

      if (data[self.FW_HDR_TYPE] == self.QUEUE_HEADER_NORMAL):
        report_count = data[self.FW_HDR_COUNT]
        if report_count > 3:
          print('The report count is greater than the max limit')
          continue
        report_len = data[self.FW_HDR_LENGTH]
        if not report_len == self.PACKET_SIZE * report_count:
          print('Mismatching report length')
          continue
        for i in xrange(report_count):
          self._finger_report_parser(data, self.HEADER_SIZE + i * self.PACKET_SIZE,
                              timestamp)
        if not self._eventQ.empty():
          return self._eventQ.get()
        continue

  def _finger_report_parser(self, data, start_point, timestamp):
    """ This function reads the finger report from data that starts from the
    start_point index. Packets with header QUEUE_HEADER_SINGLE have one finger
    report and packets with QUEUE_HEADER_NORMAL might have up to 3 finger
    reports.
    This function reads the report, builds MtEvents based on the report, and
    puts the MtEvents into the eventQ.
    eventQ is used to send the _NextEvent and building the next snapshot
    """
    n_fingers = data[start_point + self.FW_POS_STATE + 1] & 0x0f
    n_fingers = min(n_fingers, self.MAX_CONTACT_NUM)
    self._last_event_time = timestamp
    if not self._event_started:
      self._eventQ.put(None)
    self._event_started = True
    finger_state = (((data[start_point + self.FW_POS_STATE + 1] & 0x30) << 4) |
                   data[start_point + self.FW_POS_STATE])
    for i in xrange(n_fingers):
      if finger_state & 1:
        finger_start_ptr = start_point + self.FW_POS_XY + i * 3
        finger_data = data[finger_start_ptr: finger_start_ptr + 3]
        x = ((finger_data[0] & 0xf0) << 4) | finger_data[1]
        y = ((finger_data[0] & 0x0f) << 8) | finger_data[2]
        p = data[start_point + self.FW_POS_PRESSURE + i]
        w = data[start_point + self.FW_POS_WIDTH + i]
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                    linux_input.ABS_MT_TRACKING_ID, i + 1))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                    linux_input.ABS_MT_POSITION_X, x))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                    linux_input.ABS_MT_POSITION_Y, y))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                    linux_input.ABS_MT_PRESSURE, p))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                    linux_input.ABS_MT_TOUCH_MAJOR, w))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_SYN,
                                    linux_input.SYN_MT_REPORT, 0))
      finger_state = finger_state >> 1
    self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_SYN,
                                linux_input.SYN_REPORT, 0))

class SynapticsTouchDevice(RemoteAardvarkTouchDevice):
  I2C_SNPTCS_ADDRESS = 0x20

  MAX_F11_TOUCH_WIDTH = 15
  MAX_RETRIES = 10
  PAGE_SELECT_LEN = 2
  PAGES_TO_SERVICE = 10

  MASK_8BIT = 0xFF
  MASK_4BIT = 0x0F
  MASK_3BIT = 0x07
  MASK_2BIT = 0x03

  PDT_END = 0x00D0
  PDT_ENTRY_SIZE = 0x0006
  PDT_START = 0x00E9

  def __init__(self, addr):
    RemoteAardvarkTouchDevice.__init__(self,
                                SynapticsTouchDevice.I2C_SNPTCS_ADDRESS,
                                mt.MtStateMachine.PRESSURE_FROM_MT_TOUCH_MAJOR)
    self.flush_timeout = self.AARDVARK_FLUSH_TIMEOUT
    self._eventQ = queue.Queue()
    self._last_event_time = time.time()
    self._event_started = False

  def _Initialize_Device(self):
    print('initializing the device')
    self.synaptics_rmi4_query_device()
    return None

  """ f-functions have different rmi function implementations.
  SynapticsTouchDevice is designed to support the touchscreens. Therefore,
  only the functions f01 and f11 should be used. Other function are exist
  """
  def synaptics_rmi4_query_device(self):
    SYNAPTICS_RMI4_F = {
        0x01 : self.f01,
        0x11 : self.f11,
        0x12 : self.f12,
        0x1A : self.f1A,
        0x35 : self.f35,
    }
    intr_count = 0
    for page_number in xrange(self.PAGES_TO_SERVICE):
      pdt_entry_addr = self.PDT_START
      for pdt_entry_addr in xrange(self.PDT_START, self.PDT_END,
                                   -self.PDT_ENTRY_SIZE):
        read_addr = pdt_entry_addr | (page_number << 8)
        read_result = self._rmi_i2c_read(read_addr, 6)
        fn_number = read_result[5]
        if fn_number in SYNAPTICS_RMI4_F.keys():
          SYNAPTICS_RMI4_F[fn_number](read_result, page_number)
        intr_count += (fn_number & self.MASK_3BIT)

  """ Before any read or write operation the page address
  is set using this function.

  Every address consist of a page and an offset.
  In order to perform a read/write function on an address, first the page
  should be set, and then the read/write command only contains the offset.
  """
  def _rmi_i2c_set_page(self, rmi_addr):
    data_out = self.adapter.array_u08(self.PAGE_SELECT_LEN)
    data_out[0] = self.MASK_8BIT
    data_out[1] = ((rmi_addr >> 8) & self.MASK_8BIT)

    for i in xrange(self.MAX_RETRIES):
      retVal = self.adapter.aa_i2c_write(self._handle,
                                         self._addr, self.I2C_NO_FLAGS,
                                         data_out)
      if retVal == self.PAGE_SELECT_LEN:
        return retVal

    print('Page Select Error. Was not able to write all the bytes.')
    sys.exit()

  def _rmi_i2c_read(self, rmi_addr, length):
    self._rmi_i2c_set_page(rmi_addr)

    msg = self.adapter.array_u08(1)
    msg[0] = rmi_addr & self.MASK_8BIT

    for i in xrange(self.MAX_RETRIES):
      self.adapter.aa_i2c_write(self._handle, self._addr,
                                self.I2C_NO_FLAGS, msg)
      temp_len, tmp_data = self.adapter.aa_i2c_read(self._handle, self._addr,
                                                self.I2C_NO_FLAGS,
                                                self.adapter.array_u08(length))
      if temp_len == length:
        return tmp_data

    print('I2C Read Error. Was not able to read all the bytes.')
    sys.exit()

  def _rmi_i2c_write(self, rmi_addr, data_out, length):
    self._rmi_i2c_set_page(rmi_addr)

    msg = self.adapter.array_u08(length + 1)
    msg[0] = rmi_addr & self.MASK_8BIT
    for i in xrange(length):
      msg[i + 1] = data_out[i]
    for i in xrange(self.MAX_RETRIES):
      retVal = self.adapter.aa_i2c_write(self._handle,
                                         self._addr, self.I2C_NO_FLAGS, msg)
      if retVal > 0:
        return retVal

    print('I2C Write Error. Was not able to write all the bytes.')
    sys.exit()


  def _GetDimensions(self):
    # TODO (asimjour): resolution values are temporary
    x = {'min': 0, 'max': self._max_x, 'resolution': self._max_x}
    y = {'min': 0, 'max': self._max_y, 'resolution': self._max_y}
    p = {'min': 0, 'max': self.MAX_F11_TOUCH_WIDTH}
    return x, y, p

  def f01(self, data, page_number):
    self.data_base_addr = (data[3] | (page_number << 8)) + 2
    self.f01_found = True

  def f11(self, data, page_number):
    query_0_5 = self._rmi_i2c_read(data[0] | (page_number << 8), 6)
    self._max_fingers = query_0_5[1] & self.MASK_3BIT
    control_6_9 = self._rmi_i2c_read((data[2] + 6) | (page_number << 8), 4)
    self._max_y = control_6_9[0] | ((control_6_9[1] & self.MASK_4BIT) << 8)
    self._max_x = control_6_9[2] | ((control_6_9[3] & self.MASK_4BIT) << 8)
    self.f11_found = True

  # These functions weren't supposed to be used with touch panels.
  # But we should add the support of these functions in the future.
  def f12(self, data, page_number):
    print('f12 found. This functionality is not supported.')
    sys.exit()
  def f1A(self, data, page_number):
    print('f1A found. This functionality is not supported.')
    sys.exit()
  def f35(self, data, page_number):
    print('f35 found. This functionality is not supported.')
    sys.exit()

  def _NextEvent(self, timeout=None):
    if not self._eventQ.empty():
      return self._eventQ.get()

    while True:
      timestamp = time.time()
      if (self._event_started and
          timestamp - self._last_event_time > self.AARDVARK_FLUSH_TIMEOUT):
        self._event_started = False
        return None
      fingers_supported = self._max_fingers
      num_of_finger_status_regs = (fingers_supported + 3) / 4
      sensor_data = self._rmi_i2c_read(self.data_base_addr,
                                       num_of_finger_status_regs)
      if sensor_data[0] or (sensor_data[1] & self.MASK_2BIT):
        break
    self._last_event_time = time.time()
    if not self._event_started:
      self._event_started = True
      return None
    for finger in xrange(self._max_fingers):
      finger_index = finger // 4
      finger_shift = (finger % 4) * 2
      finger_status = (sensor_data[finger_index] >> finger_shift) & self.MASK_2BIT
      # Each 2-bit finger status field represents the following:
      # 00 = finger not present
      # 01 = finger present and data accurate
      # 10 = finger present but data may be inaccurate
      # 11 = reserved
      if finger_status:
        data_offset = (self.data_base_addr + 1 +
                       num_of_finger_status_regs + (finger * 5))
        sensor_finger_data = self._rmi_i2c_read(data_offset, 5)
        y = (sensor_finger_data[0] << 4) | (sensor_finger_data[2] & self.MASK_4BIT)
        x = (sensor_finger_data[1] << 4) | (sensor_finger_data[2] >> 4)
        wx = sensor_finger_data[3] & self.MASK_4BIT
        wy = sensor_finger_data[3] >> 4
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                  linux_input.ABS_MT_TRACKING_ID, finger + 1))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                  linux_input.ABS_MT_POSITION_X, x))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                  linux_input.ABS_MT_POSITION_Y, y))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_ABS,
                                  linux_input.ABS_MT_TOUCH_MAJOR, max(wx, wy)))
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_SYN,
                                  linux_input.SYN_MT_REPORT, 0))
    self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_SYN,
                                linux_input.SYN_REPORT, 0))
    return self._eventQ.get()
