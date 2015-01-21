# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import os
import pickle


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

  def __init__(self):
    """ Construct a new, empty Report """
    self.results = []

  @classmethod
  def FromFile(self, filename):
    """ Load a previously saved Report from the harddrive. """
    with open(filename, 'rb') as fo:
      return pickle.load(fo)

  def SaveToDisk(self, filename):
    """ Save this Report to the harddrive so that is can be restored later """
    with open(filename, 'wb') as fo:
      pickle.dump(self, fo)

  def AddTestResult(self, test_result, verbose=False):
    """ Add a new TestResult object to this Report """
    self.results.append(test_result)
    if verbose:
      for result in test_result.validator_results:
        print result

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
    title = '<title>%s</title>' % Report.REPORT_TITLE

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
    return '<head>%s%s%s</head>' % (title, css, js)

  def _GenerateValidatorHeadingHtml(self):
    """ Generate the html for the first row of the Validators list.  This acts
    as a heading, explaining what the values in the below entries are.
    """
    min_heading = '<div class="min">Min</div>'
    max_heading = '<div class="max">Max</div>'
    avg_heading = '<div class="avg">Avg</div>'
    scores_heading = ('<div class="scores">%s%s%s</div>' %
                      (min_heading, max_heading, avg_heading))

    name_heading = '<div class="name">Validator Name (# of results)</div>'
    return '<li class="heading">%s%s</li>' % (name_heading, scores_heading)

  def _GetResultDetailsHtml(self, result):
    """ Generate all the HTML showing the details for the specified result.
    These are displayed in a list under the heading for their validator so you
    can drill down to see the specific gesture that generated this result.
    """
    return ('<li><a class="test_link" onclick="preventClickPropagation(event)" '
            'href="#%s">%f</a></li>' % (result.test_id, result.score))

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

    # Build up a div to display the name of the Validator
    contents = '%s (%d)' % (validator_name, len(results))
    name_div = '<div class="name">%s</div>' % contents

    # Next build up a div to display the score for this Validator
    min_score = '<div class="min">%f</div>' % min([r.score for r in results])
    max_score = '<div class="max">%f</div>' % max([r.score for r in results])
    avg_score = ('<div class="avg">%f</div>' %
                 (sum([r.score for r in results]) / float(len(results))))
    contents = '%s%s%s' % (min_score, max_score, avg_score)
    scores_div = '<div class="scores">%s</div>' % contents

    # Build up the HTML for this validator's details.  (This is the part
    # that is usually hidden until you click on a validator)
    details = ''.join([self._GetResultDetailsHtml(r)
                       for r in sorted(results, key=lambda r: r.score)])
    details = '<ul class="result_details">%s</ul>' % details

    # Compose them all together into one list element for the Validator
    return ('<li onclick="expandResultDetails(this)">%s%s%s</li>' %
            (name_div, scores_div, details))

  def _GenerateInlinePngTag(self, image):
    """ Convert the png image passed in into an embedded image tag.
    This allows us to include images within the HTML but not need to include
    any data files so it's easier to pass around just the single file.
    """
    return ('<img class="plot" src="data:image/png;base64,%s" />' %
             base64.b64encode(image))

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
                        '%s (%s)' % (validator_result.observed, units))
    score = ValueRow('Score', '%f' % validator_result.score)

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
    prompt_html = ('<h3><a href="#%s">%s</a></h3>' %
                   (test_result.test_id, test_result.prompt))
    img_html = self._GenerateInlinePngTag(test_result.image)
    validators_html = ''.join([self._GenerateValidatorDetails(vr)
                               for vr in test_result.validator_results])
    content = '<a name="%s">%s%s%s</a>' % (test_result.test_id, prompt_html,
                                           img_html, validators_html)
    return '<li>%s</li>' % content

  def _GenerateHtmlBody(self):
    """ Generate the html for the <body> tag of the Report.
    This includes the actual results and anything else that will go within the
    <body> tags of the html page.  This function returns a string.
    """
    # Generate the Heading for the top of the page
    title = '<h1>Touch FW Testing Results</h1>'

    # Generate the list of validators and their scores
    validator_list_title = '<h2>Validator Scores</h1>'
    validator_names = set([vr.name for tr in self.results
                           for vr in tr.validator_results])
    validator_list_inner = ''.join([self._GenerateValidatorHtml(name)
                                    for name in sorted(validator_names)])
    validator_list_headings = self._GenerateValidatorHeadingHtml()
    validator_list_inner = validator_list_headings + validator_list_inner
    validator_list = ('%s<ul class="validators">%s</ul>' %
                      (validator_list_title, validator_list_inner))

    # Generate the detailed view of each gesture
    test_details_list_heading = '<h2>Test Details</h2>'
    test_details_list_inner = ''.join([self._GenerateTestDetailsHtml(tr)
                                       for tr in self.results])
    test_details_list = ('%s<ul class="test_details">%s</ul>' %
                         (test_details_list_heading, test_details_list_inner))

    # Wrap everything in <body> tags and return that string
    return '<body>%s%s%s</body>' % (title, validator_list, test_details_list)

