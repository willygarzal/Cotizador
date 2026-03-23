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

# Inicializar el "Carrito" de rutas y persistencia de sesión
if 'cotizacion_actual' not in st.session_state:
    st.session_state.cotizacion_actual = []

# --- 2. DICCIONARIOS Y PARÁMETROS FIJOS ---
precios_accesorios = {
    "SELLOS DE SEGURIDAD": 130.00,
    "HORA ADICIONAL MANIOBRA": 435.00,
    "DEMORAS CAJA PLANTA (4to DÍA)": 1045.00,
    "MOVIMIENTO EN FALSO / CANCELACIÓN": 2610.00,
    "PARADA ADICIONAL / DESVIACIÓN": 2610.00
}

RENDIMIENTO_BASE = 2.7 # Tu estándar de oro

# --- 3. BARRA LATERAL (CONTROLES MAESTROS) ---
with st.sidebar:
    st.header("👤 Datos del Cliente")
    # Campos en blanco por defecto para obligar captura nueva
    empresa_cliente = st.text_input("Para: (Empresa)", value="")
    atencion_cliente = st.text_input("Atención: (Contacto)", value="")
    
    st.markdown("---")
    st.header("⛽ Parámetros Diésel")
    precio_diesel = st.number_input("Precio Diésel ($/L)", value=21.30, step=0.1)
    st.caption(f"Rendimiento fijado: {RENDIMIENTO_BASE} km/L")

    st.markdown("---")
    st.header("⚙️ Configuración Global")
    moneda_neg = st.radio("Moneda:", ["MXN", "USD"])
    tipo_op = st.selectbox("Servicio General", ["Importación", "Exportación", "Nacional"])
    mult_peaje = st.number_input("Multiplicador Casetas (T3S2)", value=2.5, step=0.1)
    
    st.subheader("📊 Rentabilidad Base")
    ipk_base = st.number_input("IPK Sugerido (MXN/km)", value=15.27) # Basado en tus cálculos de flete/km
    
    telefono_wa = st.text_input("WhatsApp Destino", "521")

# --- 4. ÁREA DE TRABAJO ---
tab_cot, tab_resumen = st.tabs(["📍 Configurar Rutas", "📄 Generar Cotización Final"])

with tab_cot:
    col_mapa, col_datos = st.columns([2, 1])
    
    with col_mapa:
        st.subheader("🗺️ Definir Trayecto")
        c1, c2 = st.columns(2)
        # Rutas en blanco por defecto
        orig = c1.text_input("Origen", value="", placeholder="Ej. Nuevo Laredo, Tamps.")
        dest = c2.text_input("Destino", value="", placeholder="Ej. Silao, Gto.")
        
        km_auto = 0.0
        casetas_auto = 0.0
        
        if orig and dest:
            try:
                # Llamada a Google Routes API para KM y Peajes Reales
                routes_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
                headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key,
                           "X-Goog-FieldMask": "routes.distanceMeters,routes.travelAdvisory.tollInfo"}
                payload = {"origin": {"address": orig}, "destination": {"address": dest},
                           "travelMode": "DRIVE", "extraComputations": ["TOLLS"]}
                
                resp = requests.post(routes_url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if "routes" in data:
                        ruta = data["routes"][0]
                        km_auto = round(ruta.get("distanceMeters", 0) / 1000.0, 0) # Redondeo entero como en tu PDF
                        if "travelAdvisory" in ruta and "tollInfo" in ruta["travelAdvisory"]:
                            peajes = ruta["travelAdvisory"]["tollInfo"].get("estimatedPrice", [])
                            for p in peajes:
                                if p.get("currencyCode") == "MXN":
                                    casetas_auto = float(p.get("units", 0)) + (float(p.get("nanos", 0))/1e9)
                
                m_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}"
                st.markdown(f'<iframe width="100%" height="350" src="{m_url}" style="border-radius:10px;"></iframe>', unsafe_allow_html=True)
            except: 
                st.warning("Ingrese rutas válidas para activar el mapa y los cálculos.")

    with col_datos:
        st.subheader("💰 Cálculo de Ruta")
        kms = st.number_input("KMS Confirmados", value=float(km_auto))
        
        # Cálculo de Flete basado en IPK
        flete_calculado = kms * ipk_base
        flete = st.number_input("Flete ($)", value=float(flete_calculado))
        
        casetas = st.number_input("Casetas ($)", value=float(casetas_auto * mult_peaje))
        
        # Cálculo FSC con tu regla de 2.7 km/l
        fsc = (kms / RENDIMIENTO_BASE) * precio_diesel if kms > 0 else 0
        st.write(f"**FSC (Combustible):** ${fsc:,.2f}")
        
        total_ruta = flete + casetas + fsc
        st.metric("Total de esta Ruta", f"${total_ruta:,.2f}")

        if st.button("➕ Agregar a la Cotización", use_container_width=True, type="primary"):
            if not orig or not dest:
                st.error("Por favor defina Origen y Destino")
            else:
                st.session_state.cotizacion_actual.append({
                    "Origen": orig, "Destino": dest, "Servicio": tipo_op,
                    "KMS": int(kms), "Flete": flete, "Casetas": casetas,
                    "FSC": fsc, "Total": total_ruta
                })
                st.success(f"Ruta {orig}-{dest} agregada.")

with tab_resumen:
    if st.session_state.cotizacion_actual:
        df_res = pd.DataFrame(st.session_state.cotizacion_actual)
        st.table(df_res.style.format({"Flete": "${:,.2f}", "Casetas": "${:,.2f}", "FSC": "${:,.2f}", "Total": "${:,.2f}"}))
        
        gran_total = df_res["Total"].sum()
        
        col_acc, col_final = st.columns(2)
        
        with col_acc:
            st.subheader("📦 Accesorios Extra")
            acc_sel = st.multiselect("Agregar cargos adicionales a la cotización general:", list(precios_accesorios.keys()))
            total_acc = sum([precios_accesorios[a] for a in acc_sel])
            if total_acc > 0:
                st.write(f"Total Accesorios: ${total_acc:,.2f}")
                gran_total += total_acc

        with col_final:
            st.subheader("🏁 Resumen Final")
            st.metric("GRAN TOTAL A FACTURAR", f"${gran_total:,.2f} {moneda_neg}")
            if st.button("🗑️ Borrar Todo e Iniciar Nueva", type="secondary"):
                st.session_state.cotizacion_actual = []
                st.rerun()

        st.markdown("---")
        # --- GENERACIÓN DE FORMATOS ---
        c_pdf, c_wa = st.columns(2)
        
        with c_pdf:
            if not empresa_cliente or not atencion_cliente:
                st.warning("Complete los datos del cliente en la barra lateral para generar el PDF.")
            else:
                pdf = FPDF()
                pdf.add_page()
                # Encabezado estilo RL
                pdf.set_font("Arial", "B", 18)
                pdf.cell(0, 10, "RL TRANSPORTACIONES", ln=True)
                pdf.set_font("Arial", "", 10)
                pdf.cell(0, 5, f"Pesquería, N.L. a {datetime.now().strftime('%d de %m de %Y')}", ln=True, align='R')
                pdf.ln(5)
                
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 6, f"Para: {empresa_cliente}", ln=True)
                pdf.cell(0, 6, f"Atención: {atencion_cliente}", ln=True)
                pdf.ln(5)
                
                pdf.set_font("Arial", "", 10)
                pdf.multi_cell(0, 5, "Por medio de la presente cotización, informo a usted las tarifas que actualmente manejamos:")
                pdf.ln(5)
                
                # Tabla de Cotización
                pdf.set_font("Arial", "B", 8)
                pdf.set_fill_color(240, 240, 240)
                headers = ["Origen", "Destino", "Servicio", "KMS", "Flete", "Casetas", "FSC", "Total"]
                w = [30, 30, 20, 15, 23, 23, 23, 26]
                for i in range(len(headers)):
                    pdf.cell(w[i], 8, headers[i], border=1, fill=True, align='C')
                pdf.ln()
                
                pdf.set_font("Arial", "", 8)
                for r in st.session_state.cotizacion_actual:
                    pdf.cell(w[0], 8, r["Origen"][:18], border=1)
                    pdf.cell(w[1], 8, r["Destino"][:18], border=1)
                    pdf.cell(w[2], 8, r["Servicio"], border=1, align='C')
                    pdf.cell(w[3], 8, str(r["KMS"]), border=1, align='C')
                    pdf.cell(w[4], 8, f"${r['Flete']:,.2f}", border=1, align='R')
                    pdf.cell(w[5], 8, f"${r['Casetas']:,.2f}", border=1, align='R')
                    pdf.cell(w[6], 8, f"${r['FSC']:,.2f}", border=1, align='R')
                    pdf.cell(w[7], 8, f"${r['Total']:,.2f}", border=1, align='R')
                    pdf.ln()
                
                if total_acc > 0:
                    pdf.set_font("Arial", "I", 8)
                    pdf.cell(sum(w[:-1]), 8, f"Accesorios adicionales ({', '.join(acc_sel)}):", border=1, align='R')
                    pdf.cell(w[-1], 8, f"${total_acc:,.2f}", border=1, align='R')
                    pdf.ln()

                pdf.ln(5)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 10, f"TOTAL GLOBAL: ${gran_total:,.2f} {moneda_neg}", ln=True, align='R')
                
                # Condiciones legales corregidas (Sin caracteres especiales)
                pdf.ln(5)
                pdf.set_font("Arial", "B", 9)
                pdf.cell(0, 5, "CONDICIONES Y CLAUSULAS:", ln=True)
                pdf.set_font("Arial", "", 8)
                condiciones = [
                    "- No materiales peligrosos. Caja Regular.",
                    "- Propuesta vigente por 30 dias.",
                    "- El FSC se actualiza mensualmente segun el mercado de combustible.",
                    "- Cliente responsable por el cuidado de los remolques (daños y robo).",
                    "- Maximo 3 horas para maniobras de carga y 3 para descarga.",
                    "- Hora adicional: $435.00 MXN.",
                    "- Demoras a partir del 4to dia: $1,045.00 MXN por dia.",
                    "- Servicios cancelados: $2,610.00 MXN por movimiento en falso.",
                    "- Terminos de pago: 15 dias de credito."
                ]
                for cond in condiciones:
                    pdf.cell(0, 4, cond, ln=True)
                
                # Firmas
                pdf.ln(15)
                pdf.set_font("Arial", "B", 10)
                pdf.cell(95, 5, "Atentamente", 0, 0, 'C')
                pdf.cell(95, 5, "Acepto Tarifas y Condiciones", 0, 1, 'C')
                pdf.ln(10)
                pdf.cell(95, 5, "_______________________", 0, 0, 'C')
                pdf.cell(95, 5, "_______________________", 0, 1, 'C')
                pdf.set_font("Arial", "", 9)
                pdf.cell(95, 5, "RL Transportaciones", 0, 0, 'C')
                pdf.cell(95, 5, f"{atencion_cliente}", 0, 1, 'C')
                
                pdf_data = pdf.output(dest='S').encode('latin-1')
                st.download_button("📄 Descargar PDF RL", pdf_data, f"Cotizacion_{empresa_cliente}.pdf", "application/pdf", use_container_width=True)

        with c_wa:
            # Mensaje WhatsApp estructurado
            wa_text = f"*RL TRANSPORTACIONES - COTIZACIÓN*\n\n"
            wa_text += f"*Cliente:* {empresa_cliente}\n*Atención:* {atencion_cliente}\n\n"
            for r in st.session_state.cotizacion_actual:
                wa_text += f"📍 *{r['Origen']} -> {r['Destino']}*\n"
                wa_text += f"   KMS: {r['KMS']} | Total: ${r['Total']:,.2f}\n"
            
            if total_acc > 0:
                wa_text += f"\n➕ *Accesorios:* ${total_acc:,.2f}"
                
            wa_text += f"\n\n*GRAN TOTAL:* ${gran_total:,.2f} {moneda_neg}\n"
            wa_text += f"\n_Sujeto a términos y condiciones._"
            
            wa_url = f"https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_text)}"
            st.markdown(f'<a href="{wa_url}" target="_blank"><button style="width:100%; height:45px; background-color:#25D366; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">📲 Enviar por WhatsApp</button></a>', unsafe_allow_html=True)
    else:
        st.info("Agregue al menos una ruta para visualizar el resumen y los documentos.")
