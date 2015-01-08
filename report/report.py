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
    css_directory = os.path.dirname(os.path.realpath(__file__))
    css_path = os.path.join(css_directory, Report.CSS_FILE)
    with open(css_path, 'r') as fo:
      css = '<style media="screen" type="text/css">%s</style>' % fo.read()

    # Wrap everything in <head> tags and return that string
    return '<head>%s%s</head>' % (title, css)

  def _GenerateHtmlBody(self):
    """ Generate the html for the <body> tag of the Report.
    This includes the actual results and anything else that will go within the
    <body> tags of the html page.  This function returns a string.
    """
    names = set([result.name for result in self.results])
    name_list_inner = ''.join(['<li>%s</li>' % name for name in names])
    name_list = '<ul class="validators">%s</ul>' % name_list_inner

    # Wrap everything in <body> tags and return that string
    return '<body>%s</body>' % name_list

