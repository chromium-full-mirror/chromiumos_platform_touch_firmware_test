# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FROM debian:9.4
MAINTAINER Jingkui Wang (jkwang@google.com)

ADD  ./ /touch_firmware_test
WORKDIR /touch_firmware_test

RUN apt-get update
RUN apt-get install -qy gcc
RUN apt-get install -qy git
RUN apt-get install -qy python
RUN apt-get install -qy python-tk
RUN apt-get install -qy python-dev
RUN apt-get install -qy curl
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
RUN python get-pip.py
RUN apt-get install -qy adb
RUN pip install -r requirements.txt

ENV TOUCH_REPORT_OUTPUT /output
EXPOSE 8080
