# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main function for showing centroiding visualizer tool.

It will automatically find the dut connection (via USB cable), build up tunnel,
and open a webplot server daemon and a socket client. After then You can go and
check the visualizing demo on the browser.

For different kind of dut, you may setup a config file for parameters of
visualizer tool.

Example:
  python centroiding_main.py -s 127.0.0.1 -p 8080 -c device.conf

Server will load centroiding/device.conf as config, and build tunnel with port
12345. The webplot will be in http://127.0.0.1:8080 on the browser.

Add argument -l to record centroiding data into file.

Note: this program needs to run adb (Android Debug Bridge) inside the chroot,
please run this command in advance if you do not have adb in your chroot yet.
  sudo emerge android-tools

"""
import argparse
from datetime import datetime
import os
import subprocess
import time

from centroiding import (CentroidingDataParser,
                         CentroidingDataReceiver,
                         CentroidingDevice)
from webplot import Webplot

ADB_GETSTATE_RETRIES = 50
ADB_FORWARD_RETRIES = 10
SEPARATION_LINEWIDTH = 70


def EstablishADBConnectionTunnel(port):
  """Builds up tunnel to dut by ADB via connection cable.

  1. Poll device presence by 'adb get-state'. This command will return 'device'
     once it detects a dut connected.

  2. Make socket connection tunnel by 'adb forward tcp:<port> tcp:<port>'.

  3. Poll until tunnel established by checking 'adb forward --list' result.

  Args:
    port: port number of tunneling between device and server.

  Returns:
    Return False if errors happen; otherwise return True.
  """
  print('\n' + '-' * SEPARATION_LINEWIDTH)

  # To prevent adb no permissions issue, it needs sudo to start adb server.
  os.system('sudo adb kill-server')
  os.system('sudo adb start-server')

  def _GetDeviceOnline():
    return subprocess.check_output(['adb', 'get-state']).strip() == 'device'

  if not _GetDeviceOnline():
    print('Currently no device attached!\nPlease attach your testing device...')
    retry_times = 0
    while True:
      time.sleep(0.2)
      if _GetDeviceOnline():
        break
      retry_times += 1
      if retry_times > ADB_GETSTATE_RETRIES:
        print('Timeout polling for testing device (%.1f seconds)...' % (
            0.2 * ADB_GETSTATE_RETRIES))
        return False

  print('\nDevice is attached.\n')
  print('Try to build tunnel port %d between device and server...' % port)

  retry_times = 0
  while True:
    subprocess.check_call(
        ['adb', 'forward', 'tcp:%d' % port, 'tcp:%d' % port])
    time.sleep(0.2)
    get_port = subprocess.check_output(
        ['adb', 'forward', '--list']).strip()
    if 'tcp:%d' % port in get_port:
      break
    retry_times += 1
    if retry_times > ADB_FORWARD_RETRIES:
      return False

  print('\nTunnel is established successfully.\n')
  return True


def _ParseArguments():
  """Parses the command line options."""
  parser = argparse.ArgumentParser(description='Centroiding Main')

  parser.add_argument('-s', '--server_addr', default='127.0.0.1',
                      help='the address the webplot http server listens to')
  parser.add_argument('-p', '--server_port', default=8080, type=int,
                      help='the port the web server listens to (default: 8080)')
  parser.add_argument('-f', '--dut_forward_port', default=12345, type=int,
                      help='the forwarding port for centroiding socket server '
                           '(default: 12345)')
  parser.add_argument('-c', '--config', default='tango.conf', type=str,
                      help='config file name of device for centroiding '
                           'visualizing tool parameters.')
  parser.add_argument('-l', '--log_data', action='store_true',
                      help='log centroiding data and save to file in /tmp/.')
  parser.add_argument('--fps', default=0, type=int,
                      help='the target frame rate of visualizer plotting, set '
                           '0 for keeping same as centroiding processing frame '
                           'rate.')

  args = parser.parse_args()
  return args


def Main():
  args = _ParseArguments()

  print('\n' + '-' * SEPARATION_LINEWIDTH + '\n')
  print('**** Centroiding Data Visualizing Tool ****')
  print('webplot server address:', args.server_addr)
  print('webplot server port:', args.server_port)

  print('\n' + '-' * SEPARATION_LINEWIDTH + '\n')
  print('dut socket forwarding port:', args.dut_forward_port)
  print('  (this port will be tunneled between dut and server)\n')
  print('dut config file:', args.config)

  device = CentroidingDevice(config=args.config)

  print('  - device name:', device.device)
  print('  - data_scale:', device.data_scale)
  print('  - data_offset:', device.data_offset)
  print('  - width:', device.width)
  print('  - height:', device.height)

  if not EstablishADBConnectionTunnel(args.dut_forward_port):
    print('Connection to device failed. Task is aborted...')
    return

  print('\n' + '-' * SEPARATION_LINEWIDTH + '\n')
  print('webplot server has started...')
  print('port %d is listening on sockets from dut...' % args.dut_forward_port)
  print(('check http://%s:%d on browser of your device to view the plot...\n' %
      (args.server_addr, args.server_port)))

  if args.log_data:
    time_now = datetime.now().strftime('%Y%m%d%H%M%S')
    save_data = os.path.join('/tmp', '%s_%s.dat' % (device.device, time_now))
  else:
    save_data = None

  # Instantiate a webplot server daemon and start it.
  plot_server = Webplot(args.server_addr, args.server_port, device,
                        logging=True, is_behind_iptables_firewall=False,
                        is_centroiding=True)
  plot_server.start()

  receiver = CentroidingDataReceiver(
      '127.0.0.1', args.dut_forward_port, plot_server,
      save_data=save_data, plot_fps=args.fps)
  receiver.StartReceive()

  if args.log_data:
    print('\ncentroiding raw data are saved into file %s\n' % save_data)
    print('parsing saved raw data to analytical format...')
    data_parser = CentroidingDataParser(save_data, device)
    data_parser.Parse()
    print('parse finished...')


if __name__ == '__main__':
  Main()

