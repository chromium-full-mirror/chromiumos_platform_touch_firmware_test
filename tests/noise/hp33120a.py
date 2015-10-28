# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import serial
import sys
import time

from function_generator import FunctionGenerator


class HP33120A(FunctionGenerator):
  """ This class supplies a FunctionGenerator object that handles communication
  with the HP33120A function generator.

  The HP33120A uses standard SCPI serial communication over RS232 8N2.

  Protocol Manual:
  http://sdphca.ucsd.edu/Lab_Equip_Manuals/Agilent_33120a_Users.pdf
  """
  RESPONSE_DELAY_S = 0.5

  WAVEFORM_CODES = {FunctionGenerator.SQUARE_WAVE: 'SQU',
                    FunctionGenerator.SIN_WAVE: 'SIN'}

  def __init__(self, device_path=None):
    # Connect to the device either by scanning the ttyUSB* devices or using a
    # specifically supplied path.
    possible_paths = [device_path] if device_path else glob.glob('/dev/ttyUSB*')
    self.serial_connection = self._ProbeSerialConnection(possible_paths)
    if not self.serial_connection:
      print 'ERROR: Unable to detect function generator!'

  def __del__(self):
    self.Off()
    if self.serial_connection:
      self.serial_connection.close()

  def IsValid(self):
    return self.serial_connection is not None

  def Off(self):
    """ Turn off the function generator's output. """
    self._SendMessage('APPL:DC 1, 1, 0')

  def GenerateFunction(self, form, frequency, amplitude):
    """ Configure the function that the function generator is outputting. """
    if form not in HP33120A.WAVEFORM_CODES:
      print 'ERROR: Invalid waveform "%s"!' % form

    # Put the generator in "remote mode" so it accepts our commands
    self._SendMessage('SYST:REM')

    # Always set it to Hi-Z mode so we don't accidentally double our voltages.
    # The function generator will otherwise assume there is a 50 Ohm load on the
    # line, and match it internally effectively making a voltage divider of 1/2.
    # Therefore it will compensate by outputting 2x the voltage you expect.
    # In Hi-Z mode this doesn't happen, which is what we want since there is no
    # 50 Ohm load to divide the voltage back down.
    self._SendMessage('OUTP:LOAD INF')

    # Convert the generic waveforms into this generator's code for them
    form_code = HP33120A.WAVEFORM_CODES[form]

    # Configure the output function
    cmd = 'APPL:%s %E, %d' % (form_code, int(frequency), int(amplitude))
    self._SendMessage(cmd)


  def _ProbeSerialConnection(self, possible_paths):
    """ Find which path in possible_paths points to the serial port that the
    function generator is on.  This is done by opening a serial connection with
    each tty device with the configuration parameters for the HP33120A function
    generator, and probing to determine if it's the correct one.  This
    particular function generator responds with "HEWLETT-PACKARD" when you send
    it "*IDN?" If the device doesn't repond that way, we know we have the wrong
    device.

    This function returns a serial connection object for the correct device, or
    None if no function generator was found.
    """
    for device_path in possible_paths:
      ser = serial.Serial(
        port=device_path,
        baudrate=9600,
        stopbits=serial.STOPBITS_TWO,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        timeout=1
      )
      if 'HEWLETT-PACKARD' in self._SendMessage_Aux('*IDN?', ser):
        return ser
      else:
        ser.close()
    return None

  def _SendMessage(self, msg):
    """ Convenience function to automatically send messages to the already
    connected serial port.
    """
    return self._SendMessage_Aux(msg, self.serial_connection)

  def _SendMessage_Aux(self, msg, serial_connection):
    """ Send a message to a function generator at the specified serial
    connection and wait for its response (if there is one).  This function
    either returns the response string or None.
    """
    if not serial_connection:
      return None

    # Newlines are required to terminate each message
    serial_connection.write(msg + '\n')

    if '?' in msg:
      # The function generator only responds to commands with a '?'  If this
      # message has one, we have to wait for the response and return it.
      time.sleep(0.1)
      return serial_connection.readline()
    else:
      # Otherwise, we need to delay for a moment to allow the function generator
      # to execute our command.
      time.sleep(HP33120A.RESPONSE_DELAY_S)
      return None
