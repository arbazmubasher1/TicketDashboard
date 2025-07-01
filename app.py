# app.py
# ─────────────────────────────────────────────────────────────
#  Team Ticket Dashboard  –  multi-user edition
#  (Streamlit Cloud-ready: uses st.secrets for credentials)
# ─────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import altair as alt
import os
from typing import List

# ──────────────────────────────────────
# ⚙️  Page setup
st.set_page_config(page_title="Ticket Dashboard", layout="wide")

# ──────────────────────────────────────
# 👤  Very simple in-memory user store
USERS = {
    "osaid.jahangir@johnnyandjugnu.com": {
        "password": "admin123", "role": "admin", "domain": None},
    "leasing":      {"password": "L123",  "role": "user", "domain": "Leasing"},
    "design":       {"password": "D123",  "role": "user", "domain": "Design"},
    "equipment":    {"password": "E123",  "role": "user", "domain": "Equipment"},
    "construction": {"password": "C123",  "role": "user", "domain": "Construction"},
    "pm":           {"password": "PM123", "role": "user", "domain": "Project Management"},
}

ALL_DOMAINS:  List[str] = ["Leasing", "Design", "Equipment", "Construction", "Project Management"]
ALL_STATUSES: List[str] = ["Initiated", "Partial", "Stuck", "Completed"]

# ──────────────────────────────────────
# 🔐  Login helper
def login() -> None:
    st.title("🔐 Login to Ticket Dashboard")

    with st.form("login_form"):
        email = st.text_input("Email or Username").lower().strip()
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        user = USERS.get(email)
        if submitted:
            if user and password == user["password"]:
                st.session_state.update(
                    logged_in=True,
                    role=user["role"],
                    email=email,
                    user_domain=user["domain"],
                )
                st.rerun()
            else:
                st.error("❌ Incorrect credentials")

# ──────────────────────────────────────
# 🔐  Session init
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if not st.session_state["logged_in"]:
    login()
    st.stop()

# ──────────────────────────────────────
# 🚪  Sidebar – logout
with st.sidebar:
    st.write(f"Logged in as: **{st.session_state['email']}**")
    if st.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

# ──────────────────────────────────────
# ✅  Google Sheets connection (local or Cloud secrets)
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

def get_gspread_client():
    """Return an authorised gspread client using either Streamlit-cloud secrets or a local file."""
    if "GOOGLE_SHEETS_CREDENTIALS" in st.secrets:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    elif os.path.exists("credentials.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    else:
        st.error(
            "❌ No Google credentials found. "
            "Add credentials.json locally or set GOOGLE_SHEETS_CREDENTIALS in secrets."
        )
        st.stop()
    return gspread.authorize(creds)

client = get_gspread_client()
sheet  = client.open("TicketDashboard").sheet1     # first worksheet

# ──────────────────────────────────────
# 📦  Data helpers
def get_data() -> pd.DataFrame:
    """Read the entire sheet into a DataFrame and ensure correct dtypes."""
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        return df

    df["Created At"] = pd.to_datetime(df["Created At"])
    df["Deadline"]   = pd.to_datetime(df["Deadline"])
    if "Elapsed Days" in df.columns:
        df["Elapsed Days"] = pd.to_numeric(df["Elapsed Days"], errors="coerce")  # keep numeric
    df["SheetRow"]   = df.index + 2     # +2 because header is row 1
    return df

def add_ticket(task: str, domain: str, deadline: date,
               status: str, comments: str) -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [task, domain, created_at, deadline.strftime("%Y-%m-%d"),
           status, "", comments]
    sheet.append_row(row)

# -------------  🔑  **Fixed** -------------
def update_elapsed_in_sheet(df: pd.DataFrame) -> None:
    """
    Batch-update the whole Elapsed Days column in one write,
    instead of one API call per cell (avoids 429 quota hits).
    """
    now = datetime.now()
    values = [[(now - created).days] for created in df["Created At"]]
    rng = f"F2:F{len(values) + 1}"     # column F, skip header
    # Single API request:
    sheet.update(rng, values, value_input_option="USER_ENTERED")
# ------------------------------------------

def delete_ticket(sheet_row: int) -> None:
    sheet.delete_rows(sheet_row)

def update_ticket(sheet_row: int, task: str, domain: str,
                  deadline: date, status: str, comments: str) -> None:
    created_at   = sheet.cell(sheet_row, 3).value   # keep original timestamp
    elapsed_days = sheet.cell(sheet_row, 6).value   # keep existing elapsed value
    sheet.update(
        f"A{sheet_row}:G{sheet_row}",
        [[task, domain, created_at, deadline.strftime("%Y-%m-%d"),
          status, elapsed_days, comments]]
    )

# ──────────────────────────────────────
# ✅  Multiselect helper with “Select all”
def multiselect_with_select_all(label: str, options: List[str], key_prefix: str) -> List[str]:
    select_all_key  = f"{key_prefix}_select_all"
    multiselect_key = f"{key_prefix}_multiselect"

    select_all = st.checkbox(f"Select all {label.lower()}", key=select_all_key)
    if select_all:
        st.multiselect(label, options, default=options, key=multiselect_key, disabled=True)
        return options
    return st.multiselect(label, options, key=multiselect_key)

# ──────────────────────────────────────
# 🌐  UI  – title & CSS
st.title("🎟️ Team Ticket Dashboard")

st.markdown("""
<style>
.ticket-card{
  background-color:#fff;padding:18px 22px;border-radius:12px;
  margin-bottom:15px;box-shadow:0 1px 4px rgba(0,0,0,0.05);
}
.ticket-header{font-weight:600;font-size:1.2rem;margin-bottom:5px;}
.pill{font-size:0.75rem;background:#eee;padding:3px 8px;border-radius:20px;margin-left:10px;}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────
# ➕  Add-ticket form
with st.expander("➕ Add New Ticket"):
    with st.form("new_ticket"):
        col1, col2 = st.columns(2)
        task = col1.text_input("Task")

        if st.session_state["role"] == "admin":
            domain = col2.selectbox("Domain", ALL_DOMAINS)
        else:
            domain = st.session_state["user_domain"]
            col2.text_input("Domain", value=domain, disabled=True)

        deadline = col1.date_input("Deadline")
        status   = col2.selectbox("Status", ALL_STATUSES)
        comments = st.text_area("Comments")

        if st.form_submit_button("Submit Ticket"):
            add_ticket(task, domain, deadline, status, comments)
            st.success("✅ Ticket added successfully!")
            st.rerun()

# ──────────────────────────────────────
# 🔄  Load data & elapsed-time sync
df = get_data()
if not df.empty:
    update_elapsed_in_sheet(df)   # one batch write

# ──────────────────────────────────────
# 📊  Ticket status summary
st.subheader("📊 Ticket Status Overview")
status_counts = df["Status"].value_counts().to_dict()
status_icons  = {"Completed": "🟢", "Partial": "🟡", "Stuck": "🔴", "Initiated": "⚪"}
st.markdown(" | ".join(f"{status_icons.get(k, '❔')} **{k}**: {v}"
                       for k, v in status_counts.items()))

# ──────────────────────────────────────
# 🔍  Filters
st.subheader("🔍 Filters")
status_filter = multiselect_with_select_all("Status",
                                            sorted(df["Status"].unique()),
                                            "status_filter")
domain_filter = multiselect_with_select_all("Domain",
                                            sorted(df["Domain"].unique()),
                                            "domain_filter")

if not status_filter:
    status_filter = df["Status"].unique().tolist()
if not domain_filter:
    domain_filter = df["Domain"].unique().tolist()

filtered_df = df[df["Status"].isin(status_filter) & df["Domain"].isin(domain_filter)]

# ──────────────────────────────────────
# 📋  Ticket list
st.subheader("📋 Filtered Tickets")
now = datetime.now()

STATUS_COLORS = {
    "Completed": "#4caf50",
    "Partial":   "#fbc02d",
    "Stuck":     "#e53935",
    "Initiated": "#90a4ae",
}

for _, row in filtered_df.iterrows():
    created_time = row["Created At"]
    deadline     = row["Deadline"]
    elapsed_str  = str(now - created_time).split(".", 1)[0]
    sheet_row    = row["SheetRow"]

    border_color = STATUS_COLORS.get(row["Status"], "#ccc")

    with st.container():
        st.markdown(f"""
<div class="ticket-card" style="border-left:6px solid {border_color};">
  <div class="ticket-header">{row['Task']} <span class="pill">{row['Status']}</span></div>
  <div>🛠️ <b>Domain:</b> {row['Domain']}</div>
  <div>🕑 <b>Created:</b> {created_time.strftime('%Y-%m-%d %H:%M')}</div>
  <div>⏱️ <b>Elapsed:</b> {elapsed_str}</div>
  <div>📅 <b>Deadline:</b> {deadline.strftime('%Y-%m-%d')}</div>
  <div>💬 <b>Comments:</b> {row['Comments']}</div>
</div>
""", unsafe_allow_html=True)

        # — permissions —
        can_modify = (
            st.session_state["role"] == "admin" or
            row["Domain"] == st.session_state.get("user_domain")
        )

        if can_modify:
            colA, colB = st.columns([1, 1])
            if colA.button("🗑️ Delete", key=f"del_{sheet_row}"):
                delete_ticket(sheet_row)
                st.success("Deleted! Refreshing…")
                st.rerun()

            if colB.button("✏️ Edit", key=f"edit_btn_{sheet_row}"):
                st.session_state[f"edit_{sheet_row}"] = True

            if st.session_state.get(f"edit_{sheet_row}", False):
                with st.form(f"edit_form_{sheet_row}"):
                    new_task = st.text_input("Edit Task", value=row["Task"])

                    if st.session_state["role"] == "admin":
                        new_domain = st.selectbox("Edit Domain",
                                                  ALL_DOMAINS,
                                                  index=ALL_DOMAINS.index(row["Domain"]))
                    else:
                        new_domain = row["Domain"]
                        st.text_input("Edit Domain", value=new_domain, disabled=True)

                    new_deadline = st.date_input("Edit Deadline", value=deadline.date())
                    new_status   = st.selectbox("Edit Status",
                                                ALL_STATUSES,
                                                index=ALL_STATUSES.index(row["Status"]))
                    new_comments = st.text_area("Edit Comments", value=row["Comments"])

                    if st.form_submit_button("Save Changes"):
                        update_ticket(sheet_row, new_task, new_domain,
                                      new_deadline, new_status, new_comments)
                        st.success("✅ Ticket updated!")
                        del st.session_state[f"edit_{sheet_row}"]
                        st.rerun()

# ──────────────────────────────────────
# 🗓️  Deadline histogram
st.subheader("🗓️ Deadlines Overview")
deadline_chart = (
    alt.Chart(df)
       .mark_bar()
       .encode(
           x=alt.X("Deadline:T", title="Deadline"),
           y=alt.Y("count():Q", title="Tickets"),
           color=alt.Color("Status:N"),
           tooltip=["Task", "Domain", "Deadline", "Status"]
       )
       .properties(height=300)
)
st.altair_chart(deadline_chart, use_container_width=True)
