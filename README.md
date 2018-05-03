## Touch Firmware Test ##

This repo holds the source code of the touch firmware test.

## Get the source:
$ git clone https://chromium.googlesource.com/chromiumos/platform/touch_firmware_test

## Run the code:
See this website for details:
https://www.chromium.org/for-testers/touch-firmware-tests .

## Run in Docker:
You can also run the tests in docker now. You can build your own docker image or
use the one on docker hub.

# How to run tests in docker
* Connect the test device.
* Stop the host machine adb:
$ adb kill-server
* Start docker image:
$ docker run -t -i --privileged -v /dev/bus/usb:/dev/bus/usb -v $(pwd -L):/output -p 8080:8080 wjkcow/cros_touch_test bash
The test report will be saved into current directory. You can change "$(pwd -L)" to any directory you want.
* Start adb server in the container by
$ adb start-server
  Note: The first run might fail, try it again, it should work.
* Run the test. For android, do "python main.py -t android".
* Follow the instructions in terminal, go to http://127.0.0.1:8080.
If you don't open the webpage, the test might stuck.
