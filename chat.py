import streamlit as st
import pandas as pd
import PyPDF2
import os
import time
import json
from datetime import datetime
import requests
from openai import OpenAI

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
    if 
