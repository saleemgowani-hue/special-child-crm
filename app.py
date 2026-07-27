import streamlit as st
import pandas as pd
import os
from datetime import date

# Page Configuration
st.set_page_config(page_title="Normal Child Clinic CRM", page_icon="🏥", layout="wide")

# File path for storing patient data locally
DATA_FILE = "patients.csv"

# Function to load patient data
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=[
            "child_name", "father_name", "phone", "condition",
            "city", "visit_date", "followup_date", "notes"
        ])

# Function to save patient data
def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# App Title (Updated Heading)
st.title("🏥 Normal Child Clinic CRM")

# ---------------- SIDEBAR: Add Patient ----------------
st.sidebar.header("📝 Naya Patient Add Karein")

child_name = st.sidebar.text_input("Child Name (Bache ka Naam)")
father_name = st.sidebar.text_input("Father Name (Pita ka Naam)")
phone = st.sidebar.text_input("Phone Number")
condition = st.sidebar.selectbox("Condition Chunein", ["Normal", "Autism (ASD)", "ADHD", "Speech Delay", "Other"])
city = st.sidebar.text_input("City (Shehar)")
visit_date = st.sidebar.date_input("Clinic Aane ki Date", date.today())
followup_date = st.sidebar.date_input("Agli Follow-up Date", date.today())
notes = st.sidebar.text_area("Doctor/Clinic Notes (Khaas baatein)")

if st.sidebar.button("Patient Save Karein"):
    if child_name and phone:
        df = load_data()
        new_row = pd.DataFrame([{
            "child_name": child_name,
            "father_name": father_name,
            "phone": phone,
            "condition": condition,
            "city": city,
            "visit_date": str(visit_date),
            "followup_date": str(followup_date),
            "notes": notes
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df)
        st.sidebar.success("Record Safaltapoorvak Save Ho Gaya!")
        st.rerun()
    else:
        st.sidebar.error("Kripya Child Name aur Phone Number zaroor bharein!")

# ---------------- TABS: Main Layout ----------------
tab1, tab2, tab3 = st.tabs(["📋 Patients List & Summary", "📊 Advanced Reports", "🗑️ Delete Record"])

df = load_data()

# TAB 1: Patients List & Summary
with tab1:
    st.subheader("📋 Sabhi Patients ki List")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Abhi tak koi record nahi hai.")

# TAB 2: Advanced Reports
with tab2:
    st.subheader("📈 Zaroori Reports aur Analysis")
    st.markdown("### 📅 Date-wise Clinic Visit Report")
    
    selected_date = st.date_input("Clinic Visit Date chunein:", date.today())
    
    if not df.empty:
        filtered_df = df[df["visit_date"] == str(selected_date)]
        st.write(f"**Tarikh ({selected_date}) ko aane wale patients:**")
        if not filtered_df.empty:
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.info(f"Tarikh {selected_date} ko koi patient nahi aaya.")
    else:
        st.info("Abhi tak koi record nahi hai.")

# TAB 3: Delete Record
with tab3:
    st.subheader("🗑️ Delete Record")
    if not df.empty:
        options = [f"{row['child_name']} - {row['phone']}" for _, row in df.iterrows()]
        patient_to_delete = st.selectbox("Delete karne ke liye Patient chunein:", options)
        
        if st.button("Delete Selected Patient"):
            phone_to_del = patient_to_delete.split(" - ")[-1]
            df = df[df["phone"].astype(str) != str(phone_to_del)]
            save_data(df)
            st.success("Record successfully delete ho gaya!")
            st.rerun()
    else:
        st.info("Delete karne ke liye koi record nahi hai.")
