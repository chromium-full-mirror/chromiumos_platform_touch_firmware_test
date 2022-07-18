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
import pwd
import re
import subprocess
import time
import threading
import webbrowser

import cherrypy

from ws4py import configure_logger
from ws4py.messaging import TextMessage
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket

from remote import ChromeOSTouchDevice, AndroidTouchDevice


# The WebSocket connection state object.
state = None

# The touch events are saved in this file as default.
current_username = pwd.getpwuid(os.getuid()).pw_name
SAVED_FILE = '/tmp/webplot_%s.dat' % current_username
SAVED_IMAGE = '/tmp/webplot_%s.png' % current_username


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
  except Exception as e:
    logging.warning('Command (%s) failed (%s).', cmd, e)
  else:
    return None if proc.returncode else stdout.decode().strip()


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
    cherrypy.log('Adding a rule to accept incoming connections on port %d in '
                 'iptables.' % port)
    cmd = ('sudo iptables -A INPUT -p tcp -m conntrack --ctstate NEW '
           '--dport %d -j ACCEPT' % port)
    if SimpleSystem(cmd) != 0:
      raise Error('Failed to enable port in iptables: %d.' % port)


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
  state.QuitAndShutdown()


def _IOError(e, filename):
  err_msg = ['\n', '!' * 60, str(e),
             'It is likely that %s is owned by root.' % filename,
             'Please remove the file and then run webplot again.',
             '!' * 60, '\n']
  cherrypy.log('\n'.join(err_msg))

image_lock = threading.Event()
image_string = ''

class WebplotWSHandler(WebSocket):
  """The web socket handler for webplot."""

  def opened(self):
    """This method is called when the handler is opened."""
    cherrypy.log('WS handler is opened!')

  def received_message(self, msg):
    """A callback for received message."""
    data = msg.data.decode().split(':', 1)
    mtype = data[0].lower()
    content = data[1] if len(data) == 2 else None

    # Do not print the image data since it is too large.
    if mtype != 'save':
      cherrypy.log('Received message: %s' % str(msg.data))

    if mtype == 'quit':
      # A shutdown message requested by the user.
      cherrypy.log('The user requests to shutdown the cherrypy server....')
      state.DecCount()
    elif mtype == 'save':
      cherrypy.log('All data saved to "%s"' % SAVED_FILE)
      self.SaveImage(content, SAVED_IMAGE)
      cherrypy.log('Plot image saved to "%s"' % SAVED_IMAGE)
    else:
      cherrypy.log('Unknown message type: %s' % mtype)

  def closed(self, code, reason="A client left the room."):
    """This method is called when the handler is closed."""
    cherrypy.log('A client requests to close WS.')
    cherrypy.engine.publish('websocket-broadcast', TextMessage(reason))

  @staticmethod
  def SaveImage(image_data, image_file):
    """Decoded the base64 image data and save it in the file."""
    global image_string
    image_string = base64.b64decode(image_data)
    image_lock.set()
    try:
      with open(image_file, 'w') as f:
        f.write(image_string)
    except IOError as e:
      _IOError(e, image_file)
      state.QuitAndShutdown()


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
    self.quit_flag = False

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

  def ShutdownWhenNoConnections(self):
    """Shutdown cherrypy server when there is no client connection."""
    self.lock.acquire()
    if self.count == 0 and self.shutdown_timer is None:
      self.Shutdown()
    self.lock.release()

  def Shutdown(self):
    """Shutdown the cherrypy server."""
    cherrypy.log('Shutdown timer expires. Cherrypy server for Webplot exits.')
    cherrypy.engine.exit()

  def QuitAndShutdown(self):
    """The server notifies clients to quit and then shuts down."""
    if not self.quit_flag:
      self.quit_flag = True
      cherrypy.engine.publish('websocket-broadcast', TextMessage('quit'))
      self.ShutdownWhenNoConnections()


class TouchRoot(object):
  """A class to handle requests about docroot."""

  def __init__(self, ip, port, touch_min_x, touch_max_x, touch_min_y,
               touch_max_y, touch_min_pressure, touch_max_pressure,
               tilt_min_x, tilt_max_x, tilt_min_y, tilt_max_y,
               major_min, major_max, minor_min, minor_max):
    self.ip = ip
    self.port = port
    self.touch_min_x = touch_min_x
    self.touch_max_x = touch_max_x
    self.touch_min_y = touch_min_y
    self.touch_max_y = touch_max_y
    self.touch_min_pressure = touch_min_pressure
    self.touch_max_pressure = touch_max_pressure
    self.tilt_min_x = tilt_min_x
    self.tilt_max_x = tilt_max_x
    self.tilt_min_y = tilt_min_y
    self.tilt_max_y = tilt_max_y
    self.major_min = major_min
    self.major_max = major_max
    self.minor_min = minor_min
    self.minor_max = minor_max
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
      'tiltMinX': str(self.tilt_min_x),
      'tiltMaxX': str(self.tilt_max_x),
      'tiltMinY': str(self.tilt_min_y),
      'tiltMaxY': str(self.tilt_max_y),
    }
    root_page = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'webplot.html')
    with open(root_page) as f:
      return f.read() % websocket_dict

  @cherrypy.expose
  def linechart(self):
    """This is the default linechart.html page."""
    websocket_dict = {
      'websocketUrl': '%s://%s:%s/ws' % (self.scheme, self.ip, self.port),
      'touchMinX': str(self.touch_min_x),
      'touchMaxX': str(self.touch_max_x),
      'touchMinY': str(self.touch_min_y),
      'touchMaxY': str(self.touch_max_y),
      'touchMinPressure': str(self.touch_min_pressure),
      'touchMaxPressure': str(self.touch_max_pressure),
      'tiltMinX': str(self.tilt_min_x),
      'tiltMaxX': str(self.tilt_max_x),
      'tiltMinY': str(self.tilt_min_y),
      'tiltMaxY': str(self.tilt_max_y),
      'majorMin': str(self.major_min),
      'majorMax': str(self.major_max),
      'minorMin': str(self.minor_min),
      'minorMax': str(self.minor_max),
    }
    root_page = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'linechart/linechart.html')
    with open(root_page) as f:
      return f.read() % websocket_dict

  @cherrypy.expose
  def ws(self):
    """This handles the request to create a new web socket per client."""
    cherrypy.log('A new client requesting for WS')
    cherrypy.log('WS handler created: %s' % repr(cherrypy.request.ws_handler))
    state.IncCount()


class Webplot(threading.Thread):
  """The server handling the Plotting of finger traces.

  Use case 1: embedding Webplot as a plotter in an application

    # Instantiate a webplot server and starts the daemon.
    plot = Webplot(server_addr, server_port, device)
    plot.start()

    # Repeatedly get a snapshot and add it for plotting.
    while True:
      # GetSnapshot() is essentially device.NextSnapshot()
      snapshot = plot.GetSnapshot()
      if not snapshot:
        break
      # Add the snapshot to the plotter for plotting.
      plot.AddSnapshot(snapshot)

    # Save a screen dump
    plot.Save()

    # Notify the browser to clear the screen.
    plot.Clear()

    # Notify both the browser and the cherrypy engine to quit.
    plot.Quit()


  Use case 2: using webplot standalone

    # Instantiate a webplot server and starts the daemon.
    plot = Webplot(server_addr, server_port, device)
    plot.start()

    # Get touch snapshots from the touch device and have clients plot them.
    webplot.GetAndPlotSnapshots()
  """

  def __init__(self, server_addr, server_port, device, saved_file=SAVED_FILE,
               logging=False, is_behind_iptables_firewall=False):
    self._server_addr = server_addr
    self._server_port = server_port
    self._device = device
    self._saved_file = saved_file
    super(Webplot, self).__init__(name='webplot thread')

    self.daemon = True
    self._prev_tids = []

    # The logging is turned off by default when imported as a module so that
    # it does not mess up the screen.
    if not logging:
      cherrypy.log.screen = None

    # Allow input traffic in iptables, if the user has specified.  This setting
    # should be used if webplot is being run directly on a chromebook, but it
    # requires root access, so we don't want to use it all the time.
    if is_behind_iptables_firewall:
      EnableDestinationPort(self._server_port)

    # Create a ws connection state object to wait for the condition to
    # shutdown the whole process.
    global state
    state = ConnectionState()

    cherrypy.config.update({
      'server.socket_host': self._server_addr,
      'server.socket_port': self._server_port,
    })

    WebSocketPlugin(cherrypy.engine).subscribe()
    cherrypy.tools.websocket = WebSocketTool()

    # If the cherrypy server exits for whatever reason, close the device
    # for required cleanup. Otherwise, there might exist local/remote
    # zombie processes.
    cherrypy.engine.subscribe('exit',  self._device.__del__)

    cherrypy.engine.signal_handler.handlers['SIGINT'] = InterruptHandler
    cherrypy.engine.signal_handler.handlers['SIGTERM'] = InterruptHandler

  def run(self):
    """Start the cherrypy engine."""
    x_min, x_max = self._device.RangeX()
    y_min, y_max = self._device.RangeY()
    p_min, p_max = self._device.RangeP()
    tilt_x_min, tilt_x_max = self._device.RangeTiltX()
    tilt_y_min, tilt_y_max = self._device.RangeTiltY()
    major_min, major_max = self._device.RangeMajor()
    minor_min, minor_max = self._device.RangeMinor()

    root = TouchRoot(self._server_addr, self._server_port,
                     x_min, x_max, y_min, y_max, p_min, p_max, tilt_x_min,
                     tilt_x_max, tilt_y_min, tilt_y_max,
                     major_min, major_max, minor_min, minor_max,)

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
                'tools.websocket.handler_cls': WebplotWSHandler,
            },
        }
    )

  def _ConvertNamedtupleToDict(self, snapshot):
    """Convert namedtuples to ordinary dictionaries and add leaving slots.

    This is to make a snapshot json serializable. Otherwise, the namedtuples
    would be transmitted as arrays which is less readable.

    A snapshot looks like
      MtSnapshot(
          syn_time=1420524008.368854,
          button_pressed=False,
          fingers=[
              MtFinger(tid=162, slot=0, syn_time=1420524008.368854, x=524,
                        y=231, pressure=45, tilt_x=0, tilt_y=0),
              MtFinger(tid=163, slot=1, syn_time=1420524008.368854, x=677,
                        y=135, pressure=57, tilt_x=0, tilt_y=0)
          ]
      )

    Note:
    1. that there are two levels of namedtuples to convert.
    2. The leaving slots are used to notify javascript that a finger is leaving
       so that the corresponding finger color could be released for reuse.
    """
    # Convert MtSnapshot.
    converted = snapshot._asdict()

    # Convert MtFinger.
    converted['fingers'] = [finger._asdict()
                            for finger in converted['fingers']]
    converted['raw_events'] = [str(event) for event in converted['raw_events']]

    # Add leaving fingers to notify js for reclaiming the finger colors.
    curr_tids = [finger['tid'] for finger in converted['fingers']]
    for tid in set(self._prev_tids) - set(curr_tids):
      leaving_finger = {'tid': tid, 'leaving': True}
      converted['fingers'].append(leaving_finger)
    self._prev_tids = curr_tids

    # Convert raw events from a list of classes to a list of its strings
    # so that the raw_events is serializable.
    converted['raw_events'] = [str(event) for event in converted['raw_events']]

    return converted

  def GetSnapshot(self):
    """Get a snapshot from the touch device."""
    return self._device.NextSnapshot()

  def AddSnapshot(self, snapshot):
    """Convert the snapshot to a proper format and publish it to clients."""
    snapshot = self._ConvertNamedtupleToDict(snapshot)
    cherrypy.engine.publish('websocket-broadcast', json.dumps(snapshot))
    return snapshot

  def GetAndPlotSnapshots(self):
    """Get and plot snapshots."""
    cherrypy.log('Start getting the live stream snapshots....')
    try:
      with open(self._saved_file, 'w') as f:
        while True:
          try:
            snapshot = self.GetSnapshot()
            if not snapshot:
              cherrypy.log('webplot is terminated.')
              break
            converted_snapshot = self.AddSnapshot(snapshot)
            f.write('\n'.join(converted_snapshot['raw_events']) + '\n')
            f.flush()
          except KeyboardInterrupt:
            cherrypy.log('Keyboard Interrupt accepted')
            cherrypy.log('webplot is being terminated...')
            state.QuitAndShutdown()
    except IOError as e:
      _IOError(e, self._saved_file)
      state.QuitAndShutdown()

  def Publish(self, msg):
    """Publish a message to clients."""
    cherrypy.engine.publish('websocket-broadcast', TextMessage(msg))

  def Clear(self):
    """Notify clients to clear the display."""
    self.Publish('clear')

  def Quit(self):
    """Notify clients to quit.

    Note that the cherrypy engine would quit accordingly.
    """
    state.QuitAndShutdown()

  def Save(self):
    """Notify clients to save the screen, then wait for the image file to be
    created, and return the image.
    """
    global image_lock
    global image_string

    # Trigger a save action
    self.Publish('save')

    # Block until the server has completed saving it to disk
    image_lock.wait()
    image_lock.clear()
    return image_string

  def Url(self):
    """The url the server is serving at."""
    return 'http://%s:%d' % (self._server_addr, self._server_port)


def _CheckLegalUser():
  """If this program is run in chroot, it should not be run as root for security
  reason.
  """
  if os.path.exists('/etc/cros_chroot_version') and os.getuid() == 0:
    print('You should run webplot in chroot as a regular user '
           'instead of as root.\n')
    exit(1)


def _ParseArguments():
  """Parse the command line options."""
  parser = argparse.ArgumentParser(description='Webplot Server')
  parser.add_argument('-d', '--dut_addr', default=None,
                      help='the address of the dut')

  # Make an exclusive group to make the webplot.py command option
  # consistent with the webplot.sh script command option.
  # What is desired:
  #   When no command option specified in webplot.sh/webplot.py: grab is True
  #   When '--grab'   option specified in webplot.sh/webplot.py: grab is True
  #   When '--nograb' option specified in webplot.sh/webplot.py: grab is False
  grab_group = parser.add_mutually_exclusive_group()
  grab_group.add_argument('--grab', help='grab the device exclusively',
                          action='store_true')
  grab_group.add_argument('--nograb', help='do not grab the device',
                          action='store_true')

  parser.add_argument('--is_touchscreen', help='the DUT is touchscreen',
                      action='store_true')
  parser.add_argument('-p', '--server_port', default=8080, type=int,
                      help='the port the web server listens to (default: 8080)')
  parser.add_argument('--behind_firewall', action='store_true',
                      help=('With this flag set, you tell webplot to add a '
                            'rule to iptables to allow incoming traffic to '
                            'the webserver.  If you are running webplot on '
                            'a chromebook, this is needed.'))
  parser.add_argument('-s', '--server_addr', default='0.0.0.0',
                      help='the address the webplot http server listens to')
  parser.add_argument('-t', '--dut_type', default='chromeos', type=str.lower,
                      help='dut type: chromeos, android')
  parser.add_argument('--automatically_start_browser', action='store_true',
                      help=('When this flag is set the script will try to '
                            'start a web browser automatically once webplot '
                            'is ready, instead of waiting for the user to.'))
  parser.add_argument('--protocol',type=str, default='auto',
                      choices=['auto', 'stylus', 'MTB', 'MTA'],
                      help=('Which protocol does the device use? Choose from '
                            'auto, MTB, MTA, or stylus'))

  args = parser.parse_args()

  args.grab = not args.nograb

  return args


def Main():
  """The main function to launch webplot service."""
  _CheckLegalUser()

  configure_logger(level=logging.ERROR)
  args = _ParseArguments()

  print('\n' + '-' * 70)
  cherrypy.log('dut machine type: %s' % args.dut_type)
  cherrypy.log('dut\'s touch device: %s' %
                 ('touchscreen' if args.is_touchscreen else 'touchpad'))
  cherrypy.log('dut address: %s' % args.dut_addr)
  cherrypy.log('web server address: %s' % args.server_addr)
  cherrypy.log('web server port: %s' % args.server_port)
  cherrypy.log('grab the touch device: %s' % args.grab)
  if args.dut_type == 'android' and args.grab:
    cherrypy.log('Warning: the grab option is not supported on Android devices'
                 ' yet.')
  cherrypy.log('touch events are saved in %s' % SAVED_FILE)
  print('-' * 70 + '\n\n')

  if args.server_port == 80:
    url = 'http://%s' % args.server_addr
  else:
    url = 'http://%s:%d' % (args.server_addr, args.server_port)

  msg = 'Type "%s" in browser %s to see finger traces.\n'
  if args.server_addr == '127.0.0.1':
    which_machine = 'on the webplot server machine'
  else:
    which_machine = 'on any machine'

  print('*' * 70)
  print(msg % (url, which_machine))
  print('Press \'q\' on the browser to quit.')
  print('*' * 70 + '\n\n')

  # Instantiate a touch device.
  if args.dut_type == 'chromeos':
    addr = args.dut_addr if args.dut_addr else '127.0.0.1'
    device = ChromeOSTouchDevice(addr, args.is_touchscreen, grab=args.grab,
                                 protocol=args.protocol)
  elif args.dut_type == 'android':
    device = AndroidTouchDevice(args.dut_addr, True, protocol=args.protocol)
  else:
    print('Unrecognized dut_type: %s. Webplot is aborted...' % args.dut_type)
    exit(1)

  # Instantiate a webplot server daemon and start it.
  webplot = Webplot(args.server_addr, args.server_port, device, logging=True,
                    is_behind_iptables_firewall=args.behind_firewall)
  webplot.start()

  if args.automatically_start_browser:
    opened_successfully = webbrowser.open(url)
    if opened_successfully:
      print('Web browser opened successfully!')
    else:
      print('!' * 80)
      print('Sorry, we were unable to automatically open a web browser for you')
      print('Please navigate to "%s" in a browser manually, instead' % url)
      print('!' * 80)

  # Get touch snapshots from the touch device and have clients plot them.
  webplot.GetAndPlotSnapshots()


if __name__ == '__main__':
  Main()
