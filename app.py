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
    st.error("⚠️ Configura 'MAPS_API_KEY' en el archivo secrets.toml")

st.set_page_config(page_title="Cotizador Maestro 53' Full", layout="wide")

if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. BASE DE DATOS ---
datos_ref = [
    ["EXPO", "MTY-AREA METRO", "NUEVO LAREDO", 230, 26.00, 34.67],
    ["EXPO", "SALTILLO - RAMOS", "NUEVO LAREDO", 310, 24.00, 32.00],
    ["EXPO", "DERRAMADERO", "NUEVO LAREDO", 380, 25.00, 33.33],
    ["IMPO", "NUEVO LAREDO", "MTY-AREA METRO", 230, 31.10, 41.46],
    ["IMPO", "NUEVO LAREDO", "SALTILLO - RAMOS", 310, 28.00, 37.33],
    ["IMPO", "NUEVO Laredo", "DERRAMADERO", 380, 28.10, 37.47]
]
df_ref = pd.DataFrame(datos_ref, columns=["Tipo", "Origen", "Destino", "KM_Ref", "CPK_Base", "IPK_Ref"])

# --- 3. BARRA LATERAL (CONTROL FINANCIERO) ---
with st.sidebar:
    st.header("👤 Operación")
    nombre_cliente = st.text_input("Cliente", "Cliente General")
    tipo_op = st.selectbox("Tipo de Operación", ["EXPO", "IMPO"])
    tc = st.number_input("Tipo de Cambio (MXN/USD)", value=17.50, step=0.1)
    
    st.markdown("---")
    st.header("⚙️ Negociación de Tarifa")
    moneda_neg = st.radio("Negociar IPK en:", ["MXN (Pesos)", "USD (Dólares)"])
    
    rutas_filtro = df_ref[df_ref["Tipo"] == tipo_op]
    texto_manual = "Manual (Ruta Nueva)"
    opciones = [texto_manual] + (rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]).tolist()
    ruta_sel = st.selectbox("Cargar de Tabla:", opciones)
    
    cpk_init, km_init = 25.0, 1.0
    orig_sug, dest_sug = "Monterrey", "Nuevo Laredo"

    if ruta_sel != texto_manual:
        d_r = rutas_filtro[(rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]) == ruta_sel].iloc[0]
        cpk_init, km_init = float(d_r["CPK_Base"]), float(d_r["KM_Ref"])
        orig_sug, dest_sug = d_r["Origen"], d_r["Destino"]

    cpk_manual = st.number_input("CPK Base (MXN) $", value=cpk_init)
    
    with st.expander("🛠️ Costos Operativos (Opcionales)"):
        cpac = st.number_input("CPAC / Otros", 0.0)
        e1 = st.number_input("E1 (Variable)", 0.0)
        e2 = st.number_input("E2 (Variable)", 0.0)
    
    cpk_total_mxn = cpk_manual + cpac + e1 + e2

    if moneda_neg == "MXN (Pesos)":
        ipk_mxn = st.number_input("IPK Objetivo (MXN) $", value=cpk_total_mxn / 0.75)
        ipk_usd = ipk_mxn / tc
    else:
        ipk_usd = st.number_input("IPK Objetivo (USD) $", value=(cpk_total_mxn / 0.75) / tc)
        ipk_mxn = ipk_usd * tc

    margen_real = (1 - (cpk_total_mxn / ipk_mxn)) * 100 if ipk_mxn > 0 else 0
    if margen_real < 0: st.error(f"🚨 PÉRDIDA: {margen_real:.1f}%")
    elif margen_real < 15: st.warning(f"⚠️ CRÍTICO: {margen_real:.1f}%")
    else: st.success(f"🟢 Margen Real: {margen_real:.1f}%")
    
    telefono_wa = st.text_input("WhatsApp Cliente", "521")

# --- 4. COTIZADOR ---
tab1, tab2 = st.tabs(["🎯 Cotizador", "📜 Historial Detallado"])

with tab1:
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.subheader("📍 Ruta (Parámetros 53')")
        c1, c2 = st.columns(2)
        orig, dest = c1.text_input("Origen", orig_sug), c2.text_input("Destino", dest_sug)
        km_final = st.number_input("KM de Ruta (Ajuste Camionero):", value=km_init)
        
        try:
            res = gmaps.directions(orig, dest)
            if res:
                dist_google = res[0]['legs'][0]['distance']['value'] / 1000
                st.caption(f"Google: {dist_google:.1f} km vs Tabla: {km_final} km")
                m_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}"
                st.markdown(f'<iframe width="100%" height="300" frameborder="0" src="{m_url}"></iframe>', unsafe_allow_html=True)
        except: pass

    with col_r:
        st.subheader("💰 Desglose de Cargos")
        casetas = st.number_input("Casetas MXN", 0.0)
        maniobras = st.number_input("Maniobras MXN", 0.0)
        cruce = st.number_input("Cruce MXN", 0.0)
        
        flete_mxn = km_final * ipk_mxn
        total_mxn = flete_mxn + casetas + maniobras + cruce
        total_usd = total_mxn / tc

        st.metric("TOTAL MXN", f"${total_mxn:,.2f}")
        st.metric("TOTAL USD", f"${total_usd:,.2f}")
        st.metric("IPK REAL", f"${ipk_mxn:.2f}", f"{margen_real:.1f}% Margen")

    st.markdown("---")
    a1, a2, a3 = st.columns(3)

    with a1:
        if st.button("💾 Guardar Historial", use_container_width=True):
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Cliente": nombre_cliente,
                "Ruta": f"{orig}-{dest}",
                "Flete MXN": f"${flete_mxn:,.2f}",
                "Casetas": f"${casetas:,.2f}",
                "Maniobras": f"${maniobras:,.2f}",
                "Cruce": f"${cruce:,.2f}",
                "Total MXN": f"${total_mxn:,.2f}",
                "TC": tc
            })
            st.toast("Guardado con desglose")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"COTIZACION: {nombre_cliente}", ln=True, align='C')
        pdf.set_font("Arial", size=11)
        pdf.ln(5)
        pdf.cell(0, 7, f"Ruta: {orig} - {dest} ({km_final} km)", ln=True)
        pdf.cell(0, 7, f"IPK Pactado: ${ipk_mxn:.2f} MXN", ln=True)
        pdf.ln(3)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 7, "DETALLE DE CARGOS:", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 7, f" - Flete Neto: ${flete_mxn:,.2f} MXN", ln=True)
        if casetas > 0: pdf.cell(0, 7, f" - Casetas: ${casetas:,.2f} MXN", ln=True)
        if maniobras > 0: pdf.cell(0, 7, f" - Maniobras: ${maniobras:,.2f} MXN", ln=True)
        if cruce > 0: pdf.cell(0, 7, f" - Cruce: ${cruce:,.2f} MXN", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 10, f"TOTAL FINAL: ${total_mxn:,.2f} MXN", ln=True)
        pdf.cell(0, 10, f"TOTAL USD: ${total_usd:,.2f} (TC: {tc})", ln=True)
        pdf_out = pdf.output(dest='S').encode('latin-1')
        st.download_button("📄 Descargar PDF", pdf_out, f"Cot_{orig}.pdf", "application/pdf", use_container_width=True)

    with a3:
        wa_text = (
            f"*COTIZACIÓN LOGÍSTICA*\n"
            f"*Cliente:* {nombre_cliente}\n"
            f"*Ruta:* {orig} - {dest}\n\n"
            f"*Desglose:*\n"
            f"• Flete: ${flete_mxn:,.2f}\n"
        )
        if casetas > 0: wa_text += f"• Casetas: ${casetas:,.2f}\n"
        if maniobras > 0: wa_text += f"• Maniobras: ${maniobras:,.2f}\n"
        if cruce > 0: wa_text += f"• Cruce: ${cruce:,.2f}\n"
        wa_text += f"\n*TOTAL: ${total_mxn:,.2f} MXN*\n*USD: ${total_usd:,.2f}* (TC: {tc})"
        
        st.markdown(f'<a href="https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_text)}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 WhatsApp</button></a>', unsafe_allow_html=True)

with tab_hist:
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
