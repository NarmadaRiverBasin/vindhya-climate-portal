#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYNTHETIC MERA KHET PROOF-OF-CONCEPT -- data generator

  *** OWNER-AUTHORIZED, NARROWLY-SCOPED EXCEPTION TO CLAUDE.md's
      "No synthetic data, ever" RULE -- same bounded pattern as
      dashboard/crop_insurance_pilot/generate_synthetic_pilot.py.
      Read that file's header first; this one follows it exactly. ***

PURPOSE: Mera Khet (dashboard/mera_khet.js) lets a real farmer draw their
own field polygon and get a real, live GeoAI analysis (satellite NDVI,
cropland fraction, Sentinel-1 field wetness) -- but nobody has drawn a
real field yet, so there's nothing to show as a demo of what the feature
actually produces. Owner asked for a synthetic proof-of-concept: "MP ke
[crop-insurance] demo jaise ... synthetic, keval samajhne ke liye" (like
the MP demo, synthetic, only for understanding).

SCOPE: output is dashboard/data/mera_khet_pilot/synthetic_fields.json,
consumed by exactly one standalone page (mera_khet_pilot/pilot_study.html).
Never merged into the live Mera Khet feature or any national dataset.

REAL (must stay real):
  - Simrol village polygon (same file the crop_insurance_pilot already
    uses: dashboard/data/crop_insurance_pilot/simrol_boundary.geojson --
    Survey of India via NWDP, vil_lgd 476504) -- every synthetic field is
    clipped inside it.
  - Per-field NDVI, Dynamic World cropland fraction, and Sentinel-1 field
    wetness: LIVE Google Earth Engine query via the actual deployed Mera
    Khet Worker's /analyze endpoint (cloudflare/mera_khet_worker.js) --
    the exact same call the real feature makes when a farmer draws a
    polygon. If the Worker reports unavailable for a field, this script
    writes that honestly (available: false), never substitutes a guess.
  - Indore district climate (IMD, mp_climate_data.json), soil moisture
    (NASA SMAP, dashboard/data/soil_moisture/) and soil type (OpenLandMap/
    ISRIC, dashboard/data/soil_type/) -- real per-district files already
    in this repo, reused as-is. If a file isn't ready yet it says so.

SYNTHETIC (the point of the demo): the field boundaries themselves
(randomly placed/sized small polygons inside the real village), and the
farmer labels (SYN-KHET-001 etc, non-realistic placeholders -- no name,
Aadhaar, phone or bank detail is ever generated).

DETERMINISM: fixed SEED -> the same fields regenerate identically.

Run (needs network -- calls the live Worker N times):
  python3 dashboard/mera_khet_pilot/generate_synthetic_pilot.py
"""

import json
import math
import os
import random
import time

import requests
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

SEED = 20261021  # fixed -> identical fields on every run
N_FIELDS = 12     # kept small -- each one is a real live GEE call

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BOUNDARY = os.path.join(ROOT, "dashboard/data/crop_insurance_pilot/simrol_boundary.geojson")
MP_CLIMATE = os.path.join(ROOT, "dashboard/data/mp_climate_data.json")
SOIL_MOISTURE = os.path.join(ROOT, "dashboard/data/soil_moisture/madhya_pradesh/indore.json")
SOIL_TYPE = os.path.join(ROOT, "dashboard/data/soil_type/madhya_pradesh/indore.json")
OUT = os.path.join(ROOT, "dashboard/data/mera_khet_pilot/synthetic_fields.json")
WORKER_ANALYZE_URL = "https://vindhya-mera-khet.vindhyaresearch25.workers.dev/analyze"

random.seed(SEED)


def load_boundary():
    data = json.loads(open(BOUNDARY, encoding="utf-8").read())
    return shape(data["feature"]["geometry"]), data["feature"].get("properties", {})


def ha_to_deg_side(ha, lat_deg):
    """Rough square side length in degrees for a given area in hectares
    at this latitude -- good enough for placing small demo polygons, not
    used for the reported area (that comes from the real ring below)."""
    side_m = math.sqrt(ha * 10000.0)
    lat_m_per_deg = 111320.0
    lon_m_per_deg = 111320.0 * math.cos(math.radians(lat_deg))
    return side_m / lat_m_per_deg, side_m / lon_m_per_deg


def geodesic_area_ha(poly):
    """Same spherical-area approach already used elsewhere in this repo
    (geoai_professional.js) -- good enough at field scale; not a UTM
    projection, consistent with the live Mera Khet feature's own area calc."""
    coords = list(poly.exterior.coords)
    R = 6371000.0
    area = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        area += math.radians(lon2 - lon1) * (2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    area = abs(area * R * R / 2.0)
    return area / 10000.0


def make_field(boundary, area_ha):
    """A small random quad clipped inside the boundary. Retries with a
    fresh random placement if the generated shape doesn't actually fall
    inside the real village (never falls back to a shape outside it)."""
    minx, miny, maxx, maxy = boundary.bounds
    for _ in range(200):
        lat0 = random.uniform(miny, maxy)
        lon0 = random.uniform(minx, maxx)
        dlat, dlon = ha_to_deg_side(area_ha, lat0)
        jitter = lambda v: v * random.uniform(0.85, 1.15)
        ring = [
            (lon0, lat0),
            (lon0 + jitter(dlon), lat0 + jitter(dlon * 0.15)),
            (lon0 + jitter(dlon) + jitter(dlon * 0.1), lat0 + jitter(dlat)),
            (lon0 + jitter(dlon * 0.1), lat0 + jitter(dlat) + jitter(dlat * 0.1)),
        ]
        from shapely.geometry import Polygon
        poly = Polygon(ring)
        if not poly.is_valid or poly.is_empty:
            continue
        if boundary.contains(poly):
            return poly
    return None  # honest failure -- caller skips this field rather than placing it wrong


def call_analyze(ring_latlon):
    body = {"ring": ring_latlon}
    try:
        r = requests.post(WORKER_ANALYZE_URL, json=body, timeout=60)
        return r.json()
    except Exception as e:
        return {"available": False, "reason": "generator_request_failed", "detail": str(e)[:200]}


def main():
    boundary, boundary_props = load_boundary()
    mp_climate = json.loads(open(MP_CLIMATE, encoding="utf-8").read())
    indore_climate = mp_climate.get("districts", {}).get("indore")

    soil_moisture = None
    if os.path.exists(SOIL_MOISTURE):
        soil_moisture = json.loads(open(SOIL_MOISTURE, encoding="utf-8").read()).get("district")

    soil_type = None
    if os.path.exists(SOIL_TYPE):
        soil_type = json.loads(open(SOIL_TYPE, encoding="utf-8").read()).get("district")

    field_sizes_ha = [round(random.uniform(0.4, 2.8), 2) for _ in range(N_FIELDS)]

    fields = []
    for i, target_ha in enumerate(field_sizes_ha):
        poly = make_field(boundary, target_ha)
        if poly is None:
            continue
        real_area_ha = round(geodesic_area_ha(poly), 3)
        # Worker's validateRing destructures each point as [lon, lat]
        # (cloudflare/mera_khet_worker.js line ~159) -- shapely's own
        # exterior.coords are already (x, y) = (lon, lat), so no swap.
        ring_for_worker = [[lon, lat] for lon, lat in poly.exterior.coords]

        print(f"[{i+1}/{len(field_sizes_ha)}] SYN-KHET-{i+1:03d}: calling live Mera Khet Worker "
              f"(real GEE query) for a {real_area_ha} ha field...")
        t0 = time.time()
        analysis = call_analyze(ring_for_worker)
        elapsed = time.time() - t0
        print(f"    -> available={analysis.get('available')} in {elapsed:.1f}s")

        cultivated_ha = None
        if analysis.get("available") and analysis.get("cropland_fraction") is not None:
            cultivated_ha = round(real_area_ha * analysis["cropland_fraction"], 3)

        fields.append({
            "id": f"SYN-KHET-{i+1:03d}",
            "label": f"Synthetic Field {i+1}",
            "synthetic": True,
            "village": boundary_props.get("village_name", "Simrol"),
            "district": "Indore", "state": "Madhya Pradesh",
            "geometry": mapping(poly),
            "zameen_ka_hisab": {
                "total_area_ha": real_area_ha,
                "cultivated_area_ha": cultivated_ha,
                "non_crop_area_ha": (round(real_area_ha - cultivated_ha, 3) if cultivated_ha is not None else None),
                "cropland_fraction_source": "live Dynamic World V1 classification via Mera Khet Worker /analyze"
                                             if analysis.get("available") else None,
            },
            "fasal_ki_sehat": {
                "ndvi_now": analysis.get("ndvi"),
                "source": analysis.get("source"),
                "note": "Single live satellite reading at generation time -- this proof-of-concept does "
                        "not compute a 6-month history (that needs repeated live GEE calls per field, "
                        "out of scope for a demo of this size).",
            },
            "khet_wetness": {
                "relative_pct_vs_district": analysis.get("field_wetness_index_relative"),
                "detail": analysis.get("field_wetness_index_detail"),
                "caveat": analysis.get("field_wetness_index_caveat"),
            },
            "live_analysis_raw": analysis,
        })

    payload = {
        "metadata": {
            "title": "SYNTHETIC Mera Khet proof-of-concept -- field boundaries are fabricated, "
                     "placed inside a real village",
            "synthetic_data_notice": "SYNTHETIC: the field polygons and farmer labels on this page are "
                                      "fabricated for demonstration only -- no real farmer drew these. "
                                      "REAL: every NDVI, cropland-fraction and field-wetness number is a "
                                      "live satellite query via the same Mera Khet Worker a real farmer's "
                                      "drawn field would hit. District-level climate/soil figures are the "
                                      "same real files the live dashboard uses.",
            "boundary_source": "Survey of India village boundary via NWDP (vil_lgd 476504, Simrol, "
                               "Mhow block, Indore district) -- same file as crop_insurance_pilot's pilot",
            "generated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                         .strftime("%Y-%m-%d"),
            "n_fields": len(fields),
        },
        "district_context": {
            "climate_imd": indore_climate,
            "soil_moisture_smap": soil_moisture,
            "soil_type_openlandmap": soil_type,
        },
        "fields": fields,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"\n[done] wrote {len(fields)} synthetic fields -> {OUT}")


if __name__ == "__main__":
    main()
