import streamlit as st
import pandas as pd
import PyPDF2
import os
import time
import json
from datetime import datetime
import requests
from openai import OpenAI
from fpdf import FPDF 

# -------------------------------
# Data & PDF Initialization
# -------------------------------
talent_pool_df = pd.read_excel('talentpool.xlsx')

def extract_pdf_text(pdf_path: str) -> str:
    text = ""
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted
    return text

pdf_text = extract_pdf_text("Data Roles Indonesian.pdf")

# -------------------------------
# LLM API Initialization
# -------------------------------
client = OpenAI(
    api_key=st.secrets["openai"]["api_key"],
    base_url=st.secrets["openai"]["base_url"],
    default_headers={"x-api-key": st.secrets["openai"]["header"]}
)

# -------------------------------
# Webhook Function to Trigger Power Automate
# -------------------------------
def trigger_power_automate(payload: dict):
    webhook_url = "https://prod-59.southeastasia.logic.azure.com:443/workflows/600114214da148eea88c68bed87b2f46/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=oxPCcf0WivPxuIz_gcRUnj8qFEfTPHelRgEcCJzSd_w"
    if not webhook_url:
        st.error("Power Automate webhook URL not configured.")
        return None
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        st.write("Response code:", response.status_code)
        st.write("Response body:", response.text)
        return response
    except Exception as e:
        st.error(f"Error triggering Power Automate: {str(e)}")
        return None

# -------------------------------
# Chatbot Functions (Normal Mode)
# -------------------------------
def chatbot_response(user_input: str, chat_history: list) -> str:
    conversation_str = ""
    for msg in chat_history:
        conversation_str += f"{msg['role'].capitalize()}: {msg['content']}\n"
    prompt = (
        f"Berikut adalah informasi yang terdapat pada dokumen (context):\n{pdf_text}\n\n"
        f"Percakapan sebelumnya:\n{conversation_str}\n"
        f"User: {user_input}\n"
        "Silakan berikan jawaban yang relevan berdasarkan konteks tersebut."
    )
    completion = client.chat.completions.create(
        model="telkom-ai",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return completion.choices[0].message.content

# -------------------------------
# Project Recommendation Functions (Recommendation Mode)
# -------------------------------
def generate_dynamic_response(user_input: str, context: str) -> str:
    prompt = (
        f"Berikut adalah informasi mengenai peran data dari dokumen:\n{context}\n\n"
        f"Pertanyaan pengguna: {user_input}\n"
        "Berdasarkan informasi di atas, tolong rekomendasikan peran data yang tepat, "
        "jumlah orang yang diperlukan, dan alasan singkat untuk rekomendasi tersebut. "
        "Jawab pertanyaan di atas secara deskriptif dan sertakan ringkasan dalam format JSON seperti:\n"
        '{ "recommended_role": "<role>", "talent_count": <number>, "description": "<brief description>" }\n'
    )
    completion = client.chat.completions.create(
        model="telkom-ai",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return completion.choices[0].message.content

def select_talent_from_pool(dynamic_response: str, talent_pool_df: pd.DataFrame) -> str:
    talent_pool_text = talent_pool_df.to_csv(index=False)
    prompt = (
        "Berikut adalah respons dinamis yang berisi rekomendasi peran dan jumlah talent yang dibutuhkan "
        "dalam format JSON:\n"
        f"{dynamic_response}\n\n"
        "Berikut adalah data talent yang tersedia dalam format CSV:\n"
        f"{talent_pool_text}\n\n"
        "Berdasarkan rekomendasi di atas, pilihlah talent yang sesuai dengan peran yang direkomendasikan "
        "dan jumlah yang dibutuhkan, serta siap diassign. Keluarkan hasilnya dalam format JSON dengan jumlah "
        "talent yang dipilih sama dengan jumlah yang direkomendasikan pada dynamic_response. Setiap entry harus "
        "berupa objek dengan kunci 'Nama', 'JOB ROLE USECASE', dan kunci relevan lainnya jika diperlukan. "
        "Jangan sertakan detail tentang status penugasan."
    )
    completion = client.chat.completions.create(
        model="telkom-ai",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return completion.choices[0].message.content

def log_recommendation(user_name: str, user_unit: str, user_email: str, user_input: str, 
                       dynamic_response: str, selected_talent: str) -> None:
    log_entry = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Name": user_name,
        "Unit": user_unit,
        "Email": user_email,
        "User Input": user_input,
        "Dynamic Response": dynamic_response,
        "Selected Talent": selected_talent
    }
    
    log_file = "recommendation_log.csv"
    if os.path.exists(log_file):
        log_df = pd.read_csv(log_file)
        log_df = pd.concat([log_df, pd.DataFrame([log_entry])], ignore_index=True)
    else:
        log_df = pd.DataFrame([log_entry])
    log_df.to_csv(log_file, index=False)

# -------------------------------
# Integrated Official Document Generation Function
# -------------------------------
def generate_official_document_integration(user_input: str, dynamic_response: str, selected_talent: str, template_text: str) -> (str, str):
    """
    Generates an official talent request document using the provided template, project details, and recommendation.
    Returns a tuple of (pdf_filename, document_text).
    """
    prompt = (
        f"Gunakan template berikut sebagai dasar untuk membuat draft dokumen resmi permohonan kebutuhan talent:\n\n"
        f"{template_text}\n\n"
        f"Berdasarkan informasi dan rekomendasi proyek berikut:\n"
        f"User Input: {user_input}\n"
        f"Rekomendasi (Dynamic Response): {dynamic_response}\n"
        f"Selected Talent: {selected_talent}\n\n"
        "Buatlah draft dokumen permohonan kebutuhan talent dengan bahasa formal, mengacu pada format dan gaya di template."
    )
    completion = client.chat.completions.create(
        model="telkom-ai",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    document_text = completion.choices[0].message.content

    # Create a PDF from the generated document text using FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    for line in document_text.split('\n'):
        pdf.multi_cell(0, 10, line)
    pdf_filename = f"Official_Document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(pdf_filename)
    
    return pdf_filename, document_text

# -------------------------------
# Streamlit UI: Flow Selection & Interfaces
# -------------------------------
def chatbot_mode():
    st.subheader("Mode Chatbot (Pertanyaan Umum)")
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Tulis pesan Anda:")
        submitted = st.form_submit_button("Kirim")

    if submitted and user_input.strip():
        with st.spinner("Memproses jawaban..."):
            st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})
            response = chatbot_response(user_input.strip(), st.session_state.chat_history)
            st.session_state.chat_history.append({"role": "bot", "content": response})

    # Display chat history
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f"**User:** {msg['content']}")
        else:
            st.markdown(f"**Bot:** {msg['content']}")

def project_recommendation_mode():
    st.subheader("Mode Rekomendasi Proyek")
    
    # Ensure session state variables are initialized
    if "project_recommendation_done" not in st.session_state:
        st.session_state.project_recommendation_done = False
    if "project_recommendation_result" not in st.session_state:
        st.session_state.project_recommendation_result = {}
    if "project_user_input" not in st.session_state:
        st.session_state.project_user_input = ""

    user_input = st.text_input("Apa kebutuhan data proyek Anda?", key="proj_input")
    
    # 1) Generate recommendation if a new prompt is entered
    if user_input and not st.session_state.project_recommendation_done:
        st.session_state.project_user_input = user_input
        loading_placeholder = st.empty()
        for i in range(10):
            dots = "." * ((i % 5) + 1)
            loading_placeholder.markdown(
                f'<div style="text-align:center; font-size:24px; font-weight:bold;">'
                f'Permintaan Anda sedang dalam pengecekan. Tunggu sebentar{dots}</div>',
                unsafe_allow_html=True
            )
            time.sleep(0.5)
        dynamic_response = generate_dynamic_response(user_input, pdf_text)
        selected_talent = select_talent_from_pool(dynamic_response, talent_pool_df)
        st.session_state.project_recommendation_result = {
            "dynamic_response": dynamic_response,
            "selected_talent": selected_talent
        }
        st.session_state.project_recommendation_done = True
        loading_placeholder.empty()
    
    # 2) If a recommendation has been generated, display it
    if st.session_state.project_recommendation_done:
        st.subheader("🤖 Rekomendasi (LLM-enhanced):")
        try:
            dynamic_data = json.loads(st.session_state.project_recommendation_result["dynamic_response"])
        except Exception:
            dynamic_data = {}
        if dynamic_data:
            st.markdown("### Rekomendasi")
            st.markdown(f"**Recommended Role:** {dynamic_data.get('recommended_role', 'N/A')}")
            st.markdown(f"**Talent Count:** {dynamic_data.get('talent_count', 'N/A')}")
            st.markdown(f"**Description:** {dynamic_data.get('description', 'N/A')}")
        else:
            st.write("Dynamic Response:", st.session_state.project_recommendation_result["dynamic_response"])
        
        try:
            selected_talent_data = json.loads(st.session_state.project_recommendation_result["selected_talent"])
        except Exception:
            selected_talent_data = st.session_state.project_recommendation_result["selected_talent"]
        st.markdown("### Selected Talent")
        if isinstance(selected_talent_data, list):
            talent_df = pd.DataFrame(selected_talent_data)
            st.dataframe(talent_df)
        else:
            st.write("Selected Talent:", selected_talent_data)
        
        st.markdown("### 📋 Konfirmasi")
        st.write(
            "Berdasarkan rangkuman di atas, kami telah memilih talent dengan role dan kemampuan yang sesuai "
            "dengan kebutuhan proyek Anda.\n\n"
            "Apakah Anda setuju dengan rekomendasi ini dan ingin meneruskan permintaan ke manajemen?"
        )

        # "Setuju & Kirim ke Manajemen" button (integrated with official document generation)
        if st.button("Setuju & Kirim ke Manajemen"):
            log_recommendation(
                st.session_state.user_name,
                st.session_state.user_unit,
                st.session_state.user_email,
                st.session_state.project_user_input,
                st.session_state.project_recommendation_result["dynamic_response"],
                st.session_state.project_recommendation_result["selected_talent"]
            )
            
            try:
                dynamic_json = json.loads(st.session_state.project_recommendation_result["dynamic_response"])
                recommended_role = dynamic_json.get("recommended_role", "Not Specified")
            except Exception:
                recommended_role = "Not Specified"
            
            payload = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Name": st.session_state.user_name,
                "Unit": st.session_state.user_unit,
                "Email": st.session_state.user_email,
                "User Input": st.session_state.project_user_input,
                "Recommended Role": recommended_role,
                "Recommended Talents": st.session_state.project_recommendation_result["selected_talent"],
                "Dynamic Response": st.session_state.project_recommendation_result["dynamic_response"],
                "Selected Talent": st.session_state.project_recommendation_result["selected_talent"]
            }
            response = trigger_power_automate(payload)
            if response and response.status_code in [200, 202]:
                st.success("Permintaan telah dikirim ke manajemen dan dicatat!")
                
                # Generate the official document draft and PDF
                with st.spinner("Membuat draft dokumen resmi..."):
                    pdf_filename, doc_text = generate_official_document_integration(
                        st.session_state.project_user_input,
                        st.session_state.project_recommendation_result["dynamic_response"],
                        st.session_state.project_recommendation_result["selected_talent"],
                        pdf_text  # Using the extracted template as guidance
                    )
                st.markdown("### Preview Dokumen Resmi")
                st.text(doc_text)
                with open(pdf_filename, "rb") as pdf_file:
                    st.download_button("Download PDF Dokumen Resmi", pdf_file.read(), file_name=pdf_filename, mime="application/pdf")
            else:
                st.error("Gagal mengirim permintaan ke Power Automate. Silakan coba lagi.")

# -------------------------------
# App Initialization & Main Flow
# -------------------------------
st.set_page_config(
    page_title="🤖 Cimolbot 🍡",
    page_icon="🍡"
)

def main():
    st.title("🤖 Data Role Cimolbot  🍡 🍡 🍡 ")

    st.sidebar.markdown("### Informasi Diri")
    user_name = st.sidebar.text_input("Nama:")
    user_unit = st.sidebar.selectbox("Unit:", [
        "AGR", "BSP", "DAG", "DBE", "DEX", "DOA", "DPE", "DPM",
        "DSC", "DSZ", "EDU", "ENT", "EWZ", "GTP", "IDM", "IHX",
        "INS", "IOT", "LGS", "MKT", "PAS", "SMB", "SVC", "TOS"
    ])
    user_email = st.sidebar.text_input("Email:")

    if not (user_name and user_unit and user_email):
        st.sidebar.warning("Silakan lengkapi informasi diri Anda.")
        st.stop()

    st.session_state.user_name = user_name
    st.session_state.user_unit = user_unit
    st.session_state.user_email = user_email

    # Mode selection now only shows Chatbot and Rekomendasi Proyek
    mode = st.sidebar.radio("Pilih Alur:", ("Chatbot", "Rekomendasi Proyek"))
    
    if mode == "Chatbot":
        chatbot_mode()
    else:
        project_recommendation_mode()

if __name__ == "__main__":
    main()
