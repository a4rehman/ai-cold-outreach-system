import streamlit as st
import asyncio
import pandas as pd
import os
import json
from datetime import datetime
import src.lead_gen as lead_gen
from src.lead_gen import DATA_DIR

# --- Page Config ---
st.set_page_config(
    page_title="100Solutionz | Lead Gen Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Premium Look ---
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #ff4b4b;
        color: white;
        font-weight: bold;
    }
    .stMetric {
        background-color: #161b22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    .status-card {
        background-color: #161b22;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'pipeline_state' not in st.session_state:
    st.session_state.pipeline_state = None

def hidden_config_input(label, env_name):
    is_configured = bool(os.environ.get(env_name, ""))
    return st.text_input(
        label,
        type="password",
        value="",
        placeholder="Configured (hidden)" if is_configured else "",
        help="Leave blank to keep the current saved value." if is_configured else None,
    )

# --- Sidebar ---
with st.sidebar:
    st.image("https://100solutionz.vercel.app/logo.png", width=200) # Placeholder for logo
    st.title("Settings")
    
    target_count = st.number_input("Target Leads", min_value=1, max_value=200, value=50)
    
    st.markdown("---")
    st.subheader("API Configuration")
    openai_key = hidden_config_input("OpenAI API Key", "OPENAI_API_KEY")
    
    st.subheader("SMTP Configuration")
    email_user = hidden_config_input("Sender Email", "EMAIL_USER")
    email_pass = hidden_config_input("Email Password", "EMAIL_PASSWORD")
    
    if st.button("Save Config"):
        updated = False

        if openai_key.strip():
            clean_openai_key = openai_key.strip()
            os.environ["OPENAI_API_KEY"] = clean_openai_key
            lead_gen.OPENAI_API_KEY = clean_openai_key
            lead_gen.client = lead_gen.OpenAI(api_key=clean_openai_key)
            updated = True

        if email_user.strip():
            clean_email_user = email_user.strip()
            os.environ["EMAIL_USER"] = clean_email_user
            lead_gen.EMAIL_USER = clean_email_user
            updated = True

        if email_pass.strip():
            clean_email_pass = email_pass.strip()
            os.environ["EMAIL_PASSWORD"] = clean_email_pass
            lead_gen.EMAIL_PASS = clean_email_pass
            updated = True

        if updated:
            st.success("Config updated!")
        else:
            st.info("No config changes entered. Existing hidden values were kept.")

# --- Main Dashboard ---
st.title("🚀 Salon Lead Generation & Outreach")
st.markdown("Automated Discovery, AI Analysis, and Professional Cold Emailing.")

col1, col2, col3, col4 = st.columns(4)

# Placeholder metrics
discovered_placeholder = col1.empty()
sent_placeholder = col2.empty()
failed_placeholder = col3.empty()
progress_placeholder = col4.empty()

# Progress metrics
def update_metrics(state):
    discovered_placeholder.metric("Discovered", len(state.get("discovered_urls", [])))
    sent_placeholder.metric("Emails Sent", state.get("emails_sent", 0))
    failed_placeholder.metric("Failed", state.get("failed_count", 0))
    progress_placeholder.metric("Current Lead", f"{state.get('current_index', 0)}/{target_count}")

# Dashboard table area
status_container = st.container()
results_area = st.empty()

def ui_callback(state):
    st.session_state.pipeline_state = state
    update_metrics(state)
    
    with status_container:
        st.subheader("Workflow Status")
        ni = state.get("node_info", {})
        cols = st.columns(len(ni))
        for i, (node, info) in enumerate(ni.items()):
            with cols[i % len(cols)]:
                st.markdown(f"**{node.replace('_', ' ').title()}**")
                st.caption(f"{info['status']} - {info['message']}")

    # Update results table
    if state.get("reports"):
        df = pd.DataFrame(state["reports"])
        if 'email_message' in df.columns:
            # Show only relevant columns in preview
            cols_to_show = ["business_name", "website", "status"]
            results_area.table(df[cols_to_show].tail(10))

# --- Execution ---
if not st.session_state.is_running:
    if st.button("🔥 Launch Campaign"):
        st.session_state.is_running = True
        st.rerun()

if st.session_state.is_running:
    st.info("Campaign in progress... Please do not close this tab.")
    if st.button("🛑 Stop Campaign"):
        st.session_state.is_running = False
        st.rerun()

    # Run the async pipeline
    async def run_app():
        await lead_gen.run_pipeline(target_override=target_count, ui_callback=ui_callback)
        st.session_state.is_running = False
        st.success("Campaign Complete!")
        st.balloons()

    asyncio.run(run_app())

# --- Results Tab ---
st.markdown("---")
st.subheader("📊 Recent Campaign Results")

# Load existing results from data directory
try:
    all_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.json') and 'lead_gen_results' in f]
    if all_files:
        latest_file = max([os.path.join(DATA_DIR, f) for f in all_files], key=os.path.getctime)
        with open(latest_file, 'r') as f:
            data = json.load(f)
            df_full = pd.DataFrame(data)
            st.dataframe(df_full)
            
            csv = df_full.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Results (CSV)",
                data=csv,
                file_name=f"lead_gen_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime='text/csv',
            )
    else:
        st.write("No campaign data found yet. Start a campaign to see results.")
except Exception as e:
    st.write(f"Error loading results: {e}")
