import streamlit as st
import sqlite3
import pandas as pd
import sys
import io
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PDE Claim Processing System",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ───────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0f1117; }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, #1a1f35 0%, #0d3b66 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border: 1px solid #1e3a5f;
        box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    }
    .main-header h1 { color: #e0f0ff; font-size: 2rem; margin: 0; }
    .main-header p  { color: #7fb3d3; margin: 0.3rem 0 0 0; font-size: 0.95rem; }

    /* Cards */
    .metric-card {
        background: linear-gradient(135deg, #1a1f35, #16213e);
        border: 1px solid #2a3f5f;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        text-align: center;
        box-shadow: 0 2px 12px rgba(0,0,0,0.3);
    }
    .metric-card .value { font-size: 2rem; font-weight: 700; color: #4fc3f7; }
    .metric-card .label { font-size: 0.8rem; color: #7fb3d3; margin-top: 0.3rem; }

    /* Agent step boxes */
    .agent-step {
        border-radius: 10px;
        padding: 1rem 1.4rem;
        margin: 0.5rem 0;
        border-left: 4px solid;
        font-size: 0.9rem;
    }
    .agent-orchestrator { background: #1a2744; border-color: #4fc3f7; color: #b3d9f7; }
    .agent-rx           { background: #1a2d1a; border-color: #66bb6a; color: #b7dfb7; }
    .agent-935          { background: #2d1a10; border-color: #ffa726; color: #ffd580; }
    .agent-servicenow   { background: #1a1a2d; border-color: #7c4dff; color: #d0b3ff; }
    .agent-report       { background: #2d1a2d; border-color: #ab47bc; color: #dbb3db; }
    .agent-email        { background: #2d2200; border-color: #ffa726; color: #ffd580; }

    /* Decision badges */
    .badge-reprocess    { background: #1a3a1a; color: #66bb6a; padding: 0.3rem 0.9rem; border-radius: 20px; font-weight: 600; font-size: 0.85rem; border: 1px solid #66bb6a; }
    .badge-reject       { background: #3a1a1a; color: #ef5350; padding: 0.3rem 0.9rem; border-radius: 20px; font-weight: 600; font-size: 0.85rem; border: 1px solid #ef5350; }
    .badge-processed    { background: #1a2744; color: #4fc3f7; padding: 0.3rem 0.9rem; border-radius: 20px; font-weight: 600; font-size: 0.85rem; border: 1px solid #4fc3f7; }
    .badge-sent         { background: #2d2200; color: #ffa726; padding: 0.3rem 0.9rem; border-radius: 20px; font-weight: 600; font-size: 0.85rem; border: 1px solid #ffa726; }

    /* Section titles */
    .section-title {
        color: #4fc3f7;
        font-size: 1.05rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid #1e3a5f;
    }

    /* Log box */
    .log-box {
        background: #0d1117;
        border: 1px solid #1e3a5f;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        font-family: 'Courier New', monospace;
        font-size: 0.8rem;
        color: #7fb3d3;
        max-height: 320px;
        overflow-y: auto;
        white-space: pre-wrap;
    }

    /* Sidebar */
    .css-1d391kg, [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1b2a 0%, #0a1628 100%);
    }
    [data-testid="stSidebar"] .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #0d3b66, #1565c0);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem;
        font-weight: 600;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: linear-gradient(135deg, #1565c0, #0d3b66);
        box-shadow: 0 0 12px rgba(79,195,247,0.3);
    }

    /* Run button */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #0d3b66, #1565c0) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.7rem 2rem !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        width: 100% !important;
        box-shadow: 0 4px 15px rgba(79,195,247,0.25);
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        box-shadow: 0 4px 20px rgba(79,195,247,0.5) !important;
    }

    /* Dataframe */
    .stDataFrame { border-radius: 10px; overflow: hidden; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { background: #1a1f35; border-radius: 10px; padding: 4px; }
    .stTabs [data-baseweb="tab"] { color: #7fb3d3; }
    .stTabs [aria-selected="true"] { background: #0d3b66 !important; color: #e0f0ff !important; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── DB helpers ────────────────────────────────────────────────────────────────
RX_DB      = "db/rx_claims.db"
REPORTS_DB = "db/reports.db"

def fetch_all_claims():
    conn = sqlite3.connect(RX_DB)
    df = pd.read_sql_query("SELECT * FROM claims ORDER BY claim_id", conn)
    conn.close()
    return df

def fetch_reports():
    conn = sqlite3.connect(REPORTS_DB)
    df = pd.read_sql_query("SELECT * FROM reports ORDER BY created_ts DESC", conn)
    conn.close()
    return df

def fetch_provider_mapping():
    conn = sqlite3.connect(RX_DB)
    df = pd.read_sql_query("SELECT * FROM provider_mapping", conn)
    conn.close()
    return df

def get_claim_ids():
    conn = sqlite3.connect(RX_DB)
    cur = conn.cursor()
    cur.execute("SELECT claim_id, error_code FROM claims ORDER BY claim_id")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_db_stats():
    conn1 = sqlite3.connect(RX_DB)
    cur1 = conn1.cursor()
    cur1.execute("SELECT COUNT(*) FROM claims")
    total = cur1.fetchone()[0]
    cur1.execute("SELECT COUNT(*) FROM claims WHERE status='READY_FOR_REPROCESS'")
    reprocess = cur1.fetchone()[0]
    cur1.execute("SELECT COUNT(*) FROM claims WHERE status='REJECTED'")
    rejected = cur1.fetchone()[0]
    cur1.execute("SELECT COUNT(*) FROM claims WHERE status='ALREADY_PROCESSED'")
    already_processed = cur1.fetchone()[0]
    cur1.execute("SELECT COUNT(*) FROM claims WHERE error_code='781'")
    e781 = cur1.fetchone()[0]
    cur1.execute("SELECT COUNT(*) FROM claims WHERE error_code='935'")
    e935 = cur1.fetchone()[0]
    conn1.close()

    conn2 = sqlite3.connect(REPORTS_DB)
    cur2 = conn2.cursor()
    cur2.execute("SELECT COUNT(*) FROM reports")
    reports = cur2.fetchone()[0]
    conn2.close()
    return total, reprocess, rejected, already_processed, e781, e935, reports

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💊 PDE Claim System-")
    st.markdown("---")
    st.markdown("**🤖 Dynamic ReAct Orchestrator**")
    st.markdown("""
    <div style='font-size:0.82rem; color:#7fb3d3; line-height:2'>
    🧠 <b style='color:#4fc3f7'>Dynamic Orchestrator</b> <span style='color:#4a6080'>[ReAct Supervisor]</span><br>
    &nbsp;&nbsp;↳ reads SOP → fetches claim → decides pipeline<br>
    &nbsp;&nbsp;↳ calls only agents required for each error code<br>
    <br>
    <span style='color:#4a6080'>Agents invoked as tools:</span><br>
    &nbsp;&nbsp;💊 <b style='color:#66bb6a'>RX Agent</b> — adjudication (781 &amp; 935)<br>
    &nbsp;&nbsp;📋 <b style='color:#ab47bc'>Report Builder</b> — RCL / compliance report<br>
    &nbsp;&nbsp;🎫 <b style='color:#7c4dff'>ServiceNow</b> — ticket (REPROCESS only)<br>
    &nbsp;&nbsp;📧 <b style='color:#ffa726'>Email</b> — notification (not for REJECT)
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**📋 Error Codes**")
    st.markdown("""
    <div style='font-size:0.82rem; color:#7fb3d3; line-height:2'>
    <b style='color:#ef5350'>781</b> — Provider ID Missing/Invalid<br>
    <b style='color:#ffa726'>935</b> — Claim Already Adjudicated
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**⚡ Quick Links**")
    page = st.radio("Navigate", ["🏠 Dashboard", "🔍 Process Claim", "📊 Reports", "🗄️ Database"], label_visibility="collapsed")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='main-header'>
    <h1>💊 PDE Claim Processing System</h1>
    <p>Dynamic Multi-Agent AI · LangGraph · Azure OpenAI GPT-4o · Dynamic ReAct Orchestrator · SOP-driven Pipeline</p>
</div>
""", unsafe_allow_html=True)

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
if page == "🏠 Dashboard":
    total, reprocess, rejected, already_processed, e781, e935, reports = get_db_stats()

    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    with col1:
        st.markdown(f"<div class='metric-card'><div class='value'>{total}</div><div class='label'>Total Claims</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'><div class='value' style='color:#66bb6a'>{reprocess}</div><div class='label'>Ready to Reprocess</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='metric-card'><div class='value' style='color:#ef5350'>{rejected}</div><div class='label'>Rejected</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='metric-card'><div class='value' style='color:#4fc3f7'>{already_processed}</div><div class='label'>Already Processed</div></div>", unsafe_allow_html=True)
    with col5:
        st.markdown(f"<div class='metric-card'><div class='value' style='color:#ef5350'>{e781}</div><div class='label'>Error 781</div></div>", unsafe_allow_html=True)
    with col6:
        st.markdown(f"<div class='metric-card'><div class='value' style='color:#ffa726'>{e935}</div><div class='label'>Error 935</div></div>", unsafe_allow_html=True)
    with col7:
        st.markdown(f"<div class='metric-card'><div class='value' style='color:#ab47bc'>{reports}</div><div class='label'>Reports Generated</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("<div class='section-title'>🔄 Dynamic Orchestration Workflow</div>", unsafe_allow_html=True)
        st.markdown("""
        <div class='agent-step agent-orchestrator'>
            🧠 <b>DYNAMIC ORCHESTRATOR</b> <span style='font-size:0.75rem; color:#7fb3d3'>[ReAct Supervisor · Full Pipeline]</span><br>
            <span style='font-size:0.8rem'>Reads SOP → fetches claim → decides which agents to invoke → calls them as tools</span>
        </div>
        <div style='text-align:center; color:#4fc3f7; font-size:1.1rem; padding:4px 0'>↓ calls as tools (LLM-decided order) ↓</div>
        <div class='agent-step agent-rx'>
            💊 <b>RX AGENT</b> <span style='font-size:0.75rem'>[always invoked]</span><br>
            <span style='font-size:0.78rem'>
            <b>Error 781:</b> resolve provider ID → REPROCESS / REJECT<br>
            <b>Error 935:</b> compare dates → REPROCESS / ALREADY_PROCESSED
            </span>
        </div>
        <div style='text-align:center; color:#ab47bc; font-size:1.1rem; padding:4px 0'>↓ if NOT REJECT ↓</div>
        <div class='agent-step agent-report'>
            📋 <b>REPORT BUILDER</b> <span style='font-size:0.75rem'>[skipped on REJECT]</span><br>
            <span style='font-size:0.8rem'>REPROCESS → generates RCL file &nbsp;|&nbsp; ALREADY_PROCESSED → compliance report</span>
        </div>
        <div style='text-align:center; color:#7c4dff; font-size:1.1rem; padding:4px 0'>↓ if REPROCESS only ↓</div>
        <div class='agent-step agent-servicenow'>
            🎫 <b>SERVICENOW AGENT</b> <span style='font-size:0.75rem'>[REPROCESS only — LLM decides]</span><br>
            <span style='font-size:0.8rem'>raises incident ticket for all claims marked for reprocessing</span>
        </div>
        <div style='text-align:center; color:#ffa726; font-size:1.1rem; padding:4px 0'>↓ if NOT REJECT ↓</div>
        <div class='agent-step agent-email'>
            📧 <b>EMAIL AGENT</b> <span style='font-size:0.75rem'>[skipped on REJECT]</span><br>
            <span style='font-size:0.8rem'>LLM composes professional notification → simulates send via tool</span>
        </div>
        """, unsafe_allow_html=True)

    with col_right:
        st.markdown("<div class='section-title'>📈 Recent Reports</div>", unsafe_allow_html=True)
        try:
            df_reports = fetch_reports().head(5)
            if not df_reports.empty:
                for _, row in df_reports.iterrows():
                    badge = (
                        f"<span class='badge-reprocess'>{row['decision']}</span>" if row['decision'] == 'REPROCESS'
                        else f"<span class='badge-processed'>{row['decision']}</span>" if row['decision'] == 'ALREADY_PROCESSED'
                        else f"<span class='badge-reject'>{row['decision']}</span>"
                    )
                    ts = str(row['created_ts'])[:19]
                    st.markdown(f"""
                    <div style='background:#1a1f35; border:1px solid #2a3f5f; border-radius:8px; padding:0.7rem 1rem; margin:0.3rem 0; display:flex; justify-content:space-between; align-items:center'>
                        <span style='color:#e0f0ff; font-weight:600'>🗂️ {row['claim_id']}</span>
                        <span style='color:#7fb3d3; font-size:0.8rem'>Error: {row['error_code']}</span>
                        {badge}
                        <span style='color:#4a6080; font-size:0.75rem'>{ts}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No reports yet. Process a claim to get started.")
        except Exception as e:
            st.warning(f"Could not load reports: {e}")

# ── PROCESS CLAIM ─────────────────────────────────────────────────────────────
elif page == "🔍 Process Claim":
    st.markdown("<div class='section-title'>🔍 Process a PDE Claim</div>", unsafe_allow_html=True)

    col_form, col_info = st.columns([1, 1])

    with col_form:
        st.markdown("#### Select Claim")
        claim_rows = get_claim_ids()
        claim_options = {f"{r[0]}  —  Error {r[1]}": (r[0], r[1]) for r in claim_rows}
        selected_label = st.selectbox("Choose Claim", list(claim_options.keys()))
        selected_claim_id, selected_error_code = claim_options[selected_label]

        st.markdown("#### Or enter manually")
        manual_claim_id = st.text_input("Claim ID", value=selected_claim_id)
        manual_error_code = st.selectbox("Error Code", ["781", "935"], index=0 if selected_error_code == "781" else 1)

        run_btn = st.button("🚀 Run Agent Pipeline", type="primary")

    with col_info:
        st.markdown("#### SOP Preview")
        ec = manual_error_code
        try:
            with open(f"sop/SOP_PDE_{ec}.txt", "r", encoding="utf-8") as f:
                sop_text = f.read()
            st.markdown(f"""
            <div style='background:#0d1117; border:1px solid #1e3a5f; border-radius:10px; padding:1rem; font-size:0.8rem; color:#7fb3d3; max-height:240px; overflow-y:auto; white-space:pre-wrap'>
{sop_text}
            </div>
            """, unsafe_allow_html=True)
        except:
            st.warning(f"SOP file for error code {ec} not found.")

    # ── Run the pipeline ──────────────────────────────────────────────────────
    if run_btn:
        claim_id   = manual_claim_id.strip()
        error_code = manual_error_code

        st.markdown("---")
        st.markdown(f"### 🤖 Dynamic Orchestrator — Claim `{claim_id}` | Error Code `{error_code}`")

        log_capture = io.StringIO()
        old_stdout  = sys.stdout
        sys.stdout  = log_capture

        result = None
        pipeline_error = None

        with st.spinner("Running agent pipeline..."):
            try:
                from graph import build_graph
                app = build_graph()
                result = app.invoke({"claim_id": claim_id, "error_code": error_code})
            except Exception as e:
                pipeline_error = str(e)
            finally:
                sys.stdout = old_stdout

        logs = log_capture.getvalue()

        # ── Dynamic agent step indicators ─────────────────────────────────────
        agents_invoked = result.get("agents_invoked", []) if result else []
        decision   = result.get("decision", "") if result else ""
        email_st   = result.get("email_status", "") if result else ""
        sn_ticket  = result.get("servicenow_ticket", "") if result else ""

        a1, a2, a3, a4, a5 = st.columns(5)

        with a1:
            st.markdown("<div class='agent-step agent-orchestrator'>🧠 <b>ORCHESTRATOR</b><br><span style='font-size:0.8rem'>✅ Pipeline orchestrated</span></div>", unsafe_allow_html=True)
        with a2:
            if "RX_AGENT" in agents_invoked:
                ec = result.get("error_code", "") if result else ""
                sub = "781: provider resolved" if ec == "781" else "935: dates compared"
                rx_label = f"✅ {decision}<br><span style='font-size:0.72rem; opacity:0.8'>{sub}</span>"
            else:
                rx_label = "⏭️ Not invoked"
            st.markdown(f"<div class='agent-step agent-rx'>💊 <b>RX AGENT</b><br><span style='font-size:0.8rem'>{rx_label}</span></div>", unsafe_allow_html=True)
        with a3:
            if "REPORT" in agents_invoked:
                report = result.get("report", "") if result else ""
                rpt_status = "✅ Generated"
            else:
                rpt_status = "⏭️ Skipped (REJECT)"
            st.markdown(f"<div class='agent-step agent-report'>📋 <b>REPORT</b><br><span style='font-size:0.8rem'>{rpt_status}</span></div>", unsafe_allow_html=True)
        with a4:
            if "SERVICENOW" in agents_invoked and sn_ticket:
                st.markdown(f"<div class='agent-step agent-servicenow'>🎫 <b>SERVICENOW</b><br><span style='font-size:0.8rem'>✅ {sn_ticket}</span></div>", unsafe_allow_html=True)
            elif "SERVICENOW" in agents_invoked:
                st.markdown("<div class='agent-step agent-servicenow'>🎫 <b>SERVICENOW</b><br><span style='font-size:0.8rem'>✅ Ticket raised</span></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='agent-step agent-servicenow' style='opacity:0.35'>🎫 <b>SERVICENOW</b><br><span style='font-size:0.8rem'>⏭️ Not needed</span></div>", unsafe_allow_html=True)
        with a5:
            if "EMAIL" in agents_invoked:
                em_status = "✅ Sent" if email_st == "SENT" else "⚠️ Not sent"
            else:
                em_status = "⏭️ Skipped (REJECT)"
            st.markdown(f"<div class='agent-step agent-email'>📧 <b>EMAIL</b><br><span style='font-size:0.8rem'>{em_status}</span></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Result summary ────────────────────────────────────────────────────
        if result:
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.markdown("<div class='section-title'>📊 Final State</div>", unsafe_allow_html=True)
                decision_badge = (
                    f"<span class='badge-reprocess'>{decision}</span>" if decision == "REPROCESS"
                    else f"<span class='badge-processed'>{decision}</span>" if decision == "ALREADY_PROCESSED"
                    else f"<span class='badge-reject'>{decision}</span>"
                )
                orch_reasoning = result.get("reasoning", "")
                agents_invoked_list = result.get("agents_invoked", [])
                agents_str = " → ".join(agents_invoked_list) if agents_invoked_list else "N/A"
                sn_row = f"<tr><td style='color:#7c4dff; padding:4px 8px'>ServiceNow</td><td style='padding:4px 8px'><span style='color:#d0b3ff'>{sn_ticket or '—'}</span></td></tr>" if sn_ticket else ""
                rcl_row = f"<tr><td style='color:#ab47bc; padding:4px 8px'>RCL File</td><td style='padding:4px 8px; font-size:0.78rem; color:#dbb3db'>{result.get('rcl_file','—')}</td></tr>" if result.get('rcl_file') else ""
                st.markdown(f"""
                <div style='background:#1a1f35; border:1px solid #2a3f5f; border-radius:10px; padding:1.2rem'>
                    <table style='width:100%; font-size:0.88rem; color:#b3d9f7'>
                        <tr><td style='color:#4fc3f7; padding:4px 8px'>Claim ID</td><td style='padding:4px 8px'>{result.get('claim_id','')}</td></tr>
                        <tr><td style='color:#4fc3f7; padding:4px 8px'>Error Code</td><td style='padding:4px 8px'>{result.get('error_code','')}</td></tr>
                        <tr><td style='color:#4fc3f7; padding:4px 8px'>Agents Invoked</td><td style='padding:4px 8px; font-size:0.82rem'>{agents_str}</td></tr>
                        <tr><td style='color:#4fc3f7; padding:4px 8px'>Provider ID</td><td style='padding:4px 8px'>{result.get('provider_id','N/A')}</td></tr>
                        <tr><td style='color:#4fc3f7; padding:4px 8px'>Decision</td><td style='padding:4px 8px'>{decision_badge}</td></tr>
                        {sn_row}
                        {rcl_row}
                        <tr><td style='color:#4fc3f7; padding:4px 8px'>Email</td><td style='padding:4px 8px'><span class='badge-sent'>{email_st or 'N/A'}</span></td></tr>
                    </table>
                    {f"<div style='margin-top:0.8rem; padding:0.7rem; background:#0d1117; border-radius:8px; font-size:0.8rem; color:#7fb3d3'><b style='color:#4fc3f7'>🧠 Orchestrator Reasoning:</b><br>{orch_reasoning}</div>" if orch_reasoning else ""}
                </div>
                """, unsafe_allow_html=True)

            with col_r2:
                st.markdown("<div class='section-title'>📋 Report</div>", unsafe_allow_html=True)
                st.markdown(f"""
                <div style='background:#0d1117; border:1px solid #1e3a5f; border-radius:10px; padding:1.2rem; font-size:0.88rem; color:#b3d9f7; min-height:120px'>
                    {result.get('report','No report generated.')}
                </div>
                """, unsafe_allow_html=True)

                if result.get("rcl_file"):
                    st.markdown(f"""
                    <div style='background:#1a2d1a; border:1px solid #2a5f2a; border-radius:10px; padding:1rem; margin-top:0.8rem; font-size:0.85rem; color:#b7dfb7'>
                        📄 <b>RCL File Generated</b><br>
                        <span style='color:#66bb6a'>{result['rcl_file']}</span>
                    </div>
                    """, unsafe_allow_html=True)

                if result.get("servicenow_ticket"):
                    sn_summary = result.get("servicenow_summary", "")
                    claims_count = result.get("claims_count", "")
                    st.markdown(f"""
                    <div style='background:#1a1a2d; border:1px solid #4a2aaa; border-radius:10px; padding:1rem; margin-top:0.8rem; font-size:0.85rem; color:#d0b3ff'>
                        🎫 <b>ServiceNow Ticket Raised</b><br>
                        Ticket: <span style='color:#7c4dff; font-weight:600'>{result['servicenow_ticket']}</span>
                        {f"&nbsp;·&nbsp; {claims_count} claims" if claims_count else ""}
                        {f"<br><span style='color:#a08bcc; font-size:0.82rem'>{sn_summary}</span>" if sn_summary else ""}
                    </div>
                    """, unsafe_allow_html=True)

                if result.get("resolved_provider"):
                    p = result["resolved_provider"]
                    st.markdown(f"""
                    <div style='background:#1a2d1a; border:1px solid #2a5f2a; border-radius:10px; padding:1rem; margin-top:0.8rem; font-size:0.85rem; color:#b7dfb7'>
                        ✅ <b>Provider Resolved</b><br>
                        Name: {p.get('provider_name','')}<br>
                        New ID: {p.get('new_provider_id','')}<br>
                        NPI: {p.get('npi','')}
                    </div>
                    """, unsafe_allow_html=True)

            # ── ReAct Reasoning Traces ────────────────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("<div class='section-title'>🧠 ReAct Agent Reasoning Traces</div>", unsafe_allow_html=True)

            trace_tabs = st.tabs([
                "🧠 Orchestrator",
                "💊 RX Agent",
                "📋 Report Builder",
                "🎫 ServiceNow",
                "📧 Email Agent",
            ])

            def render_trace(trace_text: str):
                if not trace_text:
                    st.info("This agent was not invoked for this claim.")
                    return
                lines = trace_text.split("\n")
                html_lines = []
                for line in lines:
                    if line.startswith("🔧 Tool"):
                        html_lines.append(
                            f"<div style='background:#1a2d1a; border-left:3px solid #66bb6a; padding:4px 10px; margin:2px 0; border-radius:4px; font-size:0.78rem; color:#b7dfb7'>{line}</div>"
                        )
                    elif "tool" in line.lower():
                        html_lines.append(
                            f"<div style='background:#2d1a1a; border-left:3px solid #ef5350; padding:4px 10px; margin:2px 0; border-radius:4px; font-size:0.78rem; color:#f7b3b3'>{line}</div>"
                        )
                    elif line.startswith("💬 [ai]") or line.startswith("💬 [AIMessage"):
                        html_lines.append(
                            f"<div style='background:#1a2744; border-left:3px solid #4fc3f7; padding:4px 10px; margin:2px 0; border-radius:4px; font-size:0.78rem; color:#b3d9f7'>{line}</div>"
                        )
                    elif line.strip():
                        html_lines.append(
                            f"<div style='padding:3px 10px; font-size:0.78rem; color:#7fb3d3'>{line}</div>"
                        )
                st.markdown(
                    f"<div style='background:#0d1117; border:1px solid #1e3a5f; border-radius:10px; padding:0.8rem; max-height:350px; overflow-y:auto'>{''.join(html_lines)}</div>",
                    unsafe_allow_html=True
                )

            with trace_tabs[0]:
                render_trace(result.get("orchestrator_trace", ""))
            with trace_tabs[1]:
                render_trace(result.get("rx_agent_trace", ""))
            with trace_tabs[2]:
                render_trace(result.get("report_agent_trace", ""))
            with trace_tabs[3]:
                render_trace(result.get("servicenow_trace", ""))
            with trace_tabs[4]:
                render_trace(result.get("email_agent_trace", ""))

        if pipeline_error:
            st.error(f"Pipeline error: {pipeline_error}")

        # ── Agent logs ────────────────────────────────────────────────────────
        with st.expander("🔍 View Agent Logs", expanded=False):
            st.markdown(f"<div class='log-box'>{logs}</div>", unsafe_allow_html=True)

# ── REPORTS ───────────────────────────────────────────────────────────────────
elif page == "📊 Reports":
    st.markdown("<div class='section-title'>📊 Generated Reports</div>", unsafe_allow_html=True)

    try:
        df = fetch_reports()
        if df.empty:
            st.info("No reports found. Process some claims first.")
        else:
            # Filter bar
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                dec_filter = st.multiselect("Filter by Decision", df["decision"].unique().tolist(), default=df["decision"].unique().tolist())
            with col_f2:
                ec_filter = st.multiselect("Filter by Error Code", df["error_code"].unique().tolist(), default=df["error_code"].unique().tolist())
            with col_f3:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(f"<div style='color:#4fc3f7; font-size:0.9rem'>📝 Total reports: <b>{len(df)}</b></div>", unsafe_allow_html=True)

            filtered = df[df["decision"].isin(dec_filter) & df["error_code"].isin(ec_filter)]

            for _, row in filtered.iterrows():
                decision_badge = (
                    f"<span class='badge-reprocess'>{row['decision']}</span>" if row['decision'] == 'REPROCESS'
                    else f"<span class='badge-processed'>{row['decision']}</span>" if row['decision'] == 'ALREADY_PROCESSED'
                    else f"<span class='badge-reject'>{row['decision']}</span>"
                )
                with st.expander(f"🗂️ {row['claim_id']}  |  Error {row['error_code']}  |  {str(row['created_ts'])[:19]}"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.markdown(f"""
                        <div style='font-size:0.88rem; color:#b3d9f7; line-height:1.8'>
                            <b style='color:#4fc3f7'>Claim ID:</b> {row['claim_id']}<br>
                            <b style='color:#4fc3f7'>Error Code:</b> {row['error_code']}<br>
                            <b style='color:#4fc3f7'>Provider ID:</b> {row.get('provider_id','N/A')}<br>
                            <b style='color:#4fc3f7'>Decision:</b> {decision_badge}<br>
                            <b style='color:#4fc3f7'>Timestamp:</b> {str(row['created_ts'])[:19]}
                        </div>
                        """, unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"""
                        <div style='background:#0d1117; border:1px solid #1e3a5f; border-radius:8px; padding:1rem; font-size:0.85rem; color:#7fb3d3'>
                            {row.get('reason','N/A')}
                        </div>
                        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading reports: {e}")

# ── DATABASE ──────────────────────────────────────────────────────────────────
elif page == "🗄️ Database":
    st.markdown("<div class='section-title'>🗄️ Database Explorer</div>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📋 Claims", "🔗 Provider Mapping", "📊 Reports DB"])

    with tab1:
        try:
            df_claims = fetch_all_claims()
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                status_filter = st.multiselect("Filter by Status", df_claims["status"].unique().tolist(), default=df_claims["status"].unique().tolist())
            with col_s2:
                ec_filter2 = st.multiselect("Filter by Error Code", df_claims["error_code"].unique().tolist(), default=df_claims["error_code"].unique().tolist())

            filtered_claims = df_claims[df_claims["status"].isin(status_filter) & df_claims["error_code"].isin(ec_filter2)]
            st.dataframe(filtered_claims, use_container_width=True, height=420)
            st.markdown(f"<div style='color:#4a6080; font-size:0.8rem'>Showing {len(filtered_claims)} of {len(df_claims)} claims</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error loading claims: {e}")

    with tab2:
        try:
            df_pm = fetch_provider_mapping()
            st.dataframe(df_pm, use_container_width=True, height=350)
        except Exception as e:
            st.error(f"Error loading provider mapping: {e}")

    with tab3:
        try:
            df_rep = fetch_reports()
            st.dataframe(df_rep, use_container_width=True, height=420)
        except Exception as e:
            st.error(f"Error loading reports DB: {e}")
