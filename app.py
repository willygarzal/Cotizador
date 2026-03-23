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

# Inicializar el "Carrito" de rutas si no existe
if 'cotizacion_actual' not in st.session_state:
    st.session_state.cotizacion_actual = []
if 'historial_eterno' not in st.session_state:
    st.session_state.historial_eterno = []

# --- DICCIONARIO DE ACCESORIOS (Precios Walmart) ---
precios_accesorios = {
    "SELLOS DE SEGURIDAD": 130.00,
    "HORA ADICIONAL MANIOBRA": 435.00,
    "DEMORAS CAJA PLANTA (4to DÍA)": 1045.00,
    "MOVIMIENTO EN FALSO / CANCELACIÓN": 2610.00,
    "PARADA ADICIONAL / DESVIACIÓN": 2610.00,
    "LAVADO DE CAJA": 170.00,
    "FUMIGACION": 552.50,
    "BASCULA": 935.00
}

# --- 3. BARRA LATERAL (CONTROLES MAESTROS) ---
with st.sidebar:
    st.header("👤 Datos del Cliente")
    # CAMBIO: Se eliminan los nombres predeterminados para obligar a captura nueva
    empresa_cliente = st.text_input("Para: (Empresa)", value="", placeholder="Nombre de la empresa")
    atencion_cliente = st.text_input("Atención: (Contacto)", value="", placeholder="Persona de contacto")
    tc = st.number_input("Tipo de Cambio", value=17.50, step=0.1)
    
    st.markdown("---")
    st.header("⛽ Parámetros Diésel")
    precio_diesel = st.number_input("Precio Diésel ($/L)", value=21.30, step=0.1)
    # Rendimiento fijado en 2.7 km/l según estándar operativo
    rendimiento_fijo = 2.7 
    st.caption(f"Rendimiento base: {rendimiento_fijo} km/L")

    st.markdown("---")
    st.header("⚙️ Configuración de Ruta")
    tipo_op = st.selectbox("Tipo de Servicio", ["Importación", "Exportación", "Nacional"])
    mult_peaje = st.number_input("Multiplicador Casetas (T3S2)", value=2.5, step=0.1)
    
    # Lógica de IPK / Margen (Interno)
    st.subheader("📊 Rentabilidad (Interna)")
    cpk_base = st.number_input("CPK Base (MXN) $", value=25.0)
    ipk_objetivo = st.number_input("IPK Objetivo (MXN) $", value=cpk_base / 0.75)
    
    telefono_wa = st.text_input("WhatsApp para envío", value="521", placeholder="521XXXXXXXXXX")

# --- 4. ÁREA DE TRABAJO ---
tab_cot, tab_resumen = st.tabs(["📍 Configurar Rutas", "📄 Generar Cotización Final"])

with tab_cot:
    col_mapa, col_datos = st.columns([2, 1])
    
    with col_mapa:
        st.subheader("🗺️ Definir Trayecto")
        c1, c2 = st.columns(2)
        # CAMBIO: Se eliminan las rutas predeterminadas
        orig = c1.text_input("Origen", value="", placeholder="Ej: Nuevo Laredo, Tamps.")
        dest = c2.text_input("Destino", value="", placeholder="Ej: Silao, Gto.")
        
        km_auto = 0.0
        casetas_auto = 0.0
        
        if orig and dest:
            try:
                # Llamada a Routes API para KM y Casetas
                routes_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
                headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key,
                           "X-Goog-FieldMask": "routes.distanceMeters,routes.travelAdvisory.tollInfo"}
                payload = {"origin": {"address": orig}, "destination": {"address": dest},
                           "travelMode": "DRIVE", "extraComputations": ["TOLLS"]}
                
                resp = requests.post(routes_url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if "routes" in data and len(data["routes"]) > 0:
                        ruta = data["routes"][0]
                        km_auto = round(ruta.get("distanceMeters", 0) / 1000.0, 1)
                        if "travelAdvisory" in ruta and "tollInfo" in ruta["travelAdvisory"]:
                            peajes = ruta["travelAdvisory"]["tollInfo"].get("estimatedPrice", [])
                            for p in peajes:
                                if p.get("currencyCode") == "MXN":
                                    casetas_auto = float(p.get("units", 0)) + (float(p.get("nanos", 0))/1e9)
                
                m_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}"
                st.markdown(f'<iframe width="100%" height="300" src="{m_url}"></iframe>', unsafe_allow_html=True)
            except: st.warning("Error conectando con Google Maps")

    with col_datos:
        st.subheader("💰 Valores de esta Ruta")
        km_final = st.number_input("KMS Reales", value=float(km_auto))
        flete_sug = km_final * ipk_objetivo
        flete_final = st.number_input("Flete ($)", value=float(flete_sug))
        
        casetas_final = st.number_input("Casetas ($)", value=float(casetas_auto * mult_peaje))
        
        # Cálculo FSC con tu regla de 2.7
        fsc_final = (km_final / rendimiento_fijo) * precio_diesel
        st.write(f"**FSC (Combustible):** ${fsc_final:,.2f}")
        
        total_ruta = flete_final + casetas_final + fsc_final
        st.metric("Subtotal Ruta", f"${total_ruta:,.2f}")

        if st.button("➕ Agregar Ruta a la Propuesta", use_container_width=True, type="primary"):
            if not orig or not dest:
                st.error("⚠️ Debes ingresar un Origen y Destino válido antes de agregar.")
            else:
                nueva_fila = {
                    "Origen": orig, "Destino": dest, "Servicio": tipo_op,
                    "KMS": km_final, "Flete": flete_final, "Casetas": casetas_final,
                    "FSC": fsc_final, "Total": total_ruta
                }
                st.session_state.cotizacion_actual.append(nueva_fila)
                st.toast("Ruta agregada correctamente")

with tab_resumen:
    if st.session_state.cotizacion_actual:
        df_view = pd.DataFrame(st.session_state.cotizacion_actual)
        st.table(df_view)
        
        gran_total = df_view["Total"].sum()
        st.subheader(f"Total Global de Cotización: ${gran_total:,.2f} MXN")
        
        if st.button("🗑️ Limpiar Cotización", type="secondary"):
            st.session_state.cotizacion_actual = []
            st.rerun()

        st.markdown("---")
        # --- GENERACIÓN DE PDF Y WHATSAPP ---
        c_pdf, c_wa = st.columns(2)
        
        with c_pdf:
            # Validación para asegurar que el usuario llenó los datos del cliente
            if not empresa_cliente or not atencion_cliente:
                st.warning("⚠️ Completa 'Para' y 'Atención' en la barra lateral para habilitar el PDF.")
            else:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "RL TRANSPORTACIONES", ln=True)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, f"COTIZACIÓN - {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='R')
                pdf.ln(5)
                
                pdf.set_font("Arial", "", 10)
                pdf.cell(0, 5, f"Para: {empresa_cliente}", ln=True)
                pdf.cell(0, 5, f"Atención: {atencion_cliente}", ln=True)
                pdf.ln(5)
                
                # Encabezados de Tabla
                pdf.set_font("Arial", "B", 8)
                pdf.set_fill_color(230)
                headers = ["Origen", "Destino", "KMS", "Flete", "Casetas", "FSC", "Total"]
                w = [35, 35, 15, 25, 25, 25, 30]
                for i in range(len(headers)):
                    pdf.cell(w[i], 7, headers[i], border=1, fill=True, align='C')
                pdf.ln()
                
                # Filas del Carrito
                pdf.set_font("Arial", "", 8)
                for r in st.session_state.cotizacion_actual:
                    pdf.cell(w[0], 7, r["Origen"][:20], border=1)
                    pdf.cell(w[1], 7, r["Destino"][:20], border=1)
                    pdf.cell(w[2], 7, str(r["KMS"]), border=1, align='C')
                    pdf.cell(w[3], 7, f"${r['Flete']:,.2f}", border=1, align='R')
                    pdf.cell(w[4], 7, f"${r['Casetas']:,.2f}", border=1, align='R')
                    pdf.cell(w[5], 7, f"${r['FSC']:,.2f}", border=1, align='R')
                    pdf.cell(w[6], 7, f"${r['Total']:,.2f}", border=1, align='R')
                    pdf.ln()
                
                pdf.ln(5)
                pdf.set_font("Arial", "B", 10)
                pdf.cell(0, 10, f"TOTAL COTIZADO: ${gran_total:,.2f} MXN", ln=True, align='R')
                
                # Cláusulas (Sin caracteres especiales que rompan el PDF)
                pdf.ln(5)
                pdf.set_font("Arial", "B", 9)
                pdf.cell(0, 5, "CONDICIONES COMERCIALES:", ln=True)
                pdf.set_font("Arial", "", 8)
                clausulas = [
                    "- Propuesta vigente por 30 dias.",
                    "- Rendimiento base de combustible: 2.7 km/L.",
                    "- El FSC se actualiza segun el precio del diesel del mercado.",
                    "- No se transportan materiales peligrosos.",
                    "- El cliente es responsable por el cuidado de los remolques.",
                    "- Maniobras: Maximo 3 horas carga / 3 horas descarga.",
                    "- Hora adicional de maniobra: $435.00 MXN.",
                    "- Demoras en planta a partir del 4to dia: $1,045.00 MXN.",
                    "- Terminos de pago: 15 dias de credito."
                ]
                for c in clausulas:
                    pdf.cell(0, 4, c, ln=True)
                
                # Firmas
                pdf.ln(10)
                pdf.cell(90, 5, "_______________________", 0, 0, 'C')
                pdf.cell(90, 5, "_______________________", 0, 1, 'C')
                pdf.cell(90, 5, "RL Transportaciones", 0, 0, 'C')
                pdf.cell(90, 5, f"Acepto: {atencion_cliente}", 0, 1, 'C')
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                st.download_button("📄 Descargar PDF Formal", pdf_bytes, "Cotizacion.pdf", "application/pdf", use_container_width=True)

        with c_wa:
            wa_msg = f"*RL TRANSPORTACIONES - COTIZACIÓN*\n\n"
            wa_msg += f"*Cliente:* {empresa_cliente}\n*Atención:* {atencion_cliente}\n\n"
            for r in st.session_state.cotizacion_actual:
                wa_msg += f"📍 {r['Origen']} -> {r['Destino']}\n"
                wa_msg += f"   Total: ${r['Total']:,.2f}\n"
            wa_msg += f"\n*GRAN TOTAL:* ${gran_total:,.2f} MXN\n"
            wa_msg += f"\n_Acepto Tarifas y Condiciones_"
            
            url_wa = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_msg)}"
            st.markdown(f'<a href="{url_wa}" target="_blank"><button style="width:100%; height:40px; background-color:#25D366; color:white; border:none; border-radius:5px; cursor:pointer;">📲 Enviar por WhatsApp</button></a>', unsafe_allow_html=True)
    else:
        st.info("Agrega rutas en la pestaña anterior para generar el documento.")

