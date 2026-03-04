"""
ServiceNow Agent – ReAct Specialist
======================================
Creates a simulated ServiceNow incident ticket when claims need reprocessing.
In production this would call the ServiceNow REST API.
"""
from dotenv import load_dotenv
load_dotenv()

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from datetime import datetime
import json

from tools.llm_tools import llm
from tools.db_tools import tool_get_reprocess_claims_summary


# ── Simulated ServiceNow ticket store ─────────────────────────────────────────
_ticket_store: list[dict] = []


@tool
def tool_create_servicenow_ticket(
    short_description: str,
    description: str,
    priority: str,
    category: str,
    affected_claims: str
) -> str:
    """
    Create a ServiceNow incident ticket for PDE claim reprocessing.
    In production this calls the ServiceNow Table API (POST /api/now/table/incident).

    Parameters:
      short_description : brief title of the incident
      description       : full details of what needs to be done
      priority          : 1-Critical, 2-High, 3-Medium, 4-Low
      category           : e.g. 'PDE Reprocessing', 'CMS Submission'
      affected_claims   : comma-separated list of claim IDs
    """
    ticket_number = f"INC{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ticket = {
        "ticket_number":     ticket_number,
        "short_description": short_description,
        "description":       description,
        "priority":          priority,
        "category":          category,
        "affected_claims":   affected_claims,
        "state":             "New",
        "created_at":        datetime.now().isoformat(),
        "assigned_to":       "PDE Operations Team",
        "assignment_group":  "Medicare Part D Processing",
    }
    _ticket_store.append(ticket)

    print(f"\n[ServiceNow] 🎫 Ticket Created: {ticket_number}")
    print(f"[ServiceNow]    Priority   : {priority}")
    print(f"[ServiceNow]    Category   : {category}")
    print(f"[ServiceNow]    Claims     : {affected_claims}")
    print(f"[ServiceNow]    Assigned To: PDE Operations Team")

    return (
        f"ServiceNow ticket created successfully.\n"
        f"  Ticket Number : {ticket_number}\n"
        f"  Short Desc    : {short_description}\n"
        f"  Priority      : {priority}\n"
        f"  Category      : {category}\n"
        f"  Assigned To   : PDE Operations Team\n"
        f"  State         : New\n"
        f"  Affected Claims: {affected_claims}"
    )


@tool
def tool_get_ticket_status(ticket_number: str) -> str:
    """
    Check the status of a previously created ServiceNow ticket by ticket number.
    """
    for t in _ticket_store:
        if t["ticket_number"] == ticket_number:
            return f"Ticket {ticket_number}: State={t['state']}, Priority={t['priority']}, Assigned To={t['assigned_to']}"
    return f"Ticket '{ticket_number}' not found."


# ── System prompt ──────────────────────────────────────────────────────────────
SERVICENOW_SYSTEM = """You are a ServiceNow integration agent for a Medicare Part D PDE claim system.

Your job is to raise an incident ticket in ServiceNow for claims that need reprocessing.

Steps:
1. Fetch the list of claims marked for reprocessing using tool_get_reprocess_claims_summary.
2. Based on the claims list, create a ServiceNow incident ticket using tool_create_servicenow_ticket:
   - short_description: "PDE Reprocessing Required – [N] claims flagged for CMS resubmission"
   - description: detailed explanation including claim IDs, error codes, and required action
   - priority: "2" (High) if more than 5 claims, "3" (Medium) otherwise
   - category: "PDE Reprocessing"
   - affected_claims: comma-separated list of claim IDs from the summary

After creating the ticket, respond with a JSON block:
{
  "ticket_number": "<the ticket number>",
  "ticket_summary": "one sentence summary of what was raised",
  "claims_count": <number of claims in ticket>
}
"""

_servicenow_agent = create_agent(
    model=llm,
    tools=[tool_get_reprocess_claims_summary, tool_create_servicenow_ticket],
    system_prompt=SERVICENOW_SYSTEM,
)


def servicenow_agent(state: dict) -> dict:
    print("\n[ServiceNow Agent] =============================")
    claim_id  = state.get("claim_id")
    decision  = state.get("decision")
    rcl_file  = state.get("rcl_file", "")

    print(f"[ServiceNow Agent] Raising ticket for claim: {claim_id} | Decision: {decision}")

    user_msg = (
        f"Raise a ServiceNow incident ticket for PDE claims requiring reprocessing.\n"
        f"  Triggered by  : claim_id={claim_id}, error_code=935\n"
        f"  Decision      : {decision}\n"
        f"  RCL File      : {rcl_file or 'not yet generated'}\n\n"
        f"Get the full list of claims marked for reprocessing and create the ticket."
    )

    react_result = _servicenow_agent.invoke({"messages": [HumanMessage(content=user_msg)]})

    final_message = react_result["messages"][-1].content
    print(f"[ServiceNow Agent] ReAct output:\n{final_message}")

    # Capture trace
    trace_lines = []
    for msg in react_result["messages"]:
        role = getattr(msg, "type", type(msg).__name__)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                trace_lines.append(f"🔧 Tool: {tc['name']}({tc['args']})")
        elif hasattr(msg, "content") and msg.content:
            trace_lines.append(f"💬 [{role}]: {str(msg.content)[:400]}")
    state["servicenow_trace"] = "\n".join(trace_lines)

    # Parse result
    import re
    ticket_number = ""
    ticket_summary = ""

    json_match = re.search(r'\{.*?"ticket_number".*?\}', final_message, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            ticket_number  = parsed.get("ticket_number", "")
            ticket_summary = parsed.get("ticket_summary", "")
            state["claims_count"] = parsed.get("claims_count", 0)
        except json.JSONDecodeError:
            pass

    state["servicenow_ticket"] = ticket_number
    state["servicenow_summary"] = ticket_summary

    print(f"[ServiceNow Agent] ✅ Ticket raised: {ticket_number}")
    print("[ServiceNow Agent] =============================\n")
    return state
