'use strict';
const map = L.map('map', {zoomControl: false, minZoom: 2, maxZoom: 18, worldCopyJump: true}).setView([20, 0], 2);
L.control.zoom({position: 'topright'}).addTo(map);
let tiles, marker, position, accuracyCircle;
window.startMap = function () {
  if (tiles) return;
  tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, keepBuffer: 1,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
  });
  tiles.on('tileerror', () => { document.getElementById('tile-error').style.display = 'block'; });
  tiles.on('load', () => {
    const visible = Array.from(document.querySelectorAll('.leaflet-tile'));
    const failed = visible.some(tile => !tile.naturalWidth);
    document.getElementById('tile-error').style.display = failed ? 'block' : 'none';
  });
  tiles.addTo(map);
};
window.locationStatus = function (text, clear) {
  document.getElementById('state').textContent = text;
  if (clear) {
    if (marker) { map.removeLayer(marker); marker = null; }
    if (accuracyCircle) { map.removeLayer(accuracyCircle); accuracyCircle = null; }
    position = null;
    document.getElementById('center').disabled = true;
    document.getElementById('place').textContent = 'My location';
    document.getElementById('coordinates').textContent = '-- / --';
    document.getElementById('source').textContent = 'NO POSITION DETECTED';
  }
};
window.showLocation = function (data) {
  if (!Number.isFinite(data.latitude) || !Number.isFinite(data.longitude)) return;
  position = [data.latitude, data.longitude];
  if (marker) map.removeLayer(marker);
  if (accuracyCircle) { map.removeLayer(accuracyCircle); accuracyCircle = null; }
  marker = L.marker(position, {icon: L.divIcon({className: 'target', iconSize: [28, 28], iconAnchor: [14, 14]})}).addTo(map);
  document.getElementById('place').textContent = data.label;
  document.getElementById('source').textContent = data.source.toUpperCase();
  document.getElementById('coordinates').textContent = data.latitude.toFixed(5) + ' / ' + data.longitude.toFixed(5);
  const device = data.kind === 'device';
  const accuracyKnown = device && Number.isFinite(data.accuracy) && data.accuracy >= 0;
  document.getElementById('state').textContent = device ? (accuracyKnown ? 'REPORTED ACCURACY: +/- ' + Math.round(data.accuracy) + ' m' : 'DEVICE POSITION / ACCURACY UNKNOWN') : (data.source.startsWith('IP') ? 'APPROXIMATE AREA' : 'SELECTED POSITION');
  if (accuracyKnown && data.accuracy > 0) {
    accuracyCircle = L.circle(position, {radius: data.accuracy, color:'#5edbff', weight:1, fillOpacity:.08}).addTo(map);
  }
  document.getElementById('center').disabled = false;
  if (accuracyCircle && data.accuracy > 500) map.fitBounds(accuracyCircle.getBounds(), {padding:[60,60], maxZoom:14});
  else map.flyTo(position, device && accuracyKnown ? 14 : 10, {duration: 1.8});
};
document.getElementById('center').addEventListener('click', () => { if (position) map.panTo(position); });
new ResizeObserver(() => map.invalidateSize()).observe(document.getElementById('map'));
