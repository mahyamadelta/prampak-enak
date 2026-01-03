import streamlit as st
import pandas as pd
import json
import uuid
import time
from datetime import datetime
import paho.mqtt.client as mqtt

# --- KONFIGURASI MQTT ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "project/tralalilo_trolia/sensor"

# --- INISIALISASI SESSION STATE ---
if "session_active" not in st.session_state:
    st.session_state.session_active = False

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "session_label" not in st.session_state:
    st.session_state.session_label = None

if "data_buffer" not in st.session_state:
    st.session_state.data_buffer = []

if "last_message" not in st.session_state:
    st.session_state.last_message = None

# --- FUNGSI MQTT CALLBACK ---
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        # Simpan pesan terakhir ke variabel global/state sementara
        # Kita tidak bisa langsung akses st.session_state dengan aman dari thread background
        # Jadi kita simpan di list global atau queue jika perlu, tapi untuk Streamlit
        # cara termudah adalah memperbarui state dan memaksa rerun (jika menggunakan st.experimental_rerun)
        # Namun, di sini kita akan tampung di buffer global dulu.
        
        # Tambahkan timestamp saat diterima
        payload['rec_timestamp'] = datetime.now()
        
        # Masukkan ke queue userdata yang terhubung ke state streamlit
        if userdata is not None:
             userdata.append(payload)
             
    except Exception as e:
        print(f"Error parsing MQTT: {e}")

# --- SETUP MQTT CLIENT ---
@st.cache_resource
def setup_mqtt():
    # Kita gunakan list biasa sebagai 'userdata' untuk menampung pesan masuk
    message_queue = [] 
    client = mqtt.Client(userdata=message_queue)
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()
    return client, message_queue

# Inisialisasi Client
client, message_queue = setup_mqtt()

# --- TAMPILAN DASHBOARD ---
st.set_page_config(page_title="IoT Data Collector", layout="wide")
st.title("📡 AI Data Collector Dashboard")

# --- SIDEBAR KONTROL ---
with st.sidebar:
    st.header("🎮 Kontrol Sesi")
    
    # Pilihan Label
    label_input = st.selectbox(
        "Label Kondisi Udara:",
        ["Baik", "Sedang", "Tidak Sehat", "Sangat Tidak Sehat", "Berbahaya"]
    )

    # Tombol Start/Stop
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("▶️ Start Rec", type="primary", disabled=st.session_state.session_active):
            st.session_state.session_active = True
            st.session_state.session_label = label_input
            st.session_state.session_id = str(uuid.uuid4())[:8] # Ambil 8 karakter aja biar pendek
            st.success("Sesi Dimulai!")
            st.rerun()

    with col_btn2:
        if st.button("⏹ Stop Rec", disabled=not st.session_state.session_active):
            st.session_state.session_active = False
            st.warning("Sesi Dihentikan.")
            st.rerun()

    # Status Indikator
    if st.session_state.session_active:
        st.success(f"🔴 PEREKAMAN AKTIF\n\nID: {st.session_state.session_id}\nLabel: {st.session_state.session_label}")
    else:
        st.info("⚪ MENUNGGU")

    st.markdown("---")
    
    # Tombol Download
    if st.session_state.data_buffer:
        df_download = pd.DataFrame(st.session_state.data_buffer)
        csv = df_download.to_csv(index=False).encode('utf-8')
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dataset_{st.session_state.session_label}_{timestamp_str}.csv"
        
        st.download_button(
            label="💾 Download CSV",
            data=csv,
            file_name=filename,
            mime="text/csv",
        )
        
        if st.button("🗑️ Reset Buffer"):
            st.session_state.data_buffer = []
            st.rerun()

# --- LOGIKA PEMROSESAN DATA ---
# Cek apakah ada pesan baru di queue MQTT
while message_queue:
    # Ambil pesan paling lama (FIFO)
    payload = message_queue.pop(0) 
    
    # Update tampilan 'Last Message' meskipun tidak sedang merekam
    st.session_state.last_message = payload

    # Jika sesi aktif, simpan ke buffer data
    if st.session_state.session_active:
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session_id": st.session_state.session_id,
            "label": st.session_state.session_label,
            "suhu": payload.get("suhu", 0),
            "hum": payload.get("hum", 0),
            "co_ppm": payload.get("co_ppm", 0),
            "dust_mg": payload.get("dust_mg", 0),
            "mq7_raw": payload.get("mq7_raw", 0),
            "mq7_volt": payload.get("mq7_volt", 0),
            "dust_raw": payload.get("dust_raw", 0),
            "dust_volt": payload.get("dust_volt", 0)
        }
        st.session_state.data_buffer.append(record)

# --- VISUALISASI ---
# Layout Metrik Utama
col1, col2, col3, col4 = st.columns(4)

# Gunakan data terakhir yang diterima untuk menampilkan metrik
current_data = st.session_state.last_message if st.session_state.last_message else {}

with col1:
    st.metric("Suhu (°C)", value=current_data.get("suhu", "-"))
with col2:
    st.metric("Kelembapan (%)", value=current_data.get("hum", "-"))
with col3:
    st.metric("CO (PPM)", value=current_data.get("co_ppm", "-"))
with col4:
    st.metric("Debu (mg/m³)", value=current_data.get("dust_mg", "-"))

st.markdown("### 📊 Live Data Buffer")

# Tampilkan Tabel Data
if st.session_state.data_buffer:
    df = pd.DataFrame(st.session_state.data_buffer)
    # Tampilkan data terbaru di atas
    st.dataframe(df.sort_index(ascending=False).head(10), use_container_width=True)
    st.caption(f"Total data tersimpan: {len(df)} baris")
else:
    st.info("Belum ada data yang direkam dalam sesi ini.")

# --- AUTO REFRESH ---
# Ini trik agar Streamlit terus membaca queue message tanpa interaksi user
time.sleep(1) 
st.rerun()