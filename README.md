# Secureprint
# Secure Cloud-Based Print Solution 🖨️☁️

A privacy-first document printing system that eliminates the need to share sensitive files over personal platforms like WhatsApp. This system allows users to securely upload PDFs and retrieve them using a unique print code — all with automatic expiry and complete control.

---

## 🚩 Problem Statement

In India and many other countries, people often share their documents for printing through WhatsApp or other social apps. This practice compromises **data privacy** and opens up risks of **document misuse**, **unauthorized access**, or **unethical retention** of files by third parties.

**Goal:** To create a convenient yet secure print-sharing system where users do **not** have to share their documents on personal messaging platforms.

---

## ✅ Proposed Solution

This application allows users to upload their PDF files through a web interface built with **Streamlit**. A unique **print code** is generated, which can be used at the printer’s end to retrieve and print the document.

Key features:

- 🔐 No sharing via WhatsApp or personal platforms
- ⏳ Documents auto-delete after a user-defined expiry time
- 📄 PDF content preview before printing
- 🖨️ OS-level printing support (Windows, Linux, macOS)
- 📁 MongoDB backend to securely store file metadata and content
- 🧼 Background job scheduler to clean up expired jobs

---

## 🚀 Tech Stack

| Component      | Technology                  |
|----------------|------------------------------|
| Frontend       | Streamlit                    |
| Backend        | Python                       |
| Database       | MongoDB                      |
| Scheduler      | APScheduler (background jobs)|
| PDF Handling   | PyPDF2                       |
| OS Printing    | subprocess, win32print (Windows), lp (Linux/macOS) |
| Deployment     | Localhost / Can be Dockerized or hosted on cloud platforms |

---

## ☁️ Why This is a Cloud-Based Secure Solution

- **Cloud Storage**: Documents are stored temporarily in a MongoDB database hosted on a server (can be cloud-deployed).
- **Remote Access**: The print portal can be accessed from any location—home, office, cyber café, etc.
- **No Data Leaks**: Documents are never transferred over personal platforms like WhatsApp, reducing privacy threats.
- **Auto Deletion**: Files are scheduled for deletion after a configurable expiry time to avoid misuse.
- **Security First**: Only people with the correct print code can access the file — no signup/login needed.

---

## 🧠 How it Works

1. **Upload Phase**
   - User uploads a PDF and selects an expiry time.
   - File is saved in MongoDB with a unique `PRNTXXXX` code.
   - Text is extracted using PyPDF2 for previewing.

2. **Printer Side**
   - Operator enters the code.
   - Document is fetched and previewed.
   - A print job is initiated to the default or specified printer.
   - Debug info is shown for troubleshooting if needed.

3. **Cleanup**
   - APScheduler runs every minute to remove expired documents.
   - Additionally, each file is tracked using a background thread for expiry.

---

## 💻 Code Structure

```bash
.
├── app.py                  # Main Streamlit App
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
