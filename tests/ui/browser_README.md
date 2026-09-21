# RE:Build Agent browser verification

All results are **TEST_STORAGE_INJECTED**. This uses the production frontend, API, parser, comparison, approval and export code with an explicitly injected in-memory test store and synthetic auth. It does not prove Supabase Auth/DB/Storage/RLS or real AI connectivity.

Start `& ./ops/python.ps1 tests/ui/browser_server.py` on 127.0.0.1:8782 in a hidden helper process. Restart the helper before each complete run so its test storage is empty. It generates the synthetic DOCX fixture itself. It disables local environment file loading before importing the product API.

Run `node tests/ui/browser_flow.cjs`, then `& ./ops/python.ps1 tests/ui/browser_workbook.py`. The browser runner currently uses the existing Playwright 1.62.1 installation in `tools/web/node_modules`; adjust that import for a different installation. Playwright is Apache-2.0 licensed. The parent installed and pinned this dependency locally during the expanded verification.

Artifacts: `ops/runtime/browser-report.json`, `browser-workbook-report.json`, downloaded `browser-result.xlsx`, and `browser-mobile.png`. Earlier failing evidence is preserved in `browser-report-before-fixes.json` and `browser-workbook-before-fixes.json`.

The test signs in as a synthetic user, seeds historical text through the real API, proves the new DOCX hash was absent, uploads through the browser, verifies actual extracted values, edits/approves/downloads an ITB workbook, checks both comparison panels and direct source route, verifies management/seven templates/settings, checks failure/retry/logout, and measures settings-page document overflow at 390px. Workbook verification checks uploaded/historical values, filenames, edited reviewer rationale and source links.

Mobile validation covers settings and error recovery only; it is not exhaustive mobile QA. The test store is process-local and intentionally ephemeral. Do not expose the fixture server externally.

Expanded verification also creates, edits, approves and downloads `browser-risk.xlsx` and `browser-committee.pptx`. The Office proof verifies the reviewed mitigation/decision and exactly five actual PPTX slides. Browser reports are copied to timestamped JSON files on every completed run; failing assertions remain recorded and make the process fail. Server readiness is checked via a bounded successful `/api/config` probe before creating test records.


The expanded browser run now starts from an empty project list and creates historical source data through the UI, with no API seed shortcut. It covers persisted approved-draft reopening after reload, unsaved-edit approval/export guards, approval invalidation on save and reapproval, matching default Risk/committee templates, five editable committee rows, graph comparison/document identity, and template version upload/download/select/export/reopen. API reads are used for independent output verification only. The Office checks also verify edited committee titles/bodies and uploaded-template metadata preservation.


AR10 mixed-upload proof: run `node tests/ui/browser_mixed_upload.cjs` against the isolated fixture. One actual UI batch contains a fresh valid TXT and a corrupt supported DOCX. Assertions require valid extraction and preserved original records, explicit ERROR/FAILED conversion status, honest failed retry, surviving valid draft input, and no removed failure/processing KPI. The source UI check verifies successful original requests and visible TXT content; separate authenticated original API checks require exact uploaded bytes for both files before/after retry. Chromium's CDP attachment response body was empty despite the visible source and byte-identical API response, so those observation paths are recorded separately. Earlier diagnostic failures remain in timestamped browser-mixed-upload reports. `ops/python.ps1` uses the configured base interpreter and project packages, avoiding the hanging virtual-environment redirector.
