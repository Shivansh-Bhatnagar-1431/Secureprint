import streamlit as st
from pymongo import MongoClient
import time
from datetime import datetime, timedelta
import io
import os
import subprocess
import platform
from PyPDF2 import PdfReader
import tempfile
import threading
from apscheduler.schedulers.background import BackgroundScheduler

# MongoDB Connection
client = MongoClient("mongodb://localhost:27017/")
db = client["secure_printing"]
collection = db["print_jobs"]

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Session state initialization
if 'print_status' not in st.session_state:
    st.session_state.print_status = None
if 'debug_info' not in st.session_state:
    st.session_state.debug_info = ""

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PdfReader(pdf_file)
        return "\n".join(page.extract_text() for page in pdf_reader.pages)
    except Exception as e:
        return f"Error extracting text: {str(e)}"

# Enhanced printing function
def print_pdf(file_content, printer_name=None):
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        system = platform.system()
        debug_info = []
        debug_info.append(f"System: {system}")
        debug_info.append(f"Temporary file created at: {temp_file_path}")

        if system == "Windows":
            return print_windows(temp_file_path, printer_name, debug_info)
        elif system in ["Linux", "Darwin"]:
            return print_unix(temp_file_path, printer_name, debug_info)
        else:
            raise Exception("Unsupported operating system")

    except Exception as e:
        error_msg = f"Print failed: {str(e)}"
        debug_info.append(error_msg)
        return False, error_msg, "\n".join(debug_info)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def print_windows(temp_file_path, printer_name, debug_info):
    try:
        import win32print
        import win32api
        
        # Get available printers
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)
        printer_names = [p[2] for p in printers]
        debug_info.append(f"Available printers: {', '.join(printer_names)}")

        # Validate printer
        if printer_name and printer_name not in printer_names:
            raise Exception(f"Printer '{printer_name}' not found. Available printers: {', '.join(printer_names)}")
        
        # Use default printer if none specified
        if not printer_name:
            printer_name = win32print.GetDefaultPrinter()
            debug_info.append(f"Using default printer: {printer_name}")

        # Print using ShellExecute
        debug_info.append(f"Attempting to print to: {printer_name}")
        win32api.ShellExecute(0, "print", temp_file_path, f'/d:"{printer_name}"', ".", 0)
        return True, "Print job sent successfully", "\n".join(debug_info)

    except Exception as e:
        debug_info.append(f"Windows print error: {str(e)}")
        return False, f"Print failed: {str(e)}", "\n".join(debug_info)

def print_unix(temp_file_path, printer_name, debug_info):
    try:
        cmd = ['lp'] + (['-d', printer_name] if printer_name else [])
        cmd.append(temp_file_path)
        debug_info.append(f"Print command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        
        debug_info.append(f"Command output: {result.stdout.strip()}")
        return True, "Print job sent successfully", "\n".join(debug_info)

    except subprocess.CalledProcessError as e:
        debug_info.append(f"Command failed: {e.stderr.strip()}")
        return False, f"Print failed: {e.stderr.strip()}", "\n".join(debug_info)
    except Exception as e:
        debug_info.append(f"Unix print error: {str(e)}")
        return False, f"Print failed: {str(e)}", "\n".join(debug_info)

# Auto-deletion functions
def start_auto_delete(doc_id, expiry_minutes):
    def delete_job():
        time.sleep(expiry_minutes * 60)
        collection.delete_one({"_id": doc_id})
        st.cache_data.clear()
    threading.Thread(target=delete_job, daemon=True).start()

def setup_scheduled_cleanup():
    def cleanup_expired_jobs():
        now = datetime.now()
        collection.delete_many({"expiry_datetime": {"$lte": now}})
    
    scheduler.add_job(
        cleanup_expired_jobs,
        'interval',
        minutes=1,
        id='cleanup_job'
    )

# Initialize scheduled cleanup
setup_scheduled_cleanup()

# Main App
def main():
    st.set_page_config(page_title="Secure Print Solution", layout="wide")
    
    # Custom CSS
    st.markdown("""
        <style>
        .big-font { font-size:20px !important; font-weight: bold; }
        .success-box { background-color: #e6ffe6; padding: 10px; border-radius: 5px; }
        .error-box { background-color: #ffe6e6; padding: 10px; border-radius: 5px; }
        .debug-info { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    # Upload Portal
    with col1:
        st.markdown('<p class="big-font">Upload Your Document</p>', unsafe_allow_html=True)
        with st.form("upload_form"):
            uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
            expiry_time = st.slider("Set expiry time (minutes)", 1, 360, 15)
            
            if st.form_submit_button("Upload"):
                if uploaded_file:
                    with st.spinner("Uploading..."):
                        code = f"PRNT{int(time.time())}"
                        file_content = uploaded_file.getvalue()
                        expiry_datetime = datetime.now() + timedelta(minutes=expiry_time)
                        
                        doc = {
                            "_id": code,
                            "filename": uploaded_file.name,
                            "content": file_content,
                            "text_content": extract_text_from_pdf(io.BytesIO(file_content)),
                            "upload_time": datetime.now(),
                            "expiry_time": expiry_time,
                            "expiry_datetime": expiry_datetime
                        }
                        collection.insert_one(doc)
                        start_auto_delete(code, expiry_time)
                        
                        st.session_state.upload_code = code
                        st.success(f"Upload Successful! Print Code: {code}")

    # Printer Dashboard
    with col2:
        st.markdown('<p class="big-font">Printer Dashboard</p>', unsafe_allow_html=True)
        with st.form("print_form"):
            search_code = st.text_input("Enter Print Code", value=getattr(st.session_state, 'upload_code', ''))
            
            if st.form_submit_button("Search"):
                if search_code:
                    with st.spinner("Searching..."):
                        document = collection.find_one({"_id": search_code})
                        
                        if document:
                            st.session_state.current_doc = document
                            time_left = (document['expiry_datetime'] - datetime.now()).total_seconds() / 60
                            st.success(f"Found: {document['filename']} (Expires in {max(0, round(time_left))} minutes)")
                        else:
                            st.error("Invalid code or document expired")

        if hasattr(st.session_state, 'current_doc'):
            with st.expander("Document Preview", expanded=True):
                st.text_area("Content", st.session_state.current_doc["text_content"], height=200, disabled=True)
                
                with st.form("print_job_form"):
                    printer_name = st.text_input("Printer Name (optional)", help="Leave blank for default printer")
                    
                    if st.form_submit_button("Print Document"):
                        with st.spinner("Printing..."):
                            document = st.session_state.current_doc
                            success, message, debug_info = print_pdf(document["content"], printer_name)
                            
                            st.session_state.print_status = success
                            st.session_state.debug_info = debug_info
                            
                            if success:
                                st.success("Print job initiated successfully!")
                            else:
                                st.error("Print failed")

    # Print status and debug information
    if st.session_state.print_status is not None:
        with st.expander("Printing Details", expanded=not st.session_state.print_status):
            if st.session_state.print_status:
                st.markdown(f'<div class="success-box">✅ {st.session_state.debug_info}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="error-box">❌ {st.session_state.debug_info}</div>', unsafe_allow_html=True)
                st.markdown("**Troubleshooting Tips:**")
                st.write("""
                - Verify printer name matches exactly with system printers
                - Ensure printer is online and has paper
                - Check printer permissions
                - For Windows: Try specifying printer name
                - For Linux/macOS: Ensure CUPS is installed and configured
                """)

    # System status sidebar
    with st.sidebar:
        st.header("System Status")
        now = datetime.now()
        active_jobs = collection.count_documents({"expiry_datetime": {"$gt": now}})
        st.metric("Active Print Jobs", active_jobs)
        st.write(f"Current server time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if st.button("Refresh Status"):
            st.experimental_rerun()

if __name__ == "__main__":
    main()