/*
 * soil_type_loader.js -- real national soil-type coverage (2026-10-21),
 * from dashboard/data/soil_type/<state_slug>/<district_slug>.json
 * (scripts/17_gee_national_soil_type.py, real OpenLandMap/ISRIC texture-
 * class raster via GEE -- see that script's header for why Soil Health
 * Card / NBSS&LUP were checked and rejected first: neither has a public
 * bulk API).
 *
 * HONESTY RULES this file exists to get right:
 *   - This is a global 250m statistical soil map, NOT an India-specific
 *     ground survey like a Soil Health Card test -- every render says so,
 *     never presented as equivalent.
 *   - Texture is a CATEGORY (one of 12 USDA classes), never averaged into
 *     a number -- the dominant class plus the real pixel-count histogram
 *     behind it is shown, not just a bare winner.
 *   - Village tier shows the real sampled class for that village's own
 *     centroid pixel (not a shared district value) -- when the sample
 *     was unavailable for a given village, that village is simply absent
 *     from the file's villages map, never backfilled.
 *   - A district with no real coverage says so plainly.
 *
 * Pattern: same addPane()-as-its-own-bottom-tab approach as
 * soil_moisture_loader.js/groundwater_loader.js.
 */
(function () {
  'use strict';

  var manifestPromise = null;
  var manifestSet = null; // "stateSlug/districtSlug" -> true
  var cache = {};

  function el(id) { return document.getElementById(id); }

  function fetchWithTimeout(url) {
    var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    var timer = controller ? setTimeout(function () { controller.abort(); }, 30000) : null;
    return fetch(url, controller ? { signal: controller.signal } : undefined)
      .finally(function () { if (timer) clearTimeout(timer); });
  }

  function slugify(s) {
    return String(s || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  }

  function loadManifest() {
    if (manifestPromise) return manifestPromise;
    manifestPromise = fetchWithTimeout('data/soil_type/manifest.json')
      .then(function (r) { return r.ok ? r.json() : { districts: [] }; })
      .then(function (d) {
        manifestSet = {};
        (d.districts || []).forEach(function (k) { manifestSet[k] = true; });
        return manifestSet;
      })
      .catch(function () { manifestSet = {}; return manifestSet; });
    return manifestPromise;
  }

  function loadDistrictFile(stateName, districtName) {
    var key = slugify(stateName) + '/' + slugify(districtName);
    if (cache[key] !== undefined) return Promise.resolve(cache[key]);
    return loadManifest().then(function (set) {
      if (!set[key]) { cache[key] = null; return null; }
      return fetchWithTimeout('data/soil_type/' + key + '.json')
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { cache[key] = d; return d; })
        .catch(function () { cache[key] = null; return null; });
    });
  }

  function histogramRows(counts) {
    var total = 0, rows = [];
    Object.keys(counts || {}).forEach(function (k) { total += counts[k]; });
    Object.keys(counts || {}).forEach(function (k) {
      var pct = total ? (counts[k] / total * 100) : 0;
      rows.push({ name: k, pct: pct });
    });
    rows.sort(function (a, b) { return b.pct - a.pct; });
    return rows.map(function (r) {
      return '<div style="display:flex;justify-content:space-between;gap:0.5rem;padding:0.15rem 0;">'
        + '<span>' + r.name + '</span><span style="color:var(--text-dim);">' + r.pct.toFixed(1) + '%</span></div>';
    }).join('');
  }

  function renderDistrict(file, sel) {
    var host = el('soiltype-panel-body');
    if (!host) return;
    if (!file) {
      host.className = 'btm-pane-empty';
      host.innerHTML = '<i class="fa fa-layer-group chart-empty-icon"></i>'
        + '<span>No real soil-type coverage computed for this district yet.</span>';
      return;
    }
    var d = file.district;
    var vilRow = null;
    if (sel && sel.villageLgd && file.villages && file.villages[sel.villageLgd]) {
      var v = file.villages[sel.villageLgd];
      vilRow = '<div style="padding:0.5rem 0.75rem;border-top:1px solid var(--border);">'
        + '<div style="font-weight:700;">' + (v[0] || 'Selected village') + ' — real sampled pixel</div>'
        + '<div style="color:var(--cyan);font-size:var(--fs-4);font-weight:700;">' + (v[3] || '—') + '</div>'
        + '</div>';
    }
    host.className = 'u-scroll-pane';
    host.innerHTML = ''
      + '<div style="padding:0.6rem 0.75rem;">'
      + '<div style="font-size:var(--fs-1);color:var(--text-dim);">District-dominant texture class (mode of '
      + (d.n_pixels || 0) + ' real 250m pixels)</div>'
      + '<div style="color:var(--cyan);font-size:var(--fs-5);font-weight:800;">' + (d.dominant_class || '—') + '</div>'
      + '</div>'
      + '<div style="padding:0 0.75rem 0.5rem;font-size:var(--fs-1);">' + histogramRows(d.class_pixel_counts) + '</div>'
      + (vilRow || '')
      + '<div style="padding:0.5rem 0.75rem;font-size:var(--fs-1);color:var(--text-dim);border-top:1px solid var(--border);">'
      + 'Source · OpenLandMap/ISRIC (global 250m statistical soil map, via Google Earth Engine) — '
      + 'not an India-specific ground survey. ' + (file.village_count_sampled || 0) + '/'
      + (file.village_count_total || 0) + ' villages sampled. No block-level tier yet.'
      + '</div>';
  }

  function render() {
    var stateSel = el('stateSelect'), distSel = el('districtSelect'), vilSel = el('villageSelect');
    var stateName = stateSel && stateSel.value ? (stateSel.options[stateSel.selectedIndex].text) : null;
    var distName = distSel && distSel.value ? (distSel.options[distSel.selectedIndex].text) : null;
    var host = el('soiltype-panel-body');
    if (!host) return;
    if (!stateName || !distName) {
      host.className = 'btm-pane-empty';
      host.innerHTML = '<i class="fa fa-layer-group chart-empty-icon"></i>'
        + '<span>राज्य/ज़िला चुनें · Select a state/district</span>'
        + '<button class="btm-pane-empty-btn" onclick="focusLocationSelector()"><i class="fa fa-location-crosshairs"></i> Select district</button>';
      return;
    }
    loadDistrictFile(stateName, distName).then(function (file) {
      renderDistrict(file, { villageLgd: vilSel && vilSel.value ? vilSel.value : null });
    });
  }

  function addPane() {
    var first = document.querySelector('.btm-pane');
    var host = first ? first.parentNode : null;
    if (!host || el('pane-soiltype')) return;

    var p = document.createElement('div');
    p.className = 'btm-pane';
    p.id = 'pane-soiltype';
    p.innerHTML = '<div class="section-header"><i class="fa fa-layer-group u-cyan-sm"></i>'
      + '<div class="section-title">SOIL TYPE — OpenLandMap/ISRIC (250 m)</div></div>'
      + '<div id="soiltype-panel-body" class="btm-pane-empty">'
      + '<i class="fa fa-layer-group chart-empty-icon"></i><span>राज्य/ज़िला चुनें · Select a state/district</span>'
      + '<button class="btm-pane-empty-btn" onclick="focusLocationSelector()"><i class="fa fa-location-crosshairs"></i> Select district</button></div>';
    host.appendChild(p);

    var firstTab = document.querySelector('.btm-tab');
    var tabs = firstTab ? firstTab.parentNode : null;
    if (tabs && !el('soiltype-tab')) {
      var tab = document.createElement('div');
      tab.innerHTML = '<i class="fa fa-layer-group"></i>Soil Type';
      tab.className = 'btm-tab';
      tab.id = 'soiltype-tab';
      tab.onclick = function () {
        var panes = document.querySelectorAll('.btm-pane'), i;
        for (i = 0; i < panes.length; i++) panes[i].classList.remove('active');
        el('pane-soiltype').classList.add('active');
        var tb = document.querySelectorAll('.btm-tab');
        for (i = 0; i < tb.length; i++) tb[i].classList.remove('active');
        this.classList.add('active');
        render();
      };
      tabs.appendChild(tab);
    }
  }

  function wireSelectionHooks() {
    var originalOnDistrictChange = window.onDistrictChange;
    window.onDistrictChange = function (distKey) {
      if (typeof originalOnDistrictChange === 'function') originalOnDistrictChange(distKey);
      setTimeout(render, 0);
    };
    var originalOnVillageChange = window.onVillageChange;
    window.onVillageChange = function (vilLgd) {
      if (typeof originalOnVillageChange === 'function') originalOnVillageChange(vilLgd);
      setTimeout(render, 0);
    };
  }

  function boot() {
    if (!document.querySelector('.btm-pane')) { setTimeout(boot, 700); return; }
    try { addPane(); wireSelectionHooks(); } catch (e) { console.warn('[soil_type_loader]', e); }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(boot, 1000); });
  } else {
    setTimeout(boot, 1000);
  }

  window.VindhyaSoilType = { reload: render };
})();
