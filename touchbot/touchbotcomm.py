# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import select
import socket


TOUCHBOT_DEBUG = False
RECV_CHUNK_SIZE = 1024
MESSAGE_TERMINATOR = '\n'


class TouchbotComm:
  """ Touchbot II Low-level communications module

  This class handles the low-level communications between the controller
  and the robot.  Touchbot II uses an Ethernet link to accept commands and
  send responses to those commands.  Here we set up a socket and initialize
  the robot and through the member functions allow direct access to sending
  whatever commands you want

    botcomm = TouchbotComm('192.168.0.1')
    error_code, data = botcomm.SendCmd('freemode', -1)
    ...
  """
  def __init__(self, ip_addr, port):
    """ Initiate contact with the TouchbotII over ethernet """
    self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_DONTROUTE, 1)

    self.soc.connect((ip_addr, port))

    self.SendCmd('version')  # Print the version string
    self.SendCmd('mode', 0)  # Set the robot to PC communication mode
    self.SendCmd('attach', 1)  # Connect to the Touchbot (robot 1)
    self.SendCmd('hp', 1, 10)  # Turn on 'high power' mode

  def __del__(self):
    """ Close the socket before cleaning up the object """
    self.soc.close()

  def SendCmd(self, cmd, *args):
    """ Send a command to the TouchbotII
    Commands are newline terminated strings of the format:
      'command arg0 arg1 ... argn'
    eg:
      'mode 0'
    Then wait for the robot's response and return that
    """
    string_args = [str(arg) for arg in args]
    cmd_string = ' '.join([cmd] + string_args) + MESSAGE_TERMINATOR
    self.DisplayCmd(cmd_string)
    self.soc.send(cmd_string)
    return self.GetResponse()

  def SendFingerCmd(self, cmd):
    """ Send a command throught the robot to the fingers """
    cmd_string = 'CustomSerial ' + cmd + MESSAGE_TERMINATOR

    if TOUCHBOT_DEBUG:
      print '[FINGER]\t"%s"' % cmd

    self.soc.send(cmd_string)
    ready_to_read, _, _ = select.select([self.soc], [], [], 5)
    if self.soc in ready_to_read:
      return self.soc.recv(RECV_CHUNK_SIZE)
    return None

  def GetResponse(self):
    """ Listen on the socket for a response from the TouchbotII
    parse the response and return it.  Responses are of the format:
      'response_code data'
      eg: For a command requesting the cartesian coordinates 'wherec'
      '0 23.4 280.3 31.2 130.0 180.0 90.0'
    """
    response = self.soc.recv(RECV_CHUNK_SIZE)
    while response[-1] != MESSAGE_TERMINATOR:
      response += self.soc.recv(RECV_CHUNK_SIZE)

    split_results = response.split(' ', 1)
    raw_error_code = split_results[0]
    num_results = len(split_results)
    raw_data = split_results[1] if num_results == 2 else MESSAGE_TERMINATOR
    error_code, data = int(raw_error_code), raw_data[:-1]
    self.DisplayResponse(error_code, data)

    return error_code, data

  def DisplayCmd(self, cmd_string):
    """ Print the name of a command to the console before sending it """
    if TOUCHBOT_DEBUG:
      print '[COMMAND]\t"%s"' % cmd_string[:-1]

  def DisplayResponse(self, error_code, data):
    """ Display the message the robot returned and indicate any errors """
    if TOUCHBOT_DEBUG:
      success = (error_code == 0)
      formatter = '[SUCCESS (%d)]\t%s' if success else '[ERROR(%d)]\t%s'
      print formatter % (error_code, data)
