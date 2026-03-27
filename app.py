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
    
# --- NUEVO: INICIALIZAR MEMORIA MULTIRUTA ---
if 'rutas_propuesta' not in st.session_state:
    st.session_state.rutas_propuesta = []

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
    
    tc = st.number_input("Tipo de Cambio (MXN/USD)", value=17.50, step=0.1)
    
    st.markdown("---")
    st.header("⛽ Combustible (FSC)")
    precio_diesel = st.number_input("Precio Diésel ($/L)", value=24.50, step=0.50)
    
    # --- MOTOR DIÉSEL: ESPEJO VISUAL ---
    st.markdown("#### Factor Diésel de Referencia:")
    factor_espejo = (precio_diesel / 3.1) + 0.90
    st.subheader(f"${factor_espejo:.2f} / km")
    st.caption("Para rutas > 400km (Rend 3.1 + Ajuste $0.90)")
    
    st.markdown("---")
    st.header("⚙️ Negociación y Ajustes")
    moneda_neg = st.radio("Cerrar trato en:", ["MXN (Pesos)", "USD (Dólares)"])
    
    st.caption("Ajuste de Casetas Automáticas (Auto vs Tracto)")
    mult_peaje = st.number_input("Multiplicador Carga Pesada (T3S2)", value=2.5, step=0.1)
    
    telefono_wa = st.text_input("WhatsApp Cliente", "")

# --- 3. ÁREA DE COTIZACIÓN ---
tab_cot, tab_hist = st.tabs(["🎯 Cotizador Pro", "📜 Historial Completo"])

with tab_cot:
    st.markdown("## Resumen de Cotización (Operación Pura)")

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
                else:
                    res_basico = gmaps.directions(orig, dest)
                    if res_basico:
                        distancia_real_km = round(res_basico[0]['legs'][0]['distance']['value'] / 1000.0, 1)
                        
            except Exception as e:
                st.info("Calculando ruta avanzada...")

        km_final = st.number_input("KMS", value=float(distancia_real_km), key="km_input_main") 

        # --- LÓGICA DE CPK AUTOMÁTICO ACTUALIZADA ---
        cpk_base = 0.0
        if tipo_op in ["Importación", "Exportación"]:
            if km_final > 0:
                if km_final <= 199:
                    cpk_base = 16.80
                elif km_final <= 249:
                    cpk_base = 16.13
                elif km_final <= 349:
                    cpk_base = 15.40
                elif km_final <= 400:
                    cpk_base = 15.50
                elif km_final <= 799:
                    cpk_base = 14.50
                elif km_final <= 1099:
                    cpk_base = 13.50
                else:
                    cpk_base = 12.56
                
                # AJUSTE: El extra por caja propia ahora es $1.50
                if tipo_equipo == "Caja Propia":
                    cpk_base += 1.50
        else:
            cpk_base = st.number_input("CPK Base Manual (Nacional) $", value=0.0)

        if tipo_op in ["Importación", "Exportación"] and km_final > 0:
            st.success(f"⚙️ **CPK Automático Aplicado:** ${cpk_base:.2f} MXN ({tipo_equipo})")

        st.markdown("---")
        c_cpk, c_ipk = st.columns(2)
        with c_cpk:
            st.metric("Costo Por Kilómetro (CPK)", f"${cpk_base:.2f}")
            
        with c_ipk:
            if moneda_neg == "MXN (Pesos)":
                ipk_pactado = st.number_input("IPK Objetivo (MXN) $", value=cpk_base * 1.25 if cpk_base > 0 else 0.0)
                ipk_mxn_final = ipk_pactado
                moneda_tag = "MXN"
            else:
                ipk_pactado = st.number_input("IPK Objetivo (USD) $", value=(cpk_base * 1.25) / tc if cpk_base > 0 else 0.0)
                ipk_mxn_final = ipk_pactado * tc
                moneda_tag = "USD"

        margen_real = ((ipk_mxn_final - cpk_base) / cpk_base) * 100 if cpk_base > 0 else 0.0

        st.markdown("---")
        # --- LÓGICA DE MOTOR DIÉSEL ACORDADA ---
        if km_final <= 400:
            rendimiento_uso = 2.7
            ajuste_extra = 0.0
        else:
            rendimiento_uso = 3.1
            ajuste_extra = 0.90

        factor_calculado = (precio_diesel / rendimiento_uso) + ajuste_extra
        total_fsc_mxn = km_final * factor_calculado
        st.info(f"⛽ **FSC Proyectado:** Factor ${factor_calculado:.2f} (Rend: {rendimiento_uso} | Ajuste: ${ajuste_extra}) = **${total_fsc_mxn:,.2f} MXN**")

    with col_extras:
        st.subheader("💰 Cargos Extra y Accesorios")
        with st.container(border=True):
            st.markdown("**Cargos Fijos de Ruta**")
            col_f1, col_f2 = st.columns(2)
            
            casetas = col_f1.number_input("Casetas Grales. API ($)", value=float(costo_peaje_pesado))
            factor_cpac = col_f2.number_input("Factor CPAC ($/km)", 0.0, format="%.2f")
            
            total_cpac = km_final * factor_cpac
            if total_cpac > 0:
                st.caption(f"Total CPAC ({km_final} km x ${factor_cpac}): **${total_cpac:,.2f}**")
            
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

            total_extras_mxn = casetas + total_cpac + total_accesorios_mxn

        flete_neto_mxn = km_final * ipk_mxn_final
        total_mxn_neto = flete_neto_mxn + total_extras_mxn + total_fsc_mxn
        total_usd_neto = total_mxn_neto / tc

        with st.expander("📄 Ver Desglose Operativo (MXN)", expanded=False):
            st.write(f"Flete: **${flete_neto_mxn:,.2f}**")
            st.write(f"(+) FSC: **${total_fsc_mxn:,.2f}**")
            st.write(f"(+) Casetas: **${casetas:,.2f}**")
            if total_cpac > 0:
                st.write(f"(+) Total CPAC: **${total_cpac:,.2f}**")
            for acc, datos in detalle_accesorios.items():
                st.write(f"(+) {acc}: **${datos['subtotal']:,.2f}**")
            st.write(f"**Total Cargos: ${(total_extras_mxn + total_fsc_mxn):,.2f}**")

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
            label="Margen sobre Costo (Markup)", 
            value=f"{margen_real:.1f}%", 
            delta=f"{margen_real - 25:.1f}% vs Obj (25%)",
            delta_color=color_delta
        )

    # --- NUEVO: SISTEMA MULTIRUTA (CARRITO) ---
    st.markdown("---")
    col_btn_add, col_btn_clear = st.columns([3, 1])
    with col_btn_add:
        if st.button("➕ Añadir este Tramo a la Propuesta", use_container_width=True, type="primary"):
            if orig and dest:
                st.session_state.rutas_propuesta.append({
                    "Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final,
                    "Flete": flete_neto_mxn, "FSC": total_fsc_mxn, "Casetas": casetas, 
                    "Extras": total_extras_mxn - casetas, "Total MXN": total_mxn_neto, "Total USD": total_usd_neto
                })
                st.toast(f"✅ Tramo {orig} - {dest} añadido a la propuesta")
            else:
                st.warning("⚠️ Ingresa Origen y Destino para poder añadir el tramo.")
    with col_btn_clear:
        if st.button("🗑️ Limpiar Tramos", use_container_width=True):
            st.session_state.rutas_propuesta = []
            st.rerun()

    gran_total_mxn = total_mxn_neto
    gran_total_usd = total_usd_neto

    if st.session_state.rutas_propuesta:
        st.markdown("### 📋 Desglose de Propuesta Multiruta")
        df_prop = pd.DataFrame(st.session_state.rutas_propuesta)
        
        st.dataframe(
            df_prop[["Origen", "Destino", "Servicio", "KM", "Flete", "FSC", "Casetas", "Extras", "Total MXN"]].style.format({
                "Flete": "${:,.2f}", "FSC": "${:,.2f}", "Casetas": "${:,.2f}", 
                "Extras": "${:,.2f}", "Total MXN": "${:,.2f}"
            }),
            use_container_width=True
        )
        
        gran_total_mxn = df_prop["Total MXN"].sum()
        gran_total_usd = df_prop["Total USD"].sum()
        
        st.info(f"**GRAN TOTAL ACUMULADO:** **${gran_total_mxn:,.2f} MXN** | **${gran_total_usd:,.2f} USD**")

    st.markdown("---")
    st.subheader("🚀 Acciones")
    a1, a2, a3 = st.columns(3)

    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    fecha_hoy_dt = datetime.now()
    fecha_texto = f"{meses[fecha_hoy_dt.month - 1]} {fecha_hoy_dt.day}, {fecha_hoy_dt.year}"

    with a1:
        if st.button("💾 Guardar Historial", use_container_width=True, type="primary"):
            nombres_accesorios = ", ".join(detalle_accesorios.keys()) if detalle_accesorios else "Ninguno"
            
            rutas_a_guardar = st.session_state.rutas_propuesta if st.session_state.rutas_propuesta else [{
                "Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final,
                "Flete Neto": flete_neto_mxn, "FSC": total_fsc_mxn, "Casetas": casetas, 
                "Total Extras": total_extras_mxn, "Total MXN": total_mxn_neto, "Total USD": total_usd_neto
            }]

            for r in rutas_a_guardar:
                st.session_state.historial.insert(0, {
                    "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                    "Empresa": empresa_cliente,
                    "Atención": atencion_cliente,
                    "Servicio": r.get("Servicio", tipo_op),
                    "Tipo Equipo": tipo_equipo,
                    "Ruta": f"{r['Origen']}-{r['Destino']}",
                    "KMS": r["KM"],
                    "Moneda": moneda_tag,
                    "TC": tc,
                    "CPK Base": round(cpk_base, 2),
                    "IPK Pactado": round(ipk_pactado, 2),
                    "Flete Neto": round(r.get("Flete", r.get("Flete Neto", flete_neto_mxn)), 2),
                    "FSC": round(r["FSC"], 2),
                    "Casetas": round(r["Casetas"], 2),
                    "Total Extras": round(r.get("Extras", r.get("Total Extras", total_extras_mxn)), 2),
                    "Accesorios Incluidos": nombres_accesorios,
                    "Total MXN": round(r["Total MXN"], 2),
                    "Total USD": round(r["Total USD"], 2),
                    "Margen Markup %": round(margen_real, 1)
                })
            st.toast(f"✅ Guardado en Historial Completo")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        
        pdf.set_font("Arial", "B", 20)
        pdf.set_text_color(0, 51, 102) 
        pdf.cell(0, 10, empresa_remitente, ln=True, align='L')
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, "COTIZACIÓN", ln=True, align='R')
        
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, f"{lugar_expedicion} {fecha_texto}", ln=True, align='R')
        pdf.ln(5)
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 5, f"Para. {empresa_cliente}", ln=True)
        pdf.cell(0, 5, f"Atención. {atencion_cliente}", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 5, "Por medio de la presente cotización, informo a usted las tarifas que actualmente manejamos en las siguientes rutas y/o servicios:")
        pdf.ln(4)
        
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(220, 220, 220)
        w_orig = 35; w_dest = 35; w_serv = 20; w_kms = 15; w_flete = 20; w_cas = 20; w_fsc = 20; w_tot = 25
        
        pdf.cell(w_orig, 8, "Origen", border=1, fill=True, align='C')
        pdf.cell(w_dest, 8, "Destino", border=1, fill=True, align='C')
        pdf.cell(w_serv, 8, "Servicio", border=1, fill=True, align='C')
        pdf.cell(w_kms, 8, "KMS", border=1, fill=True, align='C')
        pdf.cell(w_flete, 8, "Flete", border=1, fill=True, align='C')
        pdf.cell(w_cas, 8, "Casetas", border=1, fill=True, align='C')
        pdf.cell(w_fsc, 8, "FSC", border=1, fill=True, align='C')
        pdf.cell(w_tot, 8, f"Total {moneda_tag}", border=1, fill=True, align='C')
        pdf.ln()
        
        pdf.set_font("Arial", "", 8)
        
        rutas_pdf = st.session_state.rutas_propuesta if st.session_state.rutas_propuesta else [{
            "Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final,
            "Flete": flete_neto_mxn, "Casetas": casetas, "FSC": total_fsc_mxn, "Total MXN": total_mxn_neto
        }]

        # --- CONVERSIÓN DE MONEDA PARA EL PDF ---
        f_conv = (1/tc) if moneda_neg == "USD (Dólares)" else 1

        for r in rutas_pdf:
            pdf.cell(w_orig, 8, r["Origen"][:20], border=1, align='C')
            pdf.cell(w_dest, 8, r["Destino"][:20], border=1, align='C')
            pdf.cell(w_serv, 8, r.get("Servicio", tipo_op)[:10], border=1, align='C')
            pdf.cell(w_kms, 8, str(r["KM"]), border=1, align='C')
            pdf.cell(w_flete, 8, f"${(r['Flete'] * f_conv):,.2f}", border=1, align='C')
            pdf.cell(w_cas, 8, f"${(r['Casetas'] * f_conv):,.2f}", border=1, align='C')
            pdf.cell(w_fsc, 8, f"${(r['FSC'] * f_conv):,.2f}", border=1, align='C')
            pdf.cell(w_tot, 8, f"${(r['Total MXN'] * f_conv):,.2f}", border=1, align='C')
            pdf.ln(8)
            
        if total_cpac > 0 or detalle_accesorios:
            pdf.ln(2)
            pdf.set_font("Arial", "B", 8)
            pdf.cell(0, 5, f"Cargos Adicionales Cotizados ({moneda_tag}):", ln=True)
            pdf.set_font("Arial", "", 8)
            if total_cpac > 0:
                pdf.cell(0, 5, f"  - CPAC Operativo: ${(total_cpac * f_conv):,.2f}", ln=True)
            for acc, datos in detalle_accesorios.items():
                pdf.cell(0, 5, f"  - {acc} ({datos['cantidad']} mov): ${(datos['subtotal'] * f_conv):,.2f}", ln=True)
            pdf.ln(2)

        pdf.ln(3)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(0, 5, "Caja Regular", ln=True)
        pdf.cell(0, 5, "No materiales peligrosos", ln=True)
        pdf.ln(2)
        
        pdf.set_font("Arial", "", 8)
        clausulas_str = (
            "Propuesta vigente por 30 dias para su aceptacion, posteriormente sera valida por 12 meses. Sujeto a disponibilidad de equipo.\n\n"
            "EL COSTO POR VARIACION DE DIESEL (FSC) SE ACTUALIZARA DE ACUERDO AL COMPORTAMIENTO DE LOS PRECIOS EN COMBUSTIBLES.\n\n"
            "Las tarifas presentadas, son calculadas de acuerdo con la asignacion conjunta de los volumenes por viajes domesticos, de importacion o exportacion.\n\n"
            "- Maximo 22 toneladas.\n"
            "- Libre de maniobras de carga y descarga.\n"
            "- La mercancia viaja asegurada por cuenta y riesgo del cliente.\n"
            "- El cliente es responsable por el cuidado de nuestros remolques (daños y robo) tanto con sus proveedores o clientes, como en sus instalaciones.\n"
            "- Paradas adicionales, dentro del recorrido natural de la ruta $2,610.00 MXN, en desviaciones, cargo por kilometraje recorrido.\n"
            "- Servicios cancelados, tienen costo de $2,610.00 MXN por movimiento en falso.\n"
            "- Si no cuentan con sellos de seguridad y requieren que los provea H GT, el costo es de $130.00 MXN cada uno.\n"
            "- Maximo tres horas para maniobras de carga y tres para descarga, la hora adicional se factura a $435.00 MXN.\n"
            "- Cajas en plantas maximo tres dias para salir cargadas o vacias, a partir del 4to. dia, generan cargos por concepto de demoras $1,045.00 MXN por caja por dia.\n"
            "- Cruces en fines de semana y/o dias festivos tienen un costo del 30% adicional.\n"
            "- La variacion se actualiza mensualmente.\n"
            "- Equipo de sujecion se cobra por aparte.\n"
            "- Terminos de pago, 15 dias de credito.\n\n"
            "Para mejor servicio, por favor programe con anticipacion sus requerimientos.\n"
            "Importes en Moneda Nacional antes de Impuestos. Sujeto a lo dispuesto en la Ley del Impuesto al Valor Agregado."
        )
        pdf.multi_cell(0, 4, clausulas_str)
        
        pdf.ln(5)
        pdf.cell(0, 5, "Esperando recibir su preferencia, quedo a sus ordenes.", ln=True)
        pdf.ln(8)
        
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
        except Exception as e:
            st.error(f"Error generando PDF: {e}")

    with a3:
        wa_text = f"*{empresa_remitente} - COTIZACIÓN*\n\n"
        wa_text += f"*Fecha:* {fecha_texto}\n"
        wa_text += f"*Para:* {empresa_cliente}\n"
        wa_text += f"*Atención:* {atencion_cliente}\n\n"
        
        rutas_wa = st.session_state.rutas_propuesta if st.session_state.rutas_propuesta else [{
            "Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final,
            "Flete": flete_neto_mxn, "Casetas": casetas, "FSC": total_fsc_mxn, "Total MXN": total_mxn_neto
        }]
        
        for idx, r in enumerate(rutas_wa, 1):
            if len(rutas_wa) > 1:
                wa_text += f"*{idx}. Tramo:* {r['Origen']} a {r['Destino']}\n"
            else:
                wa_text += f"📍 *Origen:* {r['Origen']}\n"
                wa_text += f"📍 *Destino:* {r['Destino']}\n"
            
            wa_text += f"🚛 *Servicio:* {r.get('Servicio', tipo_op)} | {r['KM']} KMS\n"
            wa_text += f"• *Flete:* ${r['Flete']:,.2f}\n"
            wa_text += f"• *Casetas:* ${r['Casetas']:,.2f}\n"
            wa_text += f"• *FSC:* ${r['FSC']:,.2f}\n"
            if len(rutas_wa) > 1:
                wa_text += f"Subtotal Tramo: ${r['Total MXN']:,.2f} MXN\n\n"
            else:
                wa_text += f"\n"
                
        if len(rutas_wa) > 1:
            wa_text += f"💰 *GRAN TOTAL:* ${gran_total_mxn:,.2f} MXN\n\n"
        else:
            wa_text += f"💰 *TOTAL:* ${gran_total_mxn:,.2f} {moneda_tag}\n\n"
            
        wa_text += f"_{atencion_cliente}_\n*Acepto Tarifas y Condiciones*"
            
        st.markdown(f'<a href="https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_text)}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 Enviar por WhatsApp</button></a>', unsafe_allow_html=True)

with tab_hist:
    st.subheader("📜 Auditoría Detallada")
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
    else:
        st.info("Aún no hay cotizaciones guardadas.")
