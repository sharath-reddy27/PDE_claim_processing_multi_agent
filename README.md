# 💊 PDE Claim Processing System — Dynamic Multi-Agent AI

> **Medicare Part D · LangGraph · Azure OpenAI GPT-4o · Dynamic ReAct Orchestrator · SOP-Driven Pipeline**

---

## 📌 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Agent Descriptions](#3-agent-descriptions)
4. [Decision Logic & Routing Table](#4-decision-logic--routing-table)
5. [Scenario Walkthroughs](#5-scenario-walkthroughs)
6. [Database Schema](#6-database-schema)
7. [Tools Reference](#7-tools-reference)
8. [File Structure](#8-file-structure)
9. [Setup & Running](#9-setup--running)
10. [Testing](#10-testing)

---

## 1. Project Overview

The **PDE Claim Processing System** is a fully dynamic, LLM-driven multi-agent AI pipeline that processes Medicare Part D Prescription Drug Event (PDE) claims flagged by CMS with error codes.

### What it does

- Reads the relevant **Standard Operating Procedure (SOP)** document for a given CMS error code
- Fetches the claim from a SQLite database
- Uses an LLM-powered **ReAct Orchestrator** to **decide at runtime** which specialist agents to invoke and in what order
- Calls specialist agents as **tools** — each agent handles one specific responsibility
- Collects all outputs into a unified **LangGraph state**
- Displays full results and reasoning traces in a **Streamlit dashboard**

### Supported Error Codes

| Error Code | Description | Possible Outcomes |
|---|---|---|
| **781** | Provider ID missing or invalid | `REPROCESS` or `REJECT` |
| **935** | Claim already adjudicated (duplicate) | `REPROCESS` or `ALREADY_PROCESSED` |

---

## 2. Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       LANGGRAPH PIPELINE                            │
│                                                                     │
│   INPUT                                                             │
│  (claim_id, ──►  ORCHESTRATOR NODE  ──────────────────────► END    │
│   error_code)    [Dynamic ReAct Agent]                              │
│                                                                     │
│                  Reads SOP → Fetches Claim → Calls Agents as Tools  │
└─────────────────────────────────────────────────────────────────────┘
```

The LangGraph graph is a **single-node pipeline**. All routing, agent invocation, and state management happen dynamically inside the orchestrator's ReAct loop — driven entirely by the LLM reading the SOP for each claim.

---

### Dynamic ReAct Orchestrator Flow

```
┌───────────────────────────────────────────────────────────────────────────┐
│                      DYNAMIC ORCHESTRATOR (ReAct Loop)                    │
│                                                                           │
│  Step 1: tool_load_sop(error_code)                                        │
│           └─► Reads SOP_PDE_781.txt or SOP_PDE_935.txt                   │
│                                                                           │
│  Step 2: tool_get_claim(claim_id)                                         │
│           └─► Fetches claim from rx_claims.db                             │
│                                                                           │
│  Step 3: tool_run_rx_agent(claim_id, error_code)                          │
│           └─► Adjudicates the claim → returns DECISION                   │
│                                                                           │
│  Step 4: [IF decision ≠ REJECT]                                           │
│           tool_run_report_agent(claim_id, error_code, decision)           │
│           └─► Generates RCL file (REPROCESS) or compliance report         │
│                                                                           │
│  Step 5: [IF decision = REPROCESS only]                                   │
│           tool_run_servicenow_agent(claim_id, error_code, rcl_file)       │
│           └─► Raises ServiceNow incident ticket                           │
│                                                                           │
│  Step 6: [IF decision ≠ REJECT]                                           │
│           tool_run_email_agent(claim_id, error_code, decision)            │
│           └─► Sends notification email to compliance team                 │
│                                                                           │
│  Final:  Writes all outputs back into LangGraph ClaimState                │
└───────────────────────────────────────────────────────────────────────────┘
```

---

### Multi-Agent Component Diagram

```
                         ┌─────────────────────────────────┐
                         │       STREAMLIT UI (app.py)      │
                         │   Dashboard · Process · Reports  │
                         └────────────────┬────────────────┘
                                          │ invoke
                                          ▼
                    ┌─────────────────────────────────────────┐
                    │         LANGGRAPH (graph.py)            │
                    │   StateGraph: ORCHESTRATOR ──► END      │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
          ┌──────────────────────────────────────────────────────────┐
          │          DYNAMIC ORCHESTRATOR (orchestrator.py)          │
          │  AzureChatOpenAI · create_agent() · ReAct Loop           │
          │                                                          │
          │  Shared context bag: _ctx (per-run dict)                 │
          │                                                          │
          │  Tool wrappers:                                          │
          │   tool_run_rx_agent  ──────────────► RX_CLAIM_AGENT      │
          │   tool_run_report_agent ──────────► REPORT_BUILDER_AGENT │
          │   tool_run_servicenow_agent ──────► SERVICENOW_AGENT     │
          │   tool_run_email_agent ───────────► EMAIL_AGENT          │
          └──────────────────────────────────────────────────────────┘
                    │              │             │            │
                    ▼              ▼             ▼            ▼
          ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────┐
          │  RX Claim    │ │    Report    │ │ServiceNow│ │  Email   │
          │   Agent      │ │   Builder   │ │  Agent   │ │  Agent   │
          │(rx_claim_    │ │   Agent     │ │(servicen │ │(email_   │
          │  agent.py)   │ │(report_     │ │ ow_agent │ │ agent.py)│
          │              │ │ builder_    │ │  .py)    │ │          │
          │ 781: provider│ │  agent.py)  │ │Ticket    │ │Compose + │
          │ 935: dates   │ │ RCL / report│ │creation  │ │  Send    │
          └──────┬───────┘ └──────┬──────┘ └────┬─────┘ └────┬─────┘
                 │                │              │            │
                 ▼                ▼              ▼            ▼
          ┌──────────────────────────────────────────────────────────┐
          │                    TOOLS LAYER                           │
          │  tools/db_tools.py   tools/sop_tools.py                 │
          │  tools/llm_tools.py                                      │
          └──────────────────────────────────────────────────────────┘
                 │                │
                 ▼                ▼
          ┌────────────┐   ┌────────────┐
          │rx_claims.db│   │ reports.db │
          │  (SQLite)  │   │  (SQLite)  │
          └────────────┘   └────────────┘
```

---

## 3. Agent Descriptions

### 🧠 Dynamic Orchestrator (`agents/orchestrator.py`)

The central coordinator. It is a **LangChain ReAct agent** powered by Azure OpenAI GPT-4o.

**Responsibilities:**
- Load the SOP for the given error code
- Fetch the claim from the database
- Dynamically decide which specialist agents to invoke (and in what order) by reading the SOP rules
- Call each required specialist agent as a LangChain tool
- Collect all outputs into the shared `_ctx` context bag
- Write the final merged state back to LangGraph

**Key design decisions:**
- The orchestrator uses a **module-level `_ctx` dict** that is reset at the start of each run. Tool wrappers read from and write to this dict, so agents can share results without touching LangGraph state directly.
- Routing is **entirely LLM-driven** — the orchestrator reads the SOP and decides the pipeline at runtime, rather than via hardcoded routing edges.

---

### 💊 RX Claim Agent (`agents/rx_claim_agent.py`)

The adjudication specialist. Handles **both** error code types.

**Error 781 — Missing/Invalid Provider ID:**
1. Fetch the claim (`tool_get_claim`)
2. Look up the CMS-validated provider ID in the mapping table (`tool_get_provider_mapping`)
3. If found → update claim provider ID and status to `READY_FOR_REPROCESS` → **REPROCESS**
4. If not found → update claim status to `REJECTED` → **REJECT**

**Error 935 — Already Adjudicated:**
1. Fetch the claim (`tool_get_claim`)
2. Compare `received_date` vs `adjudication_ts` (`tool_compare_claim_dates`)
3. If dates are equal → update status to `READY_FOR_REPROCESS` → **REPROCESS**
4. If `adjudication_ts` is more recent → update status to `ALREADY_PROCESSED` → **ALREADY_PROCESSED**

---

### 📋 Report Builder Agent (`agents/report_builder_agent.py`)

The compliance reporting specialist. **Skipped for REJECT decisions.**

**REPROCESS path (Error 781 or 935):**
1. Fetch claim details
2. Get summary of all `READY_FOR_REPROCESS` claims
3. Generate an RCL (Reprocess Claims List) CSV file in `output/`
4. Save report to `reports.db`

**ALREADY_PROCESSED path (Error 935):**
1. Fetch claim details
2. Save a compliance report to `reports.db`
3. Notes: claim excluded from reprocessing, included in PDE compliance report

---

### 🎫 ServiceNow Agent (`agents/servicenow_agent.py`)

The incident management specialist. **Only invoked when decision = REPROCESS.**

**Steps:**
1. Get summary of all claims marked for reprocessing
2. Create a simulated ServiceNow incident ticket with:
   - Priority: High (>5 claims) or Medium (≤5 claims)
   - Category: `PDE Reprocessing`
   - Assigned To: `PDE Operations Team`
   - Affected claims list from the summary

> In production, this would call the ServiceNow Table API (`POST /api/now/table/incident`).

---

### 📧 Email Agent (`agents/email_agent.py`)

The notification specialist. **Skipped for REJECT decisions.**

**Steps:**
1. Fetch the claim to confirm final status
2. Compose a professional notification email (To: `compliance-team@healthplan.com`)
3. Simulate sending via `tool_send_email`

> In production, this would connect to SMTP / SendGrid / Azure Communication Services.

---

## 4. Decision Logic & Routing Table

### Agent Invocation Matrix

| Error Code | Decision | RX Agent | Report | ServiceNow | Email |
|---|---|:---:|:---:|:---:|:---:|
| 781 | REPROCESS | ✅ | ✅ | ✅ | ✅ |
| 781 | REJECT | ✅ | ❌ | ❌ | ❌ |
| 935 | REPROCESS | ✅ | ✅ | ✅ | ✅ |
| 935 | ALREADY_PROCESSED | ✅ | ✅ | ❌ | ✅ |

### Decision Tree

```
Claim Received
      │
      ├─► Error Code 781 (Provider ID)
      │         │
      │         └─► RX Agent: Look up provider mapping
      │                   │
      │                   ├─► Mapping FOUND  ──► REPROCESS
      │                   │   → Update provider ID
      │                   │   → RX → Report → ServiceNow → Email
      │                   │
      │                   └─► Mapping NOT FOUND ──► REJECT
      │                       → Update status REJECTED
      │                       → RX only — no report/email
      │
      └─► Error Code 935 (Already Adjudicated)
                │
                └─► RX Agent: Compare dates
                          │
                          ├─► received_date == adjudication_ts
                          │   → REPROCESS (potential duplicate submission)
                          │   → RX → Report → ServiceNow → Email
                          │
                          └─► adjudication_ts > received_date
                              → ALREADY_PROCESSED
                              → RX → Report → Email (no ServiceNow)
```

---

## 5. Scenario Walkthroughs

### Scenario 1 — Error 781, Missing Provider → REPROCESS

- **Claim:** `C0009`, error code `781`, `provider_id = ''` (blank)
- **Orchestrator reads SOP 781:** Must validate provider ID, resolve from CMS mapping
- **RX Agent:**
  - `tool_get_claim("C0009")` → provider_id is blank
  - `tool_get_provider_mapping("")` → finds mapping for blank → returns `P002`
  - `tool_update_claim_provider_id("C0009", "P002")` → updates DB
  - `tool_update_claim_status("C0009", "READY_FOR_REPROCESS")` → updates DB
  - **Decision: REPROCESS**
- **Report Agent:** Generates RCL CSV file, saves report to `reports.db`
- **ServiceNow Agent:** Creates incident ticket `INC<timestamp>`, priority Medium/High
- **Email Agent:** Sends notification to `compliance-team@healthplan.com`
- **Agents invoked:** `RX_AGENT → REPORT → SERVICENOW → EMAIL`

---

### Scenario 2 — Error 935, Equal Dates → REPROCESS

- **Claim:** `C0010`, error code `935`, `received_date = 2025-01-02`, `adjudication_ts = 2025-01-02`
- **Orchestrator reads SOP 935:** Compare dates to determine if claim is duplicate
- **RX Agent:**
  - `tool_get_claim("C0010")` → both dates are equal
  - `tool_compare_claim_dates("C0010")` → returns `EQUAL → REPROCESS`
  - `tool_update_claim_status("C0010", "READY_FOR_REPROCESS")` → updates DB
  - **Decision: REPROCESS**
- **Report Agent:** Generates RCL CSV file
- **ServiceNow Agent:** Creates reprocessing ticket
- **Email Agent:** Sends notification
- **Agents invoked:** `RX_AGENT → REPORT → SERVICENOW → EMAIL`

---

### Scenario 3 — Error 935, Adjudication Newer → ALREADY_PROCESSED

- **Claim:** `C0006`, error code `935`, `received_date = 2024-12-15`, `adjudication_ts = 2025-01-02`
- **Orchestrator reads SOP 935:** Compare dates
- **RX Agent:**
  - `tool_compare_claim_dates("C0006")` → returns `ADJUDICATION_MORE_RECENT → ALREADY_PROCESSED`
  - `tool_update_claim_status("C0006", "ALREADY_PROCESSED")` → updates DB
  - **Decision: ALREADY_PROCESSED**
- **Report Agent:** Saves compliance report (no RCL file generated)
- **ServiceNow Agent:** ⏭️ **SKIPPED** — SOP says not to reprocess, no incident needed
- **Email Agent:** Sends compliance notification
- **Agents invoked:** `RX_AGENT → REPORT → EMAIL`

---

### Scenario 4 — Error 781, No Provider Mapping → REJECT

- **Claim:** `TEST-REJECT-001`, error code `781`, `provider_id = P999` (invalid, no mapping)
- **Orchestrator reads SOP 781:** Must validate provider ID
- **RX Agent:**
  - `tool_get_claim("TEST-REJECT-001")` → provider_id = P999
  - `tool_get_provider_mapping("P999")` → **no mapping found**
  - `tool_update_claim_status("TEST-REJECT-001", "REJECTED")` → updates DB
  - **Decision: REJECT**
- **Report Agent:** ⏭️ **SKIPPED** — no report needed for rejected claims
- **ServiceNow Agent:** ⏭️ **SKIPPED** — no ticket for rejected claims
- **Email Agent:** ⏭️ **SKIPPED** — no notification for rejected claims
- **Agents invoked:** `RX_AGENT` only

---

## 6. Database Schema

### `db/rx_claims.db`

#### Table: `claims`

| Column | Type | Description |
|---|---|---|
| `claim_id` | TEXT (PK) | Unique claim identifier (e.g. `C0001`, `TEST-REJECT-001`) |
| `error_code` | TEXT | CMS error code: `781` or `935` |
| `provider_id` | TEXT | Provider NPI / ID (may be blank for 781 errors) |
| `adjudication_ts` | TEXT | Date claim was adjudicated (YYYY-MM-DD) |
| `received_date` | TEXT | Date claim was received (YYYY-MM-DD) |
| `status` | TEXT | Processing status (see below) |

**Valid status values:**

| Status | Meaning |
|---|---|
| `NEW` | Claim received, not yet processed |
| `PENDING` | Processing in progress |
| `READY_FOR_REPROCESS` | Resolved, queued for CMS resubmission |
| `ALREADY_PROCESSED` | Claim was already adjudicated, excluded from reprocessing |
| `REJECTED` | Claim could not be resolved, rejected |

#### Table: `provider_mapping`

| Column | Type | Description |
|---|---|---|
| `old_provider_id` | TEXT | Invalid / missing / old provider ID (empty string = missing) |
| `new_provider_id` | TEXT | Correct CMS-validated provider ID |
| `provider_name` | TEXT | Provider organization name |
| `npi` | TEXT | National Provider Identifier |

---

### `db/reports.db`

#### Table: `reports`

| Column | Type | Description |
|---|---|---|
| `claim_id` | TEXT | Reference to the processed claim |
| `error_code` | TEXT | `781` or `935` |
| `provider_id` | TEXT | Provider ID at time of processing |
| `decision` | TEXT | `REPROCESS`, `REJECT`, or `ALREADY_PROCESSED` |
| `reason` | TEXT | Detailed explanation of the decision |
| `created_ts` | TEXT | ISO timestamp of report creation |

---

## 7. Tools Reference

### `tools/db_tools.py`

| Tool | Description |
|---|---|
| `tool_get_claim(claim_id)` | Fetch full claim record from `rx_claims.db` |
| `tool_get_provider_mapping(old_provider_id)` | Look up CMS-validated provider from mapping table |
| `tool_update_claim_provider_id(claim_id, new_provider_id)` | Update provider ID on a claim record |
| `tool_update_claim_status(claim_id, status)` | Update processing status of a claim |
| `tool_compare_claim_dates(claim_id)` | Compare `received_date` vs `adjudication_ts` for 935 claims |
| `tool_insert_report(claim_id, ...)` | Save a processed report to `reports.db` |
| `tool_generate_rcl_file()` | Generate RCL CSV file from all `READY_FOR_REPROCESS` claims |
| `tool_get_reprocess_claims_summary()` | List all claims currently marked `READY_FOR_REPROCESS` |

### `tools/sop_tools.py`

| Tool | Description |
|---|---|
| `tool_load_sop(error_code)` | Load the SOP text file for a given error code (781 or 935) |

### `tools/llm_tools.py`

| Export | Description |
|---|---|
| `llm` | Shared `AzureChatOpenAI` instance used by all ReAct agents |
| `call_llm(prompt)` | One-shot LLM call helper |

---

## 8. File Structure

```
Multi Agentic POC/
│
├── app.py                          # Streamlit dashboard (UI)
├── graph.py                        # LangGraph pipeline definition (ClaimState + build_graph)
├── run.py                          # CLI runner (non-Streamlit)
│
├── agents/
│   ├── orchestrator.py             # ★ Dynamic ReAct orchestrator (main coordinator)
│   ├── rx_claim_agent.py           # ★ Adjudication specialist (781 + 935)
│   ├── report_builder_agent.py     # ★ Report / RCL file generator
│   ├── servicenow_agent.py         # ★ ServiceNow ticket creator
│   ├── email_agent.py              # ★ Email notification sender
│   ├── pde_file_reader.py          # PDE flat file reader (ingest utility)
│   └── sop_reader.py               # SOP file reader utility
│
├── tools/
│   ├── db_tools.py                 # ★ All database tools (LangChain @tool)
│   ├── sop_tools.py                # ★ SOP loading tool
│   └── llm_tools.py                # ★ Shared LLM instance (AzureChatOpenAI)
│
├── sop/
│   ├── SOP_PDE_781.txt             # Standard Operating Procedure for Error 781
│   └── SOP_PDE_935.txt             # Standard Operating Procedure for Error 935
│
├── db/
│   ├── rx_claims.db                # Claims database (SQLite)
│   └── reports.db                  # Reports database (SQLite)
│
├── output/
│   └── RCL_*.csv                   # Generated Reprocess Claims List files
│
├── data/
│   └── PDE_flat_file.txt           # Sample PDE flat file for ingestion
│
├── orchestrator_test.py            # ★ End-to-end test (all 4 scenarios)
├── init_rx_claims_db.py            # DB initialization script (claims + provider mapping)
├── init_reports_db.py              # DB initialization script (reports)
├── insert_test_claim.py            # Insert test claim utility
├── _seed_reject_claim.py           # Seed REJECT test claim (TEST-REJECT-001)
├── check_claims.py                 # DB inspection utility
├── _check_mapping.py               # Provider mapping inspection utility
├── ingest_pde.py                   # PDE flat file ingestion
├── view_db.py                      # View database contents
├── migrate_db.py                   # Database migration helper
├── load_env.py                     # .env loader
├── patch_app.py                    # App patching utility
├── demo_run.py                     # Demo run script
├── test_llm.py                     # LLM connectivity test
├── test_rx_claim_agent.py          # Unit test for RX agent
├── test_report_builder_agent.py    # Unit test for Report Builder agent
├── test.ipynb                      # Jupyter notebook for exploratory testing
│
├── requirements.txt                # Python dependencies
├── README.md                       # ← This file
└── PROJECT_DOCUMENTATION.html      # Comprehensive HTML documentation with diagrams
```

---

## 9. Setup & Running

### Prerequisites

- Python 3.10+
- Azure OpenAI resource with GPT-4o deployment
- A `.env` file in the project root

### `.env` File

Create a `.env` file in the project root with your Azure OpenAI credentials:

```env
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Initialize Databases (first time only)

```bash
python init_rx_claims_db.py
python init_reports_db.py
```

### Seed the REJECT Test Claim (optional, for testing scenario 4)

```bash
python _seed_reject_claim.py
```

### Run the Streamlit Dashboard

```bash
streamlit run app.py
```

The dashboard will open at `http://localhost:8501` with three pages:
- **🏠 Dashboard** — Metrics overview, recent reports, workflow diagram
- **🔍 Process Claim** — Select a claim and run the agent pipeline
- **📊 Reports** — Browse all generated compliance reports
- **🗄️ Database** — Explore claims, provider mapping, and reports tables

### Run a Claim Programmatically (CLI)

```python
from graph import build_graph

app = build_graph()
result = app.invoke({
    "claim_id":   "C0009",
    "error_code": "781",
})

print(result["decision"])        # REPROCESS
print(result["agents_invoked"])  # ['RX_AGENT', 'REPORT', 'SERVICENOW', 'EMAIL']
print(result["report"])          # compliance report text
print(result["rcl_file"])        # path to generated RCL CSV
```

---

## 10. Testing

### End-to-End Test (`orchestrator_test.py`)

Runs all 4 scenarios against the live database and LLM:

```bash
python orchestrator_test.py
```

**Test cases:**

| # | Claim | Error | Expected Decision | Expected Agents |
|---|---|---|---|---|
| 1 | `C0009` | 781 | `REPROCESS` | RX → Report → ServiceNow → Email |
| 2 | `C0010` | 935 | `REPROCESS` | RX → Report → ServiceNow → Email |
| 3 | `C0006` | 935 | `ALREADY_PROCESSED` | RX → Report → Email |
| 4 | `TEST-REJECT-001` | 781 | `REJECT` | RX only |

Each test case validates:
- ✅ Correct decision returned
- ✅ All expected agents were invoked
- ✅ No excluded agents were invoked (e.g., ServiceNow not called for ALREADY_PROCESSED)

### Individual Agent Tests

```bash
python test_rx_claim_agent.py
python test_report_builder_agent.py
python test_llm.py
```

---

## Key Design Principles

| Principle | Implementation |
|---|---|
| **SOP-Driven** | Orchestrator reads the SOP before making any decision |
| **LLM-Driven Routing** | No hardcoded `if/else` routing — the LLM decides which agents to call |
| **ReAct Pattern** | All agents use LangChain's `create_agent()` with Reasoning + Acting loop |
| **Tool Isolation** | Each specialist agent only receives the tools it needs |
| **Shared Context** | `_ctx` dict allows tool wrappers to pass results between agents |
| **Traceable** | Every agent logs its ReAct trace, visible in the Streamlit UI |
| **Idempotent** | Each run resets `_ctx` and re-evaluates from the SOP |
| **Single Node Graph** | LangGraph has 1 node (ORCHESTRATOR → END); routing is internal to the LLM |

---

*Built with LangChain · LangGraph · Azure OpenAI GPT-4o · Streamlit · SQLite*
