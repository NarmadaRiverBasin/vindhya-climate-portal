#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYNTHETIC 100-FARMER PILOT STUDY DATA GENERATOR

  *** DELIBERATE, NARROWLY-SCOPED EXCEPTION TO CLAUDE.md's
      "No synthetic data, ever" RULE -- READ BEFORE EDITING ***

CLAUDE.md forbids synthetic data anywhere in this repo, because a prior
version shipped 50 fabricated districts and procedurally-generated cadastral
owner names indistinguishable from real records. That rule still stands
everywhere else. This ONE file is an owner-authorized exception, bounded as:

 1. SCOPE. Its only output is
    dashboard/data/crop_insurance_pilot/synthetic_farmers_100.json, consumed
    by exactly one standalone page (crop_insurance_pilot/pilot_study.html).
    Never read by the main dashboard, never merged into mp_climate_data.json,
    crop_stats, mandi_prices or groundwater, never feeds a landing-page stat.
 2. LABELLING. Every record carries synthetic=true, IDs carry SYN-/SF-
    prefixes, and the page prints SYNTHETIC/SIMULATED labels on every screen,
    table, popup, chart and card.
 3. NO FAKE IDENTITIES. Farmer names are deliberately NON-realistic
    placeholders ("SYN-FARMER-001"). A realistic-looking Indian personal name
    is NEVER generated -- that was the exact defect of the 2026-08 cleanup.
    No Aadhaar, bank details, phone numbers or real policy numbers.
 4. NOT IN scripts/. .github/workflows/verify-data.yml greps scripts/ for
    random-generation calls and must keep failing the build if any appear
    there. That check is not meant to cover this labelled pilot generator, so
    the generator lives beside the module it serves.

REAL (must stay real):
  - Simrol village polygon: Survey of India / NWDP (vil_lgd 476504), reused
    as-is; every synthetic parcel is clipped to lie inside it.
  - Census population/households carried in that same SoI feature.
  - Per-crop yield baselines and PMFBY threshold yields computed from the REAL
    DES (data.desagri.gov.in) Indore records, using the actual threshold-yield
    method (mean of best 5 of last 7 available years x indemnity level).
  - PMFBY farmer premium-share caps (Kharif 2%, Rabi 1.5%, commercial 5%).
  - Parcel component areas are GEOMETRICALLY DERIVED from the polygons
    (bund = negative-buffer ring, cultivated = remainder), so components sum
    exactly to cadastral area. They are not typed-in numbers.

SYNTHETIC (the point of the pilot): the 100 farmers, names, IDs, khasra
numbers, parcel polygons, girdawari records, land status, all NDVI/NDWI/EVI
series and health scores, all weather events, damage areas, loss percentages,
AI confidence and evidence scores, and all premium/claim values.

LIVE_SATELLITE_CHECK field (added 2026-10-21, owner request): each farmer's
`live_satellite_check` is a REAL, additive field -- NOT synthetic -- a live
Google Earth Engine query against that farmer's actual (synthetic) parcel
polygon, via the real deployed Mera Khet Worker's /analyze endpoint (the
exact same call dashboard/mera_khet.js makes for a real farmer-drawn field).
It sits ALONGSIDE the synthetic scenario-driven rs_series/tech fields above,
never replacing them -- the scenario story (drought/flood/pest/etc) stays
intentionally fabricated for demonstration, while this one field shows what
today's actual satellite conditions are at that location, honestly labelled
as a live snapshot, not tied to the parcel's assigned scenario. This is the
"Optional per-parcel live satellite check" already named in the REAL-inputs
table in docs/DATA_SOURCES.md's crop-insurance-pilot section -- that line
predates this script actually calling it; this generator is what makes it
real rather than just documented.

DETERMINISM: fixed SEED -> the same 100 farmers' synthetic fields regenerate
identically. live_satellite_check is NOT deterministic across runs (it is a
real-time satellite query -- rerunning this script later will show whatever
the real conditions are at that later time).

Run (needs network -- calls the live Worker 100 times):
  python3 dashboard/crop_insurance_pilot/generate_synthetic_pilot.py
"""

import json
import math
import os
import random
import time
from collections import defaultdict

import requests
from shapely.geometry import shape, box, Point, mapping
from shapely.ops import transform as shp_transform

WORKER_ANALYZE_URL = "https://vindhya-mera-khet.vindhyaresearch25.workers.dev/analyze"


def call_live_analyze(ring_lonlat):
    """Real live GEE query via the deployed Mera Khet Worker -- same
    contract as dashboard/mera_khet_pilot/generate_synthetic_pilot.py's
    call_analyze(). Any failure is written honestly (available: false),
    never substituted with a plausible-looking guess."""
    try:
        r = requests.post(WORKER_ANALYZE_URL, json={"ring": ring_lonlat}, timeout=60)
        return r.json()
    except Exception as e:
        return {"available": False, "reason": "generator_request_failed", "detail": str(e)[:200]}

SEED = 20260819  # fixed -> identical dataset on every run

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BOUNDARY = os.path.join(ROOT, "dashboard/data/crop_insurance_pilot/simrol_boundary.geojson")
DES = os.path.join(ROOT, "dashboard/data/crop_stats_des_by_district/madhya_pradesh/indore.json")
OUT = os.path.join(ROOT, "dashboard/data/crop_insurance_pilot/synthetic_farmers_100.json")

# Section 2 of the spec: the exact scenario breakdown (sums to 100)
SCENARIOS = [
    ("healthy",       20, "Healthy / normal crop"),
    ("drought",       15, "Drought / dry spell"),
    ("excess_rain",   15, "Excess rainfall"),
    ("flood",         10, "Flood / waterlogging"),
    ("pest",          10, "Pest / disease stress"),
    ("hail",          10, "Hailstorm / storm damage"),
    ("crop_mismatch", 10, "Girdawari-vs-satellite crop mismatch"),
    ("area_mismatch",  5, "Cultivated-area mismatch"),
    ("mortgaged",      5, "Mortgaged / bank-linked land"),
]
assert sum(n for _, n, _ in SCENARIOS) == 100

# Crops actually recorded for Indore district in the real DES dataset.
CROPS = ["Soyabean", "Wheat", "Gram", "Maize", "Cotton(lint)",
         "Onion", "Potato", "Rapeseed &Mustard", "Urad"]

# CONFIGURABLE PILOT PARAMETERS -- not official notified values. Real PMFBY
# Sum Insured is the notified Scale of Finance and varies by state/district/
# season/crop; the UI exposes these as editable inputs (spec section 15:
# "Do not hard-code one universal rate").
SUM_INSURED_PER_HA = {
    "Soyabean": 45000, "Wheat": 42000, "Gram": 40000, "Maize": 38000,
    "Cotton(lint)": 62000, "Onion": 90000, "Potato": 95000,
    "Rapeseed &Mustard": 41000, "Urad": 36000,
}
# Real notified PMFBY farmer premium-share caps.
FARMER_PREMIUM_RATE = {"Kharif": 0.02, "Rabi": 0.015, "Commercial": 0.05}
COMMERCIAL_CROPS = {"Cotton(lint)", "Onion", "Potato"}
INDEMNITY_LEVEL = 0.80      # notified per crop (70/80/90%); configurable in UI
GROSS_PREMIUM_RATE = 0.11   # discovered by insurer bidding; pilot assumption

LAND_STATUS = ["Owner-cultivated (SYNTHETIC)",
               "Tenant-cultivated (SYNTHETIC)",
               "Owner-cultivated, joint holding (SYNTHETIC)"]
IRRIGATION_SOURCES = ["Tube well", "Canal", "Open well", "Rainfed (none)"]

MONTHS = ["June", "July", "August", "September", "October"]
STAGES = ["Sowing", "Emergence", "Vegetative Growth", "Flowering",
          "Grain/Fruit Development", "Maturity"]

# Relative canopy vigour Jun -> Oct for a normal, undamaged crop.
SHAPE_F = [0.30, 0.68, 1.00, 0.88, 0.55]

EVENT_BY_SCENARIO = {
    "drought":     ("Drought / dry spell",      "Prolonged rainfall deficit"),
    "excess_rain": ("Excess rainfall",          "Continuous heavy rainfall spell"),
    "flood":       ("Flood / waterlogging",     "Field inundation, standing water"),
    "pest":        ("Pest / disease stress",    "Pest incidence above threshold"),
    "hail":        ("Hailstorm / storm damage", "Hail with strong wind"),
}

# --- PART 1 END ---


def to_metres(geom, lon0, lat0):
    mlat = 110540.0
    mlon = 111320.0 * math.cos(math.radians(lat0))
    return shp_transform(lambda x, y: ((x - lon0) * mlon, (y - lat0) * mlat), geom)


def to_degrees(geom, lon0, lat0):
    mlat = 110540.0
    mlon = 111320.0 * math.cos(math.radians(lat0))
    return shp_transform(lambda x, y: (x / mlon + lon0, y / mlat + lat0), geom)


def ha(geom_m):
    return geom_m.area / 10000.0


def r2(x):
    return round(x + 1e-12, 2)


def round_geom(geom, nd=6):
    return shp_transform(lambda x, y: (round(x, nd), round(y, nd)), geom)


def des_baselines():
    """Per-crop yield baselines from the REAL DES Indore district records.

    threshold_yield follows the actual PMFBY method: mean of the best 5 of the
    last 7 available years, times the indemnity level. Nothing here is invented.
    """
    with open(DES, encoding="utf-8") as fh:
        recs = json.load(fh)["records"]
    by_crop = defaultdict(list)
    for r in recs:
        y = r.get("yield_per_ha")
        if r.get("crop") in CROPS and isinstance(y, (int, float)) and y > 0:
            start = int(str(r["year"]).split("-")[0].strip())
            by_crop[r["crop"]].append((start, float(y), r.get("season") or ""))
    out = {}
    for crop, rows in by_crop.items():
        rows.sort(key=lambda t: t[0])
        last7 = rows[-7:]
        best5 = sorted((v for _, v, _ in last7), reverse=True)[:5]
        seasons = [s.strip() for _, _, s in rows if s and s.strip() not in ("", "Whole Year")]
        season = max(set(seasons), key=seasons.count) if seasons else "Kharif"
        last10 = rows[-10:]
        out[crop] = {
            "crop": crop,
            "season": season,
            "des_years_used": [y for y, _, _ in last7],
            "des_mean_yield_t_ha": round(sum(v for _, v, _ in last10) / len(last10), 3),
            "des_best5of7_mean_t_ha": round(sum(best5) / len(best5), 3),
            "threshold_yield_t_ha": round((sum(best5) / len(best5)) * INDEMNITY_LEVEL, 3),
            "source": "DES (data.desagri.gov.in), Indore district -- REAL",
        }
    return out

# --- PART 2 END ---


def build_parcels(village_m, rng, n=100):
    """Fine grid over the REAL village polygon, clipped to it, with ~45% of
    cells subdivided so holding sizes vary realistically (0.35-2.0 ha)."""
    minx, miny, maxx, maxy = village_m.bounds
    step = 132.0  # ~1.74 ha per full cell
    cells = []
    x = minx
    while x < maxx:
        y = miny
        while y < maxy:
            cell = box(x, y, x + step, y + step)
            if village_m.intersects(cell):
                clipped = village_m.intersection(cell)
                if clipped.geom_type == "Polygon" and 0.55 <= ha(clipped) <= 2.0:
                    cells.append(clipped)
            y += step
        x += step

    rng.shuffle(cells)
    parcels = []
    for cell in cells:
        if len(parcels) >= n:
            break
        if rng.random() < 0.45 and ha(cell) > 1.2:
            cminx, cminy, cmaxx, cmaxy = cell.bounds
            frac = rng.uniform(0.38, 0.62)
            if (cmaxx - cminx) >= (cmaxy - cminy):
                cut = cminx + (cmaxx - cminx) * frac
                halves = [box(cminx, cminy, cut, cmaxy), box(cut, cminy, cmaxx, cmaxy)]
            else:
                cut = cminy + (cmaxy - cminy) * frac
                halves = [box(cminx, cminy, cmaxx, cut), box(cminx, cut, cmaxx, cmaxy)]
            for h in halves:
                piece = cell.intersection(h)
                if piece.geom_type == "Polygon" and ha(piece) >= 0.35 and len(parcels) < n:
                    parcels.append(piece)
        else:
            parcels.append(cell)
    return parcels[:n]


def decompose(parcel_m, rng, scenario):
    """Carve a parcel into cadastral components. Every area is GEOMETRY-DERIVED,
    so cultivated + bund + fallow + non-crop + road + water == cadastral area."""
    area = ha(parcel_m)
    comps = {}

    # Bund / med: boundary ring from a negative buffer (real field bunds are
    # 1-3 m earthen ridges around the plot).
    bund_w = rng.uniform(1.4, 2.8)
    inner = parcel_m.buffer(-bund_w)
    if inner.is_empty or inner.geom_type != "Polygon":
        inner = parcel_m.buffer(-0.8)
    comps["bund"] = parcel_m.difference(inner)

    remaining = inner
    minx, miny, maxx, maxy = remaining.bounds

    # Farm road: thin strip along one edge, on roughly half the parcels.
    road = None
    if rng.random() < 0.5:
        w = rng.uniform(2.5, 4.0)
        strip = box(minx, miny, maxx, miny + w) if rng.random() < 0.5 \
            else box(minx, miny, minx + w, maxy)
        road = remaining.intersection(strip)
        if road.is_empty or road.geom_type not in ("Polygon", "MultiPolygon"):
            road = None
        else:
            remaining = remaining.difference(strip)

    # Waterbody: small farm pond on a minority of parcels.
    water = None
    if rng.random() < 0.18:
        cx = rng.uniform(minx + 12, maxx - 12)
        cy = rng.uniform(miny + 12, maxy - 12)
        disc = Point(cx, cy).buffer(rng.uniform(7, 12))
        water = remaining.intersection(disc)
        if water.is_empty or water.geom_type != "Polygon":
            water = None
        else:
            remaining = remaining.difference(disc)

    # Fallow / non-crop block -- deliberately larger for the area-mismatch scenario.
    frac = rng.uniform(0.20, 0.32) if scenario == "area_mismatch" else rng.uniform(0.04, 0.16)
    rminx, rminy, rmaxx, rmaxy = remaining.bounds
    cutbox = box(rminx, rmaxy - (rmaxy - rminy) * frac, rmaxx, rmaxy) if rng.random() < 0.5 \
        else box(rmaxx - (rmaxx - rminx) * frac, rminy, rmaxx, rmaxy)
    fallow = remaining.intersection(cutbox)
    if fallow.is_empty:
        fallow = None
    else:
        remaining = remaining.difference(cutbox)

    # Non-crop (homestead / tree cover) corner on some parcels.
    noncrop = None
    if rng.random() < 0.35:
        s = rng.uniform(9, 16)
        nminx, nminy, _, _ = remaining.bounds
        corner = box(nminx, nminy, nminx + s, nminy + s)
        noncrop = remaining.intersection(corner)
        if noncrop.is_empty or noncrop.area < 1:
            noncrop = None
        else:
            remaining = remaining.difference(corner)

    comps["road"] = road
    comps["water"] = water
    comps["fallow"] = fallow
    comps["noncrop"] = noncrop
    comps["cultivated"] = remaining
    comps["cadastral_ha"] = area
    return comps


# A "Very Severe" event must produce a deeper decline than a "Moderate" one --
# otherwise the intensity label and the vegetation response contradict each other.
INTENSITY_FACTOR = {"Moderate": 0.75, "Severe": 1.05, "Very Severe": 1.40}


def ndvi_series(rng, scenario, event_month_idx, peak, intensity=None):
    """SIMULATED phenology curve with event-driven decline and partial recovery.
    This is NOT a satellite observation."""
    out = []
    for i, f in enumerate(SHAPE_F):
        v = peak * f + rng.uniform(-0.02, 0.02)
        if scenario != "healthy" and event_month_idx is not None and i >= event_month_idx:
            drop = {"drought": 0.34, "excess_rain": 0.26, "flood": 0.40,
                    "pest": 0.22, "hail": 0.36}.get(scenario, 0.20)
            drop = min(0.85, drop * INTENSITY_FACTOR.get(intensity, 1.0))
            v *= 1.0 - drop * (0.62 ** (i - event_month_idx))
        out.append(max(0.06, round(v, 3)))
    return out

# --- PART 3 END ---


def build_farmer(n, pm, scenario, scen_label, crop, binfo, base, rng, props, lon0, lat0):
    """Assemble one SYNTHETIC farmer record (spec sections 2,3,5,6,9,11-16,18)."""
    season = binfo["season"] if binfo["season"] in ("Kharif", "Rabi") else "Kharif"

    comps = decompose(pm, rng, scenario)
    cad = comps["cadastral_ha"]
    cult = ha(comps["cultivated"])
    bund = ha(comps["bund"])
    fallow = ha(comps["fallow"]) if comps["fallow"] is not None else 0.0
    noncrop = ha(comps["noncrop"]) if comps["noncrop"] is not None else 0.0
    road = ha(comps["road"]) if comps["road"] is not None else 0.0
    water = ha(comps["water"]) if comps["water"] is not None else 0.0

    irr_source = IRRIGATION_SOURCES[rng.randrange(len(IRRIGATION_SOURCES))]
    irrigated = 0.0 if irr_source == "Rainfed (none)" else cult * rng.uniform(0.55, 1.0)
    rainfed = max(0.0, cult - irrigated)

    # Section 5 -- girdawari reports the whole parcel, as records typically do
    reported_area = round(cad * rng.uniform(0.94, 1.02), 2)

    # Section 11 -- event
    if scenario in EVENT_BY_SCENARIO:
        ev_type, ev_desc = EVENT_BY_SCENARIO[scenario]
        ev_month_idx = rng.randrange(1, 4)
        ev_date = "%02d-%02d-2025" % (rng.randrange(3, 27), 6 + ev_month_idx)
        ev_intensity = rng.choice(["Moderate", "Severe", "Very Severe"])
    else:
        ev_type = ev_desc = ev_date = ev_intensity = ev_month_idx = None

    # Section 9 -- SIMULATED remote sensing
    peak = rng.uniform(0.68, 0.82)
    ts = ndvi_series(rng, scenario, ev_month_idx, peak, ev_intensity)
    ndwi, evi = [], []
    for k, v in enumerate(ts):
        adj = 0.0
        if ev_month_idx is not None and k >= ev_month_idx:
            if scenario == "flood":
                adj = 0.30
            elif scenario == "excess_rain":
                adj = 0.14
            elif scenario == "drought":
                adj = -0.14
        ndwi.append(round(min(0.55, max(-0.35, v * 0.42 - 0.16 + adj)), 3))
        evi.append(round(v * rng.uniform(0.72, 0.80), 3))

    # Damage is measured as a vegetation ANOMALY against the expected undamaged
    # curve for the SAME date -- not as a raw month-on-month difference. Early in
    # the season the canopy is still growing, so a month-on-month comparison
    # confounds damage with normal growth and can even yield a negative "decline".
    expected_curve = [peak * k for k in SHAPE_F]
    if ev_month_idx is not None:
        ndvi_before = ts[ev_month_idx - 1]          # last observation before the event
        ndvi_after = ts[ev_month_idx]               # first observation after it
        ndvi_expected = round(expected_curve[ev_month_idx], 3)
        decline = max(0.0, (expected_curve[ev_month_idx] - ndvi_after)
                      / expected_curve[ev_month_idx] * 100.0)
    else:
        ndvi_before = ndvi_after = ndvi_expected = None
        decline = 0.0

    # Section 12 -- damage, as a share of CULTIVATED area
    if scenario in EVENT_BY_SCENARIO:
        dmg_frac = min(0.92, max(0.08, decline / 100.0 * rng.uniform(1.05, 1.5)))
        damage_area = cult * dmg_frac
        loss_pct = round(min(85.0, decline * rng.uniform(0.9, 1.25)), 1)
    else:
        dmg_frac = damage_area = 0.0
        loss_pct = 0.0

    # Crop health = vigour RETAINED against the expected undamaged curve for the
    # same dates. Using the raw October value instead would score every parcel as
    # "stressed" simply because canopies senesce at maturity.
    # Score the WORST observed condition against expectation: a season average
    # would let pre-event months and post-event recovery mask the damage.
    retained = min(min(1.0, ts[i] / e) for i, e in enumerate(expected_curve))
    health = int(max(8, min(97, round(100 * retained * rng.uniform(0.95, 1.02)))))
    stage = STAGES[min(len(STAGES) - 1, 2 + (n % 4))]

    # Section 6/7 -- AI/RS classification
    #
    # ai_confidence_pct is COMPUTED, not drawn. Until 2026-09-02 it was
    # `round(rng.uniform(86.0, 95.0), 1)` -- a pure random number with no
    # connection to any other field in the record, which is exactly the
    # "random display number" CROP_INSURANCE_SYSTEM_PROMPT.md Sec 21(i)
    # forbids. It was also the single most-repeated figure in the UI (11
    # render sites) AND it drove a decision rule below (`ai_conf < 88` ->
    # "additional evidence advised"), i.e. an anomaly flag decided by a coin
    # flip. Being a synthetic study does not excuse that: the requirement is
    # that every number be correctly computed FROM the synthetic inputs by a
    # real formula, so that a reader can re-derive it.
    #
    # Three real, weighted terms, all traceable to fields stored in this same
    # record. The components are written into the output so the UI can show
    # the arithmetic, exactly as it already does for the evidence score:
    #
    #  1. PHENOLOGY FIT (w 0.45) -- how closely this parcel's own simulated
    #     NDVI series tracks the undamaged expected curve for the same dates.
    #     A classifier keyed on crop phenology is most confident on a clean,
    #     on-curve signal and least confident on a disturbed canopy.
    #  2. PIXEL SUPPORT (w 0.25) -- a Sentinel-2 pixel is 10 m x 10 m =
    #     0.01 ha, so a parcel's cultivated area IS its pixel count. More
    #     pixels = more samples = a better-supported class decision. Log
    #     scaled, saturating at 1000 px (10 ha): the 20th pixel adds far more
    #     than the 1000th does.
    #  3. CLASS SEPARABILITY (w 0.30) -- 1.0 when the classifier's crop and
    #     the girdawari crop agree (one consistent hypothesis). When they
    #     disagree, the decision was taken among the real set of same-season
    #     candidate crops, so confidence falls as that candidate set grows:
    #     more plausible alternatives means less separable.
    px_per_ha = 100.0 * 100.0            # 10 m Sentinel-2 pixel = 0.01 ha
    n_pixels = max(1.0, cult * px_per_ha)
    support = min(1.0, math.log10(n_pixels) / 3.0)
    dev = [abs(ts[i] - e) / e for i, e in enumerate(expected_curve) if e > 0]
    fit = max(0.0, 1.0 - (sum(dev) / len(dev) if dev else 0.0))

    if scenario == "crop_mismatch":
        alts = [x for x in CROPS if x != crop and x in base and base[x]["season"] == binfo["season"]] \
            or [x for x in CROPS if x != crop and x in base]
        ai_crop = alts[n % len(alts)]
        separability = 1.0 / (1.0 + 0.5 * len(alts))
    else:
        ai_crop = crop
        alts = []
        separability = 1.0

    ai_conf_components = [
        {"factor": "Phenology fit to expected curve",
         "value": "mean deviation from expected = %.1f%%" % ((1.0 - fit) * 100.0),
         "score": round(100.0 * fit, 1), "weight": 0.45},
        {"factor": "Pixel support (Sentinel-2 10 m)",
         "value": "%d pixels over %.2f ha cultivated" % (int(n_pixels), cult),
         "score": round(100.0 * support, 1), "weight": 0.25},
        {"factor": "Class separability",
         "value": ("classifier agrees with girdawari crop"
                   if not alts else
                   "%d same-season candidate crops considered" % len(alts)),
         "score": round(100.0 * separability, 1), "weight": 0.30},
    ]
    ai_conf = round(sum(c["score"] * c["weight"] for c in ai_conf_components), 1)

    area_diff = reported_area - cult
    area_diff_pct = (area_diff / reported_area * 100.0) if reported_area else 0.0

    # Section 18 -- flags only, never a fraud verdict
    anomalies = []
    if scenario == "crop_mismatch":
        anomalies.append("Crop mismatch: girdawari record differs from AI/RS classification")
    if abs(area_diff_pct) >= 30:
        anomalies.append("Cultivated-area mismatch: reported area exceeds detected cultivated area by %.1f%%" % area_diff_pct)
    if scenario == "mortgaged":
        anomalies.append("Bank-linked/mortgaged holding: lender interest recorded, verification of insured area advised")
    if loss_pct >= 45:
        anomalies.append("High simulated loss estimate: field inspection recommended before assessment")
    if ai_conf < 88:
        anomalies.append("AI confidence below 88%: additional evidence advised")

    # Section 13 -- explicit weighted evidence components.
    #
    # Every component score below is DERIVED from a quantity stored elsewhere
    # in this same record, so a reader can re-add them and get the published
    # evidence score back. Four of the seven used to be `rng.uniform(...)`
    # draws (2026-09-02 audit): the NDWI, rainfall-anomaly and
    # multi-temporal components in the event branch, and both components in
    # the no-event branch -- together roughly 70% of the total weight. They
    # were replaced with the real signals that were already being simulated
    # and stored a few lines above, which is what Sec 21(i) asks for. The
    # weights themselves are a fixed, stated editorial choice, not fitted to
    # anything -- that is why they are printed on screen next to each score.
    if scenario in EVENT_BY_SCENARIO:
        # Real observed NDWI step across the event date. Waterlogging shows
        # up as a POSITIVE step (more surface water), drought as a negative
        # one; the magnitude of the step is the evidence, so use its size and
        # keep the sign in the displayed value for the reader.
        ndwi_step = ndwi[ev_month_idx] - ndwi[ev_month_idx - 1]
        # 0.30 NDWI is the largest step this simulator produces (flood), so
        # scale against that and clamp.
        ndwi_score = min(100.0, abs(ndwi_step) / 0.30 * 100.0)
        # Real observed departure of the series from the expected curve,
        # measured over every date AFTER the event rather than just the
        # event date -- a persistent depression is stronger evidence than a
        # single-date dip, and that persistence is a real property of `ts`.
        post = [(expected_curve[k] - ts[k]) / expected_curve[k]
                for k in range(ev_month_idx, len(ts)) if expected_curve[k] > 0]
        persistence = sum(1 for d in post if d > 0.05) / len(post) if post else 0.0
        mt_score = min(100.0, 100.0 * (0.5 * persistence + 0.5 * min(1.0, decline / 50.0)))
        ev_components = [
            {"factor": "NDVI decline vs expected", "value": "%.1f%% below expected" % decline,
             "score": round(min(100, decline * 2.4), 1), "weight": 0.30},
            {"factor": "NDWI / waterlogging signal",
             "value": "%.3f -> %.3f (step %+.3f)" % (ndwi[ev_month_idx - 1], ndwi[ev_month_idx], ndwi_step),
             "score": round(ndwi_score, 1), "weight": 0.20},
            {"factor": "Rainfall / weather anomaly", "value": "%s (%s)" % (ev_type, ev_intensity),
             "score": float({"Moderate": 62, "Severe": 80, "Very Severe": 92}[ev_intensity]),
             "weight": 0.20},
            {"factor": "Spatial damage pattern", "value": "%.2f ha contiguous within parcel" % damage_area,
             "score": round(min(100, 45 + dmg_frac * 60), 1), "weight": 0.15},
            {"factor": "Multi-temporal change detection",
             "value": "%d-date series, Jun-Oct; %.0f%% of post-event dates below expected"
                      % (len(ts), persistence * 100.0),
             "score": round(mt_score, 1), "weight": 0.15},
        ]
    else:
        # No event: the evidence is that nothing departed from expectation.
        # Score the real closeness of the series to the expected curve
        # (`fit`, computed above for the classifier) and the real absence of
        # any single-date drop, instead of drawing a number in the 80s.
        worst_drop = max([(e - ts[k]) / e for k, e in enumerate(expected_curve) if e > 0] or [0.0])
        stability = max(0.0, 1.0 - worst_drop / 0.25)
        ev_components = [
            {"factor": "Multi-temporal vegetation stability",
             "value": "no anomaly detected; worst single-date departure %.1f%% below expected"
                      % (worst_drop * 100.0),
             "score": round(100.0 * stability, 1), "weight": 0.5},
            {"factor": "Crop calendar consistency",
             "value": "matches %s calendar; mean departure from expected curve %.1f%%"
                      % (season, (1.0 - fit) * 100.0),
             "score": round(100.0 * fit, 1), "weight": 0.5},
        ]
    evidence_score = round(sum(x["score"] * x["weight"] for x in ev_components), 1)
    verification_required = bool(anomalies) or loss_pct >= 30

    # Sections 15/16 -- insurance
    rate_key = "Commercial" if crop in COMMERCIAL_CROPS else season
    prem_rate = FARMER_PREMIUM_RATE[rate_key]
    si_per_ha = SUM_INSURED_PER_HA[crop]
    insured_area = round(cult, 2) if scenario == "mortgaged" else round(cult * rng.uniform(0.9, 1.0), 2)
    sum_insured = insured_area * si_per_ha
    farmer_premium = sum_insured * prem_rate
    gross_premium = sum_insured * GROSS_PREMIUM_RATE
    subsidy = max(0.0, gross_premium - farmer_premium)

    threshold_yield = binfo["threshold_yield_t_ha"]
    actual_yield = round(threshold_yield * (1 - loss_pct / 100.0) * rng.uniform(0.97, 1.06), 3)
    shortfall = max(0.0, (threshold_yield - actual_yield) / threshold_yield) if threshold_yield else 0.0
    indicative_claim = round(shortfall * sum_insured)

    parcel_deg = round_geom(to_degrees(pm, lon0, lat0))
    cen_deg = to_degrees(pm.centroid, lon0, lat0)

    # Real, live GEE query against this farmer's actual (synthetic) parcel
    # ring -- see this module's header for why this is additive, not a
    # replacement for the scenario-driven rs_series/tech fields below.
    # Worker's validateRing expects [lon, lat] pairs; shapely's own
    # exterior.coords are already (x, y) = (lon, lat), no swap needed.
    ring_for_worker = [[lon, lat] for lon, lat in parcel_deg.exterior.coords]
    live_check = call_live_analyze(ring_for_worker)

    def geo(g):
        if g is None or g.is_empty or g.geom_type not in ("Polygon", "MultiPolygon"):
            return None
        return mapping(round_geom(to_degrees(g, lon0, lat0)))

    return {
        "synthetic": True,
        "farmer_id": "SF-%03d" % n,
        "farmer_name": "SYN-FARMER-%03d" % n,
        "farmer_name_local": "किसान-उदाहरण-%03d" % n,
        "khasra_no": "SYN-%d/%d" % (100 + n, 1 + (n % 4)),
        "parcel_id": "SYN-PCL-%03d" % n,
        "village": props["village_name"], "tehsil": props["subdistrict_name"],
        "district": props["district_name"], "state": "Madhya Pradesh",
        "land_status": ("Mortgaged / bank-linked (SYNTHETIC)" if scenario == "mortgaged"
                        else LAND_STATUS[n % len(LAND_STATUS)]),
        "scenario": scenario, "scenario_label": scen_label,

        "cadastral_area_ha": r2(cad), "cultivated_area_ha": r2(cult),
        "bund_area_ha": r2(bund), "fallow_area_ha": r2(fallow),
        "noncrop_area_ha": r2(noncrop), "farm_road_ha": r2(road), "waterbody_ha": r2(water),
        "irrigated_area_ha": r2(irrigated), "rainfed_area_ha": r2(rainfed),
        "irrigation_source": irr_source,
        "centroid": [round(cen_deg.x, 6), round(cen_deg.y, 6)],
        "geometry": mapping(parcel_deg),
        "components": {k: geo(comps[k]) for k in
                       ("cultivated", "bund", "fallow", "noncrop", "road", "water")},

        "live_satellite_check": {
            "note": "REAL, not synthetic -- a live Google Earth Engine query against this "
                    "farmer's actual parcel polygon, generated at script-run time. Independent "
                    "of the scenario/rs_series fields above, which stay deliberately synthetic "
                    "for demonstration.",
            "available": bool(live_check.get("available")),
            "ndvi_now": live_check.get("ndvi"),
            "cropland_fraction_now": live_check.get("cropland_fraction"),
            "field_wetness_index_relative_pct": live_check.get("field_wetness_index_relative"),
            "field_wetness_caveat": live_check.get("field_wetness_index_caveat"),
            "source": live_check.get("source"),
            "error": None if live_check.get("available") else (live_check.get("reason") or live_check.get("error")),
        },

        "girdawari": {
            "crop": crop, "season": season, "reported_area_ha": reported_area,
            "reported_loss_pct": round(loss_pct * rng.uniform(0.55, 1.45), 1) if loss_pct > 0 else 0.0,
            "assessment_status": "Manual assessment pending" if loss_pct > 0 else "No loss reported",
            "evidence_available": ("Patwari field note (SIMULATED)" if loss_pct > 0
                                   else "Routine girdawari entry (SIMULATED)"),
            "record_id": "SYN-GRD-%03d" % n,
        },

        "tech": {
            "ai_crop": ai_crop, "ai_confidence_pct": ai_conf,
            "ai_confidence_components": ai_conf_components,
            "detected_cultivated_area_ha": r2(cult),
            "area_difference_ha": r2(area_diff), "area_difference_pct": round(area_diff_pct, 1),
            "crop_stage": stage, "crop_health_score": health,
            "vegetation_anomaly": ("None detected" if scenario == "healthy"
                                   else "%.1f%% below expected NDVI after event" % decline),
            "damage_area_ha": r2(damage_area), "estimated_loss_pct": loss_pct,
            "evidence_score_pct": evidence_score, "evidence_components": ev_components,
            "verification_required": verification_required,
            "verification_status": "Verification Required" if verification_required else "Auto-cleared (pilot)",
        },

        "rs_series": {
            "note": "SIMULATED REMOTE-SENSING DATA -- not actual satellite observations",
            "months": MONTHS, "ndvi": ts, "ndwi": ndwi, "evi": evi,
            "stages": [STAGES[min(len(STAGES) - 1, k + 1)] for k in range(len(MONTHS))],
        },

        "event": None if ev_type is None else {
            "date": ev_date, "type": ev_type, "description": ev_desc,
            "intensity": ev_intensity, "affected_area_ha": r2(damage_area),
            "pre_event_ndvi": ndvi_before, "post_event_ndvi": ndvi_after,
            "expected_ndvi": ndvi_expected,
            "ndvi_decline_pct": round(decline, 1),
            "pre_event_condition": "Canopy before event, NDVI %.2f" % ndvi_before,
            "post_event_condition": "Stressed canopy, NDVI %.2f (expected %.2f)" % (ndvi_after, ndvi_expected),
        },

        "anomalies": anomalies,

        "insurance": {
            "insured_area_ha": insured_area, "sum_insured_per_ha": si_per_ha,
            "sum_insured": round(sum_insured),
            "farmer_premium_rate_pct": round(prem_rate * 100, 2), "premium_rate_basis": rate_key,
            "farmer_premium": round(farmer_premium), "gross_premium": round(gross_premium),
            "subsidy": round(subsidy),
            "premium_per_ha": round(farmer_premium / insured_area) if insured_area else 0,
            "indemnity_level_pct": round(INDEMNITY_LEVEL * 100),
            "threshold_yield_t_ha": threshold_yield, "actual_yield_t_ha": actual_yield,
            "yield_shortfall_pct": round(shortfall * 100, 1),
            "indicative_claim": indicative_claim,
            "status": "Insured (SYNTHETIC policy record)",
        },
    }

# --- PART 4 END ---


def main():
    rng = random.Random(SEED)

    with open(BOUNDARY, encoding="utf-8") as fh:
        feat = json.load(fh)["feature"]
    props = feat["properties"]
    village = shape(feat["geometry"])
    lon0, lat0 = village.centroid.x, village.centroid.y
    village_m = to_metres(village, lon0, lat0)

    base = des_baselines()
    crops = [c for c in CROPS if c in base]
    missing = [c for c in CROPS if c not in base]
    if missing:
        raise SystemExit("no real DES baseline for: %s -- refusing to invent one" % missing)

    parcels_m = build_parcels(village_m, rng, 100)
    if len(parcels_m) < 100:
        raise SystemExit("only %d parcels generated" % len(parcels_m))

    scen_list = []
    for key, n, label in SCENARIOS:
        scen_list += [(key, label)] * n
    rng.shuffle(scen_list)

    farmers = []
    for i, pm in enumerate(parcels_m):
        scenario, scen_label = scen_list[i]
        crop = crops[i % len(crops)]
        t0 = time.time()
        f = build_farmer(i + 1, pm, scenario, scen_label, crop,
                          base[crop], base, rng, props, lon0, lat0)
        farmers.append(f)
        lc = f["live_satellite_check"]
        print(f"[{i+1}/100] SF-{i+1:03d}: live GEE check available={lc['available']} "
              f"in {time.time()-t0:.1f}s")

    disclaimer = (
        "This is a Pilot Study/Proof-of-Concept based entirely on synthetic and simulated "
        "data. The farmer records, cadastral parcels, crop observations, remote-sensing "
        "observations, weather events, crop-loss estimates, insurance premiums and claim "
        "values are generated for research and demonstration purposes only. The system does "
        "not represent actual farmer records, official satellite observations, official "
        "crop-loss assessment or official PMFBY claim determination. Real-world deployment "
        "would require field validation, authorized datasets, applicable government protocols "
        "and regulatory approval."
    )

    payload = {
        "metadata": {
            "title": ("GIS, Remote Sensing and AI-Assisted Cadastral-Level Crop Insurance "
                      "Assessment: A Synthetic 100-Farmer Pilot Study"),
            "dataset": "synthetic_farmers_100",
            "synthetic": True,
            "SYNTHETIC_DATA_NOTICE": (
                "ALL FARMER RECORDS, CADASTRAL PARCELS, GIRDAWARI ENTRIES, REMOTE-SENSING TIME "
                "SERIES, WEATHER EVENTS, DAMAGE ESTIMATES, PREMIUMS AND CLAIM VALUES IN THIS "
                "FILE ARE SYNTHETIC AND SIMULATED, generated for a research pilot study / "
                "proof-of-concept. They are NOT real farmer records, NOT official satellite "
                "observations, NOT official crop-loss assessment and NOT official PMFBY claim "
                "determination. No real identities, Aadhaar numbers, bank details or policy "
                "numbers are present or derivable."
            ),
            "source": (
                "SYNTHETIC dataset generated by dashboard/crop_insurance_pilot/"
                "generate_synthetic_pilot.py (fixed seed %d). REAL components reused: Survey of "
                "India / NWDP Simrol village boundary (vil_lgd 476504) and its Census population/"
                "household fields; DES (data.desagri.gov.in) Indore district crop yield history "
                "for per-crop yield baselines and PMFBY threshold yields; notified PMFBY farmer "
                "premium-share caps (Kharif 2%%, Rabi 1.5%%, annual commercial/horticultural 5%%)."
            ) % SEED,
            "resolution": ("Cadastral parcel level (synthetic parcels, 0.35-2.0 ha), clipped to "
                           "the real Simrol village polygon"),
            "crs": "EPSG:4326",
            "processing": (
                "Deterministic seeded generation (seed %d). Parcels: 132 m grid over the real "
                "village polygon, clipped, ~45%% subdivided for holding-size variety. Parcel "
                "components (bund/med, farm road, waterbody, fallow, non-crop, cultivated) are "
                "GEOMETRICALLY DERIVED via negative-buffer and difference operations, so they sum "
                "exactly to the cadastral area. Yield baselines: real DES Indore series; threshold "
                "yield = mean of best 5 of last 7 available years x %d%% indemnity level. "
                "NDVI/NDWI/EVI: simulated phenology curves with event-driven decline -- NOT "
                "satellite observations."
            ) % (SEED, round(INDEMNITY_LEVEL * 100)),
            "last_updated": "2026-08-19",
            "scenario_breakdown": {k: n for k, n, _ in SCENARIOS},
            "configurable_parameters": {
                "sum_insured_per_ha": SUM_INSURED_PER_HA,
                "farmer_premium_rate": FARMER_PREMIUM_RATE,
                "indemnity_level": INDEMNITY_LEVEL,
                "gross_premium_rate": GROSS_PREMIUM_RATE,
                "note": ("Sum Insured per hectare and the actuarial/gross premium rate are "
                         "CONFIGURABLE PILOT PARAMETERS, not official notified values. Actual "
                         "PMFBY Sum Insured is the notified Scale of Finance and varies by state/"
                         "district/season/crop; the actuarial rate is discovered by insurer "
                         "bidding per cluster. The farmer premium-share caps are the real "
                         "notified scheme caps."),
            },
            "village_real_boundary": {
                "village": props["village_name"], "vil_lgd": props["vil_lgd"],
                "block": props["block_name"], "district": props["district_name"],
                "state": props["state_name"],
                "population_census": props["population"],
                "households_census": props["households"],
                "source": ("Survey of India village boundary via National Water Data Portal "
                           "(NWDP) -- REAL"),
            },
            "yield_baselines_real_des": base,
            "disclaimer": disclaimer,
        },
        "farmers": farmers,
    }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    tot_cad = sum(f["cadastral_area_ha"] for f in farmers)
    tot_cult = sum(f["cultivated_area_ha"] for f in farmers)
    print("wrote %s" % OUT)
    print("farmers=%d  cadastral=%.2f ha  cultivated=%.2f ha" % (len(farmers), tot_cad, tot_cult))
    print("damaged=%d  verification_required=%d  crops=%d"
          % (sum(1 for f in farmers if f["tech"]["damage_area_ha"] > 0),
             sum(1 for f in farmers if f["tech"]["verification_required"]), len(crops)))
    print("size=%.1f KB" % (os.path.getsize(OUT) / 1024.0))


if __name__ == "__main__":
    main()
