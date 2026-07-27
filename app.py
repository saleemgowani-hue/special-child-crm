import hashlib
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="Normal Child Clinic CRM", page_icon="🏥", layout="wide"
)


# Password Hashing Helper Functions
def make_hashes(password):
  return hashlib.sha256(str.encode(password)).hexdigest()


def check_hashes(password, hashed_text):
  if make_hashes(password) == hashed_text:
    return hashed_text
  return False


# 2. Database Initialization
def init_db():
  with sqlite3.connect("crm.db") as conn:
    cursor = conn.cursor()

    # Leads Table
    cursor.execute("""
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
                status TEXT
            )
        """)

    # Users Table for Login/Signup
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)

    # Default HR Admin account banayein (agar users table khali ho)
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
      default_pass = make_hashes("admin123")
      cursor.execute(
          """
                INSERT INTO users (username, password, name, role)
                VALUES (?, ?, ?, ?)
            """,
          ("admin", default_pass, "HR Admin", "HR Admin"),
      )

    conn.commit()


init_db()

# 3. Session State Initialization
if "logged_in" not in st.session_state:
  st.session_state["logged_in"] = False
if "username" not in st.session_state:
  st.session_state["username"] = ""
if "user_role" not in st.session_state:
  st.session_state["user_role"] = ""
if "user_name" not in st.session_state:
  st.session_state["user_name"] = ""


# User Authentication Helper Functions
def login_user(username, password):
  hashed_pswd = make_hashes(password)
  with sqlite3.connect("crm.db") as conn:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, name, role FROM users WHERE username =? AND"
        " password = ?",
        (username, hashed_pswd),
    )
    data = cursor.fetchone()
    return data


def add_user(username, password, name, role):
  hashed_pswd = make_hashes(password)
  try:
    with sqlite3.connect("crm.db") as conn:
      cursor = conn.cursor()
      cursor.execute(
          "INSERT INTO users(username, password, name, role) VALUES (?,?,?,?)",
          (username, hashed_pswd, name, role),
      )
      conn.commit()
    return True
  except sqlite3.IntegrityError:
    return False


# ==========================================
# 🔐 AUTHENTICATION SCREEN (LOGIN / SIGNUP)
# ==========================================
if not st.session_state["logged_in"]:
  st.title("🏥 Normal Child Clinic CRM")
  st.markdown("### 🔐 Kripya Portal Me Login Karein")

  auth_tab1, auth_tab2 = st.tabs(["🔑 Login", "📝 Sign Up (Naya User)"])

  # Login Form
  with auth_tab1:
    with st.form("login_form"):
      username = st.text_input("Username")
      password = st.text_input("Password", type="password")
      login_btn = st.form_submit_button("Login Karein")

      if login_btn:
        result = login_user(username, password)
        if result:
          st.session_state["logged_in"] = True
          st.session_state["username"] = result[0]
          st.session_state["user_name"] = result[1]
          st.session_state["user_role"] = result[2]
          st.success(f"Aapka Swagat Hai, {result[1]}!")
          st.rerun()
        else:
          st.error("Galat Username ya Password! Kripya dobara koshish karein.")

  # Sign Up Form
  with auth_tab2:
    with st.form("signup_form"):
      new_name = st.text_input("Aapka Pura Naam")
      new_username = st.text_input("Chuna Hua Username")
      new_password = st.text_input("Password", type="password")
      new_role = st.selectbox(
          "Role Chunein", ["Staff / Receiver", "HR Admin"]
      )
      signup_btn = st.form_submit_button("Account Banayein")

      if signup_btn:
        if new_name and new_username and new_password:
          success = add_user(
              new_username, new_password, new_name, new_role
          )
          if success:
            st.success(
                "Account safalpurvak ban gaya hai! Ab aap Login tab se login"
                " kar sakte hain."
            )
          else:
            st.error(
                "Ye Username pehle se maujood hai. Kripya doosra username"
                " chunein."
            )
        else:
          st.warning("Kripya sabhi jaankari bharein.")

  st.info(
      "💡 **Default HR Admin Credentials:**\n- Username: `admin`\n- Password:"
      " `admin123`"
  )

# ==========================================
# 🏥 MAIN APPLICATION (LOGIN HO JANE KE BAAD)
# ==========================================
else:
  # Sidebar Header with User Profile & Logout Button
  st.sidebar.markdown(f"👤 **User:** {st.session_state['user_name']}")
  st.sidebar.markdown(f"🏷️ **Role:** `{st.session_state['user_role']}`")

  if st.sidebar.button("🚪 Logout"):
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["user_role"] = ""
    st.session_state["user_name"] = ""
    st.rerun()

  st.sidebar.markdown("---")
  st.sidebar.header("➕ Nayi Entry Jodein")

  # Entry Form in Sidebar
  with st.sidebar.form("entry_form", clear_on_submit=True):
    receiver_name = st.text_input(
        "Call Receiver ka Naam *", value=st.session_state["user_name"]
    )
    child_name = st.text_input("Bachche ka Naam *")
    father_name = st.text_input("Pita ka Naam")
    phone = st.text_input("Mobile Number *")

    condition = st.selectbox(
        "Condition Chunein",
        [
            "Autism (ASD)",
            "ADHD",
            "Learning Disability",
            "Speech Delay",
            "Intellectual Disability",
            "Down Syndrome",
            "Cerebral Palsy",
            "Other",
        ],
    )

    city = st.text_input("City (Shehar)")
    visit_date = st.date_input("Clinic Aane ki Date", value=datetime.today())
    followup_date = st.date_input(
        "Agli Follow-up Date", value=datetime.today()
    )
    notes = st.text_area("Doctor/Clinic Notes (Khaas baatein)")
    status = st.selectbox("Status", ["New Lead", "In Treatment", "Completed"])

    submit_button = st.form_submit_button(label="Record Save Karein")

    if submit_button:
      if receiver_name and child_name and phone:
        with sqlite3.connect("crm.db") as conn:
          cursor = conn.cursor()
          cursor.execute(
              """
                        INSERT INTO leads (receiver_name, child_name, father_name, phone, condition, city, visit_date, followup_date, notes, status) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
              (
                  receiver_name,
                  child_name,
                  father_name,
                  phone,
                  condition,
                  city,
                  str(visit_date),
                  str(followup_date),
                  notes,
                  status,
              ),
          )
          conn.commit()
        st.sidebar.success("Record Safalpurvak Save Ho Gaya!")
        st.rerun()
      else:
        st.sidebar.error(
            "Kripya Receiver ka Naam, Bachche ka Naam aur Phone Number bharein."
        )

  # Application Main Title
  st.title("🏥 Normal Child Clinic CRM")
  st.markdown("---")

  # Read Current Leads Data
  with sqlite3.connect("crm.db") as conn:
    df = pd.read_sql("SELECT * FROM leads ORDER BY id DESC", conn)

  today_str = str(datetime.today().date())

  # ----------------------------------------------------
  # 🔴 ROLE BASED VIEW LOGIC (HR ADMIN VS STAFF)
  # ----------------------------------------------------
  if st.session_state["user_role"] == "HR Admin":
    # HR Admin gets Full Access
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Patients Dashboard (Full Access)",
        "✏️ Edit / Update Record",
        "📊 Advanced Reports",
        "🗑️ Delete Record",
    ])

    # --- TAB 1: Dashboard (Full View + Call Receiver Stats) ---
    with tab1:
      m1, m2, m3, m4 = st.columns(4)
      total_leads = len(df)
      today_visits = (
          len(df[df["visit_date"] == today_str]) if not df.empty else 0
      )
      today_followups = (
          len(df[df["followup_date"] == today_str]) if not df.empty else 0
      )
      in_treatment = (
          len(df[df["status"] == "In Treatment"]) if not df.empty else 0
      )

      m1.metric("Total Patients / Leads", total_leads)
      m2.metric("Today's Clinic Visits", today_visits)
      m3.metric("Today's Follow-ups Due", today_followups)
      m4.metric("Active in Treatment", in_treatment)

      st.markdown("---")

      if not df.empty:
        col_search, col_export = st.columns([3, 1])

        with col_search:
          search_query = st.text_input(
              "🔍 Search (Naam, Phone, City, ya Receiver se):"
          )

        with col_export:
          st.markdown("###")
          csv_data = df.to_csv(index=False).encode("utf-8")
          st.download_button(
              label="📥 Export CSV Data",
              data=csv_data,
              file_name=f"clinic_leads_{today_str}.csv",
              mime="text/csv",
          )

        filtered_df = df.copy()
        if search_query:
          filtered_df = df[
              df["child_name"].str.contains(search_query, case=False, na=False)
              | df["phone"].str.contains(search_query, case=False, na=False)
              | df["city"].str.contains(search_query, case=False, na=False)
              | df["receiver_name"].str.contains(
                  search_query, case=False, na=False
              )
          ]

        st.dataframe(filtered_df, use_container_width=True)

        st.markdown("### 📊 Call Receiver Performance Summary")
        receiver_counts = df["receiver_name"].value_counts().reset_index()
        receiver_counts.columns = ["Receiver Naam", "Kul Calls / Entries"]
        st.dataframe(receiver_counts, use_container_width=True)
      else:
        st.info("Abhi tak koi record nahi hai. Sidebar se entry add karein.")

    # --- TAB 2: Edit Record ---
    with tab2:
      st.subheader("✏️ Existing Patient Record Update Karein")
      if not df.empty:
        patient_options = {
            f"ID {row['id']} - {row['child_name']} ({row['phone']})": row["id"]
            for _, row in df.iterrows()
        }
        selected_patient_label = st.selectbox(
            "Update karne ke liye Patient chunein:",
            list(patient_options.keys()),
        )
        selected_id = patient_options[selected_patient_label]

        patient_data = df[df["id"] == selected_id].iloc[0]

        with st.form("edit_form"):
          e_col1, e_col2 = st.columns(2)

          with e_col1:
            e_receiver_name = st.text_input(
                "Call Receiver", value=patient_data["receiver_name"]
            )
            e_child_name = st.text_input(
                "Bachche ka Naam", value=patient_data["child_name"]
            )
            e_father_name = st.text_input(
                "Pita ka Naam", value=patient_data["father_name"]
            )
            e_phone = st.text_input(
                "Mobile Number", value=patient_data["phone"]
            )
            e_city = st.text_input("City", value=patient_data["city"])

          with e_col2:
            condition_list = [
                "Autism (ASD)",
                "ADHD",
                "Learning Disability",
                "Speech Delay",
                "Intellectual Disability",
                "Down Syndrome",
                "Cerebral Palsy",
                "Other",
            ]
            cond_idx = (
                condition_list.index(patient_data["condition"])
                if patient_data["condition"] in condition_list
                else 0
            )
            e_condition = st.selectbox(
                "Condition", condition_list, index=cond_idx
            )

            try:
              v_date = datetime.strptime(
                  patient_data["visit_date"], "%Y-%m-%d"
              ).date()
            except Exception:
              v_date = datetime.today().date()

            try:
              f_date = datetime.strptime(
                  patient_data["followup_date"], "%Y-%m-%d"
              ).date()
            except Exception:
              f_date = datetime.today().date()

            e_visit_date = st.date_input("Clinic Visit Date", value=v_date)
            e_followup_date = st.date_input("Agli Follow-up Date", value=f_date)

            status_list = ["New Lead", "In Treatment", "Completed"]
            status_idx = (
                status_list.index(patient_data["status"])
                if patient_data["status"] in status_list
                else 0
            )
            e_status = st.selectbox("Status", status_list, index=status_idx)

          e_notes = st.text_area(
              "Doctor/Clinic Notes", value=patient_data["notes"]
          )

          update_button = st.form_submit_button("Record Update Karein")

          if update_button:
            with sqlite3.connect("crm.db") as conn:
              cursor = conn.cursor()
              cursor.execute(
                  """
                            UPDATE leads 
                            SET receiver_name=?, child_name=?, father_name=?, phone=?, 
                                condition=?, city=?, visit_date=?, followup_date=?, notes=?, status=?
                            WHERE id=?
                        """,
                  (
                      e_receiver_name,
                      e_child_name,
                      e_father_name,
                      e_phone,
                      e_condition,
                      e_city,
                      str(e_visit_date),
                      str(e_followup_date),
                      e_notes,
                      e_status,
                      selected_id,
                  ),
              )
              conn.commit()
            st.success(
                f"ID {selected_id} ka record safalpurvak update ho gaya hai!"
            )
            st.rerun()
      else:
        st.info("Update karne ke liye koi record nahi hai.")

    # --- TAB 3: Advanced Reports ---
    with tab3:
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
          st.write(f"**Total Patients Scheduled ({v_str}):** {len(v_filtered)}")
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
          st.write(f"**Total Follow-ups Due ({f_str}):** {len(f_filtered)}")
          if not f_filtered.empty:
            st.dataframe(f_filtered, use_container_width=True)
          else:
            st.info("Is tarikh ko koi follow-up scheduled nahi hai.")

        st.markdown("---")
        st.markdown("### 🩺 Condition-wise Patient Count")
        condition_counts = df["condition"].value_counts().reset_index()
        condition_counts.columns = ["Bimari / Condition", "Kul Bachche"]
        st.dataframe(condition_counts, use_container_width=True)
      else:
        st.info("Reports dekhne ke liye pehle records save karein.")

    # --- TAB 4: Delete Record ---
    with tab4:
      st.subheader("🗑️ Record Delete Karein")
      if not df.empty:
        del_options = {
            f"ID {row['id']} - {row['child_name']} ({row['phone']})": row["id"]
            for _, row in df.iterrows()
        }
        selected_del_label = st.selectbox(
            "Delete karne ke liye Record chunein:", list(del_options.keys())
        )
        delete_id = del_options[selected_del_label]

        if st.button("🚨 Record Hatayein", type="primary"):
          with sqlite3.connect("crm.db") as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM leads WHERE id = ?", (delete_id,))
            conn.commit()
          st.success(f"ID {delete_id} ka record delete kar diya gaya hai.")
          st.rerun()
      else:
        st.info("Delete karne ke liye koi record uplabdh nahi hai.")

  else:
    # ----------------------------------------------------
    # 🟢 LIMITED ACCESS FOR STAFF / CALL RECEIVER
    # ----------------------------------------------------
    st.subheader("📋 Patients List (Staff View)")
    st.info(
        "💡 Aap nayi entries sidebar me form bhar kar save kar sakte hain."
        " Advanced reports aur administrative control sirf HR Admin ke paas"
        " hain."
    )

    if not df.empty:
      search_query = st.text_input(
          "🔍 Search (Bachche ka Naam ya Phone number se):"
      )
      filtered_df = df.copy()
      if search_query:
        filtered_df = df[
            df["child_name"].str.contains(search_query, case=False, na=False)
            | df["phone"].str.contains(search_query, case=False, na=False)
        ]

      # Show restricted view columns to staff
      staff_view_cols = [
          "id",
          "child_name",
          "father_name",
          "phone",
          "condition",
          "visit_date",
          "followup_date",
          "status",
      ]
      st.dataframe(filtered_df[staff_view_cols], use_container_width=True)
    else:
      st.info("Abhi tak koi entry nahi hai. Sidebar se nayi entry karein.")
