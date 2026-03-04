"""
LangGraph Pipeline – Dynamic Single-Orchestrator Architecture
==============================================================
The dynamic orchestrator now runs the FULL pipeline internally:
  it reads the SOP, fetches the claim, and calls specialist agents
  as tools (rx_agent, report_agent, servicenow_agent, email_agent)
  inside its own ReAct loop.

The LangGraph graph is therefore a single node:
  ORCHESTRATOR → END

This is intentional: all routing, agent invocation, and state
management is handled dynamically by the LLM-driven orchestrator.
The old static routing edges (route_after_orchestrator, route_after_rx,
route_after_report) are no longer needed.

Previous multi-node flow (for reference):
  ORCHESTRATOR → RX_AGENT → REPORT → SERVICENOW → EMAIL → END
  (routing was hardcoded by decision value)

New dynamic flow:
  ORCHESTRATOR (runs full pipeline via tools) → END
  (routing decided by LLM reading SOP per claim)
"""
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END

from agents.orchestrator import orchestrator_agent


# ── Typed state ───────────────────────────────────────────────────────────────
class ClaimState(TypedDict, total=False):
    # ── Input ──────────────────────────────────────────────────────────────
    claim_id:              str
    error_code:            str

    # ── Orchestrator outputs ────────────────────────────────────────────────
    next_agent:            str          # always "DONE" for dynamic orchestrator
    sop_text:              str
    reasoning:             str
    agents_invoked:        List[str]    # list of agents actually called this run
    retry_count:           int

    # ── RX agent outputs (781 + 935) ────────────────────────────────────────
    decision:              str          # REPROCESS | REJECT | ALREADY_PROCESSED
    reason:                str
    provider_id:           str
    resolved_provider:     Optional[dict]
    received_date:         str
    adjudication_ts:       str

    # ── Report / Email outputs ──────────────────────────────────────────────
    report:                str
    rcl_file:              str
    email_status:          str
    email_summary:         str

    # ── ServiceNow outputs ──────────────────────────────────────────────────
    servicenow_ticket:     str
    servicenow_summary:    str
    claims_count:          int

    # ── ReAct trace logs (for Streamlit UI per-agent tabs) ──────────────────
    orchestrator_trace:    str
    rx_agent_trace:        str
    report_agent_trace:    str
    email_agent_trace:     str
    servicenow_trace:      str


# ── Graph builder ─────────────────────────────────────────────────────────────
def build_graph():
    graph = StateGraph(ClaimState)

    # Single node: the dynamic orchestrator runs everything
    graph.add_node("ORCHESTRATOR", orchestrator_agent)

    graph.set_entry_point("ORCHESTRATOR")
    graph.add_edge("ORCHESTRATOR", END)

    return graph.compile()