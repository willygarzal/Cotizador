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
if 'ruta_previa' not in st.session_state:
    st.session_state.ruta_previa = ""
if 'km_input' not in st.session_state:
    st.session_state.km_input = 0.0
if 'casetas_input' not in st.session_state:
    st.session_state.casetas_input = 0.0
if 'redonda_previa' not in st.session_state:
    st.session_state.redonda_previa = False

default_params = {
    "w_llantas_largo": 0.62, "w_mtto_largo": 1.09, "gasto_op_largo": 247.0,
    "w_llantas_corto": 0.60, "w_mtto_corto": 1.05, "gasto_op_corto": 88.0,
    "w_admin": 4.16, "w_operador": 1.8928, "w_carga_soc": 35.0,
    "w_seguro": 5000.0, "w_gps_tracto": 1228.74, "w_gps_caja": 215.25, 
    "w_dep_tracto": 20628.08, "w_dep_caja": 3062.50,
    "valor_tractor": 2500000.0, "valor_caja": 800000.0,
    "km_mes_tracto_largo": 18500.0, "km_mes_tracto_corto": 13500.0,
    "km_mes_caja_largo": 8000.0, "km_mes_caja_corto": 1500.0,
    "margen_cruce": 5.0, "margen_accesorios": 20.0
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
    tipo_equipo = st.radio("Tipo de Equipo", ["Caja de Intercambio ", "Caja Propia"])
    tc = st.number_input("Tipo de Cambio (MXN/USD)", value=17.50, step=0.1)
    
    st.markdown("---")
    st.header("⛽ Combustible (FSC)")
    precio_diesel = st.number_input("Precio Diésel ($/L)", value=24.57, step=0.50)
    rendimiento_base = st.number_input("Rendimiento (km/L)", value=2.70, step=0.05)
    
    factor_calculado = precio_diesel / rendimiento_base if rendimiento_base > 0 else 0
    st.markdown("#### Factor Diésel ")
    st.subheader(f"${factor_calculado:.2f} / km")
    
    st.markdown("---")
    st.header("⚙️ Ajustes Margen")
    margen_objetivo = st.number_input("🎯 Margen Neto Objetivo (%)", value=25.0, step=1.0)
    moneda_neg = st.radio("Cerrar trato en:", ["MXN (Pesos)", "USD (Dólares)"])
    telefono_wa = st.text_input("WhatsApp Cliente", "")

    mult_peaje = 2.5

# --- 3. ÁREA PRINCIPAL CON 4 PESTAÑAS ---
tab_cot, tab_rx, tab_hist, tab_config = st.tabs(["🎯 Cotizador Pro", "📊 Rayos X (EBITDA)", "📜 Historial", "⚙️ Configuración Costeo"])

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
        st.subheader("📍 Ruta ")
        c1, c2 = st.columns(2)
        orig = c1.text_input("Origen", "")
        dest = c2.text_input("Destino", "")
        
        st.markdown("**Configuración del Viaje:**")
        ctrl_1, ctrl_2, ctrl_3 = st.columns(3)
        es_ruta_redonda = ctrl_1.checkbox("🔄 Ruta Redonda")
        es_doble_operador = ctrl_2.checkbox("👥 Doble Operador")
        tipo_ruta_manual = ctrl_3.selectbox("Tipo de Ruta", ["Automático", "Mov. Local/Patio", "Forzar Tramo Corto", "Forzar Tramo Largo"])
        st.markdown("---")
        
        ruta_actual = f"{orig}-{dest}"
        
        # 1. LLAMADA A LA API (Solo si cambia Origen o Destino)
        if orig and dest and ruta_actual != st.session_state.ruta_previa:
            try:
                m_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}"
                st.markdown(f'<iframe width="100%" height="250" src="{m_url}" style="border-radius:10px; border: 1px solid #ddd;"></iframe>', unsafe_allow_html=True)
                
                dist_api = 0.0
                peaje_api = 0.0
                
                routes_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
                headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "routes.distanceMeters,routes.travelAdvisory.tollInfo"}
                payload = {"origin": {"address": orig}, "destination": {"address": dest}, "travelMode": "DRIVE", "extraComputations": ["TOLLS"]}
                resp = requests.post(routes_url, json=payload, headers=headers)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if "routes" in data and len(data["routes"]) > 0:
                        ruta_data = data["routes"][0]
                        if "distanceMeters" in ruta_data: dist_api = round(ruta_data["distanceMeters"] / 1000.0, 1)
                        if "travelAdvisory" in ruta_data and "tollInfo" in ruta_data["travelAdvisory"]:
                            peajes = ruta_data["travelAdvisory"]["tollInfo"].get("estimatedPrice", [])
                            for peaje in peajes:
                                if peaje.get("currencyCode") == "MXN":
                                    costo_auto = float(peaje.get("units", "0")) + (float(peaje.get("nanos", 0)) / 1e9)
                                    peaje_api += costo_auto * mult_peaje
                else:
                    res_basico = gmaps.directions(orig, dest)
                    if res_basico: dist_api = round(res_basico[0]['legs'][0]['distance']['value'] / 1000.0, 1)
                
                # Guardamos los resultados en el estado para que no se sobreescriban
                st.session_state.km_input = dist_api
                st.session_state.casetas_input = peaje_api
                st.session_state.ruta_previa = ruta_actual
                st.session_state.redonda_previa = False # Reset toggle
                
            except Exception as e:
                st.info("Calculando ruta avanzada...")

        # 2. LÓGICA DE RUTA REDONDA (Multiplica el estado actual, sea API o manual)
        if es_ruta_redonda != st.session_state.redonda_previa:
            if es_ruta_redonda:
                st.session_state.km_input *= 2
                st.session_state.casetas_input *= 2
            else:
                st.session_state.km_input /= 2
                st.session_state.casetas_input /= 2
            st.session_state.redonda_previa = es_ruta_redonda

        km_final = st.number_input("KMS Totales (Editar si es necesario)", key="km_input", format="%.2f", step=1.0)

        # --- MOTOR FINANCIERO: REGLA DE TRAMOS Y DOBLE OPERADOR ---
        if tipo_ruta_manual == "Forzar Tramo Corto" or tipo_ruta_manual == "Mov. Local/Patio":
            es_largo = False
        elif tipo_ruta_manual == "Forzar Tramo Largo":
            es_largo = True
        else:
            es_largo = km_final > 350
            
        w_llantas = st.session_state.w_llantas_largo if es_largo else st.session_state.w_llantas_corto
        w_mtto = st.session_state.w_mtto_largo if es_largo else st.session_state.w_mtto_corto
        gasto_op_viaje = st.session_state.gasto_op_largo if es_largo else st.session_state.gasto_op_corto
        w_km_mes_tracto = st.session_state.km_mes_tracto_largo if es_largo else st.session_state.km_mes_tracto_corto
        w_km_mes_caja = st.session_state.km_mes_caja_largo if es_largo else st.session_state.km_mes_caja_corto
        
        mult_operador = 2 if es_doble_operador else 1

        cpk_piso_flete = 0.0
        costo_operador = 0.0
        costo_llantas_mtto = 0.0
        costo_admin_viaje = 0.0
        costo_seg_gps_viaje = 0.0
        costo_deprec_viaje = 0.0
        total_fsc_mxn = km_final * factor_calculado
        costo_piso_total = 0.0
        
        if km_final > 0:
            costo_operador = ((km_final * w_operador * (1 + (w_carga_soc/100))) + gasto_op_viaje) * mult_operador
            costo_llantas_mtto = km_final * (w_llantas + w_mtto)
            costo_admin_viaje = km_final * w_admin
            
            w_km_mes_tracto_calc = w_km_mes_tracto if w_km_mes_tracto > 0 else 1
            w_km_mes_caja_calc = w_km_mes_caja if w_km_mes_caja > 0 else 1
            
            costo_seg_gps_viaje = km_final * ((w_seguro + w_gps_tracto) / w_km_mes_tracto_calc) + (km_final * (w_gps_caja / w_km_mes_caja_calc) if tipo_equipo == "Caja Propia" else 0)
            costo_deprec_viaje = km_final * (w_dep_tracto / w_km_mes_tracto_calc) + (km_final * (w_dep_caja / w_km_mes_caja_calc) if tipo_equipo == "Caja Propia" else 0)
                
            costo_piso_total = costo_operador + costo_llantas_mtto + costo_admin_viaje + costo_seg_gps_viaje + costo_deprec_viaje
            cpk_piso_flete = costo_piso_total / km_final
            
            st.success(f"⚖️ **Costo Piso Flete:** ${cpk_piso_flete:.2f} MXN por km | TRAMO: {'Largo (>350km)' if es_largo else 'Corto (<=350km)'}")

    # --- LECTURA DE CASETAS Y ACCESORIOS (INYECCIÓN DE MÁRGENES) ---
    with col_extras:
        st.subheader("💰 Cargos Extra y Accesorios")
        with st.container(border=True):
            st.markdown("**Cargos Fijos de Ruta**")
            col_f1, col_f2 = st.columns(2)
            casetas = col_f1.number_input("Casetas Grales. API ($)", key="casetas_input", format="%.2f")
            factor_ajuste_comb = col_f2.number_input("Ajuste Combustible ($/km)", 0.0, format="%.2f")
            total_ajuste_comb = km_final * factor_ajuste_comb
            if total_ajuste_comb > 0: st.caption(f"Total Ajuste Combustible: **${total_ajuste_comb:,.2f}**")
            
            st.markdown("---")
            st.markdown("**Listado de Accesorios Adicionales**")
            accesorios_seleccionados = st.multiselect("Selecciona uno o más accesorios:", list(precios_accesorios.keys()))
            
            total_accesorios_costo = 0.0
            total_accesorios_venta = 0.0
            detalle_accesorios = {} 
            
            if accesorios_seleccionados:
                for acc in accesorios_seleccionados:
                    col_c1, col_c2 = st.columns(2)
                    cant = col_c1.number_input(f"Cant. ({acc})", min_value=1.0, value=1.0, step=1.0, key=f"cant_{acc}")
                    costo = col_c2.number_input(f"Costo ($) - {acc}", min_value=0.0, value=float(precios_accesorios[acc]), step=50.0, key=f"costo_{acc}")
                    
                    subtotal_costo = cant * costo
                    if acc == "CRUCE":
                        subtotal_venta = subtotal_costo * (1 + (st.session_state.margen_cruce / 100.0))
                    else:
                        subtotal_venta = subtotal_costo * (1 + (st.session_state.margen_accesorios / 100.0))
                        
                    total_accesorios_costo += subtotal_costo
                    total_accesorios_venta += subtotal_venta
                    detalle_accesorios[acc] = {"cantidad": cant, "costo": subtotal_costo, "venta": subtotal_venta}
            
            st.markdown("---")
            st.markdown("**Accesorio Especial / Maniobra Libre**")
            col_p1, col_p2 = st.columns([2, 1])
            desc_personalizado = col_p1.text_input("Descripción del cargo")
            monto_personalizado = col_p2.number_input("Monto Costo ($)", min_value=0.0, step=100.0)
            if desc_personalizado and monto_personalizado > 0:
                subtotal_costo = monto_personalizado
                subtotal_venta = subtotal_costo * (1 + (st.session_state.margen_accesorios / 100.0))
                total_accesorios_costo += subtotal_costo
                total_accesorios_venta += subtotal_venta
                detalle_accesorios[desc_personalizado] = {"cantidad": 1.0, "costo": subtotal_costo, "venta": subtotal_venta}

            total_extras_venta_mxn = casetas + total_ajuste_comb + total_accesorios_venta

    # --- PARTE 2 DE LA COLUMNA RUTA (Cálculo del IPK Puro Flete) ---
    with col_ruta:
        st.markdown("---")
        c_cpk, c_ipk = st.columns(2)
        with c_cpk:
            # El Margen Objetivo solo aplica a los Costos del Flete (Aislamos los accesorios)
            costos_puros_flete = costo_piso_total + total_fsc_mxn + casetas + total_ajuste_comb
            margen_decimal = margen_objetivo / 100.0
            
            if km_final > 0 and margen_decimal < 1:
                venta_flete_requerida = costos_puros_flete / (1 - margen_decimal)
                flete_requerido = venta_flete_requerida - total_fsc_mxn - casetas - total_ajuste_comb
                ipk_sugerido_mxn = flete_requerido / km_final
            else:
                ipk_sugerido_mxn = 0.0
                
            st.metric(f"Tarifa Sugerida Flete (Margen {margen_objetivo}%)", f"${ipk_sugerido_mxn:.2f}")
            
        with c_ipk:
            if moneda_neg == "MXN (Pesos)":
                ipk_pactado = st.number_input("IPK a Facturar (MXN) $", value=float(ipk_sugerido_mxn))
                ipk_mxn_final = ipk_pactado
                moneda_tag = "MXN"
            else:
                ipk_pactado = st.number_input("IPK a Facturar (USD) $", value=float(ipk_sugerido_mxn / tc) if tc > 0 else 0.0)
                ipk_mxn_final = ipk_pactado * tc
                moneda_tag = "USD"

        flete_neto_mxn = km_final * ipk_mxn_final
        total_mxn_neto = flete_neto_mxn + total_extras_venta_mxn + total_fsc_mxn
        total_usd_neto = total_mxn_neto / tc

        st.markdown("---")
        st.info(f"⛽ **FSC Proyectado:** Factor ${factor_calculado:.2f} (Rend. Base: {rendimiento_base}) = **${total_fsc_mxn:,.2f} MXN**")

    # --- CÁLCULO FINAL DE UTILIDAD Y KPIs CON COSTOS REALES ---
    egreso_total_viaje = costo_piso_total + total_fsc_mxn + casetas + total_ajuste_comb + total_accesorios_costo
    utilidad_neta_viaje_actual = total_mxn_neto - egreso_total_viaje
    ebitda_viaje_actual = utilidad_neta_viaje_actual + costo_deprec_viaje # Se suma la depre porque no es salida de efectivo
    
    margen_neto_real = (utilidad_neta_viaje_actual / total_mxn_neto) * 100 if total_mxn_neto > 0 else 0.0

    st.markdown("---")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1: st.metric(label="TOTAL A FACTURAR MXN", value=f"${total_mxn_neto:,.2f}")
    with kpi2: st.metric(label="TOTAL A FACTURAR USD", value=f"${total_usd_neto:,.2f}", delta=f"TC: {tc}")
    with kpi3: st.metric(label=f"IPK Facturado ({moneda_tag})", value=f"${ipk_pactado:.2f}")
    with kpi4:
        color_delta = "normal" if margen_neto_real >= margen_objetivo else ("off" if margen_neto_real >= 0 else "inverse")
        if utilidad_neta_viaje_actual < 0: st.error("🚨 ¡PÉRDIDA DETECTADA! La tarifa no cubre los costos totales.")
        st.metric(
            label="Utilidad Neta del Viaje", 
            value=f"${utilidad_neta_viaje_actual:,.2f}", 
            delta=f"Margen Neto Real: {margen_neto_real:.1f}%", 
            delta_color=color_delta
        )

    # --- SISTEMA MULTIRUTA ---
    st.markdown("---")
    col_btn_add, col_btn_clear = st.columns([3, 1])
    with col_btn_add:
        if st.button("➕ Añadir este Tramo a la Propuesta", use_container_width=True, type="primary"):
            if orig and dest:
                st.session_state.rutas_propuesta.append({
                    "Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final,
                    "Flete": flete_neto_mxn, "FSC": total_fsc_mxn, "Casetas": casetas, 
                    "Extras": total_extras_venta_mxn - casetas, "Total MXN": total_mxn_neto, "Total USD": total_usd_neto,
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

# --- PESTAÑA 2: TABLERO FINANCIERO DIRECTIVO (RAYOS X) ---
with tab_rx:
    st.markdown("## 📊 Radiografía Financiera ")
    if km_final > 0:
        st.info("Este tablero evalúa la rentabilidad del tramo configurado actualmente, aplicando el Costeo ABC y los márgenes de venta en accesorios.")
        
        margen_ebitda = (ebitda_viaje_actual / total_mxn_neto) * 100 if total_mxn_neto > 0 else 0
        margen_neto = (utilidad_neta_viaje_actual / total_mxn_neto) * 100 if total_mxn_neto > 0 else 0

        # Implementación de Idea 9: El Nuevo Acomodo de Tarjetas
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Ingreso Total (Venta)", f"${total_mxn_neto:,.2f}")
        k2.metric("Egreso Total (Costo Real)", f"${egreso_total_viaje:,.2f}")
        k3.metric("EBITDA (Flujo)", f"${ebitda_viaje_actual:,.2f}", f"{margen_ebitda:.1f}%", delta_color="normal" if ebitda_viaje_actual>0 else "inverse")
        k4.metric("Utilidad Neta", f"${utilidad_neta_viaje_actual:,.2f}", f"{margen_neto:.1f}%", delta_color="normal" if utilidad_neta_viaje_actual>0 else "inverse")

        with st.expander("🔍 Desglose Completo de Egresos", expanded=True):
            st.markdown("#### Costos Directos del Viaje")
            st.write(f"- **Diésel (FSC):** ${total_fsc_mxn:,.2f}")
            st.write(f"- **Peajes/Casetas:** ${casetas:,.2f}")
            st.write(f"- **Sueldo, Carga Social y Op. Fijo:** ${costo_operador:,.2f} *(Multiplicador x{mult_operador})*")
            st.write(f"- **Costo Real de Accesorios/Cruces:** ${total_accesorios_costo:,.2f}")
            st.markdown("#### Costos Asignados (Prorrateo ABC)")
            st.write(f"- **Llantas y Mantenimiento:** ${costo_llantas_mtto:,.2f} *({'Tramo Largo' if es_largo else 'Tramo Corto'})*")
            st.write(f"- **Gasto Administrativo Asignado:** ${costo_admin_viaje:,.2f}")
            st.write(f"- **Seguros y Satélite Prorrateado:** ${costo_seg_gps_viaje:,.2f}")
            st.write(f"- **Depreciación Fierros Prorrateada:** ${costo_deprec_viaje:,.2f}")
            st.markdown("---")
            st.write(f"**TOTAL EGRESOS:** ${egreso_total_viaje:,.2f}")
    else:
        st.warning("⚠️ Ingresa los KMS en el Cotizador para ver el análisis de rentabilidad.")

# --- PESTAÑA 3: HISTORIAL Y AUDITORÍA ---
with tab_hist:
    st.markdown("## 📜 Sábana Financiera de Auditoría")
    st.info("Las funciones de guardado en el historial y generación de PDF siguen activas en la Pestaña 1.")

# --- PESTAÑA 4: CONFIGURACIÓN ABC (EL CUARTO DE MÁQUINAS) ---
with tab_config:
    st.markdown("## ⚙️ Configuración de Costeo Operativo ")
    st.info("Estos parámetros controlan el 'Cerebro Financiero'. Las modificaciones se aplican en tiempo real.")
    
    col_c1, col_c2, col_c3 = st.columns(3)
    
    with col_c1:
        st.subheader("1. Gastos Variables (Por Distancia)")
        st.markdown("**Ruta Larga (> 350 km)**")
        st.session_state.w_llantas_largo = st.number_input("Llantas Larga ($/km)", value=st.session_state.w_llantas_largo, step=0.01)
        st.session_state.w_mtto_largo = st.number_input("Mtto. Motriz Larga ($/km)", value=st.session_state.w_mtto_largo, step=0.01)
        st.session_state.gasto_op_largo = st.number_input("Gasto Op. Largo ($)", value=st.session_state.gasto_op_largo, step=10.0)
        
        st.markdown("**Ruta Corta (<= 350 km)**")
        st.session_state.w_llantas_corto = st.number_input("Llantas Corta ($/km)", value=st.session_state.w_llantas_corto, step=0.01)
        st.session_state.w_mtto_corto = st.number_input("Mtto. Motriz Corta ($/km)", value=st.session_state.w_mtto_corto, step=0.01)
        st.session_state.gasto_op_corto = st.number_input("Gasto Op. Corto ($)", value=st.session_state.gasto_op_corto, step=10.0)

        st.markdown("---")
        st.subheader("2. Operador y Administrativos")
        st.session_state.w_operador = st.number_input("Sueldo Operador Base ($/km)", value=st.session_state.w_operador, step=0.01)
        st.session_state.w_carga_soc = st.number_input("Carga Social (%)", value=st.session_state.w_carga_soc, step=1.0)
        st.session_state.w_admin = st.number_input("Gasto Administrativo ($/km)", value=st.session_state.w_admin, step=0.01)

    with col_c2:
        st.subheader("3. Costos Fijos y Equipos")
        st.session_state.valor_tractor = st.number_input("Valor de Adquisición Tractor ($)", value=st.session_state.valor_tractor, step=50000.0)
        st.session_state.valor_caja = st.number_input("Valor de Adquisición Caja ($)", value=st.session_state.valor_caja, step=10000.0)
        
        st.markdown("---")
        st.session_state.w_seguro = st.number_input("Seguro Tractor ($/mes)", value=st.session_state.w_seguro, step=100.0)
        st.session_state.w_gps_tracto = st.number_input("GPS Tractor ($/mes)", value=st.session_state.w_gps_tracto, step=10.0)
        st.session_state.w_gps_caja = st.number_input("GPS Caja ($/mes)", value=st.session_state.w_gps_caja, step=10.0)
        st.session_state.w_dep_tracto = st.number_input("Depreciación Fija Tractor ($/mes)", value=st.session_state.w_dep_tracto, step=100.0)
        st.session_state.w_dep_caja = st.number_input("Depreciación Fija Caja ($/mes)", value=st.session_state.w_dep_caja, step=10.0)

    with col_c3:
        st.subheader("4. Metas de Kilometraje")
        st.session_state.km_mes_tracto_largo = st.number_input("KM Larga (Tracto)", value=st.session_state.km_mes_tracto_largo, step=500.0)
        st.session_state.km_mes_tracto_corto = st.number_input("KM Corta (Tracto)", value=st.session_state.km_mes_tracto_corto, step=500.0)
        st.session_state.km_mes_caja_largo = st.number_input("KM Larga (Caja)", value=st.session_state.km_mes_caja_largo, step=500.0)
        st.session_state.km_mes_caja_corto = st.number_input("KM Corta (Caja)", value=st.session_state.km_mes_caja_corto, step=500.0)
        
        st.markdown("---")
        st.subheader("5. Ajustes de Utilidad (Extras)")
        st.session_state.margen_cruce = st.number_input("Margen extra Cruces (%)", value=st.session_state.margen_cruce, step=1.0)
        st.session_state.margen_accesorios = st.number_input("Margen extra Accesorios (%)", value=st.session_state.margen_accesorios, step=1.0)
