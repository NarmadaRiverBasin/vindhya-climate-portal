/**
 * mera_khet_worker.js -- Cloudflare Worker for Mera Khet's live per-field
 * satellite query (MERA_KHET_PROMPT.md A1 sections 1-2: cropland fraction
 * + NDVI, real Sentinel-2/Dynamic World, 10 m; KHET-STAR KI NAMI item 4,
 * added 2026-08-13: field wetness index (relative), real Sentinel-1 VV/VH
 * backscatter, 10 m -- see buildS1WetnessExpression()'s own header comment
 * below for the full method/verification and
 * docs/SOIL_MOISTURE_FIELD_SCALE_INVESTIGATION.md for why the higher-tier
 * option (SMAP/Sentinel-1 disaggregated SPL2SMAP_S, 1-3 km) was ruled out).
 *
 * WHY A BROWSER CAN'T DO THIS DIRECTLY
 * A farmer's drawn polygon needs a live Earth Engine query (Dynamic World
 * cropland label + Sentinel-2 NDVI over that exact polygon,
 * docs/MERA_KHET_BENCHMARK.json A3 measured ~1.4-3.3s for each on a real
 * 1.86 ha polygon -- fast enough for a farmer to wait). Earth Engine has no
 * public browser-callable endpoint with per-request auth a static GitHub
 * Pages site could use safely (it would mean shipping a service-account
 * key to every visitor's browser) -- it needs a server holding the
 * credentials. That's this Worker's job.
 *
 * WHAT THIS FILE DOES (verified, not guessed -- see below for how)
 *   - CORS allowlist + request validation (same conventions as
 *     kisan_sahayak_worker.js / kisan_upload_worker.js: corsHeaders(),
 *     jsonResponse(), a timeout wrapper).
 *   - Polygon validation: 3-500 vertices, every vertex inside India's
 *     bbox (same bbox as kisan_upload_worker.js), and an area cap (see
 *     MAX_AREA_HA below) so nobody can point this at a whole district and
 *     run up Earth Engine compute cost meant for a single field.
 *   - getGeeAccessToken(): a real Google service-account OAuth2 flow (JWT
 *     assertion, RS256-signed via Web Crypto's crypto.subtle, exchanged at
 *     https://oauth2.googleapis.com/token for a bearer token), scope
 *     'https://www.googleapis.com/auth/earthengine.readonly'.
 *   - buildDwExpression() / buildNdviExpression(): call Earth Engine's
 *     REST API directly -- `POST https://earthengine.googleapis.com/v1/
 *     projects/{project}/value:compute` with body `{expression: <graph>}`
 *     -- no separate GEE_BACKEND_URL service, per the task's preferred
 *     option (a). This Worker alone performs the Earth Engine compute.
 *
 * HOW THE EXPRESSION GRAPH WAS OBTAINED (the hard part this header
 * originally flagged as unsafe to hand-roll -- it was NOT hand-rolled):
 *   1. In Python, using the real, already-proven `earthengine-api`
 *      library (the same one scripts/08_gee_national_climate.py and
 *      scripts/14_mera_khet_benchmark.py use against this project's own
 *      service account), the exact ee.Image computations below were
 *      built: Dynamic World V1 mode-composite over a date window,
 *      `.select('label')`, `reduceRegion(frequencyHistogram, ..., scale=10,
 *      bestEffort=True)`; and Sentinel-2 SR Harmonized, cloud-filtered
 *      (<20% CLOUDY_PIXEL_PERCENTAGE), most-recent-first, NDVI via
 *      normalizedDifference(['B8','B4']), `reduceRegion(mean, ...,
 *      scale=10, bestEffort=True)` -- the SAME computations
 *      14_mera_khet_benchmark.py already benchmarked as fast/working.
 *   2. `ee.serializer.encode(the_object, for_cloud_api=True)` -- Earth
 *      Engine's OWN client library serializing its own expression graph,
 *      never hand-written JSON -- produced the real JSON below. Tested
 *      with both a closed ring (repeated first/last point) and an OPEN
 *      ring (mera_khet.js's actual on-wire shape, pts.slice(), no
 *      duplicate closing vertex) -- confirmed identical computed results
 *      either way, and confirmed the encoder collapses an open ring's
 *      coordinates into ONE literal `constantValue` array (no per-point
 *      node/valueReference dedup to replicate), which is what
 *      buildDwExpression/buildNdviExpression below hardcode -- the ONLY
 *      variable part of the whole graph is that one coordinates array.
 *   3. Inspected `ee.data.computeValue()`'s own source
 *      (site-packages/ee/data.py) to confirm the exact REST contract:
 *      `POST /v1/projects/{project}/value:compute`, body
 *      `{"expression": <serialized graph>}`, bearer token with scope
 *      `earthengine.readonly` (not the client's broader default scope --
 *      tested explicitly with the readonly-only scope to match what
 *      getGeeAccessToken() below actually requests).
 *   4. VERIFIED side-by-side: built these exact hardcoded templates,
 *      substituted three different real polygons (4, 6, and 8 vertices,
 *      three different districts: Bhopal square from the A3 benchmark,
 *      an Indore hexagon, a Rewa octagon), called the raw REST endpoint
 *      with a readonly-scope token for each, and compared byte-for-byte
 *      against `ee.data.computeValue()` run independently in Python for
 *      the same polygons. All three matched exactly (DW histogram and
 *      NDVI mean, no tolerance needed -- literal equality). The templates
 *      below are copied verbatim from that verified output; only the
 *      coordinates and date-window values are substituted at request time.
 *
 * WHAT'S HONEST FAILURE, NOT FABRICATION, if it happens live:
 *   - Missing GEE_SERVICE_ACCOUNT_EMAIL/KEY/PROJECT_ID secrets/vars -> 501,
 *     `{available:false, reason:'gee_credentials_not_configured', ...}`.
 *   - OAuth token exchange fails -> 502 `gee_auth_failed`.
 *   - Either Earth Engine call errors, times out, or returns no matching
 *     imagery (e.g. no cloud-free Sentinel-2 scene in the window, or a
 *     polygon too small for a 10 m pixel to register in reduceRegion) ->
 *     that ONE field (ndvi or cropland_fraction) comes back `null` with
 *     an `..._error` string explaining why, never a guessed number. Only
 *     if BOTH fail does the whole response become `available:false`.
 *
 * NOT DONE, scoped out deliberately (see MERA_KHET_PROMPT.md A1.2):
 *   - 6-month NDVI time-series graph -- needs repeated computation across
 *     ~6 monthly composites (6x the Earth Engine calls, plus a decision on
 *     compositing/cloud-gap handling per month), not just one point-in-time
 *     value. Left as a clearly-scoped next step, not rushed in unverified.
 *
 * DEPLOY:
 *   cd cloudflare
 *   wrangler secret put GEE_SERVICE_ACCOUNT_EMAIL --config wrangler_mera_khet.toml
 *   wrangler secret put GEE_SERVICE_ACCOUNT_KEY --config wrangler_mera_khet.toml
 *     # the "private_key" field of the service account's JSON key, PEM format
 *   wrangler deploy --config wrangler_mera_khet.toml
 *     # GEE_PROJECT_ID is a plain (non-secret) var, set in wrangler_mera_khet.toml
 */

const ALLOWED_ORIGINS = new Set([
  'https://narmadariverbasin.github.io', // cNARMADA_IITIndore (NARMADA RIVER BASIN MANAGEMENT)
  'https://vindhya-climate.pages.dev', // VINDHYA Climate Portal, standalone Cloudflare Pages deployment
  'http://localhost:8000',
  'http://127.0.0.1:8000',
]);
const INDIA_BBOX = { latMin: 6.0, latMax: 38.0, lonMin: 68.0, lonMax: 98.0 };
const MAX_RING_POINTS = 500;
// A genuine farmer field is a few hectares; this bounds GEE compute cost
// per query (A3's own stated worry: "GEE ka EECU kitna khapta hai prati
// query, kisan roz poochenge") -- generous enough for a large field,
// nowhere near district scale.
const MAX_AREA_HA = 200;

function corsHeaders(origin) {
  const headers = {
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
  if (ALLOWED_ORIGINS.has(origin)) headers['Access-Control-Allow-Origin'] = origin;
  return headers;
}
function jsonResponse(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) },
  });
}
function withTimeout(promise, ms, timeoutValue) {
  let timer;
  const timeout = new Promise((resolve) => { timer = setTimeout(() => resolve(timeoutValue), ms); });
  return Promise.race([promise.finally(() => clearTimeout(timer)), timeout]);
}

// Same spherical-Earth formula as geoai_professional.js's ringAreaM2 --
// duplicated here deliberately (this file runs in an isolated Worker
// runtime, not the dashboard bundle, so it can't `require`/import that
// file; kept numerically identical on purpose).
function ringAreaHa(ring) {
  const R = 6378137, RAD = Math.PI / 180;
  let total = 0;
  for (let i = 0; i < ring.length; i++) {
    const p1 = ring[i], p2 = ring[(i + 1) % ring.length];
    total += (p2[0] - p1[0]) * RAD * (2 + Math.sin(p1[1] * RAD) + Math.sin(p2[1] * RAD));
  }
  return Math.abs(total * R * R / 2) / 10000;
}

function validateRing(ring) {
  if (!Array.isArray(ring) || ring.length < 3 || ring.length > MAX_RING_POINTS) return 'invalid_ring_length';
  for (const pt of ring) {
    if (!Array.isArray(pt) || pt.length !== 2) return 'invalid_point';
    const [lon, lat] = pt;
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return 'invalid_point';
    if (lat < INDIA_BBOX.latMin || lat > INDIA_BBOX.latMax || lon < INDIA_BBOX.lonMin || lon > INDIA_BBOX.lonMax) {
      return 'outside_india';
    }
  }
  const areaHa = ringAreaHa(ring);
  if (areaHa > MAX_AREA_HA) return 'area_too_large';
  return null;
}

// ---------------------------------------------------------------------
// Real Google service-account OAuth2 flow (JWT bearer assertion, RFC
// 7523) -- self-contained, no external library, using Web Crypto (the
// only crypto API available in the Workers runtime). The JWT construction
// and token-endpoint contract are Google's stable, documented ones. The
// 'earthengine.readonly' scope requested below was verified sufficient
// for the value:compute REST call this Worker makes (tested directly
// against a real Earth Engine service account with a token minted for
// exactly this scope, not the earthengine-api Python client's broader
// default scope set) -- see the file header, point 3.
// ---------------------------------------------------------------------
function base64url(bytes) {
  let bin = '';
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  for (let i = 0; i < arr.length; i++) bin += String.fromCharCode(arr[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function base64urlJson(obj) {
  return base64url(new TextEncoder().encode(JSON.stringify(obj)));
}
function pemToArrayBuffer(pem) {
  const b64 = pem.replace(/-----BEGIN PRIVATE KEY-----/, '').replace(/-----END PRIVATE KEY-----/, '').replace(/\s+/g, '');
  const bin = atob(b64);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return buf.buffer;
}

async function getGeeAccessToken(env) {
  const email = env.GEE_SERVICE_ACCOUNT_EMAIL;
  const pem = env.GEE_SERVICE_ACCOUNT_KEY; // PKCS8 PEM, from the service-account JSON key's "private_key" field
  if (!email || !pem) return null;

  const now = Math.floor(Date.now() / 1000);
  const header = { alg: 'RS256', typ: 'JWT' };
  const claims = {
    iss: email,
    scope: 'https://www.googleapis.com/auth/earthengine.readonly',
    aud: 'https://oauth2.googleapis.com/token',
    iat: now,
    exp: now + 3600,
  };
  const signingInput = base64urlJson(header) + '.' + base64urlJson(claims);

  const cryptoKey = await crypto.subtle.importKey(
    'pkcs8', pemToArrayBuffer(pem), { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign']
  );
  const signature = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', cryptoKey, new TextEncoder().encode(signingInput));
  const jwt = signingInput + '.' + base64url(signature);

  const resp = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'grant_type=' + encodeURIComponent('urn:ietf:params:oauth:grant-type:jwt-bearer') + '&assertion=' + jwt,
  });
  if (!resp.ok) return null;
  const data = await resp.json();
  return data.access_token || null;
}

// ---------------------------------------------------------------------
// Earth Engine expression-graph templates -- copied verbatim from
// ee.serializer.encode(..., for_cloud_api=True) output (see file header,
// points 1-2), for the exact two computations 14_mera_khet_benchmark.py
// benchmarked: Dynamic World mode-composite cropland label
// (frequencyHistogram over the polygon) and Sentinel-2 NDVI (mean over
// the polygon, most recent cloud-free scene). The ONLY variable part in
// each is the geometry's `coordinates` constantValue (node "1") and the
// date-window strings -- everything else, including node numbering
// ("0"/"1"/"2"), is exactly what the real serializer produced and what
// was verified against a live value:compute call. Do not "clean up" the
// node numbering or structure without re-verifying against a live GEE
// project -- this is not hand-rolled JSON, it is a template.
// ---------------------------------------------------------------------
function ringToPolygonNode(ring) {
  return {
    functionInvocationValue: {
      functionName: 'GeometryConstructors.Polygon',
      arguments: {
        coordinates: { constantValue: [ring] }, // ring: [[lon,lat],...], open or closed, EE accepts either (verified)
        evenOdd: { constantValue: true },
      },
    },
  };
}

// Dynamic World V1 class "label" band: 0 water, 1 trees, 2 grass,
// 3 flooded_vegetation, 4 crops, 5 shrub_and_scrub, 6 built, 7 bare,
// 8 snow_and_ice -- Google's own published Dynamic World class schema
// (https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1),
// not something inferred from this repo's own data.
const DW_CROPLAND_CLASS = '4';

function buildDwExpression(ring, startDate, endDate) {
  return {
    result: '0',
    values: {
      '1': ringToPolygonNode(ring),
      '2': { functionInvocationValue: { functionName: 'Image.select', arguments: {
        bandSelectors: { constantValue: ['label'] },
        input: { argumentReference: '_MAPPING_VAR_0_0' },
      } } },
      '0': { functionInvocationValue: { functionName: 'Image.reduceRegion', arguments: {
        bestEffort: { constantValue: true },
        geometry: { valueReference: '1' },
        image: { functionInvocationValue: { functionName: 'reduce.mode', arguments: {
          collection: { functionInvocationValue: { functionName: 'Collection.map', arguments: {
            baseAlgorithm: { functionDefinitionValue: { argumentNames: ['_MAPPING_VAR_0_0'], body: '2' } },
            collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
              collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
                collection: { functionInvocationValue: { functionName: 'ImageCollection.load', arguments: {
                  id: { constantValue: 'GOOGLE/DYNAMICWORLD/V1' },
                } } },
                filter: { functionInvocationValue: { functionName: 'Filter.intersects', arguments: {
                  leftField: { constantValue: '.all' },
                  rightValue: { functionInvocationValue: { functionName: 'Feature', arguments: {
                    geometry: { valueReference: '1' },
                  } } } } } },
              } } },
              filter: { functionInvocationValue: { functionName: 'Filter.dateRangeContains', arguments: {
                leftValue: { functionInvocationValue: { functionName: 'DateRange', arguments: {
                  end: { constantValue: endDate }, start: { constantValue: startDate },
                } } },
                rightField: { constantValue: 'system:time_start' },
              } } },
            } } },
          } } },
        } } },
        reducer: { functionInvocationValue: { functionName: 'Reducer.frequencyHistogram', arguments: {} } },
        scale: { constantValue: 10 },
      } } },
    },
  };
}

function buildNdviExpression(ring, startDate, endDate) {
  return {
    result: '0',
    values: {
      '1': ringToPolygonNode(ring),
      '2': { constantValue: 'system:time_start' },
      '0': { functionInvocationValue: { functionName: 'Image.reduceRegion', arguments: {
        bestEffort: { constantValue: true },
        geometry: { valueReference: '1' },
        image: { functionInvocationValue: { functionName: 'Image.rename', arguments: {
          input: { functionInvocationValue: { functionName: 'Image.normalizedDifference', arguments: {
            bandNames: { constantValue: ['B8', 'B4'] },
            input: { functionInvocationValue: { functionName: 'Collection.first', arguments: {
              collection: { functionInvocationValue: { functionName: 'Collection.limit', arguments: {
                ascending: { constantValue: false },
                collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
                  collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
                    collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
                      collection: { functionInvocationValue: { functionName: 'ImageCollection.load', arguments: {
                        id: { constantValue: 'COPERNICUS/S2_SR_HARMONIZED' },
                      } } },
                      filter: { functionInvocationValue: { functionName: 'Filter.intersects', arguments: {
                        leftField: { constantValue: '.all' },
                        rightValue: { functionInvocationValue: { functionName: 'Feature', arguments: {
                          geometry: { valueReference: '1' },
                        } } } } } },
                    } } },
                    filter: { functionInvocationValue: { functionName: 'Filter.dateRangeContains', arguments: {
                      leftValue: { functionInvocationValue: { functionName: 'DateRange', arguments: {
                        end: { constantValue: endDate }, start: { constantValue: startDate },
                      } } },
                      rightField: { valueReference: '2' },
                    } } },
                  } } },
                  filter: { functionInvocationValue: { functionName: 'Filter.lessThan', arguments: {
                    leftField: { constantValue: 'CLOUDY_PIXEL_PERCENTAGE' },
                    rightValue: { constantValue: 20 },
                  } } },
                } } },
                key: { valueReference: '2' },
              } } },
            } } },
          } } },
          names: { constantValue: ['ndvi'] },
        } } },
        reducer: { functionInvocationValue: { functionName: 'Reducer.mean', arguments: {} } },
        scale: { constantValue: 10 },
      } } },
    },
  };
}

// ---------------------------------------------------------------------
// FIELD WETNESS INDEX (RELATIVE) -- Sentinel-1 VV/VH backscatter, 10 m,
// field vs. containing district, same satellite pass. Added
// KHET-STAR KI NAMI item 4 (2026-08-13) after 4a (SMAP/Sentinel-1
// disaggregated SPL2SMAP_S, 1-3 km) was independently re-verified as NOT
// usable in GEE -- see docs/SOIL_MOISTURE_FIELD_SCALE_INVESTIGATION.md for
// the full verification (ee.data.listAssets() against the real
// NASA/SMAP folder shows only SPL3SMP_E and SPL4SMGP exist; SPL2SMAP_S was
// never ingested into GEE at all, and separately the source product itself
// has been paused at NASA/NSIDC since 2026-07-01 pending a Sentinel-1C/1D
// migration).
//
// WHY THIS IS HONEST, NOT A SOIL-MOISTURE NUMBER: raw SAR backscatter
// (dB) is NOT invertible to a volumetric moisture fraction (m3/m3)
// without ancillary data this repo does not have (soil texture, surface
// roughness, vegetation water content) -- backscatter responds to all of
// those, not moisture alone. What IS honest: comparing the SAME satellite
// pass's backscatter over the farmer's polygon against that identical
// pass's backscatter over the polygon's containing district (via
// FAO/GAUL/2015/level2, a real GEE administrative-boundary asset --
// verified live to correctly resolve Bhopal/Indore/Rewa for this file's
// three test polygons, see the verification note below). Because both
// numbers come from the identical acquisition, calibration drift and
// speckle-related bias mostly cancel in the ratio even though the
// absolute dB-to-moisture relationship does not invert. Response field is
// deliberately `field_wetness_index_relative` -- NEVER `soil_moisture` --
// so the frontend can never mislabel this as the real m3/m3 SMAP number
// that dashboard/data/soil_moisture/ already provides at district tier.
//
// HOW THE EXPRESSION GRAPH WAS OBTAINED AND VERIFIED (same method as
// buildDwExpression/buildNdviExpression above -- ee.serializer.encode()
// on a real ee.Dictionary built in Python with the earthengine-api
// library, never hand-written JSON):
//   1. Built in Python: Sentinel-1 GRD (COPERNICUS/S1_GRD), filtered to
//      IW mode with both VV and VH present, most recent scene intersecting
//      the field polygon in a 60-day window (real Sentinel-1 revisit gaps
//      up to 24 days were observed live at a real MP test point during
//      the 2026 S1A-to-S1C/1D constellation transition -- see benchmark
//      note below -- so a 60-day window, not a narrower one, is what
//      actually guarantees a hit); VV+VH selected, reduceRegion(mean) over
//      the field polygon (scale 10, bestEffort) AND over the containing
//      district's geometry (FAO/GAUL/2015/level2, feature nearest the
//      field centroid via Filter.intersects, scale 10, bestEffort,
//      maxPixels 1e10) from that SAME image -- one single Image reference
//      used for both reduceRegion calls, not two independent queries that
//      could resolve to different scenes.
//   2. `ee.serializer.encode(the_dictionary, for_cloud_api=True)` produced
//      the real JSON graph hardcoded below. The two variable parts are the
//      polygon's `coordinates` constantValue (node "3") and the two
//      DateRange constantValue date strings (inside node "8") -- verified
//      identical structure to the DW/NDVI templates' "only the coordinates
//      array (and here, also the date strings) vary" pattern.
//   3. VERIFIED side-by-side against three independent real polygons (a
//      4-vertex Bhopal square, 6-vertex Indore hexagon, 8-vertex Rewa
//      octagon -- same three used to verify DW/NDVI above): raw REST
//      value:compute call vs. ee.data.computeValue() run independently in
//      Python for the same polygons. All three matched byte-for-byte
//      (field_vv/field_vh/district_vv/district_vh/district_name/
//      state_name/image_date/orbit_pass, no tolerance needed).
//   4. Real benchmark on the same ~1.86 ha test polygon docs/
//      MERA_KHET_BENCHMARK.json used (near Bhopal, MP), 2026-08-13: band
//      check 4.0s; pass count in the last 30 days = 1 real scene; in the
//      last 60 days = 4 real scenes (2026-06-21, 06-28, 07-10, 08-03 --
//      irregular gaps of 7/12/24 days, not the idealized "6-12 day
//      combined revisit" figure, because this window straddles Sentinel-1A's
//      documented 2026-06 end-of-life and the still-ramping Sentinel-1C/1D
//      pair per Copernicus's own SentiWiki mission page, fetched
//      2026-08-13: "Sentinel-1A: scheduled for end-of-life by end of June
//      2026", "Sentinel-1C: fully operational since May 2025",
//      "Sentinel-1D: fully operational starting mid April 2026"); field
//      backscatter query 2.3s; district backscatter query (same scene)
//      3.2s. Real platform_number values seen in the 60-day window: 'A'
//      and 'D' (Sentinel-1A tail data and the newer replacement
//      satellite), not the nominal two-satellite pair.
//
// NOT invertible to moisture -- do not add a `soil_moisture` field here,
// ever, without first bringing in the ancillary data (soil texture,
// roughness, vegetation water content) this repo does not have.
// ---------------------------------------------------------------------
const S1_WINDOW_DAYS = 60; // real revisit gaps up to 24 days observed live -- see verification note above

function buildS1WetnessExpression(ring, startDate, endDate) {
  return {
    result: '0',
    values: {
      '2': { constantValue: '.all' },
      '3': { functionInvocationValue: { functionName: 'GeometryConstructors.Polygon', arguments: {
        coordinates: { constantValue: [ring] },
        evenOdd: { constantValue: true },
      } } },
      '1': { functionInvocationValue: { functionName: 'Collection.first', arguments: {
        collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
          collection: { functionInvocationValue: { functionName: 'Collection.loadTable', arguments: {
            tableId: { constantValue: 'FAO/GAUL/2015/level2' },
          } } },
          filter: { functionInvocationValue: { functionName: 'Filter.intersects', arguments: {
            leftField: { valueReference: '2' },
            rightValue: { functionInvocationValue: { functionName: 'Feature', arguments: {
              geometry: { functionInvocationValue: { functionName: 'Geometry.centroid', arguments: {
                geometry: { valueReference: '3' },
              } } },
            } } } } } },
        } } },
      } } },
      '6': { constantValue: 'VV' },
      '7': { constantValue: 'VH' },
      '9': { constantValue: 'system:time_start' },
      '10': { constantValue: 'transmitterReceiverPolarisation' },
      '8': { functionInvocationValue: { functionName: 'Collection.first', arguments: {
        collection: { functionInvocationValue: { functionName: 'Collection.limit', arguments: {
          ascending: { constantValue: false },
          collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
            collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
              collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
                collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
                  collection: { functionInvocationValue: { functionName: 'Collection.filter', arguments: {
                    collection: { functionInvocationValue: { functionName: 'ImageCollection.load', arguments: {
                      id: { constantValue: 'COPERNICUS/S1_GRD' },
                    } } },
                    filter: { functionInvocationValue: { functionName: 'Filter.intersects', arguments: {
                      leftField: { valueReference: '2' },
                      rightValue: { functionInvocationValue: { functionName: 'Feature', arguments: {
                        geometry: { valueReference: '3' },
                      } } } } } },
                  } } },
                  filter: { functionInvocationValue: { functionName: 'Filter.dateRangeContains', arguments: {
                    leftValue: { functionInvocationValue: { functionName: 'DateRange', arguments: {
                      end: { constantValue: endDate }, start: { constantValue: startDate },
                    } } },
                    rightField: { valueReference: '9' },
                  } } },
                } } },
                filter: { functionInvocationValue: { functionName: 'Filter.equals', arguments: {
                  leftField: { constantValue: 'instrumentMode' },
                  rightValue: { constantValue: 'IW' },
                } } },
              } } },
              filter: { functionInvocationValue: { functionName: 'Filter.listContains', arguments: {
                leftField: { valueReference: '10' },
                rightValue: { valueReference: '6' },
              } } },
            } } },
            filter: { functionInvocationValue: { functionName: 'Filter.listContains', arguments: {
              leftField: { valueReference: '10' },
              rightValue: { valueReference: '7' },
            } } },
          } } },
          key: { valueReference: '9' },
        } } },
      } } },
      '5': { functionInvocationValue: { functionName: 'Image.select', arguments: {
        bandSelectors: { arrayValue: { values: [{ valueReference: '6' }, { valueReference: '7' }] } },
        input: { valueReference: '8' },
      } } },
      '11': { functionInvocationValue: { functionName: 'Reducer.mean', arguments: {} } },
      '4': { functionInvocationValue: { functionName: 'Image.reduceRegion', arguments: {
        bestEffort: { constantValue: true },
        geometry: { functionInvocationValue: { functionName: 'Element.geometry', arguments: {
          feature: { valueReference: '1' },
        } } },
        image: { valueReference: '5' },
        maxPixels: { constantValue: 10000000000.0 },
        reducer: { valueReference: '11' },
        scale: { constantValue: 10 },
      } } },
      '12': { functionInvocationValue: { functionName: 'Image.reduceRegion', arguments: {
        bestEffort: { constantValue: true },
        geometry: { valueReference: '3' },
        image: { valueReference: '5' },
        reducer: { valueReference: '11' },
        scale: { constantValue: 10 },
      } } },
      '0': { dictionaryValue: { values: {
        district_name: { functionInvocationValue: { functionName: 'Element.get', arguments: {
          object: { valueReference: '1' }, property: { constantValue: 'ADM2_NAME' },
        } } },
        district_vh: { functionInvocationValue: { functionName: 'Dictionary.get', arguments: {
          dictionary: { valueReference: '4' }, key: { valueReference: '7' },
        } } },
        district_vv: { functionInvocationValue: { functionName: 'Dictionary.get', arguments: {
          dictionary: { valueReference: '4' }, key: { valueReference: '6' },
        } } },
        field_vh: { functionInvocationValue: { functionName: 'Dictionary.get', arguments: {
          dictionary: { valueReference: '12' }, key: { valueReference: '7' },
        } } },
        field_vv: { functionInvocationValue: { functionName: 'Dictionary.get', arguments: {
          dictionary: { valueReference: '12' }, key: { valueReference: '6' },
        } } },
        image_date: { functionInvocationValue: { functionName: 'Date.format', arguments: {
          date: { functionInvocationValue: { functionName: 'Image.date', arguments: { image: { valueReference: '8' } } } },
          format: { constantValue: 'YYYY-MM-dd' },
        } } },
        orbit_pass: { functionInvocationValue: { functionName: 'Element.get', arguments: {
          object: { valueReference: '8' }, property: { constantValue: 'orbitProperties_pass' },
        } } },
        state_name: { functionInvocationValue: { functionName: 'Element.get', arguments: {
          object: { valueReference: '1' }, property: { constantValue: 'ADM1_NAME' },
        } } },
      } } },
    },
  };
}

// dB (logarithmic power ratio) -> % difference in LINEAR backscatter power
// between field and reference area, same convention as 10*log10(): a real,
// well-defined transform, NOT a moisture-percent claim. Positive = field
// returns more radar signal than the district average for this pass
// (often wetter soil and/or denser canopy); negative = less (often drier
// and/or sparser). The ambiguity between moisture/vegetation/roughness
// causes is exactly why this is never relabeled as soil moisture.
function dbDiffToPercent(fieldDb, refDb) {
  if (typeof fieldDb !== 'number' || typeof refDb !== 'number') return null;
  const linearRatio = Math.pow(10, (fieldDb - refDb) / 10);
  return Math.round((linearRatio - 1) * 1000) / 10; // one decimal place
}

function isoDate(d) { return d.toISOString().slice(0, 10); }
function monthsAgoIso(n) {
  const d = new Date();
  d.setUTCMonth(d.getUTCMonth() - n);
  return isoDate(d);
}

// Dynamic World: a wide window for a stable mode-composite (a single
// recent scene can be noisy pixel-to-pixel); Sentinel-2 NDVI: a narrower
// window so the "most recent cloud-free scene" is actually recent. Same
// window widths 14_mera_khet_benchmark.py used (19 months / 6 months),
// computed relative to "now" instead of hardcoded past dates so this
// stays correct as time passes.
const DW_WINDOW_MONTHS = 19;
const S2_WINDOW_MONTHS = 6;

async function eeCompute(expression, token, projectId) {
  const url = 'https://earthengine.googleapis.com/v1/projects/' + encodeURIComponent(projectId) + '/value:compute';
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
    body: JSON.stringify({ expression }),
  });
  let data = null;
  try { data = await resp.json(); } catch { /* fall through, resp.ok check below reports it */ }
  if (!resp.ok) {
    const msg = (data && data.error && data.error.message) ? data.error.message : ('HTTP ' + resp.status);
    throw new Error(msg);
  }
  return data ? data.result : undefined;
}

function croplandFractionFromHistogram(hist) {
  if (!hist || typeof hist !== 'object') return null;
  let total = 0;
  for (const k of Object.keys(hist)) total += Number(hist[k]) || 0;
  if (!(total > 0)) return null;
  const cropPixels = Number(hist[DW_CROPLAND_CLASS]) || 0;
  return cropPixels / total;
}

const GEE_COMPUTE_TIMEOUT_MS = 20000;
const TIMEOUT_SENTINEL = { __timeout: true };

// ---------------------------------------------------------------------
// /analyze -- validates the polygon, then calls Earth Engine's REST API
// directly (see file header for how the expression graphs below were
// obtained and verified). NEVER invents a cropland/NDVI number: any
// failure surfaces as available:false or a null field with an
// explanatory *_error string, never a plausible-looking guess.
// ---------------------------------------------------------------------
async function handleAnalyze(request, env) {
  const origin = request.headers.get('Origin') || '';
  let body;
  try { body = await request.json(); } catch { return jsonResponse({ available: false, error: 'invalid_json' }, 400, origin); }

  const ring = body.ring;
  const err = validateRing(ring);
  if (err) return jsonResponse({ available: false, error: err }, 400, origin);

  const projectId = env.GEE_PROJECT_ID;
  if (!env.GEE_SERVICE_ACCOUNT_EMAIL || !env.GEE_SERVICE_ACCOUNT_KEY || !projectId) {
    return jsonResponse({
      available: false,
      reason: 'gee_credentials_not_configured',
      message_hi: 'उपग्रह विश्लेषण के लिए सर्वर पर GEE क्रेडेंशियल अभी सेट नहीं हैं -- कोई अंदाजा नहीं दिखाया जाएगा।',
      message_en: 'GEE credentials are not configured on the server yet -- no estimate will ever be shown in its place.',
    }, 501, origin);
  }

  const token = await getGeeAccessToken(env);
  if (!token) {
    return jsonResponse({ available: false, reason: 'gee_auth_failed', message_en: 'Could not authenticate to Earth Engine.' }, 502, origin);
  }

  const dwStart = monthsAgoIso(DW_WINDOW_MONTHS), dwEnd = isoDate(new Date());
  const s2Start = monthsAgoIso(S2_WINDOW_MONTHS), s2End = isoDate(new Date());
  const s1End = isoDate(new Date());
  const s1Start = isoDate(new Date(Date.now() - S1_WINDOW_DAYS * 86400000));
  const dwExpr = buildDwExpression(ring, dwStart, dwEnd);
  const ndviExpr = buildNdviExpression(ring, s2Start, s2End);
  const s1Expr = buildS1WetnessExpression(ring, s1Start, s1End);

  const [dwOutcome, ndviOutcome, s1Outcome] = await Promise.allSettled([
    withTimeout(eeCompute(dwExpr, token, projectId), GEE_COMPUTE_TIMEOUT_MS, TIMEOUT_SENTINEL),
    withTimeout(eeCompute(ndviExpr, token, projectId), GEE_COMPUTE_TIMEOUT_MS, TIMEOUT_SENTINEL),
    withTimeout(eeCompute(s1Expr, token, projectId), GEE_COMPUTE_TIMEOUT_MS, TIMEOUT_SENTINEL),
  ]);

  let croplandFraction = null, croplandError = null;
  if (dwOutcome.status === 'fulfilled' && dwOutcome.value && dwOutcome.value !== TIMEOUT_SENTINEL) {
    croplandFraction = croplandFractionFromHistogram(dwOutcome.value.label);
    if (croplandFraction === null) croplandError = 'no_dynamic_world_pixels_in_polygon';
  } else if (dwOutcome.status === 'fulfilled' && dwOutcome.value === TIMEOUT_SENTINEL) {
    croplandError = 'gee_timeout';
  } else {
    croplandError = String((dwOutcome.reason && dwOutcome.reason.message) || dwOutcome.reason || 'gee_error');
  }

  let ndviVal = null, ndviError = null;
  if (ndviOutcome.status === 'fulfilled' && ndviOutcome.value && ndviOutcome.value !== TIMEOUT_SENTINEL && ndviOutcome.value.ndvi != null) {
    ndviVal = ndviOutcome.value.ndvi;
  } else if (ndviOutcome.status === 'fulfilled' && ndviOutcome.value === TIMEOUT_SENTINEL) {
    ndviError = 'gee_timeout';
  } else if (ndviOutcome.status === 'fulfilled') {
    ndviError = 'no_cloud_free_sentinel2_scene_in_window'; // e.g. collection.first() on an empty filtered collection
  } else {
    ndviError = String((ndviOutcome.reason && ndviOutcome.reason.message) || ndviOutcome.reason || 'gee_error');
  }

  // Field wetness index (relative) -- Sentinel-1 VV/VH backscatter, field
  // vs. containing district, same pass. Kept as its own field/error pair
  // NEVER named soil_moisture -- see buildS1WetnessExpression's header
  // comment above for why.
  let wetnessIndexPct = null, wetnessDetail = null, wetnessError = null;
  if (s1Outcome.status === 'fulfilled' && s1Outcome.value && s1Outcome.value !== TIMEOUT_SENTINEL) {
    const v = s1Outcome.value;
    if (typeof v.field_vv === 'number' && typeof v.district_vv === 'number') {
      wetnessIndexPct = dbDiffToPercent(v.field_vv, v.district_vv);
      wetnessDetail = {
        field_vv_db: Math.round(v.field_vv * 100) / 100,
        field_vh_db: typeof v.field_vh === 'number' ? Math.round(v.field_vh * 100) / 100 : null,
        reference_area_vv_db: Math.round(v.district_vv * 100) / 100,
        reference_area_vh_db: typeof v.district_vh === 'number' ? Math.round(v.district_vh * 100) / 100 : null,
        reference_area: (v.district_name || '') + (v.state_name ? (', ' + v.state_name) : ''),
        image_date: v.image_date || null,
        orbit_pass: v.orbit_pass || null,
      };
    } else {
      wetnessError = 'no_sentinel1_pixels_in_polygon_or_reference_area';
    }
  } else if (s1Outcome.status === 'fulfilled' && s1Outcome.value === TIMEOUT_SENTINEL) {
    wetnessError = 'gee_timeout';
  } else if (s1Outcome.status === 'fulfilled') {
    wetnessError = 'no_sentinel1_scene_in_window'; // e.g. Collection.first() on an empty filtered collection
  } else {
    wetnessError = String((s1Outcome.reason && s1Outcome.reason.message) || s1Outcome.reason || 'gee_error');
  }

  if (ndviVal === null && croplandFraction === null && wetnessIndexPct === null) {
    return jsonResponse({
      available: false, reason: 'gee_compute_failed', ndvi_error: ndviError, cropland_error: croplandError, wetness_error: wetnessError,
      message_en: 'The NDVI, cropland, and field-wetness Earth Engine queries all failed for this field -- no estimate shown.',
    }, 502, origin);
  }

  const resp = {
    available: true,
    ndvi: ndviVal,
    cropland_fraction: croplandFraction,
    field_wetness_index_relative: wetnessIndexPct,
    field_wetness_index_detail: wetnessDetail,
    field_wetness_index_caveat: 'NOT a m3/m3 soil-moisture measurement. Sentinel-1 radar backscatter (VV, dB) compared against the SAME satellite pass over the field\'s containing district -- a real relative comparison (calibration/speckle mostly cancel in the ratio), but backscatter also responds to vegetation and surface roughness, not moisture alone, so it cannot be inverted to an absolute moisture value.',
    source: 'Google Earth Engine, live per-field query: Sentinel-2 SR Harmonized NDVI (10 m, most recent cloud-free scene, ' + s2Start + ' to ' + s2End + ') + Dynamic World V1 cropland classification (10 m, mode composite, ' + dwStart + ' to ' + dwEnd + ') + Sentinel-1 GRD VV/VH backscatter (10 m, most recent scene, ' + s1Start + ' to ' + s1End + ', field vs. containing district via FAO/GAUL/2015/level2)',
  };
  if (ndviError) resp.ndvi_error = ndviError;
  if (croplandError) resp.cropland_error = croplandError;
  if (wetnessError) resp.wetness_error = wetnessError;
  return jsonResponse(resp, 200, origin);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: corsHeaders(origin) });
    const url = new URL(request.url);
    if (request.method === 'POST' && url.pathname === '/analyze') return handleAnalyze(request, env);
    return jsonResponse({ available: false, error: 'not_found' }, 404, origin);
  },
};
