# RE:Build Agent Independent Code Review

Reviewer: /root/final_code_review. Date: 2026-09-21 KST.
Read-only product review; only this review artifact is written. Scope: 21 product boundary files: backend server/security/templates/storage/auth/ai/config/drafts/exports/analysis, frontend/app.js, Supabase migration, and nine AI provider/runtime JavaScript modules. Analysis AR01 is under an independent worker's active correction and is not duplicated here.

## Code Review Summary

**Files Reviewed:** 21
**Total Issues:** 2

### By Severity
- CRITICAL: 0
- HIGH: 2
- MEDIUM: 0
- LOW: 0

### Issues

[HIGH] CR01 — Stale analysis can receive a fresh input fingerprint
File: backend/server.py:542 (create_draft); backend/server.py:459 (analysis_result input snapshot)
Issue: analysis_result compares one input snapshot. create_draft then calls inputs again and assigns that later fingerprint to the already-computed rows. An upload completing during analysis therefore becomes part of the approved fingerprint even though the draft never considered it. Original SourceRefs remain valid, so approval and export succeed.
Evidence: deterministic injected-store reproduction used a Notice period 14 calendar days document, then inserted a newly ingested Employer document between comparison and the later inputs call. Observed new_file_count=2, draft_has_new_condition=false, approval_status=200, export_status=200. Three command variants reproduced this result; only synthetic bytes and isolated test storage were used. No live credentials or evaluator data.
Impact: violates AC08/AC12/AC30 and the requirement that approval binds the exact reviewed input version.
Fix: preserve the fingerprint of the analysis snapshot, recheck current inputs before persisting, and explicitly reject changed inputs. Do not replace the old fingerprint with a current one. Add controlled-interleaving regression evidence.
Status: root reports a guard and regression have been implemented after this finding; independent re-review and passing evidence are pending. This finding is not yet closed.

[HIGH] CR02 — Knowledge results persist across project and execution-mode changes
File: frontend/app.js:63; frontend/app.js:88; frontend/app.js:103
Issue: renderKnowledge renders shared state.result unconditionally. Opening/switching projects clears only draft state. Mode switching changes state.mode but keeps the previous result. Query completion at line81 also writes result state without checking the initiating project, mode, or render generation.
Evidence: direct control-flow inspection: a search result for project A remains in state.result after selecting project B, and the same result is rendered when selecting AI Insight Mode. The displayed cards do not identify the result's original project/mode. This pass did not complete a dynamic browser reproduction; the parallel browser suite exercises other flows.
Impact: prior-project evidence can appear in another project's context, and rule/search results appear under the AI tab without a corresponding AI execution. Violates AC30/AC33 and execution-mode honesty.
Fix: bind results to project ID, mode and question; clear or separate results on context changes, and discard responses that finish after the initiating context changes. Validate project switch, mode switch and delayed-response cases with the real frontend.
Status: unresolved at review handoff.

### Specification and root-cause guard

The reviewed implementation has explicit no-fallback OAuth/API-key routing, SourceRef validation, signed intake/evidence/approval envelopes, immutable original/sidecar paths, template-version seals and atomic approval writes. These are useful implemented boundaries, but CR01 bypasses input freshness and CR02 misrepresents context. No primary-path failure is excused through a mock fallback.

Known architecture findings are tracked in docs/ARCHITECTURE_REVIEW.md. This reviewer does not decide architecture or close that lane. Live Supabase schema/Auth/Storage/RLS/restart proof and actual local OAuth inference remain acknowledged mandatory external verification gaps, separate from the two new defects.

### Diagnostics and limitations

- node --check frontend/app.js: exit 0.
- Existing scoped suite was launched: pytest tests/test_security.py tests/test_templates.py tests/test_auth.py tests/test_storage.py -q, followed by AI module syntax checks. At handoff it is still running in exec session 32568; do not count it as PASS until the parent captures completion.
- CR01 isolated API reproduction: approval 200 and export 200 despite omitted newly added condition; confirmed defect, not a success criterion.
- Tests using injected storage are not proof of actual Supabase RLS.
- Product files were not edited. No holdout, raw secrets, or OAuth tokens were read.

### Recommendation

REQUEST CHANGES. Resolve and independently recheck CR01 and CR02; retain the separate architecture and external-service gates. This is not a product-completion or deployment approval.
## Independent re-review — CR01 and AR01

2026-09-21, reviewer /root/final_code_review. This section supersedes only the scoped statuses named below; the original failure evidence remains above.

- CR01 CLOSED for the reported input-interleaving defect. backend/server.py:543 compares the fingerprint returned by analysis_result with the freshly retrieved documents and rejects mismatches before draft persistence. A change after that check leaves the old fingerprint on the draft, so later approval freshness validation still rejects it. Fresh regression test_concurrent_upload_during_analysis_cannot_approve_stale_rows passed: HTTP 409 INPUT_CHANGED and zero saved drafts.
- AR01 independently checked as requested by the leader. Full contract identities are retained at backend/analysis.py:40 and target filtering at lines288–317 includes project and complete contract ID. Same-project N77-ITB-001/002 with an addendum targeting only 001 preserves contract002 at35days, replaces001 from28to14days. Missing target with two candidates preserves all versions and REVIEW_REQUIRED. Both exact regression cases passed. This does not substitute for the architecture lane's overall verdict.
- Fresh diagnostics: ops/python.ps1 -m pytest tests/test_api.py tests/test_review_regressions.py tests/test_analysis.py tests/test_security.py tests/test_templates.py tests/test_storage.py -q => 67 PASS, two existing Starlette deprecation warnings.
- JavaScript syntax diagnostics: frontend/app.js and codex-provider, deployed-provider, evidence-contract, local-server, runtime-config, response-metadata, scripts/bridge and scripts/runtime all exited0.
- Diagnostic recovery: old virtualenv-launcher exec32568 was cancelled. The first helper attempt referenced nonexistent tests/test_auth.py and ran no tests; corrected six-module invocation produced the67PASS result above. No failed attempt was counted as PASS.
- CR02 remains open while its assigned frontend worker implements context binding and delayed-response handling.

Current scoped recommendation remains REQUEST CHANGES until CR02 is independently checked. External Supabase and OAuth validation gaps are unchanged and no product-completion approval is made.
## Independent re-review — CR02

2026-09-21. Reviewed the actual updated frontend/app.js and tests/ui/frontend_context.cjs.

- CR02 CLOSED for the reported cross-project/mode and late-response defects. Knowledge results now carry projectId/mode/query; rendering checks that context. Project selection, reopening, creation and switching use setKnowledgeProject; mode changes use setKnowledgeMode. Both invalidate the result and advance the request sequence. Query completion checks captured context and requestId before updating shared state or the result region. Typing a new question invalidates the prior result.
- Independently executed node tests/ui/frontend_context.cjs: 4 PASS. Cases cover project switch during a request, mode switch during a request, newer query winning out-of-order completion, and preserving an unsubmitted question across a mode switch. These execute actual frontend functions with a VM/DOM stub; they are not claimed as full browser or Supabase proof.
- node --check frontend/app.js: PASS.
- Actual transition call sites were inspected; these do not merely add unused helper functions.

### Current scoped verdict

COMMENT. Both reported HIGH defects CR01 and CR02 are resolved within their reproduced scope; no open HIGH/CRITICAL finding remains from this independent code-review pass. AR01's requested contract-target cases also passed independent review. Overall architecture sign-off, current full browser/regression evidence, actual Supabase DB/Storage/Auth/RLS/restart, local OAuth inference and the required final harness gate remain separate prerequisites. This verdict is not APPROVE for complete product readiness and does not authorize deployment or public publication.
## Narrow independent review — live-verifier metadata preflight

Scope: ops/runtime/supabase_live_verify.py, tests/test_live_verifier.py and the relevant tests/test_storage.py contracts. New code defects found in this requested preflight change:0. Scoped recommendation COMMENT; actual live-service verification remains pending.

- The table preflight uses service headers only for GET rb_entities with select=id and limit=0. It checks schema access without retrieving application rows. Auth settings uses the publishable key; bucket lookup checks metadata and requires public=false.
- Preflight failures return before test-user creation. Neither missing schema nor public/missing bucket can produce a successful RLS claim.
- Actual DB read/write isolation uses SupabaseStore instances created with publishable key plus each test user's JWT. The explicit cross-owner Storage GET also uses userB's JWT. The metadata service credential is not substituted for these tests.
- Service privilege after preflight is limited to creating isolated run-tagged test users and scoped cleanup of their exact user IDs/entity IDs/object paths. Cleanup failure changes final status to FAILED.
- This reviewer ran ops/python.ps1 -m pytest tests/test_live_verifier.py tests/test_storage.py -q:29PASS. Both missing-schema no-user-mutation contracts and privileged zero-row preflight tests passed. These synthetic HTTP tests do not establish a live RLS result.
- No actual live verifier was invoked by this reviewer, and no .env values or headers were printed.

The preflight change preserves the intended primary user-JWT isolation contract. Supabase and OAuth mandatory execution gaps remain explicit.
## Presentation layout / notes review — additional findings

2026-09-21 KST, /root/final_code_review. New layout changes in backend/drafts.py, backend/exports.py and root API/UI validation were inspected. This section does not duplicate the known in-flight255-character PPTX core-property failure or uploaded workbook-title preservation fix. Product source remains read-only in this lane.

[HIGH] PL01 — Excluded and nested statistical evidence lost when building slide rows
File: backend/drafts.py:145 (build_slide_rows source aggregation); backend/exports.py:407 (notes receive only the reduced slide row; line may shift).
Confirmed evidence: actual allowed P01/N01 comparison contains25 excluded SourceRefs; all25 are absent from the generated slide rows' collected source_refs. The builder gathers source/current/historical refs and selected severity_evidence refs, but not excluded_refs, mitigation_refs or all nested sample risk_refs/severity_refs. _comparison_detail also omits original value_classes and statistical samples. Thus the notes cannot meet the new full evidence/detail preservation claim.
Fix: preserve the complete comparison detail as reviewable plain text and all SourceRefs in validated top-level categorized fields, retaining the difference between applied/excluded/mitigation/statistical evidence. Do not introduce unchecked nested SourceRefs or silently present excluded documents as effective conditions.
Status: reported directly to documents_impl and root; fix/retest pending.

[HIGH] PL02 — Accepted custom template dimensions produce off-canvas output
File: backend/templates.py:111 (slide template validation); backend/exports.py:512 (fixed-inch layout).
Confirmed isolated API reproduction: retain the original five slides/placeholders but change template dimensions to7.5x10in; registration201, draft201, approval200, export200. Reopened output has25 text shapes outside the slide canvas. Template validation checks shape/text structure but exporter assumes13.333x7.5in.
Fix: enforce supported dimensions explicitly at registration and export/resolution, including already registered versions, or derive shared geometry/validation from actual dimensions. Reject unsupported layouts with a specific visible error. Preserve uploaded original bytes.
Status: reported directly to documents_impl and root; fix/retest pending.

[MEDIUM] PL03 — Character-unit budget understates wide-Latin text and visible source labels
File: backend/drafts.py:39 (_display_units) and backend/exports.py:374/_compact_ref (line numbers before in-flight edits).
The validator accepts title W*80 and body seven lines of W*88. Actual generated PPTX title inner geometry851.04x66.96pt at28pt and body813.6x249.84pt at18pt were measured. The estimator counts2 title lines/7 body lines; installed Arial glyph metrics require3/14 lines (84/252pt). The actual provided theme is Calibri Light/Calibri; matching-theme measurements and real rendering are being checked before declaring a final visual verdict. The three visible source labels additionally emit unbounded filenames/locators despite a0.95in source box.
Fix: ground the conservative budget in the selected font and real geometry, test wide Latin and CJK boundary cases, and use explicit bounded source labels while preserving the full source metadata in notes. Never silently cut edited title/body text.
Status: actionable measured-fit concern reported to implementer/root; final theme/render proof pending. No hypothetical product failure is claimed beyond the concrete geometry discrepancy.

Scoped recommendation remains REQUEST CHANGES for PL01/PL02 until fresh fixes are independently checked. No overall product or architecture approval is issued.
## Presentation re-review — first ready revision

Independent run: ops/python.ps1 -m pytest tests/test_slide_layout.py tests/test_templates.py tests/test_exports.py tests/test_review_regressions.py -q =>27PASS, two existing Starlette deprecation warnings. An earlier invocation named nonexistent tests/test_slide_api_limits.py, ran no tests, and was corrected; no false PASS recorded.

- PL02 CLOSED in scoped registration/export paths: unsupported canvas now rejects registration with422 SLIDE_TEMPLATE_SIZE_UNSUPPORTED before object/record writes; original bytes remain unchanged. Direct exporter also rejects unsupported dimensions. Same-size custom metadata template remains accepted and byte-identical on original download.
- Known in-flight255-character metadata/export failure resolved in the tested path: bounded core properties plus complete provenance in speaker notes; long UUID/template-hash regression passed. Uploaded workbook title preservation regression passed.
- PL01 PARTIALLY FIXED, still HIGH/open: actual excluded/mitigation top-level refs are normalized and role labels retained. However severity_evidence.samples[*].risk_refs/severity_refs still are not traversed; full samples and value_classes still are not serialized into detail_text. Fresh synthetic export result: nested_ref_retained=false, nested_ref_quote_in_notes=false, sample_project_in_notes=false, value_class_in_notes=false. Reported directly to implementer and leader. The new test checks top-level excluded/mitigation refs but does not yet cover nested sample evidence.
- PL03 PARTIALLY FIXED, still MEDIUM/open: W title/body is now rejected and72-character compact source labels preserve complete notes. Matching-theme source-label bound72CJK*9pt=648pt fits813.6pt width. But accepted H*88 on seven explicit body lines has622chars/estimated7lines. Actual supplied-theme Calibri18pt width of H*88 is990pt; available813.6pt requires14lines,252pt, exceeding249.84pt inner body height. The W-only special case did not repair the same width assumption for other wide glyphs. Reported directly to implementer and leader.

Scoped verdict remains REQUEST CHANGES for unresolved PL01/PL03. Structural27PASS does not negate the independent counterexamples or establish rendered layout completion.
## Presentation re-review — PL01 / PL03 scoped closure

Reviewer /root/final_code_review; independent recheck of the previously reproduced defects only. Earlier failed probes and first-revision findings above remain part of the record.

- PL01 CLOSED within the reported evidence-preservation scope. backend/drafts.py:37 now collects nested severity_evidence.samples risk_refs/severity_refs into the same validated top-level source_refs. The plain-text detail preserves sample project_id, severity, scale, sample classifications, statistical summaries, and role labels; backend/drafts.py:119 also preserves the production contract's top-level row.value_classes. No new unchecked nested SourceRef channel was added. Existing current_refs/historical_refs remain distinct, while excluded_refs and mitigation_refs retain their explicit role labels in full comparison detail.
- Fresh exact synthetic export probe: nested_ref_retained=true, nested_ref_quote_in_notes=true, sample_project_in_notes=true, value_class_in_notes=true. The last condition uses a distinct SPECIAL_UNCONFIRMED_CLASS marker at row.value_classes, matching the previously failing location, rather than only sample.value_classes.
- Fresh allowed P01/N01 comparison and slide conversion: excluded_count=25, excluded_missing=0, validate_refs succeeded for the collected references, and the excluded_refs role label remains present. The independently rerun real-data export regression verifies complete detail_text and every collected reference's filename/path, locator and quote in editable speaker notes. Excluded evidence is preserved as excluded evidence, not relabelled as an effective contract condition.
- PL03 CLOSED for the reported wide-Latin/title/body and source-label counterexamples. backend/drafts.py:68 now counts all ASCII uppercase letters conservatively in addition to CJK and the previous wide-character cases. Exact W88x7 and H88x7 bodies reject with SLIDE_CONTENT_TOO_LONG. Matching supplied-theme font measurement using installed Calibri18pt gives H88=990pt against813.6pt available width; the revised estimator counts14 lines instead of7, preventing the252pt content from exceeding249.84pt inner body height. Calibri Light28pt gives W80=1980pt against851.04pt title width; the revised estimator counts3 lines and rejects it. Visible source labels remain bounded to72 characters; the documented72-CJK-at9pt bound648pt fits813.6pt, with full metadata retained in notes.
- PL02 closure and the previously verified255-character core-metadata/custom-workbook-title fixes remain valid. No source template was changed by this review.
- Independent diagnostic: ops/python.ps1 -m pytest tests/test_slide_layout.py tests/test_templates.py tests/test_exports.py tests/test_review_regressions.py -q =>28PASS, two existing Starlette deprecation warnings.
- Recovery record: the first run in this pass produced1FAIL/27PASS because the newly added test asserted top-level value classifications without supplying them in its fixture. This was reported; the implementer added production-shaped fixture data without weakening the assertion. The repeated invocation above passed. The separate exact product probe already preserved the supplied classification marker. A read-only git diff attempt also returned a usage error and was not treated as validation; direct source inspection and executed diagnostics supplied the evidence.

### Scoped verdict

COMMENT. PL01, PL02 and PL03 are resolved for the reproduced defects and stated validation boundaries. This review does not certify arbitrary font/template layouts, replace the separate actual rendered-output check, or approve overall product completion. Actual Supabase DB/Storage/Auth/RLS execution and local OAuth inference remain separate mandatory gates. Product source and tests were not edited by this reviewer.
## Provider profile / asynchronous context review — scoped closure

Independent /root/acceptance_architecture reproduced two defects during AC25 implementation: provider selection changed during comparison/model execution could persist obsolete AI output (HIGH), and delayed settings response A could overwrite already-rendered B state (MEDIUM). Backend now compares project version/profile selection before model invocation, after response and before draft save; mismatch returns409 PROVIDER_CONFIGURATION_CHANGED without a draft. An already-started call is not represented as cancelled. Frontend gates both DOM and shared-state updates on the same request generation/page context.

Exact independent probes verified zero model calls/no draft when selection changed before invocation and discard after one controlled in-flight call. Settings A/B probe retains B after late A. Profile tests5, independent profile/boundary8, frontend context9/errors3 PASS. Actual browser6 verifies edit identity/version, persisted project selection, honest unconnected profile refusal, default reset, and no corporate endpoint requests/errors. Latest proof: ops/runtime/browser-provider-profiles-2026-09-21T15-07-45-436Z.json. TEST_STORAGE_INJECTED; no actual corporate connection or overall live-service pass.

## Condition-role and browser ownership review — scoped closure

Independent /root/acceptance_architecture found unrated/text-scale risk records promoted to primary conditions (MEDIUM), and runner port mismatches allowing a different pre-existing fixture to be tested (MEDIUM). The former now uses risk-table structure independently from numeric severity eligibility. Two regressions first failed, then passed. Independent targeted31PASS.

The browser runner now passes one loopback URL and unique run ID; all six scenarios validate200, TEST_STORAGE_INJECTED and the exact run ID before browser mutations. Independent controlled boundary6PASS; root boundary4PASS. Root actual nondefault8784 run verified matching run IDs: Provider6 and mobile9PASS. All source/archive records remain intact. These findings are CLOSED within their reproduced scope; Supabase schema/RLS/persistence, local OAuth and final output review remain mandatory.

## Mixed allowance/design classification — scoped closure

2026-09-22 independent /root/acceptance_architecture reviewed analysis.py _value_kind/_labeled and compare review guard. Same-fact allowance plus design/unknown is now labeled mixed with REVIEW_REQUIRED, without changing source text/numbers/units/references. Pure allowance and pure design/unknown cases remain separate. Independent analysis+slide tests31PASS. The initial regression fixture was corrected from two sentences (correctly parsed separately) to the observed single fact before changing product logic. This is a narrow classification repair, not a semantic extraction completeness claim.
## XLSX detail preservation — independent repair review

/root/acceptance_architecture found a MEDIUM regression in the compact source display: two items with[A,B] and[A,C] shared the same visible A/count/link, while global Sources lacked item attribution. The worker added source role, Source ID, original locator and Sources-row mapping to Review Detail, with long mapping chunk preservation. The reviewer re-ran the exact A/B versus A/C counterexample and confirmed distinct complete associations. Scoped mapping finding CLOSED; independent3PASS covers role mapping, long content and formula injection.

Independent checks also confirmed exact approved body preservation, continuous chunks beyond Excel's32,767-character limit, literal reviewer/source formula-like strings, generated Risk formulas, and unchanged template SHA. These checks do not certify the unfinished Risk visual review or overall live-service completion.
## Final XLSX scoped independent review — 2026-09-22T01:09:54.763632+09:00

/root/acceptance_architecture independently verified4 narrow regressions and a multi-item long-text/source-offset probe: PASS, original template hashes unchanged. After root's real-render finding, the condition→past→rationale reorder and new regression were re-reviewed with3PASS. Scoped CLEAR: full content/SourceRef roles, literal strings, generated formulas, zero and missing ratings preserved. No additional abstraction or fallback change justified. This does not approve live Supabase/OAuth or overall completion.
