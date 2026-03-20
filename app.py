import streamlit as st
import googlemaps
from fpdf import FPDF

# --- 1. CONFIGURACIÓN DE API SEGURA ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
except Exception:
    st.error("⚠️ No se encontró 'MAPS_API_KEY' en los secretos de Streamlit.")

st.set_page_config(page_title="Cotizador Logístico Pro", layout="wide")
st.title("Cotizador Logístico Pro 🚚")

# --- 2. CÁLCULO DE RUTA (GOOGLE MAPS) ---
st.markdown("### 📍 Detalles de la Ruta")
col_orig, col_dest = st.columns(2)

with col_orig:
    origen = st.text_input("Ciudad de Origen", placeholder="Ej. Monterrey, NL")
with col_dest:
    destino = st.text_input("Ciudad de Destino", placeholder="Ej. Ciudad de México")

distancia_km = 0
tiempo_estimado = ""

if origen and destino:
    try:
        directions_result = gmaps.directions(origen, destino, mode="driving")
        if directions_result:
            distancia_km = directions_result[0]['legs'][0]['distance']['value'] / 1000
            tiempo_estimado = directions_result[0]['legs'][0]['duration']['text']
            st.success(f"🛣️ Distancia: {distancia_km:.2f} km | ⏱️ Tiempo: {tiempo_estimado}")
    except Exception as e:
        st.error(f"Error al calcular ruta: {e}")

st.markdown("---")

# --- 3. DESGLOSE DE COSTOS ---
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("### 💰 Costos Operativos")
    costo_base = st.number_input("Tarifa Base/Flete ($)", min_value=0.0, step=100.0)
    costo_casetas = st.number_input("Casetas ($)", min_value=0.0, step=50.0)
    costo_maniobras = st.number_input("Maniobras ($)", min_value=0.0, step=50.0)
    costo_seguro = st.number_input("Seguro / Otros ($)", min_value=0.0, step=50.0)

with col_b:
    st.markdown("### ➕ Cargos Adicionales")
    with st.expander("Agregar hasta 4 conceptos extra"):
        c1_nom = st.text_input("Concepto 1", key="c1n")
        c1_val = st.number_input("Monto 1 ($)", min_value=0.0, key="c1v")
        
        c2_nom = st.text_input("Concepto 2", key="c2n")
        c2_val = st.number_input("Monto 2 ($)", min_value=0.0, key="c2v")
        
        c3_nom = st.text_input("Concepto 3", key="c3n")
        c3_val = st.number_input("Monto 3 ($)", min_value=0.0, key="c3v")
        
        c4_nom = st.text_input("Concepto 4", key="c4n")
        c4_val = st.number_input("Monto 4 ($)", min_value=0.0, key="c4v")

# --- 4. TOTALIZACIÓN ---
suma_extras = c1_val + c2_val + c3_val + c4_val
total_general = costo_base + costo_casetas + costo_maniobras + costo_seguro + suma_extras

st.markdown("---")
st.metric(label="COSTO TOTAL DE COTIZACIÓN", value=f"${total_general:,.2f}")

# --- 5. GENERACIÓN DE PDF ---
if st.button("📄 Generar Cotización Formal"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    # Cabecera
    pdf.cell(0, 10, "COTIZACIÓN LOGÍSTICA", ln=True, align="C")
    pdf.ln(5)
    
    # Datos de Ruta
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"Origen: {origen}", ln=True)
    pdf.cell(0, 8, f"Destino: {destino}", ln=True)
    pdf.cell(0, 8, f"Distancia estimada: {distancia_km:.2f} km", ln=True)
    pdf.cell(0, 8, f"Tiempo estimado: {tiempo_estimado}", ln=True)
    pdf.ln(5)
    
    # Tabla de Costos
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Desglose de Costos:", ln=True)
    pdf.set_font("Arial", size=11)
    
    items = [
        ("Flete Base", costo_base),
        ("Casetas", costo_casetas),
        ("Maniobras", costo_maniobras),
        ("Seguro / Otros", costo_seguro),
        (c1_nom if c1_nom else "Extra 1", c1_val),
        (c2_nom if c2_nom else "Extra 2", c2_val),
        (c3_nom if c3_nom else "Extra 3", c3_val),
        (c4_nom if c4_nom else "Extra 4", c4_val)
    ]
    
    for desc, monto in items:
        if monto > 0:
            pdf.cell(100, 8, f"{desc}:", border=0)
            pdf.cell(0, 8, f"${monto:,.2f}", border=0, ln=True, align="R")
    
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_font("Arial", "B", 12)
    pdf.cell(100, 10, "TOTAL:", border=0)
    pdf.cell(0, 10, f"${total_general:,.2f}", border=0, ln=True, align="R")
    
    pdf_output = pdf.output(dest="S")
    st.download_button("⬇️ Descargar PDF", data=pdf_output, file_name=f"Cotizacion_{destino}.pdf", mime="application/pdf")
