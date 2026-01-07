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
st.set_page_config(page_title="Air Quality Collector", layout="wide")
st.title("📡 ISPU Data Collector Dashboard")

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
            st.session_state.session_id = str(uuid.uuid4())[:8] 
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
        filename = f"ISPU_Dataset_{st.session_state.session_label}_{timestamp_str}.csv"
        
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
while message_queue:
    payload = message_queue.pop(0) 
    st.session_state.last_message = payload

    if st.session_state.session_active:
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session_id": st.session_state.session_id,
            "label": st.session_state.session_label,
            
            # Parameter Sensor Lokal & API
            "suhu": payload.get("suhu", 0),
            "kelembaban": payload.get("kelembaban", 0),
            "co_mg": payload.get("co", 0),      # mg/m3
            "pm25_ug": payload.get("pm25", 0),  # ug/m3
            "no2_ug": payload.get("no2", 0),
            "pm10_ug": payload.get("pm10", 0),
            "so2_ug": payload.get("so2", 0),
            "o3_ug": payload.get("o3", 0)
        }
        st.session_state.data_buffer.append(record)

# --- VISUALISASI ---
current_data = st.session_state.last_message if st.session_state.last_message else {}

# 1. METRICS (ANGKA BESAR)
st.subheader("🏠 Sensor Lokal")
row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
with row1_col1:
    st.metric("Suhu (°C)", value=current_data.get("suhu", "-"))
with row1_col2:
    st.metric("Kelembapan (%)", value=current_data.get("kelembaban", "-"))
with row1_col3:
    st.metric("CO (mg/m³)", value=current_data.get("co", "-"))
with row1_col4:
    st.metric("PM 2.5 (µg/m³)", value=current_data.get("pm25", "-"))

st.subheader("☁️ Data API (WAQI)")
row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)
with row2_col1:
    st.metric("NO₂ (µg/m³)", value=current_data.get("no2", "-"))
with row2_col2:
    st.metric("PM 10 (µg/m³)", value=current_data.get("pm10", "-"))
with row2_col3:
    st.metric("SO₂ (µg/m³)", value=current_data.get("so2", "-"))
with row2_col4:
    st.metric("O₃ (µg/m³)", value=current_data.get("o3", "-"))

# 2. GRAFIK (LINE CHARTS)
st.markdown("---")
st.subheader("📈 Grafik Tren Real-time")

if st.session_state.data_buffer:
    # Buat DataFrame dari buffer
    df_chart = pd.DataFrame(st.session_state.data_buffer)
    # Konversi kolom timestamp ke datetime object agar sumbu X benar
    df_chart['timestamp'] = pd.to_datetime(df_chart['timestamp'])
    # Set timestamp sebagai index untuk plotting
    df_chart = df_chart.set_index('timestamp')

    # Gunakan Tabs agar grafik tidak menumpuk memanjang ke bawah
    tab1, tab2, tab3 = st.tabs(["🌡️ Lingkungan Fisik", "🌫️ Partikel Debu", "☠️ Gas Polutan"])

    with tab1:
        st.caption("Grafik Suhu dan Kelembapan")
        st.line_chart(df_chart[['suhu', 'kelembaban']])

    with tab2:
        st.caption("Grafik Partikulat (PM2.5 Lokal & PM10 API)")
        st.line_chart(df_chart[['pm25_ug', 'pm10_ug']])

    with tab3:
        st.caption("Grafik Gas (CO, NO2, SO2, O3)")
        st.line_chart(df_chart[['co_mg', 'no2_ug', 'so2_ug', 'o3_ug']])

else:
    st.info("Menunggu data untuk menampilkan grafik...")

# 3. TABEL DATA
st.markdown("### 📊 Live Data Buffer")

if st.session_state.data_buffer:
    df = pd.DataFrame(st.session_state.data_buffer)
    st.dataframe(df.sort_index(ascending=False).head(10), use_container_width=True)
    st.caption(f"Total data tersimpan: {len(df)} baris")
else:
    st.info("Belum ada data yang direkam dalam sesi ini.")

# --- AUTO REFRESH ---
time.sleep(1) 
st.rerun()
