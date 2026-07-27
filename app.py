import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="Special Child Clinic CRM", layout="wide")

# Database Setup
def init_db():
    conn = sqlite3.connect('crm.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
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
    ''')
    conn.commit()
    conn.close()

init_db()

# Title
st.title("🏥 Special Child Clinic CRM")

# Sidebar - Nayi Entry Jodne ke liye Form
st.sidebar.header("➕ Nayi Entry Jodein")

with st.sidebar.form("entry_form", clear_on_submit=True):
    receiver_name = st.text_input("Call Receiver ka Naam")
    child_name = st.text_input("Bachche ka Naam")
    father_name = st.text_input("Pita ka Naam")
    phone = st.text_input("Mobile Number")
    
    condition = st.selectbox("Condition Chunein", [
        "Autism (ASD)", "ADHD", "Learning Disability", 
        "Speech Delay", "Intellectual Disability", 
        "Down Syndrome", "Cerebral Palsy", "Other"
    ])
    
    city = st.text_input("City (Shehar)")
    visit_date = st.date_input("Clinic Aane ki Date", value=datetime.today())
    followup_date = st.date_input("Aagli Follow-up Date", value=datetime.today())
    notes = st.text_area("Doctor/Clinic Notes (Khaas baatein)")
    status = st.selectbox("Status", ["New Lead", "In Treatment", "Completed"])
    
    submit_button = st.form_submit_button(label="Record Save Karein")
    
    if submit_button:
        if receiver_name and child_name and phone:
            conn = sqlite3.connect('crm.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO leads (receiver_name, child_name, father_name, phone, condition, city, visit_date, followup_date, notes, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (receiver_name, child_name, father_name, phone, condition, city, str(visit_date), str(followup_date), notes, status))
            conn.commit()
            conn.close()
            st.sidebar.success("Record Safalpurvak Save Ho Gaya!")
        else:
            st.sidebar.error("Kripya Receiver ka Naam, Bachche ka Naam aur Phone Number bharein.")

# Main Screen Tabs (Navigation ke liye)
tab1, tab2, tab3 = st.tabs(["📋 Patients List & Summary", "📊 Advanced Reports", "🗑️ Delete Record"])

# --- TAB 1: Patients List & Search ---
with tab1:
    st.subheader("📋 Sabhi Patients ki List")
    
    conn = sqlite3.connect('crm.db')
    df = pd.read_sql("SELECT * FROM leads ORDER BY id DESC", conn)
    conn.close()

    if not df.empty:
        # Call Receiver Summary
        st.markdown("### 📊 Call Receiver Performance")
        receiver_counts = df['receiver_name'].value_counts().reset_index()
        receiver_counts.columns = ['Receiver Naam', 'Kul Calls/Entries']
        st.dataframe(receiver_counts, use_container_width=True)
        
        st.markdown("---")

        # Search Box
        search_query = st.text_input("🔍 Records Dhoondhein (Naam, City ya Receiver se):")
        filtered_df = df.copy()
        if search_query:
            filtered_df = df[df['child_name'].str.contains(search_query, case=False, na=False) | 
                             df['city'].str.contains(search_query, case=False, na=False) | 
                             df['receiver_name'].str.contains(search_query, case=False, na=False)]
        
        st.dataframe(filtered_df, use_container_width=True)
    else:
        st.info("Abhi tak koi record nahi hai.")

# --- TAB 2: Advanced Reports (Date-wise & Follow-ups) ---
with tab2:
    st.subheader("📈 Zaroori Reports aur Analysis")
    
    conn = sqlite3.connect('crm.db')
    report_df = pd.read_sql("SELECT * FROM leads", conn)
    conn.close()

    if not report_df.empty:
        # 1. Date-wise Lead Report (Clinic Visit Date ke anusar)
        st.markdown("### 📅 Date-wise Clinic Visit Report")
        selected_visit_date = st.date_input("Clinic Visit Date chunein:", value=datetime.today())
        
        # Date ko string format mein convert karke filter karein
        date_str = str(selected_visit_date)
        date_filtered = report_df[report_df['visit_date'] == date_str]
        
        st.write(f"**Tarikha ({date_str}) ko aane wale patients:** {len(date_filtered)}")
        if not date_filtered.empty:
            st.dataframe(date_filtered, use_container_width=True)
        else:
            st.info("Is tarikh ko koi visit scheduled nahi hai.")

        st.markdown("---")

        # 2. Follow-up Report
        st.markdown("### 📞 Follow-up Report (Aagli Date)")
        selected_follow_date = st.date_input("Follow-up Date chunein:", value=datetime.today(), key="follow_date_picker")
        
        follow_str = str(selected_follow_date)
        follow_filtered = report_df[report_df['followup_date'] == follow_str]
        
        st.write(f"**Tarikha ({follow_str}) ko hone wale follow-ups:** {len(follow_filtered)}")
        if not follow_filtered.empty:
            st.dataframe(follow_filtered, use_container_width=True)
        else:
            st.info("Is tarikh ko koi follow-up nahi hai.")

        st.markdown("---")

        # 3. Condition/Bimari wise Summary Report
        st.markdown("### 🩺 Condition-wise Patient Count")
        if 'condition' in report_df.columns:
            condition_counts = report_df['condition'].value_counts().reset_index()
            condition_counts.columns = ['Bimari / Condition', 'Kul Bachche']
            st.dataframe(condition_counts, use_container_width=True)

    else:
        st.info("Report dekhne ke liye pehle kuch entries save karein.")

# --- TAB 3: Delete Section ---
with tab3:
    st.subheader("🗑️ Record Delete Karein")
    conn = sqlite3.connect('crm.db')
    del_df = pd.read_sql("SELECT id, child_name, phone FROM leads", conn)
    conn.close()
    
    if not del_df.empty:
        st.dataframe(del_df, use_container_width=True)
        delete_id = st.number_input("Delete karne ke liye Sahi ID dalein:", min_value=0, step=1)
        if st.button("Record Hatayein"):
            if delete_id > 0:
                conn = sqlite3.connect('crm.db')
                cursor = conn.cursor()
                cursor.execute("DELETE FROM leads WHERE id = ?", (delete_id,))
                conn.commit()
                conn.close()
                st.success(f"ID {delete_id} ko safalpurvak hata diya gaya hai! Kripya page refresh karein.")
    else:
        st.info("Delete karne ke liye koi record uplabdh nahi hai.")
