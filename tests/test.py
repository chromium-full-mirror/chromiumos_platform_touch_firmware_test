# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from constants import GV

class Test:
  """ This class defines all the characteristics of a test in the test suite

  The touch firmware test suite consists of a collection of tests (represented
  by this class) and their variations.  A single Test class may have many
  variations.  The actual tests used in the test suite are defined in the file
  test_configurations.py where many Test objects are described.
  """
  DEFAULT_TIMEOUT_S = 1

  def __init__(self, name=None, variations=None, prompt=None, subprompt=None,
               validators=None, timeout=DEFAULT_TIMEOUT_S):
    self.name = name
    self.variations = self._ExpandVariationTuples(variations)
    self.prompt = prompt
    self.subprompt = subprompt
    self.validators = validators
    self.timeout = timeout

  def RunAllValidators(self, snapshots):
    return [validator.Validate(snapshots) for validator in self.validators]

  def PromptForVariation(self, variation_number):
    """ Generate an English prompt to explain to the user what gesture to
    perform for the given variation of this test.

    Generally Tests have multiple variations, so this function substitues in
    the correct subprompts to generate a string that explains what gesture
    this variation of the test needs as input.

    Examples could look something like this:
        "Draw a line horizontally across the screen quickly."
        "Draw a line vertically across the screen slowly."
        ...
    """
    variation = self.variations[variation_number]
    prompt = self.prompt
    if variation:
      formatters = ()
      for v in variation:
        formatters += self.subprompt.get(v, (v,))
      prompt = self.prompt.format(*formatters)
    return prompt

  def WaveformForVariation(self, variation_number):
    """ Determine what kind of electrical noise (if any) this variation needs.
    If this is a noise test, this function should return a tuple of the form:
    (waveform, frequency, amplitude) otherwise it will return None.
    """
    # First check if this is even a test that needs a function generator at all
    if 'noise' not in self.name:
        return None

    # Next try to take apart the variation to determine the wave's details
    variation = self.variations[variation_number]
    frequency = amplitude = form = None
    for value in variation:
      if value in GV.NOISE_WAVEFORMS:
        form = value
      elif value in GV.NOISE_FREQUENCIES:
        frequency = int(value.replace('Hz', ''))
      elif value in GV.NOISE_AMPLITUDES:
        amplitude = int(value.replace('V', ''))
    if not all([value is not None for value in (form, frequency, amplitude)]):
      return None

    if frequency <= 0:
      return None
    return form, frequency, amplitude

  def _ExpandVariationTuples(self, tuples):
    """ Return a list of expanded tuples (one for each variation)

    Tests have their variations passed in using human-friendly formats
        1. ((va1, va2), (vb1, vb2))
        2. (v1, v2, v3, ...)
        3. None

    This function takes all three formats and converts them into the same
    one: a single list of tuples like so:
        1. [(va1, vb1), (va1, vb2), (va2, vb1), (va2, vb2)]
        2. [(v1,), (v2,), (v3,), ... ]
        3. [None]
    """
    if tuples is None:
      return [None]
    elif isinstance(tuples[0], tuple):
      return list(reduce(self._SpanSeq, tuples))
    else:
      return list((v,) for v in tuples)

  def _SpanSeq(self, seq1, seq2):
    """ Span sequence seq1 over sequence seq2.

    E.g., seq1 = (('a', 'b'), 'c')
          seq2 = ('1', ('2', '3'))
          res = (('a', 'b', '1'), ('a', 'b', '2', '3'),
                 ('c', '1'), ('c', '2', '3'))
    E.g., seq1 = ('a', 'b')
          seq2 = ('1', '2', '3')
          res  = (('a', '1'), ('a', '2'), ('a', '3'),
                  ('b', '1'), ('b', '2'), ('b', '3'))
    E.g., seq1 = (('a', 'b'), ('c', 'd'))
          seq2 = ('1', '2', '3')
          res  = (('a', 'b', '1'), ('a', 'b', '2'), ('a', 'b', '3'),
                  ('c', 'd', '1'), ('c', 'd', '2'), ('c', 'd', '3'))
    """
    to_list = lambda s: list(s) if isinstance(s, tuple) else [s]
    return tuple(tuple(to_list(s1) + to_list(s2)) for s1 in seq1 for s2 in seq2)

  def __str__(self):
    """ A nice, human-readable, way to display the test """
    s = ''
    s += 'TEST: "%s"\n' % self.name
    s += '\tVariations:\n'
    if self.variations:
      for v in self.variations:
        s += '\t\t%s\n' % str(v)
    s += '\tPrompt: "%s"\n' % self.prompt
    s += '\tSubprompt:\n'
    if self.subprompt:
      for sp in self.subprompt:
        s += '\t\t%s: %s\n' % (sp, self.subprompt[sp])
    s += '\tValidators:\n'
    for v in self.validators:
      s += '\t\t%s\n' % v.name
    s += '\tTimeout: "%d"\n' % self.timeout
    return s
