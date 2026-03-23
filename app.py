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

# --- 2. BASE DE DATOS DE REFERENCIA ---
datos_ref = [
    ["EXPO", "MTY-AREA METRO", "NUEVO LAREDO", 230, 26.00, 34.67],
    ["EXPO", "SALTILLO - RAMOS", "NUEVO LAREDO", 310, 24.00, 32.00],
    ["EXPO", "DERRAMADERO", "NUEVO LAREDO", 380, 25.00, 33.33],
    ["IMPO", "NUEVO LAREDO", "MTY-AREA METRO", 230, 31.10, 41.46],
    ["IMPO", "NUEVO LAREDO", "SALTILLO - RAMOS", 310, 28.00, 37.33],
    ["IMPO", "NUEVO LAREDO", "DERRAMADERO", 380, 28.10, 37.47]
]
df_ref = pd.DataFrame(datos_ref, columns=["Tipo", "Origen", "Destino", "KM_Ref", "CPK_Base", "IPK_Ref"])

# --- 3. BARRA LATERAL (LÓGICA DE NEGOCIACIÓN) ---
with st.sidebar:
    st.header("👤 Datos de Cotización")
    empresa_remitente = st.text_input("Nuestra Empresa", "RL TRANSPORTACIONES")
    nombre_remitente = st.text_input("Nuestro Representante", "Gilberto Ochoa Sepúlveda")
    lugar_expedicion = st.text_input("Lugar de Expedición", "Pesquería N. L.")
    
    st.markdown("---")
    empresa_cliente = st.text_input("Para: (Empresa)", "Comercializadora México Americana")
    atencion_cliente = st.text_input("Atención: (Contacto)", "Iker Aldape Uribares")
    tipo_op = st.selectbox("Servicio", ["Importación", "Exportación", "Nacional"])
    tc = st.number_input("Tipo de Cambio (MXN/USD)", value=17.50, step=0.1)
    
    st.markdown("---")
    st.header("⛽ Combustible (FSC)")
    precio_diesel = st.number_input("Precio Diésel ($/L)", value=24.50, step=0.50)
    rendimiento = st.number_input("Rendimiento (km/L)", value=2.2, step=0.1)
    
    st.markdown("---")
    st.header("⚙️ Negociación y Ajustes")
    moneda_neg = st.radio("Cerrar trato en:", ["MXN (Pesos)", "USD (Dólares)"])
    
    st.caption("Ajuste de Casetas Automáticas (Auto vs Tracto)")
    mult_peaje = st.number_input("Multiplicador Carga Pesada (T3S2)", value=2.5, step=0.1)
    
    rutas_filtro = df_ref[df_ref["Tipo"] == ("EXPO" if tipo_op == "Exportación" else "IMPO")] if tipo_op in ["Exportación", "Importación"] else df_ref
    texto_manual = "Manual (Ruta Nueva)"
    
    if not rutas_filtro.empty:
        opciones = [texto_manual] + (rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]).tolist()
    else:
        opciones = [texto_manual]
        
    ruta_sel = st.selectbox("Ruta de Tabla:", opciones)
    
    cpk_init, km_init, orig_sug, dest_sug = 25.0, 1.0, "Nuevo Laredo, Tamps.", "Silao, Gto."

    if ruta_sel != texto_manual and not rutas_filtro.empty:
        d_r = rutas_filtro[(rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]) == ruta_sel].iloc[0]
        cpk_init, km_init = float(d_r["CPK_Base"]), float(d_r["KM_Ref"])
        orig_sug, dest_sug = d_r["Origen"], d_r["Destino"]

    cpk_base = st.number_input("CPK Base (MXN) $", value=cpk_init)
    
    with st.expander("🛠️ Costos Op. (CPAC/E1/E2)"):
        cpac = st.number_input("CPAC / Otros", 0.0)
        e1 = st.number_input("E1 (Variable)", 0.0)
        e2 = st.number_input("E2 (Variable)", 0.0)
    
    cpk_total_mxn = cpk_base + cpac + e1 + e2

    if moneda_neg == "MXN (Pesos)":
        ipk_pactado = st.number_input("IPK Objetivo Libre de Impuestos (MXN) $", value=cpk_total_mxn / 0.75)
        ipk_mxn_final = ipk_pactado
        moneda_tag = "MXN"
    else:
        ipk_pactado = st.number_input("IPK Objetivo Libre de Impuestos (USD) $", value=(cpk_total_mxn / 0.75) / tc)
        ipk_mxn_final = ipk_pactado * tc
        moneda_tag = "USD"

    margen_real = (1 - (cpk_total_mxn / ipk_mxn_final)) * 100 if ipk_mxn_final > 0 else 0
    
    telefono_wa = st.text_input("WhatsApp Cliente", "521")

# --- 4. ÁREA DE COTIZACIÓN (INTERFAZ MEJORADA) ---
tab_cot, tab_hist = st.tabs(["🎯 Cotizador Pro", "📜 Historial Completo"])

with tab_cot:
    st.markdown("## Resumen de Cotización (Operación Pura)")

    col_ruta, col_extras = st.columns([2, 1])

    with col_ruta:
        st.subheader("📍 Ruta y Extracción de Peajes")
        c1, c2 = st.columns(2)
        orig = c1.text_input("Origen", orig_sug)
        dest = c2.text_input("Destino", dest_sug)
        
        distancia_real_km = km_init
        costo_peaje_pesado = 0.0
        
        # --- CONEXIÓN A GOOGLE ROUTES API PARA CASETAS DINÁMICAS ---
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
                else:
                    res_basico = gmaps.directions(orig, dest)
                    if res_basico:
                        distancia_real_km = round(res_basico[0]['legs'][0]['distance']['value'] / 1000.0, 1)
                        
            except Exception as e:
                st.info("Calculando ruta avanzada...")

        km_final = st.number_input("KMS", value=float(distancia_real_km), key="km_input_main") 

        # --- CÁLCULO DINÁMICO DEL FSC (Basado en Opción A) ---
        total_fsc_mxn = (km_final / rendimiento) * precio_diesel if rendimiento > 0 else 0
        st.info(f"⛽ **FSC Proyectado:** {km_final} km ÷ {rendimiento} km/L x ${precio_diesel:,.2f} = **${total_fsc_mxn:,.2f} MXN**")

    with col_extras:
        st.subheader("💰 Cargos Extra y Accesorios")
        with st.container(border=True):
            st.markdown("**Cargos Fijos de Ruta**")
            col_f1, col_f2 = st.columns(2)
            
            casetas = col_f1.number_input("Casetas Grales. API ($)", value=float(costo_peaje_pesado))
            factor_cepac = col_f2.number_input("Factor CEPAC ($/km)", 0.0, format="%.2f")
            
            total_cepac = km_final * factor_cepac
            if total_cepac > 0:
                st.caption(f"Total CEPAC ({km_final} km x ${factor_cepac}): **${total_cepac:,.2f}**")
            
            st.markdown("---")
            st.markdown("**Listado de Accesorios Adicionales**")
            
            accesorios_seleccionados = st.multiselect(
                "Selecciona uno o más accesorios:", 
                list(precios_accesorios.keys())
            )
            
            total_accesorios_mxn = 0.0
            detalle_accesorios = {} 
            
            if accesorios_seleccionados:
                st.markdown("*Detalle de cobros:*")
                for acc in accesorios_seleccionados:
                    col_c1, col_c2 = st.columns(2)
                    cant = col_c1.number_input(f"Cant. ({acc})", min_value=1.0, value=1.0, step=1.0, key=f"cant_{acc}")
                    costo = col_c2.number_input(f"Costo ($) - {acc}", min_value=0.0, value=float(precios_accesorios[acc]), step=50.0, key=f"costo_{acc}")
                    
                    subtotal = cant * costo
                    total_accesorios_mxn += subtotal
                    
                    detalle_accesorios[acc] = {"cantidad": cant, "costo": costo, "subtotal": subtotal}
                    st.caption(f"Subtotal {acc}: **${subtotal:,.2f}**")

            total_extras_mxn = casetas + total_cepac + total_accesorios_mxn

        flete_neto_mxn = km_final * ipk_mxn_final
        # Sumamos el FSC al total a facturar
        total_mxn_neto = flete_neto_mxn + total_extras_mxn + total_fsc_mxn
        total_usd_neto = total_mxn_neto / tc

        with st.expander("📄 Ver Desglose Operativo (MXN)", expanded=False):
            st.write(f"Flete: **${flete_neto_mxn:,.2f}**")
            st.write(f"(+) FSC: **${total_fsc_mxn:,.2f}**")
            st.write(f"(+) Casetas: **${casetas:,.2f}**")
            if total_cepac > 0:
                st.write(f"(+) Total CEPAC: **${total_cepac:,.2f}**")
            for acc, datos in detalle_accesorios.items():
                st.write(f"(+) {acc}: **${datos['subtotal']:,.2f}**")
            st.write(f"**Total Cargos: ${(total_extras_mxn + total_fsc_mxn):,.2f}**")

    # --- FILA 2: METRICAS GRANDES (KPIs) ---
    st.markdown("---")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.metric(label="TOTAL A FACTURAR MXN", value=f"${total_mxn_neto:,.2f}")
    
    with kpi2:
        st.metric(label="TOTAL A FACTURAR USD", value=f"${total_usd_neto:,.2f}", delta=f"TC: {tc}")

    with kpi3:
        st.metric(label=f"IPK Pactado ({moneda_tag})", value=f"${ipk_pactado:.2f}")

    with kpi4:
        color_delta = "normal" 
        if margen_real < 0:
            color_delta = "inverse" 
            st.error(f"🚨🚨 ¡PÉRDIDA DETECTADA! ({margen_real:.1f}%) 🚨🚨")
        elif margen_real < 25:
            color_delta = "off" 
            st.warning(f"⚠️ Margen por debajo del objetivo (25%)")
        
        st.metric(
            label="Margen Real (Flete Puro)", 
            value=f"{margen_real:.1f}%", 
            delta=f"{margen_real - 25:.1f}% vs Obj (25%)",
            delta_color=color_delta
        )

    # --- FILA 3: ACCIONES ---
    st.markdown("---")
    st.subheader("🚀 Acciones")
    a1, a2, a3 = st.columns(3)

    # Formateo de fecha al estilo del PDF: "febrero 27, 2026"
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    fecha_hoy_dt = datetime.now()
    fecha_texto = f"{meses[fecha_hoy_dt.month - 1]} {fecha_hoy_dt.day}, {fecha_hoy_dt.year}"

    with a1:
        if st.button("💾 Guardar Historial", use_container_width=True, type="primary"):
            nombres_accesorios = ", ".join(detalle_accesorios.keys()) if detalle_accesorios else "Ninguno"
            
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Empresa": empresa_cliente,
                "Atención": atencion_cliente,
                "Ruta": f"{orig}-{dest}",
                "KMS": km_final,
                "Moneda": moneda_tag,
                "IPK Pactado": round(ipk_pactado, 2),
                "CPK Base": round(cpk_base, 2),
                "FSC": round(total_fsc_mxn, 2),
                "Casetas": round(casetas, 2),
                "Factor CEPAC": round(factor_cepac, 2),
                "Total CEPAC": round(total_cepac, 2),
                "Accesorios Incluidos": nombres_accesorios,
                "Total Accesorios": round(total_accesorios_mxn, 2),
                "TC": tc,
                "Total": round(total_mxn_neto, 2),
                "Margen Flete %": round(margen_real, 1)
            })
            st.toast(f"✅ Guardado con éxito en {moneda_tag}")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        
        # --- ENCABEZADO Y LOGO TEXTUAL ---
        pdf.set_font("Arial", "B", 20)
        pdf.set_text_color(0, 51, 102) # Azul oscuro para dar aspecto corporativo
        pdf.cell(0, 10, empresa_remitente, ln=True, align='L')
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, "COTIZACIÓN", ln=True, align='R')
        
        # --- FECHA Y LUGAR ---
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, f"{lugar_expedicion} {fecha_texto}", ln=True, align='R')
        pdf.ln(5)
        
        # --- DATOS DEL CLIENTE ---
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 5, f"Para. {empresa_cliente}", ln=True)
        pdf.cell(0, 5, f"Atención. {atencion_cliente}", ln=True)
        pdf.ln(5)
        
        # --- INTRODUCCIÓN ---
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 5, "Por medio de la presente cotización, informo a usted las tarifas que actualmente manejamos en las siguientes rutas y/o servicios:")
        pdf.ln(4)
        
        # --- TABLA EXACTA DEL FORMATO ---
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(220, 220, 220)
        # Anchos de columna que sumen ~190 (ancho de hoja)
        w_orig = 35; w_dest = 35; w_serv = 20; w_kms = 15; w_flete = 20; w_cas = 20; w_fsc = 20; w_tot = 25
        
        pdf.cell(w_orig, 8, "Origen", border=1, fill=True, align='C')
        pdf.cell(w_dest, 8, "Destino", border=1, fill=True, align='C')
        pdf.cell(w_serv, 8, "Servicio", border=1, fill=True, align='C')
        pdf.cell(w_kms, 8, "KMS", border=1, fill=True, align='C')
        pdf.cell(w_flete, 8, "Flete", border=1, fill=True, align='C')
        pdf.cell(w_cas, 8, "Casetas", border=1, fill=True, align='C')
        pdf.cell(w_fsc, 8, "FSC", border=1, fill=True, align='C')
        pdf.cell(w_tot, 8, "Total", border=1, fill=True, align='C')
        pdf.ln()
        
        pdf.set_font("Arial", "", 8)
        # Recorte de nombres para que entren en la celda
        pdf.cell(w_orig, 8, orig[:20], border=1, align='C')
        pdf.cell(w_dest, 8, dest[:20], border=1, align='C')
        pdf.cell(w_serv, 8, tipo_op, border=1, align='C')
        pdf.cell(w_kms, 8, str(km_final), border=1, align='C')
        pdf.cell(w_flete, 8, f"${flete_neto_mxn:,.2f}", border=1, align='C')
        pdf.cell(w_cas, 8, f"${casetas:,.2f}", border=1, align='C')
        pdf.cell(w_fsc, 8, f"${total_fsc_mxn:,.2f}", border=1, align='C')
        pdf.cell(w_tot, 8, f"${total_mxn_neto:,.2f}", border=1, align='C')
        pdf.ln(8)
        
        if total_cepac > 0 or detalle_accesorios:
            pdf.set_font("Arial", "B", 8)
            pdf.cell(0, 5, "Cargos Adicionales Cotizados:", ln=True)
            pdf.set_font("Arial", "", 8)
            if total_cepac > 0:
                pdf.cell(0, 5, f"  - CEPAC Operativo: ${total_cepac:,.2f}", ln=True)
            for acc, datos in detalle_accesorios.items():
                pdf.cell(0, 5, f"  - {acc} ({datos['cantidad']} mov): ${datos['subtotal']:,.2f}", ln=True)
            pdf.ln(2)

        # --- CLÁUSULAS (LETRAS CHIQUITAS EXACTAS) ---
        pdf.ln(3)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(0, 5, "Caja Regular", ln=True)
        pdf.cell(0, 5, "No materiales peligrosos", ln=True)
        pdf.ln(2)
        
        pdf.set_font("Arial", "", 8)
        clausulas_str = (
            "Propuesta vigente por 30 días para su aceptación, posteriormente será válida por 12 meses. Sujeto a disponibilidad de equipo.\n\n"
            "EL COSTO POR VARIACION DE DIESEL (FSC) SE ACTUALIZARÁ DE ACUERDO AL COMPORTAMIENTO DE LOS PRECIOS EN COMBUSTIBLES.\n\n"
            "Las tarifas presentadas, son calculadas de acuerdo con la asignación conjunta de los volúmenes por viajes domésticos, de importación o exportación.\n\n"
            "• Máximo 22 toneladas.\n"
            "• Libre de maniobras de carga y descarga.\n"
            "• La mercancía viaja asegurada por cuenta y riesgo del cliente.\n"
            "• El cliente es responsable por el cuidado de nuestros remolques (daños y robo) tanto con sus proveedores o clientes, como en sus instalaciones.\n"
            "• Paradas adicionales, dentro del recorrido natural de la ruta $2,610.00 MXN, en desviaciones, cargo por kilometraje recorrido.\n"
            "• Servicios cancelados, tienen costo de $2,610.00 MXN por movimiento en falso.\n"
            "• Sí no cuentan con sellos de seguridad y requieren que los provea H GT, el costo es de $130.00 MXN cada uno.\n"
            "• Máximo tres horas para maniobras de carga y tres para descarga, la hora adicional se factura a $435.00 MXN.\n"
            "• Cajas en plantas máximo tres días para salir cargadas o vacías, a partir del 4to. día, generan cargos por concepto de demoras $1,045.00 MXN por caja por día.\n"
            "• Cruces en fines de semana y/o días festivos tienen un costo del 30% adicional.\n"
            "• La variación se actualiza mensualmente.\n"
            "• Equipo de sujeción se cobra por aparte.\n"
            "• Términos de pago, 15 días de crédito.\n\n"
            "Para mejor servicio, por favor programe con anticipación sus requerimientos.\n"
            "Importes en Moneda Nacional antes de Impuestos. Sujeto a lo dispuesto en la Ley del Impuesto al Valor Agregado."
        )
        pdf.multi_cell(0, 4, clausulas_str)
        
        # --- CIERRE Y FIRMAS ---
        pdf.ln(5)
        pdf.cell(0, 5, "Esperando recibir su preferencia, quedo a sus órdenes.", ln=True)
        pdf.ln(8)
        
        # Firmas alineadas (Tú a la izquierda, Cliente a la derecha)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(95, 5, "Atentamente", align='C')
        pdf.cell(95, 5, "Acepto Tarifas y Condiciones", align='C', ln=True)
        pdf.ln(12)
        
        pdf.cell(95, 5, "___________________________________", align='C')
        pdf.cell(95, 5, "___________________________________", align='C', ln=True)
        
        pdf.set_font("Arial", "", 9)
        pdf.cell(95, 5, nombre_remitente, align='C')
        pdf.cell(95, 5, atencion_cliente, align='C', ln=True)
        pdf.cell(95, 5, empresa_remitente, align='C')
        pdf.cell(95, 5, empresa_cliente, align='C', ln=True)

        try:
            pdf_out = pdf.output(dest='S').encode('latin-1')
            st.download_button("📄 Descargar PDF", pdf_out, f"Cotizacion_{empresa_cliente}.pdf", "application/pdf", use_container_width=True)
        except:
            st.error("Error generando PDF (caracteres especiales)")

    with a3:
        # --- MENSAJE DE WHATSAPP CON FORMATO ---
        wa_text = f"*{empresa_remitente} - COTIZACIÓN*\n\n"
        wa_text += f"*Fecha:* {fecha_texto}\n"
        wa_text += f"*Para:* {empresa_cliente}\n"
        wa_text += f"*Atención:* {atencion_cliente}\n\n"
        wa_text += f"Por medio de la presente, informo las tarifas de servicio:\n\n"
        wa_text += f"📍 *Origen:* {orig}\n"
        wa_text += f"📍 *Destino:* {dest}\n"
        wa_text += f"🚛 *Servicio:* {tipo_op} | {km_final} KMS\n\n"
        wa_text += f"*-- DESGLOSE --*\n"
        wa_text += f"• *Flete:* ${flete_neto_mxn:,.2f}\n"
        wa_text += f"• *Casetas:* ${casetas:,.2f}\n"
        wa_text += f"• *FSC:* ${total_fsc_mxn:,.2f}\n"
        
        if total_cepac > 0:
            wa_text += f"• *CEPAC:* ${total_cepac:,.2f}\n"
            
        if detalle_accesorios:
            for acc, datos in detalle_accesorios.items():
                wa_text += f"• *{acc}:* ${datos['subtotal']:,.2f}\n"
                
        wa_text += f"\n💰 *TOTAL:* ${total_mxn_neto:,.2f} {moneda_tag} (Antes de IVA)\n\n"
        wa_text += f"⚠️ *Condiciones Principales:*\n"
        wa_text += f"- Vigencia 30 días.\n"
        wa_text += f"- FSC se actualiza al mercado.\n"
        wa_text += f"- Máx 22 Tons. Libre maniobras.\n"
        wa_text += f"- Crédito a 15 días.\n\n"
        wa_text += f"_{atencion_cliente}_\n_{empresa_cliente}_\n*Acepto Tarifas y Condiciones*"
            
        st.markdown(f'<a href="https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_text)}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 Enviar por WhatsApp</button></a>', unsafe_allow_html=True)

with tab_hist:
    st.subheader("📜 Auditoría Detallada")
    if st.session_state.historial:
        df_full = pd.DataFrame(st.session_state.historial)
        st.dataframe(df_full, use_container_width=True)
        csv = df_full.to_csv(index=False).encode('utf-8')
        st.download_button("📊 Exportar Historial (CSV)", csv, "historial_completo.csv", "text/csv")
    else:
        st.info("Aún no hay cotizaciones guardadas.")
