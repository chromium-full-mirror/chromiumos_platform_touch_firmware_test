# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module launches the cherrypy server for webplot and sets up
web sockets to handle the messages between the clients and the server.
"""

import argparse
import base64
import json
import logging
import os
import re
import subprocess
import threading

import cherrypy

import remote

from ws4py import configure_logger
from ws4py.messaging import TextMessage
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket

from remote.remote import ChromeOSTouchDevice, AndroidTouchDevice


# The WebSocket connection state object.
state = None

# The touch events are saved in this file as default.
SAVED_FILE = '/tmp/webplot.dat'
SAVED_IMAGE = '/tmp/webplot.png'


def InterruptHandler():
  """An interrupt handler for both SIGINT and SIGTERM

  The stop procedure triggered is as follows:
  1. This handler sends a 'quit' message to the listening client.
  2. The client sends the canvas image back to the server in its quit message.
  3. WebplotWSHandler.received_message() saves the image.
  4. WebplotWSHandler.received_message() handles the 'quit' message.
     The cherrypy engine exits if this is the last client.
  """
  cherrypy.log('Cherrypy engine is sending quit message to clients.')
  cherrypy.engine.publish('websocket-broadcast', TextMessage('quit'))


class WebplotWSHandler(WebSocket):
  """The web socket handler for webplot."""

  def opened(self):
    """This method is called when the handler is opened."""
    cherrypy.log('WS handler is opened!')

  def received_message(self, msg):
    """A callback for received message."""
    cherrypy.log('Received message: %s' % str(msg.data))
    data = msg.data.split(':', 1)
    mtype = data[0].lower()
    content = data[1] if len(data) == 2 else None
    if mtype == 'quit':
      # A shutdown message requested by the user.
      cherrypy.log('Save the image to %s' % SAVED_IMAGE)
      self.SaveImage(content, SAVED_IMAGE)
      cherrypy.log('The user requests to shutdown the cherrypy server....')
      state.DecCount()
    elif mtype == 'save':
      cherrypy.log('Save data to %s' % content)
    else:
      cherrypy.log('Unknown message type: %s' % mtype)

  def closed(self, code, reason="A client left the room."):
    """This method is called when the handler is closed."""
    cherrypy.log('A client requests to close WS.')
    cherrypy.engine.publish('websocket-broadcast', TextMessage(reason))

  @staticmethod
  def SaveImage(image_data, image_file):
    """Decoded the base64 image data and save it in the file."""
    with open(image_file, 'w') as f:
      f.write(base64.b64decode(image_data))


class TouchDeviceWrapper(object):
  """This is a wrapper of remote.RemoteTouchDevice.

  It handles the instantiation of different device types, and the beginning
  and ending of the event stream.
  """

  def __init__(self, dut_type, addr, is_touchscreen):
    if dut_type == 'chromeos':
      self.device = ChromeOSTouchDevice(addr, is_touchscreen)
    else:
      self.device = AndroidTouchDevice(addr, True)

  def close(self):
    """ Close the device gracefully. """
    if self.device.event_stream_process:
      self.device.__del__()

  def __str__(self):
    return '\n  '.join(sorted([str(slot) for slot in self.slots.values()]))


def ThreadedGetLiveStreamSnapshots(device, saved_file):
  """A thread to poll and get live stream snapshots continuously."""

  def _ConvertNamedtupleToDict(snapshot, prev_tids):
    """Convert namedtuples to ordinary dictionaries and add leaving slots.

    This is to make a snapshot json serializable. Otherwise, the namedtuples
    would be transmitted as arrays which is less readable.

    A snapshot looks like
      MtSnapshot(
          syn_time=1420524008.368854,
          button_pressed=False,
          fingers=[
              MtFinger(tid=162, slot=0, syn_time=1420524008.368854, x=524,
                        y=231, pressure=45),
              MtFinger(tid=163, slot=1, syn_time=1420524008.368854, x=677,
                        y=135, pressure=57)
          ]
      )

    Note:
    1. that there are two levels of namedtuples to convert.
    2. The leaving slots are used to notify javascript that a finger is leaving
       so that the corresponding finger color could be released for reuse.
    """
    # Convert MtSnapshot.
    converted = dict(snapshot.__dict__.items())

    # Convert MtFinger.
    converted['fingers'] = [dict(finger.__dict__.items())
                            for finger in converted['fingers']]
    converted['raw_events'] = [str(event) for event in converted['raw_events']]

    # Add leaving fingers to notify js for reclaiming the finger colors.
    curr_tids = [finger['tid'] for finger in converted['fingers']]
    for tid in set(prev_tids) - set(curr_tids):
      leaving_finger = {'tid': tid, 'leaving': True}
      converted['fingers'].append(leaving_finger)

    return converted, curr_tids

  def _GetSnapshots():
    """Get live stream snapshots."""
    cherrypy.log('Start getting the live stream snapshots....')
    prev_tids = []
    with open(saved_file, 'w') as f:
      while True:
        snapshot = device.device.NextSnapshot()
        # TODO: remove the next line when NextSnapshot returns the raw events.
        events = []
        if snapshot:
          f.write('\n'.join(events) + '\n')
          f.flush()
          snapshot, prev_tids = _ConvertNamedtupleToDict(snapshot, prev_tids)
          cherrypy.engine.publish('websocket-broadcast', json.dumps(snapshot))

  get_snapshot_thread = threading.Thread(target=_GetSnapshots,
                                         name='_GetSnapshots')
  get_snapshot_thread.daemon = True
  get_snapshot_thread.start()


class ConnectionState(object):
  """A ws connection state object for shutting down the cherrypy server.

  It shuts down the cherrypy server when the count is down to 0 and is not
  increased before the shutdown_timer expires.

  Note that when a page refreshes, it closes the WS connection first and
  then re-connects immediately. This is why we would like to wait a while
  before actually shutting down the server.
  """
  TIMEOUT = 1.0

  def __init__(self):
    self.count = 0;
    self.lock = threading.Lock()
    self.shutdown_timer = None

  def IncCount(self):
    """Increase the connection count, and cancel the shutdown timer if exists.
    """
    self.lock.acquire()
    self.count += 1;
    cherrypy.log('  WS connection count: %d' % self.count)
    if self.shutdown_timer:
      self.shutdown_timer.cancel()
      self.shutdown_timer = None
    self.lock.release()

  def DecCount(self):
    """Decrease the connection count, and start a shutdown timer if no other
    clients are connecting to the server.
    """
    self.lock.acquire()
    self.count -= 1;
    cherrypy.log('  WS connection count: %d' % self.count)
    if self.count == 0:
      self.shutdown_timer = threading.Timer(self.TIMEOUT, self.Shutdown)
      self.shutdown_timer.start()
    self.lock.release()

  def Shutdown(self):
    """Shutdown the cherrypy server."""
    cherrypy.log('Shutdown timer expires. Cherrypy server for Webplot exits.')
    cherrypy.engine.exit()


class Root(object):
  """A class to handle requests about docroot."""

  def __init__(self, ip, port, touch_min_x, touch_max_x, touch_min_y,
               touch_max_y, touch_min_pressure, touch_max_pressure):
    self.ip = ip
    self.port = port
    self.touch_min_x = touch_min_x
    self.touch_max_x = touch_max_x
    self.touch_min_y = touch_min_y
    self.touch_max_y = touch_max_y
    self.touch_min_pressure = touch_min_pressure
    self.touch_max_pressure = touch_max_pressure
    self.scheme = 'ws'
    cherrypy.log('Root address: (%s, %s)' % (ip, str(port)))
    cherrypy.log('scheme: %s' % self.scheme)

  @cherrypy.expose
  def index(self):
    """This is the default index.html page."""
    websocket_dict = {
      'websocketUrl': '%s://%s:%s/ws' % (self.scheme, self.ip, self.port),
      'touchMinX': str(self.touch_min_x),
      'touchMaxX': str(self.touch_max_x),
      'touchMinY': str(self.touch_min_y),
      'touchMaxY': str(self.touch_max_y),
      'touchMinPressure': str(self.touch_min_pressure),
      'touchMaxPressure': str(self.touch_max_pressure),
    }
    root_page = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'webplot.html')
    with open(root_page) as f:
      return f.read() % websocket_dict

  @cherrypy.expose
  def ws(self):
    """This handles the request to create a new web socket per client."""
    cherrypy.log('A new client requesting for WS')
    cherrypy.log('WS handler created: %s' % repr(cherrypy.request.ws_handler))
    state.IncCount()


def SimpleSystem(cmd):
  """Execute a system command."""
  ret = subprocess.call(cmd, shell=True)
  if ret:
    logging.warning('Command (%s) failed (ret=%s).', cmd, ret)
  return ret


def SimpleSystemOutput(cmd):
  """Execute a system command and get its output."""
  try:
    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, _ = proc.communicate()
  except Exception, e:
    logging.warning('Command (%s) failed (%s).', cmd, e)
  else:
    return None if proc.returncode else stdout.strip()


def IsDestinationPortEnabled(port):
  """Check if the destination port is enabled in iptables.

  If port 8000 is enabled, it looks like
    ACCEPT  tcp  --  0.0.0.0/0  0.0.0.0/0  ctstate NEW tcp dpt:8000
  """
  pattern = re.compile('ACCEPT\s+tcp.+\s+ctstate\s+NEW\s+tcp\s+dpt:%d' % port)
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
    cherrypy.log('To enable port %d in iptables.' % port)
    cmd = ('sudo iptables -A INPUT -p tcp -m conntrack --ctstate NEW '
           '--dport %d -j ACCEPT' % port)
    if SimpleSystem(cmd) != 0:
      raise Error('Failed to enable port in iptables: %d.' % port)


def _ParseArguments():
  """Parse the command line options."""
  parser = argparse.ArgumentParser(description='Webplot Server')
  parser.add_argument('-d', '--dut_addr', default='localhost',
                      help='the address of the dut')
  parser.add_argument('-s', '--server_addr', default='localhost',
                      help='the address the webplot http server listens to')
  parser.add_argument('-p', '--server_port', default=80, type=int,
                      help='the port the web server to listen to (default: 80)')
  parser.add_argument('--is_touchscreen', help='the DUT is touchscreen',
                      action='store_true')
  parser.add_argument('-t', '--dut_type', default='chromeos',
                      help='dut type: chromeos, android')
  args = parser.parse_args()
  return args


def Main():
  """The main function to launch webplot service."""
  global state

  configure_logger(level=logging.DEBUG)
  args = _ParseArguments()

  print '\n' + '-' * 70
  cherrypy.log('dut machine type: %s' % args.dut_type)
  cherrypy.log('dut\'s touch device: %s' %
               ('touchscreen' if args.is_touchscreen else 'touchpad'))
  cherrypy.log('dut address: %s' % args.dut_addr)
  cherrypy.log('web server address: %s' % args.server_addr)
  cherrypy.log('web server port: %s' % args.server_port)
  cherrypy.log('touch events are saved in %s' % SAVED_FILE)
  print '-' * 70 + '\n\n'

  if args.server_port == 80:
    url = args.server_addr
  else:
    url = '%s:%d' % (args.server_addr, args.server_port)

  msg = 'Type "%s" in browser %s to see finger traces.\n'
  if args.server_addr == 'localhost':
    which_machine = 'on the webplot server machine'
  else:
    which_machine = 'on any machine'

  print '*' * 70
  print msg % (url, which_machine)
  print 'Press \'q\' on the browser to quit.'
  print '*' * 70 + '\n\n'

  # Allow input traffic in iptables.
  EnableDestinationPort(args.server_port)

  # Instantiate a touch device.
  device = TouchDeviceWrapper(args.dut_type, args.dut_addr, args.is_touchscreen)

  # Start to get touch snapshots from the specified touch device.
  ThreadedGetLiveStreamSnapshots(device, SAVED_FILE)

  # Create a ws connection state object to wait for the condition to
  # shutdown the whole process.
  state = ConnectionState()

  cherrypy.config.update({
    'server.socket_host': args.server_addr,
    'server.socket_port': args.server_port,
  })

  WebSocketPlugin(cherrypy.engine).subscribe()
  cherrypy.tools.websocket = WebSocketTool()

  # If the cherrypy server exits for whatever reason, close the device
  # for required cleanup. Otherwise, there might exist local/remote
  # zombie processes.
  cherrypy.engine.subscribe('exit',  device.close)

  cherrypy.engine.signal_handler.handlers['SIGINT'] = InterruptHandler
  cherrypy.engine.signal_handler.handlers['SIGTERM'] = InterruptHandler

  cherrypy.quickstart(
    Root(args.server_addr, args.server_port,
         device.device.x_min, device.device.x_max,
         device.device.y_min, device.device.y_max,
         device.device.p_min, device.device.p_max), '',
         config={
           '/': {
             'tools.staticdir.root': os.path.abspath(os.path.dirname(__file__)),
             'tools.staticdir.on': True,
             'tools.staticdir.dir': '',
           },
           '/ws': {
             'tools.websocket.on': True,
             'tools.websocket.handler_cls': WebplotWSHandler,
           },
         }
  )


if __name__ == '__main__':
  Main()
