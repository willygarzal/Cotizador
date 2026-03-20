import streamlit as st
import googlemaps
from fpdf import FPDF
import urllib.parse
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE API ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
except Exception:
    st.error("⚠️ Error: No se encontró 'MAPS_API_KEY' en los secretos.")

st.set_page_config(page_title="Cotizador Maestro Logístico", layout="wide")

# Inicializar historial en la sesión para que no se borre al interactuar
if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. BARRA LATERAL: PREMISAS Y CONTROL ---
with st.sidebar:
    st.header("👤 Datos del Cliente")
    nombre_cliente = st.text_input("Nombre / Razón Social", "Cliente General")
    
    st.markdown("---")
    st.header("⚙️ Premisas de Venta")
    # El CPK y el Margen ahora son los motores del precio
    cpk_objetivo = st.number_input("CPK Objetivo ($)", min_value=0.0, value=28.0, step=0.5)
    margen_utilidad = st.slider("Margen de Utilidad (%)", min_value=0, max_value=100, value=25)
    tipo_cambio = st.number_input("Tipo de Cambio (USD/MXN)", value=18.50, step=0.1)
    
    st.markdown("---")
    st.subheader("📊 Referencias de Mercado")
    data_ref = [
        ["MTY-METRO", "N. LAREDO", 230, 26.0],
        ["SALTILLO", "N. LAREDO", 310, 24.0],
        ["DERRAMADERO", "N. LAREDO", 380, 25.0],
        ["IMPO LAR", "MTY", 230, 31.1]
    ]
    st.table(pd.DataFrame(data_ref, columns=["Orig", "Dest", "KM", "CPK"]))
    
    telefono_wa = st.text_input("WhatsApp de Envío (ej: 521...)", "")

# --- 3. DISEÑO POR PESTAÑAS ---
tab_cotizador, tab_historial = st.tabs(["🎯 Panel de Cotización", "📜 Historial de Consultas"])

with tab_cotizador:
    st.header(f"Cotización Actual: {nombre_cliente}")
    
    # SECCIÓN RUTA
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        origen = st.text_input("Punto de Origen", "Monterrey, NL")
    with col_r2:
        destino = st.text_input("Punto de Destino", "Nuevo Laredo, Tamps")

    distancia_km = 0
    tiempo_est = ""
    if origen and destino:
        try:
            res = gmaps.directions(origen, destino, mode="driving")
            if res:
                distancia_km = res[0]['legs'][0]['distance']['value'] / 1000
                tiempo_est = res[0]['legs'][0]['duration']['text']
                st.success(f"🛣️ Ruta calculada: {distancia_km:.2f} km | ⏱️ {tiempo_est}")
        except:
            st.warning("Introduce ciudades válidas para calcular distancia.")

    st.markdown("---")

    # SECCIÓN COSTOS Y EXTRAS
    st.subheader("💰 Desglose de Cargos")
    c_col1, c_col2 = st.columns(2)
    
    with c_col1:
        st.write("**Gastos de Operación**")
        c_casetas = st.number_input("Casetas ($)", min_value=0.0)
        c_maniobras = st.number_input("Maniobras ($)", min_value=0.0)
        c_seguro = st.number_input("Seguro / Otros ($)", min_value=0.0)

    with c_col2:
        st.write("**Cargos Extra (Opcionales)**")
        with st.expander("Abrir panel de 4 cargos adicionales"):
            e1_n = st.text_input("Concepto 1", key="e1n"); e1_v = st.number_input("Monto 1", key="e1v")
            e2_n = st.text_input("Concepto 2", key="e2n"); e2_v = st.number_input("Monto 2", key="e2v")
            e3_n = st.text_input("Concepto 3", key="e3n"); e3_v = st.number_input("Monto 3", key="e3v")
            e4_n = st.text_input("Concepto 4", key="e4n"); e4_v = st.number_input("Monto 4", key="e4v")

    # --- LÓGICA FINANCIERA INTEGRAL ---
    # 1. Calculamos el flete base según el CPK objetivo de las premisas
    flete_base = distancia_km * cpk_objetivo
    
    # 2. Sumamos todos los gastos operativos y extras
    suma_gastos_extras = c_casetas + c_maniobras + c_seguro + e1_v + e2_v + e3_v + e4_v
    
    # 3. Calculamos el Subtotal
    subtotal = flete_base + suma_gastos_extras
    
    # 4. Aplicamos el margen de utilidad definido en el Slider de premisas
    # El margen se calcula como un multiplicador sobre el costo/subtotal
    venta_total_mxn = subtotal * (1 + (margen_utilidad / 100))
    venta_total_usd = venta_total_mxn / tipo_cambio

    st.markdown("---")
    
    # PANEL DE RESULTADOS FINAL
    res_a, res_b, res_c = st.columns(3)
    res_a.metric("TOTAL COTIZADO (MXN)", f"${venta_total_mxn:,.2f}", f"Margen: {margen_utilidad}%")
    res_b.metric("TOTAL COTIZADO (USD)", f"${venta_total_usd:,.2f}")
    res_c.metric("CPK APLICADO", f"${cpk_objetivo:,.2f}")

    # ACCIONES FINALES
    st.markdown("### 📤 Finalizar y Enviar")
    acc1, acc2, acc3 = st.columns(3)
    
    with acc1:
        if st.button("💾 Guardar en Historial", use_container_width=True):
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Cliente": nombre_cliente,
                "Ruta": f"{origen} -> {destino}",
                "Distancia": f"{distancia_km:.2f} km",
                "Total MXN": f"${venta_total_mxn:,.2f}"
            })
            st.toast(f"Cotización de {nombre_cliente} guardada.")

    with acc2:
        # Generación de PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"COTIZACIÓN: {nombre_cliente}", ln=True, align="C")
        pdf.set_font("Arial", size=10)
        pdf.ln(5)
        pdf.cell(0, 7, f"Origen: {origen} | Destino: {destino}", ln=True)
        pdf.cell(0, 7, f"Distancia: {distancia_km:.2f} km | Tiempo: {tiempo_est}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "DESGLOSE DE SERVICIOS:", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(100, 7, f"Flete Base (CPK ${cpk_objetivo}):", border=0)
        pdf.cell(0, 7, f"${flete_base:,.2f}", ln=True, align="R")
        if suma_gastos_extras > 0:
            pdf.cell(100, 7, "Cargos Adicionales y Otros:", border=0)
            pdf.cell(0, 7, f"${suma_gastos_extras:,.2f}", ln=True, align="R")
        pdf.ln(2)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(100, 10, f"TOTAL FINAL (Margen {margen_utilidad}%):", border=0)
        pdf.cell(0, 10, f"${venta_total_mxn:,.2f} MXN", ln=True, align="R")
        
        st.download_button("📄 Descargar PDF", pdf.output(dest="S"), f"Cot_{nombre_cliente}.pdf", use_container_width=True)

    with acc3:
        msg_wa = f"Cotización para: {nombre_cliente}\nRuta: {origen} a {destino}\nTotal: ${venta_total_mxn:,.2f} MXN\nGracias por su preferencia."
        url_wa = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(msg_wa)}"
        st.markdown(f'<a href="{url_wa}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 Enviar por WhatsApp</button></a>', unsafe_allow_html=True)

with tab_historial:
    st.header("📜 Historial de Cotizaciones de la Sesión")
    if st.session_state.historial:
        df_hist = pd.DataFrame(st.session_state.historial)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no has guardado ninguna cotización en esta sesión.")
