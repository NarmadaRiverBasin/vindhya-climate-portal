# 20-panel source audit

FINAL_PROMPT.md Phase 9. Verified against the actual running code
(`dashboard/index.html` panel HTML + JS state, `docs/DATA_SOURCES.md`),
not against what a panel is titled or what an earlier plan assumed.
Most "not integrated" panels were already fixed to say so honestly in
the 2026-08-01 audit (`docs/AUDIT_2026-08-01.md`) -- this pass confirms
that's still true today and adds the "does a real free public API exist"
research CHARAN asks for, per panel.

| Panel | Source | Status | Public API? | Next step |
|---|---|---|---|---|
| Climate Risk Atlas / Heat Waves / Extreme Precipitation / Drought | ERA5-Land + CHIRPS via GEE (IMD for the original 5 MP districts) | **INTEGRATED**, 218/733 districts and growing (background fetch running, see `logs/gee_national_heartbeat.json`) | GEE (Google service account) | Let the national fetch finish; no new integration needed |
| Rainfall Monitor | CHIRPS via GEE | **INTEGRATED**, same 218/733 | GEE | Same as above |
| NDVI Analytics | UNDP DiCRA (MODIS-derived) | **INTEGRATED, MP's 52 districts only** | GEE (MODIS/Sentinel-2 collections are public in Earth Engine's catalog) | National extension is task #12 in this session's tracker -- real, not started |
| Crop Health | Sentinel-2 EVI/NDVI via GEE | **NOT INTEGRATED** -- Agriculture pane's Crop Health/NDVI Mean cards show "—" | Yes, Sentinel-2 L2A is public in GEE's catalog | Same national-NDVI effort as above would cover this |
| Soil Moisture | SMAP via GEE | **INTEGRATED, 733/733 districts (all 36 states/UTs) — national run completed 2026-08-12, see docs/DATA_SOURCES.md** (this row was stale -- written against the 2026-08-09 snapshot and never updated after the national run actually finished; corrected 2026-10-21) | Yes, NASA SMAP L3/L4 is public in GEE's catalog, no separate key | None -- done |
| Forest Monitor | FSI ISFR + Hansen/GFC | **NOT INTEGRATED**, honestly labeled (previously showed invented district risk levels and carbon-stock figures, removed per `docs/AUDIT_2026-08-01.md`) | Hansen/GFC (UMD Global Forest Change) is public in GEE's catalog; FSI's own ISFR reports are PDF-only, not an API | GEE layer is the realistic path; FSI would need a PDF-extraction pipeline like `extract_state_reports.py`'s |
| Satellite Viewer | GEE + Bhuvan (ISRO) WMS | **NOT INTEGRATED as a distinct viewer** -- doubles as the honest GEE-status panel (shows what's live vs not, see the panel's own "MODIS/LIVE, CHIRPS+ERA5-Land/IN PROGRESS, Sentinel-2/NOT INTEGRATED, SMAP/NOT INTEGRATED" table) | Bhuvan's WMS endpoints are public (no key) but historically rate-limited/unreliable for programmatic use; GEE tile layers already work (basemap switcher, Phase 5.1) | Low priority -- the honest-status table already does this panel's real job |
| Live Weather | NASA POWER | **NOT INTEGRATED, not even a placeholder panel exists in the current nav** | **Yes, confirmed free, no API key, no rate-limit registration needed** (`power.larc.nasa.gov/api`) | **Best next real-integration candidate in this table** -- simplest of everything listed here to wire up for real |
| Groundwater & Irrigation | CGWB / India-WRIS | **NOT INTEGRATED**, honestly labeled (Agriculture pane's GW Stress/Level/Recharge cards show "—", code comment confirms "requires CGWB/India-WRIS data, not integrated") | India-WRIS has a public portal but no documented open API found this pass; CGWB publishes groundwater-level PDFs/reports, not a machine API | Needs its own portal-discovery pass, same methodology as `docs/STATE_REPORTS.md`'s |
| Village Profile | Survey of India attribute table (NWDP) | **INTEGRATED**, 649,719 villages, 46 columns | n/a (static download, not a live API) | None -- done |
| Mandi Prices | AGMARKNET via data.gov.in | **INTEGRATED**, daily, all 733 districts | Yes, in active use (`scripts/fetch_mandi_prices.py`) | None -- done |
| Crop Statistics | DES (data.desagri.gov.in), legacy data.gov.in cross-check | **INTEGRATED nationally**, 372,904 records, 2000-01 to 2022-23 (this session) | Yes, DES's own endpoint (see `scripts/fetch_des_apy.py`) | State-report cross-checks (CHARAN 4) continuing state-by-state |
| Panchayat Dashboard | LGD + eGramSwaraj | **NOT INTEGRATED**, honestly labeled (previously showed invented Gram Panchayat names with fabricated vulnerability scores, removed) | eGramSwaraj has a public portal; no documented open bulk-data API found this pass | Needs its own portal-discovery pass |
| PMFBY Insurance | pmfby.gov.in / data.gov.in | **NOT INTEGRATED**, honestly labeled | **Yes, confirmed real** -- data.gov.in hosts "District-wise Details of Farmer Applications Insured under PMFBY" (found this pass, e.g. Madhya Pradesh 2021-22 to 2023-24), same OGD Platform API pattern already used for mandi/crop stats | Second-best next real-integration candidate -- same fetch pattern as `fetch_mandi_prices.py`/`fetch_crop_stats.py` would apply directly |
| Trend Forecast | Own OLS trend on real history | **INTEGRATED**, explicitly labeled "indicative" | n/a (derived, not fetched) | None -- done, matches METHODOLOGY.md's own rule that only CMIP6 may claim to be a real projection |
| Biodiversity Risk | ENVIS / India Biodiversity Portal | **NOT INTEGRATED**, honestly labeled (shares the Forest Monitor panel's "Not available" state) | India Biodiversity Portal has a public species-occurrence API (iNaturalist-style); ENVIS is mostly PDF reports per state/topic | Real but lower-value integration -- occurrence points don't map cleanly to district-level "biodiversity risk" without real methodology work first |
| Cadastral Map | MP Bhulekh / Bhu-Naksha | **Deliberately disabled** (`cadastral_loader.js` is a stub per CLAUDE.md: "disabled pending official MP Bhulekh / Revenue Dept. cadastral records -- do not re-enable with placeholder data") | Bhulekh has no public bulk API; would need an official data-sharing request | Institutional request required, not a fetch-script problem |
| Farmer Advisory | Derived from climate + crop + NDVI (no independent source) | **Partially integrated** -- draws on Agriculture pane's other cards, which are themselves a mix of integrated (rainfall) and not (crop health, soil, groundwater) | n/a (derived) | Quality is capped by its inputs -- SMAP/Sentinel-2 integration above would improve it directly |
| Kisan Sahayak | Cloudflare Worker (Workers AI) + IMD/DES/AGMARKNET context | **INTEGRATED** for the popup + real-data-first prompting; research-paper citation APIs (OpenAlex etc.) **not yet wired in** | Yes, all 8 named APIs (OpenAlex, Semantic Scholar, CORE, CrossRef, DOAJ, PubMed/PMC, FAO AGRIS, ICAR KRISHI) are free | Tracked separately as task #11 |

## Ranked next real-integration candidates (from this pass's research)

1. **NASA POWER** (Live Weather) -- confirmed free, keyless, no panel built yet at all. Simplest real win available.
2. **PMFBY via data.gov.in** -- confirmed a real district-wise dataset exists; same fetch-script pattern already proven twice (mandi, crop stats).
3. **SMAP via GEE** (Soil Moisture) -- no new credential needed (same GEE service account already in use), but competes with the national climate/NDVI fetches for the same compute budget.
4. Groundwater (India-WRIS) and Panchayat (eGramSwaraj) both need a real discovery pass (like `docs/STATE_REPORTS.md`'s) before it's known whether either has anything better than PDF reports.

## Not done this pass

Actually integrating any of the above -- this document is the audit/
research CHARAN itself, not the integration work. No panel's displayed
data changed as a result of writing this file.
