import streamlit as st
import googlemaps
from fpdf import FPDF
import urllib.parse
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
except Exception:
    st.error("⚠️ Revisa tu archivo 'secrets.toml'. No se detecta la API Key.")

st.set_page_config(page_title="Cotizador Maestro Logístico", layout="wide")

if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.header("👤 Datos del Cliente")
    nombre_cliente = st.text_input("Nombre del Cliente", "Cliente General")
    
    st.markdown("---")
    st.header("⚙️ Premisas de Venta")
    cpk_objetivo = st.number_input("CPK Objetivo ($)", min_value=0.0, value=28.0, step=0.5)
    margen_utilidad = st.slider("Margen de Utilidad (%)", 0, 100, 25)
    tipo_cambio = st.number_input("Tipo de Cambio (USD/MXN)", value=18.50, step=0.1)
    
    st.markdown("---")
    st.subheader("📊 Referencias")
    data_ref = [
        ["MTY-METRO", "N. LAREDO", 230, 26.0],
        ["SALTILLO", "N. LAREDO", 310, 24.0],
        ["DERRAMADERO", "N. LAREDO", 380, 25.0],
        ["IMPO LAR", "MTY", 230, 31.1]
    ]
    st.table(pd.DataFrame(data_ref, columns=["Orig", "Dest", "KM", "CPK"]))
    
    telefono_wa = st.text_input("WhatsApp (ej: 521...)", "")

# --- 3. PESTAÑAS ---
tab_cotizador, tab_historial = st.tabs(["🎯 Cotizador", "📜 Historial"])

with tab_cotizador:
    st.header(f"Cotización: {nombre_cliente}")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        origen = st.text_input("Origen", "Monterrey, NL")
    with col_r2:
        destino = st.text_input("Destino", "Nuevo Laredo, Tamps")

    distancia_km = 0
    if origen and destino:
        try:
            res = gmaps.directions(origen, destino, mode="driving")
            if res:
                distancia_km = res[0]['legs'][0]['distance']['value'] / 1000
                st.success(f"🛣️ Distancia: {distancia_km:.2f} km")
        except:
            st.warning("Verifica las ciudades.")

    st.markdown("---")
    st.subheader("💰 Gastos")
    c1, c2 = st.columns(2)
    with c1:
        c_casetas = st.number_input("Casetas ($)", min_value=0.0)
        c_maniobras = st.number_input("Maniobras ($)", min_value=0.0)
        c_seguro = st.number_input("Seguro/Otros ($)", min_value=0.0)
    with c2:
        with st.expander("Panel de 4 Extras"):
            e1_n = st.text_input("Concepto 1"); e1_v = st.number_input("Monto 1", key="v1")
            e2_n = st.text_input("Concepto 2"); e2_v = st.number_input("Monto 2", key="v2")
            e3_n = st.text_input("Concepto 3"); e3_v = st.number_input("Monto 3", key="v3")
            e4_n = st.text_input("Concepto 4"); e4_v = st.number_input("Monto 4", key="v4")

    # LÓGICA
    flete_base = distancia_km * cpk_objetivo
    suma_gastos = c_casetas + c_maniobras + c_seguro + e1_v + e2_v + e3_v + e4_v
    subtotal = flete_base + suma_gastos
    venta_total_mxn = subtotal * (1 + (margen_utilidad / 100))
    venta_total_usd = venta_total_mxn / tipo_cambio

    st.markdown("---")
    res_a, res_b = st.columns(2)
    res_a.metric("TOTAL MXN", f"${venta_total_mxn:,.2f}", f"Margen {margen_utilidad}%")
    res_b.metric("TOTAL USD", f"${venta_total_usd:,.2f}")

    # ACCIONES
    a1, a2, a3 = st.columns(3)
    
    with a1:
        if st.button("💾 Guardar Historial", use_container_width=True):
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Cliente": nombre_cliente,
                "Ruta": f"{origen}-{destino}",
                "Total MXN": f"${venta_total_mxn:,.2f}"
            })
            st.toast("Guardado")

    with a2:
        # --- GENERACIÓN DE PDF CON CORRECCIÓN DE ERROR ---
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"COTIZACION: {nombre_cliente}", ln=True, align="C")
        pdf.set_font("Arial", size=11)
        pdf.ln(10)
        pdf.cell(0, 7, f"Ruta: {origen} - {destino} ({distancia_km:.2f} km)", ln=True)
        pdf.cell(0, 7, f"Subtotal: ${subtotal:,.2f}", ln=True)
        pdf.cell(0, 7, f"Margen: {margen_utilidad}%", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f"TOTAL: ${venta_total_mxn:,.2f} MXN", ln=True)
        
        # SOLUCIÓN AL ATTRIBUTE ERROR
        pdf_raw = pdf.output(dest='S')
        if isinstance(pdf_raw, str):
            pdf_bytes = pdf_raw.encode('latin-1')
        else:
            pdf_bytes = pdf_raw

        st.download_button(
            label="📄 Descargar PDF",
            data=pdf_bytes,
            file_name=f"Cotizacion_{nombre_cliente}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    with a3:
        msg = f"Cotización {nombre_cliente}: {origen}-{destino}. Total: ${venta_total_mxn:,.2f} MXN"
        url = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(msg)}"
        st.markdown(f'<a href="{url}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 WhatsApp</button></a>', unsafe_allow_html=True)

with tab_historial:
    st.header("📜 Historial")
    if st.session_state.historial:
        st.table(pd.DataFrame(st.session_state.historial))
