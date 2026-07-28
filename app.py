import io
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import streamlit as st

# ==========================================================
# 1. PAGE CONFIGURATION & STYLING
# ==========================================================
st.set_page_config(
    page_title="Normal Child Clinic CRM",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .metric-card {
        background-color: #ffffff !important;
        padding: 16px 20px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1) !important;
        border: 1px solid #cbd5e1 !important;
        text-align: left !important;
        margin-bottom: 15px !important;
    }
    .metric-label {
        color: #334155 !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        margin-bottom: 6px !important;
        display: block !important;
    }
    .metric-value {
        color: #1d4ed8 !important;
        font-weight: 800 !important;
        font-size: 28px !important;
        line-height: 1.2 !important;
        margin: 0 !important;
    }
    .badge-new { background:#e0f2fe !important; color:#0369a1 !important; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
    .badge-treatment { background:#fef9c3 !important; color:#854d0e !important; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
    .badge-completed { background:#dcfce7 !important; color:#166534 !important; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
    .badge-risk { background:#fee2e2 !important; color:#991b1b !important; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
    </style>
    """,
    unsafe_allow_html=True,
)

DB_PATH = "crm.db"
CONDITIONS = [
    "Autism (ASD)",
    "ADHD",
    "Learning Disability",
    "Speech Delay",
    "Intellectual Disability",
    "Down Syndrome",
    "Cerebral Palsy",
    "Other",
]
STATUSES = ["New Lead", "In Treatment", "Completed"]

# ==========================================================
# HELPERS
# ==========================================================
def make_hashes(password):
    import hashlib
    return hashlib.sha256(str.encode(password)).hexdigest()

def clean_phone_for_link(phone, default_country_code="91"):
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if len(digits) == 10:
        digits = default_country_code + digits
    return digits

def whatsapp_link(phone, message=""):
    digits = clean_phone_for_link(phone)
    if not digits:
        return None
    return f"https://wa.me/{digits}" + (f"?text={quote(message)}" if message else "")

# ==========================================================
# 2. DATABASE INITIALIZATION
# ==========================================================
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receiver_name TEXT NOT NULL,
                child_name TEXT NOT NULL,
                father_name TEXT,
                phone TEXT NOT NULL,
                condition TEXT,
                city TEXT,
                visit_date TEXT,
                followup_date TEXT,
                notes TEXT,
                status TEXT,
                created_at TEXT,
                fee_amount REAL,
                doctor_name TEXT,
                dob TEXT
            )
            """
        )
        
        cursor.execute("PRAGMA table_info(leads)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        if "dob" not in existing_cols:
            cursor.execute("ALTER TABLE leads ADD COLUMN dob TEXT")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL
            )
            """
        )

        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            default_pass = make_hashes("admin123")
            cursor.execute(
                "INSERT INTO users (username, password, name, role) VALUES (?, ?, ?, ?)",
                ("admin", default_pass, "HR Admin", "HR Admin"),
            )

        conn.commit()

init_db()

# ==========================================================
# 3. SESSION STATE & AUTH
# ==========================================================
for key, default in {"logged_in": False, "username": "", "user_role": "", "user_name": ""}.items():
    if key not in st.session_state:
        st.session_state[key] = default

def login_user(username, password):
    hashed_pswd = make_hashes(password)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, name, role FROM users WHERE username=? AND password=?", (username, hashed_pswd))
        return cursor.fetchone()

if not st.session_state["logged_in"]:
    _, col_center, _ = st.columns([1, 1.2, 1])
    with col_center:
        st.markdown("<h1 style='text-align:center;'>🏥 Normal Child Clinic</h1><h4 style='text-align:center; color:#555;'>CRM Portal</h4>", unsafe_allow_html=True)
        st.markdown("---")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login Karein", use_container_width=True):
                result = login_user(username, password)
                if result:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = result[0]
                    st.session_state["user_name"] = result[1]
                    st.session_state["user_role"] = result[2]
                    st.rerun()
                else:
                    st.error("Galat Username ya Password!")

# ==========================================================
# 🏥 MAIN APP
# ==========================================================
else:
    # Sidebar Entry Form
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    st.sidebar.caption(f"🏷️ {st.session_state['user_role']}")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("➕ Nayi Entry Jodein")

    with st.sidebar.form("entry_form", clear_on_submit=True):
        receiver_name = st.text_input("Call Receiver ka Naam *", value=st.session_state["user_name"])
        child_name = st.text_input("Bachche ka Naam *")
        father_name = st.text_input("Pita ka Naam")
        phone = st.text_input("Mobile Number *")
        dob = st.date_input("Bachche ki Date of Birth (DOB)", value=None)
        condition = st.selectbox("Condition Chunein", CONDITIONS)
        city = st.text_input("City (Shehar)")
        doctor_name = st.text_input("Doctor ka Naam")
        visit_date = st.date_input("Clinic Aane ki Date", value=datetime.today())
        followup_date = st.date_input("Agli Follow-up Date", value=datetime.today() + timedelta(days=7))
        notes = st.text_area("Doctor/Clinic Notes")
        status = st.selectbox("Status", STATUSES)
        fee_amount = st.number_input("Fee Amount (₹)", min_value=0.0, step=100.0, value=0.0)

        if st.form_submit_button("💾 Record Save Karein", use_container_width=True):
            if receiver_name and child_name and phone:
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO leads
                        (receiver_name, child_name, father_name, phone, condition, city,
                         visit_date, followup_date, notes, status, created_at, fee_amount, doctor_name, dob)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (receiver_name, child_name, father_name, phone, condition, city, str(visit_date), str(followup_date), notes, status, datetime.now().isoformat(timespec="seconds"), fee_amount, doctor_name, str(dob) if dob else None),
                    )
                    conn.commit()
                st.sidebar.success("Record save ho gaya!")
                st.rerun()

    # Data Load
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT * FROM leads ORDER BY id DESC", conn)

    today_dt = datetime.today().date()
    today_str = str(today_dt)

    st.title("🏥 Normal Child Clinic — CRM Dashboard")
    st.caption(f"Aaj: {datetime.today().strftime('%d %B %Y')}")

    # Navigation Tabs
    tab_dashboard, tab_reports = st.tabs(["📋 Main Dashboard & Action Panel", "📊 Analytics & Advanced Reports"])

    # ==========================================================
    # TAB 1: DASHBOARD & QUICK ACTIONS
    # ==========================================================
    with tab_dashboard:
        if not df.empty:
            df["followup_dt"] = pd.to_datetime(df["followup_date"], errors="coerce").dt.date
            
            # OVERDUE RED ALERT
            overdue_df = df[df["followup_dt"] < today_dt]
            if not overdue_df.empty:
                st.error(f"🚨 **OVERDUE ALERT:** {len(overdue_df)} Patients ke follow-ups choot gaye hain!")

            # BIRTHDAY ALERT
            if "dob" in df.columns:
                df["dob_clean"] = pd.to_datetime(df["dob"], errors="coerce")
                bday_today = df[(df["dob_clean"].dt.month == today_dt.month) & (df["dob_clean"].dt.day == today_dt.day)]
                if not bday_today.empty:
                    st.balloons()
                    st.info(f"🎈 **HAPPY BIRTHDAY!** Aaj {len(bday_today)} child(ren) ka birthday hai!")
                    for _, b_row in bday_today.iterrows():
                        b_msg = f"Normal Child Clinic ki taraf se {b_row['child_name']} ko Janamdin ki bohot bohot shubhkamnayein! 🎂🎉"
                        b_url = whatsapp_link(b_row['phone'], b_msg)
                        c_b1, c_b2 = st.columns([3, 1])
                        c_b1.write(f"🎂 **{b_row['child_name']}** (Pita: {b_row['father_name'] or '—'})")
                        if b_url:
                            c_b2.link_button("🎉 Send Wish", b_url, use_container_width=True)

            # DROPOUT RISK ALERT
            thirty_days_ago = today_dt - timedelta(days=30)
            dropout_df = df[
                (df["status"] != "Completed") & 
                (df["followup_dt"].notna()) & 
                (df["followup_dt"] < thirty_days_ago)
            ]

            if not dropout_df.empty:
                st.warning(f"⚠️ **DROP-OUT RISK ALERT:** {len(dropout_df)} patients 30+ dino se inactive hain!")

        st.markdown("---")

        # DROPOUT RECOVERY EXPANDER
        if not df.empty and not dropout_df.empty:
            with st.expander("🚨 View & Re-engage Drop-out Risk Patients (30+ Days Inactive)", expanded=False):
                for _, d_row in dropout_df.iterrows():
                    col_d1, col_d2, col_d3 = st.columns([2.5, 2, 1.5])
                    with col_d1:
                        st.markdown(f"**🧒 {d_row['child_name']}** <span class='badge-risk'>Lapsed Patient</span>", unsafe_allow_html=True)
                        st.caption(f"📱 {d_row['phone']} | 📍 {d_row['city'] or 'N/A'}")
                    with col_d2:
                        st.markdown(f"🩺 **Condition:** {d_row['condition']}")
                        st.caption(f"🗓️ Last Follow-up Due: **{d_row['followup_date']}**")
                    with col_d3:
                        re_engage_msg = f"Namaste {d_row['father_name'] or ''} ji, Normal Child Clinic se doctor ka message hai. Humne notice kiya ki {d_row['child_name']} ki regular sessions beech me ruk gayi hain. Treatment continuous rakhne se hi behtar improvement aati hai. Kripya humse contact karke agli visit schedule karein."
                        re_wa_url = whatsapp_link(d_row["phone"], re_engage_msg)
                        if re_wa_url:
                            st.link_button("🔄 Re-engage WhatsApp", re_wa_url, use_container_width=True)
                    st.divider()

        # ACTION PANEL
        st.markdown("### 💬 Quick Follow-up Action Panel")
        template_option = st.selectbox(
            "📱 WhatsApp Message Template Chunein:",
            ["General Follow-up", "Appointment Reminder", "Reports Ready", "Custom Message"]
        )

        due_today_list = df[df["followup_date"] == today_str] if not df.empty else pd.DataFrame()

        if not due_today_list.empty:
            for idx, p_row in due_today_list.iterrows():
                if template_option == "General Follow-up":
                    msg = f"Namaste {p_row['father_name'] or ''} ji, Normal Child Clinic se follow-up call/msg hai. Bachche {p_row['child_name']} ki health kaisi hai?"
                elif template_option == "Appointment Reminder":
                    msg = f"Namaste {p_row['father_name'] or ''} ji, Reminding about {p_row['child_name']}'s visit scheduled at Normal Child Clinic."
                elif template_option == "Reports Ready":
                    msg = f"Namaste, {p_row['child_name']} ki clinic reports ready hain. Kripya clinic se collect kar lein."
                else:
                    msg = f"Namaste {p_row['father_name'] or ''} ji, Normal Child Clinic se contact kar rahe hain."

                wa_btn_url = whatsapp_link(p_row["phone"], msg)

                col_p1, col_p2, col_p3 = st.columns([2, 2, 1.5])
                with col_p1:
                    st.markdown(f"**🧒 {p_row['child_name']}** (Pita: {p_row['father_name'] or '—'})")
                    st.caption(f"📱 {p_row['phone']} | 📍 {p_row['city'] or 'N/A'}")
                
                with col_p2:
                    st.caption(f"📝 Current Note: {p_row['notes'] or 'N/A'}")
                    new_quick_note = st.text_input("Naya Remark likhein:", key=f"note_input_{p_row['id']}", placeholder="+ Add note...")
                    if st.button("Save Note", key=f"save_note_{p_row['id']}"):
                        updated_note = (p_row['notes'] or "") + f" | [{today_str}]: " + new_quick_note
                        with sqlite3.connect(DB_PATH) as conn:
                            cursor = conn.cursor()
                            cursor.execute("UPDATE leads SET notes=? WHERE id=?", (updated_note, p_row['id']))
                            conn.commit()
                        st.success("Note Saved!")
                        st.rerun()

                with col_p3:
                    if wa_btn_url:
                        st.link_button("💬 WhatsApp", wa_btn_url, use_container_width=True, type="primary")
                st.divider()
        else:
            st.success("🎉 Aaj ke liye koi pending follow-up nahi hai!")

    # ==========================================================
    # TAB 2: ANALYTICS & ADVANCED REPORTS (NEW)
    # ==========================================================
    with tab_reports:
        st.markdown("## 📊 Clinic Analytics & Business Reports")
        
        if df.empty:
            st.info("Pehle kuch records entry karein, phir reports yahan dikhenge.")
        else:
            # Row 1: Condition Distribution & Lead Conversion
            col_rep1, col_rep2 = st.columns(2)

            with col_rep1:
                st.markdown("### 2️⃣ Condition-wise Patient Distribution")
                cond_counts = df["condition"].value_counts().reset_index()
                cond_counts.columns = ["Condition", "Patient Count"]
                fig_cond = px.pie(
                    cond_counts, 
                    names="Condition", 
                    values="Patient Count", 
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_cond.update_layout(margin=dict(t=20, b=20, l=10, r=10))
                st.plotly_chart(fig_cond, use_container_width=True)

            with col_rep2:
                st.markdown("### 3️⃣ Lead Conversion & Status Tracking")
                status_counts = df["status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Count"]
                fig_status = px.bar(
                    status_counts, 
                    x="Status", 
                    y="Count", 
                    color="Status",
                    text_auto=True,
                    color_discrete_map={"New Lead": "#38bdf8", "In Treatment": "#facc15", "Completed": "#4ade80"}
                )
                fig_status.update_layout(showlegend=False, margin=dict(t=20, b=20, l=10, r=10))
                st.plotly_chart(fig_status, use_container_width=True)

            st.markdown("---")

            # Row 2: Doctor/Staff Performance & Location Density
            col_rep3, col_rep4 = st.columns(2)

            with col_rep3:
                st.markdown("### 4️⃣ Doctor & Staff Workload Summary")
                st.caption("Patients assigned per Doctor")
                doc_summary = df["doctor_name"].fillna("Unassigned").value_counts().reset_index()
                doc_summary.columns = ["Doctor Name", "Total Patients"]
                st.dataframe(doc_summary, use_container_width=True, hide_index=True)

                st.caption("Entries made by Receiver/Staff")
                rec_summary = df["receiver_name"].value_counts().reset_index()
                rec_summary.columns = ["Staff/Receiver Name", "Entries Handled"]
                st.dataframe(rec_summary, use_container_width=True, hide_index=True)

            with col_rep4:
                st.markdown("### 5️⃣ City / Location Density Report")
                city_counts = df["city"].fillna("Unknown").value_counts().reset_index()
                city_counts.columns = ["City", "Patient Count"]
                fig_city = px.bar(
                    city_counts, 
                    x="City", 
                    y="Patient Count", 
                    color_discrete_sequence=["#818cf8"],
                    text_auto=True
                )
                fig_city.update_layout(margin=dict(t=20, b=20, l=10, r=10))
                st.plotly_chart(fig_city, use_container_width=True)
