import streamlit as st
import gspread
import time

# --- CONFIGURATION ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/19KF5a8XCvLGVdpUzvUK70iAzeVBa6itD8CEHA20cD6A/edit?gid=0"

# --- SESSION STATE INITIALIZATION (Must be first) ---
# Initialize all keys if they don't exist
default_values = {
    'pres_id': "",
    'raw_name': "",
    'mrn': "",
    'sep': "",
    'iter_box': "Tanpa Iterasi",
    'detur_box': "Ne Detur",
    'success_msg': None,
    'trigger_reset': False,       # For partial reset (ID only)
    'trigger_full_reset': False   # For full reset (All fields)
}

for key, value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- RESET LOGIC HANDLERS ---
# 1. Full Reset (Clears Everything)
if st.session_state.trigger_full_reset:
    st.session_state.raw_name = ""
    st.session_state.mrn = ""
    st.session_state.sep = ""
    st.session_state.pres_id = ""
    st.session_state.iter_box = "Tanpa Iterasi"
    st.session_state.detur_box = "Ne Detur"
    st.session_state.trigger_full_reset = False # Turn off flag

# 2. Partial Reset (Clears ID only - for successful save)
if st.session_state.trigger_reset:
    st.session_state.pres_id = ""
    st.session_state.trigger_reset = False 

# --- AUTHENTICATION ---
@st.cache_resource
def get_worksheet():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("❌ Error: 'gcp_service_account' missing in secrets.")
            return None
        creds_dict = dict(st.secrets["gcp_service_account"])
        client = gspread.service_account_from_dict(creds_dict)
        return client.open_by_url(SHEET_URL).worksheet("main")
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

# --- HELPER FUNCTIONS ---
def get_next_id(sheet):
    try:
        return len(sheet.col_values(1)) 
    except:
        return 1

def check_duplicate(sheet, new_pres_id):
    try:
        existing_ids = sheet.col_values(6) 
        return new_pres_id in existing_ids
    except:
        return False

# --- APP UI ---
st.title("🏥 Input Data Resep")

# Display Success Message (if any)
if st.session_state.success_msg:
    st.success(st.session_state.success_msg)
    st.session_state.success_msg = None 

# --- FORM START ---
# Note: We bind every widget to a key in session_state so we can reset them
with st.form("entry_form"):
    st.info("💡 ID will be generated automatically upon save.")

    dttm = st.date_input("Tanggal Resep") # Date usually defaults to today, so we don't reset it
    
    # We use key='raw_name' to allow resetting
    raw_name = st.text_input("Nama Pasien (ex: PANCA WISANTA)", key="raw_name")
    name = raw_name.upper() if raw_name else ""
    
    mrn = st.text_input("Nomor Rekam Medis (6 Digit)", max_chars=6, key="mrn")
    sep = st.text_input("Nomor SEP (19 Digit)", max_chars=19, key="sep")
    
    st.markdown("---")
    
    pres_id = st.text_input("Nomor Resep (14 Digit)", max_chars=14, key="pres_id")
    
    iter_status = st.selectbox("Iterasi", ["Tanpa Iterasi", "Diperbolehkan Iterasi 1 Kali", "Diperbolehkan Iterasi 2 Kali"], key="iter_box")
    detur_status = st.selectbox("Detur", ["Ne Detur", "Detur Orig", "Detur Iter 1x", "Detur Iter 2x"], key="detur_box") 
    
    # Column layout for buttons
    col_submit, col_reset = st.columns([1, 1])
    
    with col_submit:
        submitted = st.form_submit_button("💾 Simpan Data", type="primary")
    
    with col_reset:
        # Form reset button inside a form is tricky. 
        # Usually, a secondary submit button acts as a submit too.
        # We will handle the logic below.
        reset_clicked = st.form_submit_button("🔄 Reset Form", type="secondary")

    if reset_clicked:
        st.session_state.trigger_full_reset = True
        st.rerun()

    if submitted:
        # --- BLOCKING UI WITH SPINNER ---
        # This spinner blocks the UI logic until done
        with st.spinner("⏳ Sedang menyimpan data... Mohon tunggu..."):
            
            # --- VALIDATION ---
            errors = []
            if not name: errors.append("❌ Nama Pasien wajib diisi.")
            if len(mrn) != 6 or not mrn.isdigit(): errors.append("❌ Nomor RM harus tepat 6 angka.")
            if len(sep) != 19: errors.append("❌ Nomor SEP harus tepat 19 karakter.")
            if len(pres_id) != 14 or not pres_id.isdigit(): errors.append("❌ Nomor Resep harus tepat 14 angka.")

            if errors:
                for error in errors:
                    st.error(error)
            else:
                sheet = get_worksheet()
                if sheet:
                    if check_duplicate(sheet, pres_id):
                        st.error(f"⛔ DATA GANDA: Nomor Resep {pres_id} sudah ada!")
                    else:
                        # Save Logic
                        next_id = get_next_id(sheet)
                        row = [next_id, str(dttm), name, mrn, sep, pres_id, iter_status, detur_status]
                        
                        try:
                            sheet.append_row(row)
                            
                            # Success! Set flags for next run
                            st.session_state.success_msg = f"✅ Data Saved! ID: {next_id}"
                            st.session_state.trigger_reset = True # Only clears ID
                            
                            time.sleep(0.5) # Slight delay so user sees the spinner finish
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Save Failed: {e}")