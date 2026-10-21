"""
17_gee_national_soil_type.py -- real national soil-type coverage.

Owner request (2026-10-21): soil type should be real data, like climate/
NDVI/soil-moisture already are. Checked and rejected first, per this
repo's own "verify against the real source before writing any extraction
code" convention (see 08_/13_'s headers for why that step matters):

  - Soil Health Card portal (soilhealth.dac.gov.in): no public bulk API.
    data.gov.in's own listing for this dataset says the same -- a request
    can be submitted, none exists today.
  - ICAR-NBSS&LUP's BHOOMI Geoportal (bhoomigeoportal-nbsslup.in): hosts
    real district-level soil texture/type layers, but no documented WMS/
    WFS/REST endpoint or bulk export on the portal. Same class of gap as
    the cadastral map (docs/PANEL_SOURCE_AUDIT.md) -- an institutional
    data-sharing request, not a fetch-script problem.

  - OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02 -- CHOSEN. Confirmed
    live in the real GEE catalog 2026-10-21 (ee.Image(...).bandNames()
    returned b0/b10/b30/b60/b100/b200), queryable with the same service
    account already used for climate/NDVI/soil moisture. This is a real,
    public, global 250m statistical soil map (ISRIC/OpenLandMap), NOT an
    India-specific ground survey like Soil Health Card -- every output
    file's metadata says so explicitly (scripts/config.py
    SOIL_TYPE_SOURCE_META), never presented as equivalent to one.

Method: texture CLASS is categorical (12 USDA classes, see
config.SOIL_TEXTURE_CLASSES) -- a class cannot be averaged, so the only
honest per-polygon reducer is ee.Reducer.mode() (the dominant class by
pixel count), never ee.Reducer.mean(). District tier: mode over the real
district polygon. Village tier: one batched sampleRegions() call per
district over that district's village centroids (not one GEE call per
village) -- matches this repo's existing VILLAGE_SAMPLE_METHOD=
"centroid" convention (scripts/config.py), since OpenLandMap's 250m pixel
is finer than most villages anyway. No block tier this pass (honest gap,
not fabricated from the village data -- see metadata.block_tier_note).

Usage:
  python 17_gee_national_soil_type.py --stage validate
  python 17_gee_national_soil_type.py --stage run --states Goa --resume
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import ee
import geopandas as gpd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import config as C

HEARTBEAT_PATH = Path(__file__).resolve().parent.parent / "logs" / "gee_soil_type_heartbeat.json"
GEE_REQUEST_DEADLINE_MS = 90_000  # same fix as 08_/13_'s gee_init() -- ee.data's default deadline is 0 (unlimited)


def write_heartbeat(event: str, state_name: str | None = None, district_name: str | None = None,
                     total_written: int | None = None, detail: str | None = None) -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.write_text(json.dumps({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event, "state": state_name, "district": district_name,
        "total_written_this_run": total_written, "detail": detail,
        "pid": __import__("os").getpid(),
    }, indent=1))


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def gee_init():
    if not C.GEE_SERVICE_ACCOUNT_KEY_PATH:
        raise SystemExit("GEE_SERVICE_ACCOUNT_JSON must be set -- see scripts/config.py.")
    key_path = Path(C.GEE_SERVICE_ACCOUNT_KEY_PATH)
    if not key_path.exists():
        raise SystemExit(f"GEE service account key not found at {key_path}")
    key_info = json.loads(key_path.read_text())
    client_email = key_info.get("client_email")
    if not client_email:
        raise SystemExit(f"{key_path} has no client_email field -- not a valid service account key")
    creds = ee.ServiceAccountCredentials(client_email, str(key_path))
    ee.Initialize(creds, project=C.GEE_PROJECT_ID or key_info.get("project_id"))
    ee.data.setDeadline(GEE_REQUEST_DEADLINE_MS)


def soil_image() -> ee.Image:
    return ee.Image(C.SOIL_TEXTURE_COLLECTION_IMAGE).select([C.SOIL_TEXTURE_BAND])


def stage_validate():
    print("=== VALIDATE (soil type) ===")
    gee_init()
    print("[ok] authenticated to Earth Engine")

    img = soil_image()
    band_names = img.bandNames().getInfo()
    print(f"[ok] {C.SOIL_TEXTURE_COLLECTION_IMAGE} real band: {band_names}")
    assert C.SOIL_TEXTURE_BAND in band_names, "surface texture band missing -- dataset choice needs re-checking"

    gdf = gpd.read_file(C.ensure_local_boundary_file('soi/districts.geojson'))
    row = gdf[(gdf["state_name"].str.upper() == "GOA") & (gdf["district_name"] == "North Goa")]
    if row.empty:
        row = gdf.iloc[[0]]
    geom = ee.Geometry(row.geometry.iloc[0].__geo_interface__)

    t0 = time.time()
    result = district_mode(geom)
    elapsed = time.time() - t0
    print(f"[ok] district mode class = {result} in {elapsed:.2f}s")
    print(f"     extrapolated: ~733 districts x {elapsed:.1f}s ~= {elapsed * 733 / 60:.1f} min of GEE time "
          f"(district tier only, excludes village sampling)")


def class_name(class_id) -> str | None:
    if class_id is None:
        return None
    try:
        return C.SOIL_TEXTURE_CLASSES.get(int(class_id))
    except (TypeError, ValueError):
        return None


def district_mode(geom: ee.Geometry) -> dict | None:
    """Real pixel histogram over the district polygon (ee.Reducer.mode()
    picks the dominant class; ee.Reducer.frequencyHistogram() alongside
    it so the full real distribution is kept, not just the winner)."""
    img = soil_image()
    stats = img.reduceRegion(
        reducer=ee.Reducer.mode().combine(ee.Reducer.frequencyHistogram(), sharedInputs=True),
        geometry=geom, scale=C.SOIL_TEXTURE_SCALE_METERS, maxPixels=1e9, bestEffort=True,
    ).getInfo()
    mode_val = stats.get(f"{C.SOIL_TEXTURE_BAND}_mode")
    hist = stats.get(f"{C.SOIL_TEXTURE_BAND}_histogram") or {}
    if mode_val is None or not hist:
        return None  # genuinely no real pixel covers this polygon -- caller writes nothing
    return {
        "dominant_class_id": int(mode_val),
        "dominant_class": class_name(mode_val),
        "class_pixel_counts": {class_name(int(k)) or k: int(v) for k, v in hist.items()},
        "n_pixels": int(sum(hist.values())),
    }


def sample_villages(img: ee.Image, vgdf) -> list[dict]:
    """ONE batched sampleRegions() call for every village centroid in the
    district -- not one GEE call per village (same principle as 13_'s
    village-to-cell assignment)."""
    feats = []
    idx_map = {}
    for i, row in vgdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        c = geom.centroid
        feats.append(ee.Feature(ee.Geometry.Point([c.x, c.y]), {"idx": int(i)}))
        idx_map[int(i)] = row
    if not feats:
        return []
    fc = ee.FeatureCollection(feats)
    sampled = img.sampleRegions(collection=fc, scale=C.SOIL_TEXTURE_SCALE_METERS,
                                 geometries=False).getInfo().get("features", [])
    out = []
    for f in sampled:
        props = f["properties"]
        idx = props.get("idx")
        cls = props.get(C.SOIL_TEXTURE_BAND)
        row = idx_map.get(idx)
        if row is None or cls is None:
            continue
        out.append({
            "vil_lgd": row.get("vil_lgd"), "village_name": row.get("village_name"),
            "sdcode": row.get("sdcode"), "class_id": int(cls), "class": class_name(cls),
        })
    return out


def build_district_payload(state_name: str, district_name: str, district_lgd, state_slug: str, dslug: str,
                            geom: ee.Geometry) -> dict | None:
    district_result = district_mode(geom)
    if district_result is None:
        return None  # no real coverage -- per "no fabrication", caller writes nothing

    payload = {
        "metadata": {
            **C.SOIL_TYPE_SOURCE_META,
            "state": state_name, "district": district_name,
            "district_lgd": int(district_lgd) if district_lgd == district_lgd and district_lgd is not None else None,
            "data_quality": "verified-official (real OpenLandMap/ISRIC dataset, GEE-computed)",
            "block_tier_note": "Not computed this pass -- honest gap, not derived/guessed from the "
                                "village data below.",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        "district": district_result,
        "villages": {}, "village_count_total": 0, "village_count_sampled": 0,
    }

    try:
        vpath = C.ensure_local_boundary_file(f"soi/villages/{state_slug}/{dslug}.geojson")
        vgdf = gpd.read_file(vpath)
        if vgdf.crs and vgdf.crs.to_epsg() != 4326:
            vgdf = vgdf.to_crs(4326)
    except Exception as e:
        payload["metadata"]["village_boundary_coverage"] = f"unavailable ({e})"
        return payload

    payload["village_count_total"] = len(vgdf)
    sampled = sample_villages(soil_image(), vgdf)
    payload["village_count_sampled"] = len(sampled)
    payload["metadata"]["village_boundary_coverage"] = "full" if len(sampled) == len(vgdf) else \
        f"partial ({len(sampled)}/{len(vgdf)} villages had a usable centroid + real pixel)"

    villages_out = {}
    for v in sampled:
        key = str(int(v["vil_lgd"])) if v["vil_lgd"] is not None else None
        if key is None:
            continue
        villages_out[key] = [v["village_name"], v["sdcode"], v["class_id"], v["class"]]
    payload["villages"] = villages_out

    return payload


def write_manifest():
    out_dir = C.NATIONAL_SOIL_TYPE_OUT_DIR
    if not out_dir.exists():
        return
    districts = []
    for state_dir in sorted(out_dir.iterdir()):
        if not state_dir.is_dir():
            continue
        for f in sorted(state_dir.glob("*.json")):
            districts.append(f"{state_dir.name}/{f.stem}")
    manifest = {
        "metadata": {
            "note": "Which state/district slugs have a real dashboard/data/soil_type/<state>/<district>.json "
                    "file -- generated by scripts/17_gee_national_soil_type.py, never hand-edited.",
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        "districts": districts,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"[manifest] {len(districts)} districts with real soil-type data")


def stage_run(states: list[str] | None, resume: bool):
    print("=== RUN (GEE national soil type) ===")
    gee_init()
    write_heartbeat("run_started", detail=f"deadline={GEE_REQUEST_DEADLINE_MS}ms, resume={resume}")

    gdf = gpd.read_file(C.ensure_local_boundary_file('soi/districts.geojson'))
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    if states:
        gdf = gdf[gdf["state_name"].str.upper().isin([s.upper() for s in states])]
    if gdf.empty:
        print("  no matching districts found for", states)
        return

    total_written = 0
    consecutive_quota_errors = 0
    for state_name, state_group in gdf.groupby("state_name"):
        state_slug = slugify(state_name)
        out_dir = C.NATIONAL_SOIL_TYPE_OUT_DIR / state_slug
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"-- {state_name} ({len(state_group)} districts) --")

        for _, row in state_group.iterrows():
            district_name = row["district_name"]
            dslug = slugify(district_name)
            out_path = out_dir / f"{dslug}.json"

            if resume and out_path.exists():
                print(f"  {district_name}: skipped -- already computed (--resume)")
                write_heartbeat("skipped_district", state_name, district_name, total_written, "already computed")
                continue

            write_heartbeat("started_district", state_name, district_name, total_written)
            t0 = time.time()
            try:
                geom = ee.Geometry(row.geometry.__geo_interface__)
                payload = build_district_payload(state_name, district_name, row.get("district_lgd"),
                                                   state_slug, dslug, geom)
                consecutive_quota_errors = 0
            except Exception as e:
                msg = str(e)
                print(f"  {district_name}: [ERROR] {msg[:300]}")
                write_heartbeat("error_district", state_name, district_name, total_written, msg[:300])
                if "quota" in msg.lower() or "rate limit" in msg.lower() or "429" in msg:
                    consecutive_quota_errors += 1
                    if consecutive_quota_errors >= 3:
                        print("  [STOP] 3 consecutive quota/rate-limit errors -- stopping run.")
                        write_heartbeat("stopped_quota", state_name, district_name, total_written,
                                         "3 consecutive quota errors")
                        write_manifest()
                        return
                continue

            if payload is None:
                print(f"  {district_name}: [WARN] no real pixel covers this district's geometry -- "
                      f"not writing a fabricated/substituted result")
                write_heartbeat("no_coverage", state_name, district_name, total_written, "0 pixels")
                continue

            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
            elapsed = time.time() - t0
            total_written += 1
            print(f"  {district_name}: wrote {out_path.name} in {elapsed:.1f}s "
                  f"(dominant={payload['district']['dominant_class']}, "
                  f"{payload['village_count_sampled']}/{payload['village_count_total']} villages)")
            write_heartbeat("done_district", state_name, district_name, total_written, f"{elapsed:.1f}s")

    write_manifest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["validate", "run"])
    ap.add_argument("--states", help="comma-separated state display names, e.g. 'Goa,Delhi'")
    ap.add_argument("--resume", action="store_true", help="skip districts whose output JSON already exists")
    args = ap.parse_args()

    if args.stage == "validate":
        stage_validate()
    elif args.stage == "run":
        states = [s.strip() for s in args.states.split(",")] if args.states else None
        stage_run(states, args.resume)


if __name__ == "__main__":
    main()
