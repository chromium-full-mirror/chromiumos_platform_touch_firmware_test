# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parser for recorded centroiding data stream. It will generate data files in
analytical format for our centroiding algorithm library.

It will generate 3 files:

  Trace file: will be generated in path <input_file>/<input_file>
      To view it by centroiding source tree's tool, put the trace file into
      traces/ in source tree.

  Finger contact file: will be generated in path <input_file>/<input_file>.json
      To view it by centroiding source tree's tool, put the contact file into
      outputs/centroiding/ in source tree.

  Track ID file: will be generated in path <input_file>/<input_file>.id.json
"""

import argparse
import json
import os

from centroiding_device import CentroidingDevice

_JSON_HEADER = '{\n  "events": [\n'
_JSON_TAIL = '  ]\n}'


class CentroidingDataParserError(Exception):
  pass

class CentroidingDataParser(object):
  """Parser for recorded centroiding raw data stream."""
  def __init__(self, input_file, device):
    self.input_file = input_file
    self.device = device

    self.head_trim_thres = self.device.data_scale >> 2
    self.is_head = True

    # Use the root name of input_file as generated output folder name.
    self.output_dir = os.path.splitext(input_file)[0]
    if not os.path.exists(self.output_dir):
      os.makedirs(self.output_dir)
    filename = os.path.basename(self.output_dir)
    self.output_trace = os.path.join(self.output_dir, filename)
    self.output_finger = os.path.join(self.output_dir, '%s.json' % filename)
    self.output_id = os.path.join(self.output_dir, '%s.id.json' % filename)

    self.file_trace = open(self.output_trace, 'w')
    self.file_finger = open(self.output_finger, 'w')
    self.file_id = open(self.output_id, 'w')

  def _PrintHeader(self):
    """Prints header lines of json files."""
    self.file_finger.write(_JSON_HEADER)
    self.file_id.write(_JSON_HEADER)

  def _PrintTail(self):
    """Prints tail lines of json files."""
    self.file_finger.write(_JSON_TAIL)
    self.file_id.write(_JSON_TAIL)

  def _AssertBadData(self, json_data):
    """Asserts exception if received data is not as expected."""
    if len(json_data['data']) != self.device.width * self.device.height:
      raise CentroidingDataParserError('Mismatched data length')
    if any(len(contact) != 7 for contact in json_data['contact']):
      raise CentroidingDataParserError('Mismatched contact length')

  def _IsEmptyHead(self, json_data, line_number):
    """Checks if current frame is empty for head frame trimming.

    Head frame trimming is used to trim empty frames from the beginning since
    user may not drop fingers immediately after opening data receiver.

    Frames will be regard empty-headed if there is no finger contact reported
    and all trace data is below device.data_scale / 4. Once a frame is not
    empty, all frames afterward will be parsed.

    Args:
      json_data: Frame data in json format.
      line_number: Current line number.

    Returns:
      True if this frame is empty-headed; otherwise False.
    """
    if not self.is_head:
      return False
    if len(json_data['contact']) > 0:
      self.is_head = False
      print '[Parse] Trimmed empty content in the beginning.'
      print '[Parse] Parse from line %d...' % line_number
      return False
    if any(d >= self.head_trim_thres for d in json_data['data']):
      self.is_head = False
      print '[Parse] Trimmed empty content in the beginning.'
      print '[Parse] Parse from line %d...' % line_number
      return False
    return True

  def _PrintTrace(self, data):
    """Prints trace data into trace file.

    For example, device width = 2, height = 3, data = [1, 2, 3, 4, 5, 6]
    will be printed as 1 2 3
                       4 5 6
    """
    for j in xrange(self.device.width):
      data_line = data[j * self.device.height: (j + 1) * self.device.height]
      self.file_trace.write(' '.join(str(d) for d in data_line))
      self.file_trace.write('\n')
    self.file_trace.write('\n')

  def _PrintFingerAndId(self, contact):
    """Prints contact fingers and tracking IDs into files."""
    track_id = [c.pop() for c in contact]
    self.file_finger.write('    %s,\n' % str(contact))
    self.file_id.write('    %s,\n' % str(track_id))

  def _PrintDummyEndFrame(self):
    """Prints one last dummy frame into files.

    Since json does not accept trailing comma in an array and it is difficult
    to know the last frame data in file readline loop, printing a dummy frame
    in the end can solve this issue easily.
    """
    for j in xrange(self.device.width):
      self.file_trace.write(' '.join(['0' for i in xrange(self.device.height)]))
      if j < self.device.width - 1:
        self.file_trace.write('\n')
    self.file_finger.write('    []\n')
    self.file_id.write('    []\n')

  def _CloseFiles(self):
    """Closes all file objects."""
    self.file_trace.close()
    self.file_finger.close()
    self.file_id.close()

  def Parse(self):
    """Starts parsing trace data and finger data into output files."""
    self._PrintHeader()
    with open(self.input_file) as f:
      line_number = 0
      for line in f:
        line_number += 1
        strip_line = line.strip()
        if len(strip_line) == 0:
          continue
        try:
          json_data = json.loads(strip_line)
          self._AssertBadData(json_data)
          if not self._IsEmptyHead(json_data, line_number):
            self._PrintTrace(json_data['data'])
            self._PrintFingerAndId(json_data['contact'])
        except Exception as e:
          print '[Parse] Invalid data line %d: %s' % (line_number, strip_line)
          print e
    self._PrintDummyEndFrame()
    self._PrintTail()
    self._CloseFiles()
    print '[Parse] created trace data:', self.output_trace
    print '[Parse] created finger json:', self.output_finger
    print '[Parse] created track id json:', self.output_id


def _ParseArguments():
  """Parses the command line options."""
  parser = argparse.ArgumentParser(description='Centroiding Main')

  parser.add_argument('-i', '--input_file',
                      help='the input file path of raw data')
  parser.add_argument('-c', '--config', help='the config file of device')

  args = parser.parse_args()
  return args


def Main():
  args = _ParseArguments()

  print 'parsing raw data %s to analytical format...' % args.input_file
  device = CentroidingDevice(config=args.config)
  data_parser = CentroidingDataParser(args.input_file, device)
  data_parser.Parse()


if __name__ == '__main__':
  Main()
