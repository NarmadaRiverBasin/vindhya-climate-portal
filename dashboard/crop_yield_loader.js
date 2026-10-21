/*
 * crop_yield_loader.js -- real district-level crop yield outlook
 * (2026-10-21), from dashboard/data/crop_yield_outlook/<state_slug>/
 * <district_slug>.json (scripts/18_build_crop_yield_outlook.py).
 *
 * HONESTY RULES this file exists to get right:
 *   - This is a deterministic OLS trend on real DES yield_per_ha history
 *     (same style as forecast_2040.json), NEVER a satellite/ML model --
 *     docs/CROP_YIELD_METHODOLOGY.md's literature-grounded parcel-level
 *     model remains blocked on ground truth (CCE/Digital Crop Survey),
 *     and this panel must never be read as that model running.
 *   - Every number is labelled "indicative" and shows the real n_years
 *     and the 95% band -- never a bare projection.
 *   - A crop+season with fewer than 5 real DES years is simply absent
 *     from the file (scripts/18_...'s MIN_REAL_YEARS), never shown with
 *     a thin trend dressed up as reliable.
 */
(function () {
  'use strict';

  var manifestPromise = null;
  var manifestSet = null;
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
    manifestPromise = fetchWithTimeout('data/crop_yield_outlook/manifest.json')
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
      return fetchWithTimeout('data/crop_yield_outlook/' + key + '.json')
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { cache[key] = d; return d; })
        .catch(function () { cache[key] = null; return null; });
    });
  }

  function row(c) {
    return '<div style="display:grid;grid-template-columns:1.6fr 0.9fr 0.9fr 1fr;gap:0.4rem;'
      + 'padding:0.35rem 0;border-bottom:1px solid var(--border);font-size:var(--fs-1);align-items:center;">'
      + '<span>' + c.crop + ' <span style="color:var(--text-dim);">(' + c.season + ')</span></span>'
      + '<span style="color:var(--text-dim);">' + c.n_real_years + ' yrs real</span>'
      + '<span style="color:var(--text-dim);">mean ' + c.yield_per_ha_mean + '</span>'
      + '<span style="color:var(--cyan);font-weight:700;">' + c.next_year + ': ~' + c.next_year_yield_indicative
      + ' <span style="color:var(--text-dim);font-weight:400;">(' + c.next_year_yield_lo95 + '–'
      + c.next_year_yield_hi95 + ')</span></span>'
      + '</div>';
  }

  function render() {
    var stateSel = el('stateSelect'), distSel = el('districtSelect');
    var stateName = stateSel && stateSel.value ? stateSel.options[stateSel.selectedIndex].text : null;
    var distName = distSel && distSel.value ? distSel.options[distSel.selectedIndex].text : null;
    var host = el('cropyield-panel-body');
    if (!host) return;
    if (!stateName || !distName) {
      host.className = 'btm-pane-empty';
      host.innerHTML = '<i class="fa fa-chart-line chart-empty-icon"></i>'
        + '<span>राज्य/ज़िला चुनें · Select a state/district</span>'
        + '<button class="btm-pane-empty-btn" onclick="focusLocationSelector()"><i class="fa fa-location-crosshairs"></i> Select district</button>';
      return;
    }
    loadDistrictFile(stateName, distName).then(function (file) {
      if (!file || !file.crops || !Object.keys(file.crops).length) {
        host.className = 'btm-pane-empty';
        host.innerHTML = '<i class="fa fa-chart-line chart-empty-icon"></i>'
          + '<span>No crop+season here has enough real DES years (5+) for a trend yet.</span>';
        return;
      }
      var keys = Object.keys(file.crops).sort(function (a, b) {
        return file.crops[b].n_real_years - file.crops[a].n_real_years;
      });
      host.className = 'u-scroll-pane';
      host.innerHTML = ''
        + '<div style="padding:0.5rem 0.75rem;font-size:var(--fs-1);color:var(--text-dim);">'
        + 'Indicative OLS trend on real DES yield history (data.desagri.gov.in) — NOT a satellite/ML '
        + 'prediction. Range is a 95% band from the real trend residuals.</div>'
        + '<div style="padding:0 0.75rem;">' + keys.map(function (k) { return row(file.crops[k]); }).join('') + '</div>';
    });
  }

  function addPane() {
    var first = document.querySelector('.btm-pane');
    var host = first ? first.parentNode : null;
    if (!host || el('pane-cropyield')) return;

    var p = document.createElement('div');
    p.className = 'btm-pane';
    p.id = 'pane-cropyield';
    p.innerHTML = '<div class="section-header"><i class="fa fa-chart-line u-cyan-sm"></i>'
      + '<div class="section-title">CROP YIELD OUTLOOK — indicative trend, real DES history</div></div>'
      + '<div id="cropyield-panel-body" class="btm-pane-empty">'
      + '<i class="fa fa-chart-line chart-empty-icon"></i><span>राज्य/ज़िला चुनें · Select a state/district</span>'
      + '<button class="btm-pane-empty-btn" onclick="focusLocationSelector()"><i class="fa fa-location-crosshairs"></i> Select district</button></div>';
    host.appendChild(p);

    var firstTab = document.querySelector('.btm-tab');
    var tabs = firstTab ? firstTab.parentNode : null;
    if (tabs && !el('cropyield-tab')) {
      var tab = document.createElement('div');
      tab.innerHTML = '<i class="fa fa-chart-line"></i>Yield Outlook';
      tab.className = 'btm-tab';
      tab.id = 'cropyield-tab';
      tab.onclick = function () {
        var panes = document.querySelectorAll('.btm-pane'), i;
        for (i = 0; i < panes.length; i++) panes[i].classList.remove('active');
        el('pane-cropyield').classList.add('active');
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
  }

  function boot() {
    if (!document.querySelector('.btm-pane')) { setTimeout(boot, 700); return; }
    try { addPane(); wireSelectionHooks(); } catch (e) { console.warn('[crop_yield_loader]', e); }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(boot, 1000); });
  } else {
    setTimeout(boot, 1000);
  }

  window.VindhyaCropYield = { reload: render };
})();
