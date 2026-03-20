import streamlit as st
import googlemaps
from fpdf import FPDF
import urllib.parse
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN Y DATOS DE REFERENCIA ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
except:
    st.error("⚠️ Error: MAPS_API_KEY no configurada.")

# Tabla de referencia basada en tus datos
data_referencia = [
    {"EXPO": "EXPO", "ORIGEN": "MTY-AREA METRO", "DESTINO": "NUEVO LAREDO", "KM": 230, "CPK": 26.0, "MARGEN": 0.25, "TC": 17.0},
    {"EXPO": "EXPO", "ORIGEN": "SALTILLO - RAMOS", "DESTINO": "NUEVO LAREDO", "KM": 310, "CPK": 24.0, "MARGEN": 0.25, "TC": 17.0},
    {"EXPO": "EXPO", "ORIGEN": "DERRAMADERO", "DESTINO": "NUEVO LAREDO", "KM": 380, "CPK": 25.0, "MARGEN": 0.25, "TC": 17.0},
    {"EXPO": "IMPO", "ORIGEN": "NUEVO LAREDO", "DESTINO": "MTY-AREA METRO", "KM": 230, "CPK": 31.1, "MARGEN": 0.25, "TC": 17.0},
    {"EXPO": "IMPO", "ORIGEN": "NUEVO LAREDO", "DESTINO": "SALTILLO - RAMOS", "KM": 310, "CPK": 28.0, "MARGEN": 0.25, "TC": 17.0},
    {"EXPO": "IMPO", "ORIGEN": "NUEVO LAREDO", "DESTINO": "DERRAMADERO", "KM": 380, "CPK": 28.1, "MARGEN": 0.25, "TC": 17.0},
]
df_ref = pd.DataFrame(data_referencia)

st.set_page_config(page_title="Cotizador Maestro Logístico", layout="wide")

# Inicializar historial en la sesión si no existe
if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. BARRA LATERAL: PREMISAS Y TABLA DE REFERENCIA ---
with st.sidebar:
    st.header("⚙️ Premisas de Venta")
    cpk_premesa = st.number_input("CPK Objetivo ($)", min_value=0.0, value=28.0, step=0.5)
    margen_premesa = st.slider("Margen de Utilidad (%)", 0, 100, 25) / 100
    tipo_cambio = st.number_input("Tipo de Cambio (USD/MXN)", value=18.50)
    
    st.markdown("---")
    st.subheader("📊 Tabla de Referencia")
    st.dataframe(df_ref[['ORIGEN', 'DESTINO', 'CPK']], hide_index=True)
    
    st.markdown("---")
    telefono_wa = st.text_input("WhatsApp (521...)")

st.title("Cotizador Logístico Pro 🚚")

# --- 3. ENTRADA DE RUTA ---
col1, col2 = st.columns(2)
with col1:
    origen = st.text_input("Origen", placeholder="Ej. Santa Catarina, NL")
with col2:
    destino = st.text_input("Destino", placeholder="Ej. Nuevo Laredo")

distancia_km = 0
tiempo = ""

if origen and destino:
    try:
        res = gmaps.directions(origen, destino, mode="driving")
        if res:
            distancia_km = res[0]['legs'][0]['distance']['value'] / 1000
            tiempo = res[0]['legs'][0]['duration']['text']
            st.info(f"🛣️ Distancia: {distancia_km:.2f} km | ⏱️ Tiempo: {tiempo}")
    except:
        st.error("Error en Google Maps")

# --- 4. COSTOS ADICIONALES Y EXTRAS (LOS 4 ESPACIOS) ---
st.markdown("### 💰 Gastos y Otros Cargos")
c_op1, c_op2 = st.columns(2)

with c_op1:
    c_casetas = st.number_input("Casetas ($)", min_value=0.0)
    c_maniobras = st.number_input("Maniobras ($)", min_value=0.0)
    c_seguro = st.number_input("Seguro / Otros ($)", min_value=0.0)

with c_op2:
    with st.expander("➕ Agregar hasta 4 Cargos Extra"):
        e1_n = st.text_input("Concepto 1"); e1_v = st.number_input("Monto 1", key="v1")
        e2_n = st.text_input("Concepto 2"); e2_v = st.number_input("Monto 2", key="v2")
        e3_n = st.text_input("Concepto 3"); e3_v = st.number_input("Monto 3", key="v3")
        e4_n = st.text_input("Concepto 4"); e4_v = st.number_input("Monto 4", key="v4")

# --- 5. LÓGICA DE CÁLCULO ---
flete_base = distancia_km * cpk_premesa
total_otros = c_casetas + c_maniobras + c_seguro + e1_v + e2_v + e3_v + e4_v
venta_total_mxn = flete_base + total_otros
venta_total_usd = venta_total_mxn / tipo_cambio

# --- 6. RESULTADOS Y BOTÓN DE GUARDAR ---
st.markdown("---")
r1, r2, r3 = st.columns(3)
r1.metric("TARIFA MXN", f"${venta_total_mxn:,.2f}")
r2.metric("TARIFA USD", f"${venta_total_usd:,.2f}")
r3.metric("DISTANCIA", f"{distancia_km:.2f} KM")

if st.button("💾 Guardar en Historial"):
    nueva_entrada = {
        "Fecha": datetime.now().strftime("%H:%M:%S"),
        "Ruta": f"{origen} -> {destino}",
        "KM": round(distancia_km, 2),
        "Total MXN": round(venta_total_mxn, 2)
    }
    st.session_state.historial.insert(0, nueva_entrada)
    st.success("Cotización guardada en el historial de abajo.")

# --- 7. EXPORTACIÓN ---
st.markdown("### 📤 Salida")
b1, b2 = st.columns(2)

with b1:
    if st.button("📄 Descargar PDF"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "COTIZACIÓN FORMAL", ln=True, align="C")
        pdf.set_font("Arial", size=12)
        pdf.ln(10)
        pdf.cell(0, 8, f"Ruta: {origen} a {destino}", ln=True)
        pdf.cell(0, 8, f"Distancia: {distancia_km:.2f} km", ln=True)
        pdf.cell(0, 8, f"Flete Base (CPK ${cpk_premesa}): ${flete_base:,.2f}", ln=True)
        pdf.cell(0, 8, f"Cargos Adicionales: ${total_otros:,.2f}", ln=True)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f"TOTAL: ${venta_total_mxn:,.2f} MXN", ln=True)
        pdf_bytes = pdf.output(dest="S")
        st.download_button("Guardar PDF", pdf_bytes, "cotizacion.pdf")

with b2:
    msg = f"Cotización: {origen}-{destino}\nTotal: ${venta_total_mxn:,.2f} MXN"
    url = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(msg)}"
    st.markdown(f'[📲 Enviar WhatsApp]({url})')

# --- 8. HISTORIAL DE CONSULTAS ---
st.markdown("---")
st.subheader("📜 Historial de esta sesión")
if st.session_state.historial:
    st.table(pd.DataFrame(st.session_state.historial))
else:
    st.write("No hay cotizaciones guardadas aún.")
