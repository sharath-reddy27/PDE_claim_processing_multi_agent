"""
Report Builder Agent – ReAct Specialist
=========================================
Handles two report types:
  1. Error 781 / 935-REPROCESS → Generate RCL file for CMS resubmission
  2. Error 935-ALREADY_PROCESSED → Send compliance report to PDE team
"""
from dotenv import load_dotenv
load_dotenv()

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from tools.llm_tools import llm
from tools.db_tools import (
    tool_get_claim,
    tool_insert_report,
    tool_generate_rcl_file,
    tool_get_reprocess_claims_summary,
)

REPORT_SYSTEM = """You are a PDE compliance report writer for a Medicare Part D claim system.

You handle two distinct reporting scenarios:

SCENARIO A — REPROCESS decision (error 781 OR error 935 with equal dates):
1. Fetch claim details using tool_get_claim.
2. Get a summary of all claims marked for reprocessing using tool_get_reprocess_claims_summary.
3. Generate the RCL (Reprocess Claims List) CSV file using tool_generate_rcl_file.
4. Save a report using tool_insert_report with decision="REPROCESS".
5. Report reason should note the RCL file was generated and list the claim count.

SCENARIO B — ALREADY_PROCESSED decision (error 935 adjudication_ts more recent):
1. Fetch claim details using tool_get_claim.
2. Save a report using tool_insert_report with decision="ALREADY_PROCESSED".
3. Report reason should state: claim excluded from reprocessing, included in PDE compliance report.

After completing, respond with a JSON block:
{
  "report": "the exact report text saved",
  "decision": "REPROCESS" or "ALREADY_PROCESSED",
  "rcl_file": "<file path if generated, else null>"
}
"""

_report_agent = create_agent(
    model=llm,
    tools=[tool_get_claim, tool_insert_report, tool_generate_rcl_file, tool_get_reprocess_claims_summary],
    system_prompt=REPORT_SYSTEM,
)


def report_builder_agent(state: dict) -> dict:
    print("\n[Report Builder Agent] =============================")
    claim_id    = state.get("claim_id")
    error_code  = state.get("error_code")
    decision    = state.get("decision", "UNKNOWN")
    provider_id = state.get("provider_id", "N/A")
    reason      = state.get("reason", "")

    print(f"[Report Builder Agent] Claim: {claim_id} | Error: {error_code} | Decision: {decision}")

    user_msg = (
        f"Generate a compliance report for PDE claim.\n"
        f"  claim_id    = {claim_id}\n"
        f"  error_code  = {error_code}\n"
        f"  provider_id = {provider_id}\n"
        f"  decision    = {decision}\n"
        f"  reason      = {reason[:300] if reason else 'N/A'}\n\n"
        f"{'SCENARIO A: Claim needs reprocessing. Generate RCL file and save report.' if decision == 'REPROCESS' else 'SCENARIO B: Claim already processed. Save compliance report for PDE team.'}"
    )

    react_result = _report_agent.invoke({"messages": [HumanMessage(content=user_msg)]})

    final_message = react_result["messages"][-1].content
    print(f"[Report Builder Agent] ReAct final output:\n{final_message}")

    # Capture trace
    trace_lines = []
    for msg in react_result["messages"]:
        role = getattr(msg, "type", type(msg).__name__)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                trace_lines.append(f"🔧 Tool: {tc['name']}({tc['args']})")
        elif hasattr(msg, "content") and msg.content:
            trace_lines.append(f"💬 [{role}]: {str(msg.content)[:400]}")
    state["report_agent_trace"] = "\n".join(trace_lines)

    # Parse result
    import json, re
    report_text = final_message
    rcl_file    = None

    json_match = re.search(r'\{.*?"report".*?\}', final_message, re.DOTALL)
    if json_match:
        try:
            parsed      = json.loads(json_match.group())
            report_text = parsed.get("report", final_message)
            new_decision = parsed.get("decision", decision)
            rcl_file    = parsed.get("rcl_file")
            state["decision"] = new_decision
        except json.JSONDecodeError:
            pass

    state["report"]   = report_text
    state["rcl_file"] = rcl_file or ""

    print(f"[Report Builder Agent] ✅ Report saved. RCL file: {rcl_file or 'N/A'}")
    print("[Report Builder Agent] =============================\n")
    return state
