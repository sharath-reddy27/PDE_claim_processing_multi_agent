import sqlite3
import os
import csv
from datetime import datetime
from langchain_core.tools import tool

RX_DB_PATH = "db/rx_claims.db"
REPORTS_DB_PATH = "db/reports.db"
RCL_OUTPUT_DIR = "output"


# ── Raw DB helpers (used internally and by other modules) ─────────────────────

def get_claim(claim_id: str) -> dict | None:
    """Fetch a claim by claim_id from rx_claims.db"""
    conn = sqlite3.connect(RX_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT claim_id, error_code, provider_id, adjudication_ts, status, received_date
        FROM claims
        WHERE claim_id = ?
    """, (claim_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        print(f"[DB] ⚠️ Claim {claim_id} not found in DB.")
        return None

    claim = {
        "claim_id":       row[0],
        "error_code":     row[1],
        "provider_id":    row[2],
        "adjudication_ts":row[3],
        "status":         row[4],
        "received_date":  row[5],
    }
    print(f"[DB] Fetched claim: {claim}")
    return claim


def update_claim_status(claim_id: str, status: str):
    """Update the status of a claim in rx_claims.db"""
    conn = sqlite3.connect(RX_DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id))
    conn.commit()
    conn.close()
    print(f"[DB] Claim {claim_id} → status updated to: {status}")


def update_claim_provider_id(claim_id: str, new_provider_id: str):
    """Update the provider_id of a claim after resolving from mapping table."""
    conn = sqlite3.connect(RX_DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE claims SET provider_id = ? WHERE claim_id = ?", (new_provider_id, claim_id))
    conn.commit()
    conn.close()
    print(f"[DB] Claim {claim_id} → provider_id updated to: {new_provider_id}")


def get_provider_mapping(old_provider_id: str) -> dict | None:
    """
    Look up the new provider ID for a given old/invalid provider ID.
    If old_provider_id is None or empty string, resolves to the default active provider.
    """
    if isinstance(old_provider_id, tuple):
        old_provider_id = old_provider_id[0]
    if not old_provider_id:
        old_provider_id = ""

    conn = sqlite3.connect(RX_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT new_provider_id, provider_name, npi
        FROM provider_mapping
        WHERE old_provider_id = ?
    """, (old_provider_id,))
    row = cur.fetchone()
    conn.close()

    if row:
        return {
            "new_provider_id": row[0],
            "provider_name": row[1],
            "npi": row[2]
        }
    return None


def insert_report(claim_id: str, error_code: str, provider_id: str, decision: str, reason: str):
    """Insert a report record into reports.db"""
    conn = sqlite3.connect(REPORTS_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reports (claim_id, error_code, provider_id, decision, reason, created_ts)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (claim_id, error_code, provider_id, decision, reason, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print(f"[DB] Report inserted for claim {claim_id} | Decision: {decision}")


def get_claims_for_rcl() -> list:
    """Fetch all claims marked READY_FOR_REPROCESS for RCL file generation."""
    conn = sqlite3.connect(RX_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT claim_id, error_code, provider_id, adjudication_ts, received_date, status
        FROM claims WHERE status = 'READY_FOR_REPROCESS'
    """)
    rows = cur.fetchall()
    conn.close()
    return [
        {"claim_id": r[0], "error_code": r[1], "provider_id": r[2],
         "adjudication_ts": r[3], "received_date": r[4], "status": r[5]}
        for r in rows
    ]


def generate_rcl_file() -> str:
    """Generate an RCL (Reprocess Claims List) CSV file from all READY_FOR_REPROCESS claims."""
    os.makedirs(RCL_OUTPUT_DIR, exist_ok=True)
    claims = get_claims_for_rcl()
    if not claims:
        return ""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(RCL_OUTPUT_DIR, f"RCL_{ts}.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["claim_id","error_code","provider_id","adjudication_ts","received_date","status"])
        writer.writeheader()
        writer.writerows(claims)
    print(f"[DB] RCL file generated: {filepath} ({len(claims)} claims)")
    return filepath


# ── LangChain @tool versions (used by ReAct agents) ──────────────────────────

@tool
def tool_get_claim(claim_id: str) -> str:
    """
    Fetch a PDE claim from the database by claim_id.
    Returns claim details including error_code, provider_id, adjudication_ts, received_date and status.
    Use this to retrieve full claim information before making adjudication decisions.
    """
    claim = get_claim(claim_id)
    if not claim:
        return f"ERROR: Claim '{claim_id}' not found in the database."
    return (
        f"Claim found:\n"
        f"  claim_id       = {claim['claim_id']}\n"
        f"  error_code     = {claim['error_code']}\n"
        f"  provider_id    = {claim['provider_id'] or 'MISSING'}\n"
        f"  adjudication_ts= {claim['adjudication_ts']}\n"
        f"  received_date  = {claim['received_date']}\n"
        f"  status         = {claim['status']}"
    )


@tool
def tool_get_provider_mapping(old_provider_id: str) -> str:
    """
    Look up the CMS-validated provider ID for an old, missing, or invalid provider ID.
    Pass empty string '' if provider_id is missing.
    Returns the new provider ID, provider name, and NPI number if a mapping exists.
    """
    mapping = get_provider_mapping(old_provider_id)
    if not mapping:
        return f"No provider mapping found for provider_id='{old_provider_id}'."
    return (
        f"Provider mapping found:\n"
        f"  new_provider_id = {mapping['new_provider_id']}\n"
        f"  provider_name   = {mapping['provider_name']}\n"
        f"  npi             = {mapping['npi']}"
    )


@tool
def tool_update_claim_provider_id(claim_id: str, new_provider_id: str) -> str:
    """
    Update the provider_id on a claim record in the database.
    Use after resolving a missing or invalid provider ID via the provider mapping table.
    """
    update_claim_provider_id(claim_id, new_provider_id)
    return f"Successfully updated claim '{claim_id}' provider_id to '{new_provider_id}'."


@tool
def tool_update_claim_status(claim_id: str, status: str) -> str:
    """
    Update the processing status of a PDE claim in the database.
    Valid statuses: PENDING, READY_FOR_REPROCESS, REJECTED, ALREADY_PROCESSED.
    """
    update_claim_status(claim_id, status)
    return f"Successfully updated claim '{claim_id}' status to '{status}'."


@tool
def tool_insert_report(claim_id: str, error_code: str, provider_id: str, decision: str, reason: str) -> str:
    """
    Save a processed claim report to the reports database.
    - decision: one of REPROCESS, REJECT, ALREADY_PROCESSED
    - reason: detailed explanation of the decision
    """
    insert_report(claim_id, error_code, provider_id, decision, reason)
    return f"Report saved for claim '{claim_id}' with decision '{decision}'."


@tool
def tool_compare_claim_dates(claim_id: str) -> str:
    """
    Compare the received_date vs adjudication_ts for a 935 error code claim.
    Returns the comparison result and recommended action:
      - If dates are EQUAL → claim needs REPROCESS
      - If adjudication_ts is MORE RECENT than received_date → claim is ALREADY_PROCESSED
    """
    claim = get_claim(claim_id)
    if not claim:
        return f"ERROR: Claim '{claim_id}' not found."

    received    = str(claim.get("received_date") or "").strip()[:10]
    adjudicated = str(claim.get("adjudication_ts") or "").strip()[:10]

    if not received or not adjudicated:
        return (
            f"Claim '{claim_id}': Cannot compare dates.\n"
            f"  received_date   = '{received or 'MISSING'}'\n"
            f"  adjudication_ts = '{adjudicated or 'MISSING'}'"
        )

    if received == adjudicated:
        result = "EQUAL → Claim received and adjudicated on the same date. Action: REPROCESS"
        action = "REPROCESS"
    elif adjudicated > received:
        result = "ADJUDICATION_MORE_RECENT → Claim was adjudicated after it was received. Action: ALREADY_PROCESSED"
        action = "ALREADY_PROCESSED"
    else:
        result = "RECEIVED_AFTER_ADJUDICATION → Unusual case. Action: REPROCESS for review"
        action = "REPROCESS"

    return (
        f"Date comparison for claim '{claim_id}':\n"
        f"  received_date   = {received}\n"
        f"  adjudication_ts = {adjudicated}\n"
        f"  result          = {result}\n"
        f"  recommended     = {action}"
    )


@tool
def tool_generate_rcl_file() -> str:
    """
    Generate an RCL (Reprocess Claims List) CSV file containing all claims
    marked as READY_FOR_REPROCESS in the database.
    This file is used by the PDE team for CMS resubmission.
    Returns the file path of the generated RCL file.
    """
    filepath = generate_rcl_file()
    if not filepath:
        return "No claims found with status READY_FOR_REPROCESS. RCL file not generated."
    claims = get_claims_for_rcl()
    return (
        f"RCL file generated successfully.\n"
        f"  File path  : {filepath}\n"
        f"  Total claims: {len(claims)}\n"
        f"  Status     : Ready for PDE team / CMS resubmission"
    )


@tool
def tool_get_reprocess_claims_summary() -> str:
    """
    Get a summary of all claims currently marked as READY_FOR_REPROCESS.
    Use this to check how many claims need reprocessing before generating the RCL file.
    """
    claims = get_claims_for_rcl()
    if not claims:
        return "No claims currently marked as READY_FOR_REPROCESS."
    lines = [f"  {c['claim_id']} | Error {c['error_code']} | Provider {c['provider_id']}" for c in claims]
    return f"Claims marked READY_FOR_REPROCESS ({len(claims)} total):\n" + "\n".join(lines)


