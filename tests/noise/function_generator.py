# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class FunctionGenerator(object):
  """ Abstract base class to define the interface for function generators """

  SQUARE_WAVE = 'square_wave'
  SIN_WAVE = 'sine_wave'
  WAVEFORMS = [SQUARE_WAVE, SIN_WAVE]

  def __init__(self, device_path=None):
    raise NotImplementedError('Error: __init__() not implemented.')

  def IsValid(self):
    """ Return True if the object is set up and ready to use. """
    raise NotImplementedError('Error: IsValid() not implemented.')

  def Off(self):
    """ Turn off the output of the function generator. """
    raise NotImplementedError('Error: Off() not implemented.')

  def GenerateFunction(self, form, frequency, amplitude):
    """ Generate the specified wave on this function generator """
    raise NotImplementedError('Error: GenerateFunction() not implemented.')
