#!/usr/bin/env python2
#
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module launches the cherrypy server for HeatMapPlot and sets up\
web sockets to handle the messages between the clients and the server.

This module use remote/remote_device to dump heatmap from remote device or local
device. Currently, this module device with profile sensor. The heatmap is
reported as array of x readings and y readings. Heatmap data is sent to frontend
through webscoket. Then javascript will plot the data as bar charts.
"""

from __future__ import print_function
import argparse
import logging
import os
import re
import subprocess
import threading

import cherrypy

from ws4py import configure_logger
from ws4py.messaging import TextMessage
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket

from remote.remote_device import RemoteHeatMapDevice

def SimpleSystem(cmd):
  """Execute a system command."""
  ret = subprocess.call(cmd, shell=True)
  if ret:
    logging.warning('Command (%s) failed (ret=%s).', cmd, ret)

def SimpleSystemOutput(cmd):
  """Execute a system command and get its output."""
  try:
    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, _ = proc.communicate()
  except Exception as e:
    logging.warning('Command (%s) failed (%s).', cmd, e)
  else:
    return None if proc.returncode else stdout.strip()


def IsDestinationPortEnabled(port):
  """Check if the destination port is enabled in iptables.

  If port 8000 is enabled, it looks like
    ACCEPT  tcp  --  0.0.0.0/0  0.0.0.0/0  ctstate NEW tcp dpt:8000
  """
  pattern = re.compile(r'ACCEPT\s+tcp.+\s+ctstate\s+NEW\s+tcp\s+dpt:%d' % port)
  rules = SimpleSystemOutput('sudo iptables -L INPUT -n --line-number')
  for rule in rules.splitlines():
    if pattern.search(rule):
      return True
  return False


def EnableDestinationPort(port):
  """Enable the destination port for input traffic in iptables."""
  if IsDestinationPortEnabled(port):
    cherrypy.log('Port %d has been already enabled in iptables.' % port)
  else:
    cherrypy.log('Adding a rule to accept incoming connections on port %d in '
                 'iptables.' % port)
    cmd = ('sudo iptables -A INPUT -p tcp -m conntrack --ctstate NEW '
           '--dport %d -j ACCEPT' % port)
    if SimpleSystem(cmd) != 0:
      raise 'Failed to enable port in iptables: %d.' % port


def InterruptHandler():
  """An interrupt handler for both SIGINT and SIGTERM.

  When interrupt is seen, cherrypy engine will exit.
  """
  cherrypy.log('Cherrypy engine exit due to interrupt.')
  cherrypy.engine.exit()

class HeatMapWSHandler(WebSocket):
  """The web socket handler for HeatMap."""

  setPoleCallback = None
  def opened(self):
    """This method is called when the handler is opened."""
    cherrypy.log('WS handler is opened!')

  def received_message(self, msg):
    """A callback for received message."""
    data = msg.data.split(':', 1)
    mtype = data[0].lower()
    content = data[1] if len(data) == 2 else '0'

    if mtype == 'setpole':
      # code to set pole
      pole = int(content)
      cherrypy.log("Setting pole to %d" % pole)
      if HeatMapWSHandler.setPoleCallback:
        HeatMapWSHandler.setPoleCallback(pole)

class HeatMapRoot(object):
  """A class to handle requests about docroot."""

  def __init__(self, ip, port):
    self.ip = ip
    self.port = port
    self.scheme = 'ws'
    cherrypy.log('Root address: (%s, %s)' % (ip, str(port)))
    cherrypy.log('scheme: %s' % self.scheme)

  @cherrypy.expose
  def index(self):
    """This is the default index.html page."""
    websocket_dict = {
        'websocketUrl': '%s://%s:%s/ws' % (self.scheme, self.ip, self.port),
    }
    root_page = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'heatmap.html')
    with open(root_page) as f:
      return f.read() % websocket_dict

  @cherrypy.expose
  def ws(self):
    """This handles the request to create a new web socket per client."""
    cherrypy.log('A new client requesting for WS')
    cherrypy.log('WS handler created: %s' % repr(cherrypy.request.ws_handler))

class HeatMapPlot(threading.Thread):
  """The server handling the Plotting of HeatMap."""
  def __init__(self, server_addr, server_port, device,
               is_behind_iptables_firewall=False):
    self._server_addr = server_addr
    self._server_port = server_port
    self._device = device
    super(HeatMapPlot, self).__init__(name='HeatMap thread')

    self.daemon = True
    self._prev_tids = []

    # Allow input traffic in iptables, if the user has specified.  This setting
    # should be used if HeatMap is being run directly on a chromebook, but it
    # requires root access, so we don't want to use it all the time.
    if is_behind_iptables_firewall:
      EnableDestinationPort(self._server_port)

    cherrypy.config.update({
        'server.socket_host': self._server_addr,
        'server.socket_port': self._server_port,
    })

    WebSocketPlugin(cherrypy.engine).subscribe()
    cherrypy.tools.websocket = WebSocketTool()

    # If the cherrypy server exits for whatever reason, close the device
    # for required cleanup. Otherwise, there might exist local/remote
    # zombie processes.
    cherrypy.engine.subscribe('exit', self._device.__del__)

    cherrypy.engine.signal_handler.handlers['SIGINT'] = InterruptHandler
    cherrypy.engine.signal_handler.handlers['SIGTERM'] = InterruptHandler

  def run(self):
    """Start the cherrypy engine."""
    root = HeatMapRoot(self._server_addr, self._server_port)

    cherrypy.quickstart(
        root,
        '',
        config={
            '/': {
                'tools.staticdir.root':
                    os.path.abspath(os.path.dirname(__file__)),
                'tools.staticdir.on': True,
                'tools.staticdir.dir': '',
            },
            '/ws': {
                'tools.websocket.on': True,
                'tools.websocket.handler_cls': HeatMapWSHandler,
            },
        }
    )

  def StartBridgeHeatMapEvents(self):
    """Start to read heatmap events and send it over ws."""
    cherrypy.log('Start to route heatmap events')

    try:
      while True:
        event = self._device.NextEvent()
        if event:
          cherrypy.engine.publish('websocket-broadcast', event.ToJson())
        else:
          cherrypy.log('Fail to get heatmap event, check if heatmap_tool is on\
your device.')
          cherrypy.engine.exit()
    except KeyboardInterrupt:
      cherrypy.log('Keyboard Interrupt accepted')
      cherrypy.log('HeatMapPlot is being terminated')
      cherrypy.engine.exit()

def _CheckLegalUser():
  """If this program is run in chroot, it should not be run as root for\
security reason."""
  if os.path.exists('/etc/cros_chroot_version') and os.getuid() == 0:
    print ('You should run heatmapplot in chroot as a regular user '
           'instead of as root.\n')
    exit(1)


def _ParseArguments():
  """Parse the command line options."""
  parser = argparse.ArgumentParser(description='HeatMap Server')
  parser.add_argument('-d', '--dut_addr', default=None,
                      help='the address of the dut')
  parser.add_argument('-p', '--server_port', default=8080, type=int,
                      help='the port the web server listens to (default: 8080)')
  parser.add_argument('--behind_firewall', action='store_true',
                      help=('With this flag set, you tell webplot to add a '
                            'rule to iptables to allow incoming traffic to '
                            'the webserver.  If you are running HeatMapPlot on '
                            'a chromebook, this is needed.'))
  parser.add_argument('-s', '--server_addr', default='127.0.0.1',
                      help='the address the webplot http server listens to')
  args = parser.parse_args()
  return args


def Main():
  """The main function to launch HeatMap service."""
  _CheckLegalUser()

  configure_logger(level=logging.ERROR)
  args = _ParseArguments()

  print('\n' + '-' * 70)
  cherrypy.log('dut address: %s' % args.dut_addr)
  cherrypy.log('web server address: %s' % args.server_addr)
  cherrypy.log('web server port: %s' % args.server_port)
  print('-' * 70 + '\n\n')

  if args.server_port == 80:
    url = 'http://%s' % args.server_addr
  else:
    url = 'http://%s:%d' % (args.server_addr, args.server_port)

  msg = 'Type "%s" in browser %s to see heatmap.\n'
  if args.server_addr == '127.0.0.1':
    which_machine = 'on the webplot server machine'
  else:
    which_machine = 'on any machine'

  print('*' * 70)
  print(msg % (url, which_machine))
  print('*' * 70 + '\n\n')

  # Instantiate a touch device.
  addr = args.dut_addr if args.dut_addr else '127.0.0.1'

  device = RemoteHeatMapDevice(addr)

  # Setup the call back function to set pole to device.
  HeatMapWSHandler.setPoleCallback = device.SetPole

  # Instantiate a webplot server daemon and start it.
  HeatMap = HeatMapPlot(args.server_addr, args.server_port, device,
                        is_behind_iptables_firewall=args.behind_firewall)

  HeatMap.start()
  HeatMap.StartBridgeHeatMapEvents()

if __name__ == '__main__':
  Main()
