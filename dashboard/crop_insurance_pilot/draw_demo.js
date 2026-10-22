/*
 * draw_demo.js -- interactive "draw your own field" crop-insurance
 * what-if demo (owner request, 2026-10-22).
 *
 * REAL: field geometry/area (your own drawn polygon, real spherical
 * area), land-use split (live Google Earth Engine Dynamic World via the
 * Mera Khet Worker), NDVI/field-wetness (same live Worker), crop yield
 * baseline (real DES, data.desagri.gov.in) and mandi modal price (real
 * AGMARKNET, data.gov.in) for the crop+district you pick.
 *
 * SYNTHETIC: the khasra number (randomly generated, SYN- prefixed, no
 * real land record behind it -- same non-realistic-ID convention as
 * every other synthetic identifier in this repo).
 *
 * USER CHOICE, not AI output: the crop (not auto-detected -- real crop-
 * type classification is not integrated anywhere in this project, see
 * docs/PANEL_SOURCE_AUDIT.md) and the loss% (a what-if slider, never an
 * automated damage estimate). The resulting indicative value is
 * decision-support arithmetic on real inputs, not an insurance claim
 * determination.
 */
(function () {
  'use strict';

  var WORKER_ANALYZE_URL = 'https://vindhya-mera-khet.vindhyaresearch25.workers.dev/analyze';
  var R_EARTH = 6371000, RAD = Math.PI / 180;

  var map, drawLayer = null, marks = [], pts = [], drawing = false;
  var districtsIndex = null, desData = null, mandiData = null, lastAnalyze = null, lastAreaHa = null;

  function el(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  }); }
  function slug(x) { return String(x || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, ''); }
  function inr(v) { return v == null || isNaN(v) ? '--' : '₹' + Math.round(v).toLocaleString('en-IN'); }
  function row(k, v) { return '<div class="k">' + k + '</div><div class="v">' + v + '</div>'; }

  // Spherical polygon area -- same formula already used elsewhere in this
  // repo (dashboard/geoai_professional.js's ringAreaM2 / this repo's own
  // Python generators), not a new/unverified approach.
  function ringAreaHa(ring) {
    if (ring.length < 3) return 0;
    var total = 0;
    for (var i = 0; i < ring.length; i++) {
      var p1 = ring[i], p2 = ring[(i + 1) % ring.length];
      total += (p2[0] - p1[0]) * RAD * (2 + Math.sin(p1[1] * RAD) + Math.sin(p2[1] * RAD));
    }
    return Math.abs(total * R_EARTH * R_EARTH / 2) / 10000;
  }

  function fetchJson(url) { return fetch(url).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }

  // ------------------------------------------------------------------
  // District cascading select
  // ------------------------------------------------------------------
  function initDistrictSelect() {
    fetchJson('../data/boundaries/soi/districts_index.json').then(function (d) {
      if (!d) return;
      districtsIndex = d.districts;
      var states = Array.from(new Set(districtsIndex.map(function (x) { return x.state_name; }))).sort();
      var sel = el('selState');
      states.forEach(function (s) { sel.innerHTML += '<option value="' + esc(s) + '">' + esc(s) + '</option>'; });
      // Default to Madhya Pradesh (where the richest real DES/mandi/soil data in this repo lives).
      sel.value = 'Madhya Pradesh';
      fillDistricts('Madhya Pradesh');
    });
  }
  function fillDistricts(state) {
    var dsel = el('selDistrict');
    dsel.innerHTML = '<option value="">District...</option>';
    if (!state || !districtsIndex) { dsel.disabled = true; return; }
    districtsIndex.filter(function (x) { return x.state_name === state; })
      .sort(function (a, b) { return a.district_name.localeCompare(b.district_name); })
      .forEach(function (x) { dsel.innerHTML += '<option value="' + esc(x.district_name) + '">' + esc(x.district_name) + '</option>'; });
    dsel.disabled = false;
    dsel.value = state === 'Madhya Pradesh' ? 'Indore' : '';
    onDistrictChosen();
  }
  function onDistrictChosen() {
    var state = el('selState').value, district = el('selDistrict').value;
    el('btnDraw').disabled = !district;
    if (!district) return;
    desData = null; mandiData = null;
    fetchJson('../data/crop_stats_des_by_district/' + slug(state) + '/' + slug(district) + '.json').then(function (d) { desData = d; });
    fetchJson('../data/mandi_prices.json').then(function (d) {
      mandiData = d && d.districts ? d.districts[slug(district)] : null;
    });
  }

  // ------------------------------------------------------------------
  // Map + draw
  // ------------------------------------------------------------------
  function initMap() {
    map = L.map('map').setView([22.9734, 78.6569], 6); // India-wide default
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 19, attribution: 'Tiles &copy; Esri' }).addTo(map);
    map.on('click', function (e) { if (drawing) addPoint(e.latlng); });
    map.on('dblclick', function () { if (drawing) finishDraw(); });
  }

  function addPoint(latlng) {
    pts.push([latlng.lng, latlng.lat]);
    marks.push(L.circleMarker(latlng, { radius: 4, color: '#d4793a', fillColor: '#fff', fillOpacity: 1, weight: 2 }).addTo(map));
    if (drawLayer) map.removeLayer(drawLayer);
    if (pts.length > 1) {
      drawLayer = L.polyline(pts.map(function (p) { return [p[1], p[0]]; }), { color: '#d4793a', weight: 2 }).addTo(map);
    }
    el('drawStatus').textContent = 'Points: ' + pts.length + '. Click "Finish polygon" or double-click the map when done (min 3 points).';
  }

  function startDraw() {
    resetDraw();
    drawing = true;
    map.getContainer().style.cursor = 'crosshair';
    el('btnFinish').disabled = false;
    el('drawStatus').textContent = 'Click on the map to place field corners.';
  }

  function finishDraw() {
    if (pts.length < 3) { el('drawStatus').textContent = 'Need at least 3 points to close a field.'; return; }
    drawing = false;
    map.getContainer().style.cursor = '';
    el('btnFinish').disabled = true;
    if (drawLayer) map.removeLayer(drawLayer);
    marks.forEach(function (m) { map.removeLayer(m); });
    var ring = pts.slice(); ring.push(pts[0]);
    drawLayer = L.polygon(ring.map(function (p) { return [p[1], p[0]]; }), { color: '#1a6b3c', weight: 2.5, fillColor: '#1a6b3c', fillOpacity: 0.15 }).addTo(map);
    map.fitBounds(drawLayer.getBounds(), { padding: [30, 30] });
    el('drawStatus').textContent = 'Field closed. Running real satellite check...';
    runAnalysis(ring);
  }

  function resetDraw() {
    drawing = false;
    pts = []; marks.forEach(function (m) { map.removeLayer(m); }); marks = [];
    if (drawLayer) { map.removeLayer(drawLayer); drawLayer = null; }
    el('btnFinish').disabled = true;
    el('drawStatus').textContent = 'Pick a state and district, then click "Draw field".';
    el('panelField').innerHTML = '<div class="empty">Draw a field to see this.</div>';
    el('panelLoss').innerHTML = '<div class="empty">Draw a field and wait for the satellite check to finish.</div>';
    lastAnalyze = null; lastAreaHa = null;
  }

  // ------------------------------------------------------------------
  // Real satellite check + synthetic khasra
  // ------------------------------------------------------------------
  function randomKhasra() {
    return 'SYN-DRAW-' + Math.floor(1000 + Math.random() * 9000) + '/' + (1 + Math.floor(Math.random() * 4));
  }

  function runAnalysis(ring) {
    var areaHa = ringAreaHa(ring.slice(0, -1));
    lastAreaHa = areaHa;
    var khasra = randomKhasra();
    el('panelField').innerHTML = '<div class="empty">Querying Google Earth Engine (live)&hellip;</div>';

    fetch(WORKER_ANALYZE_URL, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ring: ring }) })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        lastAnalyze = data;
        renderField(khasra, areaHa, data);
        renderLossPanel();
      })
      .catch(function () {
        lastAnalyze = { available: false, reason: 'request_failed' };
        renderField(khasra, areaHa, lastAnalyze);
      });
  }

  function renderField(khasra, areaHa, data) {
    var h = '<div class="kv">' +
      row('Synthetic khasra <span class="tag syn">synthetic</span>', esc(khasra)) +
      row('Total area (real geometry) <span class="tag ok">real</span>', areaHa.toFixed(3) + ' ha') +
      '</div>';

    if (!data || !data.available) {
      h += '<div class="note" style="color:#96231f;"><b>Live satellite query unavailable</b> (' + esc((data && (data.reason || data.error)) || 'unknown') + '). No land-use split shown -- not substituted with a guess.</div>';
      el('panelField').innerHTML = h;
      return;
    }

    var lu = data.land_use_breakdown;
    if (lu) {
      var cropHa = areaHa * lu.cropland_fraction, forestHa = areaHa * lu.forest_tree_cover_fraction, otherHa = areaHa * lu.other_noncrop_fraction;
      h += '<div class="sep" style="border-top:1px solid var(--line);margin:8px 0;"></div>';
      h += '<div class="kv">' +
        row('Cropland (live Dynamic World) <span class="tag ok">real</span>', cropHa.toFixed(3) + ' ha (' + (lu.cropland_fraction * 100).toFixed(1) + '%)') +
        row('Forest/tree cover <span class="tag ok">real</span>', forestHa.toFixed(3) + ' ha (' + (lu.forest_tree_cover_fraction * 100).toFixed(1) + '%)') +
        row('Other (bund/path/fallow/built/water) <span class="tag ok">real</span>', otherHa.toFixed(3) + ' ha (' + (lu.other_noncrop_fraction * 100).toFixed(1) + '%)') +
        '</div>';
      h += '<div class="note">' + esc(lu.note) + '</div>';
    }
    h += '<div class="kv" style="margin-top:6px;">' +
      row('NDVI now <span class="tag ok">real</span>', data.ndvi != null ? data.ndvi.toFixed(3) : (esc(data.ndvi_error) || '--')) +
      row('Field wetness vs. district <span class="tag ok">real</span>', data.field_wetness_index_relative != null ? data.field_wetness_index_relative.toFixed(1) + '%' : (esc(data.wetness_error) || '--')) +
      '</div>';
    el('panelField').innerHTML = h;
  }

  // ------------------------------------------------------------------
  // Crop + loss what-if, real DES yield x real mandi price
  // ------------------------------------------------------------------
  function availableCrops() {
    if (!desData || !desData.records || !mandiData || !mandiData.records) return [];
    var desCrops = {};
    desData.records.forEach(function (r) {
      if (r.yield_per_ha != null) { desCrops[r.crop] = desCrops[r.crop] || r; if (r.year > (desCrops[r.crop].year || '')) desCrops[r.crop] = r; }
    });
    var mandiCrops = {};
    mandiData.records.forEach(function (r) { mandiCrops[r.commodity] = mandiCrops[r.commodity] || []; mandiCrops[r.commodity].push(r.modal_price); });
    var out = [];
    Object.keys(desCrops).forEach(function (c) {
      var matchKey = Object.keys(mandiCrops).filter(function (m) { return slug(m).indexOf(slug(c)) === 0 || slug(c).indexOf(slug(m)) === 0; })[0];
      if (matchKey) {
        var prices = mandiCrops[matchKey];
        var modal = prices.reduce(function (a, b) { return a + b; }, 0) / prices.length;
        out.push({ crop: c, yield_per_ha: desCrops[c].yield_per_ha, mandi_commodity: matchKey, modal_price_per_qtl: modal, n_mandi_rows: prices.length });
      }
    });
    return out.sort(function (a, b) { return a.crop.localeCompare(b.crop); });
  }

  function renderLossPanel() {
    if (!lastAnalyze || !lastAnalyze.available || !lastAnalyze.land_use_breakdown) {
      el('panelLoss').innerHTML = '<div class="empty">Need a successful satellite check first.</div>';
      return;
    }
    var crops = availableCrops();
    if (!crops.length) {
      el('panelLoss').innerHTML = '<div class="empty">No crop has both a real DES yield baseline and a real current AGMARKNET price in this district right now -- no indicative value can be computed honestly.</div>';
      return;
    }
    var h = '<div class="ctrlrow"><select id="selCrop">' +
      crops.map(function (c, i) { return '<option value="' + i + '">' + esc(c.crop) + '</option>'; }).join('') +
      '</select></div>';
    h += '<div class="sliderrow"><span style="font-size:12px;color:var(--dim);">Loss %</span>' +
      '<input type="range" id="lossSlider" min="10" max="100" step="5" value="50">' +
      '<span class="bigval" id="lossVal" style="font-size:16px;">50%</span></div>';
    h += '<div id="lossResult" style="margin-top:10px;"></div>';
    el('panelLoss').innerHTML = h;

    window._drawDemoCrops = crops;
    el('selCrop').onchange = computeLoss;
    el('lossSlider').oninput = function () { el('lossVal').textContent = this.value + '%'; computeLoss(); };
    computeLoss();
  }

  function computeLoss() {
    var crops = window._drawDemoCrops || [];
    var c = crops[parseInt(el('selCrop').value, 10)];
    if (!c || lastAreaHa == null) return;
    var lossPct = parseInt(el('lossSlider').value, 10);
    var lu = lastAnalyze.land_use_breakdown;
    var cultHa = lastAreaHa * lu.cropland_fraction;
    var normalProdT = cultHa * c.yield_per_ha;
    var lossProdT = normalProdT * (lossPct / 100);
    var lossQtl = lossProdT * 10; // tonnes -> quintals, AGMARKNET convention
    var indicativeValue = lossQtl * c.modal_price_per_qtl;

    var h = '<div class="kv">' +
      row('Cultivated area used <span class="tag ok">real</span>', cultHa.toFixed(3) + ' ha') +
      row('DES yield baseline <span class="tag ok">real</span>', c.yield_per_ha.toFixed(3) + ' t/ha') +
      row('Normal production (this field)', normalProdT.toFixed(3) + ' t') +
      row('Mandi modal price <span class="tag ok">real</span>', inr(c.modal_price_per_qtl) + ' / quintal') +
      row('Matched mandi commodity', esc(c.mandi_commodity) + ' (' + c.n_mandi_rows + ' row' + (c.n_mandi_rows > 1 ? 's' : '') + ')') +
      '</div>';
    h += '<div style="margin-top:10px;padding:10px 12px;background:var(--ok-bg);border-radius:8px;">' +
      '<div style="font-size:10.5px;color:var(--ok);font-weight:800;text-transform:uppercase;">Indicative loss value at ' + lossPct + '%</div>' +
      '<div class="bigval">' + inr(indicativeValue) + '</div></div>';
    h += '<div class="note"><b>Decision-support arithmetic only.</b> Loss % is your own what-if input, not an AI damage estimate. ' +
      'Real notified PMFBY Sum Insured / Scale of Finance is NOT used here -- this is a market-value illustration (real yield &times; real mandi price), not an official claim calculation.</div>';
    el('lossResult').innerHTML = h;
  }

  // ------------------------------------------------------------------
  function boot() {
    initMap();
    initDistrictSelect();
    el('selState').onchange = function () { fillDistricts(this.value); };
    el('selDistrict').onchange = onDistrictChosen;
    el('btnDraw').onclick = startDraw;
    el('btnFinish').onclick = finishDraw;
    el('btnReset').onclick = resetDraw;
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
