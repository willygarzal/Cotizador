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
    st.subheader("📊 Tabla de Referencia")
    df_ref = pd.DataFrame([
        ["EXPO", "MTY-METRO", "N. LAREDO", 230, 26.0],
        ["EXPO", "SALTILLO", "N. LAREDO", 310, 24.0],
        ["IMPO", "N. LAREDO", "MTY-METRO", 230, 31.1],
        ["IMPO", "N. LAREDO", "SALTILLO", 310, 28.0]
    ], columns=["Tipo", "Origen", "Destino", "KM", "CPK"])
    st.dataframe(df_ref, hide_index=True)
    
    telefono_wa = st.text_input("WhatsApp (ej: 521...)", "")

# --- 3. DISEÑO POR PESTAÑAS ---
tab_cotizador, tab_historial = st.tabs(["🎯 Cotizador", "📜 Historial Detallado"])

with tab_cotizador:
    st.header(f"Cotización {tipo_operacion}: {nombre_cliente}")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        origen_in = st.text_input("Origen", "Monterrey, NL")
    with col_r2:
        destino_in = st.text_input("Destino", "Nuevo Laredo, Tamps")

    distancia_km = 0
    if origen_in and destino_in:
        try:
            res = gmaps.directions(origen_in, destino_in, mode="driving")
            if res:
                distancia_km = res[0]['legs'][0]['distance']['value'] / 1000
                st.success(f"🛣️ Distancia: {distancia_km:.2f} km")
                
                # Mapa de Google Maps
                map_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(origen_in)}&destination={urllib.parse.quote(destino_in)}&mode=driving"
                st.markdown(f'<iframe width="100%" height="400" frameborder="0" style="border:0" src="{map_url}" allowfullscreen></iframe>', unsafe_allow_html=True)
        except:
            st.warning("Verifica las ciudades para mostrar el mapa.")

    st.markdown("---")
    
    # --- GASTOS DESPLEGABLES ---
    with st.expander("💰 Configurar Gastos y Cargos Extra (Opcional)"):
        gc1, gc2 = st.columns(2)
        with gc1:
            c_casetas = st.number_input("Casetas ($)", min_value=0.0)
            c_maniobras = st.number_input("Maniobras ($)", min_value=0.0)
            c_seguro = st.number_input("Seguro/Otros ($)", min_value=0.0)
        with gc2:
            e1_n = st.text_input("Extra 1", "E1"); e1_v = st.number_input("Monto 1", key="v1")
            e2_n = st.text_input("Extra 2", "E2"); e2_v = st.number_input("Monto 2", key="v2")
            e3_n = st.text_input("Extra 3", "E3"); e3_v = st.number_input("Monto 3", key="v3")
            e4_n = st.text_input("Extra 4", "E4"); e4_v = st.number_input("Monto 4", key="v4")

    # Lógica Financiera
    flete_base = distancia_km * cpk_objetivo
    otros_cargos = e1_v + e2_v + e3_v + e4_v
    subtotal_gastos = c_casetas + c_maniobras + c_seguro + otros_cargos
    
    subtotal_final = flete_base + subtotal_gastos
    venta_total_mxn = subtotal_final * (1 + (margen_utilidad / 100))
    venta_total_usd = venta_total_mxn / tipo_cambio

    st.markdown("---")
    res_a, res_b, res_c = st.columns(3)
    res_a.metric("VENTA MXN", f"${venta_total_mxn:,.2f}", f"Margen {margen_utilidad}%")
    res_b.metric("VENTA USD", f"${venta_total_usd:,.2f}")
    res_c.metric("GASTOS EXTRA", f"${subtotal_gastos:,.2f}")

    # Acciones
    st.markdown("### 📤 Finalizar")
    a1, a2, a3 = st.columns(3)
    
    with a1:
        if st.button("💾 Guardar en Historial", use_container_width=True):
            # Guardamos el desglose completo
            registro = {
                "Fecha": datetime.now().strftime("%H:%M:%S"),
                "Cliente": nombre_cliente,
                "Tipo": tipo_operacion,
                "Ruta": f"{origen_in}-{destino_in}",
                "Flete Base": f"${flete_base:,.2f}",
                "Casetas": f"${c_casetas:,.2f}",
                "Maniobras": f"${c_maniobras:,.2f}",
                "Seguro": f"${c_seguro:,.2f}",
                "Extras ($)": f"${otros_cargos:,.2f}",
                "Total MXN": f"${venta_total_mxn:,.2f}"
            }
            st.session_state.historial.insert(0, registro)
            st.toast("Guardado con desglose")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, f"COTIZACION {tipo_operacion}: {nombre_cliente}", ln=True, align="C")
        pdf.set_font("Helvetica", size=10)
        pdf.ln(10)
        pdf.cell(0, 7, f"Ruta: {origen_in} - {destino_in} ({distancia_km:.2f} km)", ln=True)
        pdf.cell(0, 7, f"Flete: ${flete_base:,.2f} | Gastos/Extras: ${subtotal_gastos:,.2f}", ln=True)
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, f"TOTAL: ${venta_total_mxn:,.2f} MXN", ln=True)
        
        pdf_buf = io.BytesIO()
        pdf_out = pdf.output(dest='S')
        if isinstance(pdf_out, str): pdf_buf.write(pdf_out.encode('latin-1'))
        else: pdf_buf.write(pdf_out)
        pdf_buf.seek(0)
        
        st.download_button("📄 Descargar PDF", pdf_buf, f"Cot_{nombre_cliente}.pdf", "application/pdf", use_container_width=True)

    with a3:
        wa_msg = f"Cotización {nombre_cliente}\nTotal: ${venta_total_mxn:,.2f} MXN"
        url_wa = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_msg)}"
        st.markdown(f'<a href="{url_wa}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 WhatsApp</button></a>', unsafe_allow_html=True)

with tab_historial:
    st.header("📜 Historial de Cotizaciones Detallado")
    if st.session_state.historial:
        # Mostramos la tabla con todas las columnas de desglose
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
    else:
        st.write("No hay registros en esta sesión.")
