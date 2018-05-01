#!/bin/bash
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

OUTPUT_DIR=$(pwd -L)
docker run -t -i --privileged -v /dev/bus/usb:/dev/bus/usb \
  -v $OUTPUT_DIR:/output -p 8080:8080 wjkcow/cros_touch_test bash

