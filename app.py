# ... continuing from where your code cut off ...

                        city_filtered_df = df if selected_city == "Sabhi Cities" else df[df["city"] == selected_city]
                        st.dataframe(city_filtered_df, use_container_width=True)
                    else:
                        st.info("Koi city data available nahi hai.")
            else:
                st.info("Reports dekhne ke liye koi data nahi hai.")

        # -------- TAB 5: FOLLOW-UP TRACKER --------
        with tab5:
            st.subheader("📅 Active Follow-up Tracker")
            if not df.empty:
                f_status = st.radio("Filter Follow-ups:", ["Overdue", "Aaj Ke", "Agami (Upcoming)"], horizontal=True)
                
                df["followup_date_dt"] = pd.to_datetime(df["followup_date"], errors="coerce").dt.date
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
                                st.markdown(f"**{row['child_name']}** (Pita: {row['father_name'] or 'N/A'})")
                                st.caption(f"Phone: {row['phone']} | City: {row['city'] or 'N/A'} | Status: {row['status']}")
                            with c2:
                                st.markdown(f"🗓️ **Follow-up Date:** {row['followup_date']}")
                                st.caption(f"Note: {row['notes'] or 'Koi note nahi'}")
                            with c3:
                                wa_link = whatsapp_link(row["phone"], f"Namaste, {row['child_name']} ke follow-up ke baare mein reminder call/msg hai.")
                                if wa_link:
                                    st.link_button("💬 WhatsApp", wa_link, use_container_width=True)
                            st.divider()
                else:
                    st.success("Is category mein koi follow-up records nahi hain.")
            else:
                st.info("Follow-up track karne ke liye koi data nahi hai.")

        # -------- TAB 6: DELETE RECORD --------
        with tab6:
            st.subheader("🗑️ Patient Record Hatayein")
            st.warning("⚠️ Dhyan den: Yahan se delete kiya gaya record permanently hat jayega.")
            
            if not df.empty:
                delete_options = {
                    f"ID {row['id']} - {row['child_name']} ({row['phone']})": row["id"]
                    for _, row in df.iterrows()
                }
                selected_del_label = st.selectbox("Delete karne ke liye record chunein:", list(delete_options.keys()))
                del_id = delete_options[selected_del_label]

                if st.button("🗑️ Permanently Delete Karein", type="primary"):
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM leads WHERE id=?", (del_id,))
                        conn.commit()
                    st.success(f"Record ID {del_id} safalpurvak delete ho gaya hai!")
                    st.rerun()
            else:
                st.info("Delete karne ke liye koi record nahi hai.")

    # ==========================================================
    # STAFF / RECEIVER VIEW
    # ==========================================================
    else:
        st.subheader("📋 Patient Entries & Quick Follow-up Tracker")
        
        tab_s1, tab_s2 = st.tabs(["📋 Meri/Sabhi Entries", "📞 Today's Follow-ups"])

        with tab_s1:
            st.markdown("#### Patient Records")
            search_query_staff = st.text_input("🔍 Search (Naam, Phone, ya City से):")
            
            filtered_df_staff = df.copy()
            if search_query_staff:
                filtered_df_staff = df[
                    df["child_name"].str.contains(search_query_staff, case=False, na=False)
                    | df["phone"].str.contains(search_query_staff, case=False, na=False)
                    | df["city"].str.contains(search_query_staff, case=False, na=False)
                ]
            
            st.dataframe(filtered_df_staff, use_container_width=True, height=400)

        with tab_s2:
            st.markdown("#### 📞 Aaj Ke Due Follow-ups")
            due_today_staff = df[df["followup_date"] == today_str]
            
            if not due_today_staff.empty:
                for _, row in due_today_staff.iterrows():
                    with st.container():
                        col_a, col_b = st.columns([3, 1])
                        with col_a:
                            st.markdown(f"**{row['child_name']}** — {row['phone']}")
                            st.caption(f"Condition: {row['condition']} | City: {row['city']} | Notes: {row['notes']}")
                        with col_b:
                            wa_url_s = whatsapp_link(row["phone"], f"Namaste, {row['child_name']} ke clinic visit ke baare mein updates lene the.")
                            if wa_url_s:
                                st.link_button("💬 Message", wa_url_s, use_container_width=True)
                        st.divider()
            else:
                st.success("Aaj ke liye koi pending follow-up nahi hai! 🎉")
