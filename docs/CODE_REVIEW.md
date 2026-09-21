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