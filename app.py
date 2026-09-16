import hashlib
import hmac
import io
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import quote

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

# ---- Custom CSS for Dark & Light Mode Compatibility ----
st.markdown(
    """
    <style>
    /* Metric Card Custom HTML Fix */
    .metric-card {
        background-color: #ffffff !important;
        padding: 16px 20px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2) !important;
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
        -webkit-text-fill-color: #334155 !important;
    }
    .metric-value {
        color: #1d4ed8 !important;
        font-weight: 800 !important;
        font-size: 28px !important;
        line-height: 1.2 !important;
        margin: 0 !important;
        -webkit-text-fill-color: #1d4ed8 !important;
    }

    /* Custom Card Fix for Patient Profile */
    .card {
        background-color: #ffffff !important;
        color: #0f172a !important;
        padding: 18px 20px !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2) !important;
        margin-bottom: 14px !important;
        border: 1px solid #cbd5e1 !important;
    }
    .card h3, .card b, .card span, .card div, .card p {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }

    /* Action Box for Quick WhatsApp Followup */
    .action-box {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-left: 5px solid #22c55e !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        margin-bottom: 10px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
    }

    /* Status Badges */
    .badge-new { background:#e0f2fe !important; color:#0369a1 !important; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
    .badge-treatment { background:#fef9c3 !important; color:#854d0e !important; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
    .badge-completed { background:#dcfce7 !important; color:#166534 !important; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
    .badge-inactive { background:#f1f5f9 !important; color:#475569 !important; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;}
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
SEVERITIES = ["Not Specified", "Mild", "Moderate", "Severe"]
GENDERS = ["Male", "Female", "Other"]
STATUSES = ["New Lead", "In Treatment", "Completed", "Inactive"]
SERVICE_TYPES = [
    "Consultation",
    "Speech Therapy",
    "Occupational Therapy",
    "ABA Therapy",
    "Physiotherapy",
    "Special Education",
    "Psychological Assessment",
    "Follow-up Review",
    "Other",
]
PAYMENT_STATUSES = ["Paid", "Partial", "Pending"]
REFERRAL_SOURCES = [
    "Walk-in",
    "Doctor Referral",
    "School / Teacher",
    "Social Media",
    "Friend / Family Referral",
    "Other",
]
GOAL_CATEGORIES = [
    "Speech & Language",
    "Motor Skills",
    "Cognitive",
    "Behavioral",
    "Social Skills",
    "Academic",
    "Self-Care / Daily Living",
    "Other",
]
GOAL_STATUSES = ["Not Started", "In Progress", "Achieved", "On Hold"]
DOCUMENT_CATEGORIES = [
    "Diagnosis Report",
    "Assessment",
    "Prescription",
    "IEP / School Report",
    "Other",
]
UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

CHILD_COLUMNS = [
    "id",
    "child_name",
    "dob",
    "gender",
    "father_name",
    "mother_name",
    "phone",
    "alt_phone",
    "address",
    "city",
    "conditions",
    "severity",
    "referral_source",
    "status",
    "created_by",
    "created_at",
]
VISIT_COLUMNS = [
    "id",
    "child_id",
    "visit_date",
    "followup_date",
    "service_type",
    "doctor_name",
    "notes",
    "fee_amount",
    "payment_status",
    "created_by",
    "created_at",
]
MERGED_COLUMNS = [
    "visit_id",
    "child_id",
    "visit_date",
    "followup_date",
    "service_type",
    "doctor_name",
    "notes",
    "fee_amount",
    "payment_status",
    "visit_receiver",
    "visit_created_at",
    "child_name",
    "dob",
    "gender",
    "father_name",
    "mother_name",
    "phone",
    "alt_phone",
    "address",
    "city",
    "conditions",
    "severity",
    "referral_source",
    "status",
    "receiver_name",
    "child_created_at",
]


# ==========================================================
# PASSWORD HASHING HELPERS (PBKDF2-HMAC-SHA256, salted)
# ==========================================================
PBKDF2_ITERATIONS = 260_000


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    ).hex()
    return f"{salt}${derived}"


def verify_password(password, stored):
    """Returns True/False. Also transparently supports legacy unsalted
    SHA-256 hashes so existing databases keep working after upgrade."""
    if "$" in stored:
        salt, _ = stored.split("$", 1)
        candidate = hash_password(password, salt)
        return hmac.compare_digest(candidate, stored)
    # Legacy format: plain sha256(password)
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, stored)


def needs_rehash(stored):
    return "$" not in stored


# ==========================================================
# 2. DATABASE INITIALIZATION
# ==========================================================
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS children (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_name TEXT NOT NULL,
                dob TEXT,
                gender TEXT,
                father_name TEXT,
                mother_name TEXT,
                phone TEXT NOT NULL,
                alt_phone TEXT,
                address TEXT,
                city TEXT,
                conditions TEXT,
                severity TEXT,
                referral_source TEXT,
                status TEXT,
                created_by TEXT,
                created_at TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id INTEGER NOT NULL REFERENCES children(id),
                visit_date TEXT,
                followup_date TEXT,
                service_type TEXT,
                doctor_name TEXT,
                notes TEXT,
                fee_amount REAL,
                payment_status TEXT,
                created_by TEXT,
                created_at TEXT
            )
            """
        )

        # One-time migration from the old flat "leads" table: each old row
        # becomes a child profile plus that child's first visit.
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='leads'"
        )
        if cursor.fetchone():
            cursor.execute("SELECT * FROM leads")
            legacy_col_order = [d[0] for d in cursor.description]
            legacy_rows = cursor.fetchall()
            for legacy_row in legacy_rows:
                rec = dict(zip(legacy_col_order, legacy_row))
                created_at = rec.get("created_at") or datetime.now().isoformat(
                    timespec="seconds"
                )
                cursor.execute(
                    """
                    INSERT INTO children
                    (child_name, father_name, phone, city, conditions, status, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rec.get("child_name") or "Unknown",
                        rec.get("father_name"),
                        rec.get("phone") or "",
                        rec.get("city"),
                        rec.get("condition"),
                        rec.get("status") or "New Lead",
                        rec.get("receiver_name"),
                        created_at,
                    ),
                )
                new_child_id = cursor.lastrowid
                fee = rec.get("fee_amount") or 0
                cursor.execute(
                    """
                    INSERT INTO visits
                    (child_id, visit_date, followup_date, service_type, doctor_name,
                     notes, fee_amount, payment_status, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_child_id,
                        rec.get("visit_date"),
                        rec.get("followup_date"),
                        "Consultation",
                        rec.get("doctor_name"),
                        rec.get("notes"),
                        fee,
                        "Paid" if fee and fee > 0 else "Pending",
                        rec.get("receiver_name"),
                        created_at,
                    ),
                )
            backup_name = f"leads_migrated_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cursor.execute(f"ALTER TABLE leads RENAME TO {backup_name}")

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
            default_pass = hash_password("admin123")
            cursor.execute(
                "INSERT INTO users (username, password, name, role) VALUES (?, ?, ?, ?)",
                ("admin", default_pass, "HR Admin", "HR Admin"),
            )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                entity TEXT NOT NULL,
                entity_id TEXT,
                details TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id INTEGER NOT NULL REFERENCES children(id),
                goal_title TEXT NOT NULL,
                category TEXT,
                description TEXT,
                target_date TEXT,
                status TEXT,
                created_by TEXT,
                created_at TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL REFERENCES goals(id),
                note TEXT NOT NULL,
                created_by TEXT,
                created_at TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id INTEGER NOT NULL REFERENCES children(id),
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                category TEXT,
                uploaded_by TEXT,
                uploaded_at TEXT
            )
            """
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
# AUTH & LINK HELPERS
# ==========================================================
def log_action(username, action, entity, entity_id=None, details=""):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO audit_log (timestamp, username, action, entity, entity_id, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                username,
                action,
                entity,
                str(entity_id) if entity_id is not None else None,
                details,
            ),
        )
        conn.commit()


def login_user(username, password):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username, name, role, password FROM users WHERE username=?",
            (username,),
        )
        row = cursor.fetchone()
        if not row or not verify_password(password, row[3]):
            return None
        if needs_rehash(row[3]):
            cursor.execute(
                "UPDATE users SET password=? WHERE username=?",
                (hash_password(password), row[0]),
            )
            conn.commit()
        return (row[0], row[1], row[2])


def add_user(username, password, name, role):
    hashed_pswd = hash_password(password)
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
        "Inactive": "badge-inactive",
    }.get(status, "badge-new")
    return f'<span class="{cls}">{status or "—"}</span>'


def custom_metric(label, value):
    return f"""
    <div class="metric-card">
        <span class="metric-label">{label}</span>
        <h2 class="metric-value">{value}</h2>
    </div>
    """


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


def call_link(phone):
    digits = clean_phone_for_link(phone)
    return f"tel:+{digits}" if digits else None


def calculate_age(dob_value):
    if dob_value is None or (isinstance(dob_value, float) and pd.isna(dob_value)):
        return None
    try:
        dob = datetime.strptime(str(dob_value), "%Y-%m-%d").date()
    except Exception:
        return None
    today = datetime.today().date()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    months = (today.month - dob.month) % 12
    if years < 0:
        return None
    if years == 0:
        return f"{months} mahine"
    return f"{years} saal"


def explode_multivalue(series, delimiter=","):
    items = []
    for val in series.dropna():
        for item in str(val).split(delimiter):
            item = item.strip()
            if item:
                items.append(item)
    return pd.Series(items, dtype="object")


def parse_date_or_none(value):
    if not value or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except Exception:
        return None


def render_goals_tab(children_df):
    st.subheader("🎯 Therapy Goals & Progress Tracking")
    if children_df.empty:
        st.info("Pehle ek child register karein.")
        return

    goal_child_options = {
        f"ID {row['id']} - {row['child_name']} ({row['phone']})": row["id"]
        for _, row in children_df.iterrows()
    }
    selected_label = st.selectbox(
        "Child chunein:", list(goal_child_options.keys()), key="goals_child_select"
    )
    child_id = goal_child_options[selected_label]

    with sqlite3.connect(DB_PATH) as conn:
        goals_df = pd.read_sql(
            "SELECT * FROM goals WHERE child_id=? ORDER BY id DESC",
            conn,
            params=(child_id,),
        )

    with st.expander("➕ Naya Goal Add Karein"):
        with st.form(f"add_goal_{child_id}", clear_on_submit=True):
            g_title = st.text_input("Goal Title *")
            g_category = st.selectbox("Category", GOAL_CATEGORIES)
            g_desc = st.text_area("Description")
            g_target = st.date_input(
                "Target Date", value=datetime.today() + timedelta(days=30)
            )
            g_status = st.selectbox("Status", GOAL_STATUSES)
            g_submit = st.form_submit_button(
                "💾 Goal Save Karein", use_container_width=True
            )
            if g_submit:
                if g_title:
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            INSERT INTO goals
                            (child_id, goal_title, category, description, target_date,
                             status, created_by, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                child_id,
                                g_title,
                                g_category,
                                g_desc,
                                str(g_target),
                                g_status,
                                st.session_state["username"],
                                datetime.now().isoformat(timespec="seconds"),
                            ),
                        )
                        new_goal_id = cursor.lastrowid
                        conn.commit()
                    log_action(
                        st.session_state["username"],
                        "CREATE",
                        "goals",
                        new_goal_id,
                        f"child_id={child_id}",
                    )
                    st.success("Goal add ho gaya!")
                    st.rerun()
                else:
                    st.warning("Goal Title zaroori hai.")

    if goals_df.empty:
        st.info("Is child ke liye abhi tak koi goal set nahi hua hai.")
        return

    status_class_map = {
        "Not Started": "badge-inactive",
        "In Progress": "badge-treatment",
        "Achieved": "badge-completed",
        "On Hold": "badge-new",
    }
    for _, goal in goals_df.iterrows():
        badge_cls = status_class_map.get(goal["status"], "badge-new")
        st.markdown(
            f"""
            <div class="card">
                <h4>{goal['goal_title']} <span class="{badge_cls}">{goal['status']}</span></h4>
                <p><b>Category:</b> {goal['category'] or '—'} &nbsp; | &nbsp; <b>Target Date:</b> {goal['target_date'] or '—'}</p>
                <p>{goal['description'] or ''}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with sqlite3.connect(DB_PATH) as conn:
            notes_df = pd.read_sql(
                "SELECT * FROM goal_notes WHERE goal_id=? ORDER BY id DESC",
                conn,
                params=(goal["id"],),
            )
        if not notes_df.empty:
            for _, note_row in notes_df.iterrows():
                st.caption(
                    f"📝 {note_row['created_at']} ({note_row['created_by']}): {note_row['note']}"
                )
        with st.expander(f"➕ Progress Note / Status Update — {goal['goal_title']}"):
            with st.form(f"goal_update_{goal['id']}", clear_on_submit=True):
                new_note = st.text_area(
                    "Progress Note", key=f"note_{goal['id']}"
                )
                new_status = st.selectbox(
                    "Status",
                    GOAL_STATUSES,
                    index=(
                        GOAL_STATUSES.index(goal["status"])
                        if goal["status"] in GOAL_STATUSES
                        else 0
                    ),
                    key=f"status_{goal['id']}",
                )
                submit_note = st.form_submit_button(
                    "💾 Update", use_container_width=True
                )
                if submit_note:
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        if new_note.strip():
                            cursor.execute(
                                """
                                INSERT INTO goal_notes (goal_id, note, created_by, created_at)
                                VALUES (?, ?, ?, ?)
                                """,
                                (
                                    goal["id"],
                                    new_note.strip(),
                                    st.session_state["username"],
                                    datetime.now().isoformat(timespec="seconds"),
                                ),
                            )
                        if new_status != goal["status"]:
                            cursor.execute(
                                "UPDATE goals SET status=? WHERE id=?",
                                (new_status, goal["id"]),
                            )
                        conn.commit()
                    log_action(
                        st.session_state["username"],
                        "UPDATE",
                        "goals",
                        goal["id"],
                        f"status={new_status}",
                    )
                    st.success("Update ho gaya!")
                    st.rerun()
        st.divider()


def render_documents_section(child_id):
    st.markdown("#### 📎 Documents")
    with sqlite3.connect(DB_PATH) as conn:
        docs_df = pd.read_sql(
            "SELECT * FROM documents WHERE child_id=? ORDER BY id DESC",
            conn,
            params=(child_id,),
        )

    with st.expander("⬆️ Naya Document Upload Karein"):
        with st.form(f"upload_doc_{child_id}", clear_on_submit=True):
            uploaded_file = st.file_uploader(
                "File chunein (PDF, image, ya Word document)",
                type=["pdf", "jpg", "jpeg", "png", "doc", "docx"],
            )
            doc_category = st.selectbox("Category", DOCUMENT_CATEGORIES)
            upload_btn = st.form_submit_button(
                "⬆️ Upload Karein", use_container_width=True
            )
            if upload_btn:
                if uploaded_file is not None:
                    safe_name = os.path.basename(uploaded_file.name)
                    stored_name = (
                        f"{datetime.now().strftime('%Y%m%d%H%M%S')}_"
                        f"{secrets.token_hex(4)}_{safe_name}"
                    )
                    child_dir = os.path.join(UPLOADS_DIR, str(child_id))
                    os.makedirs(child_dir, exist_ok=True)
                    dest_path = os.path.join(child_dir, stored_name)
                    with open(dest_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            INSERT INTO documents
                            (child_id, file_name, file_path, category, uploaded_by, uploaded_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                child_id,
                                safe_name,
                                dest_path,
                                doc_category,
                                st.session_state["username"],
                                datetime.now().isoformat(timespec="seconds"),
                            ),
                        )
                        new_doc_id = cursor.lastrowid
                        conn.commit()
                    log_action(
                        st.session_state["username"],
                        "CREATE",
                        "documents",
                        new_doc_id,
                        safe_name,
                    )
                    st.success("Document upload ho gaya!")
                    st.rerun()
                else:
                    st.warning("Kripya ek file chunein.")

    if docs_df.empty:
        st.info("Is child ke liye abhi tak koi document upload nahi hua hai.")
        return

    for _, doc in docs_df.iterrows():
        d_col1, d_col2, d_col3 = st.columns([3, 1, 1])
        with d_col1:
            st.markdown(
                f"📄 **{doc['file_name']}** — _{doc['category'] or 'Other'}_"
            )
            st.caption(
                f"Uploaded by {doc['uploaded_by']} on {doc['uploaded_at']}"
            )
        with d_col2:
            if os.path.exists(doc["file_path"]):
                with open(doc["file_path"], "rb") as f:
                    st.download_button(
                        "⬇️ Download",
                        data=f.read(),
                        file_name=doc["file_name"],
                        key=f"dl_{doc['id']}",
                        use_container_width=True,
                    )
            else:
                st.caption("File missing")
        with d_col3:
            if st.button(
                "🗑️ Delete", key=f"del_doc_{doc['id']}", use_container_width=True
            ):
                if os.path.exists(doc["file_path"]):
                    os.remove(doc["file_path"])
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM documents WHERE id=?", (doc["id"],)
                    )
                    conn.commit()
                log_action(
                    st.session_state["username"],
                    "DELETE",
                    "documents",
                    doc["id"],
                    doc["file_name"],
                )
                st.rerun()


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
                login_btn = st.form_submit_button(
                    "Login Karein", use_container_width=True
                )

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
            st.caption(
                "Yahan sirf Staff/Receiver account bante hain. HR Admin account "
                "sirf ek existing HR Admin hi 'Manage Users' se bana sakta hai."
            )
            with st.form("signup_form"):
                new_name = st.text_input("Pura Naam")
                new_username = st.text_input("Username")
                new_password = st.text_input("Password", type="password")
                signup_btn = st.form_submit_button(
                    "Account Banayein", use_container_width=True
                )

                if signup_btn:
                    if new_name and new_username and new_password:
                        if len(new_password) < 8:
                            st.warning(
                                "Password kam se kam 8 characters ka hona chahiye."
                            )
                        else:
                            success = add_user(
                                new_username,
                                new_password,
                                new_name,
                                "Staff / Receiver",
                            )
                            if success:
                                log_action(
                                    new_username, "SIGNUP", "users", new_username
                                )
                                st.success(
                                    "Account ban gaya hai! Ab login karein."
                                )
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
    st.sidebar.header("➕ Patient Entry")

    with sqlite3.connect(DB_PATH) as conn:
        children_lookup_df = pd.read_sql(
            "SELECT id, child_name, phone, status FROM children ORDER BY child_name",
            conn,
        )

    entry_mode = st.sidebar.radio(
        "Entry Type",
        ["🧒 Naya Child Register Karein", "📅 Existing Child ki Nayi Visit"],
        key="entry_mode",
    )

    if entry_mode == "🧒 Naya Child Register Karein":
        with st.sidebar.form("new_child_form", clear_on_submit=True):
            st.markdown("**Child Details**")
            child_name = st.text_input("Bachche ka Naam *")
            dob = st.date_input(
                "Date of Birth (optional)",
                value=None,
                min_value=datetime(1995, 1, 1),
                max_value=datetime.today(),
            )
            gender = st.selectbox("Gender", GENDERS)
            father_name = st.text_input("Pita ka Naam")
            mother_name = st.text_input("Mata ka Naam")
            phone = st.text_input("Mobile Number *")
            alt_phone = st.text_input("Emergency / Alt Contact")
            address = st.text_area("Address")
            city = st.text_input("City (Shehar)")
            conditions_sel = st.multiselect("Conditions", CONDITIONS)
            severity = st.selectbox("Severity", SEVERITIES)
            referral_source = st.selectbox("Referral Source", REFERRAL_SOURCES)
            status = st.selectbox("Status", STATUSES)

            st.markdown("---")
            st.markdown("**Pehli Visit Details**")
            doctor_name = st.text_input("Doctor / Therapist ka Naam")
            service_type = st.selectbox("Service Type", SERVICE_TYPES)
            visit_date = st.date_input(
                "Clinic Aane ki Date", value=datetime.today()
            )
            followup_date = st.date_input(
                "Agli Follow-up Date", value=datetime.today() + timedelta(days=7)
            )
            notes = st.text_area("Doctor/Clinic Notes (Khaas baatein)")
            fee_amount = st.number_input(
                "Fee Amount (₹)", min_value=0.0, step=100.0, value=0.0
            )
            payment_status = st.selectbox("Payment Status", PAYMENT_STATUSES)

            submit_button = st.form_submit_button(
                "💾 Child Register Karein", use_container_width=True
            )

            if submit_button:
                if child_name and phone:
                    now_iso = datetime.now().isoformat(timespec="seconds")
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            INSERT INTO children
                            (child_name, dob, gender, father_name, mother_name, phone,
                             alt_phone, address, city, conditions, severity,
                             referral_source, status, created_by, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                child_name,
                                str(dob) if dob else None,
                                gender,
                                father_name,
                                mother_name,
                                phone,
                                alt_phone,
                                address,
                                city,
                                ", ".join(conditions_sel),
                                severity,
                                referral_source,
                                status,
                                st.session_state["username"],
                                now_iso,
                            ),
                        )
                        new_child_id = cursor.lastrowid
                        cursor.execute(
                            """
                            INSERT INTO visits
                            (child_id, visit_date, followup_date, service_type,
                             doctor_name, notes, fee_amount, payment_status,
                             created_by, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                new_child_id,
                                str(visit_date),
                                str(followup_date),
                                service_type,
                                doctor_name,
                                notes,
                                fee_amount,
                                payment_status,
                                st.session_state["username"],
                                now_iso,
                            ),
                        )
                        conn.commit()
                    log_action(
                        st.session_state["username"],
                        "CREATE",
                        "children",
                        new_child_id,
                        f"child={child_name}",
                    )
                    st.sidebar.success("Child register ho gaya hai!")
                    st.rerun()
                else:
                    st.sidebar.error(
                        "Kripya Bachche ka Naam aur Phone Number bharein."
                    )
    else:
        if children_lookup_df.empty:
            st.sidebar.info("Pehle ek child register karein.")
        else:
            child_options = {
                f"{row['child_name']} ({row['phone']})": row["id"]
                for _, row in children_lookup_df.iterrows()
            }
            with st.sidebar.form("new_visit_form", clear_on_submit=True):
                selected_child_label = st.selectbox(
                    "Child Chunein", list(child_options.keys())
                )
                doctor_name = st.text_input("Doctor / Therapist ka Naam")
                service_type = st.selectbox("Service Type", SERVICE_TYPES)
                visit_date = st.date_input(
                    "Visit Date", value=datetime.today()
                )
                followup_date = st.date_input(
                    "Agli Follow-up Date",
                    value=datetime.today() + timedelta(days=7),
                )
                notes = st.text_area("Session / Clinic Notes")
                fee_amount = st.number_input(
                    "Fee Amount (₹)", min_value=0.0, step=100.0, value=0.0
                )
                payment_status = st.selectbox("Payment Status", PAYMENT_STATUSES)
                selected_child_id_preview = child_options[selected_child_label]
                current_status = children_lookup_df.loc[
                    children_lookup_df["id"] == selected_child_id_preview,
                    "status",
                ].iloc[0]
                new_child_status = st.selectbox(
                    "Child ka Overall Status",
                    STATUSES,
                    index=(
                        STATUSES.index(current_status)
                        if current_status in STATUSES
                        else 0
                    ),
                )

                submit_visit_btn = st.form_submit_button(
                    "💾 Visit Save Karein", use_container_width=True
                )

                if submit_visit_btn:
                    child_id = child_options[selected_child_label]
                    now_iso = datetime.now().isoformat(timespec="seconds")
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            INSERT INTO visits
                            (child_id, visit_date, followup_date, service_type,
                             doctor_name, notes, fee_amount, payment_status,
                             created_by, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                child_id,
                                str(visit_date),
                                str(followup_date),
                                service_type,
                                doctor_name,
                                notes,
                                fee_amount,
                                payment_status,
                                st.session_state["username"],
                                now_iso,
                            ),
                        )
                        new_visit_id = cursor.lastrowid
                        if new_child_status != current_status:
                            cursor.execute(
                                "UPDATE children SET status=? WHERE id=?",
                                (new_child_status, child_id),
                            )
                        conn.commit()
                    log_action(
                        st.session_state["username"],
                        "CREATE",
                        "visits",
                        new_visit_id,
                        f"child_id={child_id}",
                    )
                    if new_child_status != current_status:
                        log_action(
                            st.session_state["username"],
                            "UPDATE",
                            "children",
                            child_id,
                            f"status -> {new_child_status}",
                        )
                    st.sidebar.success("Visit safalpurvak save ho gayi!")
                    st.rerun()

    # ---------- LOAD DATA ----------
    with sqlite3.connect(DB_PATH) as conn:
        try:
            children_df = pd.read_sql(
                "SELECT * FROM children ORDER BY id DESC", conn
            )
        except Exception:
            children_df = pd.DataFrame(columns=CHILD_COLUMNS)
        try:
            visits_df = pd.read_sql("SELECT * FROM visits ORDER BY id DESC", conn)
        except Exception:
            visits_df = pd.DataFrame(columns=VISIT_COLUMNS)
        try:
            df = pd.read_sql(
                """
                SELECT
                    v.id AS visit_id, v.child_id, v.visit_date, v.followup_date,
                    v.service_type, v.doctor_name, v.notes, v.fee_amount,
                    v.payment_status, v.created_by AS visit_receiver,
                    v.created_at AS visit_created_at,
                    c.child_name, c.dob, c.gender, c.father_name, c.mother_name,
                    c.phone, c.alt_phone, c.address, c.city, c.conditions,
                    c.severity, c.referral_source, c.status,
                    c.created_by AS receiver_name, c.created_at AS child_created_at
                FROM visits v
                JOIN children c ON v.child_id = c.id
                ORDER BY v.id DESC
                """,
                conn,
            )
        except Exception:
            df = pd.DataFrame(columns=MERGED_COLUMNS)

    for col in CHILD_COLUMNS:
        if col not in children_df.columns:
            children_df[col] = None
    for col in MERGED_COLUMNS:
        if col not in df.columns:
            df[col] = None

    today_str = str(datetime.today().date())
    tomorrow_str = str((datetime.today() + timedelta(days=1)).date())

    st.title("🏥 Normal Child Clinic — CRM Dashboard")
    st.caption(f"Aaj: {datetime.today().strftime('%d %B %Y')}")

    # ---------- TODAY'S ALERT BANNER ----------
    if not df.empty:
        due_today = df[df["followup_date"] == today_str]
        due_tomorrow = df[df["followup_date"] == tomorrow_str]
        if not due_today.empty:
            names = ", ".join(due_today["child_name"].head(5).tolist())
            st.warning(
                f"📞 Aaj {len(due_today)} follow-up(s) due hain: {names}{' ...' if len(due_today) > 5 else ''}"
            )
        if not due_tomorrow.empty:
            st.info(
                f"🔔 Kal {len(due_tomorrow)} follow-up(s) due honge — abhi se taiyaari karein."
            )

    st.markdown("---")

    # ==========================================================
    # ROLE-BASED VIEW
    # ==========================================================
    if st.session_state["user_role"] == "HR Admin":
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
            [
                "📋 Dashboard",
                "🧒 Patient Profile",
                "✏️ Edit Record",
                "📊 Reports & Analytics",
                "📅 Follow-up Tracker",
                "🗑️ Delete Record",
                "👥 Users & Audit Log",
                "🎯 Therapy Goals",
            ]
        )

        # -------- TAB 1: DASHBOARD --------
        with tab1:
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            total_children = len(children_df)
            today_visits = (
                len(df[df["visit_date"] == today_str]) if not df.empty else 0
            )
            today_followups = (
                len(df[df["followup_date"] == today_str]) if not df.empty else 0
            )
            in_treatment = (
                len(children_df[children_df["status"] == "In Treatment"])
                if not children_df.empty
                else 0
            )
            new_leads = (
                len(children_df[children_df["status"] == "New Lead"])
                if not children_df.empty
                else 0
            )
            total_revenue = (
                visits_df["fee_amount"].fillna(0).sum()
                if not visits_df.empty and "fee_amount" in visits_df.columns
                else 0
            )

            m1.markdown(
                custom_metric("Total Children", total_children),
                unsafe_allow_html=True,
            )
            m2.markdown(
                custom_metric("Aaj ke Visits", today_visits),
                unsafe_allow_html=True,
            )
            m3.markdown(
                custom_metric("Aaj ke Follow-ups", today_followups),
                unsafe_allow_html=True,
            )
            m4.markdown(
                custom_metric("In Treatment", in_treatment),
                unsafe_allow_html=True,
            )
            m5.markdown(
                custom_metric("New Leads", new_leads), unsafe_allow_html=True
            )
            m6.markdown(
                custom_metric("Total Revenue", f"₹{total_revenue:,.0f}"),
                unsafe_allow_html=True,
            )

            st.markdown("###")

            # ------- QUICK WHATSAPP ACTION PANEL FOR TODAY'S FOLLOWUPS -------
            st.markdown("### 💬 Aaj ke Sabhi Due Follow-ups (Fast WhatsApp List)")
            due_today_list = df[df["followup_date"] == today_str]

            if not due_today_list.empty:
                for idx, p_row in due_today_list.iterrows():
                    msg = f"Namaste {p_row['father_name'] or ''} ji, Normal Child Clinic se follow-up call/msg hai. Bachche {p_row['child_name']} ki health aur clinic visit ke baare mein updates lene the. Kripya batayein abhi kaisi tabiyat hai?"
                    wa_btn_url = whatsapp_link(p_row["phone"], msg)

                    col_p1, col_p2, col_p3 = st.columns([2.5, 2, 1])
                    with col_p1:
                        st.markdown(
                            f"**🧒 {p_row['child_name']}** (Pita: {p_row['father_name'] or '—'})"
                        )
                        st.caption(
                            f"📱 {p_row['phone']} | 📍 {p_row['city'] or 'N/A'}"
                        )
                    with col_p2:
                        st.markdown(
                            f"🩺 **Conditions:** {p_row['conditions'] or '—'}"
                        )
                        st.caption(f"📝 Note: {p_row['notes'] or 'N/A'}")
                    with col_p3:
                        if wa_btn_url:
                            st.link_button(
                                "💬 Send WhatsApp",
                                wa_btn_url,
                                use_container_width=True,
                                type="primary",
                            )
                    st.divider()
            else:
                st.success("🎉 Aaj ke liye koi pending follow-up nahi hai!")

            st.markdown("---")

            if not df.empty:
                chart_col1, chart_col2 = st.columns(2)
                with chart_col1:
                    st.markdown("#### 🩺 Condition-wise Distribution (Children)")
                    cond_series = explode_multivalue(children_df["conditions"])
                    if not cond_series.empty:
                        cond_counts = cond_series.value_counts().reset_index()
                        cond_counts.columns = ["Condition", "Count"]
                        fig1 = px.pie(
                            cond_counts,
                            names="Condition",
                            values="Count",
                            hole=0.45,
                        )
                        fig1.update_layout(
                            margin=dict(t=10, b=10, l=10, r=10), height=320
                        )
                        st.plotly_chart(fig1, use_container_width=True)
                    else:
                        st.info("Koi condition data available nahi hai.")

                with chart_col2:
                    st.markdown("#### 📈 Status Overview (Children)")
                    status_counts = (
                        children_df["status"].value_counts().reset_index()
                    )
                    status_counts.columns = ["Status", "Count"]
                    fig2 = px.bar(
                        status_counts,
                        x="Status",
                        y="Count",
                        color="Status",
                        text="Count",
                    )
                    fig2.update_layout(
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=320,
                        showlegend=False,
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                chart_col3, chart_col4 = st.columns(2)
                with chart_col3:
                    st.markdown("#### 🧑‍⚕️ Service-type wise Visits")
                    svc_counts = (
                        visits_df["service_type"].value_counts().reset_index()
                    )
                    svc_counts.columns = ["Service Type", "Visits"]
                    if not svc_counts.empty:
                        fig_svc = px.bar(
                            svc_counts,
                            x="Service Type",
                            y="Visits",
                            text="Visits",
                        )
                        fig_svc.update_layout(
                            margin=dict(t=10, b=10, l=10, r=10), height=320
                        )
                        st.plotly_chart(fig_svc, use_container_width=True)
                    else:
                        st.info("Koi visit data available nahi hai.")

                with chart_col4:
                    st.markdown("#### 💳 Payment Status wise Visits")
                    pay_counts = (
                        visits_df["payment_status"].value_counts().reset_index()
                    )
                    pay_counts.columns = ["Payment Status", "Count"]
                    if not pay_counts.empty:
                        fig_pay = px.pie(
                            pay_counts,
                            names="Payment Status",
                            values="Count",
                            hole=0.45,
                        )
                        fig_pay.update_layout(
                            margin=dict(t=10, b=10, l=10, r=10), height=320
                        )
                        st.plotly_chart(fig_pay, use_container_width=True)
                    else:
                        st.info("Koi payment data available nahi hai.")

                st.markdown("#### 📅 Visits Trend (Last 30 Days)")
                trend_df = visits_df.copy()
                trend_df["visit_date"] = pd.to_datetime(
                    trend_df["visit_date"], errors="coerce"
                )
                cutoff = datetime.today() - timedelta(days=30)
                trend_df = trend_df[trend_df["visit_date"] >= cutoff]
                if not trend_df.empty:
                    daily_counts = (
                        trend_df.groupby(trend_df["visit_date"].dt.date)
                        .size()
                        .reset_index(name="Visits")
                    )
                    fig3 = px.line(
                        daily_counts, x="visit_date", y="Visits", markers=True
                    )
                    fig3.update_layout(
                        margin=dict(t=10, b=10, l=10, r=10), height=280
                    )
                    st.plotly_chart(fig3, use_container_width=True)
                else:
                    st.info("Pichle 30 dinon mein koi visit data nahi hai.")

                st.markdown("#### 💰 Monthly Revenue")
                rev_df = visits_df.copy()
                rev_df["visit_date"] = pd.to_datetime(
                    rev_df["visit_date"], errors="coerce"
                )
                rev_df["fee_amount"] = rev_df["fee_amount"].fillna(0)
                rev_df = rev_df.dropna(subset=["visit_date"])
                if not rev_df.empty and rev_df["fee_amount"].sum() > 0:
                    rev_df["month"] = (
                        rev_df["visit_date"].dt.to_period("M").astype(str)
                    )
                    monthly_rev = (
                        rev_df.groupby("month")["fee_amount"]
                        .sum()
                        .reset_index()
                    )
                    fig5 = px.bar(
                        monthly_rev, x="month", y="fee_amount", text_auto=".2s"
                    )
                    fig5.update_layout(
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=280,
                        yaxis_title="Revenue (₹)",
                    )
                    st.plotly_chart(fig5, use_container_width=True)
                else:
                    st.info("Abhi tak koi fee data record nahi hua hai.")

                st.markdown("---")
                col_search, col_csv, col_excel = st.columns([2, 1, 1])
                with col_search:
                    search_query = st.text_input(
                        "🔍 Search (Naam, Phone, City, ya Receiver se):"
                    )
                with col_csv:
                    st.markdown("###")
                    csv_data = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "📄 Export CSV",
                        data=csv_data,
                        file_name=f"clinic_visits_{today_str}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                with col_excel:
                    st.markdown("###")
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                        df.to_excel(
                            writer, index=False, sheet_name="Visits_Data"
                        )
                    st.download_button(
                        "📊 Export Excel",
                        data=buffer.getvalue(),
                        file_name=f"clinic_visits_{today_str}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

                filtered_df = df.copy()
                if search_query:
                    filtered_df = df[
                        df["child_name"].str.contains(
                            search_query, case=False, na=False
                        )
                        | df["phone"].str.contains(
                            search_query, case=False, na=False
                        )
                        | df["city"].str.contains(
                            search_query, case=False, na=False
                        )
                        | df["receiver_name"].str.contains(
                            search_query, case=False, na=False
                        )
                    ]

                st.markdown("#### 📋 Visit Records")
                st.dataframe(
                    filtered_df, use_container_width=True, height=350
                )

                st.markdown("#### 🧑‍💼 Call Receiver Performance")
                receiver_counts = (
                    df["receiver_name"].value_counts().reset_index()
                )
                receiver_counts.columns = ["Receiver Naam", "Kul Entries"]
                fig4 = px.bar(
                    receiver_counts,
                    x="Receiver Naam",
                    y="Kul Entries",
                    text="Kul Entries",
                )
                fig4.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10), height=280
                )
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info(
                    "Abhi tak koi record nahi hai. Sidebar se entry add karein."
                )

        # -------- TAB 2: PATIENT PROFILE --------
        with tab2:
            st.subheader("🧒 Patient Profile — 360° View")
            if not children_df.empty:
                profile_options = {
                    f"ID {row['id']} - {row['child_name']} ({row['phone']})": row[
                        "id"
                    ]
                    for _, row in children_df.iterrows()
                }
                selected_profile_label = st.selectbox(
                    "Patient chunein:",
                    list(profile_options.keys()),
                    key="profile_select",
                )
                p_id = profile_options[selected_profile_label]
                p = children_df[children_df["id"] == p_id].iloc[0]
                child_visits = visits_df[visits_df["child_id"] == p_id].copy()

                age_str = calculate_age(p["dob"])
                total_paid = child_visits["fee_amount"].fillna(0).sum()

                col_info, col_actions = st.columns([2.5, 1])
                with col_info:
                    st.markdown(
                        f"""
                        <div class="card">
                            <h3>{p['child_name']} {status_badge(p['status'])}</h3>
                            <p><b>DOB / Age:</b> {p['dob'] or '—'} {f"({age_str})" if age_str else ''} &nbsp; | &nbsp; <b>Gender:</b> {p['gender'] or '—'}</p>
                            <p><b>Pita ka Naam:</b> {p['father_name'] or '—'} &nbsp; | &nbsp; <b>Mata ka Naam:</b> {p['mother_name'] or '—'}</p>
                            <p><b>Phone:</b> {p['phone']} &nbsp; | &nbsp; <b>Emergency Contact:</b> {p['alt_phone'] or '—'}</p>
                            <p><b>City:</b> {p['city'] or '—'} &nbsp; | &nbsp; <b>Address:</b> {p['address'] or '—'}</p>
                            <p><b>Conditions:</b> {p['conditions'] or '—'} &nbsp; | &nbsp; <b>Severity:</b> {p['severity'] or '—'}</p>
                            <p><b>Referral Source:</b> {p['referral_source'] or '—'}</p>
                            <p><b>Total Visits:</b> {len(child_visits)} &nbsp; | &nbsp; <b>Total Fee Collected:</b> ₹{total_paid:,.0f}</p>
                            <p><b>Registered By:</b> {p['created_by'] or '—'} on {p['created_at'] or '—'}</p>
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
                        st.link_button(
                            "💬 WhatsApp Karein",
                            wa_url,
                            use_container_width=True,
                        )
                    if tel_url:
                        st.link_button(
                            "📞 Call Karein", tel_url, use_container_width=True
                        )

                    with st.form(f"quick_status_{p_id}"):
                        new_status = st.selectbox(
                            "Status Update Karein",
                            STATUSES,
                            index=(
                                STATUSES.index(p["status"])
                                if p["status"] in STATUSES
                                else 0
                            ),
                        )
                        quick_update = st.form_submit_button(
                            "💾 Update", use_container_width=True
                        )
                        if quick_update:
                            with sqlite3.connect(DB_PATH) as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "UPDATE children SET status=? WHERE id=?",
                                    (new_status, p_id),
                                )
                                conn.commit()
                            log_action(
                                st.session_state["username"],
                                "UPDATE",
                                "children",
                                p_id,
                                f"status -> {new_status}",
                            )
                            st.success("Status update ho gaya!")
                            st.rerun()

                st.markdown("---")
                st.markdown("#### 📜 Visit History")
                if not child_visits.empty:
                    st.dataframe(
                        child_visits[
                            [
                                "id",
                                "visit_date",
                                "service_type",
                                "doctor_name",
                                "followup_date",
                                "fee_amount",
                                "payment_status",
                                "notes",
                            ]
                        ].sort_values("visit_date", ascending=False),
                        use_container_width=True,
                        height=220,
                    )
                else:
                    st.info("Is child ki abhi tak koi visit record nahi hai.")

                with st.expander("➕ Nayi Visit Add Karein (isi child ke liye)"):
                    with st.form(f"profile_add_visit_{p_id}"):
                        pv_doctor = st.text_input("Doctor / Therapist ka Naam")
                        pv_service = st.selectbox("Service Type", SERVICE_TYPES)
                        pv_visit_date = st.date_input(
                            "Visit Date", value=datetime.today()
                        )
                        pv_followup_date = st.date_input(
                            "Agli Follow-up Date",
                            value=datetime.today() + timedelta(days=7),
                        )
                        pv_notes = st.text_area("Session / Clinic Notes")
                        pv_fee = st.number_input(
                            "Fee Amount (₹)", min_value=0.0, step=100.0, value=0.0
                        )
                        pv_payment = st.selectbox(
                            "Payment Status", PAYMENT_STATUSES
                        )
                        pv_submit = st.form_submit_button(
                            "💾 Visit Save Karein", use_container_width=True
                        )
                        if pv_submit:
                            with sqlite3.connect(DB_PATH) as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    """
                                    INSERT INTO visits
                                    (child_id, visit_date, followup_date, service_type,
                                     doctor_name, notes, fee_amount, payment_status,
                                     created_by, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        p_id,
                                        str(pv_visit_date),
                                        str(pv_followup_date),
                                        pv_service,
                                        pv_doctor,
                                        pv_notes,
                                        pv_fee,
                                        pv_payment,
                                        st.session_state["username"],
                                        datetime.now().isoformat(
                                            timespec="seconds"
                                        ),
                                    ),
                                )
                                new_visit_id = cursor.lastrowid
                                conn.commit()
                            log_action(
                                st.session_state["username"],
                                "CREATE",
                                "visits",
                                new_visit_id,
                                f"child_id={p_id}",
                            )
                            st.success("Visit save ho gayi!")
                            st.rerun()

                st.markdown("---")
                render_documents_section(p_id)

                st.markdown("---")
                st.markdown("#### 📜 Is Receiver ke Baaki Patients")
                same_receiver = children_df[
                    (children_df["created_by"] == p["created_by"])
                    & (children_df["id"] != p_id)
                ]
                if not same_receiver.empty:
                    st.dataframe(
                        same_receiver[
                            ["id", "child_name", "phone", "status"]
                        ],
                        use_container_width=True,
                        height=200,
                    )
                else:
                    st.info(
                        "Is receiver ke paas koi aur patient record nahi hai."
                    )
            else:
                st.info(
                    "Abhi tak koi record nahi hai. Sidebar se entry add karein."
                )

        # -------- TAB 3: EDIT RECORD --------
        with tab3:
            st.subheader("✏️ Existing Record Update Karein")
            edit_type = st.radio(
                "Kya edit karna hai?",
                ["🧒 Child Profile", "📅 Ek Visit"],
                horizontal=True,
                key="edit_type",
            )

            if edit_type == "🧒 Child Profile":
                if not children_df.empty:
                    patient_options = {
                        f"ID {row['id']} - {row['child_name']} ({row['phone']})": row[
                            "id"
                        ]
                        for _, row in children_df.iterrows()
                    }
                    selected_patient_label = st.selectbox(
                        "Update karne ke liye Child chunein:",
                        list(patient_options.keys()),
                    )
                    selected_id = patient_options[selected_patient_label]
                    patient_data = children_df[
                        children_df["id"] == selected_id
                    ].iloc[0]

                    with st.form("edit_child_form"):
                        e_col1, e_col2 = st.columns(2)
                        with e_col1:
                            e_child_name = st.text_input(
                                "Bachche ka Naam", value=patient_data["child_name"]
                            )
                            e_dob = st.date_input(
                                "Date of Birth (optional)",
                                value=parse_date_or_none(patient_data["dob"]),
                                min_value=datetime(1995, 1, 1),
                                max_value=datetime.today(),
                            )
                            gender_idx = (
                                GENDERS.index(patient_data["gender"])
                                if patient_data["gender"] in GENDERS
                                else 0
                            )
                            e_gender = st.selectbox(
                                "Gender", GENDERS, index=gender_idx
                            )
                            e_father_name = st.text_input(
                                "Pita ka Naam", value=patient_data["father_name"]
                            )
                            e_mother_name = st.text_input(
                                "Mata ka Naam",
                                value=(
                                    patient_data["mother_name"]
                                    if pd.notna(patient_data.get("mother_name"))
                                    else ""
                                ),
                            )
                            e_phone = st.text_input(
                                "Mobile Number", value=patient_data["phone"]
                            )
                            e_alt_phone = st.text_input(
                                "Emergency / Alt Contact",
                                value=(
                                    patient_data["alt_phone"]
                                    if pd.notna(patient_data.get("alt_phone"))
                                    else ""
                                ),
                            )

                        with e_col2:
                            e_address = st.text_area(
                                "Address",
                                value=(
                                    patient_data["address"]
                                    if pd.notna(patient_data.get("address"))
                                    else ""
                                ),
                            )
                            e_city = st.text_input(
                                "City", value=patient_data["city"]
                            )
                            existing_conditions = [
                                c.strip()
                                for c in str(
                                    patient_data["conditions"] or ""
                                ).split(",")
                                if c.strip() in CONDITIONS
                            ]
                            e_conditions = st.multiselect(
                                "Conditions",
                                CONDITIONS,
                                default=existing_conditions,
                            )
                            severity_idx = (
                                SEVERITIES.index(patient_data["severity"])
                                if patient_data["severity"] in SEVERITIES
                                else 0
                            )
                            e_severity = st.selectbox(
                                "Severity", SEVERITIES, index=severity_idx
                            )
                            referral_idx = (
                                REFERRAL_SOURCES.index(
                                    patient_data["referral_source"]
                                )
                                if patient_data["referral_source"]
                                in REFERRAL_SOURCES
                                else 0
                            )
                            e_referral = st.selectbox(
                                "Referral Source",
                                REFERRAL_SOURCES,
                                index=referral_idx,
                            )
                            status_idx = (
                                STATUSES.index(patient_data["status"])
                                if patient_data["status"] in STATUSES
                                else 0
                            )
                            e_status = st.selectbox(
                                "Status", STATUSES, index=status_idx
                            )

                        update_button = st.form_submit_button(
                            "💾 Child Record Update Karein"
                        )

                        if update_button:
                            with sqlite3.connect(DB_PATH) as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    """
                                    UPDATE children
                                    SET child_name=?, dob=?, gender=?, father_name=?,
                                        mother_name=?, phone=?, alt_phone=?, address=?,
                                        city=?, conditions=?, severity=?, referral_source=?,
                                        status=?
                                    WHERE id=?
                                    """,
                                    (
                                        e_child_name,
                                        str(e_dob) if e_dob else None,
                                        e_gender,
                                        e_father_name,
                                        e_mother_name,
                                        e_phone,
                                        e_alt_phone,
                                        e_address,
                                        e_city,
                                        ", ".join(e_conditions),
                                        e_severity,
                                        e_referral,
                                        e_status,
                                        selected_id,
                                    ),
                                )
                                conn.commit()
                            log_action(
                                st.session_state["username"],
                                "UPDATE",
                                "children",
                                selected_id,
                                f"child={e_child_name}",
                            )
                            st.success(
                                f"ID {selected_id} ka child record update ho gaya hai!"
                            )
                            st.rerun()
                else:
                    st.info("Update karne ke liye koi record nahi hai.")
            else:
                if not df.empty:
                    visit_options = {
                        f"Visit #{row['visit_id']} - {row['child_name']} - {row['visit_date']}": row[
                            "visit_id"
                        ]
                        for _, row in df.iterrows()
                    }
                    selected_visit_label = st.selectbox(
                        "Update karne ke liye Visit chunein:",
                        list(visit_options.keys()),
                    )
                    selected_visit_id = visit_options[selected_visit_label]
                    visit_data = df[df["visit_id"] == selected_visit_id].iloc[0]

                    with st.form("edit_visit_form"):
                        ev_col1, ev_col2 = st.columns(2)
                        with ev_col1:
                            service_idx = (
                                SERVICE_TYPES.index(visit_data["service_type"])
                                if visit_data["service_type"] in SERVICE_TYPES
                                else 0
                            )
                            ev_service = st.selectbox(
                                "Service Type", SERVICE_TYPES, index=service_idx
                            )
                            ev_doctor = st.text_input(
                                "Doctor / Therapist ka Naam",
                                value=(
                                    visit_data["doctor_name"]
                                    if pd.notna(visit_data.get("doctor_name"))
                                    else ""
                                ),
                            )
                            try:
                                v_date = datetime.strptime(
                                    visit_data["visit_date"], "%Y-%m-%d"
                                ).date()
                            except Exception:
                                v_date = datetime.today().date()
                            try:
                                f_date = datetime.strptime(
                                    visit_data["followup_date"], "%Y-%m-%d"
                                ).date()
                            except Exception:
                                f_date = datetime.today().date()
                            ev_visit_date = st.date_input(
                                "Visit Date", value=v_date
                            )
                            ev_followup_date = st.date_input(
                                "Agli Follow-up Date", value=f_date
                            )
                        with ev_col2:
                            ev_fee = st.number_input(
                                "Fee Amount (₹)",
                                min_value=0.0,
                                step=100.0,
                                value=(
                                    float(visit_data["fee_amount"])
                                    if pd.notna(visit_data.get("fee_amount"))
                                    else 0.0
                                ),
                            )
                            payment_idx = (
                                PAYMENT_STATUSES.index(
                                    visit_data["payment_status"]
                                )
                                if visit_data["payment_status"]
                                in PAYMENT_STATUSES
                                else 0
                            )
                            ev_payment = st.selectbox(
                                "Payment Status",
                                PAYMENT_STATUSES,
                                index=payment_idx,
                            )
                            ev_notes = st.text_area(
                                "Session / Clinic Notes",
                                value=(
                                    visit_data["notes"]
                                    if pd.notna(visit_data.get("notes"))
                                    else ""
                                ),
                            )

                        update_visit_button = st.form_submit_button(
                            "💾 Visit Update Karein"
                        )

                        if update_visit_button:
                            with sqlite3.connect(DB_PATH) as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    """
                                    UPDATE visits
                                    SET service_type=?, doctor_name=?, visit_date=?,
                                        followup_date=?, fee_amount=?, payment_status=?, notes=?
                                    WHERE id=?
                                    """,
                                    (
                                        ev_service,
                                        ev_doctor,
                                        str(ev_visit_date),
                                        str(ev_followup_date),
                                        ev_fee,
                                        ev_payment,
                                        ev_notes,
                                        selected_visit_id,
                                    ),
                                )
                                conn.commit()
                            log_action(
                                st.session_state["username"],
                                "UPDATE",
                                "visits",
                                selected_visit_id,
                                f"child={visit_data['child_name']}",
                            )
                            st.success(
                                f"Visit #{selected_visit_id} update ho gaya hai!"
                            )
                            st.rerun()
                else:
                    st.info("Update karne ke liye koi visit record nahi hai.")

        # -------- TAB 4: REPORTS --------
        with tab4:
            st.subheader("📈 Zaroori Reports aur Analysis")
            if not df.empty:
                rep_col1, rep_col2 = st.columns(2)
                with rep_col1:
                    st.markdown("### 📅 Date-wise Visit Report")
                    selected_visit_date = st.date_input(
                        "Clinic Visit Date chunein:", value=datetime.today()
                    )
                    v_str = str(selected_visit_date)
                    v_filtered = df[df["visit_date"] == v_str]
                    st.write(
                        f"**Total Visits Scheduled ({v_str}):** {len(v_filtered)}"
                    )
                    if not v_filtered.empty:
                        st.dataframe(v_filtered, use_container_width=True)
                    else:
                        st.info("Is tarikh ko koi visit scheduled nahi hai.")

                with rep_col2:
                    st.markdown("### 📞 Follow-up Report")
                    selected_follow_date = st.date_input(
                        "Follow-up Date chunein:",
                        value=datetime.today(),
                        key="follow_date_picker",
                    )
                    f_str = str(selected_follow_date)
                    f_filtered = df[df["followup_date"] == f_str]
                    st.write(
                        f"**Total Follow-ups Due ({f_str}):** {len(f_filtered)}"
                    )
                    if not f_filtered.empty:
                        st.dataframe(f_filtered, use_container_width=True)
                    else:
                        st.info(
                            "Is tarikh ko koi follow-up scheduled nahi hai."
                        )

                st.markdown("---")
                st.markdown("### 🏙️ City-wise Report & Analysis")
                city_col1, city_col2 = st.columns([1, 2])
                with city_col1:
                    city_counts = children_df["city"].value_counts().reset_index()
                    city_counts.columns = ["City", "Kul Bachche"]
                    st.dataframe(city_counts, use_container_width=True)
                with city_col2:
                    cities_list = [
                        str(c)
                        for c in children_df["city"].dropna().unique()
                        if str(c).strip()
                    ]
                    if cities_list:
                        selected_city = st.selectbox(
                            "City chunein:", ["Sabhi Cities"] + cities_list
                        )
                        city_filtered_df = (
                            children_df
                            if selected_city == "Sabhi Cities"
                            else children_df[children_df["city"] == selected_city]
                        )
                        st.dataframe(city_filtered_df, use_container_width=True)
                    else:
                        st.info("Koi city data available nahi hai.")

                st.markdown("---")
                st.markdown("### 💰 Payment / Dues Report")
                dues_df = df[df["payment_status"] != "Paid"][
                    [
                        "visit_id",
                        "child_name",
                        "phone",
                        "visit_date",
                        "service_type",
                        "fee_amount",
                        "payment_status",
                    ]
                ]
                if not dues_df.empty:
                    st.write(
                        f"**Pending / Partial Dues:** ₹{dues_df['fee_amount'].fillna(0).sum():,.0f} "
                        f"({len(dues_df)} visits)"
                    )
                    st.dataframe(dues_df, use_container_width=True, height=250)
                else:
                    st.success("Koi pending ya partial payment nahi hai. 🎉")
            else:
                st.info("Reports dekhne ke liye koi data nahi hai.")

        # -------- TAB 5: FOLLOW-UP TRACKER --------
        with tab5:
            st.subheader("📅 Active Follow-up Tracker")
            if not df.empty:
                f_status = st.radio(
                    "Filter Follow-ups:",
                    ["Overdue", "Aaj Ke", "Agami (Upcoming)"],
                    horizontal=True,
                )

                df["followup_date_dt"] = pd.to_datetime(
                    df["followup_date"], errors="coerce"
                ).dt.date
                today_dt = datetime.today().date()

                if f_status == "Overdue":
                    tracker_df = df[df["followup_date_dt"] < today_dt]
                elif f_status == "Aaj Ke":
                    tracker_df = df[df["followup_date_dt"] == today_dt]
                else:
                    tracker_df = df[df["followup_date_dt"] > today_dt]

                st.write(f"**Kul Records Found:** {len(tracker_df)}")

                if not tracker_df.empty:
                    for _, row in tracker_df.iterrows():
                        with st.container():
                            c1, c2, c3 = st.columns([3, 2, 1])
                            with c1:
                                st.markdown(
                                    f"**{row['child_name']}** (Pita: {row['father_name'] or 'N/A'})"
                                )
                                st.caption(
                                    f"Phone: {row['phone']} | City: {row['city'] or 'N/A'} | Status: {row['status']}"
                                )
                            with c2:
                                st.markdown(
                                    f"🗓️ **Follow-up Date:** {row['followup_date']}"
                                )
                                st.caption(
                                    f"Service: {row['service_type'] or '—'} | Note: {row['notes'] or 'Koi note nahi'}"
                                )
                            with c3:
                                wa_link = whatsapp_link(
                                    row["phone"],
                                    f"Namaste, {row['child_name']} ke follow-up ke baare mein reminder call/msg hai.",
                                )
                                if wa_link:
                                    st.link_button(
                                        "💬 WhatsApp",
                                        wa_link,
                                        use_container_width=True,
                                    )
                            st.divider()
                else:
                    st.success(
                        "Is category mein koi follow-up records nahi hain."
                    )
            else:
                st.info("Follow-up track karne ke liye koi data nahi hai.")

        # -------- TAB 6: DELETE RECORD --------
        with tab6:
            st.subheader("🗑️ Record Hatayein")
            st.warning(
                "⚠️ Dhyan den: Yahan se delete kiya gaya record permanently hat jayega."
            )
            delete_type = st.radio(
                "Kya delete karna hai?",
                ["🧒 Poora Child (saari visits sahit)", "📅 Ek Visit"],
                horizontal=True,
                key="delete_type",
            )

            if delete_type == "🧒 Poora Child (saari visits sahit)":
                if not children_df.empty:
                    delete_options = {
                        f"ID {row['id']} - {row['child_name']} ({row['phone']})": row[
                            "id"
                        ]
                        for _, row in children_df.iterrows()
                    }
                    selected_del_label = st.selectbox(
                        "Delete karne ke liye child chunein:",
                        list(delete_options.keys()),
                    )
                    del_id = delete_options[selected_del_label]
                    related_visits_count = len(
                        visits_df[visits_df["child_id"] == del_id]
                    )
                    st.warning(
                        f"Is child ki {related_visits_count} visit(s) bhi saath mein delete ho jayengi."
                    )

                    if st.button(
                        "🗑️ Child aur Sabhi Visits Permanently Delete Karein",
                        type="primary",
                    ):
                        with sqlite3.connect(DB_PATH) as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "DELETE FROM visits WHERE child_id=?", (del_id,)
                            )
                            cursor.execute(
                                "DELETE FROM children WHERE id=?", (del_id,)
                            )
                            conn.commit()
                        log_action(
                            st.session_state["username"],
                            "DELETE",
                            "children",
                            del_id,
                            f"{selected_del_label} (+{related_visits_count} visits)",
                        )
                        st.success(
                            f"Child ID {del_id} aur uski sabhi visits delete ho gayi hain!"
                        )
                        st.rerun()
                else:
                    st.info("Delete karne ke liye koi record nahi hai.")
            else:
                if not df.empty:
                    visit_del_options = {
                        f"Visit #{row['visit_id']} - {row['child_name']} - {row['visit_date']}": row[
                            "visit_id"
                        ]
                        for _, row in df.iterrows()
                    }
                    selected_visit_del_label = st.selectbox(
                        "Delete karne ke liye visit chunein:",
                        list(visit_del_options.keys()),
                    )
                    del_visit_id = visit_del_options[selected_visit_del_label]

                    if st.button(
                        "🗑️ Visit Permanently Delete Karein", type="primary"
                    ):
                        with sqlite3.connect(DB_PATH) as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "DELETE FROM visits WHERE id=?", (del_visit_id,)
                            )
                            conn.commit()
                        log_action(
                            st.session_state["username"],
                            "DELETE",
                            "visits",
                            del_visit_id,
                            selected_visit_del_label,
                        )
                        st.success(
                            f"Visit #{del_visit_id} safalpurvak delete ho gayi hai!"
                        )
                        st.rerun()
                else:
                    st.info("Delete karne ke liye koi visit record nahi hai.")

        # -------- TAB 7: USERS & AUDIT LOG --------
        with tab7:
            st.subheader("👥 User Management")
            st.caption(
                "Sirf HR Admin naye accounts bana sakta hai, jinme HR Admin "
                "role bhi shaamil hai."
            )

            with sqlite3.connect(DB_PATH) as conn:
                users_df = pd.read_sql(
                    "SELECT username, name, role FROM users ORDER BY name", conn
                )

            with st.form("add_user_form", clear_on_submit=True):
                u_col1, u_col2 = st.columns(2)
                with u_col1:
                    nu_name = st.text_input("Pura Naam", key="nu_name")
                    nu_username = st.text_input("Username", key="nu_username")
                with u_col2:
                    nu_password = st.text_input(
                        "Password", type="password", key="nu_password"
                    )
                    nu_role = st.selectbox(
                        "Role", ["Staff / Receiver", "HR Admin"], key="nu_role"
                    )
                add_user_btn = st.form_submit_button(
                    "➕ Account Banayein", use_container_width=True
                )
                if add_user_btn:
                    if nu_name and nu_username and nu_password:
                        if len(nu_password) < 8:
                            st.warning(
                                "Password kam se kam 8 characters ka hona chahiye."
                            )
                        else:
                            success = add_user(
                                nu_username, nu_password, nu_name, nu_role
                            )
                            if success:
                                log_action(
                                    st.session_state["username"],
                                    "CREATE",
                                    "users",
                                    nu_username,
                                    f"role={nu_role}",
                                )
                                st.success(
                                    f"Account '{nu_username}' ban gaya hai."
                                )
                                st.rerun()
                            else:
                                st.error("Username pehle se maujood hai.")
                    else:
                        st.warning("Kripya sabhi jaankari bharein.")

            st.markdown("#### Existing Users")
            st.dataframe(users_df, use_container_width=True, height=220)

            admin_count = int((users_df["role"] == "HR Admin").sum())
            del_col1, del_col2 = st.columns([3, 1])
            with del_col1:
                deletable_users = [
                    u for u in users_df["username"].tolist()
                ]
                user_to_remove = st.selectbox(
                    "Account hataayein:", deletable_users, key="user_to_remove"
                )
            with del_col2:
                st.markdown("###")
                if st.button("🗑️ Remove User", use_container_width=True):
                    if user_to_remove == st.session_state["username"]:
                        st.error("Aap apna hi account nahi hata sakte.")
                    else:
                        removed_role = users_df.loc[
                            users_df["username"] == user_to_remove, "role"
                        ].iloc[0]
                        if removed_role == "HR Admin" and admin_count <= 1:
                            st.error(
                                "Aakhri HR Admin account hataya nahi ja sakta."
                            )
                        else:
                            with sqlite3.connect(DB_PATH) as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "DELETE FROM users WHERE username=?",
                                    (user_to_remove,),
                                )
                                conn.commit()
                            log_action(
                                st.session_state["username"],
                                "DELETE",
                                "users",
                                user_to_remove,
                            )
                            st.success(f"'{user_to_remove}' hata diya gaya.")
                            st.rerun()

            st.markdown("---")
            st.subheader("📜 Audit Log")
            with sqlite3.connect(DB_PATH) as conn:
                try:
                    audit_df = pd.read_sql(
                        "SELECT timestamp, username, action, entity, entity_id, details "
                        "FROM audit_log ORDER BY id DESC LIMIT 300",
                        conn,
                    )
                except Exception:
                    audit_df = pd.DataFrame(
                        columns=[
                            "timestamp",
                            "username",
                            "action",
                            "entity",
                            "entity_id",
                            "details",
                        ]
                    )
            if not audit_df.empty:
                st.dataframe(audit_df, use_container_width=True, height=350)
            else:
                st.info("Abhi tak koi audit activity record nahi hui hai.")

        # -------- TAB 8: THERAPY GOALS --------
        with tab8:
            render_goals_tab(children_df)

    # ==========================================================
    # STAFF / RECEIVER VIEW
    # ==========================================================
    else:
        st.subheader("📋 Patient Entries & Quick Follow-up Tracker")

        tab_s1, tab_s2, tab_s3 = st.tabs(
            ["📋 Meri/Sabhi Entries", "📞 Today's Follow-ups", "🎯 Therapy Goals"]
        )

        with tab_s1:
            st.markdown("#### Patient Records")
            search_query_staff = st.text_input(
                "🔍 Search (Naam, Phone, ya City se):"
            )

            filtered_children_staff = children_df.copy()
            if search_query_staff:
                filtered_children_staff = children_df[
                    children_df["child_name"].str.contains(
                        search_query_staff, case=False, na=False
                    )
                    | children_df["phone"].str.contains(
                        search_query_staff, case=False, na=False
                    )
                    | children_df["city"].str.contains(
                        search_query_staff, case=False, na=False
                    )
                ]

            st.dataframe(
                filtered_children_staff, use_container_width=True, height=400
            )

        with tab_s2:
            st.markdown("#### 📞 Aaj Ke Due Follow-ups")
            due_today_staff = df[df["followup_date"] == today_str]

            if not due_today_staff.empty:
                for _, row in due_today_staff.iterrows():
                    with st.container():
                        col_a, col_b = st.columns([3, 1])
                        with col_a:
                            st.markdown(
                                f"**{row['child_name']}** — {row['phone']}"
                            )
                            st.caption(
                                f"Conditions: {row['conditions']} | City: {row['city']} | Notes: {row['notes']}"
                            )
                        with col_b:
                            wa_url_s = whatsapp_link(
                                row["phone"],
                                f"Namaste, {row['child_name']} ke clinic visit ke baare mein updates lene the.",
                            )
                            if wa_url_s:
                                st.link_button(
                                    "💬 Message",
                                    wa_url_s,
                                    use_container_width=True,
                                )
                        st.divider()
            else:
                st.success("Aaj ke liye koi pending follow-up nahi hai! 🎉")

        with tab_s3:
            render_goals_tab(children_df)
