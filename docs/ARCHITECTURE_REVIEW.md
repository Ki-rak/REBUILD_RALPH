# RE:Build Agent independent architecture review

2026-09-21 21:35 KST. Reviewer: /root/architecture_gate (read only). Overall verdict BLOCK; not product completion. No evaluator/holdout used.

## Findings and assigned recovery

| ID | Finding | Evidence / recovery |
|---|---|---|
| AR01 HIGH | Past project B amendment removed past project A clause | Synthetic A28days/B14days returned B only. Document worker scoped project+contract family and added ambiguity handling; 25 analysis/extraction tests pass. Independent re-review pending. |
| AR02 HIGH | Same SHA workbook in three project IDs counted as three independent risk cases | Synthetic unique SHA1 gave samples3/severity4. Exact case dedup added; re-review pending. |
| AR03 HIGH | XLSX Notice period label lost adjacent 19 days value | Row-context facts with all contributing cell refs added; re-review pending. |
| AR04 HIGH | UI could not create historical project from empty account | Frontend kind selection implemented; zero-state browser rerun pending. |
| AR05 HIGH | Persisted drafts absent after refresh; approved drafts cannot revise; unsaved edits can approve stale content | Frontend saved list/open and dirty-state revision controls implemented; browser rerun pending. |
| AR06 HIGH | Heterogeneous graph node index selected unrelated comparison; backend decision/missing fields ignored | Actual row_id/source/edge mapping implemented; browser rerun pending. |
| AR07 HIGH | Editable topic rows differed from five output slides | Canonical overview/itb/applicability/risks/decisions rows implemented. Actual PPTX review regression PASS. |
| AR08 MEDIUM | Wrong default template for risk/slides | Match template id to output kind; browser rerun pending. |
| AR09 MEDIUM | Template versions only current hash, no previous versions or registration | Immutable owner-scoped version catalog implementation in progress. |
| AR10 MEDIUM | UI lacked conversion retry and honest mixed status errors | Frontend retry/status handling implemented; rerun pending. |
| AR11 MEDIUM | Source strings beginning = became Excel formulas | Explicit string data type implemented; reopen regression PASS. Generated score formulas remain formulas. |
| AR12 MEDIUM | Actual AI response usage discarded | Adapters now preserve normalized actual usage/execution; 31 tests PASS and actual deployed usage246/229/475 PASS. |

Preserve existing boundaries: signed intake/evidence; signed approval database version; immutable Storage objects; atomic RLS-bound approval RPC; separate OAuth/API-key adapters. Actual Supabase schema/RLS/restart and local OAuth remain external verification gaps, not justified skips.

## Bounded cleanup result so far

Plan: docs/CLEANUP_PLAN.md. Auth-client rejected-session leak fixed with finally; valid templates without calculation metadata receive explicit CalcProperties; literal Excel text is preserved. Three reproduced failures plus formula regression now green. Targeted backend/export/API suite24 PASS. Frontend read-once binary failure/refresh/drop handling under separate verification. Full cleaner verdict remains pending until frontend and regression re-run.

## Evidence chronology

Original browser failure kept: browser-report-2026-09-21T12-24-45-864Z.json (15 PASS / 1 FAIL); actual Office proof browser-workbook-20260921T122546Z.json (13 PASS). These precede canonical slide UI fixes. Do not overwrite these failures with later PASS.

Independent review is not yet closed. Verify each finding against fresh code and actual regression results before changing this verdict.
## Scoped resolution matrix — independent code-review evidence update

2026-09-21 KST, appended by /root/final_code_review at the leader's request. Original findings and failures above are preserved. This is an evidence matrix, not a replacement architecture decision. The original architect's overall BLOCK has not been silently converted to CLEAR.

Attribution: the leader relayed prior architect scoped checks for AR02/03/07/09/11 and requested a fresh AR01 recheck. This reviewer independently read the relevant fixes and ran the exact regression modules below. Browser/Office entries are from the separate browser-verification lane's actual JSON artifacts, read by this reviewer; this reviewer did not rerun that browser session. No injected-storage evidence is presented as Supabase evidence.

| ID | Scoped resolution | Evidence and attribution |
|---|---|---|
| AR01 | Reported cross-project/full-contract replacement defect resolved | This reviewer independently inspected full contract IDs and project/target filtering and ran tests/test_analysis.py. Exact same-project N77-ITB-001/002 case replaces only001 from28to14days and retains002 at35days. Unknown target preserves all versions with REVIEW_REQUIRED. |
| AR02 | Reported identical-workbook independence defect resolved | Prior architect check relayed by leader; independently rerun test_identical_risk_workbook_sha_is_one_case_even_with_three_project_aliases. One SHA produces one case/project contribution and blank severity. |
| AR03 | Reported adjacent XLSX label/value loss resolved | Prior architect check relayed by leader; independently rerun test_xlsx_row_context_keeps_label_value_and_both_cell_sources. Notice period retains19calendar days and Terms!A2/B2 SourceRefs. |
| AR04 | Historical-project creation resolved in browser fixture scope | Separate browser artifact B26: Zero-state historical project and source created through UI. Actual app and parser with TEST_STORAGE_INJECTED; no live Auth claim. |
| AR05 | Saved draft/open/revision/dirty approval controls resolved in tested paths | B26 includes unsaved-edit blocking, refresh/reopen, approved edit invalidation and reapproval. This reviewer reran API edit/approval regressions and independently closed CR01 snapshot race separately in docs/CODE_REVIEW.md. |
| AR06 | Reported graph index/contract mismatch resolved in tested paths | B26 confirms knowledge row IDs map to comparison and source edges, historical/current panels, direct source route. Earlier code review inspected actual row_id and decision/missing fields; no semantic-distance score introduced. |
| AR07 | Five editable sections and exported content aligned | Prior architect check relayed by leader; this reviewer reran test_five_slide_draft_edits_render_on_corresponding_slide_and_invalidate, including all five edited headings/bodies/rationales. B26 and O16 confirm actual5slide download and reviewed title/body/decision retention. Visual overflow at large input volumes is not established by this structural check. |
| AR08 | Wrong output-template default resolved | B26 separately confirms risk and slides default matching templates. Actual template selection/version field is bound to output kind. |
| AR09 | Immutable template-version workflow resolved in tested scope | Prior architect check relayed by leader; independently rerun four tests/test_templates.py cases: reuse across two projects, original/version preservation, reapproval, invalid version rejection, interrupted registration recovery and metadata-forgery rejection. B26/O16 confirm uploaded version byte identity, select/export/reopen and custom metadata. Live persistence remains pending. |
| AR10 | Retry/status implementation verified narrowly; specific mixed-upload browser proof remains unclosed | This reviewer reran API retry/immutable-sidecar tests and UI contract checks; frontend code has failed-conversion retry and mixed-status uploadMessage. B26 service-outage retry is a different scenario and is not proof of a corrupt/supported mixed upload through UI. Do not relabel that distinct scenario as passed. |
| AR11 | Source/user formula injection defect resolved | Prior architect check relayed by leader; independently rerun test_excel_source_and_review_strings_remain_literal_not_executable_formula. Input strings remain string cells; intentionally generated numeric score formula remains a formula. |
| AR12 | Actual model usage retention resolved for deployed adapter evidence | Root reports31AI testsPASS; this reviewer read actual product-openai-usage-20260921T124924Z.json: input305/output1263/total1568, gpt-5-mini-2025-08-07, MODEL_CALL, stored_usage_verified and export_reopened true. Scope is ACTUAL_OPENAI_DRAFT_USAGE_APPROVAL_EXPORT_WITH_TEST_STORAGE; OAuth and Supabase flags false. This supersedes the earlier illustrative246/229/475 usage tuple for this cited artifact. |

Evidence references:
- B26: ops/runtime/browser-report-2026-09-21T13-18-08-516Z.json —26PASS, zero page errors, boundary TEST_STORAGE_INJECTED.
- O16: ops/runtime/browser-workbook-20260921T131842Z.json —16true output checks, boundary TEST_STORAGE_INJECTED.
- This review run: ops/python.ps1 -m pytest tests/test_analysis.py tests/test_review_regressions.py tests/test_templates.py tests/test_api.py tests/ui/test_frontend_contract.py -q —48PASS, two existing Starlette deprecation warnings.
- This review run: node tests/ui/frontend_errors.cjs —3PASS; node tests/ui/frontend_context.cjs —4PASS.
- Prior independent code-review recheck:67PASS across API/review/analysis/security/templates/storage; recorded in docs/CODE_REVIEW.md.

Current interpretation: the listed implementation defects have scoped recovery evidence except AR10's specifically identified browser scenario. This code reviewer does not issue architecture CLEAR. Actual Supabase DB/Storage/Auth/RLS/restart, actual local OAuth inference, remaining acceptance evidence and OMX strict gate remain outstanding. Product completion, deployment and publication are not approved by this matrix.
## AR10 targeted browser evidence closure

2026-09-21 KST, /root/final_code_review. This supersedes only the AR10 scenario gap in the matrix above. Earlier failures and evidence remain preserved.

Reviewed the actual artifact ops/runtime/browser-mixed-upload-2026-09-21T13-28-04-176Z.json and its runner tests/ui/browser_mixed_upload.cjs. The separate independent browser lane recorded10PASS with zero JavaScript errors under explicit TEST_STORAGE_INJECTED.

The runner submits a single UI upload batch containing a newly generated TXT with31calendar days and a corrupt DOCX. It asserts two stored records; valid extraction and visible document row; explicit ERROR for the corrupt document; retry button and mixed-result warning; retry remaining ERROR; both original byte sequences preserved; successful document still usable in a generated ITB draft; no removed failure/processing KPI.

Original-file evidence is separated correctly: the UI opens each original endpoint successfully, the TXT popup visibly contains31calendar days, and a separately authenticated API request proves exact bytes for each file, including the corrupt DOCX after retry. It does not claim that an empty Chromium CDP response-body observation proved byte identity. This is a justified measurement correction with explicit checks, not suppression of a product failure.

AR10 is CLOSED for the reported missing conversion-retry/honest mixed-status UI behavior. This reviewer validated artifact/script correspondence, not a second browser execution. The closure establishes the local product behavior in the injected-storage fixture; live Supabase persistence/RLS/Auth, actual local OAuth, realistic presentation layout and remaining overall acceptance/strict-gate requirements are unchanged. No overall architecture CLEAR or product-completion approval is issued.