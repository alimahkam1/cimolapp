import streamlit as st
import pandas as pd
import PyPDF2
import os
import time
from datetime import datetime
from openai import OpenAI  # Ensure you have the correct openai version installed

# -------------------------------
# Data & PDF Initialization
# -------------------------------
def load_and_mask_talent_pool(file_path: str, masked_file: str) -> pd.DataFrame:
    df = pd.read_excel(file_path)
    df.to_excel(masked_file, index=False)
    return pd.read_excel(masked_file)

talent_pool_df = load_and_mask_talent_pool('talentpool.xlsx', 'masked_file.xlsx')

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
    api_key="randomkey",  # Replace with your API key
    base_url="https://telkom-ai-dag-api.apilogy.id/Telkom-LLM/0.0.4/llm",
    default_headers={"x-api-key": "88JWNTBHM4OXBusCLZuBYGUGBBrTE2iD"}  # Replace with your API key
)

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
        "Berdasarkan informasi di atas, tolong rekomendasikan peran data yang tepat, dan jumlah orang yang diperlukan. "
        "Jawab pertanyaan diatas secara deskriptif. Setelah memberikan jawaban dengan format deskriptif, tulis kembali semua jawaban dalam bentuk rangkuman dengan format berikut:\n"
        "(Bold) Role yang dibutuhkan: (Jumlah orang)\n\n"
        "(Bold) Talent yang disarankan: (Diisi dengan nama talent dari data talent pool)\n\n"
        "(Bold) Deskripsi: (Deskripsi pengalaman dan atau skill yang diharapkan dari talent unutk projek yang akan dilakukan)\n\n"
    )
    completion = client.chat.completions.create(
        model="telkom-ai",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return completion.choices[0].message.content

def recommend_role(user_message: str) -> str:
    user_message = user_message.lower()
    if "dashboard" in user_message or "laporan" in user_message:
        return "Data Analyst"
    elif "machine learning" in user_message or "prediksi" in user_message:
        return "Data Scientist"
    elif "ai" in user_message or "otomatisasi" in user_message:
        return "AI Engineer"
    elif "etl" in user_message or "pipeline" in user_message:
        return "Data Engineer"
    else:
        return "Peran yang sesuai tidak ditemukan. Mohon berikan lebih banyak detail."

def match_talent(role: str):
    matched_candidates = talent_pool_df[talent_pool_df["JOB ROLE USECASE"].str.upper() == role.upper()]
    if not matched_candidates.empty:
        return matched_candidates.head(3)[["Nama", "LeMiddleel", "JOB ROLE USECASE"]].to_dict(orient="records")
    return "Tidak ada kandidat tersedia untuk peran ini."

def extract_talent_from_response(response: str) -> str:
    """
    Extracts the talent names from the dynamic response.
    Expected to find a line starting with "Talent yang disarankan:".
    """
    for line in response.splitlines():
        if line.startswith("Talent yang disarankan:"):
            return line.split(":", 1)[1].strip()
    return ""

def log_recommendation(user_name: str, user_unit: str, user_email: str, user_input: str, 
                       recommended_role: str, recommended_talents: str, matched_talent_list) -> None:
    if isinstance(matched_talent_list, list):
        matched_talent_list = str(matched_talent_list)
    
    log_entry = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Name": user_name,
        "Unit": user_unit,
        "Email": user_email,
        "User Input": user_input,
        "Recommended Role": recommended_role,
        "Recommended Talents": recommended_talents,
        "Matched Talent List": matched_talent_list
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
    if 'loading' not in st.session_state:
        st.session_state.loading = False

    # Display chat history
    for msg in st.session_state.chat_history:
        if msg['role'] == 'user':
            st.markdown(f"**User:** {msg['content']}")
        else:
            st.markdown(f"**Bot:** {msg['content']}")

    # If waiting for reply, disable input
    if st.session_state.loading:
        st.info("Menunggu jawaban...")
        # Optionally, you can still show the text input in disabled mode
        st.text_input("Tulis pesan Anda:", key="chat_input", disabled=True)
        st.button("Kirim", disabled=True)
    else:
        user_input = st.text_input("Tulis pesan Anda:", key="chat_input", disabled=st.session_state.loading)
        if st.button("Kirim", disabled=st.session_state.loading) and user_input:
            st.session_state.loading = True
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.spinner("Memproses jawaban..."):
                response = chatbot_response(user_input, st.session_state.chat_history)
            st.session_state.chat_history.append({"role": "bot", "content": response})
            st.session_state.loading = False
            # Rerun to refresh the chat window
            if hasattr(st, "experimental_rerun"):
                st.experimental_rerun()

def project_recommendation_mode():
    st.subheader("Mode Rekomendasi Proyek")
    if "project_recommendation_done" not in st.session_state:
        st.session_state.project_recommendation_done = False
    if "project_recommendation_result" not in st.session_state:
        st.session_state.project_recommendation_result = {}
    if "project_user_input" not in st.session_state:
        st.session_state.project_user_input = ""

    user_input = st.text_input("Apa kebutuhan data proyek Anda?", key="proj_input")
    
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
        recommended_role = recommend_role(user_input)
        matched_candidates = match_talent(recommended_role)
        dynamic_response = generate_dynamic_response(user_input, pdf_text)
        recommended_talents = extract_talent_from_response(dynamic_response)
        st.session_state.project_recommendation_result = {
            "recommended_role": recommended_role,
            "matched_candidates": matched_candidates,
            "dynamic_response": dynamic_response,
            "recommended_talents": recommended_talents,
        }
        st.session_state.project_recommendation_done = True
        loading_placeholder.empty()
    
    if st.session_state.project_recommendation_done:
        st.subheader("🤖 Rekomendasi (LLM-enhanced):")
        st.write(st.session_state.project_recommendation_result["dynamic_response"])
        st.markdown("### 📋 Konfirmasi")
        st.write(
            "Berdasarkan rangkuman di atas, kami telah memilih talent dengan role dan kemampuan yang sesuai dengan kebutuhan projek Anda.\n\n"
            "Apakah Anda setuju dengan rekomendasi ini dan ingin meneruskan permintaan ke manajemen?"
        )
        if st.button("Setuju & Kirim ke Manajemen"):
            log_recommendation(
                st.session_state.user_name,
                st.session_state.user_unit,
                st.session_state.user_email,
                st.session_state.project_user_input,
                st.session_state.project_recommendation_result["recommended_role"],
                st.session_state.project_recommendation_result["recommended_talents"],
                st.session_state.project_recommendation_result["matched_candidates"]
            )
            st.success("Permintaan telah dikirim ke manajemen dan dicatat!")

def main():
    st.title("🤖 Data Role Cimolbot")

    # -------------------------------
    # Sidebar: User Information & Mode Selection
    # -------------------------------
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

    mode = st.sidebar.radio("Pilih Alur:", ("Chatbot", "Rekomendasi Proyek"))
    
    if mode == "Chatbot":
        chatbot_mode()
    else:
        project_recommendation_mode()

if __name__ == "__main__":
    main()
