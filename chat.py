#WITHOUT WHATSAPP WHEN THE DAILY LIMIT HAS BEEN REACHED

import streamlit as st
import pandas as pd
import PyPDF2
import os
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
flow_url = "https://prod-31.southeastasia.logic.azure.com:443/workflows/9aab47d509544fe1a846f947af3b8580/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=-vUSeDSLQY00EA57lHwqlfVkzLQtDleIbXz4YaEX3cI"
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

flow_url2 = "https://prod-51.southeastasia.logic.azure.com:443/workflows/95844ecd091c48e3a96421f3b94c533a/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=eL8aW2Tw-g2EY1DCm48BkS20ndKCi_3fF69kL02R6Lc"
response2 = requests.post(flow_url2)
flow_url3 = "https://prod-84.southeastasia.logic.azure.com:443/workflows/58d3a562a2b74100ad2471980a6dd83b/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=CUZ-XRmAL_ycr9jElfal2cN6TlFHvphDdowY_I56Vcg"

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
    api_key="randomkey",  # Ganti dengan API key Anda
    base_url="https://telkom-ai-dag-api.apilogy.id/Telkom-LLM/0.0.4/llm",
    default_headers={"x-api-key": "88JWNTBHM4OXBusCLZuBYGUGBBrTE2iD"}  # Ganti dengan API key Anda
)

# -------------------------------
# Fungsi Notifikasi WhatsApp via Twilio
# -------------------------------
# def send_whatsapp_notification(sender_name: str, sender_unit: str, user_input: str):
#     account_sid = 'AC69aca05267b8ed556fa1a3b1246e8015'  # Twilio SID Anda
#     auth_token = 'e71a0afb57302d8889a12fc144921727'       # Twilio Auth Token Anda
#     client_twilio = Client(account_sid, auth_token)

#     message = client_twilio.messages.create(
#         from_='whatsapp:+14155238886',  # Nomor sandbox Twilio
#         body=(
#             f"Permintaan Talenta baru telah dikirim pada {todays_date}!\n\n"
#             f"Permintaan ini dikirim oleh {sender_name} dari {sender_unit}.\n\n"
#             f"Berikut kebutuhannya: \n\n {user_input} \n\n"
#             "Periksa email serta channel teams Anda untuk informasi selengkapnya."
#         ),
#         to='whatsapp:+6282190566305'
#     )
#     print(message.sid)

# -------------------------------
# Fungsi Webhook untuk Memicu Power Automate
# -------------------------------
def trigger_power_automate(payload: dict):
    webhook_url = "https://prod-59.southeastasia.logic.azure.com:443/workflows/600114214da148eea88c68bed87b2f46/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=oxPCcf0WivPxuIz_gcRUnj8qFEfTPHelRgEcCJzSd_w"
    if not webhook_url:
        st.error("URL webhook Power Automate tidak dikonfigurasi.")
        return None
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        st.write("Status:", response.text)
        return response
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memicu Power Automate: {str(e)}")
        return None

# -------------------------------
# Fungsi Rekomendasi Talent (Mode Rekomendasi)
# -------------------------------
def generate_dynamic_response(user_input: str, context: str) -> str:
    prompt = (
        f"Berikut adalah informasi mengenai data role dari dokumen:\n{context}\n\n"
        f"Pertanyaan pengguna: {user_input}\n"
        "Berdasarkan informasi di atas, tolong rekomendasikan data role yang tepat, jumlah orang yang diperlukan, "
        "dan alasan singkat untuk rekomendasi tersebut. Jawab pertanyaan di atas secara deskriptif dan sertakan ringkasan "
        "dalam format JSON dengan format seperti:\n\n"
        '"recommended_role": "<role>"\n'
        '"talent_level": "<level (Junior, Middle, atau Senior)>"\n'
        '"talent_count": <number>\n'
        '"description": "<harus dalam format bullets poin yang menyebutkan pengalaman dan keahlian yang dibutuhkan>"'
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

def select_talent_from_pool(dynamic_response: str, talent_pool_df: pd.DataFrame) -> str:
    prompt = (
        "Berikut adalah respons dinamis yang berisi rekomendasi peran dan jumlah talent yang dibutuhkan "
        "dalam format JSON:\n"
        f"{dynamic_response}\n\n"
        "Berikut adalah data talent yang tersedia dalam format JSON:\n"
        f"{talent_pool_df}\n\n"
        "Berdasarkan rekomendasi di atas, pilihlah talent yang sesuai dengan peran yang direkomendasikan "
        "dan jumlah yang dibutuhkan, serta siap diassign. Keluarkan hasilnya dalam format JSON dengan jumlah "
        "talent yang dipilih sama dengan jumlah yang direkomendasikan pada dynamic_response. Setiap entry harus "
        "berupa objek dengan kunci 'Nama', 'JOB ROLE USECASE', dan 'UniqueCode' yang diambil langsung dari data di talent_pool_df. "
        "Jangan sertakan detail tentang status penugasan."
        "Tampilkan dalam format JSON dengan format seperti:\n\n"
        '"Nama": "<nama>"\n'
        '"JOB ROLE USECASE: "<Job role usecase>"\n'
        '"UniqueCode": <UniqueCode>'
        
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
    doc_text = "Draft NDE telah dihasilkan di memori."
    return output_buffer, doc_text

# -------------------------------
# Fungsi Mode Chatbot
# -------------------------------
def chatbot_mode():
    st.subheader("Mode Chatbot (Pertanyaan Umum Terkait Data Role)")
    with st.expander("Panduan"):
        #st.balloons()
        st.write("Selamat datang di Mode Pertanyaan Umum! \n\n"
            "Chatbot ini dirancang untuk membantu setiap unit yang membutuhkan talent data dari chapter DSC. Di sini, Anda dapat mengajukan pertanyaan mengenai berbagai role data—mulai dari ruang lingkup, tanggung jawab, hingga kemampuan masing-masing—sehingga Anda dapat memahami dengan jelas bagaimana setiap peran dapat mendukung kebutuhan proyek Anda. Setelah Anda mengenal peran-peran yang tersedia, Anda dapat beralih ke Chatbot Rekomendasi Talent kami untuk mendapatkan saran yang dipersonalisasi tentang role data ideal yang sesuai dengan proyek spesifik Anda. \n\n \n\n Tapi, jangan khawatir! Anda juga tetap bisa menanyakan pertanyaan yang tidak berhubungan dengan Data ke chatbot ini 😉")
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Tulis pesan Anda:")
        submitted = st.form_submit_button("Kirim")

    if submitted and user_input.strip():
        with st.spinner("Memproses jawaban..."):
            st.session_state.chat_history.append({"role": "pengguna", "content": user_input.strip()})
            response = chatbot_response(user_input.strip(), st.session_state.chat_history)
            st.session_state.chat_history.append({"role": "bot", "content": response})

    for msg in st.session_state.chat_history:
        if msg["role"] == "pengguna":
            st.markdown(f"**Pengguna:** {msg['content']}")
        else:
            st.markdown(f"**Bot:** {msg['content']}")

def chatbot_response(user_input: str, chat_history: list) -> str:
    conversation_str = ""
    for msg in chat_history:
        conversation_str += f"{msg['role'].capitalize()}: {msg['content']}\n"
    prompt = (
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
    st.subheader("Mode Rekomendasi Talent")
    with st.expander("Panduan"):
        st.snow()
        st.write("Selamat datang di Mode Rekomendasi Data Talent!\n\n"
                "Chatbot ini dirancang untuk membantu setiap unit menemukan ahli data yang tepat sesuai dengan kebutuhan proyek Anda. "
                "Cukup deskripsikan jenis proyek yang akan Anda kerjakan serta harapan Anda terhadap peran talenta yang diinginkan, "
                "dan sistem kami akan memberikan rekomendasi yang dipersonalisasi berdasarkan kriteria tersebut. "
                "Apakah Anda mencari data analyst, data engineer, atau spesialis machine learning, kami siap membantu Anda menemukan kandidat yang paling sesuai! \n\n \n\n"
                )
        st.markdown("""
                Berikut beberapa contoh prompt yang dapat membantu Anda memulai:

                - "Saya sedang mengerjakan proyek analisis pasar dan membutuhkan data analyst yang handal untuk menganalisa tren penjualan serta statistik."

                - "Proyek saya adalah pengembangan sistem rekomendasi untuk e-commerce. Saya membutuhkan spesialis machine learning dengan pengalaman di deep learning dan data mining."

                - "Dalam proyek optimasi supply chain, saya memerlukan data engineer yang berpengalaman dalam ETL dan pengelolaan data besar."

                - "Untuk mendukung proyek riset tren konsumen, saya mencari data scientist yang ahli dalam analisis big data dan visualisasi data."

                - "Proyek saya berkaitan dengan prediksi penjualan menggunakan algoritma forecasting. Apakah ada analis data dengan pengalaman serupa?"
                    """)

    if "project_recommendation_done" not in st.session_state:
        st.session_state["project_recommendation_done"] = False
    if "project_recommendation_result" not in st.session_state:
        st.session_state["project_recommendation_result"] = {}
    if "project_user_input" not in st.session_state:
        st.session_state["project_user_input"] = ""
    
    user_input = st.text_input("Apa kebutuhan data proyek Anda?", key="proj_input")

    if st.button("Kirim Rekomendasi"):
        dynamic_response = generate_dynamic_response(user_input, pdf_text)
        
        recommended_role = None
        talent_count = None
        description = None
        talent_level = None

        try:
            dynamic_json = json.loads(dynamic_response)
        except json.JSONDecodeError:
            start_idx = dynamic_response.find('{')
            end_idx = dynamic_response.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = dynamic_response[start_idx:end_idx+1]
                try:
                    dynamic_json = json.loads(json_str)
                except Exception as e:
                    st.error("Gagal memparsing JSON. Error: " + str(e))
                    dynamic_json = None
            else:
                dynamic_json = None

        if dynamic_json:
            if isinstance(dynamic_json, list) and len(dynamic_json) > 0:
                dynamic_json = dynamic_json[0]
            recommended_role = dynamic_json.get("recommended_role", "")
            talent_count = dynamic_json.get("talent_count", 0)
            description = dynamic_json.get("description", "")
            talent_level = dynamic_json.get("talent_level", "")
        else:
            st.error("Gagal memparsing dynamic_response sebagai JSON yang valid. Mohon periksa format output LLM.")

        st.session_state["recommended_role"] = recommended_role
        st.session_state["talent_count"] = talent_count
        st.session_state["description"] = description
        st.session_state["talent_level"] = talent_level
        st.session_state["project_user_input"] = user_input

        selected_talent = select_talent_from_pool(dynamic_response, talent_pool_df)
        st.session_state["project_recommendation_result"] = {
            "dynamic_response": dynamic_response,
            "selected_talent": selected_talent
        }
        st.session_state["project_recommendation_done"] = True

    if st.session_state["project_recommendation_done"]:
        st.subheader("🤖 Rekomendasi (LLM-enhanced):")
        try:
            dynamic_data = json.loads(st.session_state["project_recommendation_result"]["dynamic_response"])
            if isinstance(dynamic_data, list) and len(dynamic_data) > 0:
                dynamic_data = dynamic_data[0]
        except Exception:
            dynamic_data = {}
        if dynamic_data:
            st.markdown("### Rekomendasi")
            st.markdown(f"**Recommended Role:** {dynamic_data.get('recommended_role', 'N/A')}")
            st.markdown(f"**Talent Level:** {dynamic_data.get('talent_level', 'N/A')}")
            st.markdown(f"**Talent Count:** {dynamic_data.get('talent_count', 'N/A')}")
            st.markdown(f"**Description:** {dynamic_data.get('description', 'N/A')}")
        else:
            st.write("Dynamic Response:", st.session_state["project_recommendation_result"]["dynamic_response"])
        
        try:
            selected_talent_data = json.loads(st.session_state["project_recommendation_result"]["selected_talent"])
        except Exception:
            selected_talent_data = st.session_state["project_recommendation_result"]["selected_talent"]
        st.markdown("### Talent Terpilih")
        if isinstance(selected_talent_data, list):
            talent_df = pd.DataFrame(selected_talent_data)
            st.dataframe(talent_df)
        else:
            st.write("Talent Terpilih:", selected_talent_data)
        
        st.markdown("### 📋 Konfirmasi")
        st.write(
            "Berdasarkan rangkuman di atas, kami telah memilih talent dengan peran dan kemampuan yang sesuai "
            "dengan kebutuhan proyek Anda.\n\n"
            "Apakah Anda setuju dengan rekomendasi ini dan ingin meneruskan permintaan ke manajemen?"
        )

        if st.button("Setuju & Kirim ke Manajemen"):
            log_recommendation(
                st.session_state.user_name,
                st.session_state.user_unit,
                st.session_state.user_email,
                st.session_state.project_user_input,
                st.session_state["project_recommendation_result"]["dynamic_response"],
                st.session_state["project_recommendation_result"]["selected_talent"]
            )
            
            try:
                dynamic_json = json.loads(st.session_state["project_recommendation_result"]["dynamic_response"])
                if isinstance(dynamic_json, list) and len(dynamic_json) > 0:
                    dynamic_json = dynamic_json[0]
                recommended_role = dynamic_json.get("recommended_role", "Not Specified")
            except Exception:
                recommended_role = "Not Specified"
            
            payload = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Name": st.session_state.user_name,
                "Unit": st.session_state.user_unit,
                "Email": st.session_state.user_email,
                "User Input": st.session_state.project_user_input,
                "Recommended Role": st.session_state.get("recommended_role", "Not Specified"),
                "Talent Level": str(st.session_state.get("talent_level", "Not Specified")),
                "Talent Count": st.session_state.get("talent_count", 0),
                "Description": st.session_state.get("description", ""),
                "Selected Talents": st.session_state["project_recommendation_result"]["selected_talent"],
                "Matched Talent List": st.session_state["project_recommendation_result"]["dynamic_response"]
            }

            response = trigger_power_automate(payload)
            if response and response.status_code in [200, 202]:
                st.success("Permintaan telah dikirim ke manajemen dan dicatat!")
                #send_whatsapp_notification(st.session_state.user_name, st.session_state.user_unit, st.session_state.project_user_input)
                st.sidebar.success("Notifikasi WhatsApp telah dikirim ke Tim Manajemen DSC mengenai permintaan Anda!")
                
                with st.spinner("Membuat draft NDE..."):
                    doc_buffer, doc_text = generate_official_document_integration(
                        st.session_state.get("recommended_role", "Not Specified"),
                        st.session_state.user_unit,
                        st.session_state.get("talent_count", 0),
                        st.session_state.get("talent_level", 0),
                        st.session_state.get("description", ""),
                        point1,
                        point2,
                        point3
                    )
                payload_doc, response_doc = sending_docs(doc_buffer, st.session_state.user_unit)
                if response_doc and response_doc.status_code in [200, 202]:
                    the_unit = st.session_state.user_unit
                    st.success(f"Draft NDE telah tersedia. Anda dapat mengaksesnya melalui tautan: https://telkomind.sharepoint.com/:f:/r/sites/CIMOL/Shared%20Documents/Cimol%20ChatBOT/Draft%20NDE/{todays_date}_draft_NDE_{the_unit}.docx")
                    
                else:
                    st.error("Gagal mengirim email draft NDE.")
            else:
                st.error("Gagal mengirim permintaan ke Power Automate. Silakan coba lagi.")

# -------------------------------
# Inisialisasi Aplikasi & Alur Utama
# -------------------------------
st.set_page_config(
    page_title="🤖 Cimolbot 🍡",
    page_icon="🍡"
)

def main():
    st.title("Data Role")
    st.sidebar.markdown("### Informasi Diri")
    user_name = st.sidebar.text_input("Nama:")
    user_unit = st.sidebar.selectbox("Unit:", [
        "AGR", "BSP", "DAG", "DBE", "DEX", "DOA", "DPE", "DPM",
        "DSC", "DSZ", "EDU", "ENT", "EWZ", "GTP", "IDM", "IHX",
        "INS", "IOT", "LGS", "MKT", "PAS", "SMB", "SVC", "TOS"
    ])
    user_email = st.sidebar.text_input("Email:")

    if not (user_name and user_unit and user_email):
        st.sidebar.warning("Silakan lengkapi informasi diri Anda apabila Anda setuju dengan kebijakan privasi berikut: \n\n"
                           " \n\n"
                           "🔒 Pemberitahuan Privasi dan Persetujuan 🔒 \n\n"
                            "Dengan menggunakan aplikasi ini, Anda memberikan persetujuan kepada kami untuk mengumpulkan, menyimpan, dan memproses informasi pribadi berikut untuk tujuan operasional aplikasi: \n\n"
                            "- Nama, \n\n - Unit Kerja, \n\n - Email, dan \n\n - Input lain yang Anda berikan. \n\n"
                            "*Terakhir diperbarui: Maret 2025*"
                           )
        st.stop()

    st.session_state.user_name = user_name
    st.session_state.user_unit = user_unit
    st.session_state.user_email = user_email

    mode = st.sidebar.radio("Pilih Alur:", ("Chatbot", "Rekomendasi Talent"))
    if mode == "Chatbot":
        chatbot_mode()
    else:
        project_recommendation_mode()

if __name__ == "__main__":
    main()
