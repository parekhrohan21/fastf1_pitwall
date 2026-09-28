# Code Review — Issue #177

**Title:** `docs: add inline architecture commentary to app.py and sync README with missing updates`
**Branch:** `docs/issue-177-app-comments-readme-sync`
**Reviewed:** 2026-09-28
**Change class:** Documentation & comments only — no executable statement was added, removed or reordered.

---

## 1. Scope of change

| File | Change |
|---|---|
| `app.py` | Added a module-level docstring (architecture, render pipeline, comparison modes, invariants) and an explanatory comment block beneath each of the 39 `# ── Section ──` dividers. `+249` lines, all comment or docstring. |
| `README.md` | Removed closed issue #164 from the Active Roadmap; added merged PRs #176 and #175 to the Resolved Issues Index; expanded the Project Structure tree; added a **Continuous Integration** section and a **GitHub Codespaces (Dev Container)** section. |
| `code_review_issue_177.md` | This artifact. |

Verification that the `app.py` diff is comment-only — the parsed AST before and after the change is
byte-identical once the newly added module docstring node is dropped:

```python
import ast
a = ast.parse(before)   # app.py prior to this branch
b = ast.parse(after)    # app.py on this branch
b.body = b.body[1:]     # drop the added module docstring node
assert ast.dump(a) == ast.dump(b)   # → passes
```

No statement was added, removed, reordered or altered.

---

## 2. Correctness

| Check | Result |
|---|---|
| No `st.session_state["session"].laps` accessed inside a `@st.cache_data` function | ✅ N/A — no function bodies changed |
| `laps_df` passed as `pd.DataFrame(sess.laps.copy())` — not raw `fastf1.core.Laps` | ✅ Unchanged; the invariant is now documented at the `Laps snapshot` section and in the module docstring |
| Driver filtering uses `laps_df[laps_df["Driver"] == driver]` — not `.pick_drivers()` | ✅ Unchanged; rationale documented |
| All new `@st.cache_data` functions include `sess_k: str` | ✅ N/A — no new cached functions |
| All new UI showing driver identifiers wraps them in `_fmt_driver(drv)` | ✅ N/A — no new UI |
| No new inline compound colour dicts | ✅ None added |

---

## 3. Code quality

| Check | Result |
|---|---|
| Type hints on all new functions | ✅ N/A — no new functions |
| One-line docstring on all new `@st.cache_data` / data-builder functions | ✅ N/A — no new builders |
| Section headers follow `# ── Name ──────` format | ✅ All 39 existing dividers preserved verbatim; commentary was inserted *beneath* them, never in place of them |
| `plt.close(fig)` called immediately after every `st.pyplot(fig)` | ✅ Unchanged — and the reason is now documented in the `Overlapping` section |
| All FastF1 data access wrapped in `try/except Exception` | ✅ Unchanged |
| British English spelling throughout comments and docs | ✅ colour, visualise, analyse, modularisation, normalises |

---

## 4. Documentation

| Check | Result |
|---|---|
| `README.md` updated if user-visible behaviour changed | ✅ No behaviour changed; README updated for the documentation gaps that motivated this issue |
| `DOCS.md` rendering pipeline updated if a new section was added | ✅ N/A — no new rendering section |
| `DOCS.md` chart inventory updated if a new chart was added | ✅ N/A — no new chart |
| `AGENT.md` architecture map line ranges updated if sections shifted | ✅ N/A — the architecture map describes modules, not line ranges |
| `DOCS.md` roadmap item marked ✅ Done if implemented | ✅ N/A |
| `DECISIONS.md` updated with new ADR entry | ✅ N/A — no architectural or algorithmic choice was made (`DECISIONS.md` remains open work under Issue #172) |

Active Roadmap was reconciled against the live issue tracker:

```bash
gh issue list --state open   # → 172, 171, 157, 156, 155, 154
```

The README Active Roadmap table now lists exactly those six issues. Issue #164 was closed by merged
PR #176 and has been moved to the Resolved Issues Index with its PR cross-reference, matching the
`#PR / #issue` convention used by every other row.

---

## 5. Syntax & testing

| Check | Command | Result |
|---|---|---|
| Pytest suite | `python3.11 -m pytest tests/` | ✅ **95 passed** in 0.97 s (16 modules) |
| AST parse | `python3 -c "import ast; ast.parse(open('app.py').read())"` | ✅ Syntax OK |
| Compile check | `python3 -m py_compile app.py src/data/loader.py src/ui/styles.py src/ui/components.py src/charts/matplotlib.py src/charts/plotly.py` | ✅ Passed |

---

## 6. Outstanding observations (not addressed by this PR)

These were found while reading `app.py` for the commentary. They are recorded here rather than fixed,
because this issue is documentation-scoped and a code fix belongs in its own issue and branch.

1. **Duplicate helper definitions shadow the `src/` imports.** This working copy of `app.py` defines
   26 top-level functions (`render_summary`, `_build_lap_history`, `_render_leaderboard`, …) that are
   also imported from `src.ui.components` / `src.data.loader`. The local definition wins. PR #176
   removed these on `main`. The `Lap Summary` comment block flags this in place so a future editor
   does not change the wrong copy.

2. **`render_summary` raises `NameError` on every call in this working copy.** `app.py:549` calls
   `_team_logo(raw_team, active_year)`, but `_team_logo` is neither defined in `app.py` nor present
   in its import list from `src.data.loader` — it is only imported by `src/ui/components.py`. The
   call sits inside a `try/except Exception`, so the failure is swallowed silently and the driver
   banner renders with **no team badge and no headshot** rather than crashing. The imported
   `src.ui.components.render_summary`, which this local definition shadows, does not have this
   defect. A one-line import would fix it; raising this as a separate `bug` issue is recommended.

---

## 7. Verdict

✅ **Approved for merge.** Documentation-only change, all 95 tests green, compile check clean,
no executable code paths touched.
