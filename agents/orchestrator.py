"""
Orchestrator Agent – Dynamic ReAct Supervisor
===============================================
Fully dynamic: reads the SOP for the error code, fetches the claim,
then decides WHICH specialist agents to invoke and in WHAT ORDER by
calling them as tools inside its own ReAct loop.

Specialist agents exposed as tools:
  • tool_run_rx_agent         – adjudicates the claim (781 or 935)
  • tool_run_report_agent     – builds compliance report / generates RCL file
  • tool_run_servicenow_agent – raises a ServiceNow incident ticket
  • tool_run_email_agent      – composes and sends notification email

Routing is entirely LLM-driven:
  - The supervisor reads the SOP and decides which agents are needed.
  - For error 781 REPROCESS:           rx → report → servicenow → email
  - For error 781 REJECT:              rx only (no report, no email)
  - For error 935 REPROCESS:           rx → report → servicenow → email
  - For error 935 ALREADY_PROCESSED:   rx → report → email (no servicenow)

State is passed via a module-level context dict that the tool wrappers
read/write, allowing the orchestrator's tool calls to share context.
"""
from dotenv import load_dotenv
load_dotenv()

import json
import re
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from tools.llm_tools import llm
from tools.sop_tools import tool_load_sop, load_sop
from tools.db_tools import tool_get_claim

# ── Shared context bag ────────────────────────────────────────────────────────
# Each run resets _ctx; tool wrappers read/write into it so agents can
# pass results to subsequent agents without touching LangGraph state directly.
_ctx: dict = {}


# ── Specialist agent tool wrappers ────────────────────────────────────────────

@tool
def tool_run_rx_agent(claim_id: str, error_code: str) -> str:
    """
    Invoke the RX Claim specialist agent to adjudicate a PDE claim.

    Handles two error types:
      • Error 781 – resolves missing/invalid provider ID → REPROCESS or REJECT
      • Error 935 – compares received_date vs adjudication_ts → REPROCESS or ALREADY_PROCESSED

    Parameters:
      claim_id   : the PDE claim identifier
      error_code : '781' or '935'

    Returns a JSON string with keys: decision, reason, provider_id, new_provider_id,
    received_date, adjudication_ts.
    """
    from agents.rx_claim_agent import rx_claim_agent

    sub_state = {
        "claim_id":   claim_id,
        "error_code": error_code,
        "sop_text":   _ctx.get("sop_text", ""),
    }
    result = rx_claim_agent(sub_state)

    # Persist outputs back to shared context
    _ctx.update({
        "decision":          result.get("decision", ""),
        "reason":            result.get("reason", ""),
        "provider_id":       result.get("provider_id", ""),
        "resolved_provider": result.get("resolved_provider"),
        "received_date":     result.get("received_date", ""),
        "adjudication_ts":   result.get("adjudication_ts", ""),
        "rx_agent_trace":    result.get("rx_agent_trace", ""),
    })

    return json.dumps({
        "decision":        result.get("decision", ""),
        "reason":          (result.get("reason") or "")[:400],
        "provider_id":     result.get("provider_id", ""),
        "new_provider_id": result.get("provider_id", ""),
        "received_date":   result.get("received_date", ""),
        "adjudication_ts": result.get("adjudication_ts", ""),
    })


@tool
def tool_run_report_agent(claim_id: str, error_code: str, decision: str) -> str:
    """
    Invoke the Report Builder specialist agent to generate the appropriate
    compliance report or RCL (Reprocess Claims List) file.

    Use AFTER tool_run_rx_agent has produced a decision.
    Do NOT call this for a REJECT decision — no report is needed for rejected claims.

    Parameters:
      claim_id   : the PDE claim identifier
      error_code : '781' or '935'
      decision   : one of REPROCESS, REJECT, ALREADY_PROCESSED

    Returns a JSON string with keys: report, rcl_file, decision.
    """
    from agents.report_builder_agent import report_builder_agent

    sub_state = {
        "claim_id":    claim_id,
        "error_code":  error_code,
        "decision":    decision,
        "provider_id": _ctx.get("provider_id", "N/A"),
        "reason":      _ctx.get("reason", ""),
    }
    result = report_builder_agent(sub_state)

    _ctx.update({
        "report":             result.get("report", ""),
        "rcl_file":           result.get("rcl_file", ""),
        "report_agent_trace": result.get("report_agent_trace", ""),
        "decision":           result.get("decision", decision),
    })

    return json.dumps({
        "report":   (result.get("report") or "")[:400],
        "rcl_file": result.get("rcl_file", ""),
        "decision": result.get("decision", decision),
    })


@tool
def tool_run_servicenow_agent(claim_id: str, error_code: str, rcl_file: str) -> str:
    """
    Invoke the ServiceNow specialist agent to raise an incident ticket for
    claims that need reprocessing.

    Use ONLY when decision is REPROCESS (after tool_run_report_agent).
    Do NOT call for ALREADY_PROCESSED or REJECT decisions.

    Parameters:
      claim_id   : the PDE claim identifier
      error_code : '781' or '935'
      rcl_file   : path to the generated RCL file (or empty string if none)

    Returns a JSON string with keys: ticket_number, ticket_summary, claims_count.
    """
    from agents.servicenow_agent import servicenow_agent

    sub_state = {
        "claim_id":   claim_id,
        "error_code": error_code,
        "decision":   _ctx.get("decision", "REPROCESS"),
        "rcl_file":   rcl_file or _ctx.get("rcl_file", ""),
    }
    result = servicenow_agent(sub_state)

    _ctx.update({
        "servicenow_ticket":  result.get("servicenow_ticket", ""),
        "servicenow_summary": result.get("servicenow_summary", ""),
        "claims_count":       result.get("claims_count", 0),
        "servicenow_trace":   result.get("servicenow_trace", ""),
    })

    return json.dumps({
        "ticket_number":  result.get("servicenow_ticket", ""),
        "ticket_summary": result.get("servicenow_summary", ""),
        "claims_count":   result.get("claims_count", 0),
    })


@tool
def tool_run_email_agent(claim_id: str, error_code: str, decision: str) -> str:
    """
    Invoke the Email specialist agent to compose and send a notification
    email after a claim has been processed.

    Use as the FINAL step after reporting (and optionally ServiceNow).
    Do NOT call for REJECT decisions — no notification is sent for rejected claims.

    Parameters:
      claim_id   : the PDE claim identifier
      error_code : '781' or '935'
      decision   : the final decision (REPROCESS or ALREADY_PROCESSED)

    Returns a JSON string with keys: email_status, email_subject, email_summary.
    """
    from agents.email_agent import email_agent

    sub_state = {
        "claim_id":   claim_id,
        "error_code": error_code,
        "decision":   decision,
        "report":     _ctx.get("report", "No report available."),
    }
    result = email_agent(sub_state)

    _ctx.update({
        "email_status":      result.get("email_status", ""),
        "email_summary":     result.get("email_summary", ""),
        "email_agent_trace": result.get("email_agent_trace", ""),
    })

    return json.dumps({
        "email_status":  result.get("email_status", ""),
        "email_subject": result.get("email_subject", ""),
        "email_summary": result.get("email_summary", ""),
    })


# ── Orchestrator system prompt ────────────────────────────────────────────────
ORCHESTRATOR_SYSTEM = """You are a dynamic PDE claim processing orchestrator for a Medicare Part D system.

Your job is to orchestrate the FULL end-to-end processing of a PDE claim by:
1. Loading the SOP (Standard Operating Procedure) for the given error code.
2. Fetching the claim details from the database.
3. Reasoning about which specialist agents to call and in what order.
4. Calling specialist agents as tools — each one performs a specific job.

════════════════════════════════════════════
AVAILABLE SPECIALIST AGENT TOOLS:
════════════════════════════════════════════
• tool_load_sop               — Load the SOP document for an error code (ALWAYS call first)
• tool_get_claim              — Fetch claim details from the database (ALWAYS call second)
• tool_run_rx_agent           — Adjudicate the claim (ALWAYS call to get a decision)
• tool_run_report_agent       — Generate compliance report / RCL file (call if NOT REJECT)
• tool_run_servicenow_agent   — Raise incident ticket (call ONLY if decision = REPROCESS)
• tool_run_email_agent        — Send notification email (call if NOT REJECT)

════════════════════════════════════════════
DECISION LOGIC (always derived from the SOP you load):
════════════════════════════════════════════
Error 781 (Missing/Invalid Provider ID):
  • REPROCESS          → rx_agent → report_agent → servicenow_agent → email_agent
  • REJECT             → rx_agent ONLY (no report, no ServiceNow, no email)

Error 935 (Already Adjudicated):
  • REPROCESS          → rx_agent → report_agent → servicenow_agent → email_agent
  • ALREADY_PROCESSED  → rx_agent → report_agent → email_agent (NO servicenow)

════════════════════════════════════════════
MANDATORY EXECUTION ORDER:
════════════════════════════════════════════
Step 1: tool_load_sop(error_code)               ← understand the SOP rules
Step 2: tool_get_claim(claim_id)                ← understand the claim data
Step 3: tool_run_rx_agent(claim_id, error_code) ← adjudicate and get decision
Step 4: tool_run_report_agent(...)              ← build report (SKIP if REJECT)
Step 5: tool_run_servicenow_agent(...)          ← raise ticket (ONLY if REPROCESS)
Step 6: tool_run_email_agent(...)               ← send email (SKIP if REJECT)

You MUST complete ALL required steps before responding with the final JSON.
Do not stop after rx_agent — always continue to report and email unless the decision is REJECT.

After completing all required steps, respond with a final JSON summary:
{
  "next_agent": "DONE",
  "decision": "<REPROCESS|REJECT|ALREADY_PROCESSED>",
  "agents_invoked": ["RX_AGENT", "REPORT", "SERVICENOW", "EMAIL"],
  "reasoning": "brief explanation of what was done and why each agent was or was not invoked"
}
"""

# Build the dynamic orchestrator ReAct agent once at module load
_orchestrator_agent = create_agent(
    model=llm,
    tools=[
        tool_load_sop,
        tool_get_claim,
        tool_run_rx_agent,
        tool_run_report_agent,
        tool_run_servicenow_agent,
        tool_run_email_agent,
    ],
    system_prompt=ORCHESTRATOR_SYSTEM,
)


def orchestrator_agent(state: dict) -> dict:
    """
    Dynamic orchestrator entry point called by LangGraph.
    Runs the full ReAct loop — calls specialist agents as tools.
    Writes all results back into the shared LangGraph state.
    """
    global _ctx
    print("\n[Orchestrator] =============================")
    claim_id   = state.get("claim_id")
    error_code = state.get("error_code")
    print(f"[Orchestrator] Claim ID   : {claim_id}")
    print(f"[Orchestrator] Error Code : {error_code}")
    print("[Orchestrator] Mode       : DYNAMIC (full pipeline orchestration)")

    # Reset shared context for this run
    _ctx = {
        "claim_id":   claim_id,
        "error_code": error_code,
    }

    # Pre-load SOP text so sub-agents can use it immediately
    try:
        _ctx["sop_text"] = load_sop(error_code)
    except Exception:
        _ctx["sop_text"] = ""

    # ── Invoke the dynamic ReAct orchestrator ─────────────────────────────────
    user_msg = (
        f"Orchestrate the full processing of this PDE claim:\n"
        f"  claim_id   = {claim_id}\n"
        f"  error_code = {error_code}\n\n"
        f"Load the SOP for error code {error_code}, fetch the claim, then call "
        f"the appropriate specialist agent tools in the correct order based on "
        f"the SOP rules and the claim details. Complete ALL required pipeline steps."
    )

    react_result = _orchestrator_agent.invoke({"messages": [HumanMessage(content=user_msg)]})

    final_message = react_result["messages"][-1].content
    print(f"\n[Orchestrator] ReAct final output:\n{final_message}")

    # ── Capture the full ReAct trace for the UI ───────────────────────────────
    trace_lines = []
    agents_invoked_from_trace = []
    for msg in react_result["messages"]:
        role = getattr(msg, "type", type(msg).__name__)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc["name"]
                args_preview = str(tc["args"])[:150]
                trace_lines.append(f"🔧 Tool call: {name}({args_preview})")
                # Track which specialist agents were invoked
                agent_map = {
                    "tool_run_rx_agent":          "RX_AGENT",
                    "tool_run_report_agent":       "REPORT",
                    "tool_run_servicenow_agent":   "SERVICENOW",
                    "tool_run_email_agent":        "EMAIL",
                }
                if name in agent_map and agent_map[name] not in agents_invoked_from_trace:
                    agents_invoked_from_trace.append(agent_map[name])
        elif hasattr(msg, "content") and msg.content:
            trace_lines.append(f"💬 [{role}]: {str(msg.content)[:400]}")

    state["orchestrator_trace"] = "\n".join(trace_lines)

    # ── Parse the final JSON summary ──────────────────────────────────────────
    reasoning      = ""
    agents_invoked = agents_invoked_from_trace
    final_decision = _ctx.get("decision", "")

    json_match = re.search(r'\{.*?"next_agent".*?\}', final_message, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            reasoning      = parsed.get("reasoning", "")
            final_decision = parsed.get("decision", final_decision)
            if parsed.get("agents_invoked"):
                agents_invoked = parsed["agents_invoked"]
        except json.JSONDecodeError:
            pass

    # ── Merge all sub-agent results back into LangGraph state ─────────────────
    state["next_agent"]         = "DONE"
    state["reasoning"]          = reasoning
    state["agents_invoked"]     = agents_invoked
    state["sop_text"]           = _ctx.get("sop_text", "")
    state["decision"]           = final_decision or _ctx.get("decision", "")
    state["reason"]             = _ctx.get("reason", "")
    state["provider_id"]        = _ctx.get("provider_id", "")
    state["resolved_provider"]  = _ctx.get("resolved_provider")
    state["received_date"]      = _ctx.get("received_date", "")
    state["adjudication_ts"]    = _ctx.get("adjudication_ts", "")
    state["report"]             = _ctx.get("report", "")
    state["rcl_file"]           = _ctx.get("rcl_file", "")
    state["servicenow_ticket"]  = _ctx.get("servicenow_ticket", "")
    state["servicenow_summary"] = _ctx.get("servicenow_summary", "")
    state["claims_count"]       = _ctx.get("claims_count", 0)
    state["email_status"]       = _ctx.get("email_status", "")
    state["email_summary"]      = _ctx.get("email_summary", "")
    # Sub-agent traces (for per-tab display in Streamlit)
    state["rx_agent_trace"]     = _ctx.get("rx_agent_trace", "")
    state["report_agent_trace"] = _ctx.get("report_agent_trace", "")
    state["servicenow_trace"]   = _ctx.get("servicenow_trace", "")
    state["email_agent_trace"]  = _ctx.get("email_agent_trace", "")

    state.setdefault("retry_count", 0)

    print(f"[Orchestrator] ✅ Pipeline complete.")
    print(f"[Orchestrator] 📋 Agents invoked : {agents_invoked}")
    print(f"[Orchestrator] 🎯 Final decision : {state['decision']}")
    print(f"[Orchestrator] 💡 Reasoning      : {reasoning}")
    print("[Orchestrator] =============================\n")
    return state

