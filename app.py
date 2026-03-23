import streamlit as st
import googlemaps
from fpdf import FPDF
import urllib.parse
import pandas as pd
from datetime import datetime
import io
import requests

# --- 1. CONFIGURACIÓN DE SEGURIDAD Y API ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
except Exception:
    st.error("⚠️ Error Crítico: Configura 'MAPS_API_KEY' en los Secrets de Streamlit para activar Mapas y Casetas.")

st.set_page_config(page_title="Cotizador Maestro RL Pro - Operación 53'", layout="wide")

# --- 2. PERSISTENCIA DE DATOS (HISTORIAL Y CARRITO) ---
if 'historial' not in st.session_state:
    st.session_state.historial = []
if 'cotizacion_actual' not in st.session_state:
    st.session_state.cotizacion_actual = []

# --- 3. CATÁLOGO DE ACCESORIOS Y TARIFAS (ESTÁNDAR WALMART/RL) ---
precios_accesorios = {
    "SELLOS DE SEGURIDAD": 130.00,
    "HORA ADICIONAL MANIOBRA": 435.00,
    "DEMORAS CAJA EN PLANTA (4to DÍA)": 1045.00,
    "MOVIMIENTO EN FALSO / CANCELACIÓN": 2610.00,
    "PARADAS ADICIONALES/DESVIACIONES": 2610.00,
    "CRUCE": 2341.75,
    "FIANZA": 330.00,
    "CARGA / DESCARGA EN VIVO": 500.00,
    "DEMORAS GENERALES": 935.00,
    "POSICIONAMIENTO": 1190.00,
    "LAVADO DE CAJA": 170.00,
    "FUMIGACION": 552.50,
    "BASCULA": 935.00,
    "EQUIPO DE SUJECION": 595.00
}

# --- 4. BASE DE DATOS DE RUTAS FRECUENTES ---
datos_ref = [
    ["EXPO", "MTY-AREA METRO", "NUEVO LAREDO", 230, 26.00, 34.67],
    ["EXPO", "SALTILLO - RAMOS", "NUEVO LAREDO", 310, 24.00, 32.00],
    ["EXPO", "DERRAMADERO", "NUEVO LAREDO", 380, 25.00, 33.33],
    ["IMPO", "NUEVO LAREDO", "MTY-AREA METRO", 230, 31.10, 41.46],
    ["IMPO", "NUEVO LAREDO", "SALTILLO - RAMOS", 310, 28.00, 37.33],
    ["IMPO", "NUEVO LAREDO", "DERRAMADERO", 380, 28.10, 37.47],
    ["NACIONAL", "NUEVO LAREDO", "SILAO", 916, 22.00, 30.00],
    ["NACIONAL", "NUEVO LAREDO", "HUAMANTLA", 1262, 21.50, 29.50]
]
df_ref = pd.DataFrame(datos_ref, columns=["Tipo", "Origen", "Destino", "KM_Ref", "CPK_Base", "IPK_Ref"])

# --- 5. BARRA LATERAL (CONTROL DE NEGOCIACIÓN) ---
with st.sidebar:
    st.header("👤 Identidad y Cliente")
    empresa_remitente = st.text_input("Nuestra Empresa", "RL TRANSPORTACIONES")
    nombre_remitente = st.text_input("Representante", "Gilberto Ochoa Sepúlveda")
    lugar_expedicion = st.text_input("Lugar", "Pesquería N. L.")
    
    st.markdown("---")
    # AJUSTE SOLICITADO: Campos en blanco para obligar captura nueva
    empresa_cliente = st.text_input("Para: (Empresa)", value="", placeholder="Nombre del cliente")
    atencion_cliente = st.text_input("Atención: (Contacto)", value="", placeholder="Nombre del contacto")
    
    tipo_op = st.selectbox("Tipo de Operación", ["Exportación", "Importación", "Nacional"])
    tc = st.number_input("Tipo de Cambio (MXN/USD)", value=17.50, step=0.1)
    
    st.markdown("---")
    st.header("⛽ Combustible (Regla 2.7)")
    precio_diesel = st.number_input("Precio Diésel ($/L)", value=21.30, step=0.01)
    # Rendimiento de oro 2.7 km/l
    rendimiento_std = 2.7
    st.info(f"Rendimiento fijado: {rendimiento_std} km/L")

    st.markdown("---")
    st.header("⚙️ Ajustes de Rentabilidad")
    moneda_neg = st.radio("Cerrar trato en:", ["MXN (Pesos)", "USD (Dólares)"])
    mult_peaje = st.number_input("Multiplicador Casetas (T3S2)", value=2.5, step=0.1)
    
    # Lógica de sugerencia por tabla
    tipo_map = {"Exportación": "EXPO", "Importación": "IMPO", "Nacional": "NACIONAL"}
    filtro = df_ref[df_ref["Tipo"] == tipo_map[tipo_op]]
    texto_manual = "Manual (Nueva Ruta)"
    opciones = [texto_manual] + (filtro["Origen"] + " -> " + filtro["Destino"]).tolist()
    ruta_sel = st.selectbox("Seleccionar de Tabla:", opciones)
    
    cpk_init, km_init, o_sug, d_sug = 25.0, 1.0, "", ""
    if ruta_sel != texto_manual:
        sel_data = filtro[(filtro["Origen"] + " -> " + filtro["Destino"]) == ruta_sel].iloc[0]
        cpk_init, km_init, o_sug, d_sug = float(sel_data["CPK_Base"]), float(sel_data["KM_Ref"]), sel_data["Origen"], sel_data["Destino"]

    cpk_base = st.number_input("CPK Base (Costo MXN)", value=cpk_init)
    ipk_objetivo = st.number_input("IPK Objetivo (Precio MXN)", value=cpk_base / 0.75)
    
    telefono_wa = st.text_input("WhatsApp Cliente", value="521")

# --- 6. CUERPO DE LA APLICACIÓN ---
tab_cot, tab_resumen, tab_hist = st.tabs(["🎯 Configurar Rutas", "📄 Cotización Formal RL", "📜 Historial de Auditoría"])

with tab_cot:
    col_mapa, col_datos = st.columns([2, 1])
    
    with col_mapa:
        st.subheader("📍 Definición de Trayecto")
        c1, c2 = st.columns(2)
        # AJUSTE: Campos en blanco para evitar errores
        orig = c1.text_input("Origen", value=o_sug, placeholder="Ciudad de origen")
        dest = c2.text_input("Destino", value=d_sug, placeholder="Ciudad de destino")
        
        km_google, casetas_google = 0.0, 0.0
        
        if orig and dest:
            try:
                # Conexión avanzada a Routes API
                r_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
                r_headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key, 
                             "X-Goog-FieldMask": "routes.distanceMeters,routes.travelAdvisory.tollInfo"}
                r_payload = {"origin": {"address": orig}, "destination": {"address": dest}, 
                             "travelMode": "DRIVE", "extraComputations": ["TOLLS"]}
                
                res = requests.post(r_url, json=r_payload, headers=r_headers).json()
                if "routes" in res:
                    km_google = round(res["routes"][0].get("distanceMeters", 0) / 1000.0, 1)
                    if "travelAdvisory" in res["routes"][0] and "tollInfo" in res["routes"][0]["travelAdvisory"]:
                        tolls = res["routes"][0]["travelAdvisory"]["tollInfo"].get("estimatedPrice", [])
                        for t in tolls:
                            if t.get("currencyCode") == "MXN":
                                casetas_google = float(t.get("units", 0)) + (float(t.get("nanos", 0))/1e9)
                
                map_frame = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}"
                st.markdown(f'<iframe width="100%" height="350" src="{map_frame}" style="border-radius:10px; border: 1px solid #ddd;"></iframe>', unsafe_allow_html=True)
            except: st.info("Buscando ruta en Google Maps...")

    with col_datos:
        st.subheader("💰 Desglose Operativo")
        km_final = st.number_input("KMS de Ruta", value=float(km_google if km_google > 0 else km_init))
        flete_final = st.number_input("Flete Base ($)", value=float(km_final * ipk_objetivo))
        casetas_final = st.number_input("Casetas ($)", value=float(casetas_google * mult_peaje))
        
        # FÓRMULA MAESTRA: (KM / 2.7) * PRECIO DIESEL
        fsc_final = (km_final / rendimiento_std) * precio_diesel if km_final > 0 else 0
        st.info(f"FSC calculado: **${fsc_final:,.2f}**")
        
        total_ruta = flete_final + casetas_final + fsc_final
        st.metric("Total de esta Ruta", f"${total_ruta:,.2f}")

        if st.button("➕ AGREGAR A LA PROPUESTA", use_container_width=True, type="primary"):
            if not orig or not dest:
                st.error("⚠️ Falta Origen o Destino")
            else:
                st.session_state.cotizacion_actual.append({
                    "Origen": orig, "Destino": dest, "Servicio": tipo_op,
                    "KMS": km_final, "Flete": flete_final, "Casetas": casetas_final,
                    "FSC": fsc_final, "Total": total_ruta
                })
                st.toast(f"Ruta {orig}-{dest} agregada al carrito.")

with tab_resumen:
    if st.session_state.cotizacion_actual:
        st.subheader("📊 Resumen de Propuesta Multirruta")
        df_act = pd.DataFrame(st.session_state.cotizacion_actual)
        st.table(df_act.style.format({"Flete": "${:,.2f}", "Casetas": "${:,.2f}", "FSC": "${:,.2f}", "Total": "${:,.2f}"}))
        
        st.markdown("---")
        c_acc, c_fin = st.columns(2)
        
        with c_acc:
            st.subheader("📦 Accesorios Adicionales")
            acc_sel = st.multiselect("Seleccionar cargos extra:", list(precios_accesorios.keys()))
            total_acc = 0.0
            det_acc = {}
            for a in acc_sel:
                col1, col2 = st.columns(2)
                cant = col1.number_input(f"Cant {a}", min_value=1.0, value=1.0, key=f"c_{a}")
                prec = col2.number_input(f"Precio {a}", value=float(precios_accesorios[a]), key=f"p_{a}")
                sub = cant * prec
                total_acc += sub
                det_acc[a] = {"cant": cant, "sub": sub}
        
        total_global = df_act["Total"].sum() + total_acc
        
        with c_fin:
            st.subheader("🏁 Liquidación Final")
            st.metric("GRAN TOTAL (Sin Impuestos)", f"${total_global:,.2f} MXN")
            if st.button("🗑️ Vaciar Cotización", type="secondary"):
                st.session_state.cotizacion_actual = []
                st.rerun()

        st.markdown("---")
        # --- GENERACIÓN DE FORMATOS DE SALIDA ---
        b1, b2 = st.columns(2)
        
        with b1:
            if not empresa_cliente or not atencion_cliente:
                st.warning("⚠️ Capture los datos del cliente para habilitar el PDF.")
            else:
                pdf = FPDF()
                pdf.add_page()
                # Encabezado RL corporativo
                pdf.set_font("Arial", "B", 22); pdf.set_text_color(0, 51, 102)
                pdf.cell(0, 10, empresa_remitente, ln=True)
                pdf.set_font("Arial", "B", 14); pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 10, "COTIZACIÓN DE SERVICIOS", ln=True, align='R')
                pdf.set_font("Arial", "", 10); pdf.cell(0, 5, f"{lugar_expedicion}, a {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='R')
                pdf.ln(5)
                # Datos Cliente
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 6, f"Para. {empresa_cliente}", ln=True)
                pdf.cell(0, 6, f"Atención. {atencion_cliente}", ln=True)
                pdf.ln(5); pdf.set_font("Arial", "", 10)
                pdf.multi_cell(0, 5, "Por medio de la presente cotización, informo a usted las tarifas operativas para los siguientes circuitos:")
                pdf.ln(5)
                # Tabla Estilo RL (Walmart)
                pdf.set_font("Arial", "B", 8); pdf.set_fill_color(220, 220, 220)
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
                if det_acc:
                    pdf.set_font("Arial", "I", 8); pdf.cell(sum(w[:-1]), 8, "Accesorios y Cargos Extra:", 1, 0, 'R')
                    pdf.cell(w[-1], 8, f"${total_acc:,.2f}", 1, 0, 'R'); pdf.ln()
                
                pdf.ln(5); pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, f"TOTAL GLOBAL: ${total_global:,.2f} MXN", ln=True, align='R')
                # Letras Chiquitas (SIN CARACTERES ESPECIALES)
                pdf.ln(5); pdf.set_font("Arial", "B", 9); pdf.cell(0, 5, "CLAUSULAS Y CONDICIONES:", ln=True)
                pdf.set_font("Arial", "", 8)
                cla = ["- No materiales peligrosos. Caja Regular.", "- El FSC se actualiza segun mercado de diesel.",
                       "- Maximo 22 toneladas por embarque.", "- Libre de maniobras de carga y descarga.",
                       "- Cliente responsable por el cuidado de los remolques.",
                       "- Maniobras: 3h carga / 3h descarga gratis. Hora extra: $435.00.",
                       "- Demoras (4to dia): $1,045.00 por dia.", "- Cancelaciones: $2,610.00 por movimiento en falso.",
                       "- Terminos de pago: 15 dias de credito."]
                for c in cla: pdf.cell(0, 4, c, ln=True)
                # Firmas
                pdf.ln(15); pdf.set_font("Arial", "B", 10)
                pdf.cell(95, 5, nombre_remitente, 0, 0, 'C'); pdf.cell(95, 5, atencion_cliente, 0, 1, 'C')
                pdf.cell(95, 5, empresa_remitente, 0, 0, 'C'); pdf.cell(95, 5, "Acepto Tarifas y Condiciones", 0, 1, 'C')

                pdf_data = pdf.output(dest='S').encode('latin-1')
                st.download_button("📄 DESCARGAR PDF RL PRO", pdf_data, f"Cotizacion_{empresa_cliente}.pdf", "application/pdf", use_container_width=True)

        with b2:
            msg_wa = f"*RL TRANSPORTACIONES - COTIZACIÓN*\n\n"
            msg_wa += f"*Para:* {empresa_cliente}\n*Atención:* {atencion_cliente}\n\n"
            for r in st.session_state.cotizacion_actual:
                msg_wa += f"🚛 {r['Origen']} -> {r['Destino']}\n   Total: ${r['Total']:,.2f}\n"
            if total_acc > 0: msg_wa += f"\n➕ *Accesorios:* ${total_acc:,.2f}"
            msg_wa += f"\n\n*TOTAL FINAL:* ${total_global:,.2f} MXN\n\n_Acepto Tarifas y Condiciones_"
            
            st.markdown(f'<a href="https://wa.me/{telefono_wa}?text={urllib.parse.quote(msg_wa)}" target="_blank"><button style="width:100%; height:45px; background-color:#25D366; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">📲 ENVIAR POR WHATSAPP</button></a>', unsafe_allow_html=True)
    else:
        st.info("Agregue rutas en la primera pestaña para generar la propuesta formal.")

with tab_hist:
    st.subheader("📜 Historial de Auditoría Interna")
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial))
    else:
        st.info("No hay registros en esta sesión.")
