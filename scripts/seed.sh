#!/usr/bin/env bash
# SignalOps — Seed traceability store with sample data
# Usage: ./scripts/seed.sh
#
# Populates the traceability store with realistic sample reports, tool calls,
# and source references so developers can explore the UI and debug panel
# without running a full end-to-end flow.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

TRACEABILITY_URL="${TRACEABILITY_STORE_URL:-http://localhost:8002}"

# ─── Helpers ──────────────────────────────────────────────────────────────────
info()    { echo "[SEED] $*"; }
success() { echo "[SEED] OK: $*"; }
warn()    { echo "[SEED] WARN: $*" >&2; }
error()   { echo "[SEED] ERROR: $*" >&2; exit 1; }

post_json() {
  local path="$1"
  local body="$2"
  curl -sf \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-Request-ID: seed-$(date +%s)" \
    -d "${body}" \
    "${TRACEABILITY_URL}${path}" \
    || return 1
}

# ─── Check traceability store is reachable ────────────────────────────────────
info "Checking traceability store at ${TRACEABILITY_URL}..."
if ! curl -sf "${TRACEABILITY_URL}/health" &>/dev/null; then
  warn "Traceability store is not reachable at ${TRACEABILITY_URL}."
  warn "Is the service running? Try: docker compose up -d traceability-store"
  warn "Skipping seed."
  exit 0
fi
success "Traceability store is reachable"

# ─── Sample Report 1: Weekly Report ───────────────────────────────────────────
info "Seeding weekly_report for Walmart Connect..."

REPORT_1_ID="rpt_seed001"
REPORT_1_GENERATED="2026-02-28T12:00:00Z"

post_json "/api/reports" "$(cat <<'EOF'
{
  "report_id": "rpt_seed001",
  "digest_type": "weekly_report",
  "query": "Anything important about Walmart Connect this week?",
  "generated_at": "2026-02-28T12:00:00Z",
  "user_id": "seed-user",
  "digest_json": {
    "digest_type": "weekly_report",
    "query": "Anything important about Walmart Connect this week?",
    "generated_at": "2026-02-28T12:00:00Z",
    "report_id": "rpt_seed001",
    "executive_summary": "Walmart Connect made significant moves this week, expanding its self-serve advertising platform and announcing a new API integration program. These changes position Walmart Connect as a stronger competitor to Amazon Advertising and Google Ads in the retail media space.",
    "key_signals": [
      {
        "signal": "Walmart Connect launched expanded self-serve tools targeting mid-market brands, lowering the minimum spend threshold from $50K to $5K per month.",
        "source_url": "https://www.adexchanger.com/retail-media/walmart-connect-self-serve-expansion-2026",
        "source_title": "Walmart Connect Lowers Barrier to Entry with Self-Serve Expansion",
        "published_date": "2026-02-27T09:00:00Z",
        "relevance": "high"
      },
      {
        "signal": "Walmart Connect announced API partnerships with three major DSPs, enabling programmatic access to Walmart's first-party shopper data.",
        "source_url": "https://www.marketingweek.com/walmart-connect-dsp-api-partnerships",
        "source_title": "Walmart Connect Opens API to Programmatic Buyers",
        "published_date": "2026-02-25T14:30:00Z",
        "relevance": "high"
      }
    ],
    "risks": [
      {
        "description": "Walmart Connect's self-serve expansion directly threatens mid-market advertisers who previously chose our platform due to lower minimums. We may see churn among $5K-$50K monthly spend customers.",
        "severity": "high",
        "source_urls": ["https://www.adexchanger.com/retail-media/walmart-connect-self-serve-expansion-2026"]
      }
    ],
    "opportunities": [
      {
        "description": "Walmart Connect's API partnership with DSPs creates a precedent for retail media API standards. We should accelerate our own API program to attract the same DSP partners.",
        "confidence": "medium",
        "source_urls": ["https://www.marketingweek.com/walmart-connect-dsp-api-partnerships"]
      }
    ],
    "action_items": [
      {
        "action": "Conduct competitive analysis of Walmart Connect's new self-serve pricing tiers and adjust our own pricing strategy by EOW.",
        "priority": "P0",
        "rationale": "The $5K minimum threshold directly competes with our entry-level tier. We risk losing mid-market customers before they evaluate our platform."
      },
      {
        "action": "Schedule meeting with DSP partner team to discuss API roadmap acceleration.",
        "priority": "P1",
        "rationale": "Walmart Connect has established DSP API partnerships we don't yet have. First-mover advantage with remaining DSPs is achievable."
      }
    ],
    "sources": [
      {
        "url": "https://www.adexchanger.com/retail-media/walmart-connect-self-serve-expansion-2026",
        "title": "Walmart Connect Lowers Barrier to Entry with Self-Serve Expansion",
        "published_date": "2026-02-27T09:00:00Z",
        "snippet": "Walmart Connect announced today that it is reducing the minimum monthly spend for its self-serve advertising platform from $50,000 to $5,000, opening the platform to thousands of mid-market brands."
      },
      {
        "url": "https://www.marketingweek.com/walmart-connect-dsp-api-partnerships",
        "title": "Walmart Connect Opens API to Programmatic Buyers",
        "published_date": "2026-02-25T14:30:00Z",
        "snippet": "Three major demand-side platforms have signed API partnership agreements with Walmart Connect, enabling programmatic buyers to access Walmart's proprietary shopper data for audience targeting."
      }
    ],
    "tool_trace": [
      {
        "tool_name": "search_company_news",
        "input": {"company": "Walmart Connect", "time_range": "7d"},
        "output_summary": "Returned 8 articles. Top result: self-serve expansion announcement.",
        "latency_ms": 1240,
        "timestamp": "2026-02-28T11:58:12Z"
      },
      {
        "tool_name": "search_news",
        "input": {"query": "Walmart Connect retail media advertising", "time_range": "7d", "num_results": 10},
        "output_summary": "Returned 10 articles. Found DSP partnership announcement and earnings mention.",
        "latency_ms": 987,
        "timestamp": "2026-02-28T11:58:14Z"
      }
    ]
  }
}
EOF
)" && success "Report rpt_seed001 created" || warn "Failed to create rpt_seed001 (may already exist)"

# ─── Tool calls for Report 1 ──────────────────────────────────────────────────
info "Seeding tool calls for rpt_seed001..."

post_json "/api/reports/rpt_seed001/tool-calls" "$(cat <<'EOF'
{
  "tool_name": "search_company_news",
  "input_json": {"company": "Walmart Connect", "time_range": "7d"},
  "output_json": {"total_results": 8, "cached": false},
  "latency_ms": 1240,
  "status": "success",
  "timestamp": "2026-02-28T11:58:12Z"
}
EOF
)" && success "Tool call 1 for rpt_seed001 created" || warn "Failed (may already exist)"

post_json "/api/reports/rpt_seed001/tool-calls" "$(cat <<'EOF'
{
  "tool_name": "search_news",
  "input_json": {"query": "Walmart Connect retail media advertising", "time_range": "7d", "num_results": 10},
  "output_json": {"total_results": 10, "cached": false},
  "latency_ms": 987,
  "status": "success",
  "timestamp": "2026-02-28T11:58:14Z"
}
EOF
)" && success "Tool call 2 for rpt_seed001 created" || warn "Failed (may already exist)"

# ─── Sources for Report 1 ─────────────────────────────────────────────────────
info "Seeding sources for rpt_seed001..."

post_json "/api/reports/rpt_seed001/sources" "$(cat <<'EOF'
[
  {
    "url": "https://www.adexchanger.com/retail-media/walmart-connect-self-serve-expansion-2026",
    "title": "Walmart Connect Lowers Barrier to Entry with Self-Serve Expansion",
    "source_name": "AdExchanger",
    "published_date": "2026-02-27T09:00:00Z",
    "snippet": "Walmart Connect announced today that it is reducing the minimum monthly spend for its self-serve advertising platform from $50,000 to $5,000.",
    "accessed_at": "2026-02-28T11:58:12Z"
  },
  {
    "url": "https://www.marketingweek.com/walmart-connect-dsp-api-partnerships",
    "title": "Walmart Connect Opens API to Programmatic Buyers",
    "source_name": "Marketing Week",
    "published_date": "2026-02-25T14:30:00Z",
    "snippet": "Three major demand-side platforms have signed API partnership agreements with Walmart Connect.",
    "accessed_at": "2026-02-28T11:58:14Z"
  }
]
EOF
)" && success "Sources for rpt_seed001 created" || warn "Failed (may already exist)"

# ─── Sample Report 2: Daily Digest ────────────────────────────────────────────
info "Seeding daily_digest for Salesforce..."

post_json "/api/reports" "$(cat <<'EOF'
{
  "report_id": "rpt_seed002",
  "digest_type": "daily_digest",
  "query": "Daily digest for Salesforce",
  "generated_at": "2026-03-01T08:00:00Z",
  "user_id": "seed-user",
  "digest_json": {
    "digest_type": "daily_digest",
    "query": "Daily digest for Salesforce",
    "generated_at": "2026-03-01T08:00:00Z",
    "report_id": "rpt_seed002",
    "executive_summary": "Salesforce had a quiet overnight period with no major announcements. One analyst note was published citing strong pipeline metrics from the Q4 earnings call.",
    "key_signals": [
      {
        "signal": "Analyst firm Bernstein maintained its Outperform rating on Salesforce, citing strong pipeline conversion rates from the Q4 2025 earnings call.",
        "source_url": "https://www.businesswire.com/news/salesforce-bernstein-outperform-2026",
        "source_title": "Bernstein Maintains Outperform on Salesforce Following Q4 Beat",
        "published_date": "2026-03-01T06:30:00Z",
        "relevance": "medium"
      }
    ],
    "risks": [],
    "opportunities": [],
    "action_items": [
      {
        "action": "Monitor Salesforce analyst coverage for any changes in competitive positioning guidance.",
        "priority": "P2",
        "rationale": "No immediate risks identified. Continued monitoring recommended."
      }
    ],
    "sources": [
      {
        "url": "https://www.businesswire.com/news/salesforce-bernstein-outperform-2026",
        "title": "Bernstein Maintains Outperform on Salesforce Following Q4 Beat",
        "published_date": "2026-03-01T06:30:00Z",
        "snippet": "Bernstein analyst maintains Outperform rating and $350 price target on Salesforce, citing stronger-than-expected pipeline metrics disclosed during the Q4 2025 earnings call."
      }
    ],
    "tool_trace": [
      {
        "tool_name": "search_company_news",
        "input": {"company": "Salesforce", "time_range": "1d"},
        "output_summary": "Returned 3 articles. Low signal activity overnight.",
        "latency_ms": 1105,
        "timestamp": "2026-03-01T07:59:01Z"
      }
    ]
  }
}
EOF
)" && success "Report rpt_seed002 created" || warn "Failed to create rpt_seed002 (may already exist)"

post_json "/api/reports/rpt_seed002/tool-calls" "$(cat <<'EOF'
{
  "tool_name": "search_company_news",
  "input_json": {"company": "Salesforce", "time_range": "1d"},
  "output_json": {"total_results": 3, "cached": false},
  "latency_ms": 1105,
  "status": "success",
  "timestamp": "2026-03-01T07:59:01Z"
}
EOF
)" && success "Tool call for rpt_seed002 created" || warn "Failed (may already exist)"

post_json "/api/reports/rpt_seed002/sources" "$(cat <<'EOF'
[
  {
    "url": "https://www.businesswire.com/news/salesforce-bernstein-outperform-2026",
    "title": "Bernstein Maintains Outperform on Salesforce Following Q4 Beat",
    "source_name": "Business Wire",
    "published_date": "2026-03-01T06:30:00Z",
    "snippet": "Bernstein analyst maintains Outperform rating and $350 price target on Salesforce.",
    "accessed_at": "2026-03-01T07:59:01Z"
  }
]
EOF
)" && success "Sources for rpt_seed002 created" || warn "Failed (may already exist)"

# ─── Sample Report 3: Risk Alert (No Results) ─────────────────────────────────
info "Seeding risk_alert with no results (guardrail example)..."

post_json "/api/reports" "$(cat <<'EOF'
{
  "report_id": "rpt_seed003",
  "digest_type": "risk_alert",
  "query": "Risk alert: ZephyrCloud acquisition rumors",
  "generated_at": "2026-03-01T10:30:00Z",
  "user_id": "seed-user",
  "digest_json": {
    "digest_type": "risk_alert",
    "query": "Risk alert: ZephyrCloud acquisition rumors",
    "generated_at": "2026-03-01T10:30:00Z",
    "report_id": "rpt_seed003",
    "executive_summary": "No relevant articles found for this query in the specified time range.",
    "key_signals": [],
    "risks": [],
    "opportunities": [],
    "action_items": [],
    "sources": [],
    "tool_trace": [
      {
        "tool_name": "search_company_news",
        "input": {"company": "ZephyrCloud", "time_range": "1d"},
        "output_summary": "Returned 0 articles. No recent news found for ZephyrCloud.",
        "latency_ms": 843,
        "timestamp": "2026-03-01T10:29:55Z"
      },
      {
        "tool_name": "search_news",
        "input": {"query": "ZephyrCloud acquisition", "time_range": "1d", "num_results": 10},
        "output_summary": "Returned 0 articles. No acquisition news found.",
        "latency_ms": 791,
        "timestamp": "2026-03-01T10:29:57Z"
      }
    ]
  }
}
EOF
)" && success "Report rpt_seed003 created" || warn "Failed to create rpt_seed003 (may already exist)"

# ─── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "[SEED] Seeding complete."
echo "[SEED] Sample reports available:"
echo "[SEED]   GET ${TRACEABILITY_URL}/api/reports"
echo "[SEED]   GET ${TRACEABILITY_URL}/api/reports/rpt_seed001"
echo "[SEED]   GET ${TRACEABILITY_URL}/api/reports/rpt_seed002"
echo "[SEED]   GET ${TRACEABILITY_URL}/api/reports/rpt_seed003"
