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

# --- 2. BASE DE DATOS DE REFERENCIA (Tu Foto) ---
datos_referencia = [
    ["EXPO", "MTY-AREA METRO", "NUEVO LAREDO", 230, 26.00, 34.67],
    ["EXPO", "SALTILLO - RAMOS", "NUEVO LAREDO", 310, 24.00, 32.00],
    ["EXPO", "DERRAMADERO", "NUEVO LAREDO", 380, 25.00, 33.33],
    ["IMPO", "NUEVO Laredo", "MTY-AREA METRO", 230, 31.10, 41.46],
    ["IMPO", "NUEVO LAREDO", "SALTILLO - RAMOS", 310, 28.00, 37.33],
    ["IMPO", "NUEVO LAREDO", "DERRAMADERO", 380, 28.10, 37.47]
]
df_ref = pd.DataFrame(datos_referencia, columns=["Tipo", "Origen", "Destino", "KM_Ref", "CPK_Base", "IPK_Ref"])

# --- 3. BARRA LATERAL (PANEL DE CONTROL) ---
with st.sidebar:
    st.header("👤 Datos del Cliente")
    nombre_cliente = st.text_input("Nombre del Cliente", "Cliente General")
    tipo_operacion = st.selectbox("Tipo de Operación", ["EXPO", "IMPO"])
    
    st.markdown("---")
    st.header("⚙️ Negociación en Vivo")
    
    rutas_filtro = df_ref[df_ref["Tipo"] == tipo_operacion]
    ruta_sel = st.selectbox("Cargar desde Tabla:", 
                            ["Nueva Ruta (Manual)"] + (rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]).tolist())
    
    if ruta_sel != "Nueva Ruta (Manual)":
        datos_ruta = rutas_filtro[(rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]) == ruta_sel].iloc[0]
        cpk_init = float(datos_ruta["CPK_Base"])
    else:
        cpk_init = 25.0

    cpk_manual = st.number_input("Costo Base (CPK) $", value=cpk_init, step=0.5)
    
    modo_negocio = st.radio("Método de Cotización:", ["Por Margen (%)", "Por IPK ($)"])
    
    if modo_negocio == "Por Margen (%)":
        margen_input = st.slider("Margen Objetivo (%)", 1, 95, 25)
        # Lógica Excel: IPK = Costo / (1 - Margen)
        ipk_final = cpk_manual / (1 - (margen_input / 100))
    else:
        ipk_input = st.number_input("IPK Sugerido / Negociado $", value=cpk_manual * 1.33, step=0.1)
        ipk_final = ipk_input
        # Lógica inversa: Margen = 1 - (Costo / IPK)
        margen_input = (1 - (cpk_manual / ipk_final)) * 100 if ipk_final > 0 else 0

    # ALERTA DE MARGEN CRÍTICO
    if margen_input < 15:
        st.error(f"⚠️ MARGEN CRÍTICO: {margen_input:.1f}%")
    elif margen_input < 25:
        st.warning(f"Margen bajo: {margen_input:.1f}%")
    else:
        st.success(f"Margen saludable: {margen_input:.1f}%")

    tipo_cambio = st.number_input("Tipo de Cambio", value=17.00, step=0.1)
    telefono_wa = st.text_input("WhatsApp (ej: 521...)", "")

# --- 4. COTIZADOR PRINCIPAL ---
tab_cotizador, tab_historial = st.tabs(["🎯 Cotizador", "📜 Historial"])

with tab_cotizador:
    col1, col2 = st.columns(2)
    with col1:
        origen_in = st.text_input("Origen", "Monterrey, NL" if ruta_sel == "Nueva Ruta (Manual)" else datos_ruta["Origen"])
    with col2:
        destino_in = st.text_input("Destino", "Nuevo Laredo, Tamps" if ruta_sel == "Nueva Ruta (Manual)" else datos_ruta["Destino"])

    # MAPA Y DISTANCIA
    distancia_km = 0
    try:
        res = gmaps.directions(origen_in, destino_in, mode="driving")
        if res:
            distancia_km = res[0]['legs'][0]['distance']['value'] / 1000
            st.success(f"🛣️ Ruta calculada: {distancia_km:.2f} km")
            map_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(origen_in)}&destination={urllib.parse.quote(destino_in)}&mode=driving"
            st.markdown(f'<iframe width="100%" height="300" frameborder="0" style="border:0" src="{map_url}" allowfullscreen></iframe>', unsafe_allow_html=True)
    except:
        distancia_km = st.number_input("Distancia Manual (KM)", value=230.0)

    st.markdown("---")
    with st.expander("💰 Gastos y Conceptos Adicionales"):
        c1, c2, c3 = st.columns(3)
        g_casetas = c1.number_input("Casetas $", 0.0)
        g_cruce = c2.number_input("Cruce $", 0.0)
        g_maniobras = c3.number_input("Maniobras $", 0.0)
        
    # CÁLCULOS FINALES
    flete_neto = distancia_km * ipk_final
    venta_total_mxn = flete_neto + g_casetas + g_cruce + g_maniobras
    venta_total_usd = venta_total_mxn / tipo_cambio

    # MÉTRICAS DE RESULTADO
    res1, res2, res3 = st.columns(3)
    res1.metric("VENTA TOTAL MXN", f"${venta_total_mxn:,.2f}")
    res2.metric("VENTA TOTAL USD", f"${venta_total_usd:,.2f}")
    
    # Color de IPK dinámico según margen
    color_delta = "normal" if margen_input >= 25 else "inverse"
    res3.metric("IPK FINAL", f"${ipk_final:.2f}", f"{margen_input:.1f}% Margen", delta_color=color_delta)

    # ACCIONES
    st.markdown("### 📤 Finalizar")
    a1, a2, a3 = st.columns(3)
    
    with a1:
        if st.button("💾 Guardar en Historial", use_container_width=True):
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Cliente": nombre_cliente,
                "Ruta": f"{origen_in}-{destino_in}",
                "IPK": f"${ipk_final:.2f}",
                "Total MXN": f"${venta_total_mxn:,.2f}"
            })
            st.toast("Cotización archivada")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"COTIZACION: {nombre_cliente}", ln=True, align='C')
        pdf.set_font("Arial", size=11)
        pdf.ln(10)
        pdf.cell(0, 7, f"Servicio: {tipo_operacion} | Ruta: {origen_in} - {destino_in}", ln=True)
        pdf.cell(0, 7, f"Distancia: {distancia_km:.2f} km | IPK: ${ipk_final:.2f}", ln=True)
        pdf.cell(0, 7, f"Subtotal Flete: ${flete_neto:,.2f} MXN", ln=True)
        if (g_casetas + g_cruce + g_maniobras) > 0:
            pdf.cell(0, 7, f"Gastos Adicionales: ${ (g_casetas + g_cruce + g_maniobras) :,.2f} MXN", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f"TOTAL: ${venta_total_mxn:,.2f} MXN", ln=True)
        pdf.cell(0, 10, f"TOTAL USD: ${venta_total_usd:,.2f} (TC: {tipo_cambio})", ln=True)
        
        pdf_out = pdf.output(dest='S').encode('latin-1')
        st.download_button("📄 Descargar PDF", pdf_out, f"Cot_{nombre_cliente}.pdf", "application/pdf", use_container_width=True)

    with a3:
        wa_txt = f"*COTIZACIÓN {tipo_operacion}*\n*Cliente:* {nombre_cliente}\n*Ruta:* {origen_in} -> {destino_in}\n*IPK:* ${ipk_final:.2f}\n*Total:* ${venta_total_mxn:,.2f} MXN"
        wa_url = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_txt)}"
        st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 Enviar WhatsApp</button></a>', unsafe_allow_html=True)

with tab_historial:
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
    else:
        st.info("No hay historial disponible.")
