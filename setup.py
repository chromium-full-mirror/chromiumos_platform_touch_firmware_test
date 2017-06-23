# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from distutils.core import setup


setup(name='touch_firmware_test',
      version='1.0',
      description='Touch Firmware Testing Suite',
      long_description='This contains tools for testing touch devices.',
      license='BSD-Google',
      packages=['webplot',
                'webplot.remote',
                'webplot.remote.mt',
                'webplot.remote.mt.input',
                'heatmap',
                'heatmap.remote',
                'heatmap.remote.hidraw',
                'heatmap.remote.hidraw.input'],
      package_data={'webplot': ['*.html', '*.js', 'webplot', 'linechart/*.js',
                                'linechart/*.html'],
                    'webplot.remote': ['data/*',],
                    'heatmap': ['*.html', '*.js'],
                    'heatmap.remote': ['data/*',]},
      author='Joseph Hwang',
      author_email='josephsih@chromium.org',
)
