// Copyright 2017 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * PointerEventBuffer buffer the pointer event until it's expired.
 * @constructor
 * @param {int} expireTime expire time of the events in seconds.
 */
function PointerEventBuffer(expireTime = 15) {
  this.expireTime = expireTime;
  this.data = [];
}

/**
 * Function to add new event to the buffer. It will also clear expired events.
 * @param {object} new_event new pointer event. It looks like:
 *    {tid=13, slot=0, syn_time=142, x=440, y=227, pressure=33, tilt_x=3,
 *    tilt_y=4}
 */
PointerEventBuffer.prototype.appendEvent = function(newEvent) {
  // After the for loop, events before this index will be removed.
  var expired_idx  = 0;
  for (var i = 0; i < this.data.length; i++) {
    if (newEvent.syn_time - this.data[i].syn_time > this.expireTime) {
      expired_idx ++;
    } else {
      break;
    }
  }
  this.data = this.data.slice(expired_idx);
  this.data[this.data.length] = newEvent;
}

/**
 * Function to get dataTable from select columns. The dataTable will be used to
 * draw the linechart.
 * @return {google.visualization.DataTable}
 */
PointerEventBuffer.prototype.getDataTableForColumns = function(columns) {
  var data = new google.visualization.DataTable();
  data.addColumn('number', 'time');
  for (var i = 0; i < columns.length; i++) {
    data.addColumn('number', columns[i]);
  }

  var lastEventTime = 0;
  if (this.data.length) {
    lastEventTime = this.data[this.data.length - 1].syn_time;
  }
  var rows = []; // Rows for the dataTable.
  for (var i = 0; i < this.data.length; i++) {
    var new_row = [this.data[i].syn_time - lastEventTime];
    for (var j = 0; j < columns.length; j++) {
      new_row[new_row.length] = this.data[i][columns[j]];
    }
    rows[rows.length] = new_row;
  }
  data.addRows(rows);
  return data;
}

/**
 * This function generate csv file of the events and then download it.
 */
PointerEventBuffer.prototype.saveEventsToCSV = function() {
  var text = "syn_time, x, y, tilt_x, tilt_y, pressure, major, minor \n";
  for (var i = 0; i < this.data.length; i++) {
    text += this.data[i].syn_time;
    text += ",";
    text += this.data[i].x;
    text += ",";
    text += this.data[i].y;
    text += ",";
    text += this.data[i].tilt_x;
    text += ",";
    text += this.data[i].tilt_y;
    text += ",";
    text += this.data[i].pressure;
    text += ",";
    text += this.data[i].touch_major;
    text += ",";
    text += this.data[i].touch_minor;
    text += "\n";
  }
  var element = document.createElement('a');
  element.setAttribute('href',
      'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
  element.setAttribute('download', "events.csv");

  element.style.display = 'none';
  document.body.appendChild(element);

  element.click();
  document.body.removeChild(element);
}

/**
 * Draw rolling line chart for touch events.
 * @constructor
 * @param {Element} xyChartDiv the div to draw xy chart.
 * @param {Element} tiltChartDiv the div to draw tilt chart.
 * @param {Element} pressureChartDiv the div to draw pressure chart.
 * @param {Element} majorChartDiv the div to draw major chart.
 * @param {Element} minorChartDiv the div to draw minor chart.
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
 * @param {int} majorMin the min major value of the touch device.
 * @param {int} majorMax the max major value of the touch device.
 * @param {int} minorMin the min minor value of the touch device.
 * @param {int} minorMax the max minor value of the touch device.
 */
function TouchLineChart(xyChartDiv, tiltChartDiv, pressureChartDiv,
    majorChartDiv, minorChartDiv, touchMinX,
    touchMaxX, touchMinY, touchMaxY, touchMinPressure, touchMaxPressure,
    tiltMinX, tiltMaxX, tiltMinY, tiltMaxY, majorMin, majorMax, minorMin,
    minorMax) {
  this.xyChartMin = Math.min(touchMinX, touchMinY);
  this.xyChartMax = Math.min(touchMaxX, touchMaxY);
  this.tiltChartMin = Math.min(tiltMinX, tiltMinY);
  this.tiltChartMax = Math.min(tiltMaxX, tiltMaxY);
  this.pressureChartMin = touchMinPressure;
  this.pressureChartMax = touchMaxPressure;
  this.majorMin = majorMin;
  this.majorMax = majorMax;
  this.minorMin = minorMin;
  this.minorMax = minorMax;
  this.eventBuffer = new PointerEventBuffer();

  this.initCharts(xyChartDiv, tiltChartDiv, pressureChartDiv, majorChartDiv,
      minorChartDiv);
  this.drawCharts();
}

/**
 * Get chart options.
 * @param {string} vName Name of the v axis.
 * @param {int} minValue Min value of v axis.
 * @param {int} maxValue Max value of v axis.
 */
TouchLineChart.prototype.getChartOptions = function(vName, minValue, maxValue) {

  var options = {
    width: 1200,
    height: 400,
    hAxis: {
      title: 'Time',
      minValue: -this.eventBuffer.expireTime,
      maxValue:0,
    },
    vAxis: {
      title: vName,
      minValue: minValue,
      maxValue: maxValue,
    },
    colors: ['#a52714', '#097138'],
  };
  return options;
}

/**
 * This function init all the line charts.
 * @param {Element} xyChartDiv div for the xy chart.
 * @param {Element} tiltChartDiv div for the tilt chart.
 * @param {Element} pressureChartDiv div for the pressure chart.
 * @param {Element} majorChartDiv div for the major chart.
 * @param {Element} minorChartDiv div for the minor chart.
 */
TouchLineChart.prototype.initCharts = function(xyChartDiv, tiltChartDiv,
  pressureChartDiv, majorChartDiv, minorChartDiv) {
  this.xyChart = new google.visualization.LineChart(xyChartDiv);
  this.xyChartOption = this.getChartOptions("Position", this.xyChartMin,
      this.xyChartMax);

  this.tiltChart = new google.visualization.LineChart(tiltChartDiv);
  this.tiltChartOption = this.getChartOptions("Tilt", this.tiltChartMin,
      this.tiltChartMax);

  this.pressureChart =
      new google.visualization.LineChart(pressureChartDiv);
  this.pressureChartOption = this.getChartOptions("Pressure",
      this.pressureChartMin, this.pressureChartMax);

  this.majorChart =
      new google.visualization.LineChart(majorChartDiv);
  this.majorOptions = this.getChartOptions("Major",
      this.majorMin, this.majorMax);

  this.minorChart =
      new google.visualization.LineChart(minorChartDiv);
  this.minorOptions = this.getChartOptions("Minor",
      this.minorMin, this.minorMax);
}

/**
 * This function draw all the chart of the data from eventBuffer.
 */
TouchLineChart.prototype.drawCharts = function() {
  this.xyChart.draw(this.eventBuffer.getDataTableForColumns(['x', 'y']),
      this.xyChartOption);

  this.tiltChart.draw(this.eventBuffer.getDataTableForColumns(
      ['tilt_x', 'tilt_y']), this.tiltChartOption);

  this.pressureChart.draw(this.eventBuffer.getDataTableForColumns(['pressure']),
      this.pressureChartOption);

  this.majorChart.draw(this.eventBuffer.getDataTableForColumns(['touch_major']),
      this.majorOptions);

  this.minorChart.draw(this.eventBuffer.getDataTableForColumns(['touch_minor']),
      this.minorOptions);
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
 *       TouchPoint(tid=13, slot=0, syn_time=1420522152.269537, x=440, y=277,
 *                 pressure=33),
 *       TouchPoint(tid=14, slot=1, syn_time=1420522152.269537, x=271, y=308,
 *                 pressure=38)
 *     ]
 *   )
 */
TouchLineChart.prototype.processSnapshot = function(snapshot) {
  if (snapshot.fingers.length && snapshot.fingers[0].x) {
    this.eventBuffer.appendEvent(snapshot.fingers[0]);
  }
}


TouchLineChart.prototype.quitFlag = false;

/**
 * Send a 'quit' message to the server and display the event file name
 * on the canvas.
 * @param {boolean} closed_by_server True if this is requested by the server.
 */
function quit(closed_by_server) {
  // Capture the image before clearing the canvas and send it to the server,
  // and notify the server that this client quits.
  if (!touchLineChart.quitFlag) {
    touchLineChart.quitFlag = true;
    window.ws.send('quit');
  }
}

/**
 * A handler for keyup events to handle user hot keys.
 */
function keyupHandler() {
  var key = String.fromCharCode(event.which).toLowerCase();
  var ESC = String.fromCharCode(27);

  switch(String.fromCharCode(event.which).toLowerCase()) {
    // 's': Save the data as csv.
    case 's':
      window.touchLineChart.eventBuffer.saveEventsToCSV();
      break;
  }
}

/**
 * Create a web socket and a new TouchLineChart object.
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
  var majorMin = document.getElementById('majorMin').innerText;
  var majorMax = document.getElementById('majorMax').innerText;
  var minorMin = document.getElementById('minorMin').innerText;
  var minorMax = document.getElementById('minorMax').innerText;

  if (window.WebSocket) {
    ws = new WebSocket(websocket);
    ws.addEventListener("message", function(event) {
      if (event.data == 'quit') {
        quit(true);
      } else {
        var snapshot = JSON.parse(event.data);
        touchLineChart.processSnapshot(snapshot);
      }
    });
  } else {
    alert('WebSocket is not supported on this browser!')
  }

  touchLineChart = new TouchLineChart(document.getElementById('xyChart'),
                        document.getElementById('tiltChart'),
                        document.getElementById('pressureChart'),
                        document.getElementById('touchMajorChart'),
                        document.getElementById('touchMinorChart'),
                        touchMinX, touchMaxX, touchMinY, touchMaxY,
                        touchMinPressure, touchMaxPressure, tiltMinX, tiltMaxX,
                        tiltMinY, tiltMaxY);
  window.setInterval(function() {
    touchLineChart.drawCharts();
  }, 33);
}

/**
 * Init google chart.
 */
function InitChart() {
  google.charts.load('current', {'packages':['corechart']});
  google.charts.setOnLoadCallback(createWS);
}

