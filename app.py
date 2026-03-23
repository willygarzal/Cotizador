import streamlit as st
import googlemaps
from fpdf import FPDF
import urllib.parse
import pandas as pd
from datetime import datetime
import io
import requests

# --- 1. CONFIGURACIÓN ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
except Exception:
    st.error("⚠️ Configura 'MAPS_API_KEY' en secrets.toml")

st.set_page_config(page_title="Cotizador Maestro RL", layout="wide")

# Inicializar estados de sesión
if 'cotizacion_actual' not in st.session_state:
    st.session_state.cotizacion_actual = []
if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. CONSTANTES Y PRECIOS ---
RENDIMIENTO_BASE = 2.7
precios_accesorios = {
    "SELLOS DE SEGURIDAD": 130.00,
    "HORA ADICIONAL MANIOBRA": 435.00,
    "DEMORAS CAJA PLANTA (4to DÍA)": 1045.00,
    "MOVIMIENTO EN FALSO / CANCELACIÓN": 2610.00,
    "PARADA ADICIONAL / DESVIACIÓN": 2610.00,
    "CRUCE": 2341.75,
    "LAVADO DE CAJA": 170.00,
    "BASCULA": 935.00
}

# --- 3. BARRA LATERAL (DATOS MAESTROS) ---
with st.sidebar:
    st.header("👤 Datos de la Cotización")
    # Campos en blanco por defecto
    empresa_cliente = st.text_input("Para: (Empresa)", value="", placeholder="Nombre del Cliente")
    atencion_cliente = st.text_input("Atención: (Contacto)", value="", placeholder="Persona de contacto")
    
    st.markdown("---")
    st.header("⛽ Combustible (FSC)")
    # Precio del diésel ajustable, rendimiento bloqueado a 2.7
    precio_diesel = st.number_input("Precio Diésel ($/L)", value=21.30, step=0.1)
    st.info(f"Rendimiento estándar: {RENDIMIENTO_BASE} km/L")

    st.markdown("---")
    st.header("⚙️ Ajustes de Operación")
    tipo_op = st.selectbox("Servicio", ["Importación", "Exportación", "Nacional"])
    tc = st.number_input("Tipo de Cambio", value=17.50, step=0.1)
    mult_peaje = st.number_input("Multiplicador Casetas (T3S2)", value=2.5, step=0.1)
    
    st.subheader("📊 Rentabilidad Interna")
    ipk_base = st.number_input("IPK Objetivo (MXN/km)", value=15.27)
    
    telefono_wa = st.text_input("WhatsApp Cliente", "521")

# --- 4. ÁREA DE TRABAJO ---
tab_cot, tab_resumen, tab_hist = st.tabs(["📍 Configurar Rutas", "📄 Cotización Final", "📜 Historial"])

with tab_cot:
    col_mapa, col_datos = st.columns([2, 1])
    
    with col_mapa:
        st.subheader("🗺️ Ruta")
        c1, c2 = st.columns(2)
        orig = c1.text_input("Origen", value="", placeholder="Ej. Nuevo Laredo")
        dest = c2.text_input("Destino", value="", placeholder="Ej. Silao")
        
        km_auto, casetas_auto = 0.0, 0.0
        
        if orig and dest:
            try:
                # Routes API para Casetas y KM
                url = "https://routes.googleapis.com/directions/v2:computeRoutes"
                headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key,
                           "X-Goog-FieldMask": "routes.distanceMeters,routes.travelAdvisory.tollInfo"}
                payload = {"origin": {"address": orig}, "destination": {"address": dest},
                           "travelMode": "DRIVE", "extraComputations": ["TOLLS"]}
                
                resp = requests.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if "routes" in data:
                        r_data = data["routes"][0]
                        km_auto = round(r_data.get("distanceMeters", 0) / 1000.0, 0)
                        if "travelAdvisory" in r_data and "tollInfo" in r_data["travelAdvisory"]:
                            tolls = r_data["travelAdvisory"]["tollInfo"].get("estimatedPrice", [])
                            for t in tolls:
                                if t.get("currencyCode") == "MXN":
                                    casetas_auto = float(t.get("units", 0)) + (float(t.get("nanos", 0))/1e9)
                
                m_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}"
                st.markdown(f'<iframe width="100%" height="300" src="{m_url}"></iframe>', unsafe_allow_html=True)
            except: st.warning("Ingrese una ruta válida.")

    with col_datos:
        st.subheader("💰 Desglose")
        kms = st.number_input("KMS", value=float(km_auto))
        flete = st.number_input("Flete", value=float(kms * ipk_base))
        casetas = st.number_input("Casetas", value=float(casetas_auto * mult_peaje))
        
        # FÓRMULA MAESTRA: (KM / 2.7) * PRECIO DIESEL
        fsc = (kms / RENDIMIENTO_BASE) * precio_diesel if kms > 0 else 0
        st.write(f"**FSC:** ${fsc:,.2f}")
        
        total_r = flete + casetas + fsc
        st.metric("Total Ruta", f"${total_r:,.2f}")

        if st.button("➕ Agregar Ruta a la Propuesta", use_container_width=True, type="primary"):
            if not orig or not dest:
                st.error("Faltan datos de ruta.")
            else:
                st.session_state.cotizacion_actual.append({
                    "Origen": orig, "Destino": dest, "Servicio": tipo_op,
                    "KMS": int(kms), "Flete": flete, "Casetas": casetas,
                    "FSC": fsc, "Total": total_r
                })
                st.success("Ruta agregada.")

with tab_resumen:
    if st.session_state.cotizacion_actual:
        df_res = pd.DataFrame(st.session_state.cotizacion_actual)
        st.table(df_res.style.format({"Flete": "${:,.2f}", "Casetas": "${:,.2f}", "FSC": "${:,.2f}", "Total": "${:,.2f}"}))
        
        total_global = df_res["Total"].sum()
        
        # Accesorios
        st.subheader("➕ Cargos Adicionales")
        acc_sel = st.multiselect("Seleccionar accesorios:", list(precios_accesorios.keys()))
        t_acc = sum([precios_accesorios[a] for a in acc_sel])
        total_final = total_global + t_acc
        
        st.metric("TOTAL GLOBAL A FACTURAR (SIN IVA)", f"${total_final:,.2f} MXN")

        if st.button("🗑️ Limpiar Todo"):
            st.session_state.cotizacion_actual = []
            st.rerun()

        st.markdown("---")
        c1, c2 = st.columns(2)
        
        with c1:
            if not empresa_cliente: st.warning("Capture el nombre del cliente.")
            else:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "RL TRANSPORTACIONES", ln=True)
                pdf.set_font("Arial", "", 10)
                pdf.cell(0, 5, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='R')
                pdf.ln(5)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 6, f"Para: {empresa_cliente}", ln=True)
                pdf.cell(0, 6, f"Atención: {atencion_cliente}", ln=True)
                pdf.ln(5)
                
                # Tabla
                pdf.set_font("Arial", "B", 8)
                pdf.set_fill_color(220)
                h = ["Origen", "Destino", "KMS", "Flete", "Casetas", "FSC", "Total"]
                w = [35, 35, 15, 25, 25, 25, 30]
                for i in range(len(h)): pdf.cell(w[i], 8, h[i], 1, 0, 'C', True)
                pdf.ln()
                
                pdf.set_font("Arial", "", 8)
                for r in st.session_state.cotizacion_actual:
                    pdf.cell(w[0], 8, r["Origen"][:20], 1); pdf.cell(w[1], 8, r["Destino"][:20], 1)
                    pdf.cell(w[2], 8, str(r["KMS"]), 1, 0, 'C'); pdf.cell(w[3], 8, f"${r['Flete']:,.2f}", 1, 0, 'R')
                    pdf.cell(w[4], 8, f"${r['Casetas']:,.2f}", 1, 0, 'R'); pdf.cell(w[5], 8, f"${r['FSC']:,.2f}", 1, 0, 'R')
                    pdf.cell(w[6], 8, f"${r['Total']:,.2f}", 1, 0, 'R'); pdf.ln()
                
                if t_acc > 0:
                    pdf.cell(sum(w[:-1]), 8, f"Accesorios ({', '.join(acc_sel)}):", 1, 0, 'R')
                    pdf.cell(w[-1], 8, f"${t_acc:,.2f}", 1, 0, 'R'); pdf.ln()

                pdf.ln(5); pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 10, f"TOTAL: ${total_final:,.2f} MXN", ln=True, align='R')
                
                # Cláusulas (SIN CARACTERES ESPECIALES)
                pdf.ln(5); pdf.set_font("Arial", "B", 9); pdf.cell(0, 5, "CLAUSULAS:", ln=True)
                pdf.set_font("Arial", "", 8)
                c_list = ["- No materiales peligrosos. Caja Regular.", "- FSC se actualiza segun mercado.", 
                          "- Cliente responsable de remolques.", "- 3h carga / 3h descarga gratis.", 
                          "- Hora extra: $435.00. Mov. Falso: $2,610.00.", "- Terminos: 15 dias de credito."]
                for cl in c_list: pdf.cell(0, 4, cl, ln=True)
                
                pdf.ln(10); pdf.set_font("Arial", "B", 10)
                pdf.cell(95, 5, "Gilberto Ochoa", 0, 0, 'C'); pdf.cell(95, 5, atencion_cliente, 0, 1, 'C')
                pdf.cell(95, 5, "RL Transportaciones", 0, 0, 'C'); pdf.cell(95, 5, "Acepto Tarifas", 0, 1, 'C')

                pdf_data = pdf.output(dest='S').encode('latin-1')
                st.download_button("📄 Bajar PDF", pdf_data, f"Cot_{empresa_cliente}.pdf", "application/pdf", use_container_width=True)

        with c2:
            msg = f"*COTIZACIÓN RL*\n*Cliente:* {empresa_cliente}\n"
            for r in st.session_state.cotizacion_actual:
                msg += f"• {r['Origen']} -> {r['Destino']}: ${r['Total']:,.2f}\n"
            msg += f"\n*TOTAL:* ${total_final:,.2f} MXN"
            st.markdown(f'<a href="https://wa.me/{telefono_wa}?text={urllib.parse.quote(msg)}" target="_blank"><button style="width:100%; height:40px; background-color:#25D366; color:white; border:none; border-radius:5px; cursor:pointer;">📲 WhatsApp</button></a>', unsafe_allow_html=True)
    else:
        st.info("Añada una ruta para comenzar.")

with tab_hist:
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial))
    else: st.info("Historial vacío.")
