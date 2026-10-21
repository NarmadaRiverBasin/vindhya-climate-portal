/**
 * kisan_upload_worker.js -- Cloudflare Worker for the farmer ground-truth
 * crop upload (CROP_DATA_PROMPT.md Bhaag B). NOT deployed by this repo's
 * own tooling -- deploy it yourself:
 *
 *   cd cloudflare
 *   wrangler d1 create vindhya-ground-truth
 *   # paste the returned database_id into wrangler_kisan_upload.toml
 *   wrangler d1 execute vindhya-ground-truth --remote --file=kisan_upload_schema.sql
 *   wrangler secret put RATE_LIMIT_SALT --config wrangler_kisan_upload.toml
 *   wrangler deploy --config wrangler_kisan_upload.toml
 *
 * Then put the Worker's *.workers.dev (or custom) URL into
 * dashboard/kisan_upload.html's SUBMIT_URL constant AND
 * dashboard/mera_khet.js's MK_SUBMIT_URL constant -- both post to this
 * SAME /submit endpoint, this is still one upload pipeline, not two.
 *
 * MERA_KHET_PROMPT.md BHAAG A2 update: this Worker now also accepts an
 * optional `geometry` field (the farmer's drawn field boundary from Mera
 * Khet) alongside the original point-only payload kisan_upload.html has
 * always sent. If you deployed this Worker before that change, run the
 * additive migration once: `wrangler d1 execute vindhya-ground-truth
 * --remote --file=kisan_upload_schema_002_geometry.sql` (a fresh database
 * created from the current kisan_upload_schema.sql already has the column).
 *
 * KISAN_DASHBOARD_PROMPT.md section 8 (KRAM 6) update: this Worker now
 * also accepts an optional `problem_description` field (free text, capped
 * at 500 chars) from the Kisan Dashboard's damage-report form -- text +
 * location only this round, photo storage is explicitly deferred. Run
 * `wrangler d1 execute vindhya-ground-truth --remote
 * --file=kisan_upload_schema_003_problem.sql` once if you deployed this
 * Worker before that change (a fresh database already has the column).
 *
 * Owner request 2026-09-02 update ("live location with photo" for Kisan
 * Fasal Sahyog -- the photo work deferred above): this Worker now also
 * accepts an optional live field photo (base64 JPEG, already downscaled
 * client-side by dashboard/kisan_upload.html to well under 1MB) plus its
 * own capture-moment lat/lon/timestamp. The photo bytes go to an R2
 * bucket (binding PHOTOS) -- D1 only ever stores the resulting object
 * key, never the image itself. Requires:
 *   wrangler r2 bucket create vindhya-ground-truth-photos
 *   # add the [[r2_buckets]] binding to wrangler_kisan_upload.toml (see
 *   # that file's own comment for the exact block), then:
 *   wrangler d1 execute vindhya-ground-truth --remote
 *     --file=kisan_upload_schema_004_photo.sql
 *   wrangler deploy --config wrangler_kisan_upload.toml
 * A submission with no photo (Mera Khet, Kisan Dashboard's damage form)
 * is entirely unaffected -- the photo fields are optional and independent
 * of every other field this Worker already accepts.
 *
 * What this Worker does NOT do: it never stores a name, phone number,
 * Aadhaar, or raw IP address (B1/B3). The only thing derived from the
 * request's IP is a same-day salted SHA-256 hash, used solely to enforce
 * the 20-submissions/IP/day rate limit (B4) -- it is never exported,
 * never reversible without RATE_LIMIT_SALT (a Worker secret, never
 * checked in), and a new day's hash for the same IP looks nothing like
 * the previous day's.
 */

const ALLOWED_ORIGINS = new Set([
  'https://narmadariverbasin.github.io', // cNARMADA_IITIndore (NARMADA RIVER BASIN MANAGEMENT)
  'https://vindhya-climate.pages.dev', // VINDHYA Climate Portal, standalone Cloudflare Pages deployment
]);
const DAILY_LIMIT_PER_IP = 20;
// India's real bounding box (generous -- includes Andaman & Nicobar,
// Lakshadweep) -- anything outside this is rejected outright per B4
// ("Nirdeshank Bharat ke andar hone chahiye, warna reject").
const INDIA_BBOX = { latMin: 6.0, latMax: 38.0, lonMin: 68.0, lonMax: 98.0 };
const VALID_SEASONS = new Set(['kharif', 'rabi', 'zayad']);
// Mera Khet field polygons: a real field is a handful of vertices: cap
// generously so nobody can post a huge payload, never so tight a genuine
// hand-drawn field boundary gets rejected.
const MAX_GEOMETRY_POINTS = 500;
// Live field photo: the client already downscales to ~1280px/q0.75 JPEG
// (typically <400KB), so a real photo comfortably clears this; the cap
// exists to stop an abusive raw upload, not to squeeze a real one.
const MAX_PHOTO_BYTES = 2 * 1024 * 1024; // 2MB decoded
const ALLOWED_PHOTO_MIME = new Set(['image/jpeg', 'image/jpg', 'image/png']);

function corsHeaders(origin) {
  const headers = {
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
  if (ALLOWED_ORIGINS.has(origin)) headers['Access-Control-Allow-Origin'] = origin;
  return headers;
}

function json(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) },
  });
}

async function sha256Hex(text) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function handleSubmit(request, env) {
  const origin = request.headers.get('Origin') || '';
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: 'invalid_json' }, 400, origin);
  }

  const crop = String(body.crop || '').trim();
  const season = String(body.season || '').trim().toLowerCase();
  const lat = Number(body.lat);
  const lon = Number(body.lon);
  const areaHa = body.area_ha != null && body.area_ha !== '' ? Number(body.area_ha) : null;
  const consent = body.consent === true;
  // Optional (KISAN_DASHBOARD_PROMPT.md section 8, KRAM 6): free-text
  // damage/problem description from the Kisan Dashboard's report form.
  // Absent for kisan_upload.html's and Mera Khet's ordinary crop
  // ground-truth submissions -- stays null for those, exactly as before
  // this field existed.
  let problemDescription = null;
  if (body.problem_description != null) {
    problemDescription = String(body.problem_description).trim();
    if (problemDescription.length > 500) {
      return json({ ok: false, error: 'problem_description_too_long' }, 400, origin);
    }
    if (!problemDescription) problemDescription = null;
  }

  if (!consent) return json({ ok: false, error: 'consent_required' }, 400, origin);
  if (!crop || crop.length > 80) return json({ ok: false, error: 'invalid_crop' }, 400, origin);
  if (!VALID_SEASONS.has(season)) return json({ ok: false, error: 'invalid_season' }, 400, origin);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return json({ ok: false, error: 'invalid_location' }, 400, origin);
  if (lat < INDIA_BBOX.latMin || lat > INDIA_BBOX.latMax || lon < INDIA_BBOX.lonMin || lon > INDIA_BBOX.lonMax) {
    return json({ ok: false, error: 'location_outside_india' }, 400, origin);
  }
  if (areaHa != null && (!Number.isFinite(areaHa) || areaHa < 0 || areaHa > 10000)) {
    return json({ ok: false, error: 'invalid_area' }, 400, origin);
  }

  // Optional Mera Khet field boundary (A2). Absent for kisan_upload.html's
  // plain point-only submissions -- geometryJson stays null for those,
  // exactly as before this field existed.
  let geometryJson = null;
  if (body.geometry != null) {
    const g = body.geometry;
    if (!Array.isArray(g) || g.length < 3 || g.length > MAX_GEOMETRY_POINTS) {
      return json({ ok: false, error: 'invalid_geometry' }, 400, origin);
    }
    for (const pt of g) {
      if (!Array.isArray(pt) || pt.length !== 2) return json({ ok: false, error: 'invalid_geometry' }, 400, origin);
      const [plon, plat] = pt;
      if (!Number.isFinite(plon) || !Number.isFinite(plat)) return json({ ok: false, error: 'invalid_geometry' }, 400, origin);
      if (plat < INDIA_BBOX.latMin || plat > INDIA_BBOX.latMax || plon < INDIA_BBOX.lonMin || plon > INDIA_BBOX.lonMax) {
        return json({ ok: false, error: 'geometry_outside_india' }, 400, origin);
      }
    }
    // Re-round server-side to 3 decimals (~100m) -- the client already
    // does this, this is a second, code-enforced guarantee, not a trust
    // of the client.
    geometryJson = JSON.stringify(g.map(([plon, plat]) => [Math.round(plon * 1000) / 1000, Math.round(plat * 1000) / 1000]));
  }

  // Optional live field photo (owner request 2026-09-02). Absent for
  // Mera Khet's and the Kisan Dashboard's existing submissions -- stays
  // null for those, exactly as every other optional field on this
  // endpoint already works.
  let photoBytes = null, photoMime = null, photoLat = null, photoLon = null, photoCapturedAt = null;
  if (body.photo_base64 != null) {
    photoMime = String(body.photo_mime || '').trim().toLowerCase();
    if (!ALLOWED_PHOTO_MIME.has(photoMime)) {
      return json({ ok: false, error: 'invalid_photo_mime' }, 400, origin);
    }
    try {
      const binary = atob(String(body.photo_base64));
      if (binary.length === 0 || binary.length > MAX_PHOTO_BYTES) {
        return json({ ok: false, error: 'invalid_photo_size' }, 400, origin);
      }
      photoBytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) photoBytes[i] = binary.charCodeAt(i);
    } catch {
      return json({ ok: false, error: 'invalid_photo_encoding' }, 400, origin);
    }
    // Photo-capture-moment position is optional even when a photo is
    // present (geolocation can fail mid-capture) -- validated the same
    // way as the row's own required lat/lon when it IS given, but its
    // absence doesn't reject the whole submission.
    if (body.photo_lat != null && body.photo_lon != null) {
      photoLat = Number(body.photo_lat);
      photoLon = Number(body.photo_lon);
      if (!Number.isFinite(photoLat) || !Number.isFinite(photoLon) ||
          photoLat < INDIA_BBOX.latMin || photoLat > INDIA_BBOX.latMax ||
          photoLon < INDIA_BBOX.lonMin || photoLon > INDIA_BBOX.lonMax) {
        return json({ ok: false, error: 'invalid_photo_location' }, 400, origin);
      }
    }
    if (body.photo_captured_at != null) {
      const d = new Date(String(body.photo_captured_at));
      if (Number.isNaN(d.getTime())) return json({ ok: false, error: 'invalid_photo_timestamp' }, 400, origin);
      photoCapturedAt = d.toISOString();
    }
  }

  // Rate limit: a same-day salted hash of the connecting IP, never the IP
  // itself (B3/B4). RATE_LIMIT_SALT is a Worker secret (wrangler secret
  // put), never checked into this repo.
  const ip = request.headers.get('CF-Connecting-IP') || '0.0.0.0';
  const today = new Date().toISOString().slice(0, 10); // UTC date
  const ipHash = await sha256Hex(`${ip}|${today}|${env.RATE_LIMIT_SALT}`);

  const countRow = await env.DB
    .prepare('SELECT COUNT(*) AS n FROM submissions WHERE ip_hash = ? AND ip_hash_day = ?')
    .bind(ipHash, today)
    .first();
  if ((countRow?.n || 0) >= DAILY_LIMIT_PER_IP) {
    return json({ ok: false, error: 'rate_limited' }, 429, origin);
  }

  const id = crypto.randomUUID();

  // Upload the photo to R2 (if present) BEFORE the D1 insert, so a failed
  // photo upload never leaves a half-written row referencing a key that
  // doesn't exist -- if this throws, the whole request fails and the
  // farmer sees a real error asking them to retry, not a silently
  // photo-less submission.
  let photoUrl = null;
  if (photoBytes) {
    if (!env.PHOTOS) {
      return json({ ok: false, error: 'photo_storage_not_configured' }, 500, origin);
    }
    const ext = photoMime === 'image/png' ? 'png' : 'jpg';
    const key = `${today}/${id}.${ext}`;
    await env.PHOTOS.put(key, photoBytes, { httpMetadata: { contentType: photoMime } });
    photoUrl = key; // resolved to a real URL by whatever serves the PHOTOS bucket (R2 public bucket or a Worker route) -- not assumed here
  }

  await env.DB
    .prepare(
      `INSERT INTO submissions (id, created_at, crop, season, lat, lon, area_ha, geometry_json, problem_description, photo_url, photo_lat, photo_lon, photo_captured_at, status, ip_hash, ip_hash_day)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unverified', ?, ?)`
    )
    .bind(id, new Date().toISOString(), crop, season, lat, lon, areaHa, geometryJson, problemDescription,
          photoUrl, photoLat, photoLon, photoCapturedAt, ipHash, today)
    .run();

  return json({ ok: true, id, photo_saved: !!photoUrl }, 200, origin);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }
    const url = new URL(request.url);
    if (request.method === 'POST' && url.pathname === '/submit') {
      return handleSubmit(request, env);
    }
    return json({ ok: false, error: 'not_found' }, 404, origin);
  },
};
