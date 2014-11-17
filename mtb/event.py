# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from input.linux_input import *

class MtbEvent:
    """ Class that holds the contents of a single MTB event (Not a complete packet) """
    def __init__(self, timestamp, event_type=EV_SYN, event_code=None, value=None):
        self.timestamp = timestamp
        self.event_type = event_type
        self.event_code = event_code
        self.value = value

    def is_SYN_REPORT(self):
        """Determine if this event is SYN_REPORT."""
        return self.event_type == EV_SYN

    def __str__(self):
        if self.is_SYN_REPORT():
            return '%0.5f\t-- SYN --' % self.timestamp
        return '%0.5f\t%s\t%s\t%d' % (self.timestamp, EV_TYPES[self.event_type],
                                      EV_STRINGS[self.event_type][self.event_code],
                                      self.value)
