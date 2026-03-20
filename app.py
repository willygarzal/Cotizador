import streamlit as st
import googlemaps
from fpdf import FPDF
import urllib.parse
import pandas as pd
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
except Exception:
    st.error("⚠️ Error: Revisa tu archivo 'secrets.toml'.")

st.set_page_config(page_title="Cotizador Maestro Logístico", layout="wide")

if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. BASE DE DATOS DE REFERENCIA (Extraída de tu Foto) ---
datos_referencia = [
    ["EXPO", "MTY-AREA METRO", "NUEVO LAREDO", 230, 26.00, 34.67],
    ["EXPO", "SALTILLO - RAMOS", "NUEVO LAREDO", 310, 24.00, 32.00],
    ["EXPO", "DERRAMADERO", "NUEVO LAREDO", 380, 25.00, 33.33],
    ["IMPO", "NUEVO LAREDO", "MTY-AREA METRO", 230, 31.10, 41.46],
    ["IMPO", "NUEVO LAREDO", "SALTILLO - RAMOS", 310, 28.00, 37.33],
    ["IMPO", "NUEVO LAREDO", "DERRAMADERO", 380, 28.10, 37.47]
]
df_ref = pd.DataFrame(datos_referencia, columns=["Tipo", "Origen", "Destino", "KM_Ref", "CPK_Base", "IPK_Ref"])

# --- 3. BARRA LATERAL (PREMISAS) ---
with st.sidebar:
    st.header("👤 Datos del Cliente")
    nombre_cliente = st.text_input("Nombre del Cliente", "Cliente General")
    tipo_operacion = st.selectbox("Tipo de Operación", ["EXPO", "IMPO"])
    
    st.markdown("---")
    st.header("⚙️ Premisas de Venta")
    
    # Filtrar rutas por tipo (EXPO/IMPO)
    rutas_filtro = df_ref[df_ref["Tipo"] == tipo_operacion]
    ruta_sel = st.selectbox("Ruta de Referencia (Tabla)", 
                            rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"])
    
    # Extraer valores de la tabla automáticamente
    datos_ruta = rutas_filtro[(rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]) == ruta_sel].iloc[0]
    
    cpk_base = datos_ruta["CPK_Base"]
    ipk_referencia = datos_ruta["IPK_Ref"]
    km_referencia = datos_ruta["KM_Ref"]

    st.info(f"📋 **Valores Tabla:** CPK: ${cpk_base} | IPK: ${ipk_referencia}")

    margen_utilidad = st.slider("Margen de Utilidad (%)", 0, 100, 25)
    tipo_cambio = st.number_input("Tipo de Cambio (USD/MXN)", value=17.00, step=0.1)
    
    st.markdown("---")
    telefono_wa = st.text_input("WhatsApp (ej: 521...)", "")

# --- 4. DISEÑO POR PESTAÑAS ---
tab_cotizador, tab_historial = st.tabs(["🎯 Cotizador", "📜 Historial Detallado"])

with tab_cotizador:
    st.header(f"Cotización {tipo_operacion}: {nombre_cliente}")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        origen_in = st.text_input("Origen", datos_ruta["Origen"])
    with col_r2:
        destino_in = st.text_input("Destino", datos_ruta["Destino"])

    distancia_km = 0
    if origen_in and destino_in:
        try:
            res = gmaps.directions(origen_in, destino_in, mode="driving")
            if res:
                distancia_km = res[0]['legs'][0]['distance']['value'] / 1000
                st.success(f"🛣️ Distancia Real Detectada: {distancia_km:.2f} km")
        except:
            distancia_km = km_referencia
            st.warning(f"No se detectó mapa. Usando KM de tabla: {distancia_km} km")

    st.markdown("---")
    
    with st.expander("💰 Configurar Gastos y Cargos Adicionales"):
        gc1, gc2 = st.columns(2)
        with gc1:
            st.write("**Costos Operativos**")
            c_casetas = st.number_input("Casetas ($)", min_value=0.0)
            c_maniobras = st.number_input("Maniobras ($)", min_value=0.0)
            c_cpac = st.number_input("CPAC ($)", min_value=0.0)
        with gc2:
            st.write("**Cargos Extra**")
            e1_n = st.text_input("Concepto Extra 1", "Cruce"); e1_v = st.number_input("Monto Cruce", key="v1")
            e2_n = st.text_input("Concepto Extra 2", "Seguro"); e2_v = st.number_input("Monto Seguro", key="v2")

    # --- LÓGICA FINANCIERA INTEGRADA ---
    # IPK Calculado basado en el margen sobre el CPK base
    ipk_calculado = cpk_base * (1 + (margen_utilidad / 100))
    flete_con_margen = distancia_km * ipk_calculado
    
    suma_gastos_adicionales = c_casetas + c_maniobras + c_cpac + e1_v + e2_v
    
    venta_total_mxn = flete_con_margen + suma_gastos_adicionales
    venta_total_usd = venta_total_mxn / tipo_cambio

    # Mostrar métricas comparativas
    res_a, res_b, res_c = st.columns(3)
    res_a.metric("VENTA TOTAL MXN", f"${venta_total_mxn:,.2f}")
    res_b.metric("VENTA TOTAL USD", f"${venta_total_usd:,.2f}")
    delta_ipk = ipk_calculado - ipk_referencia
    res_c.metric("IPK CALCULADO", f"${ipk_calculado:.2f}", delta=f"{delta_ipk:.2f} vs Tabla")

    st.markdown("### 📤 Finalizar")
    a1, a2, a3 = st.columns(3)
    
    with a1:
        if st.button("💾 Guardar en Historial", use_container_width=True):
            registro = {
                "Fecha": datetime.now().strftime("%H:%M:%S"),
                "Cliente": nombre_cliente,
                "Ruta": f"{origen_in}-{destino_in}",
                "IPK": f"${ipk_calculado:.2f}",
                "Total MXN": f"${venta_total_mxn:,.2f}",
                "Total USD": f"${venta_total_usd:,.2f}"
            }
            st.session_state.historial.insert(0, registro)
            st.toast("Guardado correctamente")

    with a2:
        # Generación de PDF (Tu lógica original adaptada)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, f"COTIZACION {tipo_operacion}: {nombre_cliente}", ln=True, align="C")
        pdf.set_font("Helvetica", size=10)
        pdf.ln(10)
        pdf.cell(0, 7, f"Ruta: {origen_in} - {destino_in} ({distancia_km:.2f} km)", ln=True)
        pdf.cell(0, 7, f"Servicio de Flete (IPK: ${ipk_calculado:.2f}): ${flete_con_margen:,.2f} MXN", ln=True)
        if suma_gastos_adicionales > 0:
            pdf.cell(0, 7, f"Gastos Adicionales: ${suma_gastos_adicionales:,.2f} MXN", ln=True)
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, f"TOTAL: ${venta_total_mxn:,.2f} MXN", ln=True)
        pdf.cell(0, 10, f"TOTAL USD: ${venta_total_usd:,.2f} (TC: {tipo_cambio})", ln=True)
        
        pdf_buf = io.BytesIO()
        pdf_out = pdf.output(dest='S')
        if isinstance(pdf_out, str): pdf_buf.write(pdf_out.encode('latin-1'))
        else: pdf_buf.write(pdf_out)
        pdf_buf.seek(0)
        st.download_button("📄 Descargar PDF Detallado", pdf_buf, f"Cot_{nombre_cliente}.pdf", use_container_width=True)

    with a3:
        # Botón de WhatsApp con el desglose
        wa_msg = f"*COTIZACIÓN {tipo_operacion}*\n*Cliente:* {nombre_cliente}\n*Ruta:* {origen_in} -> {destino_in}\n*IPK:* ${ipk_calculado:.2f}\n*Total:* ${venta_total_mxn:,.2f} MXN"
        url_wa = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_msg)}"
        st.markdown(f'<a href="{url_wa}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 Enviar WhatsApp</button></a>', unsafe_allow_html=True)

with tab_historial:
    st.header("📜 Historial Detallado")
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
    else:
        st.info("No hay registros aún.")
