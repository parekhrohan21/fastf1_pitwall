# Code Review — Issue #154: Track Evolution & Grip Improvement Ramp Index

**Branch**: `feat/issue-154-track-evolution-ramp-index`
**Reviewer**: Software Development & Maintenance Agent
**Date**: 2026-09-29

---

## Summary of Change

Adds a Track Evolution & Grip Improvement Ramp Index section that models circuit rubbering-in across Practice and Qualifying sessions.

| File | Change |
| --- | --- |
| `src/data/loader.py` | Added `_theil_sen_estimate`, `_robust_linear_fit`, and `_build_track_evolution_data`. |
| `src/charts/plotly.py` | Added `build_track_evolution_fig` (dual-axis field scatter + evolution trend curve + track temperature profile). |
| `src/ui/components.py` | Added `_render_track_evolution_section` (3 metric cards, condition banner, chart, caption) and imports. |
| `app.py` | Wired the section in after the Weather Correlation block, passing `session_type`. |
| `tests/test_track_evolution.py` | New — 9 tests covering the estimator, filtering, classification, weather merge, failure modes and figure construction. |
| `README.md`, `DOCS.md`, `AGENT.md` | Documentation sync (see below). |

---

## Defects found and fixed during review

Two genuine defects were caught by the new tests and fixed before commit; both are worth recording because they were silent failures, not crashes.

1. **Trim-band collapse in `_robust_linear_fit`.** After the first iteration removed the gross outliers, the surviving near-linear points had residuals of ~0, so MAD collapsed toward zero and the next iteration's band rejected almost every remaining point (30 points → 3). Fixed with a `scale_floor` of 1 ms — matching F1 lap timing resolution, so the band can never shrink below the precision of the measurement — plus a `min_inlier_frac` (0.5) backstop.

2. **OLS seed produced a ~2x wrong slope.** Seeding the residual trim with ordinary least squares meant the reference line was itself tilted by the outliers being rejected; the band then discarded the *clean* laps at both ends of the session and kept the outliers near the crossing point, returning `-0.0405` where the true slope was `-0.02`. Fixed by seeding with a Theil-Sen estimator (`_theil_sen_estimate`, median of pairwise slopes, ~29% breakdown point). This also removed a bias in the multi-car case where slower cars systematically set laps slightly later in the session.

A third robustness issue was fixed proactively: `hasattr(_session_obj, "weather_data")` sat **outside** the inner `try`. FastF1 exposes `weather_data` as a property that raises when a session was loaded with `weather=False`, and a non-`AttributeError` would escape to the outer handler and return `None` for the entire evolution model over a merely-missing temperature trace. Now uses `getattr(..., None)` inside the `try`. Covered by `test_build_track_evolution_data_survives_broken_weather_object`.

---

## Correctness

- [x] No `st.session_state["session"].laps` accessed inside a `@st.cache_data` function — `laps_df` is passed in explicitly from `_all_laps1`.
- [x] `laps_df` received as `pd.DataFrame(sess.laps.copy())` — uses the existing `_all_laps1` extraction; no raw `fastf1.core.Laps` is hashed.
- [x] Driver filtering uses boolean masking (`laps[laps["Driver"].isin(...)]`, `laps["Driver"] == drv`) — no `.pick_drivers()` on a plain DataFrame.
- [x] New `@st.cache_data` function `_build_track_evolution_data` includes `sess_k: str` in its signature; the FastF1 session is passed as `_session_obj` (underscore-prefixed, unhashed).
- [x] All UI showing driver identifiers routes through `fmt_func` (`_fmt_driver1`) into `labels_map`.
- [x] No new inline compound colour dicts — this feature does not colour by compound; driver colours come from the caller's `highlight_colours`.

## Code quality

- [x] Type hints on all new function signatures.
- [x] One-line (plus extended) docstrings on `_theil_sen_estimate`, `_robust_linear_fit`, `_build_track_evolution_data`, `build_track_evolution_fig`, and `_render_track_evolution_section`.
- [x] Section headers follow the `# ── Name ──────` convention within the new functions.
- [x] `plt.close(fig)` — not applicable; this feature adds no Matplotlib figures.
- [x] All FastF1 / data access wrapped in `try/except Exception`; every builder returns `None` rather than raising, and the UI degrades to an `st.info` message.
- [x] `st.plotly_chart(fig, width="stretch")` used — no `use_container_width`.
- [x] No dead code: no unused variables, computed values or imports introduced.

## Documentation

- [x] `README.md` updated — Key Features entry, How to Use step 31, and a Resolved Issues Index row. The stale **#154 row in the Active Roadmap table was removed**, since the feature is now implemented.
- [x] `DOCS.md` rendering pipeline updated with `_render_track_evolution_section`.
- [x] `DOCS.md` chart inventory / verification checklist updated with the new section's render check.
- [x] `DOCS.md` roadmap item for #154 marked ✅ Done; changelog entry added.
- [x] `DOCS.md` new architecture section **34. Track Evolution & Grip Improvement Ramp Index Architecture** added, including the regression rationale and the two guard rails.
- [x] `AGENT.md` architecture map updated (loader, components, plotly, tests count 95 → 104 across 17 modules) and **Decision #39** recorded.
- [ ] `DECISIONS.md` — **not updated: the file does not exist in this repository.** Creating it is the scope of the separate open Issue #172 (`add DECISIONS.md to documentation`), so it is deliberately left out of this PR. The architectural rationale for #154 is recorded in `AGENT.md` Decision #39 and `DOCS.md` §34 in the meantime.

## Syntax & Testing

- [x] Pytest unit tests pass — **104 passed** (`python3.11 -m pytest tests/`), 9 of them new.
- [x] Codebase compile check passes — `python3 -m py_compile app.py src/data/loader.py src/ui/styles.py src/ui/components.py src/charts/matplotlib.py src/charts/plotly.py`.
- [x] App starts without error — `streamlit run app.py` served HTTP 200 with no errors, tracebacks or deprecation warnings in the log.

---

## Revision 2 — Real-Session Validation (2026-09-30)

The first review left one box open: the model had only been exercised on synthetic sessions. It was run against two real cached sessions (2024 Bahrain and 2024 China Qualifying, loaded offline from `./cache/`), and that surfaced a third estimator defect.

3. **Qualifying knockout bias inflated the ramp ~2–3x.** Pooling raw lap times across the field is biased by composition: the slowest cars stop running after Q1 and Q2, so late-session flyers come only from the fastest cars and the field looks faster with no change in grip. The synthetic tests missed it because every synthetic driver ran the whole session. Confirmed by refitting on Q3 drivers only and with per-driver demeaning, both of which roughly halved the slope.

   **Fix**: driver fixed effects in `_build_track_evolution_data` — each driver's median flyer is subtracted and the field median added back (`PaceAdjusted_s`), so only within-driver improvement drives the fit. Single-flyer drivers carry no within-driver information and are plotted but excluded from the fit. The minimum sample of 10 now counts fittable laps.

   | Session | Before (pooled) | After (fixed effects) |
   | --- | --- | --- |
   | 2024 Bahrain Q | −28.5 ms/min · −1.639 s · R² 0.822 | **−10.0 ms/min · −0.578 s** · R² 0.351 |
   | 2024 China Q | −23.9 ms/min · −1.657 s · R² 0.683 | **−13.2 ms/min · −0.915 s** · R² 0.629 |

   The lower Bahrain R² is expected, not a regression: most of the old fit was explaining car-to-car pace differences rather than the track.

   **Regression test**: `test_build_track_evolution_data_removes_qualifying_knockout_bias` simulates a 12-car knockout with a known −10 ms/min ramp. It reads **−17.7 ms/min against the original loader (fails)** and −10 ± 1 with the fix (passes).

4. **Legend overlapped the chart title.** Rendering the real Bahrain figure to PNG showed the horizontal legend (five entries once drivers are highlighted) drawn over `Track Evolution & Grip Improvement Ramp`. The legend now sits centred below the plot area with a larger bottom margin. `build_weather_correlation_fig` uses the same legend placement but has fewer entries; it is outside this PR's scope and was not changed.

**Chart consistency**: the scatter now plots `PaceAdjusted_s` (falling back to `LapTime_s`) on a `Pace-Adjusted Lap Time (s)` axis, so the points and the trend curve share one scale; the actual lap time is kept in the hover. The section caption explains the adjustment.

**Revision 2 files**: `src/data/loader.py`, `src/charts/plotly.py`, `src/ui/components.py`, `tests/test_track_evolution.py`, `README.md`, `DOCS.md` (§16 test list and count, §34 motivation, method, data and chart layers, roadmap, changelog), `AGENT.md` (test count, Decision #39).

**Revision 2 checks**

- [x] Pytest — **105 passed** (1 new).
- [x] `py_compile` across all six modules passes.
- [x] App boots headless — HTTP 200, no errors, tracebacks or deprecation warnings in the log.
- [x] Model and figure validated on two real Qualifying sessions; figure rendered to PNG and inspected.
- [x] Correctness checklist re-verified for the changed code: `laps_df` still passed explicitly, driver grouping uses `groupby("Driver")` on the plain DataFrame (no `.pick_drivers()`), still inside the existing `try/except`, no new cache signature.
- [ ] In-browser dark/light mode and compare mode — **still not exercised**; the verification was a static render, not the live Streamlit page.

---

## Notes & Limitations

- **Session gating**: the section renders only for Practice and Qualifying (`FP1`–`FP3`, `Q`, `SQ`, `SS`, with raw-label fallbacks). Race and Sprint pace is dominated by fuel burn and tyre stint phases, which would swamp the evolution signal. This matches the issue's stated scope ("across Practice and Qualifying sessions").
- **Minimum sample**: 10 fittable flyer laps (within 107% of the session best, from drivers with 2+ flyers). Below that the function returns `None` and the UI explains why rather than rendering a misleading fit.
- **Live verification scope**: *(updated in Revision 2)* the model and chart have now been validated on two real Qualifying sessions. Dark/light mode and compare mode have still not been exercised in the browser for this section; a quick visual pass there is still recommended.
- **Theil-Sen cost**: pair enumeration is $O(n^2)$; above 200,000 pairs a deterministic seeded subsample is used, so large lap sets stay bounded.

## Verdict

**Approved for merge.** Three estimator defects and one chart-layout defect were found and fixed, and each estimator fix is covered by a regression test. The most consequential was the Qualifying knockout bias, found only by validating against real sessions. It had overstated grip gain by roughly 2–3x. The one unchecked documentation box (`DECISIONS.md`) is blocked on a separate open issue, and in-browser theme and compare mode checks remain outstanding, as noted above.
