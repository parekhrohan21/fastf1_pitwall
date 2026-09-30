# Code Review — Issue #177: app.py Architecture Commentary & README Sync

**Branch**: `docs/issue-177-app-commentary`
**PR**: #180
**Reviewer**: Software Development & Maintenance Agent
**Date**: 2026-09-30

---

## Summary of Change

Issue #177 raised two documentation gaps. Both are now closed.

| Gap | Resolution |
| --- | --- |
| **1. `app.py` has no inline commentary** | Module docstring added, covering the `src/` package map, Streamlit's rerun execution model, the 11-stage render flow and the two comparison modes. An explanatory block now sits under all 46 section dividers. A `PDF Debrief Export & Footer` divider was added so the last stage maps 1:1 to the documented flow. |
| **2a. PR #175 missing from Resolved Issues Index** | Added (`77167c4`, merged via #179). |
| **2b. #164 missing its PR #176 cross-reference** | Row now reads `#176 / #164` (`77167c4`). |
| **2c. #164 row out of chronological order** | Moved below #179/#154 and above #175 (`77167c4`). |
| **2d. CI undocumented** | `.github/workflows/test.yml` documented in Contributing Step 4 (`77167c4`). |
| **2e. Codespaces / Dev Container undocumented** | New "Running in GitHub Codespaces" section (`77167c4`). |
| **2f. Project tree incomplete** | `.github/`, `.devcontainer/`, PWA icons, `.gitignore`, `.dockerignore`, `cache/` added (`77167c4`). |
| **Expected: Active Roadmap matches `gh issue list`** | Once #177 closes, the open issues are 172, 171, 157, 156 and 155, and the table lists exactly those. #154 closed via #179 and #177 moves to the Resolved Issues Index as `#180 / #177`. |

The README half reached `main` through PR #179. This PR adds the `app.py` commentary and the bookkeeping that closes #177.

| File | Change |
| --- | --- |
| `app.py` | Module docstring and 46 section notes. One stale comment removed. No code changes. |
| `README.md` | #177 moved from Active Roadmap to Resolved (`#180 / #177`); #154 row relabelled `#179 / #154` to match the `#PR / #issue` convention. |
| `DOCS.md` | §18 changelog entries for PR #180 / #177 and PR #179 / #154. |
| `code_review_issue_177.md` | This artifact. |

---

## Correctness

This PR changes comments only, so the data-path checklist items are not affected. What had to be verified instead is that no behaviour changed and that the comments are accurate.

- [x] **No code change**: the `ast.dump` of `app.py` is identical to `main` once the module docstring is set aside. The only removed line was a comment.
- [x] **Docstring not rendered**: Streamlit "magic" can render a top-level bare string. `AppTest` confirms the docstring does not appear on the page and that `set_page_config` still runs first (no exceptions).
- [x] **Comments match behaviour**: each note was written after reading the code it describes. Specifics were verified: the export figure keys (Lap Time History, Tyre Stints, Gap to Leader, Position History); the undercut window (`min − 1` to `max + 2`, ±3-lap pairing); the fuel slider feeding both the chart and the leaderboard; the telemetry `st.stop()` skipping every field-wide section; and the Track Evolution gate living inside the renderer.
- [x] **Stale comment removed**: `# _CMP_PALETTE removed — use COMPOUND_COLOURS (defined in Constants block)` pointed at a block that has not existed in `app.py` since modularisation. `COMPOUND_COLOURS` lives in `src/ui/styles.py`.

## Code quality

- [x] Section headers follow `# ── Name ────` format, including the new `PDF Debrief Export & Footer` divider.
- [x] Comment density is kept short: one to seven lines per section, explaining *why* and *what state* rather than restating the code.
- [x] No dead code introduced.

## Documentation

- [x] `README.md` updated — Active Roadmap and Resolved Issues Index.
- [x] `DOCS.md` §18 changelog updated.
- [x] `AGENT.md` — no `app.py` line-number references exist, so the ~150-line shift needs no map update.
- [ ] `DECISIONS.md` — not applicable (no architectural decision), and the file does not exist yet (#172).

## Syntax & Testing

- [x] Pytest — **105 passed**.
- [x] `py_compile` across all six modules passes.
- [x] App boots — `AppTest` run with no exceptions.

---

## Out-of-Scope Defects Found During Review

Reading every section of `app.py` closely surfaced four existing defects. None was introduced by this PR, and fixing them would change behaviour, which is outside a comment-only docs PR. They are recorded here with evidence and should be filed as separate `bug:` issues.

1. **`lap1` / `lap2` overwritten by the undercut simulator** (`Pit Strategy & Undercut / Overcut Simulator`). The pairing loop assigns `lap1 = p1['lap']` and `lap2 = p2['lap']`, replacing the selected lap objects with integer lap numbers. This happens whenever two compared drivers both pitted, even if no battle is found. Six downstream sections still expect the selected lap objects: braking analysis, multi-year comparison, Separate chart titles, telemetry export, the continuous Time Delta chart and the Track Map. *Fix: rename the loop variables (e.g. `pit_lap1` / `pit_lap2`).*

2. **Pit Lane Transit Loss section (#153) never renders.** `_build_pit_transit_data` is `@st.cache_data` but receives raw `sess.laps` (`fastf1.core.Laps`) and an un-prefixed `sess_obj` (`fastf1.core.Session`). Verified on cached 2024 Bahrain Race data: `UnhashableParamError` on `laps_df`, and on `sess_obj` even when `laps_df` is a plain DataFrame. `app.py` wraps the call in `except Exception: pass`, so the section silently never appears. *Fix: pass `_all_laps1` and rename the parameter to `_sess_obj`.*

3. **Undercut gap reads the wrong rows.** `_all_laps1[_all_laps1['LapNumber'] == w_start]['Time'].iloc[0]` has no driver filter, so it takes whichever driver's row comes first at that lap number. In driver-compare mode `_all_laps2` is `None`, so the lookup raises and the user sees the "missing telemetry" warning every time.

4. **`dark_mode` initialised at module import time** (`src/ui/styles.py:89`). The `if "dark_mode" not in st.session_state` guard runs once per Python process, not once per browser session. In `AppTest`, a second session in the same process fails with `KeyError: 'dark_mode'` at `inject_styles`. The Streamlit server also keeps imported modules cached across sessions, so later visitors on the same server process are likely affected. **Not yet confirmed in a real browser:** headless Chrome returned only the pre-render HTML shell. *Fix: initialise inside `inject_styles()` (called at the top of every run).*

## Verdict

**Approved for merge.** This is a comment-only change, verified by AST comparison and an app boot, and it closes every point in #177. The four defects above were found during the review and are deliberately left for their own issues and PRs.
