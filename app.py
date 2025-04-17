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

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PdfReader(pdf_file)
        return "\n".join(page.extract_text() for page in pdf_reader.pages)
    except Exception as e:
        return f"Error extracting text: {str(e)}"

# Function to print PDF (cross-platform with enhanced handling)
def print_pdf(file_content, printer_name=None):
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        system = platform.system()
        debug_info = []
        debug_info.append(f"OS: {system}, Temp file: {temp_file_path}")

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
    except ImportError:
        debug_info.append("pywin32 not installed, using fallback method")
        return print_windows_fallback(temp_file_path, printer_name, debug_info)

    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)
    printer_names = [p[2] for p in printers]
    
    if printer_name and printer_name not in printer_names:
        raise Exception(f"Printer not found. Available printers: {', '.join(printer_names)}")
    
    if not printer_name:
        printer_name = win32print.GetDefaultPrinter()

    debug_info.append(f"Attempting to print to: {printer_name}")
    win32api.ShellExecute(0, "print", temp_file_path, f'/d:"{printer_name}"', ".", 0)
    return True, "Print job sent successfully", "\n".join(debug_info)

def print_windows_fallback(temp_file_path, printer_name, debug_info):
    cmd = ['rundll32', 'mshtml.dll', 'PrintHTML', '"', temp_file_path]
    if printer_name:
        cmd += ['/d:', printer_name]
    result = subprocess.run(cmd, capture_output=True, text=True)
    debug_info.append(f"Fallback command: {' '.join(cmd)}")
    debug_info.append(f"Exit code: {result.returncode}")
    debug_info.append(f"Output: {result.stdout}")
    debug_info.append(f"Error: {result.stderr}")
    return True, "Print job sent via fallback method", "\n".join(debug_info)

def print_unix(temp_file_path, printer_name, debug_info):
    cmd = ['lp'] + (['-d', printer_name] if printer_name else [])
    cmd.append(temp_file_path)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        debug_info.append(f"Command failed: {' '.join(cmd)}")
        debug_info.append(f"Error: {e.stderr}")
        raise Exception(f"Print failed: {e.stderr}")
    
    debug_info.append(f"Print job ID: {result.stdout.strip()}")
    return True, "Print job sent successfully", "\n".join(debug_info)

# Auto-deletion functions
def start_auto_delete(doc_id, expiry_minutes):
    def delete_job():
        time.sleep(expiry_minutes * 60)
        collection.delete_one({"_id": doc_id})
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
        </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    # Upload Portal
    with col1:
        st.markdown('<p class="big-font">Upload Your Document</p>', unsafe_allow_html=True)
        with st.container():
            uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
            expiry_time = st.slider("Set expiry time (minutes)", 1, 360, 15)

            if uploaded_file and st.button("Upload"):
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
                    
                    st.markdown(f"""
                        <div class="success-box">
                            <h3>Upload Successful!</h3>
                            <p>Your Print Code: <strong>{code}</strong></p>
                            <p>File will expire at {expiry_datetime.strftime('%Y-%m-%d %H:%M:%S')}</p>
                        </div>
                    """, unsafe_allow_html=True)

    # Printer Dashboard
    with col2:
        st.markdown('<p class="big-font">Printer Dashboard</p>', unsafe_allow_html=True)
        with st.container():
            search_code = st.text_input("Enter Print Code")
            
            if search_code and st.button("Search"):
                with st.spinner("Searching..."):
                    document = collection.find_one({"_id": search_code})
                    
                    if document:
                        time_left = (document['expiry_datetime'] - datetime.now()).total_seconds() / 60
                        st.success(f"Found: {document['filename']} (Expires in {max(0, round(time_left))} minutes)")
                        st.text_area("Preview", document["text_content"], height=200, disabled=True)
                        
                        printer_name = st.text_input("Printer Name (optional)")
                        if st.button("Print Document"):
                            with st.spinner("Printing..."):
                                success, message, debug_info = print_pdf(document["content"], printer_name)
                                if success:
                                    st.markdown(f'<div class="success-box">{message}</div>', unsafe_allow_html=True)
                                else:
                                    st.markdown(f'<div class="error-box">{message}</div>', unsafe_allow_html=True)
                                    st.text(debug_info)
                    else:
                        st.error("Invalid code or document expired")

    # Sidebar
    with st.sidebar:
        st.header("System Status")
        now = datetime.now()
        active_jobs = collection.count_documents({"expiry_datetime": {"$gt": now}})
        st.write(f"Active print jobs: {active_jobs}")
        st.write(f"Current server time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()