import io
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

# ==========================================================
# 1. PAGE CONFIGURATION
# ==========================================================
st.set_page_config(
    page_title="Normal Child Clinic CRM",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Custom CSS for an attractive look ----
st.markdown(
    """
    <style>
    .main { background-color: #f7f9fc; }
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    div[data-testid="stMetricValue"] { color: #1f6feb; font-weight: 700; }
    .card {
        background-color: white;
        padding: 18px 20px;
        border-radius: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07);
        margin-bottom: 14px;
    }
    .badge-new { background:#e0f2fe; color:#0369a1; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
    .badge-treatment { background:#fef9c3; color:#854d0e; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
    .badge-completed { background:#dcfce7; color:#166534; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; }
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
# PASSWORD HASHING HELPERS
# ==========================================================
def make_hashes(password):
    import hashlib

    return hashlib.sha256(str.encode(password)).hexdigest()


def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text


# ==========================================================
# 2. DATABASE INITIALIZATION
# ==========================================================
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # ---- Step 1: If a "leads" table already exists, inspect it. ----
        # Some very old versions of this app used a different schema (e.g. a
        # NOT NULL "name" column) that our INSERT statements don't fill in.
        # SQLite can't drop a NOT NULL constraint via ALTER TABLE, so if we
        # find any column we don't recognize that is NOT NULL, we quarantine
        # the old table (rename it, data preserved) and start fresh.
        known_safe_notnull = {"id", "receiver_name", "child_name", "father_name", "phone"}
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leads'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(leads)")
            table_info = cursor.fetchall()  # (cid, name, type, notnull, dflt_value, pk)
            problematic_cols = [
                row[1] for row in table_info
                if row[3] == 1 and row[4] is None and row[1] not in known_safe_notnull
            ]
            if problematic_cols:
                backup_name = f"leads_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                cursor.execute(f"ALTER TABLE leads RENAME TO {backup_name}")

        # ---- Step 2: Create a fresh table with the current schema if needed. ----
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receiver_name TEXT NOT NULL,
                child_name TEXT NOT NULL,
                father_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                condition TEXT,
                city TEXT,
                visit_date TEXT,
                followup_date TEXT,
                notes TEXT,
                status TEXT,
                created_at TEXT,
                fee_amount REAL,
                doctor_name TEXT
            )
            """
        )

        # ---- Step 3: Ensure every column the app needs exists (covers tables ----
        # that had the right NOT NULL columns but were just missing newer ones).
        required_columns = {
            "receiver_name": "TEXT",
            "child_name": "TEXT",
            "father_name": "TEXT",
            "phone": "TEXT",
            "condition": "TEXT",
            "city": "TEXT",
            "visit_date": "TEXT",
            "followup_date": "TEXT",
            "notes": "TEXT",
            "status": "TEXT",
            "created_at": "TEXT",
            "fee_amount": "REAL",
            "doctor_name": "TEXT",
        }
        cursor.execute("PRAGMA table_info(leads)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        for col_name, col_type in required_columns.items():
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")

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
# 3. SESSION STATE
# ==========================================================
for key, default in {
    "logged_in": False,
    "username": "",
    "user_role": "",
    "user_name": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ==========================================================
# AUTH HELPERS
# ==========================================================
def login_user(username, password):
    hashed_pswd = make_hashes(password)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username, name, role FROM users WHERE username=? AND password=?",
            (username, hashed_pswd),
        )
        return cursor.fetchone()


def add_user(username, password, name, role):
    hashed_pswd = make_hashes(password)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users(username, password, name, role) VALUES (?,?,?,?)",
                (username, hashed_pswd, name, role),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def status_badge(status):
    cls = {
        "New Lead": "badge-new",
        "In Treatment": "badge-treatment",
        "Completed": "badge-completed",
    }.get(status, "badge-new")
    return f'<span class="{cls}">{status}</span>'


def clean_phone_for_link(phone, default_country_code="91"):
    """Normalize a phone number into a digits-only string suitable for wa.me / tel: links."""
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if len(digits) == 10:
        digits = default_country_code + digits
    return digits


def whatsapp_link(phone, message=""):
    digits = clean_phone_for_link(phone)
    if not digits:
        return None
    from urllib.parse import quote

    return f"https://wa.me/{digits}" + (f"?text={quote(message)}" if message else "")


def call_link(phone):
    digits = clean_phone_for_link(phone)
    return f"tel:+{digits}" if digits else None


# ==========================================================
# 🔐 AUTH SCREEN
# ==========================================================
if not st.session_state["logged_in"]:
    _, col_center, _ = st.columns([1, 1.2, 1])

    with col_center:
        st.markdown(
            "<h1 style='text-align:center;'>🏥 Normal Child Clinic</h1>"
            "<h4 style='text-align:center; color:#555;'>CRM Portal</h4>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        auth_tab1, auth_tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])

        with auth_tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                login_btn = st.form_submit_button("Login Karein", use_container_width=True)

                if login_btn:
                    result = login_user(username, password)
                    if result:
                        st.session_state["logged_in"] = True
                        st.session_state["username"] = result[0]
                        st.session_state["user_name"] = result[1]
                        st.session_state["user_role"] = result[2]
                        st.success(f"Swagat hai, {result[1]}!")
                        st.rerun()
                    else:
                        st.error("Galat Username ya Password!")

        with auth_tab2:
            with st.form("signup_form"):
                new_name = st.text_input("Pura Naam")
                new_username = st.text_input("Username")
                new_password = st.text_input("Password", type="password")
                new_role = st.selectbox("Role Chunein", ["Staff / Receiver", "HR Admin"])
                signup_btn = st.form_submit_button("Account Banayein", use_container_width=True)

                if signup_btn:
                    if new_name and new_username and new_password:
                        success = add_user(new_username, new_password, new_name, new_role)
                        if success:
                            st.success("Account ban gaya hai! Ab login karein.")
                        else:
                            st.error("Username pehle se maujood hai.")
                    else:
                        st.warning("Kripya sabhi jaankari bharein.")

# ==========================================================
# 🏥 MAIN APP
# ==========================================================
else:
    # ---------- SIDEBAR ----------
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    st.sidebar.caption(f"🏷️ {st.session_state['user_role']}")

    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["user_role"] = ""
        st.session_state["user_name"] = ""
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("➕ Nayi Entry Jodein")

    with st.sidebar.form("entry_form", clear_on_submit=True):
        receiver_name = st.text_input("Call Receiver ka Naam *", value=st.session_state["user_name"])
        child_name = st.text_input("Bachche ka Naam *")
        father_name = st.text_input("Pita ka Naam")
        phone = st.text_input("Mobile Number *")
        condition = st.selectbox("Condition Chunein", CONDITIONS)
        city = st.text_input("City (Shehar)")
        doctor_name = st.text_input("Doctor ka Naam")
        visit_date = st.date_input("Clinic Aane ki Date", value=datetime.today())
        followup_date = st.date_input("Agli Follow-up Date", value=datetime.today() + timedelta(days=7))
        notes = st.text_area("Doctor/Clinic Notes (Khaas baatein)")
        status = st.selectbox("Status", STATUSES)
        fee_amount = st.number_input("Fee Amount (₹)", min_value=0.0, step=100.0, value=0.0)

        submit_button = st.form_submit_button("💾 Record Save Karein", use_container_width=True)

        if submit_button:
            if receiver_name and child_name and phone:
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO leads
                        (receiver_name, child_name, father_name, phone, condition, city,
                         visit_date, followup_date, notes, status, created_at, fee_amount, doctor_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            receiver_name, child_name, father_name, phone, condition, city,
                            str(visit_date), str(followup_date), notes, status,
                            datetime.now().isoformat(timespec="seconds"), fee_amount, doctor_name,
                        ),
                    )
                    conn.commit()
                st.sidebar.success("Record safalpurvak save ho gaya!")
                st.rerun()
            else:
                st.sidebar.error("Kripya Receiver ka Naam, Bachche ka Naam aur Phone Number bharein.")

    # ---------- LOAD DATA ----------
    EXPECTED_COLUMNS = [
        "id", "receiver_name", "child_name", "father_name", "phone", "condition",
        "city", "visit_date", "followup_date", "notes", "status", "created_at", "fee_amount",
        "doctor_name",
    ]
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql("SELECT * FROM leads ORDER BY id DESC", conn)
        except Exception:
            df = pd.DataFrame(columns=EXPECTED_COLUMNS)

    # Safety net: guarantee every expected column exists even on old/partial DBs
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = None

    today_str = str(datetime.today().date())
    tomorrow_str = str((datetime.today() + timedelta(days=1)).date())

    st.title("🏥 Normal Child Clinic — CRM Dashboard")
    st.caption(f"Aaj: {datetime.today().strftime('%d %B %Y')}")

    # ---------- TODAY'S ALERT BANNER (MVP feature) ----------
    if not df.empty:
        due_today = df[df["followup_date"] == today_str]
        due_tomorrow = df[df["followup_date"] == tomorrow_str]
        if not due_today.empty:
            names = ", ".join(due_today["child_name"].head(5).tolist())
            st.warning(f"📞 Aaj {len(due_today)} follow-up(s) due hain: {names}{' ...' if len(due_today) > 5 else ''}")
        if not due_tomorrow.empty:
            st.info(f"🔔 Kal {len(due_tomorrow)} follow-up(s) due honge — abhi se taiyaari karein.")

    st.markdown("---")

    # ==========================================================
    # ROLE-BASED VIEW
    # ==========================================================
    if st.session_state["user_role"] == "HR Admin":
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            [
                "📋 Dashboard",
                "🧒 Patient Profile",
                "✏️ Edit Record",
                "📊 Reports & Analytics",
                "📅 Follow-up Tracker",
                "🗑️ Delete Record",
            ]
        )

        # -------- TAB 1: DASHBOARD --------
        with tab1:
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            total_leads = len(df)
            today_visits = len(df[df["visit_date"] == today_str]) if not df.empty else 0
            today_followups = len(df[df["followup_date"] == today_str]) if not df.empty else 0
            in_treatment = len(df[df["status"] == "In Treatment"]) if not df.empty else 0
            new_leads = len(df[df["status"] == "New Lead"]) if not df.empty else 0
            total_revenue = df["fee_amount"].fillna(0).sum() if not df.empty and "fee_amount" in df.columns else 0

            m1.metric("Total Patients", total_leads)
            m2.metric("Aaj ke Visits", today_visits)
            m3.metric("Aaj ke Follow-ups", today_followups)
            m4.metric("In Treatment", in_treatment)
            m5.metric("New Leads", new_leads)
            m6.metric("Total Revenue", f"₹{total_revenue:,.0f}")

            st.markdown("###")

            if not df.empty:
                chart_col1, chart_col2 = st.columns(2)
                with chart_col1:
                    st.markdown("#### 🩺 Condition-wise Distribution")
                    cond_counts = df["condition"].value_counts().reset_index()
                    cond_counts.columns = ["Condition", "Count"]
                    fig1 = px.pie(cond_counts, names="Condition", values="Count", hole=0.45)
                    fig1.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320)
                    st.plotly_chart(fig1, use_container_width=True)

                with chart_col2:
                    st.markdown("#### 📈 Status Overview")
                    status_counts = df["status"].value_counts().reset_index()
                    status_counts.columns = ["Status", "Count"]
                    fig2 = px.bar(status_counts, x="Status", y="Count", color="Status", text="Count")
                    fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320, showlegend=False)
                    st.plotly_chart(fig2, use_container_width=True)

                st.markdown("#### 📅 Visits Trend (Last 30 Days)")
                trend_df = df.copy()
                trend_df["visit_date"] = pd.to_datetime(trend_df["visit_date"], errors="coerce")
                cutoff = datetime.today() - timedelta(days=30)
                trend_df = trend_df[trend_df["visit_date"] >= cutoff]
                if not trend_df.empty:
                    daily_counts = trend_df.groupby(trend_df["visit_date"].dt.date).size().reset_index(name="Visits")
                    fig3 = px.line(daily_counts, x="visit_date", y="Visits", markers=True)
                    fig3.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
                    st.plotly_chart(fig3, use_container_width=True)
                else:
                    st.info("Pichle 30 dinon mein koi visit data nahi hai.")

                st.markdown("#### 💰 Monthly Revenue")
                rev_df = df.copy()
                rev_df["visit_date"] = pd.to_datetime(rev_df["visit_date"], errors="coerce")
                rev_df["fee_amount"] = rev_df["fee_amount"].fillna(0)
                rev_df = rev_df.dropna(subset=["visit_date"])
                if not rev_df.empty and rev_df["fee_amount"].sum() > 0:
                    rev_df["month"] = rev_df["visit_date"].dt.to_period("M").astype(str)
                    monthly_rev = rev_df.groupby("month")["fee_amount"].sum().reset_index()
                    fig5 = px.bar(monthly_rev, x="month", y="fee_amount", text_auto=".2s")
                    fig5.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280, yaxis_title="Revenue (₹)")
                    st.plotly_chart(fig5, use_container_width=True)
                else:
                    st.info("Abhi tak koi fee data record nahi hua hai.")

                st.markdown("---")
                col_search, col_csv, col_excel = st.columns([2, 1, 1])
                with col_search:
                    search_query = st.text_input("🔍 Search (Naam, Phone, City, ya Receiver se):")
                with col_csv:
                    st.markdown("###")
                    csv_data = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "📄 Export CSV", data=csv_data,
                        file_name=f"clinic_leads_{today_str}.csv", mime="text/csv",
                        use_container_width=True,
                    )
                with col_excel:
                    st.markdown("###")
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                        df.to_excel(writer, index=False, sheet_name="Patients_Data")
                    st.download_button(
                        "📊 Export Excel", data=buffer.getvalue(),
                        file_name=f"clinic_leads_{today_str}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

                filtered_df = df.copy()
                if search_query:
                    filtered_df = df[
                        df["child_name"].str.contains(search_query, case=False, na=False)
                        | df["phone"].str.contains(search_query, case=False, na=False)
                        | df["city"].str.contains(search_query, case=False, na=False)
                        | df["receiver_name"].str.contains(search_query, case=False, na=False)
                    ]

                st.markdown("#### 📋 Patient Records")
                st.dataframe(filtered_df, use_container_width=True, height=350)

                st.markdown("#### 🧑‍💼 Call Receiver Performance")
                receiver_counts = df["receiver_name"].value_counts().reset_index()
                receiver_counts.columns = ["Receiver Naam", "Kul Entries"]
                fig4 = px.bar(receiver_counts, x="Receiver Naam", y="Kul Entries", text="Kul Entries")
                fig4.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("Abhi tak koi record nahi hai. Sidebar se entry add karein.")

        # -------- TAB 2: PATIENT PROFILE (360 view, new MVP feature) --------
        with tab2:
            st.subheader("🧒 Patient Profile — 360° View")
            if not df.empty:
                profile_options = {
                    f"ID {row['id']} - {row['child_name']} ({row['phone']})": row["id"]
                    for _, row in df.iterrows()
                }
                selected_profile_label = st.selectbox("Patient chunein:", list(profile_options.keys()), key="profile_select")
                p_id = profile_options[selected_profile_label]
                p = df[df["id"] == p_id].iloc[0]

                fee_val = p["fee_amount"] if pd.notna(p.get("fee_amount")) else 0

                col_info, col_actions = st.columns([2.5, 1])
                with col_info:
                    st.markdown(
                        f"""
                        <div class="card">
                            <h3>{p['child_name']} {status_badge(p['status'])}</h3>
                            <b>Pita ka Naam:</b> {p['father_name'] or '—'}<br>
                            <b>Phone:</b> {p['phone']} &nbsp; | &nbsp; <b>City:</b> {p['city'] or '—'}<br>
                            <b>Condition:</b> {p['condition'] or '—'}<br>
                            <b>Clinic Visit Date:</b> {p['visit_date']} &nbsp; | &nbsp; <b>Follow-up Date:</b> {p['followup_date']}<br>
                            <b>Fee Paid:</b> ₹{fee_val:,.0f}<br>
                            <b>Call Receiver:</b> {p['receiver_name']}<br>
                            <b>Notes:</b> {p['notes'] or '—'}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with col_actions:
                    st.markdown("#### Quick Actions")
                    wa_url = whatsapp_link(
                        p["phone"],
                        message=f"Namaste, {p['child_name']} ke clinic visit/follow-up ke baare mein baat karni thi.",
                    )
                    tel_url = call_link(p["phone"])
                    if wa_url:
                        st.link_button("💬 WhatsApp Karein", wa_url, use_container_width=True)
                    if tel_url:
                        st.link_button("📞 Call Karein", tel_url, use_container_width=True)

                    # Quick status update without opening the Edit tab
                    with st.form(f"quick_status_{p_id}"):
                        new_status = st.selectbox(
                            "Status Update Karein",
                            STATUSES,
                            index=STATUSES.index(p["status"]) if p["status"] in STATUSES else 0,
                        )
                        quick_update = st.form_submit_button("💾 Update", use_container_width=True)
                        if quick_update:
                            with sqlite3.connect(DB_PATH) as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE leads SET status=? WHERE id=?", (new_status, p_id))
                                conn.commit()
                            st.success("Status update ho gaya!")
                            st.rerun()

                st.markdown("---")
                st.markdown("#### 📜 Is Receiver ke Baaki Patients")
                same_receiver = df[
                    (df["receiver_name"] == p["receiver_name"]) & (df["id"] != p_id)
                ]
                if not same_receiver.empty:
                    st.dataframe(
                        same_receiver[["id", "child_name", "phone", "status", "followup_date"]],
                        use_container_width=True,
                        height=200,
                    )
                else:
                    st.info("Is receiver ke paas koi aur patient record nahi hai.")
            else:
                st.info("Abhi tak koi record nahi hai. Sidebar se entry add karein.")

        # -------- TAB 3: EDIT RECORD --------
        with tab3:
            st.subheader("✏️ Existing Patient Record Update Karein")
            if not df.empty:
                patient_options = {
                    f"ID {row['id']} - {row['child_name']} ({row['phone']})": row["id"]
                    for _, row in df.iterrows()
                }
                selected_patient_label = st.selectbox("Update karne ke liye Patient chunein:", list(patient_options.keys()))
                selected_id = patient_options[selected_patient_label]
                patient_data = df[df["id"] == selected_id].iloc[0]

                with st.form("edit_form"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        e_receiver_name = st.text_input("Call Receiver", value=patient_data["receiver_name"])
                        e_child_name = st.text_input("Bachche ka Naam", value=patient_data["child_name"])
                        e_father_name = st.text_input("Pita ka Naam", value=patient_data["father_name"])
                        e_phone = st.text_input("Mobile Number", value=patient_data["phone"])
                        e_city = st.text_input("City", value=patient_data["city"])
                        e_doctor_name = st.text_input(
                            "Doctor ka Naam",
                            value=patient_data["doctor_name"] if pd.notna(patient_data.get("doctor_name")) else "",
                        )

                    with e_col2:
                        cond_idx = CONDITIONS.index(patient_data["condition"]) if patient_data["condition"] in CONDITIONS else 0
                        e_condition = st.selectbox("Condition", CONDITIONS, index=cond_idx)

                        try:
                            v_date = datetime.strptime(patient_data["visit_date"], "%Y-%m-%d").date()
                        except Exception:
                            v_date = datetime.today().date()
                        try:
                            f_date = datetime.strptime(patient_data["followup_date"], "%Y-%m-%d").date()
                        except Exception:
                            f_date = datetime.today().date()

                        e_visit_date = st.date_input("Clinic Visit Date", value=v_date)
                        e_followup_date = st.date_input("Agli Follow-up Date", value=f_date)

                        status_idx = STATUSES.index(patient_data["status"]) if patient_data["status"] in STATUSES else 0
                        e_status = st.selectbox("Status", STATUSES, index=status_idx)

                    e_notes = st.text_area("Doctor/Clinic Notes", value=patient_data["notes"])
                    e_fee = st.number_input(
                        "Fee Amount (₹)",
                        min_value=0.0,
                        step=100.0,
                        value=float(patient_data["fee_amount"]) if pd.notna(patient_data.get("fee_amount")) else 0.0,
                    )
                    update_button = st.form_submit_button("💾 Record Update Karein")

                    if update_button:
                        with sqlite3.connect(DB_PATH) as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                UPDATE leads
                                SET receiver_name=?, child_name=?, father_name=?, phone=?,
                                    condition=?, city=?, visit_date=?, followup_date=?, notes=?, status=?, fee_amount=?, doctor_name=?
                                WHERE id=?
                                """,
                                (
                                    e_receiver_name, e_child_name, e_father_name, e_phone,
                                    e_condition, e_city, str(e_visit_date), str(e_followup_date),
                                    e_notes, e_status, e_fee, e_doctor_name, selected_id,
                                ),
                            )
                            conn.commit()
                        st.success(f"ID {selected_id} ka record update ho gaya hai!")
                        st.rerun()
            else:
                st.info("Update karne ke liye koi record nahi hai.")

        # -------- TAB 4: REPORTS --------
        with tab4:
            st.subheader("📈 Zaroori Reports aur Analysis")
            if not df.empty:
                rep_col1, rep_col2 = st.columns(2)
                with rep_col1:
                    st.markdown("### 📅 Date-wise Visit Report")
                    selected_visit_date = st.date_input("Clinic Visit Date chunein:", value=datetime.today())
                    v_str = str(selected_visit_date)
                    v_filtered = df[df["visit_date"] == v_str]
                    st.write(f"**Total Patients Scheduled ({v_str}):** {len(v_filtered)}")
                    if not v_filtered.empty:
                        st.dataframe(v_filtered, use_container_width=True)
                    else:
                        st.info("Is tarikh ko koi visit scheduled nahi hai.")

                with rep_col2:
                    st.markdown("### 📞 Follow-up Report")
                    selected_follow_date = st.date_input("Follow-up Date chunein:", value=datetime.today(), key="follow_date_picker")
                    f_str = str(selected_follow_date)
                    f_filtered = df[df["followup_date"] == f_str]
                    st.write(f"**Total Follow-ups Due ({f_str}):** {len(f_filtered)}")
                    if not f_filtered.empty:
                        st.dataframe(f_filtered, use_container_width=True)
                    else:
                        st.info("Is tarikh ko koi follow-up scheduled nahi hai.")

                st.markdown("---")
                st.markdown("### 🏙️ City-wise Report & Analysis")
                city_col1, city_col2 = st.columns([1, 2])
                with city_col1:
                    city_counts = df["city"].value_counts().reset_index()
                    city_counts.columns = ["City", "Kul Bachche"]
                    st.dataframe(city_counts, use_container_width=True)
                with city_col2:
                    cities_list = [str(c) for c in df["city"].dropna().unique() if str(c).strip()]
                    if cities_list:
                        selected_city = st.selectbox("City chunein:", ["Sabhi Cities"] + cities_list)
                        city_filtered_df = df if selected_city == "Sabhi Cities" else df[df["city"] == selected_city]
                        st.dataframe(city_filtered_df, use_container_width=True)
                    else:
                        st.info("City ki koi details nahi mili.")

                st.markdown("---")
                st.markdown("### 🩺 Condition-wise Patient Count")
                condition_counts = df["condition"].value_counts().reset_index()
                condition_counts.columns = ["Condition", "Kul Bachche"]
                st.dataframe(condition_counts, use_container_width=True)

                st.markdown("---")
                st.markdown("### 💰 Revenue Report")
                rev_report_df = df.copy()
                rev_report_df["fee_amount"] = rev_report_df["fee_amount"].fillna(0)
                rev_col1, rev_col2 = st.columns(2)
                with rev_col1:
                    st.write(f"**Total Revenue:** ₹{rev_report_df['fee_amount'].sum():,.0f}")
                    receiver_rev = rev_report_df.groupby("receiver_name")["fee_amount"].sum().reset_index()
                    receiver_rev.columns = ["Receiver", "Total Fee (₹)"]
                    st.dataframe(receiver_rev, use_container_width=True)
                with rev_col2:
                    condition_rev = rev_report_df.groupby("condition")["fee_amount"].sum().reset_index()
                    condition_rev.columns = ["Condition", "Total Fee (₹)"]
                    st.dataframe(condition_rev, use_container_width=True)

                # ---- Monthly Revenue ----
                st.markdown("---")
                st.markdown("### 📆 Monthly Revenue")
                month_rev_df = df.copy()
                month_rev_df["visit_date"] = pd.to_datetime(month_rev_df["visit_date"], errors="coerce")
                month_rev_df["fee_amount"] = month_rev_df["fee_amount"].fillna(0)
                month_rev_df = month_rev_df.dropna(subset=["visit_date"])
                if not month_rev_df.empty and month_rev_df["fee_amount"].sum() > 0:
                    month_rev_df["Month"] = month_rev_df["visit_date"].dt.to_period("M").astype(str)
                    monthly_rev_table = month_rev_df.groupby("Month")["fee_amount"].sum().reset_index()
                    monthly_rev_table.columns = ["Month", "Total Revenue (₹)"]
                    st.dataframe(monthly_rev_table, use_container_width=True)
                    fig_month_rev = px.bar(monthly_rev_table, x="Month", y="Total Revenue (₹)", text_auto=".2s")
                    fig_month_rev.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
                    st.plotly_chart(fig_month_rev, use_container_width=True)
                else:
                    st.info("Abhi tak koi fee data record nahi hua hai.")

                # ---- Doctor-wise Patients ----
                st.markdown("---")
                st.markdown("### 🩺 Doctor-wise Patients")
                doctor_df = df.copy()
                doctor_df["doctor_name"] = doctor_df["doctor_name"].fillna("").astype(str).str.strip()
                doctor_df = doctor_df[doctor_df["doctor_name"] != ""]
                if not doctor_df.empty:
                    doctor_counts = doctor_df["doctor_name"].value_counts().reset_index()
                    doctor_counts.columns = ["Doctor", "Kul Patients"]
                    dr_col1, dr_col2 = st.columns(2)
                    with dr_col1:
                        st.dataframe(doctor_counts, use_container_width=True)
                    with dr_col2:
                        fig_doc = px.bar(doctor_counts, x="Doctor", y="Kul Patients", text="Kul Patients")
                        fig_doc.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
                        st.plotly_chart(fig_doc, use_container_width=True)
                else:
                    st.info("Abhi tak koi doctor ka naam record nahi hua hai.")

                # ---- Receiver-wise Conversion ----
                st.markdown("---")
                st.markdown("### 🧑‍💼 Receiver-wise Conversion")
                conv_df = df.copy()
                conv_total = conv_df.groupby("receiver_name").size().reset_index(name="Total Leads")
                conv_converted = (
                    conv_df[conv_df["status"].isin(["In Treatment", "Completed"])]
                    .groupby("receiver_name")
                    .size()
                    .reset_index(name="Converted")
                )
                conv_report = conv_total.merge(conv_converted, on="receiver_name", how="left")
                conv_report["Converted"] = conv_report["Converted"].fillna(0).astype(int)
                conv_report["Conversion Rate (%)"] = (
                    (conv_report["Converted"] / conv_report["Total Leads"] * 100).round(1)
                )
                conv_report.columns = ["Receiver", "Total Leads", "Converted", "Conversion Rate (%)"]
                st.dataframe(conv_report, use_container_width=True)

                # ---- City-wise Revenue ----
                st.markdown("---")
                st.markdown("### 🏙️ City-wise Revenue")
                city_rev_df = df.copy()
                city_rev_df["fee_amount"] = city_rev_df["fee_amount"].fillna(0)
                city_rev_table = city_rev_df.groupby("city")["fee_amount"].sum().reset_index()
                city_rev_table.columns = ["City", "Total Revenue (₹)"]
                city_rev_table = city_rev_table.sort_values("Total Revenue (₹)", ascending=False)
                cr_col1, cr_col2 = st.columns(2)
                with cr_col1:
                    st.dataframe(city_rev_table, use_container_width=True)
                with cr_col2:
                    if city_rev_table["Total Revenue (₹)"].sum() > 0:
                        fig_city_rev = px.bar(city_rev_table, x="City", y="Total Revenue (₹)", text_auto=".2s")
                        fig_city_rev.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
                        st.plotly_chart(fig_city_rev, use_container_width=True)
                    else:
                        st.info("Abhi tak koi fee data record nahi hua hai.")

                # ---- Follow-up Missed Report ----
                st.markdown("---")
                st.markdown("### ⚠️ Follow-up Missed Report")
                missed_df = df.copy()
                missed_df["followup_date"] = pd.to_datetime(missed_df["followup_date"], errors="coerce")
                missed_df = missed_df[
                    (missed_df["followup_date"].dt.date < datetime.today().date())
                    & (missed_df["status"] != "Completed")
                ]
                missed_df = missed_df.sort_values("followup_date")
                if not missed_df.empty:
                    st.write(f"**Total Missed Follow-ups:** {len(missed_df)}")
                    st.dataframe(
                        missed_df[["id", "child_name", "phone", "city", "followup_date", "status", "receiver_name"]],
                        use_container_width=True,
                    )
                else:
                    st.success("Koi bhi follow-up miss nahi hua hai. 🎉")
            else:
                st.info("Reports dekhne ke liye pehle records save karein.")

        # -------- TAB 5: FOLLOW-UP TRACKER --------
        with tab5:
            st.subheader("📅 Follow-up Tracker")
            if not df.empty:
                upcoming = df.copy()
                upcoming["followup_date"] = pd.to_datetime(upcoming["followup_date"], errors="coerce")
                upcoming = upcoming[upcoming["status"] != "Completed"]
                upcoming = upcoming.sort_values("followup_date")
                horizon = st.slider("Aane wale kitne dinon ka data dikhaayein?", 1, 30, 7)
                cutoff = datetime.today() + timedelta(days=horizon)
                upcoming = upcoming[upcoming["followup_date"] <= cutoff]

                if not upcoming.empty:
                    for _, row in upcoming.iterrows():
                        f_date = row["followup_date"]
                        overdue = f_date.date() < datetime.today().date() if pd.notna(f_date) else False
                        date_label = f_date.strftime("%d %b %Y") if pd.notna(f_date) else "N/A"
                        card_col, action_col1, action_col2 = st.columns([5, 1, 1])
                        with card_col:
                            st.markdown(
                                f"""
                                <div class="card">
                                    <b>{row['child_name']}</b> {status_badge(row['status'])}
                                    {"🔴 <b>OVERDUE</b>" if overdue else ""}<br>
                                    📞 {row['phone']} &nbsp; | &nbsp; 🏙️ {row['city']}<br>
                                    📅 Follow-up: <b>{date_label}</b> &nbsp; | &nbsp; Condition: {row['condition']}<br>
                                    🧑‍💼 Receiver: {row['receiver_name']}
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        wa_url = whatsapp_link(
                            row["phone"],
                            message=f"Namaste, {row['child_name']} ke follow-up ({date_label}) ke baare mein baat karni thi.",
                        )
                        tel_url = call_link(row["phone"])
                        with action_col1:
                            if wa_url:
                                st.link_button("💬 WhatsApp", wa_url, use_container_width=True)
                        with action_col2:
                            if tel_url:
                                st.link_button("📞 Call", tel_url, use_container_width=True)
                else:
                    st.success("Is samay-seema mein koi pending follow-up nahi hai. 🎉")
            else:
                st.info("Koi record nahi hai.")

        # -------- TAB 6: DELETE --------
        with tab6:
            st.subheader("🗑️ Record Delete Karein")
            if not df.empty:
                del_options = {
                    f"ID {row['id']} - {row['child_name']} ({row['phone']})": row["id"]
                    for _, row in df.iterrows()
                }
                selected_del_label = st.selectbox("Delete karne ke liye Record chunein:", list(del_options.keys()))
                delete_id = del_options[selected_del_label]

                if st.button("🚨 Record Hatayein", type="primary"):
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM leads WHERE id = ?", (delete_id,))
                        conn.commit()
                    st.success(f"ID {delete_id} ka record delete kar diya gaya hai.")
                    st.rerun()
            else:
                st.info("Delete karne ke liye koi record uplabdh nahi hai.")

    # ==========================================================
    # STAFF / CALL RECEIVER VIEW (LIMITED ACCESS)
    # ==========================================================
    else:
        st.subheader("📋 Patients List (Staff View)")
        st.info(
            "💡 Aap nayi entries sidebar me form bhar kar save kar sakte hain. "
            "Advanced reports aur administrative control sirf HR Admin ke paas hain."
        )

        if not df.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Aaj ke Visits", len(df[df["visit_date"] == today_str]))
            m2.metric("Aaj ke Follow-ups", len(df[df["followup_date"] == today_str]))
            m3.metric("Mere Entries", len(df[df["receiver_name"] == st.session_state["user_name"]]))

            search_query = st.text_input("🔍 Search (Bachche ka Naam ya Phone number se):")
            filtered_df = df.copy()
            if search_query:
                filtered_df = df[
                    df["child_name"].str.contains(search_query, case=False, na=False)
                    | df["phone"].str.contains(search_query, case=False, na=False)
                ]
            st.dataframe(filtered_df, use_container_width=True, height=400)
        else:
            st.info("Abhi tak koi record nahi hai. Sidebar se entry add karein.")
