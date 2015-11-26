// Copyright 2015 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * Object of a reported finger contact model.
 * @constructor
 * @param {array of float} paramArray the array of all contact parameters.
 *                         [0]: contact amplitude
 *                         [1]: x-positon of contact
 *                         [2]: y-position of contact
 *                         [3]: x-sigma of contact gaussian model
 *                         [4]: y-sigma of contact gaussian model
 *                         [5]: theta of contact gaussian model
 *                         [6]: tracking ID of contact
 *                         [7]: thumb likelihood
 *                         [8]: palm indicator (0: finger, 1: palm)
 */
function Contact(paramArray) {
  this.amp = paramArray[0];
  this.xPos = paramArray[1];
  this.yPos = paramArray[2];
  this.xSigma = paramArray[3];
  this.ySigma = paramArray[4];
  this.theta = paramArray[5];
  this.trackId = paramArray[6];
  this.thumbLikelihood = 0;
  this.isPalm = 0;
  if (paramArray.length > 7)
    this.thumbLikelihood = paramArray[7];
  if (paramArray.length > 8)
    this.isPalm = paramArray[8];
}


/**
 * Object of webplot.
 * @constructor
 * @param {Element} canvas the canvas to draw circles and clicks.
 * @param {string} dataScale the max scale of heatmap raw data.
 * @param {string} dataOffset the offset of heatmap raw data for presenting.
 * @param {string} dataWidth the size of width of heatmap raw data.
 * @param {string} dataHeight the size of height of heatmap raw data.
 */
function Webplot(canvas, dataScale, dataOffset, dataWidth, dataHeight) {
  this.canvas = canvas;
  this.ctx = canvas.getContext('2d');
  this.scale = 1 / parseInt(dataScale);
  this.offset = parseInt(dataOffset);
  this.width = parseInt(dataWidth);
  this.height = parseInt(dataHeight);
  this.gridSize = null;
  this.pointRadius = 6.0;
  this.contactLineWidth = 3.5;
}


/**
 * Update the width and height of the canvas, the max radius of circles,
 * and the edge of click rectangles.
 */
Webplot.prototype.updateCanvasDimension = function() {
  var newWidth = document.body.clientWidth;
  var newHeight = document.body.clientHeight;

  if (this.canvas.width != newWidth || this.canvas.height != newHeight) {
    var dataRatio = this.height / this.width;
    var canvasRatio = (newHeight / newWidth);

    // The actual dimension of the viewport.
    this.canvas.width = newWidth;
    this.canvas.height = newHeight;

    // Calculate the inner area of the viewport on which to draw finger traces.
    // This inner area has the same height/width ratio as the touch device.
    if (dataRatio >= canvasRatio) {
      this.canvas.innerWidth = Math.round(newHeight / dataRatio);
      this.canvas.innerHeight = newHeight;
      this.canvas.innerOffsetLeft = Math.round(
          (newWidth - this.canvas.innerWidth) / 2);
      this.canvas.innerOffsetTop = 0;
      this.gridSize = newHeight / this.height;
    } else {
      this.canvas.innerWidth = newWidth;
      this.canvas.innerHeight = Math.round(newWidth * dataRatio);
      this.canvas.innerOffsetLeft = 0;
      this.canvas.innerOffsetTop = Math.round(
          (newHeight - this.canvas.innerHeight) / 2);
      this.gridSize = newWidth / this.width;
    }
  }
  this.drawFrame(this.canvas.innerOffsetLeft, this.canvas.innerOffsetTop,
                 this.canvas.innerWidth, this.canvas.innerHeight, 'gray');
}


/**
 * Draw a rectangle of heatmap frame border.
 * @param {int} x the x coordinate of upper left corner of the rectangle.
 * @param {int} y the y coordinate of upper left corner of the rectangle.
 * @param {int} width the width of the rectangle.
 * @param {int} height the height of the rectangle.
 * @param {string} colorName
 */
Webplot.prototype.drawFrame = function(x, y, width, height, colorName) {
  this.ctx.beginPath();
  this.ctx.lineWidth = "4";
  this.ctx.strokeStyle = colorName;
  this.ctx.rect(x, y, width, height);
  this.ctx.stroke();
}


/**
 * Draw a circle of presenting contact gaussian model.
 * @param {Element} contact the contact object of gaussian finger model.
 */
Webplot.prototype.drawContactArea = function(contact) {
  var ctxLeft = this.canvas.innerOffsetLeft;
  var ctxTop = this.canvas.innerOffsetTop;
  var grid = this.gridSize;
  var offset = grid / 2;
  var x = contact.xPos;
  var y = (this.height - 1) - contact.yPos;  // Reflect over x-axis.
  var cx = x * grid + offset + ctxLeft;
  var cy = y * grid + offset + ctxTop;

  this.ctx.beginPath();
  this.ctx.save();  // save state
  this.ctx.translate(cx, cy);
  this.ctx.rotate(contact.theta);
  this.ctx.scale(contact.xSigma * grid, contact.ySigma * grid);
  this.ctx.arc(0, 0, 1, 0, 2 * Math.PI, false);
  this.ctx.restore();  // restore to original state
  this.ctx.lineWidth = this.contactLineWidth;
  if (contact.isPalm)
    this.ctx.strokeStyle = 'gold';
  else
    this.ctx.strokeStyle = 'deeppink';
  this.ctx.stroke();
}


/**
 * Draw a point of presenting contact center.
 * @param {Element} contact the contact object of gaussian finger model.
 */
Webplot.prototype.drawContactCenter = function(contact) {
  var ctxLeft = this.canvas.innerOffsetLeft;
  var ctxTop = this.canvas.innerOffsetTop;
  var grid = this.gridSize;
  var colors = ['blue', 'yellow', 'purple', 'red', 'orange', 'green',
                'gold', 'cyan', 'brown', 'limegreen'];
  var offset = grid / 2;
  var x = contact.xPos;
  var y = (this.height - 1) - contact.yPos;  // Reflect over x-axis.
  var cx = x * grid + offset + ctxLeft;
  var cy = y * grid + offset + ctxTop;

  this.ctx.beginPath();
  this.ctx.arc(cx, cy, this.pointRadius, 0, 2 * Math.PI, false);
  this.ctx.fillStyle = colors[contact.trackId % colors.length];
  this.ctx.fill();

  if (contact.isPalm) {
    var text = 'PALM';
    var text_color = 'blue';
  } else {
    var text = contact.thumbLikelihood.toFixed(4);
    var green = parseInt(255 * (1 - contact.thumbLikelihood)).toString(16);
    green = (green.length < 2) ? '0' + green : green;
    var red = parseInt(255 * contact.thumbLikelihood).toString(16);
    red = (red.length < 2) ? '0' + red : red;
    var text_color = '#' + red + green + '00';
  }
  this.fillText(text, cx + 4, cy + 20, '18px Arial', text_color);
}


/**
 * Fill text.
 * @param {string} text the text to display
 * @param {int} x the x coordinate of upper left corner of the text.
 * @param {int} y the y coordinate of upper left corner of the text.
 * @param {string} font the size and the font.
 * @param {string} color the color of the text.
 */
Webplot.prototype.fillText = function(text, x, y, font, color) {
  this.ctx.font = font;
  this.ctx.fillStyle = color;
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
 * A snapshot received from python server looks like:
 * Snapshot(
 *   data=[125,123,90,0,0, ... 230,231],
 *   contact=[[337.311, 1.55013, 6.43009, 0.747915, 0.97476, -0.026596, 1,
 *             0.13422, 0]],
 *   fps=[128.234, 49.992]
 * )
 *
 * data: a total length of width * height integers array of heatmap raw data.
 * contact: an array of contact arrays, each contact array has the following
 *          elements [amplitude, x-position, y-position, x-sigma, y-sigma,
 *          theta, track-ID, thumb likelihood, palm indicator], and they are
 *          all floating numbers.
 * fps: an 2-element array of float for receiver FPS and plot FPS.
 */
Webplot.prototype.processSnapshot = function(snapshot) {
  var ctxLeft = this.canvas.innerOffsetLeft;
  var ctxTop = this.canvas.innerOffsetTop;
  var grid = this.gridSize;
  var gridFullPixel = Math.ceil(grid);
  var data = snapshot.data;

  // Clean up canvas.
  this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

  // Draw the frame border.
  this.drawFrame(this.canvas.innerOffsetLeft, this.canvas.innerOffsetTop,
                 this.canvas.innerWidth, this.canvas.innerHeight, 'gray');

  // Draw heatmap raw data (data grid).
  for (var i = 0; i < this.width; i++) {
    for (var j = 0; j < this.height; j++) {
      var value = this.scale * (data[j + i * this.height] + this.offset);
      var x = Math.floor(ctxLeft + i * grid);
      // Reflect over x-axis.
      var y = Math.floor(ctxTop + (this.height - 1 - j) * grid);
      var color = parseInt(255 * value).toString(16);
      color = (color.length < 2) ? "0" + color : color;
      this.ctx.fillStyle = "#" + color + color + color;
      this.ctx.fillRect(x, y, gridFullPixel, gridFullPixel);
    }
  }

  // Draw finger contact models.
  for (var i = 0; i < snapshot.contact.length; i++) {
    var contact = new Contact(snapshot.contact[i]);
    this.drawContactArea(contact);
    this.drawContactCenter(contact);
  }

  // Show FPS rates.
  this.fillText("Algorithm FPS: " + snapshot.fps[0],
                20 + ctxLeft, 25 + ctxTop, '14px Verdana', 'bisque');
  this.fillText("Plot FPS: " + snapshot.fps[1],
                240 + ctxLeft, 25 + ctxTop, '14px Verdana', 'cyan');
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
      webplot.fillText('The python server has quit.',
                       startX, startY, font, 'red');
    }
    webplot.fillText('Centroiding data are saved inside "/tmp/"',
                     startX, startY + 100, font, 'red');
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
  var dataScale = document.getElementById('dataScale').innerText;
  var dataOffset = document.getElementById('dataOffset').innerText;
  var dataWidth = document.getElementById('dataWidth').innerText;
  var dataHeight = document.getElementById('dataHeight').innerText;
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
                        dataScale, dataOffset, dataWidth, dataHeight);
  webplot.updateCanvasDimension();
}
