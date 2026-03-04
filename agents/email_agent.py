"""
Email Agent – ReAct Specialist
================================
A LangGraph ReAct agent that composes and (simulates) sending
a professional notification email for the processed claim.
"""
from dotenv import load_dotenv
load_dotenv()

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from tools.llm_tools import llm
from tools.db_tools import tool_get_claim

# ── Simulated email send tool ─────────────────────────────────────────────────
@tool
def tool_send_email(to: str, subject: str, body: str) -> str:
    """
    Simulate sending an email notification.
    In production this would connect to SMTP / SendGrid / Azure Communication Services.
    Returns confirmation that the email was sent.
    """
    print(f"\n[Email Agent] 📧 Sending email to: {to}")
    print(f"[Email Agent]    Subject: {subject}")
    print(f"[Email Agent]    Body:\n{body}")
    return f"Email sent successfully to '{to}' with subject '{subject}'."


# ── System prompt ──────────────────────────────────────────────────────────────
EMAIL_SYSTEM = """You are a PDE claim notification agent for a Medicare Part D system.

Your job is to compose and send a professional email notification after a claim is processed.

Steps:
1. Fetch the claim record using tool_get_claim to confirm final status.
2. Compose a concise, professional email:
   - To: compliance-team@healthplan.com
   - Subject: should include the claim ID and decision
   - Body: 3-5 sentence summary of the claim outcome with key details
3. Send the email using tool_send_email.

After sending, respond with a JSON block:
{
  "email_status": "SENT",
  "email_subject": "the subject line you used",
  "email_summary": "one sentence summary of what was communicated"
}
"""

_email_agent = create_agent(
    model=llm,
    tools=[tool_get_claim, tool_send_email],
    system_prompt=EMAIL_SYSTEM,
)


def email_agent(state: dict) -> dict:
    print("\n[Email Agent] =============================")
    claim_id  = state.get("claim_id")
    error_code = state.get("error_code")
    decision  = state.get("decision", "UNKNOWN")
    report    = state.get("report", "No report available.")

    if not report or report == "No report available.":
        print("[Email Agent] ⚠️ No report found. Skipping email.")
        state["email_status"] = "SKIPPED"
        return state

    print(f"[Email Agent] Claim: {claim_id} | Decision: {decision}")

    user_msg = (
        f"Send a notification email for the following processed PDE claim.\n"
        f"  claim_id   = {claim_id}\n"
        f"  error_code = {error_code}\n"
        f"  decision   = {decision}\n"
        f"  report     = {report[:400]}\n\n"
        f"Fetch the claim to confirm status, compose the email, and send it."
    )

    react_result = _email_agent.invoke({"messages": [HumanMessage(content=user_msg)]})

    final_message = react_result["messages"][-1].content
    print(f"[Email Agent] ReAct final output:\n{final_message}")

    # Capture trace
    trace_lines = []
    for msg in react_result["messages"]:
        role = getattr(msg, "type", type(msg).__name__)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                trace_lines.append(f"🔧 Tool: {tc['name']}({tc['args']})")
        elif hasattr(msg, "content") and msg.content:
            trace_lines.append(f"💬 [{role}]: {str(msg.content)[:400]}")
    state["email_agent_trace"] = "\n".join(trace_lines)

    # ── Parse result ──────────────────────────────────────────────────────────
    import json, re
    email_subject = ""

    json_match = re.search(r'\{.*?"email_status".*?\}', final_message, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            state["email_status"] = parsed.get("email_status", "SENT")
            email_subject = parsed.get("email_subject", "")
            state["email_summary"] = parsed.get("email_summary", "")
        except json.JSONDecodeError:
            state["email_status"] = "SENT"
    else:
        state["email_status"] = "SENT"

    print(f"[Email Agent] ✅ Email sent | Subject: {email_subject}")
    print("[Email Agent] =============================\n")
    return state
