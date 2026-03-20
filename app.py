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
    st.error("⚠️ Error: Revisa tu archivo 'secrets.toml'.")

st.set_page_config(page_title="Cotizador Maestro 53'", layout="wide")

if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. BASE DE DATOS DE REFERENCIA (Tu Foto) ---
datos_referencia = [
    ["EXPO", "MTY-AREA METRO", "NUEVO LAREDO", 230, 26.00, 34.67],
    ["EXPO", "SALTILLO - RAMOS", "NUEVO LAREDO", 310, 24.00, 32.00],
    ["EXPO", "DERRAMADERO", "NUEVO LAREDO", 380, 25.00, 33.33],
    ["IMPO", "NUEVO LAREDO", "MTY-AREA METRO", 230, 31.10, 41.46],
    ["IMPO", "NUEVO LAREDO", "SALTILLO - RAMOS", 310, 28.00, 37.33],
    ["IMPO", "NUEVO LAREDO", "DERRAMADERO", 380, 28.10, 37.47]
]
df_ref = pd.DataFrame(datos_referencia, columns=["Tipo", "Origen", "Destino", "KM_Ref", "CPK_Base", "IPK_Ref"])

# --- 3. BARRA LATERAL (NEGOCIACIÓN Y PREMISAS) ---
with st.sidebar:
    st.header("👤 Cliente y Operación")
    nombre_cliente = st.text_input("Nombre del Cliente", "Cliente General")
    tipo_operacion = st.selectbox("Tipo de Operación", ["EXPO", "IMPO"])
    
    st.markdown("---")
    st.header("⚙️ Panel de Negociación")
    
    # Selector de Ruta
    rutas_filtro = df_ref[df_ref["Tipo"] == tipo_operacion]
    opciones = ["Nueva Ruta (Manual)"] + (rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]).tolist()
    ruta_sel = st.selectbox("Cargar desde Tabla de Referencia:", opciones)
    
    # Cargar valores iniciales
    if ruta_sel != "Nueva Ruta (Manual)":
        datos_ruta = rutas_filtro[(rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]) == ruta_sel].iloc[0]
        cpk_init = float(datos_ruta["CPK_Base"])
        km_referencia = float(datos_ruta["KM_Ref"])
    else:
        cpk_init, km_referencia = 25.0, 0.0

    cpk_manual = st.number_input("Costo Base (CPK) $", value=cpk_init, step=0.5)
    
    modo_negocio = st.radio("Método de Ajuste:", ["Por Margen (%)", "Por IPK ($)"])
    
    if modo_negocio == "Por Margen (%)":
        margen_negocio = st.slider("Margen de Utilidad (%)", 1, 95, 25)
        ipk_final = cpk_manual / (1 - (margen_negocio / 100))
    else:
        ipk_input = st.number_input("IPK a Negociar $", value=cpk_manual * 1.33, step=0.1)
        ipk_final = ipk_input
        margen_negocio = (1 - (cpk_manual / ipk_final)) * 100 if ipk_final > 0 else 0

    # ALERTA VISUAL DE MARGEN (Semáforo)
    if margen_negocio < 15:
        st.error(f"⚠️ MARGEN CRÍTICO: {margen_negocio:.1f}%")
    elif margen_negocio < 25:
        st.warning(f"Margen por debajo del objetivo: {margen_negocio:.1f}%")
    else:
        st.success(f"Margen Óptimo: {margen_negocio:.1f}%")

    tipo_cambio = st.number_input("Tipo de Cambio (MXN/USD)", value=17.00, step=0.1)
    telefono_wa = st.text_input("WhatsApp Cliente (ej: 521...)", "")

# --- 4. CUERPO PRINCIPAL (COTIZADOR) ---
tab_cot, tab_hist = st.tabs(["🎯 Cotizador en Vivo", "📜 Historial"])

with tab_cot:
    col_a, col_b = st.columns(2)
    with col_a:
        origen_in = st.text_input("Origen", "Monterrey, NL" if ruta_sel == "Nueva Ruta (Manual)" else datos_ruta["Origen"])
    with col_b:
        destino_in = st.text_input("Destino", "Nuevo Laredo, Tamps" if ruta_sel == "Nueva Ruta (Manual)" else datos_ruta["Destino"])

    # Lógica de Kilometraje (Respetando Ruta Pesada/Camionera)
    distancia_google = 0
    try:
        res = gmaps.directions(origen_in, destino_in, mode="driving")
        if res:
            distancia_google = res[0]['legs'][0]['distance']['value'] / 1000
    except:
        pass

    if ruta_sel != "Nueva Ruta (Manual)":
        km_final = km_referencia
        st.info(f"📍 KM de Tabla (Ruta 53'): {km_final} km")
        if distancia_google > 0: st.caption(f"Distancia Google (Auto): {distancia_google:.1f} km")
    else:
        km_final = st.number_input("Kilómetros Reales (Ajuste Camionero):", value=distancia_google if distancia_google > 0 else 1.0)

    # Mapa
    if distancia_google > 0:
        map_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(origen_in)}&destination={urllib.parse.quote(destino_in)}&mode=driving"
        st.markdown(f'<iframe width="100%" height="300" frameborder="0" src="{map_url}"></iframe>', unsafe_allow_html=True)

    st.markdown("---")
    with st.expander("💰 Gastos Adicionales (Cruce, Casetas, Maniobras)"):
        c1, c2, c3 = st.columns(3)
        g_casetas = c1.number_input("Casetas $", 0.0)
        g_cruce = c2.number_input("Cruce $", 0.0)
        g_maniobras = c3.number_input("Maniobras $", 0.0)

    # --- CÁLCULOS FINALES (Matemática de tu Excel) ---
    flete_neto = km_final * ipk_final
    venta_total_mxn = flete_neto + g_casetas + g_cruce + g_maniobras
    venta_total_usd = venta_total_mxn / tipo_cambio

    # Resultados Visuales
    res1, res2, res3 = st.columns(3)
    res1.metric("VENTA TOTAL MXN", f"${venta_total_mxn:,.2f}")
    res2.metric("VENTA TOTAL USD", f"${venta_total_usd:,.2f}")
    res3.metric("IPK REAL", f"${ipk_final:.2f}", f"{margen_negocio:.1f}% Margen")

    # --- ACCIONES ---
    st.markdown("### 📤 Finalizar y Enviar")
    a1, a2, a3 = st.columns(3)
    
    with a1:
        if st.button("💾 Guardar en Historial", use_container_width=True):
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Cliente": nombre_cliente,
                "Ruta": f"{origen_in}-{destino_in}",
                "KM": km_final,
                "Total MXN": f"${venta_total_mxn:,.2f}"
            })
            st.toast("¡Guardado!")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"COTIZACION LOGISTICA: {nombre_cliente}", ln=True, align='C')
        pdf.set_font("Arial", size=12)
        pdf.ln(10)
        pdf.cell(0, 8, f"Operación: {tipo_operacion} | Ruta: {origen_in} - {destino_in}", ln=True)
        pdf.cell(0, 8, f"Distancia (Ruta Pesada): {km_final} km", ln=True)
        pdf.cell(0, 8, f"IPK: ${ipk_final:.2f} | Flete Neto: ${flete_neto:,.2f} MXN", ln=True)
        if (g_casetas + g_cruce + g_maniobras) > 0:
            pdf.cell(0, 8, f"Cargos Adicionales: ${(g_casetas + g_cruce + g_maniobras):,.2f} MXN", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f"TOTAL FINAL: ${venta_total_mxn:,.2f} MXN", ln=True)
        pdf.cell(0, 10, f"TOTAL USD: ${venta_total_usd:,.2f} (TC: {tipo_cambio})", ln=True)
        
        pdf_out = pdf.output(dest='S').encode('latin-1')
        st.download_button("📄 Descargar PDF Detallado", pdf_out, f"Cot_{nombre_cliente}.pdf", "application/pdf", use_container_width=True)

    with a3:
        wa_text = f"*COTIZACIÓN {tipo_operacion}*\n*Cliente:* {nombre_cliente}\n*Ruta:* {origen_in} -> {destino_in}\n*KM:* {km_final}\n*Total:* ${venta_total_mxn:,.2f} MXN"
        url_wa = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_text)}"
        st.markdown(f'<a href="{url_wa}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 Enviar a WhatsApp</button></a>', unsafe_allow_html=True)

with tab_hist:
    if st.session_state.historial:
        st.table(pd.DataFrame(st.session_state.historial))
    else:
        st.info("No hay registros en el historial.")
