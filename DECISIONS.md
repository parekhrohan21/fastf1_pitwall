# 🧭 Architecture Decision Records — Pit Wall F1 Telemetry Dashboard

> **Audience:** engineers and AI agents who need to know *why* the code is the way it is, not just what it does.
> **Companions:** [README.md](README.md) (users) · [DOCS.md](DOCS.md) (pipeline and API manual) · [AGENT.md](AGENT.md) (maintenance rules; its "Key Design Decisions" are the short form of these records).

## How to read this file

Each record follows one format:

| Field | Meaning |
| --- | --- |
| **Issue / PR** | GitHub references. A PR is listed only where the repository history records it. |
| **Context** | The bottleneck, missing capability or data problem. |
| **Decision** | What was built. |
| **Maths & logic** | The equations or algorithm, where there is one. |
| **Alternatives & trade-offs** | What else was possible and why it was not used. |
| **Consequences & guardrails** | Cost, cache behaviour, failure handling and tests. |

**Provenance.** Records marked *(reconstructed)* describe older decisions. Their context and alternatives were
derived from the code, the issue text and `AGENT.md`, not from notes written at the time, so treat the
alternatives as the reasoning that fits the evidence rather than a contemporaneous record. Records ADR-021
onwards draw on review notes written during the work and include the defects found along the way.
Records are in roughly chronological order by issue number. Numbers in `AGENT.md` (Decision #n) are a different
sequence; the mapping is given in each record where one exists.

**Adding a record.** When a change involves an architectural choice or an algorithmic trade-off, append the next
`ADR-0nn` at the end of the log and add it to the index below (this is a Code Review checklist item in `AGENT.md`).

## Index

| ADR | Title | Issue |
| --- | --- | --- |
| [001](#adr-001--low-level-tls-impersonation-to-defeat-cdn-blocks) | Low-level TLS impersonation to defeat CDN blocks | #30, #36, #100 |
| [002](#adr-002--cache-safe-dataframes-for-streamlit) | Cache-safe DataFrames for Streamlit | #48 |
| [003](#adr-003--decompose-the-monolithic-apppy) | Decompose the monolithic `app.py` | #82 |
| [004](#adr-004--css-injection-instead-of-streamlit-theming) | CSS injection instead of Streamlit theming | #112 |
| [005](#adr-005--live-timing-through-the-fastf1-signalr-client) | Live timing through the FastF1 SignalR client | #84 |
| [006](#adr-006--grid-wide-heatmaps-with-dynamic-height) | Grid-wide heatmaps with dynamic height | #85 |
| [007](#adr-007--continuous-time-delta-per-metre) | Continuous time delta per metre | #116 |
| [008](#adr-008--undercut--overcut-detection-by-pit-pairing) | Undercut / overcut detection by pit pairing | #117 |
| [009](#adr-009--race-control-flags-as-chart-overlays) | Race control flags as chart overlays | #118 |
| [010](#adr-010--consistency-index-from-filtered-stint-variance) | Consistency index from filtered stint variance | #119 |
| [011](#adr-011--weather-correlation-by-as-of-merge) | Weather correlation by as-of merge | #120 |
| [012](#adr-012--multi-year-comparison-on-a-shared-distance-grid) | Multi-year comparison on a shared distance grid | #121 |
| [013](#adr-013--pdf-debrief-export-with-kaleido-and-fpdf2) | PDF debrief export with kaleido and fpdf2 | #122 |
| [014](#adr-014--predictive-tyre-degradation-and-the-thermal-cliff) | Predictive tyre degradation and the thermal cliff | #81, #137 |
| [015](#adr-015--multi-format-telemetry-export) | Multi-format telemetry export | #139 |
| [016](#adr-016--braking-dynamics-and-trail-braking-detection) | Braking dynamics and trail-braking detection | #148 |
| [017](#adr-017--gear-shift-strategy-and-rpm-power-bands) | Gear shift strategy and RPM power bands | #149 |
| [018](#adr-018--speed-trap-radar-and-power-unit-mapping) | Speed trap radar and power unit mapping | #150 |
| [019](#adr-019--fuel-corrected-pure-tyre-wear) | Fuel-corrected pure tyre wear | #151 |
| [020](#adr-020--teammate-battle-matrix) | Teammate battle matrix | #152 |
| [021](#adr-021--pit-lane-transit-loss-decomposition) | Pit lane transit loss decomposition | #153, #189 |
| [022](#adr-022--track-evolution-with-driver-fixed-effects-and-robust-regression) | Track evolution with driver fixed effects and robust regression | #154 |
| [023](#adr-023--corner-exit-traction-and-flat-out-detection) | Corner exit traction and flat-out detection | #155 |
| [024](#adr-024--weekend-progression-split-into-pure-and-io-layers) | Weekend progression split into pure and I/O layers | #156 |
| [025](#adr-025--dirty-air-zones-with-clean-air-detrending) | Dirty air zones with clean-air detrending | #157 |
| [026](#adr-026--brag-video-from-a-pca-latent-manifold) | Brag video from a PCA latent manifold | #171 |
| [027](#adr-027--code-review-findings-live-in-the-code) | Code review findings live in the code | #123 (superseded) |
| [028](#adr-028--a-dedicated-decisions-log) | A dedicated decisions log | #172 |

---

## ADR-001 — Low-level TLS impersonation to defeat CDN blocks

**Issue / PR:** #30, #36, #100 · *(reconstructed)* · `AGENT.md` Constraint "Requests monkey-patching"

**Context.** Streamlit Community Cloud runs on datacentre IP ranges. F1's live-timing CDN (CloudFront) and the
FastF1 mirror (Cloudflare) answered those with HTTP 403 whenever the TLS fingerprint did not look like a browser.
The first fix (#36) patched `requests`, but FastF1 builds its own `requests_cache.CachedSession` subclass, so
the patch missed the calls that mattered (#30).

**Decision.** Intercept `requests.adapters.HTTPAdapter.send` — the lowest layer every `requests.Session`
subclass goes through — and perform the request with `curl_cffi` using `impersonate="chrome124"`, so the
JA3/JA4 handshake matches a real Chrome build. The returned object is a `requests.Response` look-alike whose
`raw` attribute is a `MockRaw`. Connection state is exposed through `_PATCH_STATUS` and a diagnostics expander (#100).

**Alternatives & trade-offs.**
- *Patching `requests.get`/`Session.request`*: rejected — higher layers are bypassed by FastF1's own session class (the #30 failure).
- *A user-supplied proxy*: kept as an option (`F1_PROXY`) but cannot be the default; most users have none.
- *Rotating user-agents only*: does not change the TLS fingerprint, which is what the CDN inspects.
- Cost: a binary dependency (`curl-cffi`) and a patch that must keep up with Chrome versions.

**Consequences & guardrails.** `requests_cache` serialises `resp.raw`; if it is `None` the cache crashes with
`AttributeError: 'NoneType' object has no attribute '_request_url'`, hence the mandatory `MockRaw`.
Failures are surfaced, not swallowed (a clear error for 401/403 from the live-timing server). Covered by `test_curl_cffi_request` in `src/data/loader.py` and a sidebar diagnostic.

---

## ADR-002 — Cache-safe DataFrames for Streamlit

**Issue / PR:** #48 · *(reconstructed)* · `AGENT.md` Decision #4 and the `_all_laps` coding standard

**Context.** `@st.cache_data` hashes every argument. `fastf1.core.Laps` and `fastf1.core.Session` are pandas
subclasses with custom state, so passing them raises `UnhashableParamError` (first seen on the results DataFrame, #48).
Accessing `st.session_state["session"]` *inside* a cached function would also make the cache key lie, because the
session would not be part of it.

**Decision.**
1. Convert once, after load: `_all_laps = pd.DataFrame(sess.laps.copy())` and pass that plain DataFrame in.
2. Pass the session as an argument whose name starts with an underscore (`_sess_obj`, `_results_df`), which tells Streamlit not to hash it.
3. Every cached builder takes `sess_k` (`"{year}_{gp}_{session}"`) so the key identifies the session.
4. Inside builders filter with `laps_df[laps_df["Driver"] == drv]`, never `.pick_drivers()`, which only exists on `Laps`.

**Alternatives & trade-offs.**
- *`hash_funcs` for `Laps`*: hashes a large object on every rerun, and a hash that ignores state is unsound.
- *Caching in `st.session_state` instead*: no TTL, no cross-session sharing, and the logic cannot be unit-tested without Streamlit.
- Cost: one DataFrame copy per load; builders cannot call FastF1 convenience methods.

**Consequences & guardrails.** TTL is 3600 s on all cached builders. The same rule explains why the Pit Lane
section once never rendered (the call passed raw `Laps`; fixed in #189, ADR-021). Checked in every code review.

---

## ADR-003 — Decompose the monolithic `app.py`

**Issue / PR:** #82 · *(reconstructed)* · `AGENT.md` Decision #1 and #17

**Context.** `app.py` had grown to hold data loading, CSS, chart builders and layout in one script, which made
chart code untestable and edits risky.

**Decision.** Split into `src/data/loader.py` (fetching, caching, statistics), `src/charts/{plotly,matplotlib}.py`
(figure builders, no Streamlit state), `src/ui/{styles,components}.py` (CSS and section renderers) and keep `app.py`
as orchestration only. State such as `driver1`, `compare` and `sess_key` is passed explicitly as arguments.

**Alternatives & trade-offs.**
- *Keeping one file with sections*: no import boundaries, so nothing stops UI code reaching into data code.
- *Classes / a framework layer*: rejected as over-engineering for a linear Streamlit script and out of scope under the escalation rules.
- *Reading `st.session_state` from modules*: would create circular imports and hidden inputs, so state is injected instead.

**Consequences & guardrails.** Pure builders can be tested with synthetic DataFrames (the whole pytest suite relies on it).
Direction of imports is `ui → charts → data` and `ui → data`, never the reverse. `app.py` carries an architecture docstring and a note under every section.

---

## ADR-004 — CSS injection instead of Streamlit theming

**Issue / PR:** #112 · *(reconstructed)* · `AGENT.md` Key Design Decision #2 and Decision #19

**Context.** Streamlit's theme API cannot reach BaseWeb internals or switch constructor accent colours at runtime.

**Decision.** Inject raw CSS with `st.markdown(..., unsafe_allow_html=True)` from `inject_styles()`, driven by `st.session_state["dark_mode"]`, and call it early on every rerun.
Never apply a `forwards`/`infinite` transform animation to `[data-testid="stSidebar"]` itself — it overrides Streamlit's inline collapse transform, so the sidebar cannot slide away on mobile; scope entry transitions to `section[data-testid="stSidebar"][data-collapsed="false"]`.

**Alternatives & trade-offs.** *`.streamlit/config.toml` themes*: static, no per-constructor colour. *A component library*: new dependency for cosmetic gain. Cost: selectors depend on Streamlit's DOM and can break on upgrade.

**Consequences & guardrails.** `dark_mode` is initialised inside `inject_styles()` and `_toggle_theme()`, not only at import time (an import-time guard runs once per process, not per browser session — a defect recorded in the `app.py` review notes). Known limitation: the first theme toggle may not repaint the top bar.

---

## ADR-005 — Live timing through the FastF1 SignalR client

**Issue / PR:** #84 · *(reconstructed)* · `AGENT.md` Decision #18

**Context.** Static timing databases appear on F1's CDN hours after a session. Users wanted data during one.

**Decision.** Record the SignalR stream with `fastf1.livetiming` on a background thread (`start_live_recorder`, `stop_live_recorder`, `get_live_recorder_status`), parse the file with `load_live_session`, and add a banner and auto-refresh control. A 401/403 from the live-timing server produces a clear error, not a traceback.

**Alternatives & trade-offs.** *Polling the REST timing endpoints*: not offered by the API FastF1 wraps. *A separate service*: adds hosting; a thread is enough for one user. Cost: thread lifecycle is module-global (`_LIVE_RECORDERS`, `_LIVE_THREADS`).

**Consequences & guardrails.** Covered by `tests/test_live_timing.py`. Documented as a limitation: only works while a session is live.

---

## ADR-006 — Grid-wide heatmaps with dynamic height

**Issue / PR:** #85 · *(reconstructed)* · `AGENT.md` Decision #20

**Context.** Comparing 3–20 drivers needs a matrix view, and a fixed-height chart makes 20 rows unreadable.

**Decision.** `_build_grid_heatmap_data` produces three modes (sector split deltas, lap-by-lap pace, top-speed matrix); `build_grid_heatmap_fig` sets figure height from the number of drivers and uses broadcast-style colour scales.

**Alternatives & trade-offs.** *Tables with conditional formatting*: no hover detail. *One chart per driver*: no cross-driver comparison. Cost: wide matrices need horizontal care on mobile.

**Consequences & guardrails.** `tests/test_grid_heatmap.py`. Cached with TTL 3600 s and keyed on `sess_k` plus the selected drivers.

---

## ADR-007 — Continuous time delta per metre

**Issue / PR:** #116 · *(reconstructed)* · `AGENT.md` Decision #21

**Context.** A speed delta says *where* a driver is faster but not how much time that is worth.

**Decision.** In compare mode `build_time_delta_chart` plots `fastf1.utils.delta_time(lap_ref, lap_comp)` against distance: the cumulative time gained or lost (s) at every metre.

**Maths & logic.** `delta_time` aligns both laps on distance and returns $\Delta t(d) = t_{\text{comp}}(d) - t_{\text{ref}}(d)$; a rising curve means the compared driver is losing time.

**Alternatives & trade-offs.** *Integrating the speed difference ourselves*: `delta_time` already handles resampling and is maintained upstream. Cost: depends on lap telemetry from both drivers, so it is hidden when either is missing.

**Consequences & guardrails.** Drawn below the speed delta chart so both share the distance axis.

---

## ADR-008 — Undercut / overcut detection by pit pairing

**Issue / PR:** #117 · *(reconstructed)* · `AGENT.md` Decision #22

**Context.** Strategy battles are defined by two cars' pit stops a few laps apart, which is not visible in a lap-time chart.

**Decision.** Pair adjacent pit stops of the two drivers within ±3 laps, compute the gap before and after the pit window (from `Time` at lap `min − 1` to `max + 2`) and classify the outcome; `build_undercut_chart` plots the gap through the window.

**Alternatives & trade-offs.** *Modelling pit loss and tyre offset to simulate hypotheticals*: needs inputs the data does not contain. The ±3-lap rule is a heuristic, not a law; two stops further apart are not treated as a battle.

**Consequences & guardrails.** The loop variables are `_u_lap1`/`_u_lap2` so they do not overwrite the selected lap objects (a bug found in the #177 review), and the gap is read from per-driver frames, not from whichever driver's row comes first.

---

## ADR-009 — Race control flags as chart overlays

**Issue / PR:** #118 · *(reconstructed)* · `AGENT.md` Decision #23

**Context.** Safety Car and flag periods explain pace anomalies, but only if they appear on the same axis as the pace.

**Decision.** `_build_race_control_messages` classifies `race_control_messages` (SC, VSC, Red, Yellow, Clear, Investigation); `_add_flag_zones` draws translucent `add_vrect` bands on the Lap Time History and Gap to Leader charts; a searchable Race Control Feed table sits below.

**Alternatives & trade-offs.** *Dropping affected laps silently*: hides why. *Shading by `TrackStatus` per lap only*: coarser than the message feed. Cost: messages are absent for some sessions, so the builder returns `None` and the overlay is skipped.

---

## ADR-010 — Consistency index from filtered stint variance

**Issue / PR:** #119 · *(reconstructed)* · `AGENT.md` Decision #26

**Context.** "Who is consistent?" is confounded by pit laps, Safety Car and traffic.

**Decision.** `_build_consistency_analysis` removes in-laps, out-laps and Safety Car / Red Flag laps, then computes the lap-time standard deviation per stint, a 0–100% Consistency Score, clean-air pace and a traffic deficit (s/lap). Violin and box plots show the distribution.

**Alternatives & trade-offs.** *Raw standard deviation over all laps*: dominated by pit laps. *Coefficient of variation*: hides absolute pace. Cost: very short stints give unstable scores.

**Consequences & guardrails.** `tests/test_consistency.py`. The traffic deficit here is a coarse measure; ADR-025 later replaced the guesswork with measured gaps.

---

## ADR-011 — Weather correlation by as-of merge

**Issue / PR:** #120 · *(reconstructed)* · `AGENT.md` Decision #27

**Context.** Weather samples arrive on their own clock, not on lap boundaries.

**Decision.** `_build_weather_correlation_data` uses `pd.merge_asof` on the lap completion time `Time`, with `direction="nearest"`, so each lap gets the weather reading closest in time to its completion. A dual-axis chart overlays track temperature on pace; Pearson $r$ quantifies the link and rain-crossover windows are detected.

**Alternatives & trade-offs.** *Interpolating weather onto laps*: invents values between samples. *A backward-only merge*: always lags by up to one sampling interval, whereas the nearest reading is never further away than that. Cost: the nearest reading can come from just after the lap ended. Correlation is not causation — tyre wear and fuel burn are also time-correlated.

**Consequences & guardrails.** `tests/test_weather_correlation.py`. `weather_data` access is wrapped so a session loaded with `weather=False` degrades to a message (see ADR-022).

---

## ADR-012 — Multi-year comparison on a shared distance grid

**Issue / PR:** #121 · *(reconstructed)* · `AGENT.md` Decision #28

**Context.** Two laps from different years have different sample times and slightly different lengths.

**Decision.** `_build_multi_year_comparison` interpolates both laps onto a common 500-point grid from 0 to the shorter lap's maximum distance and computes $\Delta v = v_1 - v_2$ and a time delta, falling back to $\Delta t \approx \sum (1/v_1 - 1/v_2)\,\Delta x$ when `Time` is missing.

**Alternatives & trade-offs.** *Aligning by sample index*: wrong when sampling rates differ. *Per-corner comparison*: circuits change between eras. Cost: 500 points can smooth very short features such as brief lifts.

**Consequences & guardrails.** `tests/test_multi_year_comparison.py`. Only meaningful for the same circuit; layout changes between years are not detected.

---

## ADR-013 — PDF debrief export with kaleido and fpdf2

**Issue / PR:** #122 · *(reconstructed)* · `AGENT.md` Decision #25

**Context.** Users wanted a printable post-race summary of what they had analysed.

**Decision.** `_build_pdf_report` renders the figures collected during the run to images with `kaleido`, lays them out with `fpdf2` and `Pillow`, and offers the file from the sidebar.

**Alternatives & trade-offs.** *Browser print*: unreliable with Streamlit's layout. *HTML to PDF via a headless browser*: a much heavier dependency. Cost: three extra dependencies (`kaleido`, `fpdf2`, `Pillow`).

**Consequences & guardrails.** Figures are collected as the page renders, so the PDF only contains sections that were actually shown.

---

## ADR-014 — Predictive tyre degradation and the thermal cliff

**Issue / PR:** #81, #137 · *(reconstructed)* · `AGENT.md` Decisions #16 and #30

**Context.** A degradation slope says how fast a tyre loses pace, not when it falls off a cliff.

**Decision.** `_build_tyre_deg_data` keeps flyer laps (`IsAccurate`, no yellow / SC / VSC status), fits an OLS line for stints with ≥ 4 valid laps, and a quadratic $t = a x^2 + b x + c$ in tyre age $x$ for stints with ≥ 5 laps. The cliff is the age at which pace has dropped by a threshold above the base pace:

$$a x^2 + b x + (c - t_{\text{cliff}}) = 0,\qquad t_{\text{cliff}} = \text{base pace} + 1.5\,\text{s},\qquad x_{\text{cliff}} = \frac{-b + \sqrt{b^2 - 4a(c - t_{\text{cliff}})}}{2a}$$

The pit window is $x_{\text{cliff}} \pm 3$ laps. Only $a > 10^{-9}$ with a non-negative discriminant produces a cliff; otherwise the linear fit is used.

**Alternatives & trade-offs.** *Higher-order polynomials*: overfit 5–10 points. *Piecewise "knee" models*: unstable on short stints. The issue text proposed a 0.5 s threshold; the implemented and documented value is **1.5 s**, (see `CLIFF_THRESHOLD_S` in `_build_fuel_decoupled_tyre_deg`).

**Consequences & guardrails.** `tests/test_tyre_crossover.py`. The full-field `render_tyre_crossover_matrix` shows urgency (🟢/🟡/🔴/✅) so a wide extrapolation is visible, not hidden. The cliff is a model, not a measurement.

---

## ADR-015 — Multi-format telemetry export

**Issue / PR:** #139 · *(reconstructed)* · `AGENT.md` Decision #32

**Context.** CSV loses types and is slow for ~10 Hz telemetry across many channels.

**Decision.** Offer CSV, Apache Parquet (`pyarrow`) and JSON from one panel, all produced by `_build_export_telemetry_df`, which injects a uniform metadata block (`Driver`, `LapNumber`, `LapTime`, `Compound`, sector times in seconds) and renames `nGear` to `Gear`.

**Alternatives & trade-offs.** *Separate frames per format*: the three outputs would drift. *Excel*: row limits and a heavier dependency. Cost: `pyarrow` is a large wheel.

**Consequences & guardrails.** `tests/test_telemetry_export.py` covers the three serialisers.

---

## ADR-016 — Braking dynamics and trail-braking detection

**Issue / PR:** #148 · *(reconstructed)* · `AGENT.md` Decision #33

**Context.** Raw `Brake` is a boolean, so it cannot say how hard or how late a driver brakes.

**Decision.** `_calculate_braking_metrics` slices $[d_{\text{apex}} - 350\,\text{m},\, d_{\text{apex}} + 100\,\text{m}]$ and derives longitudinal acceleration from speed:

$$G = \frac{\Delta v}{\Delta t \cdot 9.81}\quad(\text{negative = braking})$$

smoothed with a centred 3-point moving average and clipped to $[-6.0, 2.5]$ G. It extracts the initial braking point, peak deceleration, the trail-braking release point and distance, and the brake-to-throttle transition time (ms).

**Alternatives & trade-offs.** *Differentiating unsmoothed speed*: quantisation noise creates spurious peaks. *A longer filter*: flattens the peak that is being measured. The clip removes sensor glitches that no car can produce.

**Consequences & guardrails.** `tests/test_braking_analysis.py`. The same 3-point centred smoothing is reused for exit acceleration (ADR-023).

---

## ADR-017 — Gear shift strategy and RPM power bands

**Issue / PR:** #149 · *(reconstructed)* · `AGENT.md` Decision #34

**Context.** Whether a driver short-shifts or runs to the limiter shows up in RPM at the shift, which no existing chart reported.

**Decision.** `_calculate_gear_shift_metrics` finds upshifts and downshifts from changes in the gear channel, classifies a **short shift** as RPM $< 11{,}000$ with throttle $> 60\%$ (and gear ≥ 2), a **redline shift** as RPM $\ge 11{,}800$, and reports usage per gear (1–8).

**Alternatives & trade-offs.** *Using per-car power curves*: not available. Fixed thresholds are tuned to current rev limits, so they must be revisited if regulations change the limit.

**Consequences & guardrails.** `tests/test_gear_shifts.py`.

---

## ADR-018 — Speed trap radar and power unit mapping

**Issue / PR:** #150 (PR #166) · *(reconstructed)* · `AGENT.md` Decision #35

**Context.** Straight-line speed reveals aerodynamic efficiency and power unit strength, but only when sensors and teams are comparable.

**Decision.** Use the four official sensors (`SpeedST`, `SpeedI1`, `SpeedI2`, `SpeedFL`) on a polar radar with a grid-maximum baseline; compute the DRS boost as the difference between DRS-open and closed speed-trap entries; map constructors to power unit suppliers (Ferrari, Mercedes, Red Bull Powertrains, Renault) in `get_power_unit_supplier`.

**Alternatives & trade-offs.** *Telemetry max speed*: not tied to a fixed measuring point, so values are less comparable between drivers. *Fetching PU mapping from an API*: none exists in the data source, so it is a maintained table and **must be updated each season**.

**Consequences & guardrails.** `tests/test_speed_trap.py`.

---

## ADR-019 — Fuel-corrected pure tyre wear

**Issue / PR:** #151 (PR #167) · *(reconstructed)* · `AGENT.md` Decisions #16 and #36

**Context.** Fuel burn (~0.3 kg/lap, about 0.035 s/lap) makes cars faster as a stint goes on, which hides tyre wear.

**Decision.** Normalise every lap to a zero-fuel reference:

$$t_{\text{corr}} = t_{\text{lap}} - \alpha\,(N_{\text{laps}} - n_{\text{lap}}),\qquad \alpha = 0.035\ \text{s/lap (adjustable 0.010–0.070)}$$

With tyre age $x$ increasing by one per lap within a stint, $n_{\text{lap}} = n_0 + x$, so $t_{\text{corr}} = t_{\text{lap}} + \alpha x + \text{const}$ and therefore

$$\text{Slope}_{\text{true}} = \text{Slope}_{\text{raw}} + \alpha .$$

The corrected series is fitted with OLS and a quadratic, giving the True Degradation Rate and the *fuel masking offset* (how much degradation fuel burn was hiding).

**Alternatives & trade-offs.** *A fixed correction baked into charts*: the true value varies with circuit and car, so $\alpha$ is user-adjustable. *Modelling fuel mass explicitly*: needs inputs we do not have. Cost: a single $\alpha$ for all drivers.

**Consequences & guardrails.** `tests/test_fuel_decoupled_tyre_deg.py`. The raw and corrected rates are both shown so the assumption is visible.

---

## ADR-020 — Teammate battle matrix

**Issue / PR:** #152 (PR #169) · *(reconstructed)* · `AGENT.md` Decision #37

**Context.** The cleanest car-controlled comparison in F1 is a driver against their own teammate.

**Decision.** `_build_teammate_battle_data` pairs drivers by team from session results. With three or more drivers for one constructor (reserve or mid-season changes) it keeps the top two ordered by classification position, then by number of laps (`_drv_rank`); a team with fewer than two drivers is skipped. It compares qualifying best laps ($\Delta s$, $\Delta\%$), sector bests and micro-sector dominance, and clean-air median race pace that excludes in-laps, out-laps, Safety Car laps and laps $> 107\%$ of the driver's median. A diverging bar chart is centred on parity ($\Delta = 0$).

**Alternatives & trade-offs.** *Pairing by car number*: breaks when numbers change. *Mean race pace*: dominated by outliers; the median is robust. Cost: any driver beyond the top two for a team is not shown.

**Consequences & guardrails.** `tests/test_teammate_battle.py`.

---

## ADR-021 — Pit lane transit loss decomposition

**Issue / PR:** #153, #189 (PR #191) · `AGENT.md` Decision #38

**Context.** "How long was the stop" mixes three things: the in-lap, the time in the pit lane, and the out-lap warm-up.

**Decision.** `_build_pit_transit_data` computes, against a clean-air baseline $t_{\text{base}}$ (median of valid flyers):

$$t_{\text{pit lane}} = \text{PitOutTime} - \text{PitInTime},\quad \Delta t_{\text{in}} = t_{\text{in}} - t_{\text{base}},\quad \Delta t_{\text{out}} = t_{\text{out}} - t_{\text{base}}$$
$$\Delta t_{\text{total}} = (t_{\text{in}} + t_{\text{out}}) - 2\,t_{\text{base}}$$

plus out-lap sector deltas $S_1, S_2, S_3$ against clean sector baselines. A stacked horizontal bar chart (amber in-lap, cyan transit, purple out-lap) and a ranked leaderboard present the result.

**Alternatives & trade-offs.** *Using `PitOutTime − PitInTime` alone*: ignores the time lost either side. A single baseline for the whole race ignores fuel burn, so late-race stops look slightly better than they were.

**Consequences & guardrails.**
- The section silently never rendered at first: it passed raw `Laps` and an un-prefixed session to a cached function and a bare `except` hid the error (ADR-002). Fixed by passing `_all_laps1` and `_sess_obj`.
- #189 fixed the leaderboard: NaN-safe ranking on `(net_loss, pit_lane_time, in_lap)`, alias maps so either abbreviation or car number matches, a sanitised radio state and theme-safe colours.
- `tests/test_pit_transit_loss.py` (12 tests).

---

## ADR-022 — Track evolution with driver fixed effects and robust regression

**Issue / PR:** #154 (PR #179) · `AGENT.md` Decision #39 · detailed review notes in `src/data/loader.py`

**Context.** The track gets faster as rubber is laid down, but the field is not a clean sensor: slow cars stop running after Q1/Q2, and traffic laps contaminate any fit.

**Decision.**
1. **Filter:** green-flag flyers within 107% of the session best.
2. **Driver fixed effects:** subtract each driver's median flyer and add back the field median, $t_{\text{adj}} = t_{\text{lap}} - \tilde{t}_{\text{driver}} + \tilde{t}_{\text{field}}$. Drivers with one flyer are plotted but not fitted.
3. **Robust fit:** seed with a **Theil–Sen** estimate $\hat\beta = \operatorname{median}\{(t_j - t_i)/(x_j - x_i)\}$ (about 29% breakdown point), then trim by MAD residuals, $|r| \le \sigma \cdot \max(1.4826\,\text{MAD},\, 1\,\text{ms})$.
4. Report ramp rate (ms/min), total grip gain (s), a quadratic trend and the temperature profile. Gated to Practice and Qualifying.

**Alternatives & trade-offs (each found by a failing test or real data).**
- *OLS seed for the trim*: the reference line is tilted by the outliers being rejected; it returned $-0.0405$ for a true $-0.02$.
- *No scale floor*: after the first trim the residuals were near zero, MAD collapsed and 30 points became 3. Fix: a 1 ms floor (timing resolution) and a 0.5 minimum inlier fraction.
- *Pooling raw lap times*: the knockout bias inflated the ramp two to three times (2024 Bahrain Q: −28.5 → −10.0 ms/min).
- *Quadratic or LOESS as the headline*: rejected for the rate; the quadratic is kept only for display.

**Consequences & guardrails.** `tests/test_track_evolution.py` includes a regression for the knockout bias. Theil–Sen is $O(n^2)$ and subsamples deterministically above 200,000 pairs. Race and Sprint are excluded because fuel burn swamps the signal.

---

## ADR-023 — Corner exit traction and flat-out detection

**Issue / PR:** #155 (PR #182) · `AGENT.md` Decisions #40 and #41 · review notes in `src/data/loader.py`

**Context.** Throttle pick-up quality separates drivers on corner exit, but the first version gave flat-out corners a confident score.

**Decision.** Slice $[d_{\text{apex}} - 60,\, d_{\text{apex}} + 260]$ m. Extract distance to initial and 100% throttle, ramp rate $100/\Delta d$ (%/m), gradient $100/\Delta t$ (%/s), hesitations (running-envelope drops $\ge 3.5\%$), exit speed at 100 m, peak exit acceleration (3-point-smoothed $G$), oversteer corrections where steering data exists, and a 0–100 Traction Aggression Score computed last. A corner is **flat out** when throttle within ±10 m of the apex stays $\ge 85\%$ (`FLAT_OUT_THROTTLE_PCT`); pick-up metrics and the score are then `None`. A closed-to-full pick-up between two samples is measured from the preceding sample.

**Alternatives & trade-offs.** *A ±35 m flat-out window*: picks up the next corner's lift (VER at T5). *A 90% threshold*: misclassifies a 88% breath (T12) as a pick-up. *Scoring every corner*: produced a fabricated ~75 for corners that need no traction.

**Consequences & guardrails.** `tests/test_traction_exit.py` (11 tests; boundaries at 90% and 60%). The steering channel is absent from FastF1 car data, so the oversteer count is `None` on real data and the score only penalises truthy counts.

---

## ADR-024 — Weekend progression split into pure and I/O layers

**Issue / PR:** #156

**Context.** Tracing a driver across FP1 → Race needs up to five session loads, which is slow, network-bound and hard to test.

**Decision.** Three functions: `_summarise_weekend_session` (pure, one session to one summary), `_aggregate_weekend_progression` (pure, summaries to deltas, mileage, tyre matrix, improvement) and `_build_weekend_progression_data` (cached I/O). Sessions load laps-only (`telemetry=False`); a failing session is listed under `skipped`. The UI sits behind a button. Improvement is reported as the raw practice → qualifying delta **and** as the change in gap to the session best, because the latter removes track evolution.

**Alternatives & trade-offs.** *Loading all sessions on page load*: multiplies first-load time. *Raw delta only*: misattributes track evolution to the car. *Mileage in km from lap count × circuit length*: circuit length is only known from telemetry, so it is passed in from the loaded session and omitted when unavailable.

**Consequences & guardrails.** `tests/test_weekend_progression.py`. Event name is read from the loaded session (`sess.event`), not the sidebar, which may have changed. Not verified in a browser.

---

## ADR-025 — Dirty air zones with clean-air detrending

**Issue / PR:** #157

**Context.** Traffic costs pace, but lap times also fall through a race as fuel burns, so a naive clean-versus-dirty comparison is biased.

**Decision.** Gap to the car ahead comes from the session clock at lap completion (`Time`) for the car exactly one position ahead, averaged with the lap-start gap. Zones: Clean Air $> 2.5$ s (the leader counts as clean), Dirty Air $0.8$–$2.5$ s, DRS / Battle $< 0.8$ s. Lap times are detrended against lap number and compared by median; the deficit is $\text{median}(\text{dirty}) - \text{median}(\text{clean})$ (positive = slower). Overtaking success is the share of battle runs, including the following lap, in which the driver gained a place without pitting.

**Alternatives & trade-offs.**
- *Fitting the trend on all laps* (the first version): traffic clusters early or late, so the fit absorbed the very effect being measured and biased the clean median; a failing test caught it. The slope is now fitted on **clean-air laps only**, and no trend is removed with fewer than five of them.
- *Cumulating `LapTime` for gaps*: errors build up where a lap time is missing.
- The sign follows "dirty − clean", the reverse of the issue text, so positive means time lost.

**Consequences & guardrails.** `tests/test_dirty_air.py`. Known limitation: a pass made because the car ahead pitted or retired is not filtered out, so the success rate can read slightly high. Race and Sprint only.

---

## ADR-026 — Brag video from a PCA latent manifold

**Issue / PR:** #171

**Context.** The issue asked for shareable highlight clips driven by a "latent space" of telemetry, with no committed machine-learning stack.

**Decision.**
- **Latent manifold:** standardise the available channels (speed, throttle, brake, RPM, gear, DRS, $a_{\text{lon}}$, $a_{\text{lat}}$) to $z$-scores and take the top $k = 3$ principal components by SVD, $Z = X_{\text{std}} V_k$, smoothed with a 5-point moving average. $a_{\text{lat}} = v^2 \kappa / 9.81$ with curvature $\kappa = \dot\theta / \dot s$ from the X/Y heading.
- **Moments:** top speed, peak braking (below −0.5 G), the *highest* apex speed among minima with $\ge 20$ km/h prominence (`scipy.signal.find_peaks`), and purple / personal-best sectors.
- **Frames:** a cubic spline over $z(t)$ on the frame clock; Pillow draws each frame and streams it into the encoder.
- **Encoding:** MP4 through `imageio` + `imageio-ffmpeg`, with an animated-GIF fallback so the feature never hard-fails.

**Alternatives & trade-offs.**
- *scikit-learn PCA or an autoencoder*: a heavy dependency for a three-component projection that SVD gives directly; an autoencoder would also need training data.
- *A ±5-sample window for apex detection* (first version): never fired on shallow corners; replaced after a test failed.
- *Matplotlib for frames*: a heavier per-frame figure pipeline than direct Pillow drawing (not benchmarked here).
- *MP4 only*: fails on a bare install.
- Deviations from the issue text: the data builder takes the lap's telemetry DataFrame, and `generate_brag_video_frames` returns `(bytes, mime)` because the container can change.

**Consequences & guardrails.** `tests/test_brag_video_latent.py` (16 tests). Frame counts are capped (`MAX_FRAMES`, `GIF_MAX_FRAMES`) and playback speed is adjustable; generation runs only on a button press. **Not verified here:** the MP4 path (no ffmpeg in the test environment), real FastF1 telemetry and in-browser playback.

---

## ADR-027 — Code review findings live in the code

**Issue / PR:** #123 (original process) · superseded by this change · `AGENT.md` Decision #44

**Context.** The original process required a separate `code_review_issue_<n>.md` per change. They drifted out of date (one still described defects that had since been fixed) and sat far from the code they described.

**Decision.** Review findings are recorded as `# ── Review notes (#n) ──` comment blocks directly above the code they cover, and the standalone files were removed. Architectural reasoning that outlives a single change belongs here, in this log.

**Alternatives & trade-offs.** *Keeping the files*: easy to read as a changelog but unversioned against the code. *PR descriptions only*: lost once the PR is closed. Cost: comments are less discoverable than a file listing, so this log indexes the important ones.

---

## ADR-028 — A dedicated decisions log

**Issue / PR:** #172

**Context.** `AGENT.md` keeps decisions short for an agent to follow, and `DOCS.md` describes the pipeline. Neither records the alternatives rejected or the maths behind a choice, so the same questions were being re-derived.

**Decision.** Maintain this file, one ADR per decision, in the format above. It does not replace the other two documents: `AGENT.md` holds the rule, `DOCS.md` the mechanism, `DECISIONS.md` the reasoning.

**Consequences & guardrails.** Adding a record is a Code Review checklist item. Older records are marked *(reconstructed)* so nobody mistakes inferred rationale for a contemporaneous one.
