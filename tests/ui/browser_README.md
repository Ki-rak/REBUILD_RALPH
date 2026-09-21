# RE:Build Agent browser verification

All browser results are **TEST_STORAGE_INJECTED**: the production frontend, API, parsers, comparisons, approval and exports run with an explicit in-memory test store and synthetic authentication. They do not prove actual Supabase DB/Storage/RLS, restart persistence or AI connectivity. Never expose this fixture externally.

## Owned fixture runner

From the project root in PowerShell:

    .\.venv\Scripts\python.exe -X utf8 tests/ui/run_browser.py browser_flow.cjs
    .\.venv\Scripts\python.exe -X utf8 tests/ui/browser_workbook.py
    .\.venv\Scripts\python.exe -X utf8 tests/ui/run_browser.py browser_search_scope.cjs
    .\.venv\Scripts\python.exe -X utf8 tests/ui/run_browser.py browser_slide_limits.cjs
    .\.venv\Scripts\python.exe -X utf8 tests/ui/run_browser.py browser_mixed_upload.cjs
    .\.venv\Scripts\python.exe -X utf8 tests/ui/run_browser.py browser_provider_profiles.cjs browser_mobile_core.cjs
    node tests/ui/fixture_boundary.cjs

The runner starts a loopback uvicorn thread, passes BROWSER_TEST_URL and a fresh BROWSER_TEST_RUN_ID to each child, and stops its own fixture in finally. Every browser scenario validates the server's TEST_STORAGE_INJECTED boundary and matching run ID before browser actions. Running a script directly without this context fails. Use --port 8784 when another port is occupied; scripts always use the supplied URL. No test targets an arbitrary existing product server.

Flow/search_scope/slide_limits each require empty storage: run them in separate runner invocations. Provider and mobile can share a runner. Each child is bounded to180 seconds and startup to30 seconds. The project uses its pinned Playwright installation in tools/web/node_modules (Apache-2.0); no browser dependency is installed by this runner. pytest.ini confines default Python collection to tests and excludes source/evaluator/dependency/operations folders.

## Coverage and evidence

- Flow: synthetic invalid/valid login; empty account; historical and fresh current uploads through UI; original hash absence; source extraction; source route/graph; edit/approve/reopen/reapprove; ITB/Risk/five-slide editable output; immutable custom template registration/selection; management/seven templates/settings; error/retry/logout.
- Office: reopen generated XLSX/PPTX and verify uploaded/past values, exact reviewer edits, titles, five slides, source links and selected template metadata.
- Search: all/current/historical selection, request scope, mode/query persistence and correct result membership.
- Provider: edit the same profile/version; select per project; retain through reload; refuse unconnected corporate config without outbound corporate requests; explicit reset to environment default.
- Mobile390px: project/upload dialog, source original, draft edit/revision/approval, actual XLSX download and document overflow measurements. Wide draft tables retain their internal horizontal scrolling.
- Mixed upload: valid TXT and corrupt DOCX in one batch, exact original byte preservation, isolated conversion failure, honest retry failure and remaining valid draft input.
- Slide limits: details before approval; oversized edit422 with friendly error; unchanged approved server record; unsaved UI text preserved; shorten/save/invalidate/reapprove. This scenario makes no export request.

Timestamped JSON reports and downloaded files are in ops/runtime. Every completed scenario records failures and exits nonzero when assertions fail. Earlier failure reports/screenshots remain preserved. Owned-fixture metadata appears in newer reports; older reports predate that guard. Main flow writes browser-report.json and timestamped copies, Office writes browser-workbook-report.json and timestamped copies. These are active development evidence, not a substitute for the mandatory real-service checks.

## Windows startup recovery

Some detached Python launches stalled before interpreter entry. The owned in-process fixture driver avoids that background-process path. ops/python.ps1 is an alternative launcher using the configured base interpreter and project site-packages, but its availability does not prove the target program started. Inspect actual exit/output; stop only processes whose exact command identifies the owned test. Never terminate unrelated Python or product services.