"""
config.py — MP Climate Intelligence pipeline (5 major districts).
"""
import os
from pathlib import Path

# ---------- INPUT DATA PATHS ----------
# Set via environment variables (see .env.example). Defaults assume ./data.
_ROOT = Path(__file__).resolve().parent.parent
TMAX_DIR   = Path(os.environ.get("IMD_TMAX_DIR",   _ROOT / "data" / "imd" / "tmax"))
TMIN_DIR   = Path(os.environ.get("IMD_TMIN_DIR",   _ROOT / "data" / "imd" / "tmin"))
PRECIP_DIR = Path(os.environ.get("IMD_PRECIP_DIR", _ROOT / "data" / "imd" / "precip"))

TMAX_FILE_PATTERN   = "INDmet_tmax_05km_{year}.nc"
TMIN_FILE_PATTERN   = "INDmet_tmin_05km_{year}.nc"
PRECIP_FILE_PATTERN = "INDmet_precipitation_05km_{year}.nc"

MP_SHAPEFILE = Path(os.environ.get("MP_VILLAGE_SHAPEFILE", _ROOT / "data" / "boundaries" / "MADHYA_PRADESH.shp"))

YEAR_START = 2000
YEAR_END   = 2024

# ---------- TARGET DISTRICTS (centroids from the dashboard HTML) ----------
# key, display name, lat, lng — these MUST match the keys in MP_DISTRICTS in U.html
DISTRICTS = {
    "bhopal":   {"name": "Bhopal",   "lat": 23.2600, "lng": 77.4130},
    "indore":   {"name": "Indore",   "lat": 22.7196, "lng": 75.8577},
    "jabalpur": {"name": "Jabalpur", "lat": 23.1810, "lng": 79.9860},
    "rewa":     {"name": "Rewa",     "lat": 24.5310, "lng": 81.2970},
    "sidhi":    {"name": "Sidhi",    "lat": 24.4180, "lng": 81.8810},
}

# Spatial sample radius around the centroid (degrees). 0.1 deg ~ 11 km ~ 5x5 pixels.
SAMPLE_HALF_BOX_DEG = 0.10

# ---------- OUTPUT PATHS ----------
PROJECT_ROOT       = Path(__file__).resolve().parent.parent
OUTPUT_DIR         = PROJECT_ROOT / "outputs"
CACHE_DIR          = OUTPUT_DIR / "cache"
DASHBOARD_DATA_DIR = PROJECT_ROOT / "dashboard" / "data"
for d in (OUTPUT_DIR, CACHE_DIR, DASHBOARD_DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------- NETCDF AUTO-DETECT ----------
TMAX_VAR_CANDIDATES   = ["tmax", "TMAX", "temperature", "max_temp", "t_max", "Tmax"]
TMIN_VAR_CANDIDATES   = ["tmin", "TMIN", "min_temp", "t_min", "Tmin"]
PRECIP_VAR_CANDIDATES = ["rain", "rainfall", "precip", "precipitation", "PRECIP", "RAIN", "RAINFALL"]
LAT_CANDIDATES        = ["lat", "latitude", "LATITUDE", "y", "LAT"]
LON_CANDIDATES        = ["lon", "longitude", "LONGITUDE", "x", "LON"]
TIME_CANDIDATES       = ["time", "TIME", "t"]

# ---------- HEATWAVE THRESHOLDS (IMD, plains) ----------
HW_TMAX_ABS_THRESHOLD = 40.0
HW_TMAX_SEVERE        = 45.0
HW_DEPARTURE_MILD     = 4.5
HW_DEPARTURE_SEVERE   = 6.5
HW_MIN_CONSEC_DAYS    = 2
HW_SEASON_MONTHS      = (3, 4, 5, 6)

# ---------- DROUGHT (SPI) ----------
SPI_TIMESCALES        = [3, 6, 12]
DROUGHT_SPI_THRESHOLD = -1.0          # moderate drought
SEVERE_DROUGHT_SPI    = -1.5

# ---------- EXTREME PRECIP (ETCCDI) ----------
EXT_PRECIP_PERCENTILES = [95, 99]
WET_DAY_THRESHOLD_MM   = 1.0
# Fixed base period for percentile thresholds (ETCCDI requires a stable
# reference period; with a 2000-2024 record we use the first 15 years).
EXT_PRECIP_BASE_PERIOD = (2000, 2014)

# ---------- SPATIAL SAMPLING ----------
# "centroid"  : nearest IMD pixel at village centroid (fast; adequate when
#               the village is smaller than one 5.5 km pixel).
# "polygon"   : area-weighted mean of all pixels intersecting the village
#               polygon (preferred for large villages and for districts;
#               requires geopandas + the village shapefile).
VILLAGE_SAMPLE_METHOD = "centroid"

# ---------- GEE CMIP6 ----------
GEE_PROJECT_ID     = os.environ.get("GEE_PROJECT_ID", "")
FUTURE_TARGET_YEAR = 2040
FUTURE_WINDOW      = (2036, 2045)
HISTORICAL_BASELINE_WINDOW = (2000, 2014)
CMIP6_MODELS = [
    "ACCESS-CM2", "CMCC-ESM2", "EC-Earth3", "GFDL-ESM4",
    "INM-CM5-0", "MPI-ESM1-2-HR", "MRI-ESM2-0", "NorESM2-MM",
]
CMIP6_SCENARIO = "ssp245"

# ---------- GEE NATIONAL CLIMATE (Phase 3) ----------
# No raw IMD NetCDF exists on this machine (verified 2026-08-02, see
# scripts/08_gee_national_climate.py's header) -- the owner authorized
# using Google Earth Engine's ERA5-Land (temperature) and CHIRPS
# (precipitation) as the data source for districts beyond the original 5
# MP districts (which stay on their existing IMD-derived numbers,
# untouched). This is a genuinely different, real, freely-published
# dataset -- not a substitute invented to fill a gap -- and every output
# file's metadata says so explicitly; it is never presented as IMD data.
# GEE_SERVICE_ACCOUNT_JSON: path to the service account key file itself
# (its client_email is read directly from the file -- a key file already
# states its own email, so there is no separate email var to keep in sync).
GEE_SERVICE_ACCOUNT_KEY_PATH = os.path.expanduser(
    os.environ.get("GEE_SERVICE_ACCOUNT_JSON", "")
)

ERA5LAND_COLLECTION = "ECMWF/ERA5_LAND/DAILY_AGGR"
ERA5LAND_TMAX_BAND   = "temperature_2m_max"
ERA5LAND_TMIN_BAND   = "temperature_2m_min"
CHIRPS_COLLECTION   = "UCSB-CHG/CHIRPS/DAILY"
CHIRPS_PRECIP_BAND  = "precipitation"
GEE_SCALE_METERS    = 9000  # ERA5-Land native resolution (~9 km)

NATIONAL_CLIMATE_OUT_DIR = PROJECT_ROOT / "dashboard" / "data" / "climate"
SOI_DISTRICTS_GEOJSON    = PROJECT_ROOT / "dashboard" / "data" / "boundaries" / "soi" / "districts.geojson"
# 2026-08-06's Hugging Face migration removed this file (and the rest of
# boundaries/soi/) from the git working tree -- the dashboard fetches it
# from HF at runtime via resolveDataUrl(), but local pipeline scripts
# (this file's SOI_DISTRICTS_GEOJSON consumers, e.g.
# 08_gee_national_climate.py, need the real geometry, not just the
# properties-only districts_index.json) still need an actual file on
# disk. Rather than every script re-implementing its own "if missing,
# download" check (and risk one of them forgetting it, like
# 08_gee_national_climate.py did on 2026-08-07 -- see its own history),
# this caches a copy under a gitignored local path the first time any
# script asks for it.
_SOI_BOUNDARY_CACHE_DIR = PROJECT_ROOT / ".cache" / "boundaries"


def ensure_local_boundary_file(relative_path: str) -> Path:
    """Returns a local Path to boundaries/soi/<relative_path>, downloading
    it from Hugging Face into a gitignored cache dir on first use if it
    isn't already present in the working tree (dashboard/data/boundaries/)
    or the cache. Real HTTP fetch, real file -- no synthetic fallback; a
    failed download raises rather than silently returning nothing."""
    working_tree_path = PROJECT_ROOT / "dashboard" / "data" / "boundaries" / relative_path
    if working_tree_path.exists():
        return working_tree_path
    cache_path = _SOI_BOUNDARY_CACHE_DIR / relative_path
    if cache_path.exists():
        return cache_path
    import json as _json
    import urllib.request as _urlreq
    data_config = _json.loads((PROJECT_ROOT / "dashboard" / "config" / "data_config.json").read_text())
    url = data_config["DATA_BASE_URL"].rstrip("/") + "/boundaries/" + relative_path
    print(f"[config] {relative_path} not found locally -- downloading from {url} "
          f"(caching at {cache_path}, gitignored)")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    req = _urlreq.Request(url, headers={"User-Agent": "vindhya-climate-portal/1.0"})
    with _urlreq.urlopen(req, timeout=180) as r:
        cache_path.write_bytes(r.read())
    return cache_path

GEE_SOURCE_META = {
    "source": "ERA5-Land (ECMWF, via Google Earth Engine) for Tmax/Tmin, "
              "CHIRPS (UCSB Climate Hazards Center, via Google Earth Engine) for precipitation",
    # ERA5-Land's own documented native grid spacing is 9km (0.1 deg) --
    # Muñoz-Sabater et al. 2021, the dataset's own reference paper. Not
    # "11 km": that number would be 0.1 deg of pure latitude with no
    # correction, not ERA5-Land's actual published resolution.
    "resolution": "ERA5-Land ~9 km (0.1 deg) native grid, CHIRPS ~5.5 km (0.05 deg) -- "
                  "both far coarser than a village (~2 sq km): a district's indices "
                  "here are ONE value per pixel-day within the district polygon "
                  "(GEE reduceRegion mean), not a village-resolved product. See "
                  "docs/METHODOLOGY.md Sec 3.1 (modifiable areal unit problem).",
    "method": "Heatwave: IMD plains criteria (Tmax departure from normal >=4.5C mild / "
              ">=6.5C severe, March-June season, scripts/config.py HW_DEPARTURE_MILD/"
              "SEVERE). SPI: McKee et al. 1993, 3/6/12-month timescales with the "
              "zero-inflated gamma correction for zero-rainfall periods, moderate-drought "
              "threshold SPI<=-1.0. ETCCDI: standard extreme-precipitation indices "
              "(R95p/R99p/Rx1day/Rx5day/CDD/CWD) at 95th/99th percentile thresholds. "
              "Identical formulas to scripts/02_compute_indices.py (imported directly "
              "by 08_gee_national_climate.py, never reimplemented) -- only the input "
              "grid (ERA5-Land/CHIRPS here, IMD 0.05 deg for the 5 original MP "
              "districts) differs. See docs/METHODOLOGY.md for the exact formulas.",
    "baseline": "2000-2014 (ETCCDI percentile base period and historical baseline "
               "window, scripts/config.py EXT_PRECIP_BASE_PERIOD / "
               "HISTORICAL_BASELINE_WINDOW)",
    "note": "Distinct from the IMD 0.05 deg gridded product used for Bhopal, "
            "Indore, Jabalpur, Rewa and Sidhi -- those 5 districts are untouched "
            "by this pipeline and keep their existing IMD-derived numbers. Used "
            "here because no raw IMD NetCDF file is available on this machine "
            "(verified before this pipeline was written); same heatwave/SPI/"
            "ETCCDI methodology as the IMD pipeline, applied to a different "
            "real, freely-published reanalysis/satellite source.",
}

# ---------- GEE NATIONAL NDVI (Phase 8.4) ----------
# MOD13Q1 v061: MODIS Terra Vegetation Indices, 16-day composite, 250m --
# real satellite product, freely published, distinct from
# dashboard/data/dicra_ndvi.json's UNDP DiCRA MODIS-derived district
# statistic (that file stays MP-only and untouched; this is an ADDITIONAL
# national layer, never merged into it -- see scripts/10_gee_national_ndvi.py).
MODIS_NDVI_COLLECTION = "MODIS/061/MOD13Q1"
MODIS_NDVI_BAND       = "NDVI"
MODIS_NDVI_SCALE_FACTOR = 0.0001   # MOD13Q1's own documented scale factor
MODIS_NDVI_SCALE_METERS = 250      # MOD13Q1 native pixel size
NATIONAL_NDVI_OUT_DIR = PROJECT_ROOT / "dashboard" / "data" / "ndvi"
# MOD13Q1 record starts 2000-02-18; use the same YEAR_START/YEAR_END span as
# the climate pipeline for a full calendar-year loop, first partial year
# handled naturally by filterDate() returning fewer images for 2000.
NDVI_YEAR_START = 2000
NDVI_YEAR_END   = 2024

# ---------- GEE NATIONAL SOIL MOISTURE (MERA_KHET_PROMPT.md B1) ----------
# NASA/SMAP/SPL4SMGP/008 -- SMAP L4 Global 3-hourly 9km Surface and Root
# Zone Soil Moisture. Chosen over the two alternatives after checking both
# directly against the real GEE catalog (2026-08, see
# scripts/13_gee_national_soil_moisture.py's header for how):
#   - NASA_USDA/HSL/SMAP10KM_soil_moisture: REJECTED -- its own catalog
#     page states data collection ENDED August 2022. Stale for "should I
#     irrigate right now", which is the entire point of B1.
#   - NASA/SMAP/SPL4SMGP/007: superseded by /008 (both exist; /007 is
#     explicitly marked deprecated on its own catalog page).
#   - NASA/SMAP/SPL4SMGP/008: confirmed live/actively updating, band names
#     confirmed real (sm_surface, sm_rootzone) -- this is what's used.
SMAP_COLLECTION = "NASA/SMAP/SPL4SMGP/008"
SMAP_SURFACE_BAND  = "sm_surface"    # 0-5cm depth, volume fraction m3/m3 -- primary field
SMAP_ROOTZONE_BAND = "sm_rootzone"   # 0-100cm depth, volume fraction m3/m3 -- secondary/context only
# GEE reports this asset's pixel size as 11,000 m; SMAP's own EASE-Grid 2.0
# native spacing is documented as 9 km -- same "reported pixel size vs.
# documented native resolution" distinction already made for ERA5-Land
# above (GEE_SOURCE_META['resolution']). The owner's spec is explicit:
# state 9 km everywhere this data is shown.
SMAP_SCALE_METERS = 11000
SMAP_RESOLUTION_LABEL = "~9 km (SMAP EASE-Grid 2.0 native spacing; GEE reports an 11,000 m pixel size for this asset)"
# SMAP L4 has occasional per-image/per-pixel gaps; averaging the last 5
# days of 3-hourly images per pixel is still "current conditions" (not a
# long-term climatology) and is resilient to any single missing granule.
SMAP_LOOKBACK_DAYS = 5

NATIONAL_SOIL_MOISTURE_OUT_DIR = PROJECT_ROOT / "dashboard" / "data" / "soil_moisture"

SMAP_SOURCE_META = {
    "source": "NASA SMAP L4 Global 3-hourly 9km Surface and Root Zone Soil Moisture "
              "(NASA/SMAP/SPL4SMGP/008), via Google Earth Engine",
    "resolution": SMAP_RESOLUTION_LABEL,
    "band": "sm_surface (0-5cm depth, volume fraction m3/m3) -- primary field this pipeline "
           "reports. sm_rootzone (0-100cm depth, volume fraction m3/m3) carried alongside as "
           "secondary context, never the headline number.",
    "method": "Each district's real SMAP grid cells (few per district at 9km) are sampled "
              "directly via Earth Engine (ee.Image.sample over the district polygon -- each "
              "cell's own value AND location kept, not collapsed into one reduceRegion mean). "
              "Village tier: the SMAP cell nearest to the village polygon's centroid (nearest "
              "cell-center match). Block tier: mean + standard deviation of its villages' "
              "assigned cell values, N = village count. District tier: mean + standard "
              "deviation of the real SMAP cells sampled directly over the district polygon, "
              "N = cell count (independent of village-boundary coverage). State tier "
              "(computed client-side in the dashboard loader): mean + standard deviation of "
              "its districts' values, N = districts actually computed so far -- always shown "
              "against the state's real total district count.",
    "note": "Resolution is ~9 km -- one SMAP cell covers many villages. Village tier NEVER "
           "claims a village-specific value; it always shows the real count of villages "
           "sharing that cell. See MERA_KHET_PROMPT.md section B1.",
}

# ---------- GROUNDWATER (National Water Data Portal / CGWB) ----------
# PENDING.md item 4 was closed as a dead end on 2026-08-09 after checking
# india-wris.gov.in (Angular shell, no JSON API), gwdata.cgwb.gov.in
# (maintenance mode, form-driven), cgwb.gov.in (PDF reports only) and
# data.gov.in (no CGWB groundwater-level resource_id found). Found and
# verified working 2026-08-19: nwdp.nwic.gov.in (the SAME Survey-of-India-
# adjacent government portal this project already trusts for village
# boundaries, standing order #3) also publishes CGWB's own real quarterly
# manual groundwater-level readings as plain CSV, no login, no API key --
# see scripts/16_fetch_groundwater.py for the resource URL table and
# scraping method used to find it.
NATIONAL_GROUNDWATER_OUT_DIR = PROJECT_ROOT / "dashboard" / "data" / "groundwater"

GWL_SOURCE_META = {
    "source": "CGWB (Central Ground Water Board, Ministry of Jal Shakti) via the National "
              "Water Data Portal, nwdp.nwic.gov.in -- dataset 'Ground Water Level "
              "(Manual - Quarterly), CGWB'",
    "source_url": "https://nwdp.nwic.gov.in/dataset/gwl-manual-quarterly-central-ground-water-board-department",
    "resolution": "Station points (CGWB manual quarterly monitoring wells/piezometers), "
                  "aggregated to district by joining each row's own 'District LGD Code' "
                  "field against this project's own Survey-of-India district_lgd (see "
                  "dashboard/data/boundaries/soi/districts_index.json) -- not a name match, "
                  "so it does not inherit the AGMARKNET-style spelling-mismatch problem "
                  "documented in scripts/fetch_mandi_prices.py.",
    "unit": "meters (depth to water level below ground level, 'mbgl' -- the NWDP dataset's "
           "own notes text says only 'GWL values in meter (m)'; the mbgl-below-ground "
           "convention is CGWB's own standard reporting convention for this series and was "
           "cross-checked for plausibility against known real MP readings, see "
           "scripts/16_fetch_groundwater.py header)",
    "method": "Real CSV rows only -- no interpolation, no carrying forward. Per district: "
              "latest reading = the row with the maximum parsed Data Acquisition Time; "
              "trend = a plain OLS slope (same 'indicative OLS trend on real history' style "
              "as forecast_2040.json) fit on every station-district's numeric quarterly "
              "series across both the 1991-2020 and 2021-2025 (and 2026-2030 where present) "
              "CSV slices, only when enough real points exist -- never a projection dressed "
              "as an observation.",
    "data_quality": "verified-official (real CGWB dataset, government portal, no login)",
}

# ---------- GEE NATIONAL SOIL TYPE (2026-10-21) ----------
# Owner asked for real national soil-type coverage. Checked first, per this
# repo's convention: Soil Health Card portal (soilhealth.dac.gov.in) and
# data.gov.in -- data.gov.in's own page states no API exists for this
# dataset (can only submit a request). ICAR-NBSS&LUP's BHOOMI Geoportal
# (bhoomigeoportal-nbsslup.in) hosts real district-level soil texture/type
# layers but exposes no documented WMS/WFS/REST endpoint or bulk export --
# same "institutional request needed, not a fetch-script problem" class as
# the cadastral gap in docs/PANEL_SOURCE_AUDIT.md. Neither is usable here.
#
# OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02 -- CHOSEN instead: a real,
# public, global 250m soil-texture-class raster (ISRIC/OpenLandMap, 1950-2018
# training period), confirmed live in the GEE catalog and queryable with the
# same service-account credentials already used for climate/NDVI/soil
# moisture. This is coarser-provenance than an Indian government ground
# survey would be (global model, not India-specific field sampling) -- every
# output file's metadata says so explicitly, never presented as a Soil
# Health Card equivalent.
SOIL_TEXTURE_COLLECTION_IMAGE = "OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02"
SOIL_TEXTURE_BAND = "b0"  # 0cm (surface) depth band; the asset also has b10/b30/b60/b100/b200
SOIL_TEXTURE_SCALE_METERS = 250
# Real USDA 12-class texture scheme this band's integer values encode --
# verified against the asset's own GEE catalog page (2026-10-21), not
# guessed from the class count alone.
SOIL_TEXTURE_CLASSES = {
    1: "Clay", 2: "Silty Clay", 3: "Sandy Clay", 4: "Clay Loam",
    5: "Silty Clay Loam", 6: "Sandy Clay Loam", 7: "Loam", 8: "Silty Loam",
    9: "Sandy Loam", 10: "Silt", 11: "Loamy Sand", 12: "Sand",
}

NATIONAL_SOIL_TYPE_OUT_DIR = PROJECT_ROOT / "dashboard" / "data" / "soil_type"

SOIL_TYPE_SOURCE_META = {
    "source": "OpenLandMap Soil Texture Class, USDA system (ISRIC World Soil Information / "
              "OpenLandMap project), via Google Earth Engine -- a global statistical soil map, "
              "NOT an India-specific ground survey (Soil Health Card / ICAR-NBSS&LUP have no "
              "public bulk API as of 2026-10-21 -- see scripts/config.py's header above for "
              "what was checked and rejected).",
    "resolution": "250 m native pixel, surface (0cm) depth band",
    "band": "b0 (0cm depth) of SOL_TEXTURE-CLASS_USDA-TT_M/v02 -- the asset also carries "
           "b10/b30/b60/b100/b200 (deeper soil layers), not used here; this pipeline reports "
           "surface texture only, matching what a farmer standing in the field would judge by hand.",
    "method": "Per district/block/village polygon: ee.Reducer.mode() over the real raster "
              "pixels inside that polygon (the dominant texture class by pixel count -- a "
              "categorical class cannot be averaged, so mode, not mean, is the only honest "
              "reducer). Village/block tiers computed in ONE batched ee.Image.reduceRegions() "
              "call per district over that district's whole village FeatureCollection, not one "
              "GEE call per village.",
    "classes": SOIL_TEXTURE_CLASSES,
    "data_quality": "verified-official (real OpenLandMap/ISRIC dataset, confirmed live in the "
                    "GEE catalog 2026-10-21) -- global model resolution, not a substitute for "
                    "an official in-field Soil Health Card test result.",
}
