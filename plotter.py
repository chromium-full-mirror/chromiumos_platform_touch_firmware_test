# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This module defines a class used to plot MtEvents live as they arrive

This is done the pyqtgraph library to plot the points.  It's not as common as
matplotlib, but it's much much faster which is very useful for live updating.
The class works by maintaining its own state machine and updating it with
the new events it receives.  Every time a SYN arrives, it updates the display.
"""

import os
import tempfile
from collections import defaultdict

import pyqtgraph as pg
import pyqtgraph.exporters
from pyqtgraph.Qt import QtGui, QtCore


# Initialize Qt display here only once
qt_app = QtGui.QApplication([])

class TouchPlotter:
  EXPORT_IMAGE_WIDTH = 500
  EXPORT_IMAGE_FILENAME = 'plot.png'
  MIN_POINT_SIZE = 3.0
  MAX_POINT_SIZE = 25.0
  COLORS = ['F00', '0F0', '00F', 'FF0', 'F0F', '0FF', 'FFF']

  def __init__(self, touch_dev, window_title='Live Touch Events'):
    self.window_title = window_title

    self.paths_by_tid = defaultdict(list)
    self.curves_by_tid = defaultdict(lambda:self.plot_window.plot())
    self.retired_curves = []
    self.pens_by_tid = {}
    self.next_color_index = 0

    self.x_min = touch_dev.x_min
    self.x_max = touch_dev.x_max
    self.y_min = touch_dev.y_min
    self.y_max = touch_dev.y_max
    self.p_min = touch_dev.p_min
    self.p_max = touch_dev.p_max
    width = self.x_max - self.x_min
    height = self.y_max - self.y_min

    # Configure the main window
    pg.setConfigOptions(background='b')
    pg.setConfigOptions(foreground='w')

    # Create a new plot and set up labels/etc
    self.plot_window = pg.plot()
    self.plot_window.invertY()
    self.plot_window.setAspectLocked()
    self.plot_window.setRange(QtCore.QRectF(0, 0, width, height))
    self.plot_window.setTitle(self.window_title)
    self.plot_window.hideAxis('bottom')
    self.plot_window.hideAxis('left')

    # Draw a bounding box around the pad
    self.plot_window.addLine(x=0)
    self.plot_window.addLine(y=0)
    self.plot_window.addLine(x=width)
    self.plot_window.addLine(y=height)
    self.plot_window.plotItem.vb.state['background'] = 'k'
    self.plot_window.plotItem.vb.updateBackground()

  def add_snapshot(self, snapshot):
    """ Take in an MtSnapshot and update the plot

    A TouchPlotter maintains a visual plot of the snapshots "so far", and this
    funtion just adds an additional snapshot's data to the plot.
    """
    # Any TID with a finger currently on the pad should get a new finger
    tids_to_draw = set([])
    for finger in snapshot.fingers:
      if finger:
        self.paths_by_tid[finger.tid].append(finger)
        tids_to_draw.add(finger.tid)

    # Retire any curves that have had their fingers leave.
    for tid, curve in self.curves_by_tid.items():
      if tid not in tids_to_draw:
        self.retired_curves.append(curve)
        del self.paths_by_tid[tid]
        del self.curves_by_tid[tid]
        del self.pens_by_tid[tid]

    # Go through and draw all the contacts
    for tid in tids_to_draw:
      xs = [p.x - self.x_min for p in self.paths_by_tid[tid]]
      ys = [p.y - self.y_min for p in self.paths_by_tid[tid]]

      # Interpolate the size of each dot based on the range of pressures for
      # this device so the dot sizes range from MIN_POINT_SIZE to MAX_POINT_SIZE
      size_range = TouchPlotter.MAX_POINT_SIZE - TouchPlotter.MIN_POINT_SIZE
      ps = [(TouchPlotter.MIN_POINT_SIZE + size_range *
             (p.pressure - self.p_min) / float(self.p_max - self.p_min))
            for p in self.paths_by_tid[tid]]

      # If we don't already have a pen set up for this TID, do so now
      if tid not in self.pens_by_tid:
        next_color = TouchPlotter.COLORS[self.next_color_index]
        self.next_color_index = ((self.next_color_index + 1) %
                                 len(TouchPlotter.COLORS))
        self.pens_by_tid[tid] = pg.mkPen({'color': next_color, 'width': 2})

      # Update the points for this TID's curve
      self.curves_by_tid[tid].setData(
          x=xs, y=ys, pen=self.pens_by_tid[tid], symbol='o', symbolSize=ps,
          symbolPen=self.pens_by_tid[tid], symbolBrush=None)

    # Update the display
    qt_app.processEvents()

  def end(self):
    """ After the plot is no longer needed, clean up resources and return a
    snapshot of the final plot to be saved/bundled with the report.

    The returned image should be a .png image that can later be base64 encoded
    and included in an HTML document or written to disk directly as a file.
    """
    # First, export the image that's currently displayed as a .png image.
    # Unfortunately, PyQtPlot doesn't allow you to export directly into memory,
    # so this image is saved into a temp file and read back into ram before
    # the file on the hard drive is deleted.
    tmp_filename = tempfile.mktemp(suffix='.png')
    exporter = pg.exporters.ImageExporter(self.plot_window.plotItem)
    exporter.parameters()['width'] = TouchPlotter.EXPORT_IMAGE_WIDTH
    exporter.export(tmp_filename)
    with open(tmp_filename, 'rb') as fo:
      image = fo.read()
    os.remove(tmp_filename)

    # Clean up the plotter's resources and close the window before returning
    self.plot_window.win.close()

    return image


def live_display(touch_dev):
  """ Simply initialize a plotter for this touch device and plot the touches

  This will loop forever until you kill it with Ctrl+C but allows you to
  quickly view the touch information on a DUT and will save a copy of the plot
  to disk as a png image when you exit.
  """
  touch_dev.FlushSnapshotBuffer()
  plotter = TouchPlotter(touch_dev)

  print 'Displaying live touch events from your DUT.  Press Ctrl+C to stop.'
  try:
    snapshot = touch_dev.NextSnapshot()
    while snapshot:
      plotter.add_snapshot(snapshot)
      snapshot = touch_dev.NextSnapshot()
  except KeyboardInterrupt:
    print 'Ctrl+C caught.  Exiting...'
  except Exception as e:
    print 'Exption caught (%s), exiting.' % str(e)
  finally:
    print 'Saving plot to disk as "%s"...' % TouchPlotter.EXPORT_IMAGE_FILENAME
    with open(TouchPlotter.EXPORT_IMAGE_FILENAME, 'wb') as fo:
      fo.write(plotter.end())
