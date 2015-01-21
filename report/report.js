// Copyright 2015 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

function expandResultDetails(validatorElement) {
  // This function is used as the onClick function of the Validator list items.
  // The <li> element of the Validator gets passed in as validatorElement and
  // this function finds it's "result_details" child and toggles if it is
  // visible or not, effectively expanding the sublist when you click it.
  for (var i = 0; i < validatorElement.childNodes.length; i++) {
    var child = validatorElement.childNodes[i];

    // If this is the child we want, toggle its visibility
    if (child.className == 'result_details') {
      var curStyle = child.style.display;
      child.style.display = (curStyle == 'block') ? 'none' : 'block';
    }
  }
}

function preventClickPropagation(event) {
  // This click handler keeps the clicked object's parents from acting on the
  // click too.  This is used to keep expandable divs open after a link in them
  // has been clicked.  Otherwise, it would also close the expandable div.
  event.stopPropagation();
}
