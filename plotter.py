# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This module defines a class used to plot MtbEvents live as they arrive

This is done the pyqtgraph library to plot the points.  It's not as common as
matplotlib, but it's much much faster which is very useful for live updating.
The class works by maintaining its own MtbStateMachine and updating it with
the new events it receives.  Every time a SYN arrives, it updates the display.
"""

import os
import tempfile
from collections import defaultdict

import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore

import mtb


# Initialize Qt display here only once
qt_app = QtGui.QApplication([])

class TouchPlotter:
  EXPORT_IMAGE_WIDTH = 500
  COLORS = ['F00', '0F0', '00F', 'FF0', 'F0F', '0FF', 'FFF']

  def __init__(self, width, height):
    self.paths_by_tid = defaultdict(list)
    self.curves_by_tid = defaultdict(lambda:self.plot_window.plot())
    self.pens_by_tid = {}

    # The MtbStateMachine that makes sense of the incoming events
    self.sm = mtb.MtbStateMachine()

    # Configure the main window
    pg.setConfigOptions(background='b')
    pg.setConfigOptions(foreground='w')

    # Create a new plot and set up labels/etc
    self.plot_window = pg.plot()
    self.plot_window.invertY()
    self.plot_window.setAspectLocked()
    self.plot_window.setRange(QtCore.QRectF(0, 0, width, height))
    self.plot_window.setTitle('Live Touch Events')
    self.plot_window.hideAxis('bottom')
    self.plot_window.hideAxis('left')

    # Draw a bounding box around the pad
    self.plot_window.addLine(x=0)
    self.plot_window.addLine(y=0)
    self.plot_window.addLine(x=width)
    self.plot_window.addLine(y=height)
    self.plot_window.plotItem.vb.state['background'] = 'k'
    self.plot_window.plotItem.vb.updateBackground()

  def add_event(self, event):
    """ Take an MtbEvent and update the plot if required.

    A TouchPlotter maintains a visual plot of the events "so far", and this
    funtion just adds an additional event to the internal state.
    """

    # Update the state machine
    self.sm.add_event(event)
    if not event.is_SYN_REPORT():
      return

    # Any TID with a finger currently on the pad should get a new finger
    tids_to_draw = set([])
    snapshot = self.sm.get_current_snapshot()
    for finger in snapshot.fingers:
      if finger:
        self.paths_by_tid[finger.tid].append(finger)
        tids_to_draw.add(finger.tid)

    # Go through and draw all the contacts
    for tid in tids_to_draw:
      xs = [p.x for p in self.paths_by_tid[tid]]
      ys = [p.y for p in self.paths_by_tid[tid]]

      # If we don't already have a pen set up for this TID, do so now
      if tid not in self.pens_by_tid:
        next_color_index = len(self.pens_by_tid) % len(TouchPlotter.COLORS)
        next_color = TouchPlotter.COLORS[next_color_index]
        self.pens_by_tid[tid] = pg.mkPen({'color': next_color, 'width': 2})

      # Update the points for this TID's curve
      self.curves_by_tid[tid].setData(x=xs, y=ys, pen=self.pens_by_tid[tid])

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
    exporter = pg.exporters.ImageExporter.ImageExporter(
                                                    self.plot_window.plotItem)
    exporter.parameters()['width'] = TouchPlotter.EXPORT_IMAGE_WIDTH
    exporter.export(tmp_filename)
    with open(tmp_filename, 'rb') as fo:
      image = fo.read()
    os.remove(tmp_filename)

    # Clean up the plotter's resources and close the window before returning
    self.plot_window.win.close()

    return image
