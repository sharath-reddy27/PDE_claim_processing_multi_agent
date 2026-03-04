from dotenv import load_dotenv
load_dotenv()

from graph import build_graph

TEST_CASES = [
    {"claim_id": "C0003", "error_code": "781"},  # Provider ID missing/invalid → RX_AGENT (ReAct) → REPORT → EMAIL
    {"claim_id": "C0002", "error_code": "935"},  # Already adjudicated → REPORT (ReAct) → EMAIL
]

DIVIDER = "=" * 65

if __name__ == "__main__":
    for test in TEST_CASES:
        print(f"\n{DIVIDER}")
        print(f"  DEMO RUN | Claim: {test['claim_id']} | Error Code: {test['error_code']}")
        print(DIVIDER)

        app = build_graph()
        result = app.invoke(test)

        print(f"\n{DIVIDER}")
        print("  FINAL STATE SUMMARY")
        print(DIVIDER)
        print(f"  Claim ID       : {result.get('claim_id')}")
        print(f"  Error Code     : {result.get('error_code')}")
        print(f"  Routed To      : {result.get('next_agent')}")
        print(f"  Supervisor Why : {result.get('reasoning', 'N/A')}")
        print(f"  Provider ID    : {result.get('provider_id', 'N/A')}")
        print(f"  Decision       : {result.get('decision')}")
        print(f"  Report         : {result.get('report')}")
        print(f"  Email Status   : {result.get('email_status')}")
        print(DIVIDER)

        # Print ReAct traces
        for label, key in [
            ("🧠 Orchestrator Trace",    "orchestrator_trace"),
            ("💊 RX Agent Trace",         "rx_agent_trace"),
            ("📋 Report Builder Trace",   "report_agent_trace"),
            ("📧 Email Agent Trace",      "email_agent_trace"),
        ]:
            trace = result.get(key, "")
            if trace:
                print(f"\n  {label}")
                print("  " + "-" * 55)
                for line in trace.split("\n"):
                    print(f"  {line}")
        print()
