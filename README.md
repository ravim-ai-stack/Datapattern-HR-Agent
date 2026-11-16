# 🏢 DataPattern HR Automation Agent

> A Flask + HTML/CSS/JS HR automation portal for generating offer letters — fully integrated with **Microsoft 365** via the **Microsoft Graph API**.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Azure AD App Registration](#azure-ad-app-registration)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Using the Application](#using-the-application)
  - [Offer Letter Generator](#offer-letter-generator)
- [Environment Variables Reference](#environment-variables-reference)
- [Troubleshooting](#troubleshooting)

---

## Overview

The **DataPattern HR Automation Agent** is an internal HR tool built with a Flask backend and a plain HTML/CSS/JS frontend. It eliminates manual HR paperwork by automating:

1. **Offer Letter Generation** — Fill a DOCX template with candidate details, preview & edit the email body, and dispatch it via Microsoft Outlook (Graph API).

The module is powered by the **Microsoft Graph API** using an **Azure Active Directory Application (Client Credentials)** permission — no user login required.

---

## Features

### 📝 Offer Letter Generator
- Fill in candidate details into a pre-built DOCX template
- Preview and customize the email body before dispatch
- Download the generated DOCX offer letter
- Send the finalized letter as an email attachment via Microsoft Graph
- Supports CC recipients and custom welcome messages
- Email validation for all address fields

---

## Architecture

```
Browser (HTML/CSS/JS)
        │  fetch() calls
        ▼
main.py  (Flask app, error handlers)
        │
        ▼
src/routes/         HTTP layer: request parsing and responses only
        │
        ▼
src/services/       Business logic: drafts, documents, previews, exports, email
        │
        ▼
src/repositories/   Data access: letter templates on disk, outgoing mail
        │
        ▼
src/database/       Microsoft Graph connection (Singleton, token caching)
```

Shared by every layer: `src/settings` (env config), `src/constants`, `src/utils` (logger, `AppException`, error codes and mappers, validators).

**Authentication Flow:** Azure AD Client Credentials → Bearer Token → Microsoft Graph API v1.0

---

## Project Structure

```
HR-Agent-Microsoft/
│
├── main.py                          # Application entry point (Flask app factory)
│
├── src/
│   ├── routes/                      # HTTP layer
│   │   ├── page_routes.py           #   /, /step1 .. /step4 pages
│   │   ├── letter_routes.py         #   /api/generate-draft, /update-draft, /download
│   │   └── email_routes.py          #   /api/send-email
│   │
│   ├── services/                    # Business logic
│   │   ├── draft_service.py         #   create / update drafts, build downloads
│   │   ├── letter_service.py        #   filled template text, blocks, validation
│   │   ├── document_service.py      #   .docx fill, footer, layout fixes, edit patching
│   │   ├── preview_service.py       #   HTML previews
│   │   ├── export_service.py        #   Word / PDF / JPEG output
│   │   ├── certificate_service.py   #   internship certificate image
│   │   └── email_service.py         #   email bodies + dispatch via Graph
│   │
│   ├── repositories/                # Data access
│   │   ├── template_repository.py   #   letter templates (src/static/letter_templates)
│   │   └── mail_repository.py       #   Graph sendMail + inline logo
│   │
│   ├── database/
│   │   └── database.py              # Microsoft Graph connection -- Singleton
│   │
│   ├── utils/
│   │   ├── logger.py                # Centralized logger
│   │   ├── custom_app_exception.py  # AppException base class
│   │   ├── error_codes.py           # Error code constants
│   │   ├── error_mappers.py         # Error code -> HTTP status + JSON body
│   │   ├── validators.py            # Shared request validation
│   │   ├── fonts.py                 # Pillow font loading
│   │   └── letter_text.py           # Small text helpers
│   │
│   ├── settings/
│   │   └── settings.py              # Pydantic BaseSettings + load_dotenv()
│   │
│   ├── constants/
│   │   └── constants.py             # Status codes, letter types, layout constants
│   │
│   ├── templates/                   # Jinja pages (step1 .. step4)
│   └── static/                      # css, js, img, letter_templates/*.docx
│
├── .env                             # Environment variables (never commit)
├── .env.example                     # Template showing required keys
├── requirements.txt
├── Dockerfile / render.yaml / vercel.json
└── README.md
```

---

## Prerequisites

Before you begin, ensure you have the following:

| Requirement | Version / Details |
|---|---|
| **Python** | 3.9 or higher |
| **pip** | Latest version |
| **Microsoft 365 tenant** | Admin access required |
| **Azure Portal access** | To register the app |

---

## Azure AD App Registration

This is the most critical setup step. The application authenticates using the **Client Credentials (app-only)** flow, meaning it acts as itself rather than impersonating a user.

### Step 1 — Register a New App

1. Go to [https://portal.azure.com](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
4. Enter a name (e.g., `HR-Agent-Microsoft`)
5. Under **Supported account types**, select **Accounts in this organizational directory only**
6. Leave the **Redirect URI** blank (not needed for client credentials)
7. Click **Register**

### Step 2 — Note Your IDs

After registration, from the **Overview** page, copy and save:

- **Application (client) ID** → `AZURE_CLIENT_ID`
- **Directory (tenant) ID** → `AZURE_TENANT_ID`

### Step 3 — Create a Client Secret

1. In your app, go to **Certificates & secrets**
2. Click **New client secret**
3. Enter a description (e.g., `HR Agent Secret`) and choose an expiry
4. Click **Add**
5. **Copy the `Value` immediately** — it is only shown once → `AZURE_CLIENT_SECRET`

> ⚠️ **Warning:** Store the client secret securely. If you miss copying it, you must create a new one.

### Step 4 — Grant API Permissions

1. Go to **API permissions** → **Add a permission** → **Microsoft Graph** → **Application permissions**
2. Add the following permission:

| Permission | Reason |
|---|---|
| `Mail.Send` | Send offer letter emails |

3. Click **Grant admin consent for [Your Tenant]** — a Global Administrator must do this.

> ✅ After granting, the permission should show a green ✔ under the **Status** column.

---

## Installation

### Step 1 — Create and Activate a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---|---|
| `flask>=3.0.0` | Web server & API routes |
| `msal>=1.28.0` | Microsoft Authentication Library (Azure AD token) |
| `requests>=2.31.0` | HTTP calls to Microsoft Graph API |
| `python-dotenv>=1.0.0` | Load environment variables from `.env` |

---

## Configuration

### Step 1 — Create the `.env` File

Create a file named `.env` in the **root** of the project (same level as `main.py`):

```bash
# On Windows PowerShell:
New-Item -Name ".env" -ItemType "file"

# On macOS/Linux:
touch .env
```

### Step 2 — Fill in Your Credentials

Open `.env` in a text editor and add the following:

```env
# ─── Azure AD Credentials (from App Registration) ───────────────────────────
AZURE_TENANT_ID="your-tenant-id-here"
AZURE_CLIENT_ID="your-client-id-here"
AZURE_CLIENT_SECRET="your-client-secret-value-here"

# ─── Email Configuration ─────────────────────────────────────────────────────
# The authorized mailbox used to send offer letters (must have Mail.Send permission)
SYSTEM_SENDER_EMAIL="hr@yourdomain.com"
```

> ⚠️ **Security:** The `.env` file is listed in `.gitignore`. **Never commit it to version control.**

### Step 3 — Verify the DOCX Template

Ensure the offer letter template file exists at:
```
```

The template must contain these placeholder tokens in its text:

| Placeholder | Replaced With |
|---|---|
| `{{name}}` | Candidate full name (e.g., `Mr. Arjun Sharma`) |
| `{{role}}` | Job designation (bolded in the DOCX) |
| `{{location}}` | Office/work location |
| `{{date}}` | Offer date (DD-MM-YYYY) |
| `{{joining_date}}` | Joining date (DD-MM-YYYY) |
| `{{hr_name}}` | HR signatory name |
| `{{hr_department}}` | HR department name |
| `Dear {{name}},` | Salutation line |

---

## Running the Application

Once configured, start the Flask app with:

```bash
python main.py
```

The app will be available at:
- **Local:** `http://localhost:5000`
- **Network:** `http://<your-machine-ip>:5000`

---

## Using the Application

### Offer Letter Generator

The Offer Letter module is a **3-step tabbed workflow**.

#### Step 1 — Details & Generate

1. Select the candidate's **Title** (Mr. / Ms. / Mrs. / Dr.)
2. Enter the **Full Name** *(required)*
3. Enter the **Role / Designation** *(required)*
4. Enter the **Location**
5. Select the **Offer Date** and **Joining Date** using the date pickers (DD-MM-YYYY format)
6. Click **Generate Draft**

> ✅ On success, the DOCX is generated in memory and you'll see a confirmation message. Proceed to Step 2.

#### Step 2 — Email Body Preview

1. The **Receiver Name** and **Welcome Message** are pre-filled from Step 1
2. You can customize both fields freely
3. Click **Save Email Body** to lock in your changes
4. Use **⬇️ Download Generated DOCX** to download a copy of the draft for review/signing

#### Step 3 — Finalize & Send

1. **Upload the final signed document** (DOCX or PDF, max 10 MB)
2. Enter the **Sender Email** — must be an authorized Microsoft 365 mailbox with `Mail.Send` permission
3. Enter the **Recipient Email** (candidate's address)
4. Optionally add **CC** recipients (comma or semicolon separated)
5. Click **🚀 Send Offer Email**

> ✅ On success, the email with the attached offer letter is dispatched via Microsoft Graph and saved to the sender's Sent folder. 🎉

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `AZURE_TENANT_ID` | ✅ Yes | Your Azure Active Directory Tenant ID |
| `AZURE_CLIENT_ID` | ✅ Yes | Your registered Azure App's Client (Application) ID |
| `AZURE_CLIENT_SECRET` | ✅ Yes | The client secret value generated for your Azure App |
| `SYSTEM_SENDER_EMAIL` | ✅ Yes | Authorized Microsoft 365 mailbox for sending offer letters |

---

## Troubleshooting

### ❌ `CRITICAL ERROR: Missing Azure AD credentials`
- Ensure your `.env` file exists in the project root directory
- Verify `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and `AZURE_CLIENT_SECRET` are all set and correct

### ❌ `Failed to acquire MS Graph token`
- Double-check that the **Client Secret** has not expired in the Azure portal
- Verify the Tenant ID and Client ID are copied correctly (no extra spaces)

### ❌ `GRAPH POST FAILED — Status: 403 Forbidden`
- The Azure app is missing **admin consent** for the required permission
- Go to Azure Portal → App → API Permissions → Grant admin consent

### ❌ `Template file not found`
- Do not rename or move the template file

### ❌ `Invalid recipient email address format`
- The email address entered in the UI failed regex validation
- Check for typos or extra spaces in the email field

### ❌ Email sent but recipient did not receive it
- Verify the `SYSTEM_SENDER_EMAIL` is a licensed Microsoft 365 mailbox
- Check the sender's **Sent Items** folder — the email should appear there

### ❌ Flask app crashes on start with `exit code: 1`
- Run `pip install -r requirements.txt` again to ensure all packages are installed
- Check that your Python virtual environment is activated
- Look at the terminal output for the specific error message

---

## Security Notes

- **Never commit `.env`** to version control. It is excluded by `.gitignore`.
- Rotate your **Client Secret** periodically from the Azure Portal.
