// Copyright 2017 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * HeatMapEventBuffer buffer the heatmap event.
 * @constructor
 * @param {int} maxSize max size of the buffer.
 */
function HeatMapEventBuffer(maxSize = 50) {
  this.maxSize = maxSize;
  this.rawData = [];
  this.avgData = [];
  this.floorLevel = 0;
  this.sigData = [];
  this.sigData3 = [];
}

/**
 * Following are set of helper functions used to calculate avg, sig, and floor.
 */

// Elementwise sum of 2d array.
ElementwiseSum = arr=>arr.reduce((arr1,arr2)=>arr1.map((a,i)=>a+arr2[i]));
// Average of 2d array.
Average2D = arr=>ElementwiseSum(arr).map(a=>a/arr.length);
// Max of 1d array.
Max1D = arr=>arr.reduce((a,b)=>Math.max(a,b));
// Average of 1d Array.
Average1D = arr=>arr.reduce((a,b)=>a+b)/arr.length

/**
 * Function to add new event to the buffer.
 * @param {object} newEventData new heatmap data
 */
HeatMapEventBuffer.prototype.appendEvent = function(newEventData) {
  if (this.rawData.length >= this.maxSize) {
    this.rawData.shift();
  }
  if (this.avgData.length >= this.maxSize) {
    this.avgData.shift();
  }
  if (this.sigData.length >= this.maxSize) {
    this.sigData.shift();
  }
  this.rawData[this.rawData.length] = newEventData;
  this.avgData = Average2D(this.rawData);
  variance = Average2D(this.rawData.map(arr=>arr.map(
      (a, i)=>Math.pow(a - this.avgData[i], 2))));
  this.sigData = variance.map(x=>Math.sqrt(x));
  this.sigData3 = this.sigData.map((a,i)=>3*a + this.avgData[i]);
  this.floorLevel = Average1D(this.rawData.map(arr=>Max1D(arr)));
}

/**
 * Function to get dataTable from select columns. The dataTable will be used to
 * draw the linechart.
 * @return {google.visualization.DataTable}
 */
HeatMapEventBuffer.prototype.getDataTable = function() {
  var data = new google.visualization.DataTable();
  data.addColumn('number', 'value');
  data.addColumn('number', 'Floor');
  data.addColumn('number', 'Sigma');
  data.addColumn('number', 'Raw');
  data.addColumn('number', 'Avg');

  rows = [];
  lastIndex = this.rawData.length - 1;
  if (!this.rawData.length) {
    return data;
  }
  for (var i = 0; i < this.rawData[lastIndex].length; i++) {
    rows[rows.length] = [i, this.floorLevel, this.sigData3[i],
      this.rawData[lastIndex][i], this.avgData[i]]
  }

  data.addRows(rows);
  return data;
}

/**
 * EventBufferWrapper wrapper for x and y buffer.
 * @constructor
 */
function EventBufferWrapper() {
  this.xBuffer = new HeatMapEventBuffer();
  this.yBuffer = new HeatMapEventBuffer();
  this.startRecordFlag = false;
  this.serilizedHeatMap = "";
}

/**
 * Function to add new event to the correct buffer.
 * @param {object} newEvent new heatmap event
 */
EventBufferWrapper.prototype.appendEvent = function(newEvent) {
  if (newEvent.sensor == 'x') {
    this.xBuffer.appendEvent(newEvent.data);
  } else if (newEvent.sensor == 'y') {
    this.yBuffer.appendEvent(newEvent.data);
  }
  if (this.startRecordFlag) {
    this.serilizedHeatMap += newEvent.sensor;
    this.serilizedHeatMap += ",";
    for (var i = 0; i < newEvent.data.length; i++) {
      this.serilizedHeatMap += newEvent.data[i];
      this.serilizedHeatMap += ",";
    }
    this.serilizedHeatMap += "\n";
  }
}

/**
 * Function to get dataTable for the selected sensor.
 * @param {string} sensor x or y.
 */
EventBufferWrapper.prototype.getDataTable = function(sensor) {
  if (sensor == 'x') {
    return this.xBuffer.getDataTable();
  } else if (sensor == 'y') {
    return this.yBuffer.getDataTable();
  }
}

/**
 * Function to start recording heatmap.
 * @param {string} sensor x or y.
 */
EventBufferWrapper.prototype.startRecord = function() {
  this.startRecordFlag = true;
  this.serilizedHeatMap = "flag,";
  for (var i = 0; i < 64; i ++) {
    this.serilizedHeatMap += i;
    this.serilizedHeatMap += ",";
  }
  this.serilizedHeatMap += "\n";
}

/**
 * Function to stop recording heatmap and save the log file.
 * @param {string} sensor x or y.
 */
EventBufferWrapper.prototype.stopRecordAndSave = function() {
  this.startRecordFlag = false;
  var element = document.createElement('a');
  element.setAttribute('href',
      'data:text/plain;charset=utf-8,'
      + encodeURIComponent(this.serilizedHeatMap));
  element.setAttribute('download', "heatmap.csv");

  element.style.display = 'none';
  document.body.appendChild(element);

  element.click();
  document.body.removeChild(element);
}

/**
 * Draw chart for HeatMap readings.
 * @constructor
 * @param {Element} xChartDiv the div to draw x chart.
 * @param {Element} yChartDiv the div to draw y chart.
 */
function HeatMapChart(xChartDiv, yChartDiv) {
  this.eventBuffer = new EventBufferWrapper();

  this.initCharts(xChartDiv, yChartDiv);
  this.drawCharts();
}

/**
 * Get chart options.
 * @param {string} vName Name of the v axis.
 */
HeatMapChart.prototype.getChartOptions = function(vName) {
  var options = {
    vAxis: {
      title: vName,
      minValue: 1000,
      maxValue: 66000,
    },
    connectSteps: false,
    // The order of series is: Floor, Sigma, Raw, Average
    colors:['pink','yellow', '#000066', '#99ff33'],
    series: {
      0: {areaOpacity: 0.3},
      1: {areaOpacity: 1},
      2: {areaOpacity: 1},
      3: {areaOpacity: 0}},
  };
  return options;
}

/**
 * This function init all the line charts.
 * @param {Element} xChartDiv div for the x chart.
 * @param {Element} yChartDiv div for the y chart.
 */
HeatMapChart.prototype.initCharts = function(xChartDiv, yChartDiv) {
  this.xChart = new google.visualization.SteppedAreaChart(xChartDiv);
  this.yChart = new google.visualization.SteppedAreaChart(yChartDiv);
}

/**
 * This function draw all the chart of the data from eventBuffer.
 */
HeatMapChart.prototype.drawCharts = function() {
  this.xChart.draw(this.eventBuffer.getDataTable('x'),
      this.getChartOptions('x'));
  this.yChart.draw(this.eventBuffer.getDataTable('y'),
      this.getChartOptions('y'));
}

/**
 * Process an incoming HeatMapEvent.
 * @param {object} event
 */
HeatMapChart.prototype.processHeatMapEvent = function(event) {
    this.eventBuffer.appendEvent(event);
}

/**
 * Send setPole to backend and select the pole.
 * @param {object} event
 */
function setPole(pole) {
   window.ws.send('setPole:' + pole);
   window.console.log('setPole:' + pole);
   heatMapChart.eventBuffer = new EventBufferWrapper();
}

/**
 * Create a web socket and a new TouchLineChart object.
 */
function createWS() {
  var websocket = document.getElementById('websocketUrl').innerText;

  if (window.WebSocket) {
    ws = new WebSocket(websocket);
    ws.addEventListener("message", function(event) {
        var heatMapEvent = JSON.parse(event.data);
        heatMapChart.processHeatMapEvent(heatMapEvent);
    });
  } else {
    alert('WebSocket is not supported on this browser!')
  }

  heatMapChart = new HeatMapChart(document.getElementById('xChart'),
      document.getElementById('yChart'));

  window.setInterval(function() {
    heatMapChart.drawCharts();
  }, 33);
}

/**
 * Init google chart.
 */
function InitChart() {
  google.charts.load('current', {'packages':['corechart']});
  google.charts.setOnLoadCallback(createWS);
}

