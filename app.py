import streamlit as st
import googlemaps
from fpdf import FPDF

# --- 1. CONFIGURACIÓN DE API (Oculta en secrets) ---
# Descomenta estas líneas cuando quieras hacer las llamadas a Google Maps
# api_key = st.secrets["MAPS_API_KEY"]
# gmaps = googlemaps.Client(key=api_key)

st.title("Cotizador Logístico Pro 🚚")

# --- 2. COSTOS BASE ---
st.markdown("### Costos Base")
col1, col2, col3 = st.columns(3)
with col1:
    costo_base = st.number_input("Tarifa Base ($)", min_value=0.0, step=100.0)
with col2:
    costo_casetas = st.number_input("Casetas ($)", min_value=0.0, step=50.0)
with col3:
    costo_maniobras = st.number_input("Maniobras ($)", min_value=0.0, step=50.0)

# --- 3. CARGOS ADICIONALES DINÁMICOS ---
st.markdown("### ➕ Otros Cargos (Opcional)")

with st.expander("Haz clic aquí para agregar hasta 4 cargos adicionales personalizados"):
    col_concepto, col_monto = st.columns([2, 1])
    
    with col_concepto:
        concepto_extra_1 = st.text_input("Concepto Extra 1", placeholder="Ej. Embalaje especial")
        concepto_extra_2 = st.text_input("Concepto Extra 2", placeholder="Ej. Permiso de tránsito")
        concepto_extra_3 = st.text_input("Concepto Extra 3", placeholder="Ej. Escolta armada")
        concepto_extra_4 = st.text_input("Concepto Extra 4", placeholder="Ej. Estadía en puerto")
        
    with col_monto:
        monto_extra_1 = st.number_input("Costo Extra 1 ($)", min_value=0.0, step=100.0, format="%.2f")
        monto_extra_2 = st.number_input("Costo Extra 2 ($)", min_value=0.0, step=100.0, format="%.2f")
        monto_extra_3 = st.number_input("Costo Extra 3 ($)", min_value=0.0, step=100.0, format="%.2f")
        monto_extra_4 = st.number_input("Costo Extra 4 ($)", min_value=0.0, step=100.0, format="%.2f")

# --- 4. CÁLCULO DEL TOTAL ---
total_otros_cargos = monto_extra_1 + monto_extra_2 + monto_extra_3 + monto_extra_4
costo_total = costo_base + costo_casetas + costo_maniobras + total_otros_cargos

st.markdown("---")
st.subheader(f"💰 Costo Total de la Cotización: ${costo_total:,.2f}")

# --- 5. GENERACIÓN DEL PDF CON FPDF2 ---
st.markdown("### Generar Documento")

if st.button("📄 Generar PDF de Cotización"):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Cotización de Servicios Logísticos", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    
    # Desglose de Costos Base
    pdf.set_font("helvetica", size=12)
    if costo_base > 0:
        pdf.cell(0, 10, f"Tarifa Base: ${costo_base:,.2f}", new_x="LMARGIN", new_y="NEXT")
    if costo_casetas > 0:
        pdf.cell(0, 10, f"Casetas: ${costo_casetas:,.2f}", new_x="LMARGIN", new_y="NEXT")
    if costo_maniobras > 0:
        pdf.cell(0, 10, f"Maniobras: ${costo_maniobras:,.2f}", new_x="LMARGIN", new_y="NEXT")
    
    # Lógica inteligente para los Cargos Extra
    cargos_extra = [
        (concepto_extra_1, monto_extra_1),
        (concepto_extra_2, monto_extra_2),
        (concepto_extra_3, monto_extra_3),
        (concepto_extra_4, monto_extra_4)
    ]
    
    for concepto, monto in cargos_extra:
        if monto > 0:
            # Si el usuario olvidó poner el nombre pero sí puso costo, asignamos un nombre por defecto
            nombre_concepto = concepto.strip() if concepto.strip() != "" else "Cargo Adicional"
            pdf.cell(0, 10, f"{nombre_concepto}: ${monto:,.2f}", new_x="LMARGIN", new_y="NEXT")
            
    # Total
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, f"TOTAL: ${costo_total:,.2f}", new_x="LMARGIN", new_y="NEXT")
    
    # Procesar el PDF en memoria para Streamlit
    pdf_bytes = pdf.output(dest="S")
    
    # Botón de descarga dinámico
    st.download_button(
        label="⬇️ Descargar Cotización en PDF",
        data=pdf_bytes,
        file_name="cotizacion_logistica.pdf",
        mime="application/pdf"
    )
