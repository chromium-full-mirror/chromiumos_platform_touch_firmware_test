# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This module defines the classes that are used to store results of validators

After a validator runs, it generates some results that need to be stored.  This
module defines the class that is used for that.
"""

class Result:
  """ A class to hold the results from running a single validator. """
  def __init__(self):
    self.name = None
    self.description = None
    self.criteria = None
    self.observed = None
    self.units = None
    self.score = None
    self.error = None

  def __str__(self):
    s = 'name: %s\n' % str(self.name)
    s += '    criteria: %s (%s)\n' % (str(self.criteria), str(self.units))
    s += '    observed: %s (%s)\n' % (str(self.observed), str(self.units))
    s += '    score: %f\n' % self.score
    if self.error:
      s += '    ERROR: %s\n' % str(self.error)
    return s
