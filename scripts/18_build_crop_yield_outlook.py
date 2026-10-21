"""
18_build_crop_yield_outlook.py -- real, district-level crop yield outlook.

Owner asked for crop yield prediction. The ICRISAT panel already in this
repo (dashboard/data/crop_yield/icrisat_district_panel.json) stops at
2014-15 -- the real DES crop-stats files already in this repo
(dashboard/data/crop_stats_des_by_district/<state>/<district>.json) run to
2022-23 and are the more current real source, so this script uses those,
not ICRISAT.

Method, deliberately NOT a satellite/ML model: a deterministic OLS trend
on each district+crop+season's real yield_per_ha history, same
"deterministic OLS trend with residual-based uncertainty band, no random
noise" discipline already used by scripts/07_build_dicra_forecast.py for
forecast_2040.json and the groundwater trend in
scripts/16_fetch_groundwater.py. A real satellite/ML crop-type-and-yield
model is the literature-grounded design in docs/CROP_YIELD_METHODOLOGY.md
§3 -- genuinely blocked there on parcel-level ground truth (CCE/Digital
Crop Survey/UPAg), which this script does NOT attempt to work around.
This is a trend projection on real DISTRICT-level history, explicitly
labelled "indicative", never presented as a parcel-level or ML-validated
prediction.

Usage:
  python 18_build_crop_yield_outlook.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import config as C

SRC_DIR = C.PROJECT_ROOT / "dashboard" / "data" / "crop_stats_des_by_district"
OUT_DIR = C.PROJECT_ROOT / "dashboard" / "data" / "crop_yield_outlook"
MIN_REAL_YEARS = 5  # fewer than this and a trend line is not a meaningful statement


def parse_year_start(year_label: str) -> int | None:
    m = re.match(r"\s*(\d{4})", str(year_label))
    return int(m.group(1)) if m else None


def fit_trend(years: list[int], values: list[float]):
    years_a = np.array(years, dtype=float)
    vals_a = np.array(values, dtype=float)
    slope, intercept = np.polyfit(years_a, vals_a, 1)
    hist_pred = slope * years_a + intercept
    residuals = vals_a - hist_pred
    resid_std = float(np.std(residuals)) if len(residuals) > 2 else 0.0
    return float(slope), float(intercept), resid_std


def build_district_outlook(records: list[dict]) -> dict:
    # Note: every source record's own 'unit' field reads the constant
    # string "Area (Hectare)" regardless of crop (an upstream labelling
    # artifact describing area_ha, not yield_per_ha) -- not propagated
    # here since it would misdescribe the yield figure below.
    by_key: dict[tuple, list[tuple[int, float]]] = defaultdict(list)
    for r in records:
        y = parse_year_start(r.get("year"))
        yph = r.get("yield_per_ha")
        if y is None or yph is None:
            continue
        by_key[(r.get("crop"), r.get("season"))].append((y, float(yph)))

    crops_out = {}
    for (crop, season), points in by_key.items():
        points.sort(key=lambda p: p[0])
        years = [p[0] for p in points]
        values = [p[1] for p in points]
        unit = "bales/hectare" if re.search(r"cotton|jute", crop or "", re.I) else "tonnes/hectare"
        n = len(points)
        if n < MIN_REAL_YEARS:
            continue  # honest gap -- not enough real history for a trend statement
        slope, intercept, resid_std = fit_trend(years, values)
        next_year = years[-1] + 1
        next_val = float(slope * next_year + intercept)
        key = f"{crop}|{season}"
        crops_out[key] = {
            "crop": crop, "season": season, "unit": unit,
            "n_real_years": n, "year_range": [years[0], years[-1]],
            "yield_per_ha_mean": round(float(np.mean(values)), 3),
            "yield_per_ha_stddev": round(float(np.std(values)), 3),
            "trend_slope_per_year": round(slope, 4),
            "next_year": next_year,
            "next_year_yield_indicative": round(max(next_val, 0.0), 3),
            "next_year_yield_lo95": round(max(next_val - 1.96 * resid_std, 0.0), 3),
            "next_year_yield_hi95": round(next_val + 1.96 * resid_std, 3),
        }
    return crops_out


def main():
    if not SRC_DIR.exists():
        raise SystemExit(f"{SRC_DIR} not found")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_districts = 0
    n_crop_series = 0
    for state_dir in sorted(SRC_DIR.iterdir()):
        if not state_dir.is_dir():
            continue
        out_state_dir = OUT_DIR / state_dir.name
        out_state_dir.mkdir(parents=True, exist_ok=True)
        for f in sorted(state_dir.glob("*.json")):
            src = json.loads(f.read_text())
            records = src.get("records") or []
            crops_out = build_district_outlook(records)
            if not crops_out:
                continue
            payload = {
                "metadata": {
                    "source": "Directorate of Economics and Statistics (DES), Dept. of Agriculture "
                              "and Farmers Welfare, data.desagri.gov.in -- same real district-wise "
                              "crop APY records already in dashboard/data/crop_stats_des_by_district/, "
                              "re-aggregated here, no new fetch.",
                    "state": src.get("metadata", {}).get("state"),
                    "district": src.get("metadata", {}).get("district"),
                    "method": "Deterministic OLS trend (numpy.polyfit, degree 1) on each crop+season's "
                              "real yield_per_ha history across all available DES years -- NOT a "
                              "satellite/ML prediction (docs/CROP_YIELD_METHODOLOGY.md's literature-"
                              "grounded parcel-level model remains blocked on ground truth, see its "
                              "§7). next_year_yield_indicative is the trend line's value one year "
                              "past the last real DES year; _lo95/_hi95 is a 95% band from the real "
                              "residual standard deviation, no random noise injected. Minimum "
                              f"{MIN_REAL_YEARS} real years required per crop+season or it is omitted.",
                    "data_quality": "Indicative trend derived from verified-official real history -- "
                                    "not independently validated against a held-out year, not a "
                                    "substitute for an official crop forecast.",
                    "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                },
                "crops": crops_out,
            }
            out_path = out_state_dir / f.name
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
            n_districts += 1
            n_crop_series += len(crops_out)

    manifest = {
        "metadata": {
            "note": "Which state/district slugs have a real "
                    "dashboard/data/crop_yield_outlook/<state>/<district>.json file -- generated by "
                    "scripts/18_build_crop_yield_outlook.py, never hand-edited.",
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        "districts": [f"{p.parent.name}/{p.stem}" for p in sorted(OUT_DIR.glob("*/*.json"))],
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"[done] {n_districts} districts, {n_crop_series} crop+season trend series written")


if __name__ == "__main__":
    main()
