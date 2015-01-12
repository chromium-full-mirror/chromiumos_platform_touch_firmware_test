# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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

  def AddResults(self, results, verbose=False):
    """ Add a new list results to this Report """
    self.results.extend(results)
    if verbose:
      for result in results:
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
    # TODO(charliemooney): add links in to the detailed output.  Currently this
    # just shows the score, but it should actually be a quick way to jump to a
    # gesture that caused this low score.
    return '<li>%f</li>' % result.score

  def _GenerateValidatorHtml(self, validator_name):
    """ Generate all the HTML for a single entry in the Validators list. """
    # First separate all the results for this validator
    results = [r for r in self.results if r.name == validator_name]

    # Build up a div to display the name of the Validator
    contents = '%s (%d)' % (validator_name, len(results))
    name_div = '<div class="name">%s</div>' % contents

    # Next build up a div to display the score for this Validator
    min_score = '<div class="min">%f</div>' % min([r.score for r in results])
    max_score = '<div class="max">%f</div>' % max([r.score for r in results])
    avg_score = ('<div class="avg">%f</div>' %
                 (sum([r.score for r in results]) / len(results)))
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

  def _GenerateHtmlBody(self):
    """ Generate the html for the <body> tag of the Report.
    This includes the actual results and anything else that will go within the
    <body> tags of the html page.  This function returns a string.
    """
    # Generate the Heading for the top of the page
    title = '<h1>Touch FW Testing Results</h1>'

    # Generate the list of validators and their scores
    validator_names = set([result.name for result in self.results])
    validator_list_inner = ''.join([self._GenerateValidatorHtml(name)
                                    for name in validator_names])
    validator_list_headings = self._GenerateValidatorHeadingHtml()
    validator_list_inner = validator_list_headings + validator_list_inner
    validator_list = '<ul class="validators">%s</ul>' % validator_list_inner

    # Generate the detailed view of each gesture
    # TODO(charliemooney): Display each gesture w/ its validators, scores, and
    # an image of the plot here like the original version.  The validator list
    # will link to anchors in this section to allow you to drill down quickly
    # to the gesture that caused problems.

    # Wrap everything in <body> tags and return that string
    return '<body>%s%s</body>' % (title, validator_list)

