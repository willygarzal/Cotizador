import streamlit as st
import googlemaps
from fpdf import FPDF
import urllib.parse
import pandas as pd
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN Y API ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
except Exception:
    st.error("⚠️ Configura 'MAPS_API_KEY' en el archivo secrets.toml")

st.set_page_config(page_title="Cotizador Maestro 53' (Final)", layout="wide")

if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. BASE DE DATOS (Tu Foto) ---
datos_referencia = [
    ["EXPO", "MTY-AREA METRO", "NUEVO LAREDO", 230, 26.00, 34.67],
    ["EXPO", "SALTILLO - RAMOS", "NUEVO LAREDO", 310, 24.00, 32.00],
    ["EXPO", "DERRAMADERO", "NUEVO LAREDO", 380, 25.00, 33.33],
    ["IMPO", "NUEVO LAREDO", "MTY-AREA METRO", 230, 31.10, 41.46],
    ["IMPO", "NUEVO LAREDO", "SALTILLO - RAMOS", 310, 28.00, 37.33],
    ["IMPO", "NUEVO LAREDO", "DERRAMADERO", 380, 28.10, 37.47]
]
df_ref = pd.DataFrame(datos_referencia, columns=["Tipo", "Origen", "Destino", "KM_Ref", "CPK_Base", "IPK_Ref"])

# --- 3. BARRA LATERAL (NEGOCIACIÓN DINÁMICA) ---
with st.sidebar:
    st.header("👤 Datos de Operación")
    nombre_cliente = st.text_input("Cliente", "Cliente General")
    tipo_op = st.selectbox("Tipo de Operación", ["EXPO", "IMPO"])
    tc = st.number_input("Tipo de Cambio (MXN/USD)", value=17.50, step=0.1)
    
    st.markdown("---")
    st.header("⚙️ Negociación")
    moneda_neg = st.radio("Negociar en:", ["MXN (Pesos)", "USD (Dólares)"])
    
    rutas_filtro = df_ref[df_ref["Tipo"] == tipo_op]
    opciones = ["Manual (Ruta Nueva)"] + (rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]).tolist()
    ruta_sel = st.selectbox("Cargar de Tabla:", opciones)
    
    if ruta_sel != "Manual (Ruta Nueva)":
        d_r = rutas_filtro[(rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]) == ruta_sel].iloc[0]
        cpk_init = float(d_r["CPK_Base"])
        km_init = float(d_r["KM_Ref"])
    else:
        cpk_init, km_init = 25.0, 1.0

    cpk_mxn = st.number_input("Mi Costo (CPK MXN) $", value=cpk_init)
    
    # Lógica de IPK Dinámico
    if moneda_neg == "MXN (Pesos)":
        ipk_mxn = st.number_input("IPK Objetivo (MXN) $", value=cpk_mxn / 0.75) # 25% Margen
        ipk_usd = ipk_mxn / tc
    else:
        ipk_usd = st.number_input("IPK Objetivo (USD) $", value=(cpk_mxn / 0.75) / tc)
        ipk_mxn = ipk_usd * tc

    # CÁLCULO DE MARGEN REAL SENSIBLE AL TC
    # (Venta MXN - Costo MXN) / Venta MXN
    margen_real = (1 - (cpk_mxn / ipk_mxn)) * 100 if ipk_mxn > 0 else 0

    if margen_real < 0: st.error(f"🚨 PÉRDIDA: {margen_real:.1f}%")
    elif margen_real < 15: st.warning(f"⚠️ CRÍTICO: {margen_real:.1f}%")
    elif margen_real < 25: st.info(f"Margen: {margen_real:.1f}%")
    else: st.success(f"🟢 Margen Óptimo: {margen_real:.1f}%")

    telefono_wa = st.text_input("WhatsApp Cliente", "521")

# --- 4. CUERPO PRINCIPAL (COTIZADOR) ---
tab_cot, tab_hist = st.tabs(["🎯 Cotizador en Vivo", "📜 Historial Detallado"])

with tab_cot:
    col_l, col_r = st.columns([2, 1])

    with col_l:
        st.subheader("📍 Ruta y Mapa")
        c1, c2 = st.columns(2)
        orig = c1.text_input("Origen", "Monterrey" if ruta_sel=="Manual (Ruta Nueva)" else d_r["Origen"])
        dest = c2.text_input("Destino", "Nuevo Laredo" if ruta_sel=="Manual (Ruta Nueva)" else d_r["Destino"])
        
        # PRIORIDAD KM TABLA (Ruta Pesada)
        km_final = st.number_input("KM de Ruta (Ajuste para 53 Pies):", value=km_init)
        
        # Referencia Google Maps
        try:
            res = gmaps.directions(orig, dest)
            if res:
                dist_google = res[0]['legs'][0]['distance']['value'] / 1000
                st.caption(f"Referencia Google (Auto): {dist_google:.1f} km")
                m_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}"
                st.markdown(f'<iframe width="100%" height="300" src="{m_url}"></iframe>', unsafe_allow_html=True)
        except: pass

    with col_r:
        st.subheader("💰 Desglose")
        g_extras = st.number_input("Extras (Casetas/Cruce) MXN", 0.0)
        
        # CÁLCULOS FINALES
        flete_mxn = km_final * ipk_mxn
        total_mxn = flete_mxn + g_extras
        total_usd = total_mxn / tc
        utilidad_mxn = total_mxn - (km_final * cpk_mxn)

        st.metric("VENTA TOTAL MXN", f"${total_mxn:,.2f}")
        st.metric("VENTA TOTAL USD", f"${total_usd:,.2f}")
        
        color_metrica = "normal" if margen_real >= 15 else "inverse"
        st.metric("IPK (Pactado)", f"${ipk_mxn:.2f} MXN", f"{margen_real:.1f}% Margen", delta_color=color_metrica)

    # --- ACCIONES DE CIERRE ---
    st.markdown("---")
    a1, a2, a3 = st.columns(3)

    with a1:
        if st.button("💾 Guardar Historial", use_container_width=True):
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Cliente": nombre_cliente,
                "Ruta": f"{orig}-{dest}",
                "TC": tc,
                "IPK MXN": f"${ipk_mxn:.2f}",
                "Total MXN": f"${total_mxn:,.2f}"
            })
            st.toast("Guardado correctamente")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"COTIZACION LOGISTICA - {nombre_cliente}", ln=True, align='C')
        pdf.set_font("Arial", size=11)
        pdf.ln(10)
        pdf.cell(0, 8, f"Ruta: {orig} - {dest} ({km_final} km)", ln=True)
        pdf.cell(0, 8, f"Tarifa por KM (IPK): ${ipk_mxn:.2f} MXN", ln=True)
        pdf.cell(0, 8, f"Subtotal Flete: ${flete_mxn:,.2f} MXN", ln=True)
        if g_extras > 0: pdf.cell(0, 8, f"Adicionales: ${g_extras:,.2f} MXN", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f"TOTAL: ${total_mxn:,.2f} MXN", ln=True)
        pdf.cell(0, 10, f"TOTAL USD: ${total_usd:,.2f} (TC: {tc})", ln=True)
        pdf_out = pdf.output(dest='S').encode('latin-1')
        st.download_button("📄 Descargar PDF", pdf_out, f"Cot_{orig}.pdf", "application/pdf", use_container_width=True)

    with a3:
        wa_text = f"*COTIZACIÓN {tipo_op}*\n*Ruta:* {orig}-{dest}\n*Total:* ${total_mxn:,.2f} MXN\n*TC:* {tc}"
        url_wa = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_text)}"
        st.markdown(f'<a href="{url_wa}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 WhatsApp</button></a>', unsafe_allow_html=True)

with tab_hist:
    if st.session_state.historial:
        st.table(pd.DataFrame(st.session_state.historial))
    else:
        st.info("No hay registros.")
