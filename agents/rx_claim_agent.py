"""
RX Claim Agent - ReAct Specialist
===================================
Handles ALL claim adjudication logic for error codes 781 and 935.

Error 781 — Missing / Invalid Provider ID:
  1. Fetch the claim from the DB
  2. Resolve missing/invalid provider ID via the mapping table
  3. Update the claim record with the corrected provider ID
  4. Decide: REPROCESS (provider resolved) or REJECT (no mapping found)
  5. Update claim status in the DB

Error 935 — Already Adjudicated:
  1. Fetch the claim from the DB
  2. Compare received_date vs adjudication_ts
  3. If dates EQUAL       → mark claim READY_FOR_REPROCESS
  4. If adj_ts MORE RECENT → mark claim ALREADY_PROCESSED
  5. Update claim status in the DB
"""
from dotenv import load_dotenv
load_dotenv()

import json, re
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from tools.llm_tools import llm
from tools.db_tools import (
    tool_get_claim,
    tool_get_provider_mapping,
    tool_update_claim_provider_id,
    tool_update_claim_status,
    tool_compare_claim_dates,
    get_claim,
    get_provider_mapping,
)

# ── System prompt — covers BOTH error codes ───────────────────────────────────
RX_SYSTEM = """You are an RX claim adjudication specialist for a Medicare Part D PDE system.
You handle two types of PDE claim errors depending on the error code provided.

══════════════════════════════════════════
ERROR CODE 781 — Missing / Invalid Provider ID
══════════════════════════════════════════
Step-by-step process:
1. Fetch the claim details using tool_get_claim.
2. Check the provider_id from the claim.
3. Look up the CMS-validated provider using tool_get_provider_mapping.
   - Pass empty string '' if provider_id is MISSING or blank.
4. If a mapping is found, update the claim's provider_id with tool_update_claim_provider_id.
5. Decide:
   - Provider resolved successfully → REPROCESS
   - No valid provider found        → REJECT
6. Update the claim status using tool_update_claim_status:
   - REPROCESS → status = "READY_FOR_REPROCESS"
   - REJECT    → status = "REJECTED"

Respond with JSON:
{
  "decision": "REPROCESS" or "REJECT",
  "provider_resolved": true or false,
  "new_provider_id": "<id or null>",
  "received_date": null,
  "adjudication_ts": null,
  "reason": "detailed explanation"
}

══════════════════════════════════════════
ERROR CODE 935 — Already Adjudicated
══════════════════════════════════════════
Step-by-step process:
1. Fetch the claim details using tool_get_claim.
2. Compare received_date vs adjudication_ts using tool_compare_claim_dates.
3. Based on the result:
   - Dates EQUAL (same day)       → claim may be a duplicate submission.
     Update status to "READY_FOR_REPROCESS" using tool_update_claim_status.
     Decision = REPROCESS
   - adjudication_ts MORE RECENT  → claim was genuinely processed after receipt.
     Update status to "ALREADY_PROCESSED" using tool_update_claim_status.
     Decision = ALREADY_PROCESSED

Respond with JSON:
{
  "decision": "REPROCESS" or "ALREADY_PROCESSED",
  "provider_resolved": false,
  "new_provider_id": null,
  "received_date": "<the received_date value>",
  "adjudication_ts": "<the adjudication_ts value>",
  "reason": "clear explanation of the date comparison and your decision"
}
"""

# Single agent instance with all tools for both paths
_rx_agent = create_agent(
    model=llm,
    tools=[
        tool_get_claim,
        tool_get_provider_mapping,
        tool_update_claim_provider_id,
        tool_update_claim_status,
        tool_compare_claim_dates,
    ],
    system_prompt=RX_SYSTEM,
)


def rx_claim_agent(state: dict) -> dict:
    print("\n[RX Claim Agent] =============================")
    claim_id   = state.get("claim_id")
    error_code = state.get("error_code")
    sop_text   = state.get("sop_text", "SOP not loaded")

    print(f"[RX Claim Agent] Processing claim: {claim_id} | Error: {error_code}")

    # Build the task message based on error code
    if error_code == "935":
        task_instructions = (
            "This is an ERROR CODE 935 (Already Adjudicated) claim.\n"
            "Follow the 935 process: fetch claim → compare dates → update DB status → decide."
        )
    else:
        task_instructions = (
            "This is an ERROR CODE 781 (Missing/Invalid Provider ID) claim.\n"
            "Follow the 781 process: fetch claim → resolve provider → update DB → decide."
        )

    user_msg = (
        f"Adjudicate PDE claim.\n"
        f"  claim_id   = {claim_id}\n"
        f"  error_code = {error_code}\n\n"
        f"Standard Operating Procedure:\n{sop_text}\n\n"
        f"{task_instructions}"
    )

    react_result = _rx_agent.invoke({"messages": [HumanMessage(content=user_msg)]})

    final_message = react_result["messages"][-1].content
    print(f"[RX Claim Agent] ReAct final output:\n{final_message}")

    # ── Capture trace for UI ──────────────────────────────────────────────────
    trace_lines = []
    for msg in react_result["messages"]:
        role = getattr(msg, "type", type(msg).__name__)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                trace_lines.append(f"🔧 Tool: {tc['name']}({tc['args']})")
        elif hasattr(msg, "content") and msg.content:
            trace_lines.append(f"💬 [{role}]: {str(msg.content)[:400]}")
    state["rx_agent_trace"] = "\n".join(trace_lines)

    # ── Parse decision ────────────────────────────────────────────────────────
    default_decision = "REJECT" if error_code == "781" else "ALREADY_PROCESSED"
    decision    = default_decision
    reason      = final_message
    new_prov_id = None

    json_match = re.search(r'\{.*?"decision".*?\}', final_message, re.DOTALL)
    if json_match:
        try:
            parsed      = json.loads(json_match.group())
            decision    = parsed.get("decision", default_decision).strip().upper()
            reason      = parsed.get("reason", final_message)
            new_prov_id = parsed.get("new_provider_id")
            # Capture 935-specific date fields into state
            if parsed.get("received_date"):
                state["received_date"] = parsed["received_date"]
            if parsed.get("adjudication_ts"):
                state["adjudication_ts"] = parsed["adjudication_ts"]
        except json.JSONDecodeError:
            if "REPROCESS" in final_message.upper():
                decision = "REPROCESS"
    else:
        if "REPROCESS" in final_message.upper():
            decision = "REPROCESS"

    # ── Refresh provider info from DB ─────────────────────────────────────────
    claim = get_claim(claim_id)
    if claim:
        state["provider_id"]   = claim.get("provider_id", "")
        state["received_date"] = claim.get("received_date", "")

    if new_prov_id:
        state["provider_id"] = new_prov_id
        resolved = get_provider_mapping(new_prov_id) or get_provider_mapping("")
        if resolved:
            state["resolved_provider"] = resolved

    state["decision"] = decision
    state["reason"]   = reason

    # ── Log final decision ────────────────────────────────────────────────────
    if error_code == "781":
        icon = "✅" if decision == "REPROCESS" else "❌"
        print(f"[RX Claim Agent] {icon} Decision: {decision}")
    else:
        icon = "✅" if decision == "REPROCESS" else "ℹ️"
        print(f"[RX Claim Agent] {icon} Decision: {decision} "
              f"({'dates equal' if decision == 'REPROCESS' else 'adj_ts more recent'})")

    print("[RX Claim Agent] =============================\n")
    return state