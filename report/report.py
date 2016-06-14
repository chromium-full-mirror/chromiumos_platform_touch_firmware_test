# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import cgi
import io
import os
import pickle

import matplotlib.pyplot as plt


class Report:
  """ The Report class is designed to hold all of the Results generated during
  a run of the FW test and generate a human-readable HTML version of it.

  As Validators produce Result objects, they are added to a Report (with
  AddResults()) and then once all Results are added GenerateHtml() will
  build and return a string with all the HTML for the report.
  """

  REPORT_TITLE = 'Touch FW Test Report'
  CSS_FILE = 'report.css'
  JS_FILE = 'report.js'

  def __init__(self, title=None, test_version=None):
    """ Construct a new, empty Report """
    self.results = []
    self.warnings = []
    self.title = cgi.escape(title) if title else None
    self.test_version = cgi.escape(test_version) if test_version else None

  @classmethod
  def FromFile(self, filename):
    """ Load a previously saved Report from the harddrive. """
    with open(filename, 'rb') as fo:
      return pickle.load(fo)

  def SaveToDisk(self, filename):
    """ Save this Report to the harddrive so that is can be restored later """
    with open(filename, 'wb') as fo:
      pickle.dump(self, fo)

  def AddTestResult(self, test_result):
    """ Add a new TestResult object to this Report """
    self.results.append(test_result)

  def GenerateHtml(self):
    """ Generate the html version of this report
    This is the main function of a Report object.  Once a Report is full of all
    the results (by calling AddResults()) you can generate a human-readable
    html report by calling this function.  This function will return a string
    containing all the html code.
    """
    head = self._GenerateHtmlHead()
    body = self._GenerateHtmlBody()
    return '<html>%s%s</html>' % (head, body)

  def _GenerateHtmlHead(self):
    """ Generate the html for the <head> tag of the Report.
    This includes getting the CSS, Javascript, the title, and anything
    else that might go in the head set up.  This function returns a string.
    """
    # Define the title of the page
    title_string = Report.REPORT_TITLE
    if self.title is not None:
      title_string += ' (%s)' % self.title
    title_html = '<title>%s</title>' % title_string

    # Load the CSS from a file and include it directly in the HTML so this
    # module can ouput a standalone html file.
    css = ''
    report_directory = os.path.dirname(os.path.realpath(__file__))
    css_path = os.path.join(report_directory, Report.CSS_FILE)
    with open(css_path, 'r') as fo:
      css = '<style media="screen" type="text/css">%s</style>' % fo.read()

    # Load the JS from a file and include it directly in the HTML as well
    js = ''
    js_path = os.path.join(report_directory, Report.JS_FILE)
    with open(js_path, 'r') as fo:
      js = ('<script language="javascript" type="text/javascript">%s</script>'
                                                                    % fo.read())

    # Wrap everything in <head> tags and return that string
    return '<head>%s%s%s</head>' % (title_html, css, js)

  def _GenerateValidatorHeadingHtml(self):
    """ Generate the html for the first row of the Validators list.  This acts
    as a heading, explaining what the values in the below entries are.
    """
    min_heading = '<div class="min">Min</div>'
    max_heading = '<div class="max">Max</div>'
    avg_heading = '<div class="avg">Avg</div>'
    units_heading = '<div class="units">Units</div>'
    scores_heading = ('<div class="scores"><p>Scores:<p>%s%s%s</div>' %
                      (min_heading, max_heading, avg_heading))

    values_heading = ('<div class="values"><p>Values:</p>%s%s%s%s</div>' %
                      (units_heading, min_heading, max_heading, avg_heading))

    name_heading = '<div class="name">Validator Name (# of results)</div>'
    return ('<li class="heading">%s%s%s</li>' %
            (name_heading, scores_heading, values_heading))

  def _GetResultDetailsHtml(self, result):
    """ Generate all the HTML showing the details for the specified result.
    These are displayed in a list under the heading for their validator so you
    can drill down to see the specific gesture that generated this result.
    """
    score_div = '<div class="score">%.2f</div>' % result.score
    value_div = ('<div class="value">%.2f %s</div>' %
                 (result.observed, result.units))
    # Add a link to the detailed test run information wrapping the contents
    contents = ('<a onclick="preventClickPropagation(event)" '
                '   href="#%s">%s%s</a>' %
                (result.test_id, score_div, value_div))

    # Finally, color code the text for this particular result
    color = self._HeatmapColor(result.score)
    return '<li style="color: %s;">%s</li>' % (color, contents)

  def _GenerateValidatorHtml(self, validator_name):
    """ Generate all the HTML for a single entry in the Validators list. """
    # Just to make passing test ID's around easier I start out by storing a
    # copy temporarily inside each validator Result.
    for test_result in self.results:
      for validator_result in test_result.validator_results:
        validator_result.test_id = test_result.test_id

    # First separate all the results for this validator
    results = [vr for tr in self.results for vr in tr.validator_results
               if vr.name == validator_name]
    if not results:
      return ''

    # Build up a div to display the name of the Validator
    contents = '%s (%d)' % (validator_name, len(results))
    name_div = '<div class="name">%s</div>' % contents

    # Build up a div to display the observed values for this Validator
    min_value_div = ('<div class="min">%.2f</div>' %
                     min([r.observed for r in results]))
    max_value_div = ('<div class="max">%.2f</div>' %
                     max([r.observed for r in results]))
    # Note, infinite values indicating error messages destroy the usefullness
    # of averages, so we only actually average the finite values we observed.
    def _IsFinite(x):
      return x not in [float('inf'), float('-inf'), float('NaN')]
    values = [r.observed for r in results if _IsFinite(r.observed)]
    avg_value = ('%.2f' % (sum(values) / float(len(values)))) if values else '?'
    avg_value_div = '<div class="avg">%s</div>' % avg_value
    value_units_div = '<div class="units">(%s)</div>' % results[0].units
    contents = ('%s%s%s%s' %
                (value_units_div, min_value_div, max_value_div, avg_value_div))
    values_div = '<div class="values">%s</div>' % contents

    # Next build up a div to display the scores for this Validator
    min_score = '<div class="min">%.2f</div>' % min([r.score for r in results])
    max_score = '<div class="max">%.2f</div>' % max([r.score for r in results])
    avg_score_value = sum([r.score for r in results]) / float(len(results))
    avg_score = '<div class="avg">%.2f</div>' % avg_score_value
    contents = '%s%s%s' % (min_score, max_score, avg_score)
    scores_div = '<div class="scores">%s</div>' % contents

    # Make a div with the text description of what this validator was testing.
    # This assumes that all the validators that report the same name, will all
    # have the same description, which is a safe assumption only because if two
    # validators use the same name, but have different descriptions of how they
    # work, then something is wrong.
    validator_description = ('<div class="description">%s</div>' %
                             results[0].description)

    # Build up the HTML for this validator's details.  (This is the part
    # that is usually hidden until you click on a validator)
    details_heading = ('<li class="heading">'
                       '<div class="score">Score</div>'
                       '<div class="value">Observed Value</div>'
                       '</li>')
    details = ''.join([self._GetResultDetailsHtml(r)
                 for r in sorted(results, key=lambda r: (r.score, r.observed))])
    details = ('<ul class="result_details">%s%s%s</ul>' %
               (validator_description, details_heading, details))

    # Compose them all together into one content div element for the Validator
    content_div = ('<div onclick="expandResultDetails(this)" '
                   '     class="contents">%s%s%s%s</div>' %
                   (name_div, scores_div, values_div, details))

    # Compute which background color to give this Validator.  This is determined
    # by the average score, and changes the bg color to indicate failure/success
    color = self._HeatmapColor(avg_score_value)

    # Build a list element with a the custom color and an overlay div that can
    # darken to create a mouseover effect.
    return ('<li style="background: %s;">%s<div class=overlay></div></li>' %
            (color, content_div))

  def _HeatmapColor(self, score):
    """ Compute a heatmap color based on a score from 0.0 to 1.0.  The color
    is interpolated between red and green using a cubic exponential function and
    can be used as a visual indicator of a scores success/failure.
    This returns a css hex encoded color string of the form "#RRGGBB"
    """
    fail_color = {'r': 0xf4, 'g': 0x43, 'b': 0x36}
    pass_color = {'r': 0x4c, 'g': 0xaf, 'b': 0x50}

    alpha = (((score * 2.0 - 1.0) ** 3) + 1.0) / 2.0
    r = (pass_color['r'] * alpha) + (fail_color['r'] * (1.0 - alpha))
    g = (pass_color['g'] * alpha) + (fail_color['g'] * (1.0 - alpha))
    b = (pass_color['b'] * alpha) + (fail_color['b'] * (1.0 - alpha))
    return "#%02x%02x%02x" % (int(r), int(g), int(b))

  def _GenerateInlinePngTag(self, image, css_class='plot'):
    """ Convert the png image passed in into an embedded image tag.
    This allows us to include images within the HTML but not need to include
    any data files so it's easier to pass around just the single file.
    """
    return ('<img class="%s" src="data:image/png;base64,%s" />' %
             (css_class, base64.b64encode(image)))

  def _GenerateValidatorDetails(self, validator_result):
    """ This generates a little table with the details of a single Valifator's
    results for display in the "test details" section of the HTML report.
    These are displayed just to the right of the screenshot of the gesture's
    points.
    """
    def ValueRow(label, value):
      label_cell = '<td class="label">%s:</td>' % label
      value_cell = '<td>%s</td>' % value
      return '<tr class="value">%s%s</tr>' % (label_cell, value_cell)

    name = '<tr><td colspan=2 class="name">%s</td></tr>' % validator_result.name
    units = validator_result.units
    criteria = ValueRow('Criteria',
                        '%s (%s)' % (validator_result.criteria, units))
    observed = ValueRow('Observed',
                        '%.2f (%s)' % (validator_result.observed, units))
    score = ValueRow('Score', '%.2f' % validator_result.score)

    error = ''
    if validator_result.error:
      error = ValueRow('Error', validator_result.error)

    table = ('<table>%s%s%s%s%s</table>' %
             (name, criteria, observed, score, error))
    return '<div class="validator_details">%s</div>' % table

  def _GenerateTestDetailsHtml(self, test_result):
    """ Generate the HTML for a list item that shows all the details for a
    single TestResult object.  This include the test's prompt, an image of the
    gesture, and the full results for each validator run on this test.
    """
    timestamp_html = ('<h4 class="timestamp">%s</h4>' %
                      test_result.timestamp.strftime('%b %d %Y - %H:%M:%S'))
    prompt_html = ('<h3 class="prompt"><a href="#%s">%s</a></h3>' %
                   (test_result.test_id, test_result.prompt))
    img_html = self._GenerateInlinePngTag(test_result.image)
    validators_html = ''.join([self._GenerateValidatorDetails(vr)
                               for vr in test_result.validator_results])
    content = ('<a name="%s">%s%s%s%s</a>' %
               (test_result.test_id, timestamp_html, prompt_html, img_html,
                validators_html))
    return '<li>%s</li>' % content

  def _GenerateNoiseTestResults(self):
    def IsNoiseValidator(validator_result):
      return 'noisy' in validator_result.name.lower()

    def IsNoiseTest(test_result):
      return any([IsNoiseValidator(validator_result)
                  for validator_result in test_result.validator_results])

    # Filter out only results for noise testing
    noise_results = [result for result in self.results if IsNoiseTest(result)]
    if len(noise_results) == 0:
      return ''

    # Sort the results' scores by frequency
    results_by_frequency = {}
    for noise_result in noise_results:
      freq, amp, waveform, location = noise_result.variation
      results_by_frequency[freq] = results_by_frequency.get(freq, [])

      for validator_result in noise_result.validator_results:
        if not IsNoiseValidator(validator_result):
          continue
        results_by_frequency[freq].append(validator_result)

    # Compute the average score for each frequency
    avg_observed_value_by_freq = {}
    scores_by_freq = {}
    units_by_validator_name = {}
    for freq in results_by_frequency:
      observed_values = {}
      for result in results_by_frequency[freq]:
        observed_values[result.name] = observed_values.get(result.name, [])
        observed_values[result.name].append(result.observed)

        scores_by_freq[freq] = scores_by_freq.get(freq, [])
        scores_by_freq[freq].append(result.score)

        units_by_validator_name[result.name] = result.units

      for validator_name in observed_values:
        avg_observed_value_by_freq[validator_name] = \
            avg_observed_value_by_freq.get(validator_name, {})

        avg_observed_value_by_freq[validator_name][freq] = \
            (sum(observed_values[validator_name]) /
             float(len(observed_values[validator_name])))

    # Generate the graphics here.
    num_noisy_validators = len(observed_values)

    f, axarr = plt.subplots(num_noisy_validators + 1, sharex=True)
    f.set_size_inches(12, 5 * num_noisy_validators)
    f.suptitle('Touch Noise Test Results')

    first_freq = observed_values.keys()[0]
    freq_strings = sorted([f for f in avg_observed_value_by_freq[first_freq]],
                          key=lambda x: int(x.replace('Hz', '')))
    freqs = [int(f.replace('Hz', '')) for f in freq_strings]
    for i, validator_name in enumerate(observed_values):
      values = [avg_observed_value_by_freq[validator_name][f]
                for f in freq_strings]
      axarr[i].set_title(validator_name)
      axarr[i].set_ylabel(units_by_validator_name[validator_name])
      axarr[i].plot(freqs, values)

    # Build a subplot clearly marking which frequencies showed errors
    avg_scores = [1.0 - sum(scores_by_freq[f]) / float(len(scores_by_freq[f]))
                  for f in freq_strings]
    axarr[num_noisy_validators].set_title('Overall Error Level')
    axarr[num_noisy_validators].set_ylabel('Error')
    axarr[num_noisy_validators].plot(freqs, avg_scores,
                                     color='black', linewidth='0.25')
    axarr[num_noisy_validators].fill_between(freqs, avg_scores, 0.0,
                                             color='red')
    axarr[num_noisy_validators].set_xlabel('Frequency (Hz)')

    image_buffer = io.BytesIO()
    plt.savefig(image_buffer, format='png', transparent=True)
    image_buffer.seek(0)
    image = image_buffer.getvalue()
    image_buffer.close()
    image_html = self._GenerateInlinePngTag(image, css_class='noise_results')

    #Finally wrap it in some formatting HTML to make it fit nicely
    image_header = '<h2 class="section_title">Noise Test Results</h2>'
    return '%s%s' % (image_header, image_html)

  def _GenerateHeadings(self):
    # Generate the Headings for the top of the page
    title = '<h1>Touch FW Testing Results</h1>'

    if self.title is not None:
      title += ('<div class="test_title"><b>Test Title:</b> %s</div>' %
                self.title)

    if self.test_version is not None:
      title += ('<div class="test_version"><b>Test Version:</b> %s</div>' %
                self.test_version)

    for warning in self.warnings:
      title += ('<div class="warning"><b>WARNING</b>:%s</div>' %
                cgi.escape(warning))

    return '<div id="headings">%s</div>' % title

  def _GenerateHtmlBody(self):
    """ Generate the html for the <body> tag of the Report.
    This includes the actual results and anything else that will go within the
    <body> tags of the html page.  This function returns a string.
    """
    headings = self._GenerateHeadings()

    # Generate the list of validators and their scores
    validator_list_title = '<h2 class="section_title">Validator Scores</h1>'
    validator_names = set([vr.name for tr in self.results
                           for vr in tr.validator_results])
    validator_list_inner = ''.join([self._GenerateValidatorHtml(name)
                                    for name in sorted(validator_names)])
    validator_list_headings = self._GenerateValidatorHeadingHtml()
    validator_list_inner = validator_list_headings + validator_list_inner
    validator_list = ('%s<ul class="validators">%s</ul>' %
                      (validator_list_title, validator_list_inner))

    # If there was a noise test, generate a graph to show the results
    noise_test_results = self._GenerateNoiseTestResults()

    # Generate the detailed view of each gesture
    # We separate the noise results and sort them by frequency to make
    # the reports more readable.
    test_details_list_heading = '<h2 class="section_title">Test Details</h2>'
    performance_results = [result for result in self.results
                           if 'noise' not in result.prompt]
    noise_results = [result for result in self.results
                     if 'noise' in result.prompt]
    noise_results = sorted(noise_results,
                           key=lambda x: int(x.variation[0][:-2]))
    sorted_results = performance_results + noise_results
    test_details_list_inner = ''.join([self._GenerateTestDetailsHtml(tr)
                                       for tr in sorted_results])
    test_details_list = ('%s<ul class="test_details">%s</ul>' %
                         (test_details_list_heading, test_details_list_inner))

    # Wrap everything in <body> tags and return that string
    return '<body>%s%s%s%s</body>' % (headings, validator_list,
                                      noise_test_results, test_details_list)

