import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# 1. Page Configuration (Browser Tab Title)
st.set_page_config(
    page_title="Normal Child Clinic CRM", page_icon="🏥", layout="wide"
)


# 2. Database Initialization
def init_db():
  with sqlite3.connect("crm.db") as conn:
    cursor = conn.cursor()
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
    conn.commit()


init_db()

# 3. Application Main Title
st.title("🏥 Normal Child Clinic CRM")
st.markdown("---")

# 4. Sidebar - Add New Lead
st.sidebar.header("➕ Nayi Entry Jodein")

with st.sidebar.form("entry_form", clear_on_submit=True):
  receiver_name = st.text_input("Call Receiver ka Naam *")
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
      st.rerun()  # Screen update hone ke liye auto-refresh
    else:
      st.sidebar.error(
          "Kripya Receiver ka Naam, Bachche ka Naam aur Phone Number bharein."
      )

# Current Records Read Karein
with sqlite3.connect("crm.db") as conn:
  df = pd.read_sql("SELECT * FROM leads ORDER BY id DESC", conn)

today_str = str(datetime.today().date())

# 5. Main Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Patients Dashboard",
    "✏️ Edit / Update Record",
    "📊 Advanced Reports",
    "🗑️ Delete Record",
])

# --- TAB 1: Patients Dashboard ---
with tab1:
  # Quick Metrics Bar
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

    # Call Receiver Summary
    st.markdown("### 📊 Call Receiver Performance")
    receiver_counts = df["receiver_name"].value_counts().reset_index()
    receiver_counts.columns = ["Receiver Naam", "Kul Calls / Entries"]
    st.dataframe(receiver_counts, use_container_width=True)
  else:
    st.info("Abhi tak koi record nahi hai. Sidebar se nayi entry add karein.")

# --- TAB 2: Edit / Update Record ---
with tab2:
  st.subheader("✏️ Existing Patient Record Update Karein")

  if not df.empty:
    patient_options = {
        f"ID {row['id']} - {row['child_name']} ({row['phone']})": row["id"]
        for _, row in df.iterrows()
    }
    selected_patient_label = st.selectbox(
        "Update karne ke liye Patient chunein:", list(patient_options.keys())
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
        e_phone = st.text_input("Mobile Number", value=patient_data["phone"])
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

      e_notes = st.text_area("Doctor/Clinic Notes", value=patient_data["notes"])

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
