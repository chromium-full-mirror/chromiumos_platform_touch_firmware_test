# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module includes the python hidraw libray

The hidraw interface is a straight forward translation of linux hidraw c
interface. Running this file directly, it will print all the hidraw device.
"""

from __future__ import print_function
import array
import ctypes
import fcntl
import glob
from input.linux_ioctl import IOC, IOC_READ, IOC_WRITE

HID_MAX_DESCRIPTOR_SIZE = 4096

class HIDRawReportDescriptor(ctypes.Structure):
  """A class for linux hidraw_report_descriptor

  struct hidraw_report_descriptor {
    __u32 size;
    __u8 value[HID_MAX_DESCRIPTOR_SIZE];
  }
  """

  _fields_ = [
      ('size', ctypes.c_uint),
      ('value', ctypes.c_ubyte * HID_MAX_DESCRIPTOR_SIZE),
  ]


class HIDRawDevInfo(ctypes.Structure):
  """A class for linux hidraw_devinfo

  struct hidraw_devinfo {
    __u32 bustype;
    __s16 vendor;
    __s16 product;
  }
  """

  _fields_ = [
      ('bustype', ctypes.c_uint),
      ('vendor', ctypes.c_ushort),
      ('product', ctypes.c_ushort),
  ]


# The following code are from hidraw.h

HIDIOCGRDESCSIZE = IOC(IOC_READ, 'H', 0x01, ctypes.sizeof(ctypes.c_uint))
HIDIOCGRDESC = IOC(IOC_READ, 'H', 0x02,
                   ctypes.sizeof(HIDRawReportDescriptor))
HIDIOCGRAWINFO = IOC(IOC_READ, 'H', 0x03, ctypes.sizeof(HIDRawDevInfo))

def HIDIOCGRAWNAME(length):
  return IOC(IOC_READ, 'H', 0x04, length)

def HIDIOCGRAWPHYS(length):
  return IOC(IOC_READ, 'H', 0x05, length)

def HIDIOCSFEATURE(length):
  return IOC(IOC_READ | IOC_WRITE, 'H', 0x06, length)

def HIDIOCGFEATURE(length):
  return IOC(IOC_READ | IOC_WRITE, 'H', 0x07, length)

HIDRAW_FIRST_MINOR = 0
HIDRAW_MAX_DEVICES = 64
HIDRAW_BUFFER_SIZE = 64


class HIDRaw(object):
  """A class used to access hidraw interface."""

  def __init__(self, path):
    self.path = path
    self.f = open(path, 'rb+', buffering=0)
    self._ioctl_raw_report_descritpor()
    self._ioctl_info()
    self._ioctl_name()
    self._ioctl_physical_addr()

  def __exit__(self, *_):
    if self.f and not self.f.closed:
      self.f.close()

  def send_feature_report(self, report_buffer):
    fcntl.ioctl(self.f, HIDIOCSFEATURE(len(report_buffer)), report_buffer, 1)

  def get_feature_report(self, report_num, length):
    report_buffer = array.array('B', [0] * length)
    report_buffer[0] = report_num
    fcntl.ioctl(self.f, HIDIOCGFEATURE(length), report_buffer, 1)
    return buffer

  def read(self, size):
    return self.f.read(size)

  def _ioctl_raw_report_descritpor(self):
    """Queries device file for the report descriptor"""
    descriptor_size = ctypes.c_uint()
    fcntl.ioctl(self.f, HIDIOCGRDESCSIZE, descriptor_size, 1)

    self.descriptor = HIDRawReportDescriptor()
    self.descriptor.size = descriptor_size
    fcntl.ioctl(self.f, HIDIOCGRDESC, self.descriptor, 1)

  def _ioctl_info(self):
    """Queries device file for the dev info"""
    self.devinfo = HIDRawDevInfo()
    fcntl.ioctl(self.f, HIDIOCGRAWINFO, self.devinfo, 1)

  def _ioctl_name(self):
    """Queries device file for the dev name"""
    name_len = 255
    name = array.array('B', [0] * name_len)
    name_len = fcntl.ioctl(self.f, HIDIOCGRAWNAME(name_len), name, 1)
    self.name = name[0:name_len-1].tostring()

  def _ioctl_physical_addr(self):
    """Queries device file for the dev physical addr"""
    addr_len = 255
    addr = array.array('B', [0] * addr_len)
    addr_len = fcntl.ioctl(self.f, HIDIOCGRAWPHYS(addr_len), addr, 1)
    self.physic_addr = addr[0:addr_len-1].tostring()


def main():
  """Function to interactively select a hidraw device"""
  for path in glob.glob('/dev/hidraw*'):
    hid = HIDRaw(path)
    print('Device at:', path)
    print('   ', hid.physic_addr, ':', hid.name)
    print('   ', "Vendor:", hex(hid.devinfo.vendor))
    print('   ', 'Product:', hex(hid.devinfo.product))

if __name__ == '__main__':
  main()
