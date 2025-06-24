import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import altair as alt
import json
# ✅ This must be first
st.set_page_config(page_title="Ticket Dashboard", layout="wide")

# ──────────────────────────────────────
# 🔐 Login Setup
def login():
    st.title("🔐 Login to Ticket Dashboard")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if email == "osaid.jahangir@johnnyandjugnu.com" and password == "admin123":
                st.session_state["logged_in"] = True
                st.session_state["role"] = "admin"
                st.session_state["email"] = email
                st.rerun()
            elif password == "admin123":
                st.session_state["logged_in"] = True
                st.session_state["role"] = "user"
                st.session_state["email"] = email
                st.rerun()
            else:
                st.error("❌ Incorrect credentials")

# ──────────────────────────────────────
# 🔐 Session Init
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
    st.stop()

# ──────────────────────────────────────
# 🚪 Logout Button
with st.sidebar:
    st.write(f"Logged in as: {st.session_state.get('email')}")
    if st.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

# ──────────────────────────────────────
# ✅ Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["google_service_account"]), scope)
client = gspread.authorize(creds)
sheet = client.open("TicketDashboard").sheet1

# ──────────────────────────────────────
def get_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df["Created At"] = pd.to_datetime(df["Created At"])
        df["Deadline"] = pd.to_datetime(df["Deadline"])
        # Don't use df.index because filtering will break it — use row number from enumerate
        df["SheetRow"] = [i + 2 for i in range(len(df))]  # Offset +2 to skip header
    return df

def add_ticket(task, domain, deadline, status, comments):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [task, domain, created_at, deadline.strftime("%Y-%m-%d"), status, "", comments]
    sheet.append_row(row)

def update_elapsed_in_sheet(df):
    now = datetime.now()
    elapsed_days = (now - df['Created At']).dt.days
    for idx, days in enumerate(elapsed_days):
        sheet.update_cell(idx + 2, 6, f"{days}")

def delete_ticket(sheet_row):
    sheet.delete_rows(sheet_row)

def update_ticket(sheet_row, task, domain, deadline, status, comments):
    created_at = sheet.cell(sheet_row, 3).value
    elapsed_days = sheet.cell(sheet_row, 6).value
    sheet.update(
        f"A{sheet_row}:G{sheet_row}",
        [[task, domain, created_at, deadline.strftime("%Y-%m-%d"), status, elapsed_days, comments]]
    )

# ──────────────────────────────────────
st.title("🎟️ Team Ticket Dashboard")

# CSS Styling
st.markdown("""
    <style>
    .ticket-card {
        background-color: #ffffff;
        padding: 18px 22px;
        border-radius: 12px;
        margin-bottom: 15px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }
    .ticket-header {
        font-weight: 600;
        font-size: 1.2rem;
        margin-bottom: 5px;
    }
    .pill {
        font-size: 0.75rem;
        background-color: #eee;
        padding: 3px 8px;
        border-radius: 20px;
        margin-left: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Add Ticket Form
with st.expander("➕ Add New Ticket"):
    with st.form("new_ticket"):
        col1, col2 = st.columns(2)
        task = col1.text_input("Task")
        domain = col2.selectbox("Domain", ["Leasing", "Design", "Equipment", "Project Management"])
        deadline = col1.date_input("Deadline")
        status = col2.selectbox("Status", ["Initiated", "Partial", "Stuck", "Completed"])
        comments = st.text_area("Comments")
        submitted = st.form_submit_button("Submit Ticket")
        if submitted:
            add_ticket(task, domain, deadline, status, comments)
            st.success("✅ Ticket added successfully!")

# Load data
df = get_data()
if not df.empty:
    update_elapsed_in_sheet(df)

# Summary
st.subheader("📊 Ticket Status Overview")
status_counts = df["Status"].value_counts().to_dict()
status_icons = {"Completed": "🟢", "Partial": "🟡", "Stuck": "🔴", "Initiated": "⚪"}
st.markdown(" | ".join(f"{status_icons.get(k, '❔')} **{k}**: {v}" for k, v in status_counts.items()))

# Filters
st.subheader("🔍 Filters")
col1, col2 = st.columns(2)
status_filter = col1.multiselect("Filter by Status", options=df["Status"].unique(), default=df["Status"].unique())
domain_filter = col2.multiselect("Filter by Domain", options=df["Domain"].unique(), default=df["Domain"].unique())
filtered_df = df[df["Status"].isin(status_filter) & df["Domain"].isin(domain_filter)]

# Display Tickets
st.subheader("📋 Filtered Tickets")
now = datetime.now()

for _, row in filtered_df.iterrows():
    created_time = row['Created At']
    deadline = row['Deadline']
    elapsed = now - created_time
    elapsed_str = str(elapsed).split('.')[0]
    sheet_row = row['SheetRow']

    border_color = "#ccc"
    if now.date() > deadline.date():
        border_color = "#e53935"
    elif (deadline.date() - now.date()).days <= 2:
        border_color = "#fbc02d"

    with st.container():
        st.markdown(f"""
            <div class="ticket-card" style="border-left: 6px solid {border_color};">
                <div class="ticket-header">
                    {row['Task']} <span class="pill">{row['Status']}</span>
                </div>
                <div>🛠️ <b>Domain:</b> {row['Domain']}</div>
                <div>🕑 <b>Created:</b> {created_time.strftime('%Y-%m-%d %H:%M')}</div>
                <div>⏱️ <b>Elapsed:</b> {elapsed_str}</div>
                <div>📅 <b>Deadline:</b> {deadline.strftime('%Y-%m-%d')}</div>
                <div>💬 <b>Comments:</b> {row['Comments']}</div>
            </div>
        """, unsafe_allow_html=True)

        if st.session_state["role"] == "admin":
            colA, colB = st.columns([1, 1])
            if colA.button("🗑️ Delete", key=f"del_{sheet_row}"):
                delete_ticket(sheet_row)
                st.success("Deleted! Refreshing...")
                st.rerun()

            if colB.button("✏️ Edit", key=f"edit_btn_{sheet_row}"):
                st.session_state[f"edit_{sheet_row}"] = True

            if st.session_state.get(f"edit_{sheet_row}", False):
                with st.form(f"edit_form_{sheet_row}"):
                    domain_options = ["Leasing", "Design", "Equipment", "Project Management", "Construction"]
                    status_options = ["Initiated", "Partial", "Stuck", "Completed"]

                    new_task = st.text_input("Edit Task", value=row['Task'])
                    new_domain = st.selectbox("Edit Domain", domain_options, index=domain_options.index(row['Domain']) if row['Domain'] in domain_options else 0)
                    new_deadline = st.date_input("Edit Deadline", value=row['Deadline'])
                    new_status = st.selectbox("Edit Status", status_options, index=status_options.index(row['Status']) if row['Status'] in status_options else 0)
                    new_comments = st.text_area("Edit Comments", value=row['Comments'])

                    save = st.form_submit_button("Save Changes")
                    if save:
                        update_ticket(sheet_row, new_task, new_domain, new_deadline, new_status, new_comments)
                        st.success("✅ Ticket updated!")
                        del st.session_state[f"edit_{sheet_row}"]
                        st.rerun()

# Chart
st.subheader("📆 Deadlines Overview")
deadline_chart = (
    alt.Chart(df)
    .mark_bar()
    .encode(
        x=alt.X('Deadline:T', title='Deadline'),
        y=alt.Y('count():Q', title='Tickets'),
        color=alt.Color('Status:N'),
        tooltip=['Task', 'Domain', 'Deadline', 'Status']
    )
    .properties(height=300)
)
st.altair_chart(deadline_chart, use_container_width=True)
