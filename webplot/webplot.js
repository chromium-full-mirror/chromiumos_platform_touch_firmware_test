// Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * Choose finger colors for circles and the click color for rectangles.
 * @constructor
 */
function Color() {
  this.tids = [];
  this.lastIndex = -1;
  this.COLOR_TABLE = [
    'Blue', 'Gold', 'LimeGreen', 'Red', 'Cyan',
    'Magenta', 'Brown', 'Wheat', 'DarkGreen', 'Coral',
  ];
  this.length = this.COLOR_TABLE.length;
  this.COLOR_CLICK = 'Gray';
  this.COLOR_FRAME = 'Gray';

  for (var i = 0; i < this.length; i++) {
    this.tids[i] = -1;
  }
}


/**
 * Get the color to draw a circle for a given Tracking ID (tid).
 * @param {int} tid
 * @return {string}
 */
Color.prototype.getCircleColor = function(tid) {
  index = this.tids.indexOf(tid);
  // Find next color for this new tid.
  if (index == -1) {
    var i = (this.lastIndex + 1) % this.length;
    while (i != this.lastIndex) {
      if (this.tids[i] == -1) {
        this.tids[i] = tid;
        this.lastIndex = i;
        return this.COLOR_TABLE[i];
      }
      i = (i + 1) % this.length;
    }

    // It is very unlikely that all slots in this.tids have been occupied.
    // Should it happen, just assign a color to it.
    return this.COLOR_TABLE[0];
  } else {
    return this.COLOR_TABLE[index];
  }
}


/**
 * Get the color to draw a rectangle for a given Tracking ID (tid).
 * @param {int} tid
 * @return {string}
 */
Color.prototype.getRectColor = function(tid) {
  return this.COLOR_CLICK;
}


/**
 * Remove the Tracking ID (tid) from the tids array.
 * @param {int} tid
 */
Color.prototype.remove = function(tid) {
  index = this.tids.indexOf(tid);
  if (index >= 0) {
    this.tids[index] = -1;
  }
}


/**
 * Pick up colors for circles and rectangles.
 * @constructor
 * @param {Element} canvas the canvas to draw circles and clicks.
 * @param {int} touchMinX the min x value of the touch device.
 * @param {int} touchMaxX the max x value of the touch device.
 * @param {int} touchMinY the min y value of the touch device.
 * @param {int} touchMaxY the max y value of the touch device.
 * @param {int} touchMinPressure the min pressure value of the touch device.
 * @param {int} touchMaxPressure the max pressure value of the touch device.
 * @param {int} tiltMinX the min tilt x value of the touch device.
 * @param {int} tiltMaxX the max tilt x value of the touch device.
 * @param {int} tiltMinY the min tilt y value of the touch device.
 * @param {int} tiltMaxY the max tilt y value of the touch device.
 */
function Webplot(canvas, touchMinX, touchMaxX, touchMinY, touchMaxY,
                 touchMinPressure, touchMaxPressure, tiltMinX, tiltMaxX,
                 tiltMinY, tiltMaxY) {
  this.canvas = canvas;
  this.ctx = canvas.getContext('2d');
  this.color = new Color();
  this.minX = touchMinX;
  this.maxX = touchMaxX;
  this.minY = touchMinY;
  this.maxY = touchMaxY;
  this.minPressure = touchMinPressure;
  this.maxPressure = touchMaxPressure;
  this.tiltMinX = tiltMinX;
  this.tiltMaxX = tiltMaxX;
  this.tiltMinY = tiltMinY;
  this.tiltMaxY = tiltMaxY;
  this.showTilt = ! ((tiltMinX == tiltMaxX) && (tiltMinY == tiltMaxY))
  this.maxRadiusRatio = 0.03;
  this.maxRadius = null;
  this.clickEdge = null;
  this.clickDown = false;
  this.pressureMode = true;
  this.pointRadius = 2;
  this.saved_events = '/tmp/webplot.dat';
  this.saved_image = '/tmp/webplot.png';
}


/**
 * Update the width and height of the canvas, the max radius of circles,
 * and the edge of click rectangles.
 */
Webplot.prototype.updateCanvasDimension = function() {
  var newWidth = document.body.clientWidth;
  var newHeight = document.body.clientHeight;

  if (this.canvas.width != newWidth || this.canvas.height != newHeight) {
    var deviceRatio = (this.maxY - this.minY) / (this.maxX - this.minX);
    var canvasRatio = (newHeight / newWidth);

    // The actual dimension of the viewport.
    this.canvas.width = newWidth;
    this.canvas.height = newHeight;

    // Calculate the inner area of the viewport on which to draw finger traces.
    // This inner area has the same height/width ratio as the touch device.
    if (deviceRatio >= canvasRatio) {
      this.canvas.innerWidth = Math.round(newHeight / deviceRatio);
      this.canvas.innerHeight = newHeight;
      this.canvas.innerOffsetLeft = Math.round(
          (newWidth - this.canvas.innerWidth) / 2);
      this.canvas.innerOffsetTop = 0;
    } else {
      this.canvas.innerWidth = newWidth;
      this.canvas.innerHeight = Math.round(newWidth * deviceRatio);
      this.canvas.innerOffsetLeft = 0;
      this.canvas.innerOffsetTop = Math.round(
          (newHeight - this.canvas.innerHeight) / 2);
    }

    this.maxRadius = Math.min(this.canvas.innerWidth, this.canvas.innerHeight) *
                     this.maxRadiusRatio;
    this.clickEdge = (this.pressureMode ? this.maxRadius : this.maxRadius / 2);
  }
  this.drawRect(this.canvas.innerOffsetLeft, this.canvas.innerOffsetTop,
                this.canvas.innerWidth, this.canvas.innerHeight,
                this.color.COLOR_FRAME);
}


/**
 * Draw a circle.
 * @param {int} x the x coordinate of the circle.
 * @param {int} y the y coordinate of the circle.
 * @param {int} r the radius of the circle.
 * @param {string} colorName
 */
Webplot.prototype.drawCircle = function(x, y, r, colorName) {
  this.ctx.beginPath();
  this.ctx.fillStyle = colorName;
  this.ctx.arc(x, y, r, 0, 2 * Math.PI);
  this.ctx.fill();
}


/**
 * Draw a rectangle.
 * @param {int} x the x coordinate of upper left corner of the rectangle.
 * @param {int} y the y coordinate of upper left corner of the rectangle.
 * @param {int} width the width of the rectangle.
 * @param {int} height the height of the rectangle.
 * @param {string} colorName
 */
Webplot.prototype.drawRect = function(x, y, width, height, colorName) {
  this.ctx.beginPath();
  this.ctx.lineWidth = "4";
  this.ctx.strokeStyle = colorName;
  this.ctx.rect(x, y, width, height);
  this.ctx.stroke();
}


/**
 * Fill text.
 * @param {string} text the text to display
 * @param {int} x the x coordinate of upper left corner of the text.
 * @param {int} y the y coordinate of upper left corner of the text.
 * @param {string} font the size and the font
 */
Webplot.prototype.fillText = function(text, x, y, font) {
  this.ctx.font = font;
  this.ctx.fillText(text, x, y);
}


/**
 * Capture the canvas image.
 * @return {string} the image represented in base64 text
 */
Webplot.prototype.captureCanvasImage = function() {
  var imageData = this.canvas.toDataURL('image/png');
  // Strip off the header.
  return imageData.replace(/^data:image\/png;base64,/, '');
}


/**
 * Process an incoming snapshot.
 * @param {object} snapshot
 *
 * A 2f snapshot received from the python server looks like:
 *   MtbSnapshot(
 *     syn_time=1420522152.269537,
 *     button_pressed=False,
 *     fingers =[
 *       MtFinger(tid=13, slot=0, syn_time=1420522152.269537, x=440, y=277,
 *                pressure=33),
 *       MtFinger(tid=14, slot=1, syn_time=1420522152.269537, x=271, y=308,
 *                pressure=38)
 *     ]
 *   )
 */
Webplot.prototype.processSnapshot = function(snapshot) {
  var edge = this.clickEdge;

  for (var i = 0; i < snapshot.fingers.length; i++) {
    var finger = snapshot.fingers[i];

    // Update the color object if the finger is leaving.
    if (finger.leaving) {
      this.color.remove(finger.tid);
      continue;
    }

    // Calculate (x, y) based on the inner width/height which has the same
    // dimension ratio as the touch device.
    var x = (finger.x - this.minX) / (this.maxX - this.minX) *
            this.canvas.innerWidth + this.canvas.innerOffsetLeft;
    var y = (finger.y - this.minY) / (this.maxY - this.minY) *
            this.canvas.innerHeight + this.canvas.innerOffsetTop;
    if (this.pressureMode)
      var r = (finger.pressure - this.minPressure) /
              (this.maxPressure - this.minPressure) * this.maxRadius;
    else
      var r = this.pointRadius;

    this.drawCircle(x, y, r, this.color.getCircleColor(finger.tid));

    // If there is a click, draw the click with finger 0.
    // The flag clickDown is used to draw the click exactly once
    // during the click down period.
    if (snapshot.button_pressed == 1 && i == 0 && !this.clickDown) {
      this.drawRect(x, y, edge, edge, this.color.getRectColor());
      this.clickDown = true;
    }
  }

  // In some special situation, the click comes with no fingers.
  // This may happen if an insulated object is used to click the touchpad.
  // Just draw the click at a random position.
  if (snapshot.fingers.length == 0 && snapshot.button_pressed == 1 &&
      !this.clickDown) {
    var x = Math.random() * this.canvas.innerWidth +
            this.canvas.innerOffsetLeft;
    var y = Math.random() * this.canvas.innerHeight +
            this.canvas.innerOffsetTop;
    this.drawRect(x, y, edge, edge, this.color.getRectColor());
    this.clickDown = true;
  }

  if (snapshot.button_pressed == 0) {
    this.clickDown = false;
  }
}


Webplot.quitFlag = false;


/**
 * An handler for onresize event to update the canvas dimensions.
 */
function resizeCanvas() {
  webplot.updateCanvasDimension();
}


/**
 * Send a 'quit' message to the server and display the event file name
 * on the canvas.
 * @param {boolean} closed_by_server True if this is requested by the server.
 */
function quit(closed_by_server) {
  var canvas = document.getElementById('canvasWebplot');
  var webplot = window.webplot;
  var startX = 100;
  var startY = 100;
  var font = '30px Verdana';

  // Capture the image before clearing the canvas and send it to the server,
  // and notify the server that this client quits.
  if (!Webplot.quitFlag) {
    Webplot.quitFlag = true;
    window.ws.send('quit');

    clear(false);
    if (closed_by_server) {
      webplot.fillText('The python server has quit.', startX, startY, font);
    }
    webplot.fillText('Events are saved in "' + webplot.saved_events + '"',
                     startX, startY + 100, font);
    webplot.fillText('The image is saved in "' + webplot.saved_image + '"',
                     startX, startY + 200, font);
  }
}

function save() {
  window.ws.send('save:' + webplot.captureCanvasImage());
}

/**
 * A handler for keyup events to handle user hot keys.
 */
function keyupHandler() {
  var webplot = window.webplot;
  var key = String.fromCharCode(event.which).toLowerCase();
  var ESC = String.fromCharCode(27);

  switch(String.fromCharCode(event.which).toLowerCase()) {
    // ESC: clearing the canvas
    case ESC:
      clear(true);
      break;

    // 'b': toggle the background color between black and white
    //      default: black
    case 'b':
      document.bgColor = (document.bgColor == 'Black' ? 'White' : 'Black');
      break;

    // 'f': toggle full screen
    //      default: non-full screen
    //      Note: entering or leaving full screen will trigger onresize events.
    case 'f':
      if (document.documentElement.webkitRequestFullscreen) {
        if (document.webkitFullscreenElement)
          document.webkitCancelFullScreen();
        else
          document.documentElement.webkitRequestFullscreen(
              Element.ALLOW_KEYBOARD_INPUT);
      }
      webplot.updateCanvasDimension();
      break;

    // 'p': toggle between pressure mode and point mode.
    //      pressure mode: the circle radius corresponds to the pressure
    //      point mode: the circle radius is fixed and small
    //      default: pressure mode
    case 'p':
      webplot.pressureMode = webplot.pressureMode ? false : true;
      webplot.updateCanvasDimension();
      break;

    // 'q': Quit the server (and save the plot and logs first)
    case 'q':
      save();
      quit(false);
      break;

    // 's': Tell the server to save the touch events and a png of the plot
    case 's':
      save();
      break;
  }
}


function clear(should_redraw_border) {
  var canvas = document.getElementById('canvasWebplot');
  canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
  if (should_redraw_border) {
    window.webplot.updateCanvasDimension();
  }
}

/**
 * Create a web socket and a new webplot object.
 */
function createWS() {
  var websocket = document.getElementById('websocketUrl').innerText;
  var touchMinX = document.getElementById('touchMinX').innerText;
  var touchMaxX = document.getElementById('touchMaxX').innerText;
  var touchMinY = document.getElementById('touchMinY').innerText;
  var touchMaxY = document.getElementById('touchMaxY').innerText;
  var touchMinPressure = document.getElementById('touchMinPressure').innerText;
  var touchMaxPressure = document.getElementById('touchMaxPressure').innerText;
  var tiltMinX = document.getElementById('tiltMinX').innerText;
  var tiltMaxX = document.getElementById('tiltMaxX').innerText;
  var tiltMinY = document.getElementById('tiltMinY').innerText;
  var tiltMaxY = document.getElementById('tiltMaxY').innerText;

  if (window.WebSocket) {
    ws = new WebSocket(websocket);
    ws.addEventListener("message", function(event) {
      if (event.data == 'quit') {
        save();
        quit(true);
      } else if (event.data == 'clear') {
        clear(true);
      } else if (event.data == 'save') {
        save();
      } else {
        var snapshot = JSON.parse(event.data);
        webplot.processSnapshot(snapshot);
      }
    });
  } else {
    alert('WebSocket is not supported on this browser!')
  }

  webplot = new Webplot(document.getElementById('canvasWebplot'),
                        touchMinX, touchMaxX, touchMinY, touchMaxY,
                        touchMinPressure, touchMaxPressure);
  webplot.updateCanvasDimension();
}
