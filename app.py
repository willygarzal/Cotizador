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
    st.error("⚠️ Error: No se detecta la API Key en secrets.toml.")

st.set_page_config(page_title="Cotizador Maestro Logístico", layout="wide")

if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. BARRA LATERAL (PREMISAS) ---
with st.sidebar:
    st.header("👤 Datos del Cliente")
    nombre_cliente = st.text_input("Nombre del Cliente", "Cliente General")
    tipo_operacion = st.selectbox("Tipo de Operación", ["EXPO", "IMPO"])
    
    st.markdown("---")
    st.header("⚙️ Premisas de Venta")
    cpk_objetivo = st.number_input("CPK Objetivo ($)", min_value=0.0, value=28.0, step=0.5)
    margen_utilidad = st.slider("Margen de Utilidad (%)", 0, 100, 25)
    tipo_cambio = st.number_input("Tipo de Cambio (USD/MXN)", value=18.50, step=0.1)
    
    st.markdown("---")
    st.subheader("📊 Tabla de Referencia Completa")
    # Tabla con todos los datos de origen/destino y tarifas base
    df_ref = pd.DataFrame([
        ["EXPO", "MTY-METRO", "N. LAREDO", 230, 26.0],
        ["EXPO", "SALTILLO", "N. LAREDO", 310, 24.0],
        ["EXPO", "DERRAMADERO", "N. LAREDO", 380, 25.0],
        ["IMPO", "N. LAREDO", "MTY-METRO", 230, 31.1],
        ["IMPO", "N. LAREDO", "SALTILLO", 310, 28.0],
        ["IMPO", "N. LAREDO", "DERRAMADERO", 380, 28.1]
    ], columns=["Tipo", "Origen", "Destino", "KM", "CPK"])
    st.dataframe(df_ref, hide_index=True)
    
    telefono_wa = st.text_input("WhatsApp (ej: 521...)", "")

# --- 3. DISEÑO POR PESTAÑAS ---
tab_cotizador, tab_historial = st.tabs(["🎯 Cotizador", "📜 Historial de Sesión"])

with tab_cotizador:
    st.header(f"Cotización {tipo_operacion}: {nombre_cliente}")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        origen_input = st.text_input("Punto de Origen", "Monterrey, NL")
    with col_r2:
        destino_input = st.text_input("Punto de Destino", "Nuevo Laredo, Tamps")

    distancia_km = 0
    if origen_input and destino_input:
        try:
            res = gmaps.directions(origen_input, destino_input, mode="driving")
            if res:
                distancia_km = res[0]['legs'][0]['distance']['value'] / 1000
                st.success(f"🛣️ Distancia calculada: {distancia_km:.2f} km")
                
                # --- MAPA DE GOOGLE MAPS CORREGIDO ---
                # Usamos el modo 'place' o 'directions' para el iframe
                map_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(origen_input)}&destination={urllib.parse.quote(destino_input)}&mode=driving"
                st.markdown(f'<iframe width="100%" height="450" frameborder="0" style="border:0" src="{map_url}" allowfullscreen></iframe>', unsafe_allow_html=True)
        except Exception as e:
            st.warning("No se pudo cargar el mapa. Verifica las ciudades o la API Key.")

    st.markdown("---")
    
    # --- GASTOS Y CARGOS EN DESPLEGABLE ---
    # Inicializamos en 0 por si el usuario no abre el expander
    c_casetas = c_maniobras = c_seguro = e1_v = e2_v = e3_v = e4_v = 0.0
    
    with st.expander("💰 Configurar Gastos y Cargos Extra (Opcional)"):
        gc1, gc2 = st.columns(2)
        with gc1:
            st.write("**Costos de Operación**")
            c_casetas = st.number_input("Casetas ($)", min_value=0.0)
            c_maniobras = st.number_input("Maniobras ($)", min_value=0.0)
            c_seguro = st.number_input("Seguro/Otros ($)", min_value=0.0)
        with gc2:
            st.write("**Cargos Adicionales**")
            e1_n = st.text_input("Concepto 1", key="n1"); e1_v = st.number_input("Monto 1", key="v1")
            e2_n = st.text_input("Concepto 2", key="n2"); e2_v = st.number_input("Monto 2", key="v2")
            e3_n = st.text_input("Concepto 3", key="n3"); e3_v = st.number_input("Monto 3", key="v3")
            e4_n = st.text_input("Concepto 4", key="n4"); e4_v = st.number_input("Monto 4", key="v4")

    # --- LÓGICA DE CÁLCULO ---
    flete_base = distancia_km * cpk_objetivo
    total_gastos = c_casetas + c_maniobras + c_seguro + e1_v + e2_v + e3_v + e4_v
    
    subtotal = flete_base + total_gastos
    # El margen se aplica sobre el total de costos
    venta_total_mxn = subtotal * (1 + (margen_utilidad / 100))
    venta_total_usd = venta_total_mxn / tipo_cambio

    st.markdown("---")
    res1, res2, res3 = st.columns(3)
    res1.metric("VENTA TOTAL MXN", f"${venta_total_mxn:,.2f}", f"Margen: {margen_utilidad}%")
    res2.metric("VENTA TOTAL USD", f"${venta_total_usd:,.2f}")
    res3.metric("DISTANCIA", f"{distancia_km:.2f} KM")

    # --- ACCIONES ---
    st.markdown("### 📤 Finalizar Cotización")
    btn1, btn2, btn3 = st.columns(3)
    
    with btn1:
        if st.button("💾 Guardar en Historial", use_container_width=True):
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Tipo": tipo_operacion,
                "Cliente": nombre_cliente,
                "Ruta": f"{origen_input} a {destino_input}",
                "Total MXN": f"${venta_total_mxn:,.2f}"
            })
            st.toast(f"Guardada cotización de {nombre_cliente}")

    with btn2:
        # Generación de PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, f"COTIZACION {tipo_operacion}: {nombre_cliente}", ln=True, align="C")
        pdf.set_font("Helvetica", size=10)
        pdf.ln(10)
        pdf.cell(0, 7, f"Trayecto: {origen_input} a {destino_input} ({distancia_km:.2f} km)", ln=True)
        pdf.cell(0, 7, f"Subtotal base: ${subtotal:,.2f} | Margen: {margen_utilidad}%", ln=True)
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, f"PRECIO FINAL: ${venta_total_mxn:,.2f} MXN", ln=True)
        
        pdf_buf = io.BytesIO()
        pdf_out = pdf.output(dest='S')
        if isinstance(pdf_out, str):
            pdf_buf.write(pdf_out.encode('latin-1'))
        else:
            pdf_buf.write(pdf_out)
        pdf_buf.seek(0)
        
        st.download_button(
            label="📄 Descargar PDF",
            data=pdf_buf,
            file_name=f"Cotizacion_{nombre_cliente}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    with btn3:
        wa_text = f"Cotización {tipo_operacion} - {nombre_cliente}\nRuta: {origen_input}-{destino_input}\nTotal: ${venta_total_mxn:,.2f} MXN"
        wa_url = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_text)}"
        st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 Enviar WhatsApp</button></a>', unsafe_allow_html=True)

with tab_historial:
    st.header("📜 Historial de Sesión")
    if st.session_state.historial:
        st.table(pd.DataFrame(st.session_state.historial))
    else:
        st.info("No hay registros todavía.")
