# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Device object for centroiding visualizer tool."""

import os
import yaml


class CentroidingDevice(object):
  def __init__(self, config):
    with open(os.path.join(os.path.dirname(__file__), config), 'r') as f:
      self.config = yaml.load(f)

  @property
  def device(self):
    return self.config.get('device')

  @property
  def data_scale(self):
    return self.config.get('data_scale')

  @property
  def data_offset(self):
    return self.config.get('data_offset')

  @property
  def width(self):
    return self.config.get('width')

  @property
  def height(self):
    return self.config.get('height')
