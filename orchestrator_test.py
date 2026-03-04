"""
Dynamic Orchestrator – End-to-End Test
========================================
Tests the dynamic orchestrator for all four scenarios:
  1. Error 781  – missing provider  → REPROCESS        (rx → report → servicenow → email)
  2. Error 935  – dates equal       → REPROCESS        (rx → report → servicenow → email)
  3. Error 935  – adj_ts newer      → ALREADY_PROCESSED (rx → report → email only)
  4. Error 781  – invalid provider, no mapping → REJECT (rx only — no report/email/servicenow)

The orchestrator reads the SOP, fetches the claim, then DECIDES which
specialist agents to call — we verify it invokes only the correct ones.
"""
from graph import build_graph

# ── Test cases ────────────────────────────────────────────────────────────────
TEST_CASES = [
    {
        "label":        "Scenario 1 — Error 781 (Missing Provider → REPROCESS)",
        "claim_id":     "C0009",    # provider='', status=NEW → mapping found (P002) → REPROCESS
        "error_code":   "781",
        "expect_decision":       "REPROCESS",
        "expect_agents_include": ["RX_AGENT", "REPORT", "SERVICENOW", "EMAIL"],
        "expect_agents_exclude": [],
    },
    {
        "label":        "Scenario 2 — Error 935 (Dates Equal → REPROCESS)",
        "claim_id":     "C0010",    # received=2025-01-02, adj_ts=2025-01-02 (equal dates)
        "error_code":   "935",
        "expect_decision":       "REPROCESS",
        "expect_agents_include": ["RX_AGENT", "REPORT", "SERVICENOW", "EMAIL"],
        "expect_agents_exclude": [],
    },
    {
        "label":        "Scenario 3 — Error 935 (Adj newer → ALREADY_PROCESSED)",
        "claim_id":     "C0006",    # received=2024-12-15, adj_ts=2025-01-02 (adj is newer)
        "error_code":   "935",
        "expect_decision":       "ALREADY_PROCESSED",
        "expect_agents_include": ["RX_AGENT", "REPORT", "EMAIL"],
        "expect_agents_exclude": ["SERVICENOW"],  # no ticket for already-processed claims
    },
    {
        "label":        "Scenario 4 — Error 781 (Invalid Provider P999, No Mapping → REJECT)",
        "claim_id":     "TEST-REJECT-001",  # provider=P999, no mapping exists → REJECT
        "error_code":   "781",
        "expect_decision":       "REJECT",
        "expect_agents_include": ["RX_AGENT"],                        # only RX agent runs
        "expect_agents_exclude": ["REPORT", "SERVICENOW", "EMAIL"],   # ALL skipped on REJECT
    },
]

SEP = "=" * 70


def run_test(tc: dict, app) -> bool:
    print(f"\n{SEP}")
    print(f"🧪 {tc['label']}")
    print(f"   claim_id={tc['claim_id']}  error_code={tc['error_code']}")
    print(SEP)

    result = app.invoke({
        "claim_id":   tc["claim_id"],
        "error_code": tc["error_code"],
    })

    decision       = result.get("decision", "")
    agents_invoked = result.get("agents_invoked", [])
    reasoning      = result.get("reasoning", "")
    report         = result.get("report", "")
    rcl_file       = result.get("rcl_file", "")
    sn_ticket      = result.get("servicenow_ticket", "")
    email_status   = result.get("email_status", "")

    # ── Print collected outputs ───────────────────────────────────────────────
    print(f"\n📋 ORCHESTRATOR COLLECTED OUTPUTS:")
    print(f"   ✅ Decision        : {decision}")
    print(f"   🤖 Agents invoked  : {' → '.join(agents_invoked) if agents_invoked else 'none'}")
    print(f"   💡 Reasoning       : {reasoning[:200] if reasoning else 'N/A'}")
    print(f"   📄 Report          : {'YES (' + report[:80] + '...)' if report else 'NO'}")
    print(f"   📁 RCL File        : {rcl_file or 'N/A'}")
    print(f"   🎫 ServiceNow      : {sn_ticket or 'N/A'}")
    print(f"   📧 Email status    : {email_status or 'N/A'}")
    print(f"   🔑 Provider ID     : {result.get('provider_id', 'N/A')}")
    print(f"   📅 Received date   : {result.get('received_date', 'N/A')}")
    print(f"   📅 Adj timestamp   : {result.get('adjudication_ts', 'N/A')}")

    # ── Assertions ────────────────────────────────────────────────────────────
    passed = True

    if tc["expect_decision"] and decision.upper() != tc["expect_decision"].upper():
        print(f"\n   ❌ FAIL — Expected decision '{tc['expect_decision']}' but got '{decision}'")
        passed = False
    else:
        print(f"\n   ✅ Decision check passed: {decision}")

    for agent in tc["expect_agents_include"]:
        if agent not in agents_invoked:
            print(f"   ❌ FAIL — Expected agent '{agent}' to be invoked but it was not")
            passed = False
        else:
            print(f"   ✅ Agent '{agent}' was correctly invoked")

    for agent in tc["expect_agents_exclude"]:
        if agent in agents_invoked:
            print(f"   ❌ FAIL — Agent '{agent}' should NOT have been invoked but it was")
            passed = False
        else:
            print(f"   ✅ Agent '{agent}' was correctly SKIPPED")

    status = "✅ PASSED" if passed else "❌ FAILED"
    print(f"\n   {status}")
    return passed


if __name__ == "__main__":
    print("\n" + SEP)
    print("🚀 DYNAMIC ORCHESTRATOR — END-TO-END TEST (4 SCENARIOS)")
    print("   Orchestrator reads SOP → decides which agents to invoke per claim")
    print(SEP)

    app = build_graph()

    results = []
    for tc in TEST_CASES:
        ok = run_test(tc, app)
        results.append((tc["label"], ok))

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("📊 TEST SUMMARY")
    print(SEP)
    all_passed = True
    for label, ok in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {label}")
        if not ok:
            all_passed = False

    print(SEP)
    if all_passed:
        print("🎉 ALL TESTS PASSED — Dynamic orchestrator is working correctly!")
    else:
        print("⚠️  SOME TESTS FAILED — review output above.")
    print(SEP + "\n")

