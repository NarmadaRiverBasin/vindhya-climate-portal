# MP Climate Intelligence — Village-Level Climate Hazard Dashboard

Village and district-level heatwave, drought, and extreme precipitation
analytics for five Madhya Pradesh districts (Bhopal, Indore, Jabalpur, Rewa,
Sidhi), computed from IMD 0.05° gridded daily data (2000–2024), with UNDP
DiCRA NDVI and a CMIP6 (NEX-GDDP, SSP2-4.5) workflow for 2040 projections.

**Data policy: every displayed value is traceable to a verified source.**
Synthetic district, village, and cadastral records were removed in the
2026-08 cleanup. See `CONTRIBUTING.md` and `docs/DATA_SOURCES.md`.

## Repository layout

```
vindhya-climate-portal/
├── app.py                       Streamlit host (iframe + GitHub raw data)
├── requirements.txt             full pinned dependency set
├── .env.example                 data paths / keys (copy to .env)
├── scripts/                     reproducible pipeline
│   ├── config.py                env-driven paths, thresholds, base periods
│   ├── common.py                NetCDF loader + samplers
│   ├── 01_extract_village_timeseries.py   IMD daily series per village
│   ├── 02_compute_indices.py    heatwave / SPI / ETCCDI per village-year
│   ├── 02_finish.py             district rollup helper
│   ├── 03_build_chart_data.py   chart JSON
│   ├── 04_build_dashboard_json.py         dashboard payload
│   ├── 05_gee_cmip6_2040.js     Earth Engine CMIP6 export (paste into GEE)
│   ├── 06_convert_gee_export.py GEE CSV → dashboard JSON
│   ├── 07_build_dicra_forecast.py         DiCRA NDVI + OLS trend forecast
│   └── run_all.bat              Windows one-click runner
├── dashboard/
│   ├── index.html               single-page dashboard (Leaflet + Chart.js)
│   ├── mp_climate_loader.js     binds climate JSON
│   ├── dicra_ndvi_loader.js     NDVI charts
│   ├── cadastral_loader.js      stub — awaits MP Bhulekh official records
│   ├── india_boundaries_loader.js  all-India state/district overlays
│   └── data/                    verified JSON/GeoJSON payloads
├── tools/                       one-off inspection/debug scripts
├── tests/                       pytest unit tests for index math
├── docs/
│   ├── METHODOLOGY.md           index definitions and caveats
│   ├── DATA_SOURCES.md          provenance register for every layer
│   ├── REQUIREMENTS_ROADMAP.md  45-point requirements → implementation plan
│   └── DEPLOYMENT.md            hosting instructions
└── .github/workflows/ci.yml     syntax check + tests + synthetic-data guard
```

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env          # point IMD_* paths at your NetCDF folders
cd scripts && python 01_extract_village_timeseries.py
python 02_compute_indices.py && python 03_build_chart_data.py
python 04_build_dashboard_json.py
cd ../dashboard && python -m http.server 8000   # open localhost:8000
```

Windows: `scripts\run_all.bat`. Tests: `python -m pytest tests/`.

## What is computed

| Hazard | Indices | Definition |
|---|---|---|
| Heatwave | heatwave_days, severe_heatwave_days | IMD plains criteria: Tmax ≥ 40°C with departure ≥ 4.5°C (severe ≥ 6.5°C) or Tmax ≥ 45°C, runs ≥ 2 days, Mar–Jun |
| Drought | SPI-3/6/12, drought_months, drought_probability | McKee et al. (1993) gamma-fitted SPI |
| Extreme precipitation | R95p, R99p, Rx1day, Rx5day, CDD, CWD | ETCCDI; percentile thresholds from fixed 2000–2014 base period |
| Future | 2040 delta vs 2000–2014 baseline | 8-model CMIP6 NEX-GDDP ensemble, SSP2-4.5 (scripts 05–06) |

## Known limitations (stated deliberately)

1. Village values are nearest-pixel samples of a 5.5 km grid; most villages
   are smaller than one pixel. `VILLAGE_SAMPLE_METHOD = "polygon"` is the
   planned upgrade for polygon zonal means.
2. The 25-year record is below the WMO 30-year climate normal; SPI gamma
   fits use ≥ 15 samples per calendar month and are noisier than standard.
3. `forecast_2040.json` served to the dashboard is an OLS trend
   extrapolation labeled "indicative"; CMIP6 projections require running
   the GEE workflow.
4. Cadastral (khasra) parcels are disabled until official MP Bhulekh /
   Revenue Department records are integrated.

## License

MIT (code). IMD, DiCRA, Census boundary data retain provider licenses.
