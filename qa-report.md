# SignalOps QA Test Report

**Date:** 2026-03-02
**Suite run:** `node run_qa_tests.js`
**Base URL:** http://localhost:3000
**Duration:** ~12 minutes (18:15:40 – 18:27:56 UTC)

---

## Summary

| Result   | Count |
|----------|-------|
| PASS     | 7     |
| FAIL     | 1     |
| SKIPPED  | 0     |
| **TOTAL**| **8** |

**Overall verdict: PASS** — The 1 failure (T5) is a **test script defect**, not an application defect. The app correctly prevents empty submissions via a disabled submit button; the test script did not handle this case.

---

## Test Results

### T1 — Daily digest for Walmart Connect
**Status: PASS**
**Duration:** ~108s
**Prompt:** `Daily digest for Walmart Connect`

**Observations:**
- `digest_type` correctly rendered as `Daily Digest`
- Executive summary present with substantive Walmart Connect content
- 7 key signals extracted and displayed
- `report_id: rpt_8bbf74c8411d` generated correctly

**Sample output excerpt:**
> *"Walmart Connect is scaling rapidly toward ~$6.4B in revenue with 31-53% quarterly growth, now contributing nearly a third of Walmart's total profit..."*

---

### T2 — Weekly report on Amazon Advertising
**Status: PASS**
**Duration:** ~113s
**Prompt:** `Weekly report on Amazon Advertising`

**Observations:**
- `digest_type` correctly rendered as `Weekly Report`
- Key signals section visible with 7 signals
- Tool trace visible in UI
- Rich content: Amazon Ads AI stack, DSP integrations, Rufus $12B sales figure

---

### T3 — Risk alert for Target retail media
**Status: PASS**
**Duration:** ~97s
**Prompt:** `Risk alert for Target retail media`

**Observations:**
- `digest_type` correctly rendered as `Risk Alert`
- Risks section present and non-empty
- 6 key signals extracted; identified China-backed e-commerce platform threats (Temu, Shein, TikTok Shop) and tariff supply chain disruption as primary risks

---

### T4 — Competitor monitor (emerging retail media competitors)
**Status: PASS**
**Duration:** ~97s
**Prompt:** `Who are the emerging competitors in retail media`

**Observations:**
- `digest_type` correctly rendered as `Competitor Monitor`
- Competitor-related content present (Criteo, Google, Meta, Amazon triopoly analysis)
- Market projection data ($7.3B by 2034 at 20% CAGR) included

---

### T5 — Empty submit validation
**Status: FAIL** ⚠️ — *Test script defect, not app defect*
**Prompt:** `(empty)`

**Root cause:**
`submitPrompt()` unconditionally calls `await submitBtn.click()`. Playwright's `click()` action waits for the element to be **enabled** before clicking. The submit button has `disabled` attribute when the textarea is empty, so Playwright waited 30s and timed out.

**App behavior is CORRECT:** The button is correctly disabled (`<button disabled type="submit" aria-label="Submit digest request">`) when no input is provided. This prevents empty submissions without a crash or error state.

**Test fix needed:** In `submitPrompt()`, check `isDisabled()` before calling `click()`, or use `page.evaluate()` to force-click if the goal is to validate form validation feedback.

---

### T6 — Latest news for Google
**Status: PASS**
**Duration:** ~104s
**Prompt:** `Latest news for Google`

**Observations:**
- Content rendered successfully; digest type shown as `Daily Digest` (correct fallback for "latest news" intent)
- Rich content: Google $1T data center bond, Gemini multi-step tasks, Universal Commerce Protocol, quantum-resistant HTTPS

---

### T7 — Simple entity without intent keyword
**Status: PASS**
**Duration:** ~79s
**Prompt:** `Walmart Connect`

**Observations:**
- Graceful fallback: app produced content without an explicit intent keyword
- `digest_type` rendered as `Competitor Monitor` (reasonable inference from entity-only query)
- 6 key signals; content substantive and relevant to Walmart Connect

---

### T8 — Re-submit T1 prompt
**Status: PASS**
**Duration:** ~88s
**Prompt:** `Daily digest for Walmart Connect`

**Observations:**
- Re-submission produced fresh results (`report_id: rpt_56edf837ea4a` — different from T1's `rpt_8bbf74c8411d`)
- No blank state, no error; content fully rendered
- Confirms stateless request handling

---

## Defects

| ID  | Component       | Severity | Description                                                                 | Status    |
|-----|-----------------|----------|-----------------------------------------------------------------------------|-----------|
| QA-1 | `run_qa_tests.js` | Low    | T5 `submitPrompt()` calls `.click()` without checking `isDisabled()` first. Playwright times out on a legitimately disabled button. App behavior is correct. | Test fix needed |

---

## Pipeline Defects Fixed (Pre-QA)

The following defects were identified and fixed before this QA run:

| ID  | Component           | Description                                                                 | Fix                                     |
|-----|---------------------|-----------------------------------------------------------------------------|-----------------------------------------|
| D1  | mcp-wrapper         | MCPClient POSTed to `/tools/{name}` but server only had SSE routes → 404 → zero articles | Added REST dispatch route to Starlette app |
| D2  | agent-orchestrator  | `json.loads()` on Claude's markdown-fenced JSON responses → `JSONDecodeError` → wrong digest_type | Added `_extract_json_from_text()` fence-stripper |
| D3  | mcp-wrapper         | `engine=google_news` + `tbm=nws` invalid parameter combination              | Removed `tbm=nws` from SerpApi params   |
| D4  | agent-orchestrator  | `_signals`, `_risks`, `_opportunities`, `_action_items` missing from `OrchestratorState` TypedDict | Added all 4 keys to TypedDict |
| D5  | mcp-wrapper         | Normalizer only read `news_results`; SerpApi sometimes returns `top_stories` | Added `top_stories` fallback            |
| D6  | agent-orchestrator  | `str.format()` on prompt templates containing literal `{...}` JSON → `KeyError` | Replaced all `.format()` with `.replace()` |

---

## Screenshots

All screenshots saved to `qa-screenshots/`:

| Test | Before | After |
|------|--------|-------|
| T1   | T1-before.png | T1-after.png |
| T2   | T2-before.png | T2-after.png |
| T3   | T3-before.png | T3-after.png |
| T4   | T4-before.png | T4-after.png |
| T5   | T5-before.png | T5-error.png |
| T6   | T6-before.png | T6-after.png |
| T7   | T7-before.png | T7-after.png |
| T8   | T8-before.png | T8-after.png |

---

## Conclusion

The SignalOps pipeline is **fully functional end-to-end**. All 4 primary intent types (`daily_digest`, `weekly_report`, `risk_alert`, `competitor_monitor`) render correctly. The system handles simple entity queries with a graceful fallback, and re-submissions work without state issues. Response times averaged ~97–113s per request (LLM-bound: 3+ Claude API calls per pipeline run plus SerpApi fetch).

The single test failure (T5) reflects a test script issue with Playwright's click semantics on disabled buttons — the app itself correctly disables the submit button for empty input.
