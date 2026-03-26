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

st.set_page_config(page_title="Cotizador Maestro 53' Pro - Consolidado", layout="wide")

# Inicialización de la Memoria para Multiruta
if 'propuesta_actual' not in st.session_state:
    st.session_state.propuesta_actual = []
if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- DICCIONARIOS DE COSTOS ---
precios_accesorios = {
    "FIANZA": 330.00,
    "CARGA / DESCARGA EN VIVO": 500.00,
    "DEMORAS": 935.00,
    "CRUCE": 2341.75,
    "POSICIONAMIENTO": 1190.00,
    "LAVADO DE CAJA": 170.00,
    "FUMIGACION": 552.50,
    "BASCULA": 935.00,
    "EQUIPO DE SUJECION": 595.00,
    "SELLOS DE SEGURIDAD": 130.00,
    "HORA ADICIONAL MANIOBRA": 435.00,
    "DEMORAS CAJA EN PLANTA (4to DÍA)": 1045.00,
    "PARADAS ADICIONALES/DESVIACIONES": 2610.00,
    "MOVIMIENTO EN FALSO": 2610.00
}

# --- 2. BARRA LATERAL (LÓGICA DE NEGOCIACIÓN) ---
with st.sidebar:
    st.header("👤 Datos de Cotización")
    empresa_remitente = st.text_input("Nuestra Empresa", "")
    nombre_remitente = st.text_input("Nuestro Representante", "")
    lugar_expedicion = st.text_input("Lugar de Expedición", "")
    
    st.markdown("---")
    empresa_cliente = st.text_input("Para: (Empresa)", "")
    atencion_cliente = st.text_input("Atención: (Contacto)", "")
    tipo_op = st.selectbox("Servicio", ["Importación", "Exportación", "Nacional"])
    
    tipo_equipo = st.radio("Tipo de Equipo", ["Caja de Intercambio (Tercero)", "Caja Propia"])
    
    tc = st.number_input("Tipo de Cambio (MXN/USD)", value=17.66, step=0.01)
    
    st.markdown("---")
    st.header("⛽ Combustible (FSC)")
    precio_diesel = st.number_input("Precio Diésel ($/L)", value=24.64, step=0.01)
    
    # Lógica del Factor Espejo en Sidebar
    # Nota: Usamos una distancia de referencia de 1000km para mostrar el factor de ruta larga por defecto
    st.markdown("#### Factor Resultante:")
    rend_ref = 3.1
    ajuste_ref = 0.90
    factor_vis = (precio_diesel / rend_ref) + ajuste_ref
    st.subheader(f"${factor_vis:.2f} / km")
    st.caption(f"(Basado en rendimiento de {rend_ref} + ajuste de ${ajuste_ref})")
    
    st.markdown("---")
    st.header("⚙️ Negociación y Ajustes")
    moneda_neg = st.radio("Cerrar trato en:", ["MXN (Pesos)", "USD (Dólares)"])
    
    st.caption("Ajuste de Casetas Automáticas (Auto vs Tracto)")
    mult_peaje = st.number_input("Multiplicador Carga Pesada (T3S2)", value=2.5, step=0.1)
    
    telefono_wa = st.text_input("WhatsApp Cliente", "")

# --- 3. ÁREA DE COTIZACIÓN ---
tab_cot, tab_hist = st.tabs(["🎯 Cotizador Pro", "📜 Historial Completo"])

with tab_cot:
    st.markdown("## Configuración del Tramo")

    col_ruta, col_extras = st.columns([2, 1])

    with col_ruta:
        st.subheader("📍 Ruta y Extracción de Peajes")
        c1, c2 = st.columns(2)
        orig = c1.text_input("Origen", "")
        dest = c2.text_input("Destino", "")
        
        distancia_real_km = 0.0
        costo_peaje_pesado = 0.0
        
        if orig and dest:
            try:
                m_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}"
                st.markdown(f'<iframe width="100%" height="250" src="{m_url}" style="border-radius:10px; border: 1px solid #ddd;"></iframe>', unsafe_allow_html=True)
                
                routes_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
                headers = {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": "routes.distanceMeters,routes.travelAdvisory.tollInfo"
                }
                payload = {
                    "origin": {"address": orig},
                    "destination": {"address": dest},
                    "travelMode": "DRIVE",
                    "extraComputations": ["TOLLS"]
                }
                
                resp = requests.post(routes_url, json=payload, headers=headers)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if "routes" in data and len(data["routes"]) > 0:
                        ruta_data = data["routes"][0]
                        if "distanceMeters" in ruta_data:
                            distancia_real_km = round(ruta_data["distanceMeters"] / 1000.0, 1)
                        
                        if "travelAdvisory" in ruta_data and "tollInfo" in ruta_data["travelAdvisory"]:
                            peajes = ruta_data["travelAdvisory"]["tollInfo"].get("estimatedPrice", [])
                            for peaje in peajes:
                                if peaje.get("currencyCode") == "MXN":
                                    costo_auto = float(peaje.get("units", "0")) + (float(peaje.get("nanos", 0)) / 1e9)
                                    costo_peaje_pesado = costo_auto * mult_peaje
            except Exception as e:
                st.info("Calculando ruta avanzada...")

        km_final = st.number_input("KMS", value=float(distancia_real_km), key="km_input_main") 

        # --- LÓGICA DE CPK AUTOMÁTICO (7 NIVELES) ---
        cpk_base = 0.0
        if tipo_op in ["Importación", "Exportación"]:
            if km_final > 0:
                if km_final <= 199: cpk_base = 16.80
                elif km_final <= 249: cpk_base = 16.13
                elif km_final <= 349: cpk_base = 15.40
                elif km_final <= 400: cpk_base = 15.50
                elif km_final <= 799: cpk_base = 14.50
                elif km_final <= 1099: cpk_base = 13.50
                else: cpk_base = 12.56
                
                if tipo_equipo == "Caja Propia":
                    cpk_base += 1.50
        else:
            cpk_base = st.number_input("CPK Base Manual (Nacional) $", value=0.0)

        st.markdown("---")
        c_cpk, c_ipk = st.columns(2)
        with c_cpk:
            st.metric("Costo Por Kilómetro (CPK)", f"${cpk_base:.2f}")
            
        with c_ipk:
            # IPK sugerido con Markup 1.25
            if moneda_neg == "MXN (Pesos)":
                ipk_pactado = st.number_input("IPK Objetivo (MXN) $", value=cpk_base * 1.25 if cpk_base > 0 else 0.0)
                ipk_mxn_final = ipk_pactado
                moneda_tag = "MXN"
            else:
                ipk_pactado = st.number_input("IPK Objetivo (USD) $", value=(cpk_base * 1.25) / tc if cpk_base > 0 else 0.0)
                ipk_mxn_final = ipk_pactado * tc
                moneda_tag = "USD"

        # --- LÓGICA DE DIÉSEL (RENDIMIENTO + AJUSTE) ---
        rend_u = 2.7 if km_final <= 400 else 3.1
        ajuste_u = 0.0 if km_final <= 400 else 0.90
        factor_diesel_final = (precio_diesel / rend_u) + ajuste_u
        total_fsc_mxn = km_final * factor_diesel_final
        
        st.info(f"⛽ **Factor Diésel Aplicado:** ${factor_diesel_final:.2f} (Rend: {rend_u} | Ajuste: ${ajuste_u})")

    with col_extras:
        st.subheader("💰 Cargos Extra y Accesorios")
        with st.container(border=True):
            st.markdown("**Cargos Fijos de Ruta**")
            col_f1, col_f2 = st.columns(2)
            casetas = col_f1.number_input("Casetas ($)", value=float(costo_peaje_pesado))
            factor_cpac = col_f2.number_input("Factor CPAC ($/km)", 0.0, format="%.2f")
            
            total_cpac = km_final * factor_cpac
            
            st.markdown("---")
            st.markdown("**Accesorios**")
            acc_sel = st.multiselect("Selecciona accesorios:", list(precios_accesorios.keys()))
            total_acc_mxn = 0.0
            for a in acc_sel:
                total_acc_mxn += precios_accesorios[a]

            total_extras_mxn = casetas + total_cpac + total_acc_mxn

        flete_neto_mxn = km_final * ipk_mxn_final
        total_mxn_neto = flete_neto_mxn + total_extras_mxn + total_fsc_mxn

    # --- SISTEMA DE CARRITO (MULTIRUTA) ---
    st.markdown("---")
    if st.button("➕ Añadir este Tramo a la Propuesta", use_container_width=True, type="primary"):
        if orig and dest:
            st.session_state.propuesta_actual.append({
                "Origen": orig, "Destino": dest, "KM": km_final,
                "Flete": flete_neto_mxn, "FSC": total_fsc_mxn,
                "Casetas": casetas, "Otros": total_acc_mxn + total_cpac,
                "Total": total_mxn_neto, "Factor": factor_diesel_final
            })
            st.toast("Ruta añadida a la propuesta")
        else:
            st.error("Por favor completa Origen y Destino")

    # Mostrar la tabla de la propuesta si hay rutas
    if st.session_state.propuesta_actual:
        st.markdown("### 📋 Resumen de la Propuesta")
        df_prop = pd.DataFrame(st.session_state.propuesta_actual)
        
        # Conversión visual según moneda
        if moneda_neg == "USD (Dólares)":
            df_vis = df_prop.copy()
            for col in ["Flete", "FSC", "Casetas", "Otros", "Total"]:
                df_vis[col] = df_vis[col] / tc
            st.table(df_vis[["Origen", "Destino", "KM", "Flete", "FSC", "Casetas", "Otros", "Total"]].style.format("${:,.2f}"))
            total_global = df_prop["Total"].sum() / tc
            tag_pdf = "USD"
        else:
            st.table(df_prop[["Origen", "Destino", "KM", "Flete", "FSC", "Casetas", "Otros", "Total"]].style.format("${:,.2f}"))
            total_global = df_prop["Total"].sum()
            tag_pdf = "MXN"

        st.subheader(f"TOTAL GLOBAL: {total_global:,.2f} {tag_pdf}")

        # --- ACCIONES FINALES ---
        a1, a2, a3 = st.columns(3)
        
        with a1:
            if st.button("💾 Guardar en Historial"):
                for r in st.session_state.propuesta_actual:
                    reg = r.copy()
                    reg["Fecha"] = datetime.now().strftime("%d/%m %H:%M")
                    reg["Cliente"] = empresa_cliente
                    st.session_state.historial.insert(0, reg)
                st.success("Propuesta guardada")

        with a2:
            # PDF MULTIRUTA Y MONOMONEDA
            pdf = FPDF(orientation='L', unit='mm', format='A4')
            pdf.add_page()
            pdf.set_font("Arial", "B", 20)
            pdf.set_text_color(0, 51, 102) 
            pdf.cell(0, 10, empresa_remitente, ln=True)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 8, "PROPUESTA COMERCIAL", ln=True, align='R')
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 5, f"{lugar_expedicion}, {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='R')
            pdf.ln(5)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 6, f"Para: {empresa_cliente}", ln=True)
            pdf.cell(0, 6, f"Atención: {atencion_cliente}", ln=True)
            pdf.ln(5)

            # Tabla
            pdf.set_fill_color(0, 51, 102)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", "B", 8)
            pdf.cell(45, 8, "Origen", 1, 0, 'C', True)
            pdf.cell(45, 8, "Destino", 1, 0, 'C', True)
            pdf.cell(15, 8, "KM", 1, 0, 'C', True)
            pdf.cell(30, 8, "Flete", 1, 0, 'C', True)
            pdf.cell(30, 8, "FSC", 1, 0, 'C', True)
            pdf.cell(30, 8, "Casetas", 1, 0, 'C', True)
            pdf.cell(30, 8, "Otros", 1, 0, 'C', True)
            pdf.cell(35, 8, f"Total ({tag_pdf})", 1, 1, 'C', True)

            pdf.set_text_color(0,0,0)
            pdf.set_font("Arial", "", 8)
            f_conv = (1/tc) if tag_pdf == "USD" else 1
            for r in st.session_state.propuesta_actual:
                pdf.cell(45, 7, r["Origen"][:25], 1)
                pdf.cell(45, 7, r["Destino"][:25], 1)
                pdf.cell(15, 7, str(r["KM"]), 1, 0, 'C')
                pdf.cell(30, 7, f"${(r['Flete']*f_conv):,.2f}", 1, 0, 'R')
                pdf.cell(30, 7, f"${(r['FSC']*f_conv):,.2f}", 1, 0, 'R')
                pdf.cell(30, 7, f"${(r['Casetas']*f_conv):,.2f}", 1, 0, 'R')
                pdf.cell(30, 7, f"${(r['Otros']*f_conv):,.2f}", 1, 0, 'R')
                pdf.cell(35, 7, f"${(r['Total']*f_conv):,.2f}", 1, 1, 'R')
            
            pdf.ln(5)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 10, f"TOTAL PROPUESTA: ${total_global:,.2f} {tag_pdf}", ln=True, align='R')
            
            # Cláusulas legales recuperadas al 100%
            pdf.ln(5)
            pdf.set_font("Arial", "", 7)
            clausulas = ("- Máximo 22 toneladas. - Libre de maniobras de carga y descarga (3 hrs). "
                         "- Mercancía viaja por cuenta y riesgo del cliente. - 15 días de crédito. "
                         "- El FSC se actualiza según precios oficiales.")
            pdf.multi_cell(0, 4, clausulas)
            
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            st.download_button("📄 Descargar PDF", pdf_bytes, "Propuesta_HGT.pdf", "application/pdf")

        with a3:
            if st.button("🗑️ Limpiar Propuesta"):
                st.session_state.propuesta_actual = []
                st.rerun()

with tab_hist:
    st.subheader("📜 Auditoría de Rutas")
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
