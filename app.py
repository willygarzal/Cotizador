import streamlit as st
import googlemaps
from fpdf import FPDF
import urllib.parse

# --- 1. CONFIGURACIÓN DE API (Desde secrets.toml) ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
except Exception:
    st.error("⚠️ Error: No se encontró 'MAPS_API_KEY' en .streamlit/secrets.toml")

st.set_page_config(page_title="Cotizador Logístico Pro", layout="wide")
st.title("Cotizador Logístico Pro 🚚")

# --- 2. BARRA LATERAL: PREMISAS PARA JUGAR CON EL MARGEN ---
with st.sidebar:
    st.header("⚙️ Premisas Financieras")
    # Aquí es donde "juegas" con los números clave
    tipo_cambio = st.number_input("Tipo de Cambio (USD/MXN)", min_value=1.0, value=18.50, step=0.10)
    precio_diesel = st.number_input("Precio Diesel ($/Lito)", min_value=0.0, value=24.50, step=0.50)
    rendimiento = st.number_input("Rendimiento (km/L)", min_value=0.1, value=2.2, step=0.1)
    
    st.markdown("---")
    # EL MARGEN: La palanca principal
    margen_utilidad = st.slider("Margen de Utilidad (%)", min_value=0, max_value=100, value=25)
    porcentaje_margen = margen_utilidad / 100
    
    st.markdown("---")
    telefono_wa = st.text_input("WhatsApp para envío (ej: 5218123456789)", "")

# --- 3. SECCIÓN DE RUTA (GOOGLE MAPS) ---
st.markdown("### 📍 Detalles de la Ruta")
col_orig, col_dest = st.columns(2)
with col_orig:
    origen = st.text_input("Ciudad de Origen", "Monterrey, NL")
with col_dest:
    destino = st.text_input("Ciudad de Destino", "Nuevo Laredo, Tamps")

distancia_km = 0
tiempo_estimado = ""

if origen and destino:
    try:
        res = gmaps.directions(origen, destino, mode="driving")
        if res:
            distancia_km = res[0]['legs'][0]['distance']['value'] / 1000
            tiempo_estimado = res[0]['legs'][0]['duration']['text']
            st.success(f"🛣️ Distancia: {distancia_km:.2f} km | ⏱️ Tiempo: {tiempo_estimado}")
    except:
        st.error("Error al calcular ruta con Google Maps.")

# --- 4. CÁLCULOS TÉCNICOS (CPK Y DIESEL) ---
costo_diesel_por_km = precio_diesel / rendimiento if rendimiento > 0 else 0
gasto_total_diesel = costo_diesel_por_km * distancia_km

# --- 5. DESGLOSE DE COSTOS Y CARGOS EXTRA ---
st.markdown("### 💰 Gastos y Cargos Adicionales")
c1, c2 = st.columns(2)

with c1:
    st.write("**Costos Operativos Fijos**")
    c_casetas = st.number_input("Casetas ($)", min_value=0.0, step=100.0)
    c_maniobras = st.number_input("Maniobras ($)", min_value=0.0, step=100.0)
    c_seguro = st.number_input("Seguro / Otros ($)", min_value=0.0, step=100.0)

with c2:
    st.write("**Cargos Extra Personalizados**")
    with st.expander("Agregar hasta 4 cargos adicionales"):
        e1_n = st.text_input("Concepto 1", placeholder="Ej. Escolta")
        e1_v = st.number_input("Monto 1 ($)", min_value=0.0, key="e1")
        e2_n = st.text_input("Concepto 2", placeholder="Ej. Pernocta")
        e2_v = st.number_input("Monto 2 ($)", min_value=0.0, key="e2")
        e3_n = st.text_input("Concepto 3")
        e3_v = st.number_input("Monto 3 ($)", min_value=0.0, key="e3")
        e4_n = st.text_input("Concepto 4")
        e4_v = st.number_input("Monto 4 ($)", min_value=0.0, key="e4")

# --- 6. LÓGICA FINANCIERA FINAL ---
costo_total_operativo = gasto_total_diesel + c_casetas + c_maniobras + c_seguro + e1_v + e2_v + e3_v + e4_v

# Fórmula de Venta: Costo / (1 - Margen)
if porcentaje_margen < 1:
    precio_venta_mxn = costo_total_operativo / (1 - porcentaje_margen)
else:
    precio_venta_mxn = costo_total_operativo # Evita división por cero al 100%

precio_venta_usd = precio_venta_mxn / tipo_cambio
cpk_real = precio_venta_mxn / distancia_km if distancia_km > 0 else 0

# --- 7. PANEL DE RESULTADOS ---
st.markdown("---")
r1, r2, r3 = st.columns(3)
r1.metric("VENTA SUGERIDA (MXN)", f"${precio_venta_mxn:,.2f}", f"Margen: {margen_utilidad}%")
r2.metric("VENTA SUGERIDA (USD)", f"${precio_venta_usd:,.2f}")
r3.metric("CPK (Costo por KM)", f"${cpk_real:,.2f}")

# --- 8. ENVÍO Y EXPORTACIÓN ---
st.markdown("### 📤 Finalizar Cotización")
btn_pdf, btn_wa = st.columns(2)

with btn_pdf:
    if st.button("📄 Generar PDF"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "COTIZACIÓN LOGÍSTICA PRO", ln=True, align="C")
        pdf.set_font("Arial", size=10)
        pdf.ln(5)
        pdf.cell(0, 7, f"Ruta: {origen} -> {destino}", ln=True)
        pdf.cell(0, 7, f"Distancia: {distancia_km:.2f} km | Tiempo: {tiempo_estimado}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "DESGLOSE:", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(100, 7, f"Combustible estimado: ${gasto_total_diesel:,.2f}")
        pdf.ln(7)
        if c_casetas > 0: pdf.cell(0, 7, f"Casetas: ${c_casetas:,.2f}", ln=True)
        if c_maniobras > 0: pdf.cell(0, 7, f"Maniobras: ${c_maniobras:,.2f}", ln=True)
        # Cargos Extra en PDF
        extras_list = [(e1_n, e1_v), (e2_n, e2_v), (e3_n, e3_v), (e4_n, e4_v)]
        for nom, val in extras_list:
            if val > 0:
                label = nom if nom else "Cargo Adicional"
                pdf.cell(0, 7, f"{label}: ${val:,.2f}", ln=True)
        
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f"TOTAL MXN: ${precio_venta_mxn:,.2f}", ln=True)
        pdf.cell(0, 10, f"TOTAL USD: ${precio_venta_usd:,.2f} (T.C. {tipo_cambio})", ln=True)
        
        pdf_bytes = pdf.output(dest="S")
        st.download_button("⬇️ Descargar Archivo", pdf_bytes, "cotizacion.pdf", "application/pdf")

with btn_wa:
    msg = f"Cotización Logística\nOrigen: {origen}\nDestino: {destino}\nKM: {distancia_km:.2f}\nTotal: ${precio_venta_mxn:,.2f} MXN"
    url_wa = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(msg)}"
    st.markdown(f'<a href="{url_wa}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:12px 24px; border-radius:8px; width:100%; font-weight:bold;">📲 Enviar por WhatsApp</button></a>', unsafe_allow_html=True)
