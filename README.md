# 📊 CimolBot – DSC Talent Request Portal

**CimolBot** is an interactive AI-powered web application designed to assist teams within Telkom DBT in identifying and requesting the right data talents (Data Analyst, Data Scientist, etc.) from the DSC (Data Science & AI Chapter). Built with Streamlit and OpenAI API integration, it streamlines the process of talent recommendation and request documentation.

---

## 🎯 Purpose & Goal

The primary **goal** of CimolBot is to:

* **Simplify** the process of requesting data talents for internal projects.
* **Provide AI-powered recommendations** for suitable roles based on user-submitted project descriptions.
* **Enable automation** of request handling via SharePoint, Power Automate, and WhatsApp notifications.

---

## 🧠 How It Works

### 1. **User Input & Onboarding**

* Users must fill in their **name**, **unit**, and **email** and agree to a **privacy policy** via the sidebar.
* Once onboarded, users can choose between:

  * **Chatbot Mode**
  * **Recommendation Mode**

---

### 2. 🧾 Chatbot Mode

* Designed for **general Q\&A** regarding **data roles** (Data Analyst, Engineer, Scientist, etc.).
* Contextual responses are generated using **OpenAI's LLM**, based on a provided PDF knowledge document (`Data Roles Indonesian.pdf`).
* Helps educate users before requesting a talent.

---

### 3. 🤖 Recommendation Mode

* Users describe their project and the kind of data support they need.
* The system generates:

  * A **recommended role**
  * Suggested **talent level** (Junior/Middle/Senior)
  * **Talent count**
  * Key **responsibilities and bullet-point descriptions**
* Based on available talent data from a backend API (`flow_url`), the app suggests matching personnel.

---

### 4. 📩 Request Finalization

* Once a user accepts a recommendation:

  * A **payload is sent to Power Automate** (via webhook)
  * A **WhatsApp notification** is sent to the DSC management using **Twilio API**
  * A **Word document (NDE draft)** is automatically generated using `docxtpl` and uploaded to **SharePoint**

---

## 🛠️ Tech Stack

* **Frontend:** Streamlit
* **LLM Integration:** OpenAI (via custom API & headers)
* **Document Automation:** `docxtpl`
* **Backend Communication:** HTTP POST requests (to internal APIs / Power Automate)
* **Notifications:** Twilio WhatsApp API
* **File I/O & Uploads:** SharePoint (via encoded payload)

---

## 🔐 Security & Privacy

* The app requires users to **explicitly consent** to the privacy policy before accessing its features.
* All API keys and endpoints are managed securely via `st.secrets`.

---

## 📦 Features Summary

| Feature                               | Description                                                          |
| ------------------------------------- | -------------------------------------------------------------------- |
| Talent Role Recommender               | Suggests data roles and team structure based on project descriptions |
| General Role Chatbot                  | Answers common questions about data roles at Telkom                  |
| Talent Pool Integration               | Filters available talents via role, level, and status                |
| Document Automation (NDE)             | Creates a draft Word document for formal talent requests             |
| Management Notification               | Sends automated alerts via WhatsApp and triggers internal workflows  |
| Streamlit UI with Theme Customization | Custom design for Telkom's branding                                  |

---

## ✅ Requirements to Run

* Streamlit
* PyPDF2
* pandas
* requests
* twilio
* openai
* docxtpl

All configuration (like API keys and endpoint URLs) must be supplied in the `st.secrets` file.

---

## 📁 Secrets Configuration Example

```toml
[openai]
api_key = "your-api-key"
base_url = "https://your-openai-endpoint"
header = "your-custom-header-key"

[twilio]
account_sid = "your-twilio-sid"
auth_token = "your-twilio-token"
from_ = "whatsapp:+1415xxxxxxx"
to = "whatsapp:+62xxxxxxxxxx"

[http]
flow_url = "https://api.get-talent-pool"
flow_url2 = "https://api.get-regulations"
flow_url3 = "https://sharepoint.upload-endpoint"
webhook_url = "https://flow.powerautomate.com/webhook"
```

---

## 🚀 Getting Started

1. Clone the repository.
2. Set up your environment and install required packages.
3. Add your `secrets.toml` to `.streamlit/`.
4. Place the knowledge PDF and Word template (`Data Roles Indonesian.pdf` and `Contoh NDE.docx`) in the root folder.
5. Run the app:

```bash
streamlit run app.py
```

---

## 👥 Contributors

Developed for internal use by the **Data Science Chapter (DSC)** of **Telkom Indonesia – DBT** unit.
