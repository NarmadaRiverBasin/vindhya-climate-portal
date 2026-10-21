# Data Provenance Register

Every layer served by the dashboard is listed here with source, resolution,
CRS, processing, and quality status. Layers not listed must not be displayed.

## Hugging Face migration (2026-08-06)

`data/boundaries/soi/*` (650 MB) and `data/village_profiles/*` (102 MB) --
every row below whose "Layer / file" starts with either path -- were moved
off this repo's working tree to
[`vindhyaresearch/vindhya-climate`](https://huggingface.co/datasets/vindhyaresearch/vindhya-climate)
(public HF dataset repo, 10 GB free, CORS confirmed scoped to this site's
GitHub Pages origin, HTTP range requests supported). This repo's tracked
content was already ~760 MB against GitHub Pages' 1 GB soft limit before
these two folders were added; removing them (they were the two largest
contributors by far) brings the working tree back to a few MB.

**Nothing about the data itself changed** -- same files, same content,
same processing, same licence, verified file-for-file and byte-for-byte
identical (1510/1510 files, 784,203,871/784,203,871 bytes) before the local
copies were removed from the working tree. Only the host changed: every
loader reads `config/data_config.json`'s `DATA_BASE_URL` via
`resolveDataUrl()` (`dashboard/index.html`) instead of a hardcoded local
path. Full git history still has every file in every commit before the
removal -- `git checkout <commit> -- dashboard/data/boundaries
dashboard/data/village_profiles` recovers them; history was never rewritten
(no filter-branch/filter-repo/BFG) to remove them, so this is recoverable
by design, not a real loss.

| Layer / file | Source | Resolution | CRS | Processing | Quality | Updated |
|---|---|---|---|---|---|---|
| `data/mp_climate_data.json` (5 districts) | IMD 0.05° gridded daily Tmax/Tmin/Precip NetCDF, 2000–2024 | ~5.5 km | EPSG:4326 | scripts 01–04: nearest-pixel village sampling, IMD heatwave criteria, SPI, ETCCDI (base 2000–2014) | Verified | 2026-07-31 |
| `data/dicra_ndvi.json` (52 Madhya Pradesh districts only) | UNDP DiCRA district NDVI zonal statistics (MODIS-derived) | district zonal | EPSG:4326 | script 07 aggregation | Verified | 2026-07-31 |
| `data/forecast_2040.json` | OLS linear trend on observed 2000–2024 annual indices, 95% residual band | district | — | script 07 (deterministic, no injected noise) | Indicative | 2026-07-31 |
| `data/cmip6_2040/<state_slug>/<district_slug>.json` (**all 733 districts** — the authoritative CMIP6 layer) | NASA NEX-GDDP-CMIP6 (bias-corrected, statistically downscaled daily), 8-model ensemble (ACCESS-CM2, CMCC-ESM2, EC-Earth3, GFDL-ESM4, INM-CM5-0, MPI-ESM1-2-HR, MRI-ESM2-0, NorESM2-MM), SSP2-4.5, via Google Earth Engine | ~25 km (0.25°) native NEX-GDDP grid — coarser than most districts; **not valid at block or village scale** | EPSG:4326 | `scripts/09_gee_national_cmip6_2040.py`: `reduceRegions` (mean, 25 km scale) over each district's **real Survey of India polygon**, state-by-state, resumable. Future window 2036–2045 vs 2000–2014 historical baseline; delta computed locally from the two fetched dicts, not a third GEE call. Max-type indices (`max_summer_tmax`, `rx1day_mm`) are the **mean of the per-year maxima** (ETCCDI TXx/Rx1day), not the window maximum — see METHODOLOGY §5. `hot_days_tmax_ge40_per_yr` is a **hot-day count (Tmax ≥ 40 °C, Mar–Jun), NOT the IMD heatwave-event index** — see METHODOLOGY §5.1 | Verified — model scenario, never an observation | 2026-09-02 |
| `mp_climate_data.json` → `future_2040` (5 MP districts, via scripts 05b/06) — **SUPERSEDED, retained for provenance, no longer rendered** | Same NEX-GDDP-CMIP6 ensemble, scenario and windows as the row above | 0.25° | EPSG:4326 | `scripts/05b_run_cmip6_2040.py`: identical computation but reduced over a **5 km buffer around each district's centroid point** rather than its polygon. This project's first real CMIP6 result (2026-09-01). Superseded 2026-09-02 by the polygon-based national layer above, which measures the district rather than a disc near its middle and is the same spatial unit as every other district-level layer here. The two agree closely for the 5 overlapping districts (hot days within 0.4–3.6 d/yr, peak Tmax within 0.3 °C, annual rain within 6 %), so this is a refinement, not a contradiction — see METHODOLOGY §5.2. Each `future_2040` block carries its own `superseded_by` + `superseded_note` | Superseded | 2026-09-02 |
| `mp_districts/tehsils/blocks.geojson`, `data/villages_*.geojson` | MP-only boundary files, pre-national-selector | vector | EPSG:4326 | none | **Superseded, unreferenced** — replaced nationally by `data/boundaries/soi/*` below; files remain on disk (not deleted) but no dashboard code fetches them as of 2026-08-02 | 2026-08-02 |
| `data/boundaries/soi/states.geojson` (36 states/UTs) | Survey of India `state-boundary` product, hosted via National Water Data Portal (NWDP/NWIC, Ministry of Jal Shakti), free, no login | vector, simplified 0.0005° | EPSG:4326 (reprojected from source EPSG:7755) | script `build_national_soi_boundaries.py` --stage state: topology-preserving simplify (see below) | Verified-official | 2026-08-02 |
| `data/boundaries/soi/districts.geojson` (733 districts) | Survey of India `district-boundary` product, NWDP | vector, simplified 0.0005° | EPSG:4326 (reprojected from source EPSG:7755) | script `build_national_soi_boundaries.py` --stage district | Verified-official | 2026-08-02 |
| `data/boundaries/soi/blocks/<state_slug>.geojson` (36 states/UTs, 6,312 sub-districts) | Survey of India `sub-district-boundary` product, NWDP (SoI's own block/bkcode grouping has no separate boundary product — sdcode/subdistrict is the closest available match, treated as "Block/Tehsil" in this dashboard) | vector, simplified 0.0005° | EPSG:4326 (reprojected from source EPSG:7755) | script `build_national_soi_boundaries.py` --stage blocks | Verified-official | 2026-08-02 |
| `data/boundaries/soi/villages/<state_slug>/<district_slug>.geojson` (36 states/UTs, 654,285 villages) | Survey of India `village-boundary` product, NWDP — see `data/boundaries/README.md` "Source and a naming caveat" for the GSI/SoI attribution check | vector, simplified 0.0005° | EPSG:4326 (reprojected from source EPSG:7755) | script `build_national_soi_boundaries.py` --stage villages: topology-preserving simplify, 73→13 attribute columns | Verified-official, zero-overlap-verified | 2026-08-02 |
| `data/village_profiles/<state_slug>/<district_slug>.json` (36 states/UTs, 649,719 villages) | Survey of India village-boundary product's attribute table (same NWDP source/download as the boundary layer above), 46 of its 74 raw columns kept — population, households, drinking-water source status (tapwater/well/handpump/tubewell/spring/river/tank), drainage, land-use breakdown, irrigation area by source, nearest town | tabular, per village | not applicable | script `build_village_profiles.py`: positional-array encoding (field order recorded once per file's metadata) rather than repeated JSON keys — 654,285 villages at ~1 KB/village would have been ~665 MB, this form is 102 MB; a field blank in the source is omitted from that village, never defaulted | Verified-official | 2026-08-02 |
| `data/mandi_prices.json` (all 36 states/UTs, 733 districts) | AGMARKNET, published on data.gov.in by the Ministry of Agriculture and Farmers Welfare (resource `9ef84268-d588-465a-a308-a864a43d0070`) | APMC market, aggregated to district | not applicable (tabular) | `scripts/fetch_mandi_prices.py` on a daily GitHub Actions schedule, all 733 districts (from `national_districts.py`, the same Survey of India district layer used for boundaries — not a separately typed-in list) in one run; rows without a usable min/max/modal price, or with min above max, are dropped; nothing interpolated or carried forward; a district whose AGMARKNET spelling doesn't match its Survey of India name is a recorded per-district fetch failure, not a silent gap | Verified | daily |
| `data/crop_stats.json` (all 36 states/UTs, 733 districts) | data.gov.in, Ministry of Agriculture and Farmers Welfare, "District-wise, season-wise crop production statistics from 1997" (resource `35be999b-0208-4354-b557-f6ca9a5355de`) | district, season | not applicable (tabular) | `scripts/fetch_crop_stats.py`, monthly GitHub Actions schedule; this resource paginates and would take hours to fetch nationally in one run, so each scheduled run fetches one batch of 6 states (chosen by calendar month, all 36 cycle through over 6 months) and MERGES into the existing file rather than overwriting it; yield is derived (production/area) by this repo, never estimated when area is 0/missing | Verified, years generally 1997-2013 (varies by district) -- **not current-season data** | monthly, batched |
| `data/sources_manifest.json` | This register itself -- a machine-readable mirror of this table's distinct source rows, kept in sync by hand | not applicable | not applicable | hand-maintained; the landing page's "Verified Sources" stat counts this file's array length instead of a typed-in number | Self-referential | 2026-08-02 |
| `data/crop_yield/icrisat_district_panel.json` (20 states, 560 districts, 1990-2015) | ICRISAT District-Level Data: "Heterogeneous Climate Effect on Crop Yield and Associated Risks to Water Security in India" (Mohapatra, S. / ICRISAT), Mendeley Data, DOI `10.17632/ywp3y5j9vv.1`, CC BY 4.0 | district, annual | not applicable (tabular) | `scripts/crop_yield/01_fetch_icrisat_district_yield.py`: downloads the source's single `.xls` via Mendeley's public files API, verifies its SHA-256 against the API's own hash before parsing, keeps crop area/production/yield (rice, pearl millet, chickpea, groundnut, sugarcane) + irrigated/cropped area + fertiliser + labour + 4 seasonal (not 48 raw monthly) climate aggregates -- documented trim, raw `.xls` cached alongside (gitignored) for re-parsing | Verified-official, district-level -- **not parcel-level ground truth**, used per `docs/CROP_YIELD_METHODOLOGY.md` §4 as a regression target/sanity bound only | 2026-08-06 |
| `data/boundaries/soi/districts_index.json` (733 districts, state_name/district_name/district_lgd only, no geometry) | Same Survey of India source as `districts.geojson` (now HF-hosted, see `data/boundaries/README.md`) -- a properties-only extract of it | district | not applicable | `scripts/build_districts_index.py`: fetches the HF-hosted `districts.geojson`, drops geometry, keeps only the 3 identifying properties. Exists because `national_districts.py` (the shared district-name list every fetch script iterates) used to read `districts.geojson` directly and broke when that ~20MB file left the working tree in the 2026-08-06 HF migration -- this ~69KB file is small enough to check into git directly rather than adding a network fetch to every data-pull script | Verified-official (derived, not independently sourced) | 2026-08-07 |
| `data/crop_list.json` (59 crops) | Derived from `crop_stats.json`'s own crop labels (data.gov.in) | not applicable | not applicable | `scripts/build_crop_list.py`, hand-run when `crop_stats.json`'s crop set changes | Self-referential (derived) | 2026-08-07 |
| `data/ground_truth/<state_slug>/<district_slug>.json` -- **not live yet, 0 rows** | Farmer-submitted crop/season/location via the Kisan Fasal Sahyog form (`dashboard/kisan_upload.html`), a farmer's own drawn field boundary via Mera Khet (`dashboard/mera_khet.js`, MERA_KHET_PROMPT.md BHAAG A2), AND, as of KISAN_DASHBOARD_PROMPT.md section 8 (KRAM 6), an optional free-text damage/problem description via the Kisan Dashboard's report form (`dashboard/kisan_dashboard.js`) -- same D1 table, same `/submit` endpoint, one pipeline, three callers | village/block/district (point-in-polygon resolved); polygon geometry when submitted via Mera Khet; `problem_description` (max 500 chars) when submitted via the Kisan Dashboard's report form | EPSG:4326, coordinates (and every polygon vertex) rounded to 3 decimals (~100m) before publication -- rounded a second time server-side, not trusted from the client alone | `cloudflare/kisan_upload_worker.js` (D1 write, `submissions.geometry_json` added by `cloudflare/kisan_upload_schema_002_geometry.sql`, `submissions.problem_description` added by `cloudflare/kisan_upload_schema_003_problem.sql`, and — owner request 2026-09-02, "live location with photo" — an optional live field **photo** via `cloudflare/kisan_upload_schema_004_photo.sql`: `photo_url`, `photo_lat`, `photo_lon`, `photo_captured_at`. **Storage/access model:** the JPEG/PNG bytes go to a Cloudflare **R2 bucket** (binding `PHOTOS`, `vindhya-ground-truth-photos`); D1 and the daily export store only the resulting **object key**, never the image itself and never a public URL. Client downscales to ~1280 px / q0.75 before upload; the Worker enforces a 2 MB decoded cap and an image/jpeg|png allow-list. `photo_lat`/`photo_lon` are the capture-moment position, independent of the submission's own point, and are rounded to 3 decimals (~100 m) in the export like every other coordinate. **Nothing serves these photos back anywhere yet** — no dashboard panel, loader or export renders them; the key is recorded so a future reviewer can resolve it against the bucket. A submission with no photo (Mera Khet, Kisan Dashboard damage form) is entirely unaffected: same table, same `/submit` endpoint, a fourth optional field rather than a new pipeline) + `scripts/export_ground_truth.py` (daily export, `.github/workflows/ground-truth-export.yml`) -- see `docs/GROUND_TRUTH_UPLOAD.md` for full design and current status | **Prototype, not deployed** -- Worker needs the owner's own `wrangler deploy` (credentials never handled in chat); no submissions exist to publish yet | n/a |
| Mera Khet field polygon (`dashboard/mera_khet.js`) -- client-side only, not a stored dataset | Farmer-drawn on the map; area/perimeter via `geoai_professional.js`'s spherical/haversine geometry (reused, not reimplemented); the polygon's centroid is matched against `data/boundaries/soi/districts.geojson` to attach that district's already-published soil-moisture (`data/soil_moisture/`), climate (`data/climate/`, or `data/mp_climate_data.json` for the 5 original districts), and NDVI (`data/dicra_ndvi.json` or `data/ndvi/<state>/<district>.json`) values, each carrying its own resolution/N label; field-level cropland fraction + NDVI come from a **live** Earth Engine query via `cloudflare/mera_khet_worker.js` (Sentinel-2 SR Harmonized NDVI + Dynamic World V1 cropland classification, 10 m, `POST /analyze` calling Earth Engine's REST API `value:compute` directly with a service-account token) | field (exact, farmer-drawn; NDVI/cropland resolved at 10 m for that exact polygon, live, not cached); attached weather/soil/district-NDVI values are district/grid-cell tier, explicitly labelled as such, never claimed field-specific | EPSG:4326 | No new data pipeline for weather/soil/district-NDVI -- reuses the SoI boundary file, the existing SMAP soil-moisture pipeline (`scripts/13_gee_national_soil_moisture.py`), the ERA5-Land+CHIRPS/IMD climate pipelines, and the DiCRA/MODIS NDVI files as-is. Field-level NDVI/cropland: `cloudflare/mera_khet_worker.js`'s `/analyze` endpoint, expression graph obtained via `ee.serializer.encode()` (Earth Engine's own client library, not hand-written), verified side-by-side against `ee.data.computeValue()` in Python for 3 independent polygons before deploy -- see that file's header for the full verification method | Field NDVI/cropland: real, live, deployed (`https://vindhya-mera-khet.vindhyaresearch25.workers.dev/analyze`) as of 2026-08-13. 6-month NDVI time-series graph (MERA_KHET_PROMPT.md A1.2) explicitly **not yet built** -- scoped out, needs repeated monthly Earth Engine calls, not shipped unverified | 2026-08-13 |
| Mera Khet field wetness index (relative) (`dashboard/mera_khet.js`, section 3; `cloudflare/mera_khet_worker.js`'s `/analyze` response field `field_wetness_index_relative`) -- KHET-STAR KI NAMI item 4b, client-side only, not a stored dataset | **Live** Earth Engine query: Sentinel-1 GRD (`COPERNICUS/S1_GRD`) VV/VH backscatter (dB), most recent scene intersecting the field in a 60-day window, `reduceRegion(mean)` over the farmer's polygon vs. that SAME image's `reduceRegion(mean)` over the polygon's containing district (`FAO/GAUL/2015/level2`, a real GEE administrative-boundary asset -- verified live to correctly resolve Bhopal/Indore/Rewa for 3 independent test polygons). Chosen only after 4a (SMAP/Sentinel-1 disaggregated `SPL2SMAP_S`, 1-3 km) was independently re-verified as **not usable in GEE** -- see `docs/SOIL_MOISTURE_FIELD_SCALE_INVESTIGATION.md` (the collection was never ingested into Earth Engine's public catalog per `ee.data.listAssets()` against the real `NASA/SMAP` folder, and separately the source product itself has been paused at NASA/NSIDC since 2026-07-01 pending a Sentinel-1C/1D migration) | field (10 m, exact farmer-drawn polygon, live, not cached) vs. district (`FAO/GAUL` district polygon, not the SoI district boundary used elsewhere in this repo -- a deliberate, disclosed substitution for this one comparison) | EPSG:4326 | `cloudflare/mera_khet_worker.js`'s `buildS1WetnessExpression()`: expression graph built in Python with the real `earthengine-api` library and serialized via `ee.serializer.encode(..., for_cloud_api=True)` (never hand-written), verified byte-for-byte against `ee.data.computeValue()` for 3 independent real polygons, then structurally deep-equal-verified between the hand-transcribed JS graph and the Python-generated template. Field/district dB values converted to a percentage via the linear-power-ratio transform (`10^((field_db-district_db)/10) - 1) * 100`) -- a real, well-defined transform of the SAME acquisition's backscatter, **not** a moisture-percent claim | **NOT a m³/m³ soil-moisture measurement, and the response field is deliberately never named `soil_moisture`** -- SAR backscatter responds to vegetation and surface roughness as well as moisture, so it cannot be inverted to an absolute moisture value without ancillary data this repo does not have. Honest because both numbers come from the identical satellite pass, so calibration/speckle mostly cancel in the ratio even though the absolute value does not invert. Real, live, deployed as of 2026-08-13. Real Sentinel-1 revisit measured on the same ~1.86 ha benchmark polygon docs/MERA_KHET_BENCHMARK.json uses: only 1 scene in the last 30 days, 4 in the last 60 days (irregular gaps of 7/12/24 days) -- worse than the idealized "6-12 day combined revisit" because the observation window straddled Sentinel-1A's documented June 2026 end-of-life during the transition to the Sentinel-1C/1D pair (Copernicus SentiWiki, fetched 2026-08-13) | 2026-08-13 |
| `data/crop_stats_des/<year>-<yy>.json` (23 files, 2000-01 through 2022-23, 372,904 records) | Directorate of Economics and Statistics (DES), Dept. of Agriculture and Farmers Welfare, data.desagri.gov.in -- CROP_DATA_PROMPT.md's designated MUKHYA (primary) crop source, kept **separate** from the legacy `crop_stats.json` (data.gov.in) and any future UPAg/state-report pull, never merged | district, season (Rabi/Kharif/Autumn/Winter/Summer/Whole Year) | not applicable (tabular); area in hectares, production in tonnes (bales for cotton/jute -- see each record's own `unit` field) | `scripts/fetch_des_apy.py`: one POST per calendar year to the exact endpoint DES's own "View Report" button calls (`/report/crop/horizontal_crop_vertical_year`), all states/districts/crops/seasons per request (verified this doesn't overload the server), parsed with the same table logic as the browser-side `scripts/des_apy_table_extractor.js` twin (used interactively first to prove correctness against on-screen values before automating) | Verified: spot-checked exact match against on-screen DES values (e.g. Nicobars/Arecanut/Kharif 2000-01: 1,254.00 ha / 2,000.00 t / 1.59 t/ha); 0 negative values; district-name reconciliation against SoI done, see `docs/DISTRICT_NAME_MAP.md` | one-time historical pull, 2026-08-07 |
| `data/state_reports/madhya_pradesh_2019-20.json` (2,184 column-blocks, 61% identified) | Madhya Pradesh Department of Agriculture (Krishi Vibhag), annual compendium PDF, mpkrishi.mp.gov.in -- CROP_DATA_PROMPT.md CHARAN 4 | district, crop | not applicable (tabular) | `scripts/extract_state_reports.py`: pdfplumber table extraction; crop-column identity cross-validated against `data/crop_stats_des/` since the PDF's own headers are in a non-Unicode legacy font (Kruti Dev 010) that can't be extracted directly -- see `docs/STATE_REPORTS.md` for the full methodology and honest gap accounting | **Partial -- `extraction_verified: false`**, 39%% of column-blocks left unidentified rather than guessed; raw source PDF gitignored (`scripts/state_reports_raw/`), only the processed JSON ships | one-time, 2026-08-07 |
| `data/state_reports/rajasthan_2023-24.json` (204 rows, 4 crops x 51 districts) | Directorate of Economics & Statistics, Rajasthan, Jaipur -- Agricultural Statistics of Rajasthan 2023-24 compendium, rajas.rajasthan.gov.in -- CROP_DATA_PROMPT.md CHARAN 4, second state | district, crop | not applicable (tabular); area in hectares | `scripts/extract_rajasthan_report.py`: pdfplumber positional (x-coordinate) word extraction to reconstruct letter-spaced crop-name headers; every crop label validated against `data/crop_stats_des/`'s real crop vocabulary before being kept (306 unverified labels dropped this run) -- see `docs/STATE_REPORTS.md` for full methodology and honest gap accounting | **Partial -- `extraction_verified: false`**, area only (production-table district-merge has a known bug, not fixed), 4 of ~30+ crops, 6 of ~17 area sub-pages processed; this file covers 2023-24, a year newer than DES's current max (2022-23), so no DES cross-check was possible for it; raw source PDF gitignored | one-time, 2026-08-07 |
| `data/state_reports/karnataka_2022-23.json` (496 rows, 6 crops x 31 districts x up to 3 seasons) | Directorate of Economics and Statistics, Government of Karnataka, Bengaluru -- "Fully Revised Estimates Report on Area, Production and Yield of Principal Crops in Karnataka 2022-23", des.karnataka.gov.in -- CROP_DATA_PROMPT.md CHARAN 4, third state | district, crop, season | not applicable (tabular); area in hectares | `scripts/extract_karnataka_report.py`: plain pdfplumber text extraction (this PDF has neither MP's font problem nor Rajasthan's letter-spacing problem -- clean text throughout); one (crop, season, variety) table per page, only VARIETY=POOLED and real seasons kept; every crop label validated against `data/crop_stats_des/` (drops "Paddy" -- DES has no raw-paddy figure, only milling-adjusted "Rice", 93 Paddy rows dropped); 9 of 31 districts needed a hand-verified alias for this PDF's post-2014 Kannada-spelling renames vs DES's older transliterations, plus one genuine source-PDF typo ("VIAJAYANAGARA") -- see `docs/STATE_REPORTS.md` for full methodology and a discovered 2%% "bund correction" area relationship between this PDF and DES | **Partial -- `extraction_verified: false`** (93 Paddy rows dropped as unverified, by design); 380/496 rows have a DES cross-check, of which 358 (94%%) match DES's area exactly once the PDF's own stated 2%% bund-correction factor is applied; only the cereals section (Paddy/Rice/Jowar/Bajra/Maize/Ragi/Wheat, 19 of 171 pages) processed this pass -- pulses/oilseeds/commercial/horticulture/spices sections not yet done; raw source PDF gitignored (`scripts/state_reports_raw/`), only the processed JSON ships | one-time, 2026-08-07 |
| `data/crop_stats_comparison.json` (20,846 rows, 6.5MB) | Derived: cross-checks `data/crop_stats_des/` (MUKHYA) against the legacy `data/crop_stats.json` (data.gov.in) for their real overlap (5 MP districts, 2000-2013) -- CROP_DATA_PROMPT.md CHARAN 5 | district, season, crop, year | not applicable (tabular) | `scripts/build_crop_comparison.py`; never merges the two sources' numbers, reports each side-by-side plus %% difference | Verified: 2,002 overlapping rows found **0.0%% difference (mean and max)** -- see `docs/CROP_DATA_COVERAGE.md` CHARAN 5 for why (data.gov.in's resource appears to republish DES's own numbers, not an independent source for this overlap) | one-time, 2026-08-07 |
| `data/horticulture_stats/<state_slug>.json` (28 of 36 states/UTs, 4,028 records, fruits/vegetables/plantation crops/spices/flowers/mushroom) | **"Horticultural Statistics at a Glance 2023"**, Horticulture Statistics Unit, Economics Statistics & Evaluation Division, Dept. of Agriculture & Farmers Welfare (compiled from National Horticulture Board + State Horticulture/Agriculture Directorate returns), `agriwelfare.gov.in/Documents/Horticultural_Statistics_Glance_2023.pdf` -- CROP_DATA_PROMPT.md CHARAN 6, a **deliberate deviation** from CHARAN 6's literal "State Horticulture Department, <saal>" per-state hunt: a real, resolvable national compendium was found and checked first (NHB's own interactive query tool is state-level-only/no export button; data.gov.in's horticulture catalog entry is a narrow 2001-2010 snapshot) -- same DES-over-36-APY-PDFs reasoning CHARAN 1/2 already established for field crops. See `docs/CROP_DATA_COVERAGE.md`'s Horticulture section for the full resolvability comparison. | **state only** -- no district-wise horticulture dataset exists anywhere (checked); 53 crops (Tables 7.3.1-7.3.53), 4 years (2019-20 to 2022-23) | not applicable (tabular); area in hectares, production in tonnes (both converted from the source's '000-unit figures), yield in tonnes/ha as published | `scripts/fetch_horticulture_stats.py`: pdfplumber word-level extraction; each value bucketed to its (year, metric) column by nearest x1 (right-edge) coordinate to that table's own TOTAL/"All India Total" row, not left-to-right token order, because many state rows have blank cells for some years; a handful of the source's own row-label typos (e.g. "ARUNCHAL PRADESH", "JHARKAHND") corrected via a hand-built alias table cross-checked against the correctly-spelled variant elsewhere in the same document | Verified: 3 hand spot-checks against the PDF's own printed numbers (incl. one blank-cell case, Coriander/Meghalaya, confirming values aren't misattributed to the wrong year), all 53 tables parsed with 0 ambiguous-row skips; 8 states/UTs (Goa, Chandigarh, Delhi, Puducherry, Andaman & Nicobar Islands, Dadra & Nagar Haveli and Daman & Diu, Ladakh, Lakshadweep) never individually reported by the source itself (folded into its own "OTHERS" aggregate, not attributable to one state -- never guessed); **never summed with `crop_stats_des_by_district/` field-crop area into any "total crop area" figure** per CHARAN 6 | one-time, 2026-08-08 |
| Cadastral parcels | **disabled** — pending MP Bhulekh / Bhu-Naksha Revenue Dept. records | — | — | — | Not available | — |
| `data/ndvi/<state_slug>/<district_slug>.json` (Phase 8.4, national NDVI beyond MP) | MODIS Terra Vegetation Indices 16-Day Global 250m (MOD13Q1 v061), via Google Earth Engine | 250 m native pixel, one value/year = spatial mean of that year's temporal-mean composite over the district polygon | EPSG:4326 | `scripts/10_gee_national_ndvi.py`: per-calendar-year `ee.ImageCollection('MODIS/061/MOD13Q1').select('NDVI').mean()` then `reduceRegion` (mean+stdDev+count combined reducer, `bestEffort=True`), scaled by MOD13Q1's documented 0.0001 factor. State-by-state, resumable (`--resume`), heartbeat file `logs/gee_ndvi_heartbeat.json`. **Distinct from and never merged with `data/dicra_ndvi.json`** (UNDP DiCRA, MP's 52 districts) — `dashboard/national_ndvi_loader.js` explicitly skips any district `dicra_ndvi.json` already owns. `scripts/build_ndvi_manifest.py` counts real files into `data/ndvi_manifest.json`, read by the loader (GitHub Pages can't list a directory client-side) | Verified-official (real MODIS product), benchmarked+run for Tripura (8 districts) 2026-08-08 — see `NIGHT_LOG.md`'s 2026-08-08 entry for exact per-district timing | 2026-08-08 |
| `data/validation/<state_slug>/<district_slug>.json` (Phase 8.6, extended 2026-08-12 per PENDING.md item 7; 5 files: Bhopal/Indore/Jabalpur/Rewa/Sidhi) | ERA5-Land (ECMWF, Tmax → mean summer temperature + heatwave days) + CHIRPS (UCSB, precipitation) via Google Earth Engine, compared AGAINST the existing real IMD-derived series for the SAME district/years (`data/mp_climate_data.json` `charts.annual_trends` for rainfall/heatwave-days, `outputs/village_indices_per_year.parquet` village-mean for temperature) — validates IMD, never substitutes for it | Same as the GEE climate layer (ERA5-Land ~9 km, CHIRPS ~5.5 km) vs IMD ~5.5 km | EPSG:4326 | `scripts/11_build_validation.py`: per-year alignment on real years present on both sides only (no interpolation); CHIRPS `annual_rain_mm` and ERA5-Land `mean_summer_tmax`/`heatwave_days` all via `02_compute_indices.py`'s `extreme_for_village()`/`heatwave_for_village()` (identical IMD criteria) — imported directly, not reimplemented; real Pearson r, mean bias (GEE − IMD), RMSE, n, AND both series' actual per-year values (for the dashboard's line chart) computed and written into each file, plus a verdict string built from the actual numbers | Verified: real correlations computed 2026-08-12 (Bhopal: rainfall r=0.93, temperature r=0.96, heatwave-days r=0.85, n=25 years each — temperature correlates markedly better than the derived heatwave-day count, which is sparse/near-zero in most years; see file for the other 4 districts, all r≥0.71 rainfall / r≥0.96 temperature) | 2026-08-12 |
| `data/soil_moisture/<state_slug>/<district_slug>.json` (MERA_KHET_PROMPT.md B1, **733/733 districts, all 36 states/UTs — national run completed 2026-08-12**) | NASA SMAP L4 Global 3-hourly 9km Surface and Root Zone Soil Moisture (`NASA/SMAP/SPL4SMGP/008`), via Google Earth Engine. Checked and rejected first: `NASA_USDA/HSL/SMAP10KM_soil_moisture` (its own GEE catalog page: data collection ended August 2022 — stale) and `NASA/SMAP/SPL4SMGP/007` (deprecated in favour of /008) | `sm_surface` band, ~9 km (SMAP EASE-Grid 2.0 native spacing; GEE reports an 11,000 m pixel size for this asset — same "reported pixel size vs. documented native resolution" gap already noted for ERA5-Land) | EPSG:4326 | `scripts/13_gee_national_soil_moisture.py`: each district's real SMAP grid cells (not a single reduceRegion mean) sampled directly via `ee.Image.sample()` over the last 5 days of 3-hourly images (mean per cell) — every cell keeps its own value AND lon/lat. Village tier = nearest cell to the village polygon's centroid (scipy cKDTree, one vectorised query per district, not 654,285 individual GEE calls). Block tier = mean+stddev of its villages' assigned cells, grouped by the village layer's `sdcode` field (= `blocks/<state>.geojson`'s `block_lgd`). District tier = mean+stddev of the real cells sampled directly over the district polygon. State tier computed client-side in `dashboard/soil_moisture_loader.js` (mean+stddev of district means, N shown against the state's real total district count via `districts_index.json`) — never precomputed/frozen server-side so it always reflects current real coverage. `dashboard/data/soil_moisture/manifest.json` (`scripts/13_...`'s own `write_manifest()`) lists which district files are real | Verified-official (real NASA SMAP L4 dataset); benchmarked on Goa (2 districts, ~2s/district GEE time) 2026-08-08, extended to Delhi/Chandigarh/Puducherry/Sikkim (20 more districts) same day, then the remaining 711 districts completed 2026-08-12 (this entry had been left un-updated at the Aug-9 "benchmark only, national run not done" wording even though the run itself finished days later — corrected 2026-10-21 by actually counting the files on disk: `find dashboard/data/soil_moisture -mindepth 2 -name '*.json' \| wc -l` = 733); see heartbeat `logs/gee_soil_moisture_heartbeat.json` | 2026-08-12 |
| `data/advisory/<state_slug>/<district_slug>.json` (PENDING.md item 13, district tier, 731 districts as of 2026-08-12) | **Derived, not independently observed** — combines the real climate (`data/climate/` or `data/mp_climate_data.json`), NDVI (`data/dicra_ndvi.json` or `data/ndvi/`) and soil-moisture (`data/soil_moisture/`) rows above into four rule-based flags: `heatwave_risk`, `drought_risk`, `vegetation_stress` (NDVI, only where an NDVI file exists), `irrigation_need` (soil moisture, only where a soil-moisture file exists). **Explicitly NOT a machine-learning model and reports no confidence/probability score** — every flag is a fixed threshold on an already-published real number, cited by exact source file + field name in the flag's own `basis` object | District tier only (climate/NDVI inputs have no sub-district resolution of their own); each flag's own resolution is inherited from its source row above | EPSG:4326 | `scripts/15_build_advisory.py`: fixed threshold rules, see `docs/METHODOLOGY.md` Sec 9 for the exact per-flag table (reuses `national_climate_loader.js`'s heatwave bands, `scripts/config.py`'s real SPI thresholds, and `soil_moisture_loader.js`'s irrigation reference band verbatim rather than inventing new ones); NDVI flag computes a real z-score of the district's latest year against its own prior-years mean/stddev, with a partial-year guard (caps severity at MODERATE) when the latest year's composite count is well below typical, to avoid a seasonal-bias false HIGH. `dashboard/data/advisory/manifest.json` lists which district files are real and per-flag-type coverage counts | Derived (rule-based) — not a primary source in its own right; each flag's real underlying value is Verified per its own source row above | 2026-08-12 |

## Market and trade sources: status

| Source | Public API | Status in this portal |
|---|---|---|
| **AGMARKNET** (agmarknet.gov.in) | Yes — via data.gov.in resource `9ef84268-d588-465a-a308-a864a43d0070`, free key by registration | **Integrated, national.** Daily min/modal/max price per commodity per APMC market, all 733 districts (extended 2026-08-02 from the original 5 MP districts). First verified live on 2026-08-01 for the original 5-district scope: 32 price rows across Bhopal, Indore, Jabalpur, Rewa and Sidhi, all dated the same day. |
| **e-NAM** (enam.gov.in/web/dashboard/trade-data) | No documented public REST API found. The trade-data dashboard is a rendered web page; no bulk endpoint is published. | **Portal pointer only.** Do not scrape: the dashboard is served under portal terms, and e-NAM commodity coverage overlaps AGMARKNET, which already supplies the same trade in an authorised machine-readable form. Revisit if NIC publishes an e-NAM dataset on data.gov.in. |
| **e-CHARAK** (echarak.ayush.gov.in) | No documented public API found. It is a Ministry of AYUSH buyer–seller platform for medicinal and aromatic plants, not a price-reporting service. | **Portal pointer only.** Relevant to a future medicinal-plants module for the Vindhya region, where such cultivation is significant. Requires an institutional data request to the National Medicinal Plants Board rather than an API call. |

The rule applied to all three: cite and link the official portal, integrate
only where the publisher provides a machine-readable endpoint under terms that
permit it, and never scrape a dashboard to manufacture coverage.

## cNARMADA basin district layer (owner-supplied, 2026-09-14)

| File | Source | Resolution | CRS | Processing | Status | Updated |
|---|---|---|---|---|---|---|
| `data/cnarmada/narmada_basin_districts.geojson` (40 districts, 4 states) | **Owner-supplied** Narmada basin district shapefile (`Narmada_District_shapefile.zip`; GADM-lineage attributes ID_0/ISO/NAME_1/NAME_2/HASC_2), cross-checked against the owner's `STATE and District.xlsx` selection list | district polygon, simplified 0.0005° (topology preserved) | EPSG:4326 (source already WGS84) | `scripts/build_cnarmada_basin.py` | Owner-supplied — **not** Survey of India | 2026-09-14 |
| `data/cnarmada/narmada_basin_index.json` | Properties-only extract of the above | district | n/a | same script | derived | 2026-09-14 |

**What this layer is and is not.** It is the owner's basin delineation, used
by the cNARMADA panel **only** to populate the State/District selectors and
to outline the selected district on the map. It is deliberately NOT presented
as the Survey of India boundary product the rest of the portal uses
(`data/boundaries/soi/*`), and the panel says so on screen.

**Every analytic number the cNARMADA panel shows is read at runtime from this
repo's existing real per-district files** — no new measurement is created by
this layer:

| Layer | File | Basin coverage |
|---|---|---|
| Climate (GEE) | `data/climate/<state>/<district>.json` | 37/40 |
| Climate (IMD village product) | `data/mp_climate_data.json` | 3/40 (Bhopal, Indore, Jabalpur — by design, not a gap) |
| NDVI | `data/ndvi/<state>/<district>.json` | 40/40 |
| Soil moisture | `data/soil_moisture/<state>/<district>.json` | 40/40 |
| Groundwater | `data/groundwater/<state>/<district>.json` | 40/40 |
| Crops (DES) | `data/crop_stats_des_by_district/<state>/<district>.json` | 40/40 |
| Horticulture | `data/horticulture_stats/<state>.json` | 4/4 states (STATE level, labelled as such) |
| Advisory flags | `data/advisory/<state>/<district>.json` | 40/40 |

**Name resolution.** The basin shapefile spells six districts differently from
this repo's SoI district index. Each was resolved to the SoI spelling so the
data files above can be keyed correctly, and the build script raises rather
than silently dropping a district it cannot resolve:

| Shapefile | Resolved to | Basis |
|---|---|---|
| Kabeerdham (CG) | Kabirdham | shapefile's own `VARNAME_2` = "Kabirdham\|Kabeerdham" |
| Dahod (GJ) | Dohad | shapefile's own `VARNAME_2` = "Dohad" |
| Chhota Udaipur (GJ) | Chhotaudepur | SoI index spelling |
| Hoshangabad (MP) | Narmadapuram | official 2021 rename |
| Narsimhapur (MP) | Narsinghpur | SoI index spelling |
| West Nimar (MP) | Khargone | same district under its older revenue name |

The owner's Excel and the shapefile were cross-checked by the build script and
agree on all 40 districts (the only difference being the Kaberdham/Kabeerdham
spelling of the same district, which resolves to Kabirdham either way).

## Administrative vintage of the Survey of India district layer (2026-09-14)

**Owner report:** "MP ke sabhi 55 district nahi dikh rahe hain."
**Confirmed — this is real, and it is a source-vintage gap, not a bug in
this repo's code.**

`data/boundaries/soi/districts.geojson` carries **52** Madhya Pradesh
districts. Madhya Pradesh officially has **55**. The three absent ones
are exactly the three created in 2023, after this SoI/NWDP product's
vintage:

| District | Carved out of | Notified |
|---|---|---|
| Mauganj | Rewa | 15 Aug 2023 |
| Pandhurna | Chhindwara | 5 Oct 2023 |
| Maihar | Satna | 5 Oct 2023 |

Verified in this repo's own data, not just asserted: each of the three
is present as a **tehsil/sub-district of its parent district** — grep
confirms `Maihar` inside `data/soil_moisture/madhya_pradesh/satna.json`,
`Mauganj` inside `rewa.json`, and `Pandhurna` inside `chhindwara.json`.
So their territory, villages and readings are all present and correct;
they are simply still filed under the parent district, which is what the
source itself says.

Every downstream count inherits this vintage, which is why the UI
honestly reports "mean of 52 of 52 real districts" for Madhya Pradesh —
that figure is not wrong about what it has, it is describing a 52-district
universe.

**Not fixable by editing this repo.** Splitting Rewa/Satna/Chhindwara
into parent + child polygons would mean drawing boundaries no official
source here publishes, and re-attributing climate/NDVI/crop values
between them would mean inventing per-district numbers — both barred
outright by CLAUDE.md's no-fabrication rule. The only legitimate fix is a
newer upstream SoI/NWDP district product that already contains the three,
re-run through `build_national_soi_boundaries.py --stage district`.

**Status: pending official source.** Whether NWDP has published a
post-2023 district boundary product has NOT been confirmed here — it
needs a check against https://nwdp.nwic.gov.in (STANDING ORDERS #3's
"check NWDP first" rule) and, if a newer vintage exists, an owner
decision, because re-cutting the district layer also re-cuts the
block/village slices keyed to it and touches the Hugging Face-hosted
650 MB boundary set (STANDING ORDERS #8 — do not decide alone).

## Geometry simplification for web delivery (2026-08, revised 2026-08-02)

`build_national_soi_boundaries.py` simplifies every SoI boundary layer
(state, district, block, village) to tolerance 0.0005° (~55 m) and rounds
coordinates to 5 decimal places (~1 m) to make the portal usable on rural
mobile connections. No feature is ever dropped.

An initial version of this pipeline (2026-08-01) simplified each polygon
independently (per-feature Douglas-Peucker via shapely). That is topologically
unsound for a shared-border layer: two adjacent villages each simplify their
own copy of the same border differently, so the copies can drift apart and
overlap. A full-country audit on 2026-08-02 found this had introduced
overlapping village pairs in effectively every district processed so far
(worst case: 33% of a village's area, ~1,700 overlapping pairs in one Assam
district alone) — never present in the raw SoI source, confirmed by checking
several flagged pairs against it directly.

Fixed by switching to topology-preserving simplification (the `topojson`
Python library): every layer's shared-arc topology is built once, each arc is
simplified exactly once, and both neighbours keep the identical result. Two
further edge cases needed explicit handling and were verified fixed by hand
before being generalized: (1) a handful of small, topologically-isolated
polygons (e.g. a riverine "diyara" plot, a census town carved out of its
parent rural village) could still oversimplify into a nearby-but-unrelated
neighbour's footprint even with `shared_coords=True`; the fix restores the
original (unsimplified) geometry for both features in any residual
overlapping pair, verified against the raw source to be genuinely disjoint.
(2) A very small number of the tiniest raw polygons could round away to an
empty geometry at 5-decimal precision; the fix restores the original geometry
for that feature rather than dropping the village silently.

The entire national village layer (654,285 villages, 36 states/UTs) was
rebuilt with the fix and re-verified feature-pair-by-feature-pair
(area-overlap fraction > 2% of the smaller polygon = flagged): **zero
overlaps found**, at state, district, block, and village level, nationwide.

| Layer | Tolerance | Approx. ground error | Feature count |
|---|---|---|---|
| States | 0.0005 deg | ~55 m | 36 |
| Districts | 0.0005 deg | ~55 m | 733 |
| Blocks (sub-districts) | 0.0005 deg | ~55 m | 6,312 |
| Villages | 0.0005 deg | ~55 m | 654,285 |

This is below the 5.5 km resolution of the underlying IMD climate grid, so it
does not affect any computed index. Full-precision source vectors should be
retained offline for any cadastral or legal use.

## Groundwater / well-irrigation (MERA_KHET_PROMPT.md B2, checked 2026-08-09)

Two real, honestly-separated things live in the "GROUNDWATER & IRRIGATION"
card of the Agriculture panel:

1. **Real well/tubewell-irrigated area** (`agri-gw-wells`) -- summed live,
   client-side, from `data/village_profiles/<state>/<district>.json`'s
   `irrigated_wells_tubewells_ha` field across every village in the
   selected district, with the real village count shown ("Sum of N/total
   villages..."). Genuine SoI-sourced data, already used elsewhere in the
   dashboard (Compare feature, village profile panel) for the same field.
2. **Groundwater level TREND** (`agri-gw-level`) -- the actual water-table
   depth/trend, which needs CGWB/India-WRIS. Checked before building
   anything: `indiawris.gov.in` has no documented public API (form-based
   dashboard portal, no developer docs found); `cgwb.gov.in` has no bulk
   machine-readable download found either. Per MERA_KHET_PROMPT.md's own
   rule ("Nahi hai to panel me: 'No public API...' ... Scrape mat karo"),
   this card honestly reads "No public API. Source: CGWB India-WRIS.
   Institutional data request required." rather than being scraped or
   estimated.

**These two are never combined into one score.** The prompt's actual
ambition ("jyada nalkoop sinchai + girta bhujal star = khatra" -- a real
groundwater-risk index combining well density with a falling water table)
needs the CGWB half, which isn't available -- so it isn't computed. A
real per-state `data.gov.in` OGD channel for CGWB groundwater level data
appears to exist (same distribution channel already used for AGMARKNET/
crop stats in this project) but real per-state resource IDs were not
found/verified in the time available; worth a dedicated future session,
not chased further here to avoid guessing at unverified resource IDs.

**Re-checked 2026-08-12** (independent follow-up, same conclusion, extra
detail): `indiawris.gov.in` still returns only the Angular SPA HTML shell
to a direct request, no reachable JSON endpoint. `cgwb.gov.in`'s real-time
water-level portal, `gwdata.cgwb.gov.in`, was itself in "Maintenance Mode"
at check time and, even when reachable, is a form-driven query tool, not a
documented API -- it was not scraped either way. `cgwb.gov.in` links only
PDF reports for groundwater assessment (e.g. `GWRA_2025.pdf`, the Dynamic
Ground Water Resources district-wise assessment), never a CSV/JSON bulk
file. `data.gov.in`'s catalog/search endpoints return HTTP 403 to a direct
non-browser request (its resource-level API, `api.data.gov.in/resource/
<id>`, is the same working pattern `scripts/fetch_mandi_prices.py` uses
for AGMARKNET, but that requires already knowing a valid `resource_id`,
and no CGWB groundwater-level resource ID was located this pass). No
scraping was attempted anywhere in this check. Conclusion at the time:
honest gap message stands, well-irrigation half stays real and shown.

**RESOLVED 2026-08-19 -- a real source was found.** All four checks above
were real and correctly conducted, but missed one government portal this
project already trusts for a different dataset: **the National Water Data
Portal, `nwdp.nwic.gov.in`** -- the exact same site standing order #3
already points to for village boundaries
(https://nwdp.nwic.gov.in/dataset/village-boundary). Its dataset page
https://nwdp.nwic.gov.in/dataset/gwl-manual-quarterly-central-ground-water-board-department
publishes CGWB's own **"Ground Water Level (Manual - Quarterly), CGWB"**
series as 95 plain CSV files (fetched directly via `curl`, no login, no
API key, no JS execution needed -- the download links are static hrefs in
the page's own HTML): 33 of India's 36 states/UTs, each with up to three
time-slices (1991-2020, 2021-2025, 2026-2030). **Mizoram, Sikkim and
Ladakh have no dataset here at all** -- confirmed by their full names not
appearing anywhere in the fetched page HTML, not just a parsing miss --
and stay honestly "not available" everywhere downstream.

- Real columns verified: `SlNo,Station,Agency,State LGD Code,State,
  District LGD Code,District,Tehsil,Block,Village,River,Basin,Tributary,
  SubTributary,SubSubTributary,Local River,Latitude,Longitude,RL_MSL,Data
  Acquisition Time,Groundwater Level Quarterly Manual (meter)`.
- **Join key is `District LGD Code`**, matched directly against this
  project's own Survey-of-India `district_lgd` field (`dashboard/data/
  boundaries/soi/districts_index.json`) -- e.g. Jabalpur (MP) is LGD 411
  in both. This sidesteps the AGMARKNET-style district-name-spelling
  mismatch documented above in `scripts/fetch_mandi_prices.py`'s own
  header entirely.
- License: the CKAN "License" module on the dataset page is present in
  the HTML source but rendered inside an HTML comment (`<!-- ... -->`),
  so it never actually displays on the page; its underlying value is
  `<span property="dc:rights">Other (Open)</span>` linking to
  opendefinition.org's Open Definition. Recorded honestly as: license
  field value found is "Other (Open)" (not a named SPDX license), the
  same status this project already accepts for the village-boundary NWDP
  download used under standing order #3.
- Unit/sign convention: the dataset's own CKAN notes text says only "GWL
  values in meter (m)", without spelling out "below ground level"
  explicitly. CGWB's own standard public reporting convention for this
  exact series is depth-to-water-level below ground level (mbgl,
  positive number, larger = deeper). Cross-checked for plausibility (not
  proven against a named public report for these exact stations) against
  real fetched rows: Jabalpur's "Adhartal Naka" station reads 8.94-10.0 m
  across 2021-2022 quarters, consistent with CGWB's typically-cited
  ~5-15 m bgl range for that district; a value in the single digits
  cannot be RL/MSL for Madhya Pradesh terrain (hundreds of metres above
  sea level), which independently rules out the other plausible reading
  of "meter" in this column.
- Pipeline: `scripts/16_fetch_groundwater.py` (downloads all 95 CSVs,
  cleans/sanity-bounds each row at 0-100 m, joins on LGD code, computes a
  plain OLS trend per station from real quarterly history where >=4
  points exist -- same "indicative trend on real history" style as
  `forecast_2040.json`, never a projection). Output:
  `dashboard/data/groundwater/<state_slug>/<district_slug>.json`
  (district-wise files, matching the village-boundary convention) plus
  `dashboard/data/groundwater/manifest.json`. Dashboard:
  `dashboard/groundwater_loader.js` (own bottom-panel tab; also
  overwrites the Climate Metrics side panel's Groundwater card and the
  Agriculture pane's `agri-gw-level` field with real values where
  covered, leaving `agri-gw-stress`/`agri-gw-irr-need`/`agri-gw-recharge`
  -- a separate, already-labelled-indicative drought-derived heuristic --
  and `agri-gw-wells` -- the real SoI well/tubewell figure -- untouched).
- **Coverage after the first full national fetch (2026-08-19):** see
  `dashboard/data/groundwater/manifest.json`'s `totals` block for the
  exact counts from the actual run (never hand-typed here -- read the
  file, it is regenerated by the pipeline every run).

## Compare feature (`dashboard/compare_loader.js`, Phase 6, added 2026-08-07)

Not a new data file -- a client-side view that combines four existing
sources per selected district, each labeled distinctly, never merged into
one number:

| Column | Source | Granularity actually available |
|---|---|---|
| Heatwave days / SPI-12 / Rainfall / Rx1day | `data/mp_climate_data.json` (Bhopal/Indore/Jabalpur/Rewa/Sidhi only) or `data/climate/<state>/<district>.json` (all other districts with a file) | Real year-by-year 2000-2024 for the 5 IMD districts; a single 2000-2024 **period average** for every GEE (ERA5-Land/CHIRPS) district -- confirmed from the file's own contents (`indices` is a flat scalar dict, not a yearly series) before this was built. The UI marks GEE-sourced cells "avg" and the year slider does not change them. |
| NDVI | `data/dicra_ndvi.json` | Madhya Pradesh's 52 districts only (DiCRA/MODIS). Every other state shows "Data not available", never a neighbouring district's value. |
| Population / Net area sown / Irrigated area | `data/village_profiles/<state>/<district>.json` (HF-hosted) | Summed live, client-side, from the real per-village SoI fields (`population`, `land_net_area_sown_ha`, `irrigated_area_total_ha`) across every village in the selected district's file. Every aggregate cell's tooltip states how many villages it was summed from and the source `fetch_date`; a district with no village_profiles file (SoI coverage gap) shows "Data not available", never a partial estimate. |

District/State/Block/Village tier selector exists in the UI; only District
tier is implemented -- State/Block/Village show an explicit "not built yet"
message rather than wrong-tier or half-broken data.

## Kisan Sahayak research papers (`dashboard/research_papers_loader.js`, Phase 7.3, added 2026-08-08)

FINAL_PROMPT.md Phase 7.3 names 8 free scholarly APIs. Each was tested with
a real keyless request before deciding what to wire (2026-08-08):

| Source | Status | Evidence |
|---|---|---|
| OpenAlex | Wired | `api.openalex.org/works?search=...` -- 200, real title/authors/year/DOI |
| CrossRef | Wired | `api.crossref.org/works?query=...` -- 200, real DOI records |
| DOAJ | Wired | `doaj.org/api/search/articles/...` -- 200, real open-access articles |
| PubMed/PMC | Wired | NCBI eutils `esearch` + `esummary` -- 200, real PMIDs/titles |
| Semantic Scholar | Wired, best-effort | `api.semanticscholar.org` -- returned HTTP 429 on the very first test call (public/keyless tier is heavily rate-limited); still attempted every search, failures silently dropped rather than shown as an error |
| CORE | **Not wired** | `api.core.ac.uk/v3/search/works` returned HTTP 301 to an auth flow -- requires a registered API key this portal does not have |
| FAO AGRIS | **Not wired** | `agris.fao.org` returned HTTP 403 (Cloudflare bot challenge) on a plain request -- no documented public JSON API found; bypassing the challenge would violate this portal's own bot-detection rule |
| ICAR KRISHI | **Not wired** | `krishi.icar.gov.in` did not resolve (DNS failure) from the dev machine at time of writing -- no public API found |

Every returned result carries a real title, real authors (from the source,
never invented), real year, and a real link (DOI or the source's own
landing-page URL) -- a query with zero real matches renders an honest
"no papers found" message, never a placeholder citation. Sci-Hub is never
called or referenced, per FINAL_PROMPT.md's explicit rule.

## Kisan Sahayak agriculture DSS backend (`cloudflare/kisan_sahayak_worker.js`, added 2026-08-08)

The chat widget's Cloudflare Worker fetches five real data sources in
parallel for the farmer's selected place, all already-registered elsewhere
in this file/repo -- listed here just as the consuming point, not a new
source: `dashboard/data/mp_climate_data.json` and
`dashboard/data/climate/<state>/<district>.json` (climate), HF-hosted
`village_profiles/<state>/<district>.json` (village profile),
`dashboard/data/crop_stats_des_by_district/<state>/<district>.json` (crop
stats), `dashboard/data/mandi_prices.json` (mandi prices), and NASA POWER's
daily point API (live weather, same source as
`dashboard/live_weather_loader.js`). The Worker's `search_papers` tool is a
server-side re-implementation of the OpenAlex/CrossRef/DOAJ/PubMed sources
already wired in `dashboard/research_papers_loader.js` (same honest
inclusion/exclusion list as the row above -- Semantic Scholar/CORE/AGRIS/
ICAR-KRISHI are not re-litigated here, see that section).

**New source as of this Worker:** `search_manuals`, a Cloudflare Vectorize
RAG index (`kisan-sahayak-manuals`) over real ICAR/state-department/IMD
Package-of-Practices and agromet-advisory PDFs, embedded with Workers AI's
`@cf/baai/bge-base-en-v1.5`. Full corpus coverage, exact document list,
what was tried and excluded, and the ingestion contract are in
`docs/KISAN_SAHAYAK_RAG.md` -- 6 real documents ingested as of 2026-08-08
(wheat PoP 1984/IIWBR, organic-farming PoP/Maharashtra, direct-seeded-rice
bulletin/ICAR-CRRI 2025, Kharif agro-advisories/ICAR 2025, and IMD agromet
bulletins for Gujarat and Assam). Neither the Vectorize index nor the
Worker itself has been deployed by this session -- both require the
owner's own Cloudflare login.

## Hero landing page photos (`dashboard/index.html` `#hero` carousel, updated 2026-09-01)

Decorative stock photography, not a data layer -- listed here (rather than
invented as a new provenance section) because CLAUDE.md's "no fabrication,
ever" rule explicitly extends to "never claim a stock photo is something
it isn't." All 3 verified live on unsplash.com immediately before use,
confirmed each is under the standard free-for-commercial-use **Unsplash
License** (not the paid Unsplash+ tier -- several Getty-contributed photos
that came up in the same searches were Unsplash+ and were rejected for
that reason). Hot-linked from `images.unsplash.com`, same storage pattern
already used by the pre-existing `.u-bg-gate1-4` login-gate slideshow --
no images committed to the repo, no new asset-loading mechanism added.

| Slide | Photo | Photographer | Unsplash URL | License |
|---|---|---|---|---|
| 1 (`.u-bg-hero1`) | Farmer plowing a field with two white oxen under a stormy sky | Saikiran Kesari | https://unsplash.com/photos/zSn8VuwV7Kg | Unsplash License |
| 2 (`.u-bg-hero2`) | Wheat field close-up | Nitin Bhosale | https://unsplash.com/photos/U98LIYBFVJk | Unsplash License |
| 3 (`.u-bg-hero3`) | Farmer on agricultural equipment | Rajesh Ram | https://unsplash.com/photos/HOOKgN_zIY8 | Unsplash License |

Slide 1 is unchanged from what shipped previously (it was already this
same Saikiran Kesari photo, now positively identified/credited by name for
the first time). Slide 2 replaces a previous image
(`photo-1560493676-04071c5f467b`) whose photographer could not be
positively re-identified during this pass -- rather than keep an unverified
credit, it was swapped for the Nitin Bhosale photo above. Slide 3 is new,
added to bring the carousel to the owner's requested 3 images.

## Synthetic 100-Farmer Crop Insurance Pilot Study (added 2026-09-02)

`dashboard/data/crop_insurance_pilot/synthetic_farmers_100.json`, served only
to `dashboard/crop_insurance_pilot/pilot_study.html`, generated by
`dashboard/crop_insurance_pilot/generate_synthetic_pilot.py` (fixed seed
20260819, byte-identical on regeneration).

**This file is deliberately SYNTHETIC.** It is the single, owner-authorised
exception to CLAUDE.md's "no synthetic data, ever" rule, and it exists to
demonstrate a cadastral-level crop-insurance decision-support framework as a
research pilot study. It is bounded as follows and must stay bounded:

- Consumed by exactly one standalone page. It is never read by the main
  dashboard, never merged into `mp_climate_data.json`, `crop_stats`,
  `mandi_prices` or `groundwater`, and never contributes to a landing-page
  statistic.
- Every record carries `synthetic: true` plus a `SYNTHETIC_DATA_NOTICE`, and
  the page prints SYNTHETIC / SIMULATED labels on every screen, table, popup,
  chart and card, with the full pilot disclaimer reproduced verbatim.
- Farmer names are deliberately non-realistic placeholders
  (`SYN-FARMER-001`). No realistic Indian personal name, Aadhaar number, bank
  detail, phone number or real policy number is generated or derivable --
  fabricated realistic owner names were precisely the defect removed in the
  2026-08 cleanup below.
- The generator lives outside `scripts/` on purpose, so the CI guard that
  greps `scripts/` for random generation keeps protecting the real pipeline.

**Real inputs reused (these must remain real):**

| Component | Source |
|---|---|
| Simrol village polygon; every synthetic parcel is clipped inside it | Survey of India village boundary via NWDP, vil_lgd 476504, Mhow block, Indore district |
| Census population / households | Fields carried in that same SoI/NWDP feature |
| Per-crop yield baselines and PMFBY threshold yields (mean of best 5 of last 7 available years x indemnity level) | DES, data.desagri.gov.in, Indore district (`dashboard/data/crop_stats_des_by_district/madhya_pradesh/indore.json`) |
| Farmer premium-share caps (Kharif 2%, Rabi 1.5%, annual commercial/horticultural 5%) | Notified PMFBY scheme parameters |
| Optional per-parcel live satellite check (Sentinel-2 NDVI, Dynamic World cropland fraction, Sentinel-1 backscatter) | Live Google Earth Engine via the existing Mera Khet Worker; verified working from the deployed origin 2026-09-02 |

**Synthetic / simulated (the subject of the pilot):** the 100 farmers, their
IDs, khasra numbers and parcel polygons; girdawari records and land status;
all NDVI/NDWI/EVI series and crop-health scores; all weather events, damage
areas and loss percentages; all AI confidence and evidence scores; and all
premium and claim values.

**"Synthetic" here means the INPUTS are simulated — every displayed statistic
is still computed from them by a real, re-derivable formula, never drawn.**
That distinction is the whole point of CROP_INSURANCE_SYSTEM_PROMPT.md §21(i),
and it was not fully honoured until the 2026-09-02 audit. `ai_confidence_pct`
was `rng.uniform(86, 95)` — a bare random number with no link to any other
field, repeated at 11 render sites, and driving a decision rule (`< 88` →
"additional evidence advised"), i.e. an anomaly flag settled by a coin flip.
It is now a weighted sum of three terms computed from this same record —
phenology fit against the expected undamaged curve (0.45), Sentinel-2 pixel
support derived from the parcel's cultivated area (0.25), and class
separability over the real same-season candidate set (0.30) — with the
components written into the file as `ai_confidence_components` so the page can
show the arithmetic. Four evidence-score components (the NDWI, rainfall-anomaly
and multi-temporal terms, plus both no-event terms — together ~70 % of that
score's weight) were likewise `rng.uniform` draws and now use the real
simulated signals already stored beside them. Random draws remain only where
they represent simulated *measurement noise on top of* a real derivation (e.g.
the ±2–5 % jitter on crop health), never as the whole value.

**Not field-validated.** "Correctly computed from the synthetic inputs" is not
"validated against real farmers". No number in this module has been checked
against a real crop-loss assessment, and the page must keep saying so wherever
a percentage appears. Parcel component areas (bund/med, farm road,
waterbody, fallow, non-crop, cultivated) are geometrically derived from the
generated polygons, so they sum to the cadastral area rather than being
typed-in numbers.

Sum Insured per hectare and the actuarial/gross premium rate are
**configurable pilot parameters, not official notified values** -- real PMFBY
Sum Insured is the notified Scale of Finance and varies by
state/district/season/crop, and the actuarial rate is discovered by insurer
bidding per cluster. Both are exposed as editable inputs in the UI.

## Fertiliser dose reference (`data/fertilizer_doses.json`, added 2026-09-02)

AUDIT_FIX_PROMPT.md item 10b. Powers the Agriculture tab's "Fertilizer &
Crop Recommendation" card (`dashboard/fertilizer_loader.js`), built by
`scripts/build_fertilizer_doses.py`.

| Layer / file | Source | Resolution | CRS | Processing | Quality | Updated |
|---|---|---|---|---|---|---|
| `data/fertilizer_doses.json` (12 crops, 22 dose rows) | **Crop Production Guide — Agriculture 2020**, Directorate of Agriculture, Chepauk, Chennai 600 005 **and** Tamil Nadu Agricultural University, Coimbatore 641 003. <https://agritech.tnau.ac.in/pdf/AGRICULTURE.pdf> | Per crop × stated growing condition (irrigated / rainfed / variety / hybrid). **Not** per district, **not** per field, **not** a soil-test prescription | n/a — agronomic reference table, no geometry | `scripts/build_fertilizer_doses.py`: each N : P₂O₅ : K₂O row transcribed from the page cited on that row, from the guide's own **"blanket recommendation"** statements | Verified — real published state POP, each row page-cited | 2026-09-02 |

**What was transcribed, and what deliberately was not.** Every row is the
guide's own *blanket recommendation* — the value it instructs the reader to
use **only when a soil test is not available**; its standing instruction in
each of these sections is to follow the soil test wherever one exists, and
the card repeats that on screen. Doses appearing in the guide's
**seed-production** chapters (identifiable by roguing / male parent /
isolation-distance context) are for seed multiplication, not grain
cultivation, and were excluded rather than presented as general doses.

**Attribution method, because a near-miss here would be a fabrication.** A
naive nearest-heading match mis-assigned wheat's 80:40:40 to a millet
chapter. Attribution is therefore done through the guide's own table of
contents page ranges (PDF page = printed page + 12, verified against three
independent chapter headings), so each row is provably the crop it claims
to be, and each row stores the printed page so a reader can check it.

**Applicability, stated in the file and on screen.** These are recommendations
issued for **Tamil Nadu**. They are that state's Directorate of Agriculture
and TNAU's own published figures, **not a national ICAR dose**, and other
states' agricultural universities publish their own package of practices
with different numbers. Extending coverage means adding rows from those
states' own POPs, each page-cited the same way — a dose written from memory
must never enter this file.

**Season assignment is not in this file.** Which crops a place grows, and in
which season, comes from that district's **own real DES records**
(`data/crop_stats_des_by_district/`, which carry a published `season` field
per crop-year), using its latest reported year, which the card prints. DES
"Summer" renders as Zayad; "Whole Year" crops get their own block rather
than being forced into one of the three seasons. A crop with no transcribed
dose is named on screen under "Dose not available for: …" — never filled in
from a similar crop.

**Area scaling** uses the farmer's own measured field from Mera Khet
(`window._meraKhetLastField.area_ha`, published and cleared by
`dashboard/mera_khet.js`). With no measured field only the per-hectare
figure is shown; an assumed field size would be an invented number.

## Village Profile & Agricultural Intelligence Report (`dashboard/village_report.js`, registered 2026-09-02)

**Not a new dataset — a consumer.** This module introduces no source of its
own. It is registered here because the register's own rule is "layers not
listed must not be displayed", and this page displays values from eight
already-registered layers at once, so a reader needs one place that says
exactly which.

| Report section | Layer it reads | Row above |
|---|---|---|
| Village identity, population, households, land use, irrigation, water sources, nearest town | `data/village_profiles/<state>/<district>.json` (SoI/NWDP attribute table, HF-hosted) | SoI village profiles |
| Climate indices | `data/climate/<state>/<district>.json` | ERA5-Land + CHIRPS via GEE |
| NDVI | `data/ndvi/<state>/<district>.json` | MODIS MOD13Q1 v061 |
| Soil moisture (district / block / village-cell tiers) | `data/soil_moisture/<state>/<district>.json` | NASA SMAP L4 |
| Groundwater level + OLS trend | `data/groundwater/<state>/<district>.json` | CGWB via NWDP |
| Crop area/production/yield | `data/crop_stats_des_by_district/<state>/<district>.json` | DES, data.desagri.gov.in |
| Advisory flags | `data/advisory/<state>/<district>.json` | Derived rule-based layer |
| Horticulture | `data/horticulture_stats/<state>.json` | Horticultural Statistics at a Glance 2023 |
| Mandi prices | `data/mandi_prices.json` | AGMARKNET via data.gov.in |

Two design rules this module is held to, both re-verified 2026-09-02:

- **Every aggregate states what it was built from.** It is a *single-village*
  report, so there is no cross-village population or area roll-up to label;
  where records genuinely are combined the count travels with the number —
  the season split emits its own "Crops reported" count, the KPI strip carries
  "CROPS REPORTED" and "RECORDS IN SERIES" beside "TOTAL SOWN AREA", and the
  SMAP tier table carries both an `N` column and a "What N counts" column
  naming precisely what each N is (real cells sampled over the district
  polygon / this block's villages / the single 9 km cell shared with N
  others). Derived scalars — sex ratio, land-use share of total, irrigated
  share of net sown area — are each labelled "(derived)".
- **A gap renders as a gap, never as a zero.** An `IMPOSSIBLE_ZERO` guard
  converts a physically-impossible published zero (male = 0 in a village of
  10,405 people) into an explicit "Not recorded for this village" note naming
  the suppressed fields, and every unavailable section renders "Data not
  available for the selected location/period" plus a section-specific reason
  rather than a blank or a 0.

**Known gap, recorded not fixed:** `village_report.js` defines `t()`/
`isHindi()` but never calls them, so the report is English-only while every
sibling loader is bilingual. Translating ~20 sections is a separate piece of
work; recorded here and in PENDING.md rather than left undiscovered.

## Metadata contract and how it is enforced (added 2026-09-02)

Every JSON served under `dashboard/data/` must carry a `metadata` block with
**source, resolution, CRS, processing, last_updated**. This was stated in
CLAUDE.md and here long before it was enforced: the CI check globbed
`dashboard/data/*.json` **non-recursively** and only asserted that the key
existed, so it inspected 10 files out of ~5,200 and `"metadata": {}` passed.
99.8 % of published data was unchecked, and the workflow did not even run on
data pushes.

As of 2026-09-02 `.github/workflows/verify-data.yml` globs recursively,
asserts all five keys, and triggers on `dashboard/data/**`.
`scripts/backfill_data_metadata.py` brought all 5,200 files into compliance.
It did **not** invent provenance: almost every file already carried real,
detailed provenance recorded under a different key name by whichever pipeline
wrote it (`crs` vs `CRS`, `method`/`generator` vs `processing`,
`fetch_date`/`generated` vs `last_updated`), so the work was overwhelmingly an
alias. Only two kinds of value were newly written, both verifiable:
`CRS: EPSG:4326` for genuinely georeferenced layers (true by construction —
every geometry here comes from the Survey of India files, reprojected to
EPSG:4326 on ingest), and `processing` = the actual producing script, taken
from a per-directory map checked against each script's own output path.
Where neither applied, the script leaves the field alone and reports it, so
it surfaces as a CI failure rather than being papered over.

Two narrow, documented exemptions live in the CI check, per directory rather
than blanket: `CRS` on tabular layers that carry no geometry at all (DES and
ICRISAT crop tables, horticulture, the knowledge-base index — a coordinate
reference system is not a property of a table of crop areas), and
`resolution` on layers whose unit is an administrative area rather than a
grid (advisory flags, per-district crop tables).

## Removed in the 2026-08 cleanup

- 50 synthetic districts and ~5,000 generated villages (`08_expand_climate_data.py`)
- Fabricated cadastral parcels with invented owner names (`09_generate_cadastral.py`, `cadastral_kundam.geojson`)
- Random noise injection in forecasts; hardcoded API key fallback

## Soil type (`data/soil_type/<state_slug>/<district_slug>.json`, added 2026-10-21)

Owner asked for real national soil-type coverage. Soil Health Card portal
(soilhealth.dac.gov.in) and ICAR-NBSS&LUP's BHOOMI Geoportal
(bhoomigeoportal-nbsslup.in) were checked first (2026-10-21) -- both host
real district-level soil data but neither exposes a public bulk API/WMS/
WFS endpoint; data.gov.in's own listing confirms no API exists for the
Soil Health Card dataset. Same class of gap as the cadastral map below --
an institutional data-sharing request, not a fetch-script problem.

Used instead: `OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02` (ISRIC/
OpenLandMap), a real, public, global 250m soil-texture-class raster,
confirmed live in the GEE catalog and queryable with the same service
account already used for climate/NDVI/soil moisture. **This is a global
statistical soil map, not an India-specific ground survey** -- every
output file's `metadata` says so explicitly, never presented as a Soil
Health Card equivalent. `scripts/17_gee_national_soil_type.py`: per
district, `ee.Reducer.mode()` (dominant USDA texture class by pixel
count -- a category cannot be averaged) plus the real pixel-count
histogram behind it; village tier is one batched `sampleRegions()` call
per district over real village centroids (not one GEE call per village).
No block tier yet (honest gap). `dashboard/soil_type_loader.js` renders
it as its own bottom-panel tab (sidebar nav → Soil Type). National run
started 2026-10-21, in progress -- check
`dashboard/data/soil_type/manifest.json` for current real coverage.

## Crop yield outlook (`data/crop_yield_outlook/<state_slug>/<district_slug>.json`, added 2026-10-21)

Owner asked for crop yield prediction. `docs/CROP_YIELD_METHODOLOGY.md` §3
is the literature-grounded design for a real parcel-level satellite/ML
crop-type-and-yield model -- it remains genuinely blocked on ground truth
(CCE/Digital Crop Survey/UPAg access, §7), and this file does not attempt
to work around that block or fabricate what it would produce.

What this IS: a deterministic OLS trend (`numpy.polyfit`, degree 1) on
each district+crop+season's real `yield_per_ha` history already in
`dashboard/data/crop_stats_des_by_district/` (DES, data.desagri.gov.in,
2000-01 to 2022-23) -- same "no random noise, residual-based 95% band"
discipline already used for `forecast_2040.json`
(`scripts/07_build_dicra_forecast.py`) and the groundwater trend
(`scripts/16_fetch_groundwater.py`). `scripts/18_build_crop_yield_outlook.py`
requires 5+ real DES years per crop+season or it is omitted (693/733
districts, 22,762 crop+season series as of 2026-10-21). Rendered by
`dashboard/crop_yield_loader.js` as its own bottom-panel tab ("Yield
Outlook"). Every number is labelled indicative; this is a trend
projection on real district history, not a satellite/ML model and not a
substitute for an official crop forecast.

## Authoritative sources for planned integrations

Weather/climate: IMD (mausam.imd.gov.in API), NASA POWER (free REST, no key),
Copernicus ERA5 (CDS API). Soil: Soil Health Card portal, NBSS&LUP, ICAR --
**no public bulk API exists for either as of 2026-10-21** (see the soil-type
section above for what was checked); OpenLandMap/ISRIC via GEE is the real
substitute in use, not these two. Remote sensing: Sentinel-2, Landsat,
MODIS, SMAP via GEE. Markets: AGMARKNET via data.gov.in API (key required).
Groundwater: CGWB India-WRIS. Schemes: PMFBY, PM-KISAN portals. Land
records: MP Bhulekh / Bhu-Naksha.
