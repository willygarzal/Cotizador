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

# Inicializar historial en la sesión
if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. BARRA LATERAL (PREMISAS) ---
with st.sidebar:
    st.header("👤 Datos del Cliente")
    nombre_cliente = st.text_input("Nombre del Cliente", "Cliente General")
    
    st.markdown("---")
    st.header("⚙️ Premisas de Venta")
    cpk_objetivo = st.number_input("CPK Objetivo ($)", min_value=0.0, value=28.0, step=0.5)
    # El margen que impacta al total
    margen_utilidad = st.slider("Margen de Utilidad (%)", 0, 100, 25)
    tipo_cambio = st.number_input("Tipo de Cambio (USD/MXN)", value=18.50, step=0.1)
    
    st.markdown("---")
    st.subheader("📊 Referencia de Tarifas")
    data_ref = [
        ["MTY-AREAMETRO", "N. LAREDO", 230, 26.0],
        ["SALTILLO-RAMOS", "N. LAREDO", 310, 24.0],
        ["DERRAMADERO", "N. LAREDO", 380, 25.0],
        ["IMPO N. LAREDO", "MTY", 230, 31.1]
    ]
    st.table(pd.DataFrame(data_ref, columns=["Orig", "Dest", "KM", "CPK"]))
    
    telefono_wa = st.text_input("WhatsApp (ej: 521...)", "")

# --- 3. DISEÑO POR PESTAÑAS ---
tab_cotizador, tab_historial = st.tabs(["🎯 Cotizador", "📜 Historial de Sesión"])

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
            st.warning("Escribe ciudades válidas.")

    st.markdown("---")
    st.subheader("💰 Gastos y Otros Cargos")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Operativos**")
        c_casetas = st.number_input("Casetas ($)", min_value=0.0)
        c_maniobras = st.number_input("Maniobras ($)", min_value=0.0)
        c_seguro = st.number_input("Seguro/Otros ($)", min_value=0.0)
    with c2:
        st.write("**Extras**")
        with st.expander("Panel de 4 Cargos Extra"):
            e1_n = st.text_input("Concepto 1", key="e1n"); e1_v = st.number_input("Monto 1", key="e1v")
            e2_n = st.text_input("Concepto 2", key="e2n"); e2_v = st.number_input("Monto 2", key="e2v")
            e3_n = st.text_input("Concepto 3", key="e3n"); e3_v = st.number_input("Monto 3", key="e3v")
            e4_n = st.text_input("Concepto 4", key="e4n"); e4_v = st.number_input("Monto 4", key="e4v")

    # --- LÓGICA FINANCIERA (EL MARGEN IMPACTA AQUÍ) ---
    flete_base = distancia_km * cpk_objetivo
    suma_gastos = c_casetas + c_maniobras + c_seguro + e1_v + e2_v + e3_v + e4_v
    
    subtotal = flete_base + suma_gastos
    # Aplicación directa del margen al total
    venta_total_mxn = subtotal * (1 + (margen_utilidad / 100))
    venta_total_usd = venta_total_mxn / tipo_cambio

    st.markdown("---")
    r_a, r_b, r_c = st.columns(3)
    r_a.metric("VENTA MXN", f"${venta_total_mxn:,.2f}", f"Margen {margen_utilidad}%")
    r_b.metric("VENTA USD", f"${venta_total_usd:,.2f}")
    r_c.metric("CLIENTE", nombre_cliente)

    st.markdown("### 📤 Exportar")
    a1, a2, a3 = st.columns(3)
    
    with a1:
        if st.button("💾 Guardar en Historial", use_container_width=True):
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Cliente": nombre_cliente,
                "Ruta": f"{origen} a {destino}",
                "Total MXN": f"${venta_total_mxn:,.2f}"
            })
            st.toast("Guardado")

    with a2:
        # Generación segura de PDF en memoria
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, f"COTIZACION: {nombre_cliente}", ln=True, align="C")
        pdf.set_font("Helvetica", size=10)
        pdf.ln(5)
        pdf.cell(0, 7, f"Ruta: {origen} - {destino} ({distancia_km:.2f} km)", ln=True)
        pdf.cell(0, 7, f"Subtotal: ${subtotal:,.2f} | Margen: {margen_utilidad}%", ln=True)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, f"TOTAL: ${venta_total_mxn:,.2f} MXN", ln=True)
        
        # Convertir a bytes de forma robusta
        pdf_output = pdf.output(dest='S').encode('latin-1')
        
        st.download_button(
            label="📄 Descargar PDF",
            data=pdf_output,
            file_name=f"Cotizacion_{nombre_cliente}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    with a3:
        msg = f"Cotización para {nombre_cliente}\nRuta: {origen}-{destino}\nTotal: ${venta_total_mxn:,.2f} MXN"
        url = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(msg)}"
        st.markdown(f'<a href="{url}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 WhatsApp</button></a>', unsafe_allow_html=True)

with tab_historial:
    st.header("📜 Historial de Cotizaciones")
    if st.session_state.historial:
        st.table(pd.DataFrame(st.session_state.historial))
    else:
        st.write("Sin registros en esta sesión.")
