# RE:Build Agent bounded cleanup plan

2026-09-21 21:25 KST. Scope: backend/server.py, backend/exports.py, frontend/app.js and narrow regression tests. No architecture rewrite or new dependencies.

Behavior lock: full Python suite 88 PASS; AI adapter suite previously 25 PASS. Independent browser tests remain separate.

Fallback classification:
- Authentication context opens an HTTP client before get_user and fails without closing it. Repair ownership/finally; keep sanitized rejection.
- Risk workbook calculation flags use a silent AttributeError catch. Explicitly create openpyxl CalcProperties only when a valid workbook lacks metadata, then set flags; preserve computed-formula contract.
- File download/open attempts JSON then text on the same consumed Response. Read once by content type and preserve HTTP failure.
- Drag/drop suppresses file assignment errors. Report failure and preserve existing file selection.
- Extraction failures preserve originals and explicit FAILED/OCR_REQUIRED status: grounded fail-safe boundary; retain.
- Provider failure remains UNKNOWN/disconnected, never auth fallback: grounded fail-safe boundary; retain.
- Catch-all public HTTP boundary suppresses raw credential-bearing messages while returning SERVICE_UNAVAILABLE: grounded security boundary; retain.

Pass order: remove redundant failure branch, repair resource ownership/error reporting, add narrow regressions, rerun relevant suites. No unrelated renaming or new abstraction. Separate implementer and reviewer required.
## Acceptance follow-up cleanup plan — 2026-09-22

Scope: committed backend/analysis.py, backend/drafts.py, backend/server.py, frontend/app.js/styles.css, tests/ui/run_browser.py and fixture target helper. XLSX output repair is reviewed separately after its behavior lock is complete. No architecture rewrite or new dependency.

Behavior lock: analysis/boundary/profile28 and independent31PASS; frontend context9/errors3; owned8784 provider6/mobile9; fixture-boundary4 and independent6. Preserve complete sources, rating eligibility, strict OAuth/API separation and honest test boundaries.

Order: inspect fallbacks and fail-open behavior; check dead code/duplicates; clarify error/role boundaries; confirm regressions. Retain duplicate provider version checks at distinct asynchronous boundaries because they prevent different races. Keep risk role and numeric statistical eligibility separate. Keep explicit fixture denial on missing environment/boundary/runID. No speculative abstraction or formatter-wide churn.