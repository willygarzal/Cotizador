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

# --- INICIALIZACIÓN DE VARIABLES EN MEMORIA (CEREBRO ABC) ---
if 'historial' not in st.session_state:
    st.session_state.historial = []
if 'rutas_propuesta' not in st.session_state:
    st.session_state.rutas_propuesta = []

default_params = {
    "w_llantas": 0.624, "w_mtto": 1.092, "w_admin": 4.16, "w_operador": 1.8928, "w_carga_soc": 35.0,
    "gasto_op_largo": 230.0, "gasto_op_corto": 88.0,
    "w_seguro": 5000.0, "w_gps_tracto": 1228.74, "w_gps_caja": 215.25, 
    "w_dep_tracto": 20628.08, "w_dep_caja": 2975.0,
    "km_mes_tracto_largo": 18500.0, "km_mes_tracto_corto": 13500.0,
    "km_mes_caja_largo": 8000.0, "km_mes_caja_corto": 1500.0
}
for k, v in default_params.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- DICCIONARIOS DE COSTOS ACCESORIOS ---
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

# --- 2. BARRA LATERAL (VISTA COMERCIAL LIMPIA) ---
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
    precio_diesel = st.number_input("Precio Diésel ($/L)", value=24.57, step=0.50)
    rendimiento_base = st.number_input("Rendimiento (km/L)", value=2.70, step=0.05)
    
    factor_calculado = precio_diesel / rendimiento_base if rendimiento_base > 0 else 0
    st.markdown("#### Factor Diésel Resultante:")
    st.subheader(f"${factor_calculado:.2f} / km")
    
    st.markdown("---")
    st.header("⚙️ Negociación y Ajustes")
    margen_objetivo = st.number_input("🎯 Margen Comercial Objetivo (%)", value=25.0, step=1.0)
    moneda_neg = st.radio("Cerrar trato en:", ["MXN (Pesos)", "USD (Dólares)"])
    telefono_wa = st.text_input("WhatsApp Cliente", "")

    # Multiplicador oculto para mantener limpia la interfaz comercial
    mult_peaje = 2.5

# --- 3. ÁREA PRINCIPAL CON 4 PESTAÑAS ---
tab_cot, tab_rx, tab_hist, tab_config = st.tabs(["🎯 Cotizador Pro", "📊 Rayos X (EBITDA)", "📜 Historial", "⚙️ Configuración ABC"])

# --- VARIABLES DEL CEREBRO ABC (CARGADAS DESDE MEMORIA) ---
w_llantas = st.session_state.w_llantas
w_mtto = st.session_state.w_mtto
w_admin = st.session_state.w_admin
w_operador = st.session_state.w_operador
w_carga_soc = st.session_state.w_carga_soc
w_seguro = st.session_state.w_seguro
w_gps_tracto = st.session_state.w_gps_tracto
w_gps_caja = st.session_state.w_gps_caja
w_dep_tracto = st.session_state.w_dep_tracto
w_dep_caja = st.session_state.w_dep_caja

# --- PESTAÑA 1: COTIZADOR ---
with tab_cot:
    st.markdown("## Resumen de Cotización")

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
                headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "routes.distanceMeters,routes.travelAdvisory.tollInfo"}
                payload = {"origin": {"address": orig}, "destination": {"address": dest}, "travelMode": "DRIVE", "extraComputations": ["TOLLS"]}
                resp = requests.post(routes_url, json=payload, headers=headers)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if "routes" in data and len(data["routes"]) > 0:
                        ruta_data = data["routes"][0]
                        if "distanceMeters" in ruta_data: distancia_real_km = round(ruta_data["distanceMeters"] / 1000.0, 1)
                        if "travelAdvisory" in ruta_data and "tollInfo" in ruta_data["travelAdvisory"]:
                            peajes = ruta_data["travelAdvisory"]["tollInfo"].get("estimatedPrice", [])
                            for peaje in peajes:
                                if peaje.get("currencyCode") == "MXN":
                                    costo_auto = float(peaje.get("units", "0")) + (float(peaje.get("nanos", 0)) / 1e9)
                                    costo_peaje_pesado = costo_auto * mult_peaje
                else:
                    res_basico = gmaps.directions(orig, dest)
                    if res_basico: distancia_real_km = round(res_basico[0]['legs'][0]['distance']['value'] / 1000.0, 1)
                
                # --- INYECCIÓN AUTOMÁTICA DEL KILOMETRAJE ---
                st.session_state.km_input_main = float(distancia_real_km)

            except Exception as e:
                st.info("Calculando ruta avanzada...")

        km_final = st.number_input("KMS", value=float(distancia_real_km), key="km_input_main") 

        # --- MOTOR FINANCIERO: SEPARACIÓN EXACTA DE TRACTO Y CAJA ---
        cpk_piso_flete = 0.0
        costo_operador = 0.0
        costo_llantas_mtto = 0.0
        costo_admin_viaje = 0.0
        
        if km_final > 0:
            es_largo = km_final > 400
            
            w_km_mes_tracto = st.session_state.km_mes_tracto_largo if es_largo else st.session_state.km_mes_tracto_corto
            w_km_mes_caja = st.session_state.km_mes_caja_largo if es_largo else st.session_state.km_mes_caja_corto
            gasto_op_viaje = st.session_state.gasto_op_largo if es_largo else st.session_state.gasto_op_corto
            
            costo_operador = (km_final * w_operador * (1 + (w_carga_soc/100))) + gasto_op_viaje
            costo_llantas_mtto = km_final * (w_llantas + w_mtto)
            costo_admin_viaje = km_final * w_admin
            
            costo_fijo_tracto_km = (w_seguro + w_gps_tracto + w_dep_tracto) / w_km_mes_tracto if w_km_mes_tracto > 0 else 0
            costo_fijo_tracto_viaje = km_final * costo_fijo_tracto_km
            
            if tipo_equipo == "Caja Propia":
                costo_fijo_caja_km = (w_gps_caja + w_dep_caja) / w_km_mes_caja if w_km_mes_caja > 0 else 0
                costo_fijo_caja_viaje = km_final * costo_fijo_caja_km
            else:
                costo_fijo_caja_viaje = 0.0
                
            costo_piso_total = costo_operador + costo_llantas_mtto + costo_admin_viaje + costo_fijo_tracto_viaje + costo_fijo_caja_viaje
            cpk_piso_flete = costo_piso_total / km_final
            
            st.success(f"⚖️ **Costo Operativo Base:** ${cpk_piso_flete:.2f} MXN por km | Modalidad: {tipo_equipo}")

        st.markdown("---")
        c_cpk, c_ipk = st.columns(2)
        with c_cpk:
            ipk_sugerido_mxn = cpk_piso_flete * (1 + (margen_objetivo / 100)) if km_final > 0 else 0.0
            st.metric(f"Tarifa Sugerida (Margen {margen_objetivo}%)", f"${ipk_sugerido_mxn:.2f}")
            
        with c_ipk:
            if moneda_neg == "MXN (Pesos)":
                ipk_pactado = st.number_input("IPK a Facturar (MXN) $", value=float(ipk_sugerido_mxn))
                ipk_mxn_final = ipk_pactado
                moneda_tag = "MXN"
            else:
                ipk_pactado = st.number_input("IPK a Facturar (USD) $", value=float(ipk_sugerido_mxn / tc) if tc > 0 else 0.0)
                ipk_mxn_final = ipk_pactado * tc
                moneda_tag = "USD"

        margen_real = ((ipk_mxn_final - cpk_piso_flete) / cpk_piso_flete) * 100 if cpk_piso_flete > 0 else 0.0

        st.markdown("---")
        total_fsc_mxn = km_final * factor_calculado
        st.info(f"⛽ **FSC Proyectado:** Factor ${factor_calculado:.2f} (Rend. Base: {rendimiento_base}) = **${total_fsc_mxn:,.2f} MXN**")

    with col_extras:
        st.subheader("💰 Cargos Extra y Accesorios")
        with st.container(border=True):
            st.markdown("**Cargos Fijos de Ruta**")
            col_f1, col_f2 = st.columns(2)
            casetas = col_f1.number_input("Casetas Grales. API ($)", value=float(costo_peaje_pesado))
            factor_ajuste_comb = col_f2.number_input("Ajuste Combustible ($/km)", 0.0, format="%.2f")
            total_ajuste_comb = km_final * factor_ajuste_comb
            
            if total_ajuste_comb > 0: st.caption(f"Total Ajuste Combustible: **${total_ajuste_comb:,.2f}**")
            
            st.markdown("---")
            st.markdown("**Listado de Accesorios Adicionales**")
            accesorios_seleccionados = st.multiselect("Selecciona uno o más accesorios:", list(precios_accesorios.keys()))
            
            total_accesorios_mxn = 0.0
            detalle_accesorios = {} 
            if accesorios_seleccionados:
                for acc in accesorios_seleccionados:
                    col_c1, col_c2 = st.columns(2)
                    cant = col_c1.number_input(f"Cant. ({acc})", min_value=1.0, value=1.0, step=1.0, key=f"cant_{acc}")
                    costo = col_c2.number_input(f"Costo ($) - {acc}", min_value=0.0, value=float(precios_accesorios[acc]), step=50.0, key=f"costo_{acc}")
                    subtotal = cant * costo
                    total_accesorios_mxn += subtotal
                    detalle_accesorios[acc] = {"cantidad": cant, "costo": costo, "subtotal": subtotal}

            total_extras_mxn = casetas + total_ajuste_comb + total_accesorios_mxn

        flete_neto_mxn = km_final * ipk_mxn_final
        total_mxn_neto = flete_neto_mxn + total_extras_mxn + total_fsc_mxn
        total_usd_neto = total_mxn_neto / tc

    st.markdown("---")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1: st.metric(label="TOTAL A FACTURAR MXN", value=f"${total_mxn_neto:,.2f}")
    with kpi2: st.metric(label="TOTAL A FACTURAR USD", value=f"${total_usd_neto:,.2f}", delta=f"TC: {tc}")
    with kpi3: st.metric(label=f"IPK Facturado ({moneda_tag})", value=f"${ipk_pactado:.2f}")
    with kpi4:
        color_delta = "normal" if margen_real >= margen_objetivo else ("off" if margen_real >= 0 else "inverse")
        if margen_real < 0: st.error("🚨 ¡PÉRDIDA DETECTADA! Tarifa por debajo del costo.")
        st.metric(label="Margen Comercial Real", value=f"{margen_real:.1f}%", delta=f"{margen_real - margen_objetivo:.1f}% vs Obj.", delta_color=color_delta)

    # --- VARIABLES GLOBALES DE RENTABILIDAD PARA ESTA RUTA ---
    w_km_mes_tracto_calc = st.session_state.km_mes_tracto_largo if km_final > 400 else st.session_state.km_mes_tracto_corto
    w_km_mes_caja_calc = st.session_state.km_mes_caja_largo if km_final > 400 else st.session_state.km_mes_caja_corto
    w_km_mes_tracto_calc = w_km_mes_tracto_calc if w_km_mes_tracto_calc > 0 else 1
    w_km_mes_caja_calc = w_km_mes_caja_calc if w_km_mes_caja_calc > 0 else 1

    costo_seg_gps_viaje = km_final * ((w_seguro + w_gps_tracto) / w_km_mes_tracto_calc) + (km_final * (w_gps_caja / w_km_mes_caja_calc) if tipo_equipo == "Caja Propia" else 0) if km_final > 0 else 0
    costo_deprec_viaje = km_final * (w_dep_tracto / w_km_mes_tracto_calc) + (km_final * (w_dep_caja / w_km_mes_caja_calc) if tipo_equipo == "Caja Propia" else 0) if km_final > 0 else 0
    
    ebitda_viaje_actual = total_mxn_neto - total_fsc_mxn - casetas - total_accesorios_mxn - costo_operador - costo_llantas_mtto - costo_admin_viaje - costo_seg_gps_viaje
    utilidad_neta_viaje_actual = ebitda_viaje_actual - costo_deprec_viaje

    # --- SISTEMA MULTIRUTA (CARRITO) ---
    st.markdown("---")
    col_btn_add, col_btn_clear = st.columns([3, 1])
    with col_btn_add:
        if st.button("➕ Añadir este Tramo a la Propuesta", use_container_width=True, type="primary"):
            if orig and dest:
                st.session_state.rutas_propuesta.append({
                    "Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final,
                    "Flete": flete_neto_mxn, "FSC": total_fsc_mxn, "Casetas": casetas, 
                    "Extras": total_extras_mxn - casetas, "Total MXN": total_mxn_neto, "Total USD": total_usd_neto,
                    "Costo_Directo": cpk_piso_flete * km_final, "Operador": costo_operador if km_final > 0 else 0,
                    "LlantasMtto": costo_llantas_mtto if km_final > 0 else 0, "Admin": costo_admin_viaje if km_final > 0 else 0,
                    "Ajuste_Comb": total_ajuste_comb, "Accesorios": total_accesorios_mxn,
                    "EBITDA": ebitda_viaje_actual, "Utilidad_Neta": utilidad_neta_viaje_actual
                })
                st.toast(f"✅ Tramo añadido a la propuesta")
    with col_btn_clear:
        if st.button("🗑️ Limpiar Tramos", use_container_width=True):
            st.session_state.rutas_propuesta = []
            st.rerun()

    gran_total_mxn = total_mxn_neto
    if st.session_state.rutas_propuesta:
        df_prop = pd.DataFrame(st.session_state.rutas_propuesta)
        st.dataframe(df_prop[["Origen", "Destino", "KM", "Flete", "FSC", "Casetas", "Extras", "Total MXN"]].style.format("${:,.2f}", subset=["Flete", "FSC", "Casetas", "Extras", "Total MXN"]), use_container_width=True)
        gran_total_mxn = df_prop["Total MXN"].sum()

    st.markdown("---")
    st.subheader("🚀 Acciones")
    a1, a2, a3 = st.columns(3)
    fecha_texto = f"{['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'][datetime.now().month - 1]} {datetime.now().day}, {datetime.now().year}"

    with a1:
        if st.button("💾 Guardar Historial", use_container_width=True, type="primary"):
            nombres_accesorios = ", ".join(detalle_accesorios.keys()) if detalle_accesorios else "Ninguno"
            rutas_a_guardar = st.session_state.rutas_propuesta if st.session_state.rutas_propuesta else [{
                "Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final,
                "Flete Neto": flete_neto_mxn, "FSC": total_fsc_mxn, "Casetas": casetas, 
                "Ajuste_Comb": total_ajuste_comb, "Accesorios_Monto": total_accesorios_mxn,
                "Total MXN": total_mxn_neto, "Total USD": total_usd_neto,
                "Costo_Directo": cpk_piso_flete * km_final, "Operador": costo_operador if km_final > 0 else 0,
                "LlantasMtto": costo_llantas_mtto if km_final > 0 else 0, "Admin": costo_admin_viaje if km_final > 0 else 0,
                "EBITDA": ebitda_viaje_actual, "Utilidad_Neta": utilidad_neta_viaje_actual
            }]
            for r in rutas_a_guardar:
                moneda_ruta = r.get("Moneda", moneda_tag)
                f_conv = (1/tc) if moneda_ruta == "USD (Dólares)" else 1
                ingreso_total_mxn = r.get("Total MXN", total_mxn_neto)
                utilidad_neta_mxn = r.get("Utilidad_Neta", 0)
                margen_neto_pct = (utilidad_neta_mxn / ingreso_total_mxn) * 100 if ingreso_total_mxn > 0 else 0
                
                st.session_state.historial.insert(0, {
                    "Fecha": datetime.now().strftime("%d/%m %H:%M"), "Empresa Cliente": empresa_cliente, "Contacto Cliente": atencion_cliente,
                    "Ruta": f"{r['Origen']}-{r['Destino']}", "KMS": r["KM"], "Servicio": r.get("Servicio", tipo_op), "Equipo": tipo_equipo,
                    "Moneda": moneda_ruta, "TC": tc, 
                    "Flete Cotizado": round(r.get("Flete", r.get("Flete Neto", flete_neto_mxn)) * f_conv, 2),
                    "FSC Cotizado": round(r["FSC"] * f_conv, 2), "Casetas Cotizadas": round(r["Casetas"] * f_conv, 2), 
                    "Ajuste Combustible": round(r.get("Ajuste_Comb", total_ajuste_comb) * f_conv, 2),
                    "Accesorios": nombres_accesorios, "Monto Accs": round(r.get("Accesorios_Monto", r.get("Accesorios", total_accesorios_mxn)) * f_conv, 2),
                    "Total MXN": round(ingreso_total_mxn, 2), "Total USD": round(r.get("Total USD", total_usd_neto), 2), 
                    "Costo Piso Fijo (MXN)": round(r.get("Costo_Directo", cpk_piso_flete * km_final), 2),
                    "Costo Operador (MXN)": round(r.get("Operador", costo_operador), 2),
                    "Costo Llantas/Mtto (MXN)": round(r.get("LlantasMtto", costo_llantas_mtto), 2),
                    "Costo Admin (MXN)": round(r.get("Admin", costo_admin_viaje), 2),
                    "Margen Comercial %": round(margen_real, 1),
                    "EBITDA": round(r.get("EBITDA", 0) * f_conv, 2),
                    "Utilidad Neta": round(utilidad_neta_mxn * f_conv, 2),
                    "% Utilidad Neta": round(margen_neto_pct, 1)
                })
            st.toast("✅ Sábana Financiera Guardada en Historial")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 20); pdf.set_text_color(0, 51, 102); pdf.cell(0, 10, empresa_remitente, ln=True, align='L')
        pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", "B", 14); pdf.cell(0, 8, "COTIZACIÓN", ln=True, align='R')
        pdf.set_font("Arial", "", 10); pdf.cell(0, 5, f"{lugar_expedicion} {fecha_texto}", ln=True, align='R'); pdf.ln(5)
        pdf.set_font("Arial", "B", 10); pdf.cell(0, 5, f"Para. {empresa_cliente}", ln=True); pdf.cell(0, 5, f"Atención. {atencion_cliente}", ln=True); pdf.ln(5)
        pdf.set_font("Arial", "", 10); pdf.multi_cell(0, 5, "Por medio de la presente cotización, informo a usted las tarifas que actualmente manejamos en las siguientes rutas y/o servicios:"); pdf.ln(4)
        
        pdf.set_font("Arial", "B", 8); pdf.set_fill_color(220, 220, 220)
        w_pdf = [35, 35, 20, 15, 20, 20, 20, 25]
        for h in ["Origen", "Destino", "Servicio", "KMS", "Flete", "Casetas", "FSC", f"Total {moneda_tag}"]: pdf.cell(w_pdf[["Origen", "Destino", "Servicio", "KMS", "Flete", "Casetas", "FSC", f"Total {moneda_tag}"].index(h)], 8, h, 1, 0, 'C', True)
        pdf.ln()
        
        pdf.set_font("Arial", "", 8)
        rutas_pdf = st.session_state.rutas_propuesta if st.session_state.rutas_propuesta else [{"Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final, "Flete": flete_neto_mxn, "Casetas": casetas, "FSC": total_fsc_mxn, "Total MXN": total_mxn_neto}]
        f_conv = (1/tc) if moneda_neg == "USD (Dólares)" else 1

        for r in rutas_pdf:
            pdf.cell(35, 8, r["Origen"][:20], 1, 0, 'C'); pdf.cell(35, 8, r["Destino"][:20], 1, 0, 'C')
            pdf.cell(20, 8, r.get("Servicio", tipo_op)[:10], 1, 0, 'C'); pdf.cell(15, 8, str(r["KM"]), 1, 0, 'C')
            pdf.cell(20, 8, f"${(r['Flete'] * f_conv):,.2f}", 1, 0, 'C'); pdf.cell(20, 8, f"${(r['Casetas'] * f_conv):,.2f}", 1, 0, 'C')
            pdf.cell(20, 8, f"${(r['FSC'] * f_conv):,.2f}", 1, 0, 'C'); pdf.cell(25, 8, f"${(r['Total MXN'] * f_conv):,.2f}", 1, 1, 'C')
            
        if total_ajuste_comb > 0 or detalle_accesorios:
            pdf.ln(2); pdf.set_font("Arial", "B", 8); pdf.cell(0, 5, f"Cargos Adicionales ({moneda_tag}):", ln=True); pdf.set_font("Arial", "", 8)
            if total_ajuste_comb > 0: pdf.cell(0, 5, f"  - Ajuste de Combustible: ${(total_ajuste_comb * f_conv):,.2f}", ln=True)
            for acc, datos in detalle_accesorios.items(): pdf.cell(0, 5, f"  - {acc} ({datos['cantidad']} mov): ${(datos['subtotal'] * f_conv):,.2f}", ln=True)
        
        pdf.ln(3); pdf.set_font("Arial", "B", 9); pdf.cell(0, 5, "Caja Regular", ln=True); pdf.cell(0, 5, "No materiales peligrosos", ln=True); pdf.ln(2)
        pdf.set_font("Arial", "", 8)
        clausulas_str = (
            "Propuesta vigente por 30 dias para su aceptacion, posteriormente sera valida por 12 meses. Sujeto a disponibilidad de equipo.\n\n"
            "EL COSTO POR VARIACION DE DIESEL (FSC) SE ACTUALIZARA DE ACUERDO AL COMPORTAMIENTO DE LOS PRECIOS EN COMBUSTIBLES.\n\n"
            "Las tarifas presentadas, son calculadas de acuerdo con la asignacion conjunta de los volumenes por viajes domesticos, de importacion o exportacion.\n\n"
            "- Maximo 22 toneladas.\n- Libre de maniobras de carga y descarga.\n- La mercancia viaja asegurada por cuenta y riesgo del cliente.\n"
            "- El cliente es responsable por el cuidado de nuestros remolques (daños y robo) tanto con sus proveedores o clientes, como en sus instalaciones.\n"
            "- Paradas adicionales, dentro del recorrido natural de la ruta $2,610.00 MXN, en desviaciones, cargo por kilometraje recorrido.\n"
            "- Servicios cancelados, tienen costo de $2,610.00 MXN por movimiento en falso.\n"
            "- Si no cuentan con sellos de seguridad y requieren que los provea H GT, el costo es de $130.00 MXN cada uno.\n"
            "- Maximo tres horas para maniobras de carga y tres para descarga, la hora adicional se factura a $435.00 MXN.\n"
            "- Cajas en plantas maximo tres dias para salir cargadas o vacias, a partir del 4to. dia, generan cargos por concepto de demoras $1,045.00 MXN por caja por dia.\n"
            "- Cruces en fines de semana y/o dias festivos tienen un costo del 30% adicional.\n"
            "- La variacion se actualiza mensualmente.\n- Equipo de sujecion se cobra por aparte.\n- Terminos de pago, 15 dias de credito.\n\n"
            "Para mejor servicio, por favor programe con anticipacion sus requerimientos.\nImportes en Moneda Nacional antes de Impuestos. Sujeto a lo dispuesto en la Ley del Impuesto al Valor Agregado."
        )
        pdf.multi_cell(0, 4, clausulas_str); pdf.ln(5); pdf.cell(0, 5, "Esperando recibir su preferencia, quedo a sus ordenes.", ln=True); pdf.ln(8)
        pdf.set_font("Arial", "B", 9); pdf.cell(95, 5, "Atentamente", align='C'); pdf.cell(95, 5, "Acepto Tarifas y Condiciones", align='C', ln=True); pdf.ln(12)
        pdf.cell(95, 5, "___________________________________", align='C'); pdf.cell(95, 5, "___________________________________", align='C', ln=True)
        pdf.set_font("Arial", "", 9); pdf.cell(95, 5, nombre_remitente, align='C'); pdf.cell(95, 5, atencion_cliente, align='C', ln=True)
        pdf.cell(95, 5, empresa_remitente, align='C'); pdf.cell(95, 5, empresa_cliente, align='C', ln=True)

        try: st.download_button("📄 Descargar PDF", pdf.output(dest='S').encode('latin-1'), f"Cotizacion_{empresa_cliente}.pdf", "application/pdf", use_container_width=True)
        except Exception as e: pass

    with a3:
        wa_text = f"*{empresa_remitente} - COTIZACIÓN*\n\n*Fecha:* {fecha_texto}\n*Para:* {empresa_cliente}\n\n"
        rutas_wa = st.session_state.rutas_propuesta if st.session_state.rutas_propuesta else [{"Origen": orig, "Destino": dest, "KM": km_final, "Total MXN": total_mxn_neto}]
        for r in rutas_wa: wa_text += f"📍 {r['Origen']} a {r['Destino']} ({r['KM']} KMS)\n"
        if total_ajuste_comb > 0: wa_text += f"• *Ajuste de Combustible:* ${total_ajuste_comb:,.2f}\n"
        wa_text += f"\n💰 *TOTAL:* ${gran_total_mxn:,.2f} {moneda_tag}\n\n*Acepto Tarifas y Condiciones*"
        st.markdown(f'<a href="https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_text)}" target="_blank"><button style="background-color:#25D366; color:white; width:100%; padding:10px; border-radius:5px; border:none; font-weight:bold;">📲 WhatsApp</button></a>', unsafe_allow_html=True)

# --- PESTAÑA 2: TABLERO FINANCIERO DIRECTIVO ---
with tab_rx:
    st.markdown("## 📊 Radiografía Financiera (Directivo)")
    if km_final > 0:
        st.info("Este tablero evalúa la rentabilidad del tramo que tienes configurado actualmente en la Pestaña 1.")
        
        margen_ebitda = (ebitda_viaje_actual / total_mxn_neto) * 100 if total_mxn_neto > 0 else 0
        margen_neto = (utilidad_neta_viaje_actual / total_mxn_neto) * 100 if total_mxn_neto > 0 else 0

        k1, k2, k3 = st.columns(3)
        k1.metric("Ingreso Total (Venta)", f"${total_mxn_neto:,.2f}")
        k2.metric("EBITDA (Flujo)", f"${ebitda_viaje_actual:,.2f}", f"{margen_ebitda:.1f}% Margen", delta_color="normal" if ebitda_viaje_actual>0 else "inverse")
        k3.metric("Utilidad Neta del Viaje", f"${utilidad_neta_viaje_actual:,.2f}", f"{margen_neto:.1f}% Margen", delta_color="normal" if utilidad_neta_viaje_actual>0 else "inverse")

        with st.expander("🔍 Desglose de Egresos", expanded=True):
            st.write(f"- **Diésel y Peajes (Paso directo):** ${(total_fsc_mxn + casetas):,.2f}")
            st.write(f"- **Sueldo, Carga Social y Op. Fijo:** ${costo_operador:,.2f}")
            st.write(f"- **Llantas y Mantenimiento:** ${costo_llantas_mtto:,.2f}")
            st.write(f"- **Gasto Administrativo Asignado:** ${costo_admin_viaje:,.2f}")
            st.write(f"- **Seguros y Satélite Prorrateado:** ${costo_seg_gps_viaje:,.2f}")
            st.write(f"- **Depreciación Fierros Prorrateada:** ${costo_deprec_viaje:,.2f}")
    else:
        st.warning("⚠️ Ingresa los KMS en el Cotizador para ver el análisis de rentabilidad.")

# --- PESTAÑA 3: HISTORIAL Y AUDITORÍA ---
with tab_hist:
    st.markdown("## 📜 Sábana Financiera de Auditoría")
    if st.session_state.historial: 
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
    else:
        st.info("Aún no hay cotizaciones guardadas. Cuando guardes una, aparecerá aquí con el desglose de todos los costos.")

# --- PESTAÑA 4: CONFIGURACIÓN ABC (EL CUARTO DE MÁQUINAS) ---
with tab_config:
    st.markdown("## ⚙️ Configuración de Costeo Operativo ")
    st.info("Estos parámetros controlan el 'Cerebro Financiero' del cotizador. Las modificaciones se aplican en tiempo real.")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.subheader("1. Gastos Variables y Administrativos")
        st.session_state.w_llantas = st.number_input("Llantas ($/km)", value=st.session_state.w_llantas, step=0.01)
        st.session_state.w_mtto = st.number_input("Mantenimiento Motriz ($/km)", value=st.session_state.w_mtto, step=0.01)
        st.session_state.w_operador = st.number_input("Sueldo Operador Base ($/km)", value=st.session_state.w_operador, step=0.01)
        st.session_state.w_carga_soc = st.number_input("Carga Social (%)", value=st.session_state.w_carga_soc, step=1.0)
        st.session_state.w_admin = st.number_input("Gasto Administrativo Asignado ($/km)", value=st.session_state.w_admin, step=0.01)
        
        st.markdown("---")
        st.subheader("2. Gastos Operativos ")
        st.session_state.gasto_op_largo = st.number_input("Gasto Op. Ruta Larga (>400km) ($)", value=st.session_state.gasto_op_largo, step=10.0)
        st.session_state.gasto_op_corto = st.number_input("Gasto Op. Tramo Corto (<=400km) ($)", value=st.session_state.gasto_op_corto, step=10.0)
        
    with col_c2:
        st.subheader("3. Costos Fijos Mensuales (Capex y Seguros)")
        st.session_state.w_seguro = st.number_input("Seguro Tractor ($/mes)", value=st.session_state.w_seguro, step=100.0)
        st.session_state.w_gps_tracto = st.number_input("GPS Tractor ($/mes)", value=st.session_state.w_gps_tracto, step=10.0)
        st.session_state.w_gps_caja = st.number_input("GPS Caja ($/mes)", value=st.session_state.w_gps_caja, step=10.0)
        st.session_state.w_dep_tracto = st.number_input("Depreciación Tractor ($/mes)", value=st.session_state.w_dep_tracto, step=100.0)
        st.session_state.w_dep_caja = st.number_input("Depreciación Caja ($/mes)", value=st.session_state.w_dep_caja, step=10.0)
        
        st.markdown("---")
        st.subheader("4. Metas de Kilometraje Mensual ")
        c_km1, c_km2 = st.columns(2)
        with c_km1:
            st.markdown("**Tractor**")
            st.session_state.km_mes_tracto_largo = st.number_input("KM Ruta Larga (Tracto)", value=st.session_state.km_mes_tracto_largo, step=500.0)
            st.session_state.km_mes_tracto_corto = st.number_input("KM Tramo Corto (Tracto)", value=st.session_state.km_mes_tracto_corto, step=500.0)
        with c_km2:
            st.markdown("**Caja**")
            st.session_state.km_mes_caja_largo = st.number_input("KM Ruta Larga (Caja)", value=st.session_state.km_mes_caja_largo, step=500.0)
            st.session_state.km_mes_caja_corto = st.number_input("KM Tramo Corto (Caja)", value=st.session_state.km_mes_caja_corto, step=500.0)
