import streamlit as st
import googlemaps
import openrouteservice
from fpdf import FPDF
import urllib.parse
import pandas as pd
from datetime import datetime
import io
import requests
import base64
import tempfile
import os

# --- 1. CONFIGURACIÓN INICIAL DE LA PÁGINA ---
st.set_page_config(page_title="Cotizador Maestro 53' Pro - Consolidado", layout="wide")

# --- 2. INICIALIZACIÓN DE VARIABLES EN MEMORIA ---
if 'historial' not in st.session_state:
    st.session_state.historial = []
if 'rutas_propuesta' not in st.session_state:
    st.session_state.rutas_propuesta = []
if 'ruta_previa' not in st.session_state:
    st.session_state.ruta_previa = ""
if 'km_input_key' not in st.session_state:
    st.session_state.km_input_key = 0.0
if 'casetas_input_key' not in st.session_state:
    st.session_state.casetas_input_key = 0.0
if 'redonda_previa' not in st.session_state:
    st.session_state.redonda_previa = False

# --- MEMORIA DINÁMICA DE PEAJES (ACTUALIZADA) ---
if 'matriz_peajes_dinamica' not in st.session_state:
    st.session_state.matriz_peajes_dinamica = {
        "apodaca": 845.00,
        "saltillo": 845.00,
        "ramos arizpe": 845.00,
        "monterrey": 845.00,
        "guadalupe": 845.00,
        "san nicolas de los garza": 845.00,
        "san luis potosi": 1865.00,
        "santa catarina": 845.00,
        "villa de garcia": 845.00,
        "escobedo": 845.00,
        "queretaro": 1865.00,
        "puebla": 4019.00,
        "cuautitlan": 2886.00,
        "tlaxcala": 4116.00,
        "huamantla": 3501.00,
        "cuautla": 3585.00,
        "guadalajara": 3716.00,
        "zapopan": 3716.00,
        "cadereyta": 845.00,
        "salinas victoria": 845.00,
        "silao": 2062.00,
        "pesqueria": 845.00,
        "el derramadero": 1331.00,
        "irapuato": 2190.00,
        "toluca": 2577.00,
    }

# --- PARÁMETROS OPERATIVOS BASE ---
default_params = {
    "w_llantas_largo": 0.62, "w_mtto_largo": 1.09, "gasto_op_largo": 247.0,
    "w_llantas_corto": 0.60, "w_mtto_corto": 1.05, "gasto_op_corto": 88.0,
    "w_admin": 4.16, "w_operador": 1.8928, "w_carga_soc": 35.0,
    "w_seguro": 5000.0, "w_gps_tracto": 1228.74, "w_gps_caja": 215.25, 
    "valor_tractor": 2887931.03, "residual_tractor": 1155172.41, "vida_tractor": 7,
    "valor_caja": 612500.00, "residual_caja": 245000.00, "vida_caja": 10,
    "km_mes_tracto_largo": 18500.0, "km_mes_tracto_corto": 13500.0,
    "km_mes_caja_largo": 8000.0, "km_mes_caja_corto": 1500.0,
    "margen_cruce": 5.0, "margen_accesorios": 20.0
}
for k, v in default_params.items():
    if k not in st.session_state:
        st.session_state[k] = v

precios_accesorios = {
    "FIANZA": 330.00, "CARGA / DESCARGA EN VIVO": 500.00, "DEMORAS": 935.00,
    "CRUCE": 2341.75, "POSICIONAMIENTO": 1190.00, "LAVADO DE CAJA": 170.00,
    "FUMIGACION": 552.50, "BASCULA": 935.00, "EQUIPO DE SUJECION": 595.00,
    "SELLOS DE SEGURIDAD": 130.00, "HORA ADICIONAL MANIOBRA": 435.00,
    "DEMORAS CAJA EN PLANTA (4to DÍA)": 1045.00, "PARADAS ADICIONALES/DESVIACIONES": 2610.00,
    "MOVIMIENTO EN FALSO": 2610.00
}

# --- 3. EL CEREBRO HÍBRIDO ---
def consultar_peaje_hibrido(origen, destino):
    origen_limpio = origen.lower().strip()
    destino_limpio = destino.lower().strip()
    ruta_ida = f"{origen_limpio} - {destino_limpio}"
    ruta_vuelta = f"{destino_limpio} - {origen_limpio}"
    
    if ruta_ida in st.session_state.matriz_peajes_dinamica: return st.session_state.matriz_peajes_dinamica[ruta_ida] / 1.16
    if ruta_vuelta in st.session_state.matriz_peajes_dinamica: return st.session_state.matriz_peajes_dinamica[ruta_vuelta] / 1.16
        
    ruta_completa = f"{origen_limpio} {destino_limpio}"
    ciudades_encontradas = [ciudad for ciudad in st.session_state.matriz_peajes_dinamica.keys() if ciudad in ruta_completa]
            
    if len(ciudades_encontradas) > 1: return 0.0
    if len(ciudades_encontradas) == 1: return st.session_state.matriz_peajes_dinamica[ciudades_encontradas[0]] / 1.16
        
    return 0.0

# --- CONEXIÓN A MOTORES DE RUTEO ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
    ors_key = st.secrets["ORS_KEY"]
    ors_client = openrouteservice.Client(key=ors_key)
except Exception:
    st.error("⚠️ Configura 'MAPS_API_KEY' y 'ORS_KEY' en los Secrets de Streamlit.")


# --- 4. BARRA LATERAL ---
with st.sidebar:
    st.header("👤 Datos de Cotización")
    empresas_base = ["HG TRANSPORTACIONES, SA DE CV", "RL TRANSPORTACIONES, SA DE CV"]
    empresa_remitente = st.selectbox("Nuestra Empresa", empresas_base)
    nombre_remitente = st.text_input("Nuestro Representante", placeholder="Ej. Juan Pérez")
    
    if empresa_remitente == "HG TRANSPORTACIONES, SA DE CV":
        lugar_default = "Pesquería, NL"
    else:
        lugar_default = "Cienega de Flores, NL"
        
    lugar_expedicion = st.text_input("Lugar de Expedición", value=lugar_default)
    
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

w_dep_tracto_calc = (st.session_state.valor_tractor - st.session_state.residual_tractor) / (st.session_state.vida_tractor * 12) if st.session_state.vida_tractor > 0 else 0
w_dep_caja_calc = (st.session_state.valor_caja - st.session_state.residual_caja) / (st.session_state.vida_caja * 12) if st.session_state.vida_caja > 0 else 0
w_admin = st.session_state.w_admin
w_operador = st.session_state.w_operador
w_carga_soc = st.session_state.w_carga_soc
w_seguro = st.session_state.w_seguro
w_gps_tracto = st.session_state.w_gps_tracto
w_gps_caja = st.session_state.w_gps_caja

# --- 5. ÁREA PRINCIPAL CON 4 PESTAÑAS ---
tab_cot, tab_rx, tab_hist, tab_config = st.tabs(["🎯 Cotizador Pro", "📊 Rayos X (EBITDA)", "📜 Historial", "⚙️ Configuración Costeo"])

# --- PESTAÑA 1: COTIZADOR ---
with tab_cot:
    st.markdown("## Resumen de Cotización")
    col_ruta, col_extras = st.columns([2, 1])

    with col_ruta:
        st.subheader("📍 Ruta ")
        c1, c2 = st.columns(2)
        orig = c1.text_input("Origen", "")
        dest = c2.text_input("Destino", "")
        via_intermedia = st.text_input("Vía / Punto Intermedio (Opcional)", value="", placeholder="Ej: Matehuala, San Luis Potosi")
        
        st.markdown("**Configuración del Viaje:**")
        ctrl_1, ctrl_2, ctrl_3 = st.columns(3)
        es_ruta_redonda = ctrl_1.checkbox("🔄 Ruta Redonda")
        es_doble_operador = ctrl_2.checkbox("👥 Doble Operador")
        tipo_ruta_manual = ctrl_3.selectbox("Tipo de Ruta", ["Automático", "Mov. Local/Patio", "Forzar Tramo Corto", "Forzar Tramo Largo"])
        st.markdown("---")
        
        ruta_actual = f"{orig}-{via_intermedia}-{dest}"
        
        if orig and dest:
            if via_intermedia:
                m_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}&waypoints={urllib.parse.quote(via_intermedia)}"
            else:
                m_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}"
            
            st.markdown(f'<iframe width="100%" height="250" src="{m_url}" style="border-radius:10px; border: 1px solid #ddd;"></iframe>', unsafe_allow_html=True)
            
            if ruta_actual != st.session_state.ruta_previa:
                with st.spinner("Calculando ruta HGV y consultando peajes en memoria..."):
                    try:
                        dist_api = 0.0
                        peaje_api = 0.0 
                        coordenadas_viaje = []
                        
                        geo_orig = ors_client.pelias_search(text=orig)
                        if geo_orig['features']: coordenadas_viaje.append(geo_orig['features'][0]['geometry']['coordinates'])
                            
                        if via_intermedia:
                            geo_via = ors_client.pelias_search(text=via_intermedia)
                            if geo_via['features']: coordenadas_viaje.append(geo_via['features'][0]['geometry']['coordinates'])
                        
                        geo_dest = ors_client.pelias_search(text=dest)
                        if geo_dest['features']: coordenadas_viaje.append(geo_dest['features'][0]['geometry']['coordinates'])
                            
                        if len(coordenadas_viaje) >= 2:
                            try:
                                ruta = ors_client.directions(coordinates=coordenadas_viaje, profile='driving-hgv', format='geojson')
                            except Exception:
                                ruta = ors_client.directions(coordinates=coordenadas_viaje, profile='driving-car', format='geojson')
                                st.toast("⚠️ ORS HGV en mantenimiento: Usando cálculo de distancia estándar.")
                            dist_api = round(ruta['features'][0]['properties']['summary']['distance'] / 1000.0, 1)
                        
                        peaje_api = consultar_peaje_hibrido(orig, dest)
                        st.session_state.km_input_key = dist_api
                        st.session_state.casetas_input_key = peaje_api
                        st.session_state.ruta_previa = ruta_actual
                        st.session_state.redonda_previa = False 
                    except Exception as e:
                        st.error(f"Error en el cálculo: {e}")

        if es_ruta_redonda != st.session_state.redonda_previa:
            if es_ruta_redonda:
                st.session_state.km_input_key *= 2
                st.session_state.casetas_input_key *= 2
            else:
                st.session_state.km_input_key /= 2
                st.session_state.casetas_input_key /= 2
            st.session_state.redonda_previa = es_ruta_redonda

        km_final = st.number_input("KMS Totales (Editar si es necesario)", key="km_input_key", format="%.2f", step=1.0)

        if tipo_ruta_manual == "Forzar Tramo Corto" or tipo_ruta_manual == "Mov. Local/Patio": es_largo = False
        elif tipo_ruta_manual == "Forzar Tramo Largo": es_largo = True
        else: es_largo = km_final > 350
            
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
            costo_deprec_viaje = km_final * (w_dep_tracto_calc / w_km_mes_tracto_calc) + (km_final * (w_dep_caja_calc / w_km_mes_caja_calc) if tipo_equipo == "Caja Propia" else 0)
                
            costo_piso_total = costo_operador + costo_llantas_mtto + costo_admin_viaje + costo_seg_gps_viaje + costo_deprec_viaje
            cpk_piso_flete = costo_piso_total / km_final
            
            st.success(f"⚖️ **Costo Piso Flete:** ${cpk_piso_flete:.2f} MXN por km | TRAMO: {'Largo (>350km)' if es_largo else 'Corto (<=350km)'}")


    with col_extras:
        st.subheader("💰 Cargos Extra y Accesorios")
        with st.container(border=True):
            st.markdown("**Cargos Fijos de Ruta**")
            col_f1, col_f2 = st.columns(2)
            casetas = col_f1.number_input("Casetas Grales. API ($)", key="casetas_input_key", format="%.2f")
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
                    if acc == "CRUCE": margen_dec = min(st.session_state.margen_cruce / 100.0, 0.99)
                    else: margen_dec = min(st.session_state.margen_accesorios / 100.0, 0.99)
                        
                    subtotal_venta = subtotal_costo / (1 - margen_dec) if margen_dec < 1 else subtotal_costo
                    total_accesorios_costo += subtotal_costo
                    total_accesorios_venta += subtotal_venta
                    detalle_accesorios[acc] = {"cantidad": cant, "costo": subtotal_costo, "venta": subtotal_venta}
            
            st.markdown("---")
            st.markdown("**Accesorio Especial / Maniobra Libre**")
            col_p1, col_p2 = st.columns([2, 1])
            desc_personalizado = col_p1.text_input("Descripción del cargo")
            monto_personalizado = col_p2.number_input("Costo ($)", min_value=0.0, step=100.0)
            if desc_personalizado and monto_personalizado > 0:
                subtotal_costo = monto_personalizado
                margen_dec_custom = min(st.session_state.margen_accesorios / 100.0, 0.99)
                subtotal_venta = subtotal_costo / (1 - margen_dec_custom) if margen_dec_custom < 1 else subtotal_costo
                total_accesorios_costo += subtotal_costo
                total_accesorios_venta += subtotal_venta
                detalle_accesorios[desc_personalizado] = {"cantidad": 1.0, "costo": subtotal_costo, "venta": subtotal_venta}

            total_extras_venta_mxn = casetas + total_ajuste_comb + total_accesorios_venta
            nombres_accesorios = ", ".join([f"{k} (x{v['cantidad']})" for k, v in detalle_accesorios.items()]) if detalle_accesorios else "Ninguno"

            st.markdown("---")
            st.markdown("#### ➕ Resumen de Cargos Adicionales")
            if total_ajuste_comb > 0.0: st.write(f"**⛽ Ajuste de Combustible:** ${total_ajuste_comb:,.2f} MXN")
            if detalle_accesorios:
                st.write("**📋 Desglose de Accesorios Operativos:**")
                for acc, datos in detalle_accesorios.items():
                    st.write(f"- 📦 {acc}: ${datos['venta']:,.2f} MXN")


    with col_ruta:
        st.markdown("---")
        c_cpk, c_ipk = st.columns(2)
        with c_cpk:
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
        total_usd_neto = total_mxn_neto / tc if tc > 0 else 0.0

        st.markdown("---")
        st.info(f"⛽ **FSC Proyectado:** Factor ${factor_calculado:.2f} (Rend. Base: {rendimiento_base}) = **${total_fsc_mxn:,.2f} MXN**")

    # --- NUEVOS CÁLCULOS DE MÁRGENES SEPARADOS ---
    egreso_total_viaje = costo_piso_total + total_fsc_mxn + casetas + total_ajuste_comb + total_accesorios_costo
    utilidad_neta_viaje_actual = total_mxn_neto - egreso_total_viaje
    ebitda_viaje_actual = utilidad_neta_viaje_actual + costo_deprec_viaje 
    margen_neto_real = (utilidad_neta_viaje_actual / total_mxn_neto) * 100 if total_mxn_neto > 0 else 0.0

    # 1. Margen Puro del Flete
    ingreso_flete_total = flete_neto_mxn + total_fsc_mxn + casetas + total_ajuste_comb
    costo_flete_total = costo_piso_total + total_fsc_mxn + casetas + total_ajuste_comb
    utilidad_flete_mxn = ingreso_flete_total - costo_flete_total
    margen_flete_real = (utilidad_flete_mxn / ingreso_flete_total) * 100 if ingreso_flete_total > 0 else 0.0

    # 2. Margen de Extras/Comercialización
    ingreso_extras_total = total_accesorios_venta
    costo_extras_total = total_accesorios_costo
    utilidad_extras_mxn = ingreso_extras_total - costo_extras_total
    margen_extras_real = (utilidad_extras_mxn / ingreso_extras_total) * 100 if ingreso_extras_total > 0 else 0.0

    st.markdown("---")
    
    # ALERTAS DE RENTABILIDAD
    if utilidad_neta_viaje_actual < 0: 
        st.error("🚨 ¡PÉRDIDA DETECTADA! La tarifa no cubre los costos totales.")
    if km_final > 0 and margen_flete_real < 20.0: 
        st.error(f"🚨 ¡ALTO AHÍ! MARGEN DE FLETE MENOR AL 20% ({margen_flete_real:.1f}%). REQUIERE AUTORIZACIÓN DIRECTIVA.")

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1: st.metric(label="TOTAL A FACTURAR MXN", value=f"${total_mxn_neto:,.2f}")
    with kpi2: st.metric(label="TOTAL A FACTURAR USD", value=f"${total_usd_neto:,.2f}", delta=f"TC: {tc}")
    with kpi3: st.metric(label=f"IPK Facturado ({moneda_tag})", value=f"${ipk_pactado:.2f}")
    with kpi4:
        color_delta = "normal" if margen_neto_real >= margen_objetivo else ("off" if margen_neto_real >= 0 else "inverse")
        st.metric(label="Utilidad Neta del Viaje", value=f"${utilidad_neta_viaje_actual:,.2f}", delta=f"Margen Neto: {margen_neto_real:.2f}%", delta_color=color_delta)

    st.markdown("---")
    st.header("🤝 Tablero de Negociación: Tarifa Target vs Ideal")
    with st.container(border=True):
        col_ideal, col_target = st.columns(2)
        es_usd = moneda_neg == "USD (Dólares)"
        moneda_label = "USD" if es_usd else "MXN"
        tarifa_ideal_mostrar = total_usd_neto if es_usd else total_mxn_neto
        utilidad_ideal_mostrar = utilidad_neta_viaje_actual / tc if es_usd else utilidad_neta_viaje_actual
        
        with col_ideal:
            st.subheader("🎯 Tu Escenario Ideal")
            st.write(f"Basado en tus métricas y margen del {margen_objetivo}%.")
            st.metric(f"Tarifa a Cobrar ({moneda_label})", f"${tarifa_ideal_mostrar:,.2f}")
            st.metric(f"Utilidad Proyectada ({moneda_label})", f"${utilidad_ideal_mostrar:,.2f}", f"{margen_neto_real:.2f}% margen")
            if es_usd: st.caption(f"Equivalente a **${total_mxn_neto:,.2f} MXN** (TC: {tc})")
            
        with col_target:
            st.subheader("💼 Escenario del Cliente (Target)")
            paso_input = 50.0 if es_usd else 500.0
            tarifa_target_input = st.number_input(f"Tarifa Ofrecida Total ({moneda_label})", min_value=0.0, value=float(tarifa_ideal_mostrar), step=paso_input)
            tarifa_target_mxn = tarifa_target_input * tc if es_usd else tarifa_target_input
            
            st.write("**¿Qué accesorios te pide absorber en esta tarifa?**")
            costo_absorbido_target_mxn = 0.0
            if detalle_accesorios:
                for acc, datos in detalle_accesorios.items():
                    costo_acc_mostrar = datos['costo'] / tc if es_usd else datos['costo']
                    if st.checkbox(f"Absorber {acc} (Costo interno: ${costo_acc_mostrar:,.2f} {moneda_label})", key=f"target_check_{acc}"):
                        costo_absorbido_target_mxn += datos['costo']
            else: st.info("No has seleccionado accesorios extra en la sección superior.")
                
            egreso_base_sin_acc = costo_piso_total + total_fsc_mxn + casetas + total_ajuste_comb
            costo_target_real_mxn = egreso_base_sin_acc + costo_absorbido_target_mxn
            utilidad_target_mxn = tarifa_target_mxn - costo_target_real_mxn
            margen_target = (utilidad_target_mxn / tarifa_target_mxn) * 100 if tarifa_target_mxn > 0 else 0
            utilidad_target_mostrar = utilidad_target_mxn / tc if es_usd else utilidad_target_mxn
            
            if margen_target >= margen_objetivo: color, estado = "🟢", "Excelente Negocio"
            elif margen_target >= (margen_objetivo / 2): color, estado = "🟡", "Margen Ajustado"
            elif margen_target >= 0: color, estado = "🟠", "Punto de Equilibrio (Peligro)"
            else: color, estado = "🔴", "Pérdida / Riesgo Alto"
                
            st.metric(f"Utilidad Real Target ({moneda_label})", f"${utilidad_target_mostrar:,.2f}", f"{margen_target:.2f}% de margen")
            st.markdown(f"**Diagnóstico:** {color} {estado}")

    st.markdown("---")
    col_btn_add, col_btn_clear = st.columns([3, 1])
    with col_btn_add:
        if st.button("➕ Añadir este Tramo a la Propuesta", use_container_width=True, type="primary"):
            if orig and dest:
                st.session_state.rutas_propuesta.append({
                    "Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final,
                    "Flete": flete_neto_mxn, "FSC": total_fsc_mxn, "Casetas": casetas, 
                    "Extras": total_extras_venta_mxn - casetas, "Total MXN": total_mxn_neto, "Total USD": total_usd_neto,
                    "Costo_Directo": costo_flete_total, "Flete_Puro_Venta": ingreso_flete_total,
                    "Ajuste_Comb": total_ajuste_comb, "Accesorios_Venta": total_accesorios_venta, "Accesorios_Costo": total_accesorios_costo,
                    "Detalle_Accesorios": nombres_accesorios,
                    "EBITDA": ebitda_viaje_actual, "Utilidad_Neta": utilidad_neta_viaje_actual
                })
                st.toast("✅ Tramo añadido a la propuesta")

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
            rutas_a_guardar = st.session_state.rutas_propuesta if st.session_state.rutas_propuesta else [{
                "Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final,
                "Flete Neto": flete_neto_mxn, "FSC": total_fsc_mxn, "Casetas": casetas, 
                "Ajuste_Comb": total_ajuste_comb, "Accesorios_Venta": total_accesorios_venta, "Accesorios_Costo": total_accesorios_costo,
                "Total MXN": total_mxn_neto, "Total USD": total_usd_neto,
                "Flete_Puro_Venta": ingreso_flete_total, "Costo_Directo": costo_flete_total,
                "EBITDA": ebitda_viaje_actual, "Utilidad_Neta": utilidad_neta_viaje_actual
            }]
            for r in rutas_a_guardar:
                moneda_ruta = r.get("Moneda", moneda_tag)
                f_conv = (1/tc) if moneda_ruta == "USD (Dólares)" else 1
                
                ingreso_total_mxn = r.get("Total MXN", total_mxn_neto)
                utilidad_neta_mxn = r.get("Utilidad_Neta", 0)
                margen_neto_pct = (utilidad_neta_mxn / ingreso_total_mxn) * 100 if ingreso_total_mxn > 0 else 0
                
                # Cálculo Margen Flete para Tabla
                flete_venta_hist = r.get("Flete_Puro_Venta", ingreso_flete_total)
                costo_flete_hist = r.get("Costo_Directo", costo_flete_total)
                util_flete_hist = flete_venta_hist - costo_flete_hist
                margen_flete_pct = (util_flete_hist / flete_venta_hist) * 100 if flete_venta_hist > 0 else 0

                st.session_state.historial.insert(0, {
                    "Fecha": datetime.now().strftime("%d/%m %H:%M"), "Empresa Cliente": empresa_cliente, "Contacto Cliente": atencion_cliente,
                    "Ruta": f"{r['Origen']}-{r['Destino']}", "KMS": r["KM"], "Servicio": r.get("Servicio", tipo_op), "Equipo": tipo_equipo,
                    "Moneda": moneda_ruta, "TC": tc, "Flete Cotizado": round(r.get("Flete", r.get("Flete Neto", flete_neto_mxn)) * f_conv, 2),
                    "FSC Cotizado": round(r["FSC"] * f_conv, 2), "Casetas Cotizadas": round(r["Casetas"] * f_conv, 2), 
                    "Ajuste Combustible": round(r.get("Ajuste_Comb", total_ajuste_comb) * f_conv, 2),
                    "Accesorios (Venta)": round(r.get("Accesorios_Venta", total_accesorios_venta) * f_conv, 2),
                    "Detalle Accesorios": r.get("Detalle_Accesorios", nombres_accesorios),
                    "Total MXN": round(ingreso_total_mxn, 2), "Total USD": round(r.get("Total USD", total_usd_neto), 2), 
                    "Margen Flete %": round(margen_flete_pct, 1),
                    "Margen Neto %": round(margen_neto_pct, 1), 
                    "EBITDA": round(r.get("EBITDA", 0) * f_conv, 2),
                    "Utilidad Neta": round(utilidad_neta_mxn * f_conv, 2)
                })
            st.toast("✅ Sábana Financiera Guardada en Historial")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        logo_base64_str = "iVBORw0KGgoAAAANSUhEUgAAAioAAAIqCAMAAAA97pGBAAABAlBMVEX///8EAAZiFxkAAADs0joAAAORkZK2tbY/PkDZ2Nmmpabx2DtZABdDQkNoZmhhFBbu5+dYAADIyMhUU1X19fUIAAuamZpzcnNmGRtsa2zp6elOTU+9vb7k4+Ty8vKAf4EqKCvy698SEBRRAADlyCxfDhgdHB5bAADrzhs1NDXPzs9dBxgWExeLiovTsjR7QB/JpjHjxjivhiuGTyHdvjaPXCOYaSa8lS5wLhzAmy/MqTLXtzVeXV52Ojudd3jbzc6BTU5sKBu4n5/XyMigcih/RSCVZCWpfiqfe3y1jC1rJynGsbKJXF1xMzUjIyREAAB/QxKSZ2irjI2xlJR6OQDBmgUZUAw7AAAV8UlEQVR4nO3dCVfbSLrGcdvCGBsIIRgMBmyGX"
        try:
            img_data = base64.b64decode(logo_base64_str + "===")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(img_data); logo_path = tmp.name
            pdf.image(logo_path, x=5, y=20, w=45); os.remove(logo_path)
        except: pass 
        pdf.set_xy(55, 20); pdf.set_font("Arial", "B", 20); pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 10, empresa_remitente, ln=True, align='L'); pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 14); pdf.cell(0, 8, "COTIZACIÓN", ln=True, align='R')
        pdf.set_font("Arial", "", 10); pdf.cell(0, 5, f"{lugar_expedicion} {fecha_texto}", ln=True, align='R'); pdf.ln(5)
        pdf.set_font("Arial", "B", 10); pdf.cell(0, 5, f"Para. {empresa_cliente}", ln=True)
        pdf.cell(0, 5, f"Atención. {atencion_cliente}", ln=True); pdf.ln(5)
        pdf.set_font("Arial", "", 10); pdf.multi_cell(0, 5, "Por medio de la presente cotización, informo a usted las tarifas que actualmente manejamos en las siguientes rutas y/o servicios:"); pdf.ln(4)
        pdf.set_font("Arial", "B", 8); pdf.set_fill_color(220, 220, 220)
        w_pdf = [35, 35, 20, 15, 20, 20, 20, 25]
        for h in ["Origen", "Destino", "Servicio", "KMS", "Flete", "Casetas", "FSC", f"Total {moneda_tag}"]: 
            pdf.cell(w_pdf[["Origen", "Destino", "Servicio", "KMS", "Flete", "Casetas", "FSC", f"Total {moneda_tag}"].index(h)], 8, h, 1, 0, 'C', True)
        pdf.ln(); pdf.set_font("Arial", "", 8)
        rutas_pdf = st.session_state.rutas_propuesta if st.session_state.rutas_propuesta else [{"Origen": orig, "Destino": dest, "Servicio": tipo_op, "KM": km_final, "Flete": flete_neto_mxn, "Casetas": casetas, "FSC": total_fsc_mxn, "Total MXN": total_mxn_neto}]
        f_conv = (1/tc) if moneda_neg == "USD (Dólares)" else 1
        for r in rutas_pdf:
            pdf.cell(35, 8, r["Origen"][:20], 1, 0, 'C'); pdf.cell(35, 8, r["Destino"][:20], 1, 0, 'C')
            pdf.cell(20, 8, r.get("Servicio", tipo_op)[:12], 1, 0, 'C'); pdf.cell(15, 8, str(r["KM"]), 1, 0, 'C')
            pdf.cell(20, 8, f"${(r['Flete'] * f_conv):,.2f}", 1, 0, 'C'); pdf.cell(20, 8, f"${(r['Casetas'] * f_conv):,.2f}", 1, 0, 'C')
            pdf.cell(20, 8, f"${(r['FSC'] * f_conv):,.2f}", 1, 0, 'C'); pdf.cell(25, 8, f"${(r['Total MXN'] * f_conv):,.2f}", 1, 1, 'C')
        if total_ajuste_comb > 0 or detalle_accesorios:
            pdf.ln(2); pdf.set_font("Arial", "B", 8); pdf.cell(0, 5, f"Cargos Adicionales ({moneda_tag}):", ln=True); pdf.set_font("Arial", "", 8)
            if total_ajuste_comb > 0: pdf.cell(0, 5, f"  - Ajuste de Combustible: ${(total_ajuste_comb * f_conv):,.2f}", ln=True)
            for acc, datos in detalle_accesorios.items(): pdf.cell(0, 5, f"  - {acc} ({datos['cantidad']} mov): ${(datos['venta'] * f_conv):,.2f}", ln=True)
        pdf.ln(3); pdf.set_font("Arial", "B", 9); pdf.cell(0, 5, "Caja Regular", ln=True); pdf.cell(0, 5, "No materiales peligrosos", ln=True); pdf.ln(2); pdf.set_font("Arial", "", 8)
        clausulas_str = "Propuesta vigente por 30 dias para su aceptacion, posteriormente sera valida por 12 meses. Sujeto a disponibilidad de equipo.\n\nEL COSTO POR VARIACION DE DIESEL (FSC) SE ACTUALIZARA DE ACUERDO AL COMPORTAMIENTO DE LOS PRECIOS EN COMBUSTIBLES.\n\nLas tarifas presentadas, son calculadas de acuerdo con la asignacion conjunta de los volumenes por viajes domesticos, de importacion o exportacion.\n\n- Maximo 22 toneladas.\n- Libre de maniobras de carga y descarga.\n- La mercancia viaja asegurada por cuenta y riesgo del cliente.\n- El cliente es responsable por el cuidado de nuestros remolques (daños y robo) tanto con sus proveedores o clientes, como en sus instalaciones.\n- Paradas adicionales, dentro del recorrido natural de la ruta $2,610.00 MXN, en desviaciones, cargo por kilometraje recorrido.\n- Servicios cancelados, tienen costo de $2,610.00 MXN por movimiento en falso.\n- Si no cuentan con sellos de seguridad y requieren que los provea H GT, el costo es de $130.00 MXN cada uno.\n- Maximo tres horas para maniobras de carga y tres para descarga, la hora adicional se factura a $435.00 MXN.\n- Cajas en plantas maximo tres dias para salir cargadas o vacias, a partir del 4to. dia, generan cargos por concepto de demoras $1,045.00 MXN por caja por dia.\n- Cruces en fines de semana y/o dias festivos tienen un costo del 30% adicional.\n- La variacion se actualiza mensualmente.\n- Equipo de sujecion se cobra por aparte.\n- Terminos de pago, 15 dias de credito.\n\nPara mejor servicio, por favor programe con anticipacion sus requerimientos.\nImportes en Moneda Nacional antes de Impuestos. Sujeto a lo dispuesto en la Ley del Impuesto al Valor Agregado."
        pdf.multi_cell(0, 4, clausulas_str); pdf.ln(5); pdf.cell(0, 5, "Esperando recibir su preferencia, quedo a sus ordenes.", ln=True); pdf.ln(8); pdf.set_font("Arial", "B", 9)
        pdf.cell(95, 5, "Atentamente", align='C'); pdf.cell(95, 5, "Acepto Tarifas y Condiciones", align='C', ln=True); pdf.ln(12)
        pdf.cell(95, 5, "___________________________________", align='C'); pdf.cell(95, 5, "___________________________________", align='C', ln=True); pdf.set_font("Arial", "", 9)
        pdf.cell(95, 5, nombre_remitente, align='C'); pdf.cell(95, 5, atencion_cliente, align='C', ln=True)
        pdf.cell(95, 5, empresa_remitente, align='C'); pdf.cell(95, 5, empresa_cliente, align='C', ln=True)
        try: st.download_button("📄 Descargar PDF", pdf.output(dest='S').encode('latin-1'), f"Cotizacion_{empresa_cliente}.pdf", "application/pdf", use_container_width=True)
        except: pass

    with a3:
        wa_text = f"*{empresa_remitente} - COTIZACIÓN*\n\n*Fecha:* {fecha_texto}\n*Para:* {empresa_cliente}\n\n"
        rutas_wa = st.session_state.rutas_propuesta if st.session_state.rutas_propuesta else [{"Origen": orig, "Destino": dest, "KM": km_final, "Total MXN": total_mxn_neto}]
        for r in rutas_wa: wa_text += f"📍 {r['Origen']} a {r['Destino']} ({r['KM']} KMS)\n"
        if total_ajuste_comb > 0: wa_text += f"• *Ajuste de Combustible:* ${total_ajuste_comb:,.2f}\n"
        wa_text += f"\n💰 *TOTAL:* ${gran_total_mxn:,.2f} {moneda_tag}\n\n*Acepto Tarifas y Condiciones*"
        st.markdown(f'<a href="https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_text)}" target="_blank"><button style="background-color:#25D366; color:white; width:100%; padding:10px; border-radius:5px; border:none; font-weight:bold;">📲 WhatsApp</button></a>', unsafe_allow_html=True)

# --- PESTAÑA 2: TABLERO FINANCIERO DIRECTIVO (RAYOS X) ---
with tab_rx:
    st.markdown("## 📊 Radiografía Financiera ")
    if km_final > 0:
        # PISO 1: VISIÓN GENERAL
        st.subheader("1. Visión Directiva General")
        margen_ebitda = (ebitda_viaje_actual / total_mxn_neto) * 100 if total_mxn_neto > 0 else 0
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Ingreso Total (Venta)", f"${total_mxn_neto:,.2f}")
        k2.metric("Egreso Total (Costo Real)", f"${egreso_total_viaje:,.2f}")
        k3.metric("EBITDA (Flujo)", f"${ebitda_viaje_actual:,.2f}", f"{margen_ebitda:.2f}%")
        k4.metric("Utilidad Neta Global", f"${utilidad_neta_viaje_actual:,.2f}", f"{margen_neto_real:.2f}%")
        
        # PISO 2: DIAGNÓSTICO SEPARADO
        st.markdown("---")
        st.subheader("2. Diagnóstico de Rentabilidad Separado")
        col_rx1, col_rx2 = st.columns(2)
        
        with col_rx1:
            with st.container(border=True):
                st.markdown("### 🚛 Operación Transporte (Flete Puro)")
                st.caption("Tarifa Base + FSC + Casetas vs Costos Puros de Rodamiento")
                st.metric("Ingreso por Flete y Ruta", f"${ingreso_flete_total:,.2f}")
                st.metric("Costo Directo Operativo", f"${costo_flete_total:,.2f}")
                color_flete = "normal" if margen_flete_real >= 20.0 else "inverse"
                st.metric("Utilidad Puro Flete", f"${utilidad_flete_mxn:,.2f}", f"{margen_flete_real:.2f}%", delta_color=color_flete)
                
        with col_rx2:
            with st.container(border=True):
                st.markdown("### 📦 Comercialización y Extras")
                st.caption("Venta de Accesorios vs Pago de Servicios a Terceros")
                st.metric("Ingreso por Extras", f"${ingreso_extras_total:,.2f}")
                st.metric("Costo de Extras", f"${costo_extras_total:,.2f}")
                st.metric("Utilidad de Comercialización", f"${utilidad_extras_mxn:,.2f}", f"{margen_extras_real:.2f}%")

        # PISO 3: DESGLOSE ANALÍTICO
        st.markdown("---")
        st.subheader("3. Desglose Analítico")
        with st.expander("🔍 Desglose Completo de Egresos", expanded=True):
            st.write(f"- **Diésel (FSC):** ${total_fsc_mxn:,.2f}")
            st.write(f"- **Peajes/Casetas:** ${casetas:,.2f}")
            st.write(f"- **Sueldo, Carga Social y Op. Fijo:** ${costo_operador:,.2f}")
            st.write(f"- **Costo Real Accesorios:** ${total_accesorios_costo:,.2f}")
            st.write(f"- **Mtto. y Llantas:** ${costo_llantas_mtto:,.2f}")
            st.write(f"- **Gastos Admon. y Fijos:** ${costo_admin_viaje + costo_seg_gps_viaje + costo_deprec_viaje:,.2f}")

# --- PESTAÑA 3: HISTORIAL ---
with tab_hist:
    st.markdown("## 📜 Sábana Financiera de Auditoría")
    if st.session_state.historial: st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)

# --- PESTAÑA 4: CONFIGURACIÓN COMPLETA RESTAURADA ---
with tab_config:
    st.markdown("## ⚙️ Configuración de Costeo Operativo")

    # 1. Variables Operativas
    st.subheader("1. Variables Operativas (Por km / Viaje)")
    col_v1, col_v2, col_v3 = st.columns(3)
    with col_v1:
        st.markdown("**Tramo Largo (>350km)**")
        st.number_input("Llantas Larga ($/km)", key="w_llantas_largo", format="%.2f", step=0.05)
        st.number_input("Mtto Larga ($/km)", key="w_mtto_largo", format="%.2f", step=0.05)
        st.number_input("Gasto Operativo Larga ($/viaje)", key="gasto_op_largo", format="%.2f", step=10.0)
    with col_v2:
        st.markdown("**Tramo Corto (<=350km)**")
        st.number_input("Llantas Corta ($/km)", key="w_llantas_corto", format="%.2f", step=0.05)
        st.number_input("Mtto Corta ($/km)", key="w_mtto_corto", format="%.2f", step=0.05)
        st.number_input("Gasto Operativo Corta ($/viaje)", key="gasto_op_corto", format="%.2f", step=10.0)
    with col_v3:
        st.markdown("**Sueldos y Administrativos**")
        st.number_input("Sueldo Operador Base ($/km)", key="w_operador", format="%.4f", step=0.05)
        st.number_input("Carga Social Operador (%)", key="w_carga_soc", format="%.2f", step=1.0)
        st.number_input("Gasto Administrativo ($/km)", key="w_admin", format="%.2f", step=0.5)

    st.markdown("---")
    
    # 2. Costos Fijos, Seguros y GPS
    st.subheader("2. Costos Fijos Mensuales")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1: st.number_input("Seguro Equipo Mensual ($)", key="w_seguro", format="%.2f", step=100.0)
    with col_f2: st.number_input("GPS Tracto Mensual ($)", key="w_gps_tracto", format="%.2f", step=50.0)
    with col_f3: st.number_input("GPS Caja Mensual ($)", key="w_gps_caja", format="%.2f", step=50.0)

    st.markdown("---")

    # 3. Equipos y Depreciación
    st.subheader("3. Equipos y Depreciación")
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.markdown("**Tractor**")
        st.number_input("Valor Adquisición Tractor ($)", key="valor_tractor", format="%.2f", step=50000.0)
        st.number_input("Valor Residual Tractor ($)", key="residual_tractor", format="%.2f", step=10000.0)
        st.number_input("Vida Útil Tractor (Años)", key="vida_tractor", step=1)
        dep_mensual_tracto = (st.session_state.valor_tractor - st.session_state.residual_tractor) / (st.session_state.vida_tractor * 12) if st.session_state.vida_tractor > 0 else 0
        st.info(f"📉 Depreciación Mensual: **${dep_mensual_tracto:,.2f}**")
        
    with col_e2:
        st.markdown("**Caja (Remolque)**")
        st.number_input("Valor Adquisición Caja ($)", key="valor_caja", format="%.2f", step=50000.0)
        st.number_input("Valor Residual Caja ($)", key="residual_caja", format="%.2f", step=10000.0)
        st.number_input("Vida Útil Caja (Años)", key="vida_caja", step=1)
        dep_mensual_caja = (st.session_state.valor_caja - st.session_state.residual_caja) / (st.session_state.vida_caja * 12) if st.session_state.vida_caja > 0 else 0
        st.info(f"📉 Depreciación Mensual: **${dep_mensual_caja:,.2f}**")

    st.markdown("---")

    # 4. Metas de Kilometraje
    st.subheader("4. Metas de Kilometraje Mensual (Para prorrateo)")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("**Tractor**")
        st.number_input("Meta KM/Mes Tracto (Largo)", key="km_mes_tracto_largo", format="%.2f", step=500.0)
        st.number_input("Meta KM/Mes Tracto (Corto)", key="km_mes_tracto_corto", format="%.2f", step=500.0)
    with col_m2:
        st.markdown("**Caja**")
        st.number_input("Meta KM/Mes Caja (Largo)", key="km_mes_caja_largo", format="%.2f", step=500.0)
        st.number_input("Meta KM/Mes Caja (Corto)", key="km_mes_caja_corto", format="%.2f", step=500.0)

    st.markdown("---")

    # 5. Márgenes de Accesorios
    st.subheader("5. Márgenes de Comercialización Extras")
    col_ma1, col_ma2 = st.columns(2)
    with col_ma1: st.number_input("Margen Comercialización Cruces (%)", key="margen_cruce", format="%.2f", step=1.0)
    with col_ma2: st.number_input("Margen Comercialización Otros Accesorios (%)", key="margen_accesorios", format="%.2f", step=1.0)

    # --- SECCIÓN DE APRENDIZAJE VISUAL DE RUTAS ---
    st.markdown("---")
    st.subheader("🛣️ Aprendizaje de Nuevas Rutas (Peajes)")
    st.info("Si una ruta no arroja casetas en automático, tu equipo puede buscarla en GMap y enseñársela al sistema aquí. (El sistema le quitará el IVA solo, tú pon el costo final que te arroje la página).")
    
    col_r1, col_r2, col_r3 = st.columns([2, 2, 1])
    with col_r1: nueva_ciudad = st.text_input("Nombre de la Ciudad (Ej: San Luis Potosi)")
    with col_r2: nuevo_peaje = st.number_input("Costo Total GMap CON IVA ($)", min_value=0.0, step=50.0)
    with col_r3:
        st.write("") 
        st.write("")
        if st.button("💾 Enseñar Ruta"):
            if nueva_ciudad and nuevo_peaje >= 0:
                st.session_state.matriz_peajes_dinamica[nueva_ciudad.lower()] = nuevo_peaje
                st.success(f"¡Ruta a {nueva_ciudad} aprendida por el sistema!")
    
    with st.expander("Ver Rutas Memorizadas Actualmente"): st.write(st.session_state.matriz_peajes_dinamica)
