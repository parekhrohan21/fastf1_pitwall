# Code Review — Issue #155: Corner Exit Traction & Throttle Pick-Up Aggression Analysis

**Feature PR**: #182 (merged 2026-10-02)
**Follow-up**: `fix: flat-out corners and snap pick-ups in traction analysis` (direct commit to `main`)
**Reviewer**: Software Development & Maintenance Agent
**Date**: 2026-10-03

---

## Summary of Change

PR #182 added corner exit traction analysis. It shipped without the `code_review_issue_155.md` artifact required by Step 5 of the contributing workflow. This review covers the merged feature and validates it against real telemetry. That validation found two defects, which the follow-up commit fixes.

| File | Change (PR #182) |
| --- | --- |
| `src/data/loader.py` | `_calculate_traction_metrics`: pick-up and full-throttle distances, ramp rate (%/m), gradient (%/s), hesitations, oversteer corrections, exit speed at 100 m, peak exit G, Traction Aggression Score. |
| `src/charts/plotly.py` | `build_traction_exit_fig`: 3-row Throttle / Speed / Longitudinal G figure with pick-up, full-throttle and hesitation markers. |
| `src/ui/components.py` | `_render_traction_exit_section`: corner selector, 4 KPI cards, comparison summary. Also a 5th `⚡ Traction & Exit` tab in `render_maps_block`. |
| `app.py` | Standalone section after Braking Analysis. |
| `tests/test_traction_exit.py` | 8 tests on synthetic telemetry. |

| File | Change (follow-up) |
| --- | --- |
| `src/data/loader.py` | `flat_out` flag and `FLAT_OUT_THROTTLE_PCT`. Snap pick-up ramp measured from the preceding sample. Exit metrics no longer depend on a pick-up being found. Score computed last. |
| `src/ui/components.py` | "Flat out" on KPI cards. Flat-out comparison summary and single-driver note. |
| `tests/test_traction_exit.py` | 3 tests: flat-out corner, 85% threshold boundary, snap pick-up. |
| `README.md`, `DOCS.md`, `AGENT.md` | Feature note, §16 test list and count, §18 changelog entry, Decision #41. |

---

## Real-Data Validation

The merged tests only use synthetic telemetry, so the metric was run on every corner of the 2024 Bahrain Race fastest laps of VER and LEC, from the cached session.

**Defect 1: flat-out corners were scored as traction events.** At T3, T12 and T15 throttle stays at 88–100% through the apex. The first sample above 5% is also the full-throttle sample, so the ramp came out as `0.00 %/m` and the score as ~75 (50 base + capped distance bonus). A corner with no pick-up got a confident, mid-table score.

**Defect 2: same-sample pick-ups.** VER T5 showed `init = full = −1.3 m`, `ramp 0.00 %/m`. The raw samples show 94–100% throttle through the apex and a lift only at +12 m, for the T6 kink. So T5 is also flat out. A ±35 m apex window wrongly picked up the T6 lift, which is why the flat-out window is ±10 m (nearest sample if none, since samples are ~13 m apart at 240 km/h). Separately, a genuine closed-to-full pick-up between two samples would also give a 0 %/m ramp. The ramp is now measured from the preceding sample (unit-tested: 0→100% over one 5 m sample = 20 %/m).

**After the fix:** T3, T5 (VER), T12 and T15 report `flat_out` with no pick-up metrics or score. No corner reports a 0 %/m ramp. LEC's T15 score of 99, an artefact of a brief dip, is gone. Both drivers are now consistently flat there. LEC's T5 is still scored (lift, ramp 0.08 %/m, 1 hesitation, score 29), which is a real difference from VER being flat.

## Correctness

- [x] **Flat-out threshold**: 85% within ±10 m of the apex. Bahrain T12 (88% minimum) is a breath, not a pick-up. Real lifts sit well below (T2 72–77%, T7 55–70%). The boundary is unit-tested at 90% (flat) and 60% (not flat).
- [x] **Score ordering**: the score was computed before `oversteer_corrections_count` was final. It now runs last and only when a pick-up was observed.
- [x] **Steering channel**: FastF1 car data has no `Steering`, so `oversteer_corrections_count` is `None` on real data. The UI never renders it and the score only penalises truthy counts. This matches existing corner analysis behaviour.
- [x] **Widget keys**: the section renders twice (page section `main`, map tab `maptab_<suffix>`), so there are no duplicate `selectbox` keys.
- [x] **Comparison summary**: the original full-throttle comparison only runs when both drivers have a pick-up. Flat-out cases get their own message.

## Code Quality

- [x] Threshold is a named module constant with a comment explaining the value.
- [x] Throttle-independent metrics (oversteer, exit speed, peak G) moved out of the pick-up branch rather than duplicated.
- [x] No dead code introduced.

## Documentation

- [x] `README.md` feature line notes flat-out labelling.
- [x] `DOCS.md` §16 test list/count and §18 changelog updated.
- [x] `AGENT.md` test count and Decision #41.

## Syntax & Testing

- [x] Pytest: **116 passed** (18 modules).
- [x] `py_compile` across the changed modules passes.
- [x] `AppTest` run of `_render_traction_exit_section` on real 2024 Bahrain data, compare and single-driver mode, at T3 / T5 / T15 (flat) and T4 (normal): no exceptions, chart rendered, "Flat out" cards and summary shown only for flat corners.
- [x] `AppTest` boot of `app.py`: no exceptions.

## Verdict

**Approved.** With the follow-up, #155 is complete: the feature reports sensible values on real telemetry, and flat-out corners are labelled instead of being given fabricated scores.
