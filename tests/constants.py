# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import random

from noise import FunctionGenerator


"""Define constants for Tests """
class _ConstantError(AttributeError):
  """A constant error exception."""
  pass


class _Constant(object):
  """This is a constant base class to ensure no rebinding of constants."""
  def __setattr__(self, name, value):
    """Check the attribute assignment. No rebinding is allowed."""
    if name in self.__dict__:
        raise _ConstantError, "Cannot rebind the constant: %s" % name
    self.__dict__[name] = value


class _GestureVariation(_Constant):
  """Constants about gesture variations."""
  pass
GV = _GestureVariation()
# constants about directions
GV.HORIZONTAL = 'horizontal'
GV.VERTICAL = 'vertical'
GV.DIAGONAL = 'diagonal'
GV.LR = 'left_to_right'
GV.RL = 'right_to_left'
GV.TB = 'top_to_bottom'
GV.BT = 'bottom_to_top'
GV.CL = 'center_to_left'
GV.CR = 'center_to_right'
GV.CT = 'center_to_top'
GV.CB = 'center_to_bottom'
GV.CUR = 'center_to_upper_right'
GV.CUL = 'center_to_upper_left'
GV.CLR = 'center_to_lower_right'
GV.CLL = 'center_to_lower_left'
GV.BLTR = 'bottom_left_to_top_right'
GV.BRTL = 'bottom_right_to_top_left'
GV.TRBL = 'top_right_to_bottom_left'
GV.TLBR = 'top_left_to_bottom_right'
GV.HORIZONTAL_DIRECTIONS = [GV.HORIZONTAL, GV.LR, GV.RL, GV.CL, GV.CR]
GV.VERTICAL_DIRECTIONS = [GV.VERTICAL, GV.TB, GV.BT, GV.CT, GV.CB]
GV.DIAGONAL_DIRECTIONS = [GV.DIAGONAL, GV.BLTR, GV.BRTL, GV.TRBL, GV.TLBR,
                          GV.CUR, GV.CUL, GV.CLR, GV.CLL]
GV.GESTURE_DIRECTIONS = (GV.HORIZONTAL_DIRECTIONS + GV.VERTICAL_DIRECTIONS +
                         GV.DIAGONAL_DIRECTIONS)
# constants about locations
GV.TL = 'top_left'
GV.TR = 'top_right'
GV.BL = 'bottom_left'
GV.BR = 'bottom_right'
GV.TS = 'top_side'
GV.BS = 'bottom_side'
GV.LS = 'left_side'
GV.RS = 'right_side'
GV.CENTER = 'center'
GV.AROUND = 'around'
GV.GESTURE_LOCATIONS = [GV.TL, GV.TR, GV.BL, GV.BR, GV.TS, GV.BS, GV.LS, GV.RS,
                        GV.CENTER, GV.AROUND]
# constants about pinch to zoom
GV.ZOOM_IN = 'zoom_in'
GV.ZOOM_OUT = 'zoom_out'
# constants about speed
GV.SLOW = 'slow'
GV.NORMAL = 'normal'
GV.FAST = 'fast'
GV.FULL_SPEED = 'full_speed'
GV.GESTURE_SPEED = [GV.SLOW, GV.NORMAL, GV.FAST, GV.FULL_SPEED]
# constants used in the frequency sweep.
GV.NOISE_FREQUENCIES = ['%dHz' % f for f in range(0, 500000, 500)]
random.shuffle(GV.NOISE_FREQUENCIES)
# constants about noise waveform
GV.SQUARE_WAVE = FunctionGenerator.SQUARE_WAVE
GV.SINE_WAVE = FunctionGenerator.SIN_WAVE
GV.NOISE_WAVEFORMS = [GV.SQUARE_WAVE, GV.SINE_WAVE]
# constants about noise amplitude
GV.MAX_AMPLITUDE = '10V'
GV.NOISE_AMPLITUDES = [GV.MAX_AMPLITUDE]

# constants about thumb sizes
GV.SMALL_THUMB = 'thumb_small'
GV.LARGE_THUMB = 'thumb_large'
