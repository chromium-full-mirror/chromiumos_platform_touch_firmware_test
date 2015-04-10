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

import inspect
import os
import Queue
import re
import select
import sys
from subprocess import PIPE, Popen
import time

import colorama as color

import mt
from mt.input import linux_input
from remote import RemoteTouchDevice


try:
  from aardvark_py import *
except ImportError:
  print 'The files "aardvark.so" and "aardvark.so" are needed.'
  print 'You can download these files from the following link.'
  print 'https://www.totalphase.com/downloadable/download/sample/sample_id/16/'
  sys.exit()

class RemoteAardvarkTouchDevice(RemoteTouchDevice):
  """ This class impliments much of the shared functionality among remote
  touch devices that are connected to the system with an Aardvark adapter.
  As such, specific implimentations should derive from this class.
  """

  # This flag indicates that 10 bit address is used
  I2C_FLAG_TEN = 0x10

  # Constants
  I2C_BITRATE = 400
  I2C_AARDVARK_PORT = 0
  AARDVARK_FLUSH_TIMEOUT = 0.5

  def __init__(self, addr, is_touchscreen=False, protocol='auto'):
    self._addr = addr
    self.is_touchscreen = is_touchscreen
    self.state_machine = mt.MtaStateMachine()
    self.flush_timeout = self.AARDVARK_FLUSH_TIMEOUT

    self._Initialize_Aardvark()

    aa_sleep_ms(200)
    self._Initialize_TP()

    # Determine the ranges/resolutions of the various attributes of fingers
    x, y, p = self._GetDimensions()
    self._x_min, self._x_max, self._x_res = x['min'], x['max'], x['resolution']
    self._y_min, self._y_max, self._y_res = y['min'], y['max'], y['resolution']
    self._p_min, self._p_max = p['min'], p['max']

  def __del__(self):
    # Turning off the device
    print "Turning off"
    aa_target_power(self._handle, AA_TARGET_POWER_NONE)

  def _Initialize_Aardvark(self):
    self._port = self.I2C_AARDVARK_PORT
    handle = aa_open(self._port)
    self._handle = handle
    if handle <= 0:
      print color.Fore.RED + 'Unable to open Aardvark device on port'
      print 'Error code = %d' % handle
      sys.exit()
    # Ensure that the I2C subsystem is enabled
    aa_configure(handle,  AA_CONFIG_SPI_I2C)
    # Enable the I2C bus pullup resistors (2.2k resistors).
    aa_i2c_pullup(handle, AA_I2C_PULLUP_BOTH)
    # Enable the Aardvark adapter's power supply.
    aa_target_power(handle, AA_TARGET_POWER_BOTH)
    # Set the bitrate
    bitrate = aa_i2c_bitrate(handle, self.I2C_BITRATE)
    print 'Aardvark initialized'

  def _Initialize_TP(self):
    """ This function should initialize the TP or TS device.
    Depending on the device type this should be implemented different ways.
    It mainly depend on the protocols and the device firmware.
    """
    raise NotImplementedError(RemoteTouchDevice.not_implemented_msg)

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

  def __init__(self, addr, is_touchscreen=False):
    self._addr = ElanTouchDevice.I2C_ETP_ADDRESS
    self.device_num = 0
    self._eventQ = Queue.Queue()

    RemoteAardvarkTouchDevice.__init__(self, self._addr, is_touchscreen)

  def _i2c_write(self, flags, data):
    data_len = 4 if (data & 0xffff0000) else 2
    data_out = array_u08(data_len)
    for byte_num in range(data_len):
      data_out[byte_num] = (data & (0xff << 8 * byte_num)) >> (8 * byte_num)
    retVal = aa_i2c_write(self._handle, self._addr, flags, data_out)
    if retVal != data_len:
      print color.Fore.RED + 'Error '
      print '- Number of bytes written: %d' % retVal
      print '          Make sure that the slave address is correct'
      print '          Slave address: %d' % self._addr
      sys.exit()
    else:
      return retVal

  def _i2c_read(self, flags, num_bytes):
    return aa_i2c_read(self._handle, self._addr, flags, array_u08(num_bytes))

  def _CheckReturnVal(self, val, expected, description):
    if val != expected:
      print color.Fore.RED + 'Error '
      print '   The device does not reply to get', description, 'command.'
      sys.exit()

  def _Initialize_TP(self):
    # Elan RESET
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.RESET_CMD)
    # Waiting for the device to return resets and sends the confirmation
    aa_sleep_ms(100)
    # Reset flag receive
    self._i2c_read(self.I2C_FLAG_TEN, 2)
    # Get device description
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.DEVICE_DESC_CMD)
    desc_len, desc_data = self._i2c_read(self.I2C_FLAG_TEN,
                                         ElanTouchDevice.DEVICE_DESC_LEN)
    self._CheckReturnVal(desc_len,
                         ElanTouchDevice.DEVICE_DESC_LEN, 'description')

    # Get report description
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.REPORT_DESC_CMD)
    report_len, report_data = self._i2c_read(self.I2C_FLAG_TEN,
                                             ElanTouchDevice.REPORT_DESC_LEN)
    # Absolute mode activation
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.ABS_MODE_CMD)
    # Send wake up command
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.WAKE_UP_CMD)
    # Get Product ID
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.PRODUCT_ID_CMD)
    product_id_len, product_id = self._i2c_read(self.I2C_FLAG_TEN, 2)
    self._CheckReturnVal(product_id_len, 2, 'product ID')
    self._product_id = product_id[0]
    # Get FW version
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.FW_VERSION_CMD)
    fw_len, fw_version = self._i2c_read(self.I2C_FLAG_TEN, 2)
    self._CheckReturnVal(fw_len, 2, 'FW version')
    self._fw_version = fw_version[0]
    # Get SM version
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.SM_VERSION_CMD)
    sm_len, sm_version = self._i2c_read(self.I2C_FLAG_TEN, 2)
    self._CheckReturnVal(sm_len, 2, 'SM version')
    self._sm_version = sm_version[0]
    # Get IAP version
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.IAP_VERSION_CMD)
    iap_len, iap_version = self._i2c_read(self.I2C_FLAG_TEN, 2)
    self._CheckReturnVal(iap_len, 2, 'IAP version')
    self._iap_version = iap_version[0]

  def _GetDimensions(self):
    handle = self._handle
    slave_addr = self._addr

    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.I2C_XY_TRACENUM_CMD)
    data_len, data_val = self._i2c_read(self.I2C_FLAG_TEN, 2)
    self.trace_x = data_val[0] - 1
    self.trace_y = data_val[1] - 1

    # Get X min and max
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.X_MAX_CMD)
    data_len, max_x = self._i2c_read(self.I2C_FLAG_TEN, 2)
    self._CheckReturnVal(data_len, 2, 'Max X')

    self._max_x = (0x0f & max_x[1]) << 8 | max_x[0]
    x = {'min': 0, 'max': self._max_x}

    # Get Y Min and Max
    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.Y_MAX_CMD)
    data_len, max_y = self._i2c_read(self.I2C_FLAG_TEN, 2)
    self._CheckReturnVal(data_len, 2, 'Max Y')

    self._max_y = (0x0f & max_y[1]) << 8 | max_y[0]
    y = {'min': 0, 'max': self._max_y}

    self._i2c_write(self.I2C_FLAG_TEN, ElanTouchDevice.RESOLUTION_CMD)
    data_len, resolution = self._i2c_read(self.I2C_FLAG_TEN, 2)
    self._CheckReturnVal(data_len, 2, 'resolution')

    self._x_resolution = self._ConvertResolution(resolution[0])
    self._y_resolution = self._ConvertResolution(resolution[1])
    x['resolution'] = self._x_resolution
    y['resolution'] = self._y_resolution

    p = {'min': 0, 'max': ElanTouchDevice.MAX_PRESSURE}
    return x, y, p

  def _NextEvent(self, timeout=None):
    handle = self._handle
    slave_addr = self._addr
    if not self._eventQ.empty():
      return self._eventQ.get()
    timestamp = time.time()
    self._event_started = False;
    while True:
      input_len, data = self._i2c_read(self.I2C_FLAG_TEN,
                                       ElanTouchDevice.EVENT_LEN)
      if data[ElanTouchDevice.REPORT_ID_INDEX] != ElanTouchDevice.REPORT_ID:
        print (' Incompatible format'
               ' Maybe your device is not isolated and has noise')
      else:
        if time.time() - timestamp > timeout:
          self._event_started = False
          return None
        tp_info = data[ElanTouchDevice.TAP_INFO_INDEX]
        # 5 most significant bits of tp_info are mapped to fingers
        if tp_info & 0xf8:
          break
      aa_sleep_ms(5)

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
                                    linux_input.ABS_MT_TOUCH_MAJOR, major))
        finger_offset += ElanTouchDevice.FINGER_DATA_LEN
        self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_SYN,
                                    linux_input.SYN_MT_REPORT,0))
    self._eventQ.put(mt.MtEvent(timestamp, linux_input.EV_SYN,
                                linux_input.SYN_REPORT,0))
    return self._eventQ.get()

  def NextSnapshot(self, timeout=None):
    event = self._NextEvent(timeout)
    while event:
      self.state_machine.add_event(event)
      if event.is_SYN_REPORT():
        self.most_recent_snapshot = self.state_machine.get_current_snapshot()
        return self.most_recent_snapshot
      event = self._NextEvent(timeout)

    return None

  def _ConvertResolution(self, val):
    # TODO(asimjour): This function looks a bit magical and it has to be fixed.
    # Unfortunately, exactly the same function appears in the driver.
    # So I don't have any explanation for these numbers at this time.
    if val & 0x80:
      val = ~val + 1;
      res = (790 - val * 10) * 10 / 254;
    else:
      res = (val * 10 + 790) * 10 / 254;
    return res
