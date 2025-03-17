#WITHOUT WHATSAPP WHEN THE DAILY LIMIT HAS BEEN REACHED

import streamlit as st
import pandas as pd
import PyPDF2
import re
from io import BytesIO
import json
import base64
from datetime import datetime
import requests
from openai import OpenAI
from twilio.rest import Client  # Import Twilio
from docxtpl import DocxTemplate

# -------------------------------
# Inisialisasi Data & PDF
# -------------------------------
flow_url = st.secrets["http"]["flow_url"]
todays_date = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")

try:
    response = requests.post(flow_url)
    response.raise_for_status()
    data = response.json()

    # Ekstrak daftar record dari kunci "value"
    records = data.get("value", [])

    if records:
        required_columns = [
            "Nama",
            "Level",
            "JOB ROLE USECASE",
            "UniqueCode",
            "Assignment Status"
        ]
        df = pd.DataFrame(records)[required_columns]
        talent_pool_df = df.to_csv(index=False)
    else:
        st.write("Tidak ditemukan rekaman di data JSON.")
except requests.RequestException as e:
    st.error(f"Terjadi kesalahan saat mengambil data: {e}")

flow_url2 = st.secrets["http"]["flow_url2"]
response2 = requests.post(flow_url2)
flow_url3 = st.secrets["http"]["flow_url3"]

if response2.status_code == 200:
    data = response2.json()
    point1 = data.get("point1")
    point2 = data.get("point2")
    point3 = data.get("point3")
else:
    st.error(f"Terjadi kesalahan: {response2.status_code} {response2.text}")

# -------------------------------
# Fungsi Ekstraksi Teks dari PDF
# -------------------------------
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
# Fungsi Pengiriman Dokumen ke SharePoint
# -------------------------------
def sending_docs(the_docs, sender_unit):
    if hasattr(the_docs, "getvalue"):
        file_content = the_docs.getvalue()
    else:
        with open(the_docs, 'rb') as file:
            file_content = file.read()

    encoded_content = base64.b64encode(file_content).decode('utf-8')
    payload = {
        "fileName": f"{todays_date}_draft_NDE_{sender_unit}.docx",
        "fileContent": encoded_content
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(flow_url3, json=payload, headers=headers)
    except requests.RequestException as e:
        st.error(f"Terjadi kesalahan saat mengirim dokumen: {e}")
        return payload, None
    return payload, response

# -------------------------------
# Inisialisasi API LLM
# -------------------------------
client = OpenAI(
    api_key=st.secrets["openai"]["api_key"],  
    base_url=st.secrets["openai"]["base_url"],
    default_headers={"x-api-key": st.secrets["openai"]["header"]}  
)

# -------------------------------
# Fungsi Notifikasi WhatsApp via Twilio
# -------------------------------
# def send_whatsapp_notification(sender_name: str, sender_unit: str, user_input: str):
#     account_sid = st.secrets["twilio"]["account_sid"]
#     auth_token = st.secrets["twilio"]["auth_token"]
#     client_twilio = Client(account_sid, auth_token)

#     message = client_twilio.messages.create(
#         from_=st.secrets["twilio"]["from_"],
#         body=(
#             f"Permintaan Talenta baru telah dikirim pada {todays_date}!\n\n"
#             f"Permintaan ini dikirim oleh {sender_name} dari {sender_unit}.\n\n"
#             f"Berikut kebutuhannya: \n\n {user_input} \n\n"
#             "Periksa email serta channel teams Anda untuk informasi selengkapnya."
#         ),
#         to=st.secrets["twilio"]["to"]
#     )
#     print(message.sid)

# -------------------------------
# Fungsi Webhook untuk Memicu Power Automate
# -------------------------------
def trigger_power_automate(payload: dict):
    webhook_url = st.secrets["http"]["webhook_url"]
    if not webhook_url:
        st.error("URL webhook Power Automate tidak dikonfigurasi.")
        return None
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        #st.write("Status:", response.text)
        return response
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memicu Power Automate: {str(e)}")
        return None

# -------------------------------
# Fungsi Rekomendasi Talent (Mode Rekomendasi)
# -------------------------------

def clean_markdown(text: str) -> str:
    """
    Remove markdown bold markers (and other known formatting artifacts) from the text.
    """
    # Remove markdown bold markers (i.e. **)
    text = text.replace("**", "")
    return text

def extract_recommended_role(response_text: str) -> str:
    """
    Extract the recommended role from the response text by matching lines like:
    'Recommended Role: Data Analyst'.
    Returns a string with the recommended role. If not found, returns an empty string.
    """
    cleaned_text = clean_markdown(response_text)
    pattern = r'(?i)recommended\s*role.*?:\s*(.*)'
    match = re.search(pattern, cleaned_text)
    if match:
        return match.group(1).strip()
    return ''

def extract_talent_level(response_text: str) -> str:
    """
    Extract the talent level from the response text by matching lines like:
    'Talent Level: Middle'.
    Returns a string with the talent level. If not found, returns an empty string.
    """
    cleaned_text = clean_markdown(response_text)
    pattern = r'(?i)talent\s*level.*?:\s*(.*)'
    match = re.search(pattern, cleaned_text)
    if match:
        return match.group(1).strip()
    return ''

def extract_talent_count(response_text: str) -> int:
    """
    Extract the talent count from the response text by matching lines like:
    'Talent Count: 2' (ignoring markdown formatting).
    Returns an integer. If not found, returns 0.
    """
    cleaned_text = clean_markdown(response_text)
    pattern = r'(?i)talent\s*count.*?:\s*(\d+)'
    match = re.search(pattern, cleaned_text)
    if match:
        return int(match.group(1))
    return 0

def extract_talent_description(response_text: str) -> str:
    """
    Extract lines (bullet points) that come after 'Talent Description:' 
    and before the next known section (e.g., 'Alasan rekomendasi').
    Lines are considered bullet points if they start with '-' or '•'.
    """
    cleaned_text = clean_markdown(response_text)
    marker = "Talent Description:"
    
    # Find the starting index for the marker, case-insensitively.
    lower_text = cleaned_text.lower()
    idx = lower_text.find(marker.lower())
    if idx == -1:
        return ""

    # Extract everything after "Talent Description:"
    remainder = cleaned_text[idx + len(marker):]
    lines = remainder.splitlines()
    collected_bullets = []

    for line in lines:
        stripped_line = line.strip()
        
        # If we reach another section header or something like "Alasan rekomendasi",
        # we stop collecting lines. Adjust these checks to fit your output.
        lower_line = stripped_line.lower()
        if (lower_line.startswith("alasan rekomendasi") or
            lower_line.startswith("recommended role") or
            lower_line.startswith("talent level") or
            lower_line.startswith("talent count") or
            lower_line.startswith("talent description")):
            break
        
        # Only collect lines that start with '-' or '•'.
        if stripped_line.startswith("-") or stripped_line.startswith("•"):
            collected_bullets.append(stripped_line)
    
    # Join the bullet points back together with newlines (or however you prefer).
    return "\n".join(collected_bullets)

def generate_dynamic_response(user_input: str, context: str) -> str:
    prompt = (
        f"Berikut adalah informasi mengenai data role dari dokumen:\n{context}\n\n"
        f"Kebutuhan pengguna: {user_input}\n\n"
        "Berdasarkan informasi di atas, tolong rekomendasikan data role yang tepat, jumlah orang yang diperlukan dalam Bahasa Indonesia, "
        "dan alasan singkat untuk rekomendasi tersebut. Jawab pertanyaan secara deskriptif dan sertakan ringkasan dalam format berikut:\n\n"
        "Recommended Role (Bold): <role>\n\n"
        "Talent Level (Bold): <level (Junior, Middle, atau Senior)>\n\n"
        "Talent Count (Bold): <number>\n\n"
        "Talent Description (Bold):\n\n"
        "- <bullet point 1>\n"
        "- <bullet point 2>\n"
        "- ...\n"
        "Jika prompt tidak jelas atau kurang konteks, minta pengguna memasukkan ulang prompt dengan informasi yang lebih lengkap."
    )

    try:
        completion = client.chat.completions.create(
            model="telkom-ai",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        response_text = completion.choices[0].message.content
    except Exception as e:
        st.error("Terjadi kesalahan saat menghubungi API LLM.")
        st.error(str(e))
        response_text = "Maaf, terjadi gangguan pada sistem. Silakan coba lagi nanti."
    
    # Here we parse out the talent count from the response
    talent_count = extract_talent_count(response_text)
    recommended_role = extract_recommended_role(response_text)
    talent_level = extract_talent_level(response_text)
    talent_description = extract_talent_description(response_text)
    
    return response_text, talent_count, recommended_role, talent_level, talent_description

def extract_selected_talent_info(response_text: str) -> list:
    """
    Extract multiple talent information from the response text.
    Expected format (with variations allowed)
    Returns:
        A list of dictionaries, each containing 'Nama', 'Role', and 'Talent Unique Code'
        for each talent found in the response text.
    """
    # Regular expression that:
    # - Matches "Nama:" followed by an optional quote, then captures the name.
    # - Lazily matches any text until "Role:" is found, and captures the role.
    # - Lazily matches until "Talent Unique Code:" is found, and captures the code.
    pattern = re.compile(
        r'Nama\s*:\s*"?([^"\n]+)"?.*?'
        r'Role\s*:\s*"?([^"\n]+)"?.*?'
        r'Talent Unique Code\s*:\s*"?([^"\n]+)"?',
        re.IGNORECASE | re.DOTALL
    )
    
    # Find all matches in the text
    matches = re.findall(pattern, response_text)
    
    talents = []
    for match in matches:
        talent = {
            "Nama": match[0].strip(),
            "Role": match[1].strip(),
            "Talent Unique Code": match[2].strip()
        }
        talents.append(talent)
    
    return talents

def select_talent_from_pool(dynamic_response: str, talent_pool_df: pd.DataFrame, talent_count: int) -> str:
    prompt = (
        "Berikut adalah respons dinamis yang berisi rekomendasi peran dan jumlah talent yang dibutuhkan "
        f"{dynamic_response}\n\n"
        "Berikut adalah data talent yang tersedia dalam format JSON:\n"
        f"{talent_pool_df}\n\n"
        "Berdasarkan rekomendasi di atas, pilihlah talent yang sesuai dengan peran yang direkomendasikan "
        "dan jumlah yang dibutuhkan, serta siap diassign. Keluarkan hasilnya dalam format bullets point dengan jumlah "
        f"talent yang dipilih sama dengan jumlah ini: {talent_count}"
        "Setiap entry harus "
        "berupa objek dengan kunci 'Nama', 'JOB ROLE USECASE', dan 'UniqueCode' yang diambil langsung dari data di talent_pool_df. "
        "Jangan sertakan detail tentang status penugasan."
        "Apabila tidak ada konteks spesifik tentang proyek atau tujuan analisis data, jangan rekomendasikan siapapun"
        "Tampilkan dalam format array yang dibagi per bullet points per talent seperti:\n\n"
        '- Nama: "<nama>"\n\n'
        '- Role: "<Job role usecase>"\n\n'
        '- Talent Unique Code: <UniqueCode>'
        
    )
    try:
        completion = client.chat.completions.create(
            model="telkom-ai",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        response_text = completion.choices[0].message.content
        talent_info = extract_selected_talent_info(response_text)
        st.write(talent_info)
    except Exception as e:
        st.error("Terjadi kesalahan saat menghubungi API LLM.")
        st.error(str(e))
        response_text = "Maaf, terjadi gangguan pada sistem. Silakan coba lagi nanti."
    return response_text, talent_info

# -------------------------------
# Fungsi Integrasi Dokumen Resmi
# -------------------------------
def generate_official_document_integration(placeholder1: str, placeholder2: str, placeholder3: str, 
                                             placeholder4: str, placeholder5: str, placeholder6: str, 
                                             placeholder7: str, placeholder8: str):
    doc = DocxTemplate("Contoh NDE.docx")
    context = {
        "recommended_role": placeholder1,
        "unit": placeholder2,
        "number": placeholder3,
        "level": placeholder4,
        "dynamic_response": placeholder5, 
        "peraturan_satu": placeholder6,
        "peraturan_dua": placeholder7,
        "peraturan_tiga": placeholder8
    }
    doc.render(context)
    output_buffer = BytesIO()
    doc.save(output_buffer)
    output_buffer.seek(0)
    return output_buffer

# -------------------------------
# Mode Start
# -------------------------------
def start_mode():
    st.image("logo2.webp")
    st.write("Silakan lengkapi informasi diri Anda apabila Anda setuju dengan kebijakan privasi berikut: \n\n"
                           " \n\n"
                           "🔒 Pemberitahuan Privasi dan Persetujuan 🔒 \n\n"
                            "Dengan menggunakan aplikasi ini, Anda memberikan persetujuan kepada kami untuk mengumpulkan, menyimpan, dan memproses informasi pribadi berikut untuk tujuan operasional aplikasi: \n\n"
                            "- Nama, \n\n - Unit Kerja, \n\n - Email, dan \n\n - Input lain yang Anda berikan. \n\n"
                            "*Terakhir diperbarui: Maret 2025*"
                           )

# -------------------------------
# Mode None
# -------------------------------
def none_mode():
    st.image("logo2.webp")
    st.write("""
                Selamat datang di Cimolbot!

                Silakan memilih alur chat yang Anda butuhkan melalui menu sidebar!

                🔹 Chatbot 🤖 – Gunakan fitur ini jika Anda memiliki pertanyaan umum atau ingin berinteraksi langsung untuk mendapatkan informasi seputar manajemen talent.

                🔹 Rekomendasi 🎯 – Gunakan fitur ini jika Anda ingin mendapatkan saran terbaik mengenai talent role yang sesuai dengan kebutuhan Anda.

                Pilih opsi yang paling sesuai untuk melanjutkan! 🚀
                """)
    
    #return st.write(" ")


# -------------------------------
# Fungsi Mode Chatbot
# -------------------------------

import streamlit as st

def chatbot_mode():
    # Initialize session state variables if not already set
    if 'has_submitted' not in st.session_state:
        st.session_state.has_submitted = False
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    # Show the subheader and expander only if no message has been submitted yet
    if not st.session_state.has_submitted:
        st.subheader("Mode Chatbot (Pertanyaan Umum Terkait Data Role)")
        with st.expander("Informasi", icon="🔍", expanded=False):
            st.write(" \n\n"
                " Selamat datang di Mode Pertanyaan Umum! \n\n"
                "Chatbot ini dirancang untuk membantu setiap unit yang membutuhkan talent data dari chapter DSC. Di sini, Anda dapat mengajukan pertanyaan mengenai berbagai role data—mulai dari ruang lingkup, tanggung jawab, hingga kemampuan masing-masing—sehingga Anda dapat memahami dengan jelas bagaimana setiap peran dapat mendukung kebutuhan proyek Anda. Setelah Anda mengenal peran-peran yang tersedia, Anda dapat beralih ke Chatbot Rekomendasi Talent kami untuk mendapatkan saran yang dipersonalisasi tentang role data ideal yang sesuai dengan proyek spesifik Anda. \n\n \n\n Tapi, jangan khawatir! Anda juga tetap bisa menanyakan pertanyaan yang tidak berhubungan dengan Data ke chatbot ini 😉")

    # Chat input for the user
    user_input = st.chat_input("Tulis pesan Anda:")

    if user_input:
        # After the first user message, hide the subheader and expander
        st.session_state.has_submitted = True

        with st.spinner("Memproses jawaban..."):
            # Add user input to the chat history
            st.session_state.chat_history.append({"role": "pengguna", "content": user_input.strip()})
            # Get the chatbot's response based on the user input
            response = chatbot_response(user_input.strip(), st.session_state.chat_history)
            # Add the chatbot's response to the chat history
            st.session_state.chat_history.append({"role": "bot", "content": response})

        # Force a rerun to hide the subheader and expander immediately after the first submission
        st.rerun()

    # Display the chat history after the user submits a message
    for msg in st.session_state.chat_history:
        col1, col2 = st.columns([1, 15])  # Adjust column width ratio as needed
        if msg["role"] == "pengguna":
            with col1:
                st.image("follower_874735.svg", width=30)  # Replace with actual image path
            with col2:
                st.markdown(f"{msg['content']}")
        else:
            with col1:
                st.image("chatbot_6667605.svg", width=30)  # Replace with actual image path
            with col2:
                st.markdown(f"{msg['content']}")

def chatbot_response(user_input: str, chat_history: list) -> str:
    conversation_str = ""
    for msg in chat_history:
        conversation_str += f"{msg['role'].capitalize()}: {msg['content']}\n"
    prompt = (
        "You are a knowledge assistant called 'CimolBot', you will be answering question from the user, so act nice and humanly!"
        f"Berikut adalah informasi yang terdapat pada dokumen (context):\n{pdf_text}\n\n"
        f"Percakapan sebelumnya:\n{conversation_str}\n"
        f"Pengguna: {user_input}\n"
        "Silakan berikan jawaban yang relevan berdasarkan konteks tersebut dengan menggunakan perspektif Anda sebagai 'Pihak Manajemen DSC'. DSC adalah Data Science and AI Chapter di Telkom DBT."
        "Apabila pertanyaan di luar konteks dokumen, jawablah seakurat mungkin namun berikan catatan bahwa pertanyaannya tidak berkaitan dengan konteks 'Data'."
        "Make sure to not inform the user that this answer is being generate while considering the knowledge document that has been feed before"
    )
    try:
        completion = client.chat.completions.create(
            model="telkom-ai",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        response_text = completion.choices[0].message.content
    except Exception as e:
        st.error("Terjadi kesalahan saat menghubungi API LLM.")
        st.error(str(e))
        response_text = "Maaf, terjadi gangguan pada sistem. Silakan coba lagi nanti."
    return response_text

# -------------------------------
# Fungsi Mode Rekomendasi Talent
# -------------------------------

def project_recommendation_mode():
    # Initialize session state variables if not already set
    if "project_recommendation_done" not in st.session_state:
        st.session_state["project_recommendation_done"] = False
    if "project_recommendation_result" not in st.session_state:
        st.session_state["project_recommendation_result"] = {}
    if "project_user_input" not in st.session_state:
        st.session_state["project_user_input"] = ""

    # Input Mode
    if not st.session_state["project_recommendation_done"]:
        st.subheader("Mode Rekomendasi Talent")
        with st.expander("Informasi", icon="🔍", expanded=False):
            st.write(
                "Selamat datang di Mode Rekomendasi Data Talent!\n\n"
                "Chatbot ini dirancang untuk membantu setiap bidang/tribe menemukan ahli data yang tepat sesuai dengan kebutuhan proyek Anda. "
                "Cukup deskripsikan jenis proyek yang akan Anda kerjakan serta harapan Anda terhadap peran talenta yang diinginkan, "
                "dan sistem kami akan memberikan rekomendasi yang dipersonalisasi berdasarkan kriteria tersebut. "
                "Apakah Anda mencari data analyst, data engineer, atau spesialis machine learning, kami siap membantu Anda menemukan kandidat yang paling sesuai! \n\n \n\n"
            )
            st.markdown(
                """
                Berikut beberapa contoh prompt yang dapat Anda gunakan:

                - "Saya sedang mengerjakan proyek analisis pasar dan membutuhkan data analyst yang handal untuk menganalisa tren penjualan serta statistik."

                - "Proyek saya adalah pengembangan sistem rekomendasi untuk e-commerce. Saya membutuhkan spesialis machine learning dengan pengalaman di deep learning dan data mining."

                - "Dalam proyek optimasi supply chain, saya memerlukan data engineer yang berpengalaman dalam ETL dan pengelolaan data skala besar."

                - "Untuk mendukung proyek riset tren konsumen, saya mencari data scientist yang ahli dalam analisis big data dan visualisasi data."

                - "Proyek saya berkaitan dengan prediksi penjualan menggunakan algoritma forecasting."
                """
            )

        user_input = st.text_input(
            "Apa kebutuhan data proyek Anda?",
            key="proj_input",
            placeholder="Silakan baca informasi di atas terlebih dahulu",
            help="Tekan ENTER untuk menyimpan prompt lalu klik tombol Buatkan Saya Rekomendasi"
        )
        is_input_empty = user_input.strip() == ""

        if st.button("Buatkan Saya Rekomendasi", disabled=is_input_empty):
            dynamic_response, talent_count, recommended_role, talent_level, talent_description = generate_dynamic_response(user_input, pdf_text)

            # Since dynamic_response is now plain text (UI friendly),
            # we no longer try to decode it as JSON.
            dynamic_text = dynamic_response.strip()

            # If you want to extract specific information from the text, you can do so here.
            # For now we simply assign the full text to recommended_role
            #recommended_role = dynamic_text  
            #talent_count = 0
            #description = ""
            #talent_level = ""

            st.session_state["Recommended Role"] = recommended_role
            st.session_state["Talent Count"] = talent_count
            st.session_state["Talent Description"] = talent_description
            st.session_state["Talent Level"] = talent_level
            st.session_state["project_user_input"] = user_input

            # st.write(recommended_role)
            # st.write(talent_count)
            # st.write(talent_level)
            # st.write(talent_description)
            # st.write("Raw response_text:", repr(dynamic_response))

            selected_talent, talent_info = select_talent_from_pool(dynamic_response, talent_pool_df, talent_count)
            st.session_state["project_recommendation_result"] = {
                "dynamic_response": dynamic_text,
                "selected_talent": selected_talent,
                "talent_info": talent_info
            }
            st.session_state["project_recommendation_done"] = True

            # Force immediate UI refresh
            st.rerun()

    # Result Mode
    else:
        st.subheader("🤖 Rekomendasi")
        # Instead of attempting to parse the response as JSON, we directly use the plain text.

        dynamic_text = st.session_state["project_recommendation_result"]["dynamic_response"]

        # Retrieve the talent_count from session state
        talent_count = st.session_state.get("Talent Count", 0)

        #st.markdown("### Rekomendasi")
        st.write(dynamic_text)

        # Add separator
        st.markdown("---")  # This adds a separator line between the sections.

        try:
            selected_talent_data = json.loads(st.session_state["project_recommendation_result"]["selected_talent"])
        except Exception:
            selected_talent_data = st.session_state["project_recommendation_result"]["selected_talent"]

        st.markdown("### 🎯 Talent Terpilih")
        if isinstance(selected_talent_data, list):
            talent_df = pd.DataFrame(selected_talent_data)
            st.dataframe(talent_df)
        else:
            st.write(selected_talent_data)

        # Add separator
        st.markdown("---")  # This adds a separator line between the sections.

        st.markdown("### 📋 Konfirmasi")
        
        if talent_count == 0:
            st.warning("Silakan melakukan input ulang dengan konteks yang lebih jelas")
        else: 
            st.write("Berdasarkan rangkuman di atas, kami telah memilih talent dengan peran dan kemampuan yang sesuai "
            "dengan kebutuhan proyek Anda.\n\n"
            "Apakah Anda setuju dengan rekomendasi ini dan ingin meneruskan permintaan ke manajemen?"
            )

            if st.button("Setuju & Kirim ke Manajemen"):
                # Since dynamic_response is plain text, we use the stored Recommended Role value directly.
                recommended_role = st.session_state.get("Recommended Role", "Not Specified")

                payload = {
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Name": st.session_state.user_name,
                    "Unit": st.session_state.user_unit,
                    "Email": st.session_state.user_email,
                    "User Input": st.session_state.project_user_input,
                    "Recommended Role": recommended_role,
                    "Talent Level": str(st.session_state.get("Talent Level", "Not Specified")),
                    "Talent Count": st.session_state.get("Talent Count", 0),
                    "Talent Description": st.session_state.get("Talent Description", ""),
                    "Selected Talents": st.session_state["project_recommendation_result"]["talent_info"]
                }

                response = trigger_power_automate(payload)
                if response and response.status_code in [200, 202]:
                    st.success("Permintaan telah dikirim ke manajemen dan dicatat!")
                    st.sidebar.success("Notifikasi WhatsApp telah dikirim ke Tim Manajemen DSC mengenai permintaan Anda!")

                    with st.spinner("Membuat draft NDE..."):
                        doc_buffer = generate_official_document_integration(
                            st.session_state.get("Recommended Role", "Not Specified"),
                            st.session_state.user_unit,
                            st.session_state.get("Talent Count", 0),
                            st.session_state.get("Talent Level", 0),
                            st.session_state.get("Talent Description", ""),
                            point1,
                            point2,
                            point3
                        )
                    payload_doc, response_doc = sending_docs(doc_buffer, st.session_state.user_unit)
                    if response_doc and response_doc.status_code in [200, 202]:
                        the_unit = st.session_state.user_unit
                        draft_url = f"https://telkomind.sharepoint.com/:f:/r/sites/CIMOL/Shared%20Documents/Cimol%20ChatBOT/Draft%20NDE/{todays_date}_draft_NDE_{the_unit}.docx"
                        st.success(
                            f"Kami juga telah menyiapkan Draft NDE yang bisa Anda gunakan untuk melakukan request talent ke DSC. Anda dapat mengunduhnya melalui tautan berikut: [Download Draft NDE]({draft_url})"
                        )
                    else:
                        st.error("Gagal mengirim email draft NDE.")
                else:
                    st.error("Gagal mengirim permintaan karena email tidak valid atau tidak ada talent yang terpilih. Silakan cek email Anda serta cek input kebutuhan proyek data Anda")


        # Button to return to Input Mode
        st.markdown("---")
        st.markdown("### 🔄 Ulangi")
        st.write("Jika Anda tidak setuju atau ingin mengulangi input, Anda dapat menekan tombol berikut:")
        if st.button("Ulangi Input"):
            st.session_state["project_recommendation_done"] = False
            st.rerun()


# -------------------------------
# Inisialisasi Aplikasi & Alur Utama
# -------------------------------
st.set_page_config(
    page_title="Cimolbot - DSC Talent Request Portal",
    page_icon="logo.webp"
)

custom_css = """
<style>

/* Style the sidebar text and background */
[data-testid="stSidebar"] {
    background-color: #1F2C2F;
    color: #D1CEC8; /* text */
}

/* Style the main app text and background */
[data-testid="stAppViewContainer"] {
    background-color: #D1CEC8;
    color: #1F2C2F !important;
}

.st-emotion-cache-14553y9 {
        color: #1F2C2F;
    }

</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)

def main():
    #st.title("Data Role")
    st.logo("logo.webp", link="https://youtube.com/shorts/EZKCFyQ9QlI?si=fb-poFqRYWvrwWXv")
    st.markdown(
    """
    <style>
    html, body, [class*="css"] {
            font-family: "Source Sans Pro", sans-serif !important;
        }
    /* Target all labels inside the sidebar */
    [data-testid="stSidebar"] label {
         color: #D1CEC8;    
    }
    /* Apply styles to every element inside the radio widget */
    [data-baseweb="radio"] * {
         color: #D1CEC8; 
    }
    [data-baseweb="checkbox"] * {
         color: #D1CEC8; 
    }
    /* Target any button inside a div with class stButton */
    div.stButton button {
         background-color: #1F2C2F !important;
         color: #D1CEC8 !important;
         border: 2px !important;
         border-radius: 5px !important;
         padding: 0.5em 1em !important;
         font-size: 16px !important;
         transition: background-color 0.3s ease, color 0.3s ease;
    }
    /* On hover, swap the colors */
    div.stButton button:hover {
         background-color: #B9B1A9 !important;
         color: #1F2C2F !important;
    }
    /* On active (when clicked), swap the colors as well */
    div.stButton button:active {
         background-color: #D1CEC8 !important;
         color: #1F2C2F !important;
         border: 2px solid #1F2C2F !important;
    }

    /* Sidebar checkpoint size */
    [data-baseweb="checkbox"] .st-dr {
    height: 0.8rem;
    }
    [data-baseweb="checkbox"] .st-dq {
        width: 0.8rem;
    }

    [data-baseweb="checkbox"] .st-emotion-cache-1m4c89a {
    font-family: "Source Sans Pro", sans-serif;
    font-size: 0.8rem;
    }

    """,
    unsafe_allow_html=True
    )

# .st-dr {
#     width: 0.8rem;
#     }
#     .st-dq {
#     width: 0.8rem;
#     }
    st.sidebar.markdown("### Informasi Diri")
    user_name = st.sidebar.text_input("Nama:", placeholder="Tulis Nama Lengkap Anda")
    user_unit = st.sidebar.selectbox("Unit:", [
        "AGR", "BSP", "DAG", "DBE", "DEX", "DOA", "DPE", "DPM",
        "DSC", "DSZ", "EDU", "ENT", "EWZ", "GTP", "IDM", "IHX",
        "INS", "IOT", "LGS", "MKT", "PAS", "SMB", "SVC", "TOS"
    ])
    user_email = st.sidebar.text_input("Email:", placeholder="Direkomendasikan Email Telkom", )
    user_consent = st.sidebar.checkbox("Saya setuju dengan kebijakan privasi Cimolbot")
    if not (user_name and user_unit and user_email and user_consent):
        st.sidebar.warning("Pastikan semua informasi telah diisi dan Anda sudah setuju dengan kebijakan kami")
        start_mode()
        st.stop()

    st.session_state.user_name = user_name
    st.session_state.user_unit = user_unit
    st.session_state.user_email = user_email

    mode = st.sidebar.radio("Pilih Alur:", ("Chatbot", "Rekomendasi Talent"), index=None)
    
    if user_name.lower() == "fufufafa":
        st.sidebar.audio("fffafa.mp3", autoplay=True, loop=True)
    if mode== None:
        none_mode()
    elif mode == "Chatbot":
        chatbot_mode()
    else:
        project_recommendation_mode()

if __name__ == "__main__":
    main()
