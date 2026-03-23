import streamlit as st
import googlemaps
from fpdf import FPDF
import urllib.parse
import pandas as pd
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN ---
try:
    api_key = st.secrets["MAPS_API_KEY"]
    gmaps = googlemaps.Client(key=api_key)
except Exception:
    st.error("⚠️ Configura 'MAPS_API_KEY' en secrets.toml")

st.set_page_config(page_title="Cotizador Maestro 53' Pro - Consolidado", layout="wide")

if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- DICCIONARIO DE COSTOS DE ACCESORIOS ---
precios_accesorios = {
    "Ninguno": 0.0,
    "FIANZA": 330.00,
    "CARGA / DESCARGA EN VIVO": 500.00,
    "DEMORAS": 935.00,
    "CRUCE": 2341.75,
    "POSICIONAMIENTO": 1190.00,
    "LAVADO DE CAJA": 170.00,
    "FUMIGACION": 552.50,
    "BASCULA": 935.00,
    "EQUIPO DE SUJECION": 595.00
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
    st.header("👤 Operación")
    nombre_cliente = st.text_input("Cliente", "Cliente General")
    tipo_op = st.selectbox("Operación", ["EXPO", "IMPO"])
    tc = st.number_input("Tipo de Cambio (MXN/USD)", value=17.50, step=0.1)
    
    st.markdown("---")
    st.header("⚙️ Negociación")
    moneda_neg = st.radio("Cerrar trato en:", ["MXN (Pesos)", "USD (Dólares)"])
    
    rutas_filtro = df_ref[df_ref["Tipo"] == tipo_op]
    texto_manual = "Manual (Ruta Nueva)"
    opciones = [texto_manual] + (rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]).tolist()
    ruta_sel = st.selectbox("Ruta de Tabla:", opciones)
    
    # Valores sugeridos iniciales
    cpk_init, km_init, orig_sug, dest_sug = 25.0, 1.0, "Monterrey", "Nuevo Laredo"

    if ruta_sel != texto_manual:
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
    
    km_final = st.number_input("KM de Ruta (Ajuste 53')", value=km_init, key="km_input_main") 

    col_ruta, col_extras = st.columns([2, 1])

    with col_ruta:
        st.subheader("📍 Ruta y Mapa")
        c1, c2 = st.columns(2)
        orig, dest = c1.text_input("Origen", orig_sug), c2.text_input("Destino", dest_sug)
        
        try:
            res = gmaps.directions(orig, dest)
            if res:
                 m_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dest)}"
                 st.markdown(f'<iframe width="100%" height="250" src="{m_url}" style="border-radius:10px; border: 1px solid #ddd;"></iframe>', unsafe_allow_html=True)
        except: 
            st.info("Mapa no disponible (Verifica API Key o Ruta)")

    with col_extras:
        st.subheader("💰 Cargos Extra y Accesorios")
        with st.container(border=True):
            # Cargo Fijo Base
            casetas = st.number_input("Casetas Grales. (Ruta)", 0.0)
            
            st.markdown("---")
            st.markdown("**Listado de Accesorios**")
            
            # --- LÓGICA DE CARGOS ADICIONALES AUTOMATIZADA ---
            tipo_cargo_adicional = st.selectbox("Selecciona el Accesorio", list(precios_accesorios.keys()))
            
            cantidad_cargo = 0.0
            costo_cargo = 0.0
            total_cargo_adicional = 0.0
            
            if tipo_cargo_adicional != "Ninguno":
                costo_default = precios_accesorios[tipo_cargo_adicional]
                
                col_c1, col_c2 = st.columns(2)
                cantidad_cargo = col_c1.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
                # El valor por defecto se jala del diccionario, pero el usuario lo puede editar
                costo_cargo = col_c2.number_input("Costo Unitario ($)", min_value=0.0, value=float(costo_default), step=50.0)
                
                total_cargo_adicional = cantidad_cargo * costo_cargo
                st.caption(f"Subtotal de {tipo_cargo_adicional}: **${total_cargo_adicional:,.2f}**")

            total_extras_mxn = casetas + total_cargo_adicional

        # CÁLCULOS OPERATIVOS PUROS
        flete_neto_mxn = km_final * ipk_mxn_final
        total_mxn_neto = flete_neto_mxn + total_extras_mxn
        total_usd_neto = total_mxn_neto / tc

        with st.expander("📄 Ver Desglose Operativo (MXN)", expanded=False):
            st.write(f"Flete Base: **${flete_neto_mxn:,.2f}**")
            st.write(f"(+) Casetas: **${casetas:,.2f}**")
            if total_cargo_adicional > 0:
                st.write(f"(+) {tipo_cargo_adicional}: **${total_cargo_adicional:,.2f}**")
            st.write(f"**Total Extras: ${total_extras_mxn:,.2f}**")

    # --- FILA 2: METRICAS GRANDES (KPIs) ---
    st.markdown("---")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.metric(label="TOTAL OPERATIVO MXN", value=f"${total_mxn_neto:,.2f}")
    
    with kpi2:
        st.metric(label="TOTAL OPERATIVO USD", value=f"${total_usd_neto:,.2f}", delta=f"TC: {tc}")

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
            label="Margen Real", 
            value=f"{margen_real:.1f}%", 
            delta=f"{margen_real - 25:.1f}% vs Obj (25%)",
            delta_color=color_delta
        )

    # --- FILA 3: ACCIONES ---
    st.markdown("---")
    st.subheader("🚀 Acciones")
    a1, a2, a3 = st.columns(3)

    with a1:
        if st.button("💾 Guardar Historial", use_container_width=True, type="primary"):
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Cliente": nombre_cliente,
                "Ruta": f"{orig}-{dest}",
                "KM": km_final,
                "Moneda": moneda_tag,
                "IPK Pactado": round(ipk_pactado, 2),
                "CPK Base": round(cpk_base, 2),
                "CPAC": round(cpac, 2),
                "E1": round(e1, 2),
                "E2": round(e2, 2),
                "Casetas": round(casetas, 2),
                "Accesorio": tipo_cargo_adicional,
                "Cant. Accesorio": cantidad_cargo,
                "Costo Unit. Accesorio": round(costo_cargo, 2),
                "Total Accesorio": round(total_cargo_adicional, 2),
                "TC": tc,
                "Total Operativo MXN": round(total_mxn_neto, 2),
                "Margen %": round(margen_real, 1)
            })
            st.toast(f"✅ Guardado con éxito en {moneda_tag}")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"COTIZACION OPERATIVA: {nombre_cliente}", ln=True, align='C')
        pdf.set_font("Arial", size=11); pdf.ln(5)
        pdf.cell(0, 7, f"Ruta: {orig} - {dest} ({km_final} km)", ln=True)
        pdf.cell(0, 7, f"IPK Pactado: ${ipk_pactado:.2f} {moneda_tag}", ln=True)
        pdf.ln(3); pdf.set_font("Arial", "B", 11); pdf.cell(0, 7, "DESGLOSE DE SERVICIO (MXN):", ln=True); pdf.set_font("Arial", size=11)
        pdf.cell(0, 7, f"Flete Base: ${flete_neto_mxn:,.2f}", ln=True)
        pdf.cell(0, 7, f"Casetas Grales: ${casetas:,.2f}", ln=True)
        if total_cargo_adicional > 0:
            pdf.cell(0, 7, f"{tipo_cargo_adicional} ({cantidad_cargo} x ${costo_cargo}): ${total_cargo_adicional:,.2f}", ln=True)
        pdf.ln(5); pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 10, f"TOTAL A PAGAR (Sin Impuestos): ${total_mxn_neto:,.2f} MXN", ln=True)
        pdf.cell(0, 10, f"TOTAL USD (TC {tc}): ${total_usd_neto:,.2f}", ln=True)
        try:
            pdf_out = pdf.output(dest='S').encode('latin-1')
            st.download_button("📄 Descargar PDF", pdf_out, f"Cot_{orig}.pdf", "application/pdf", use_container_width=True)
        except:
            st.error("Error generando PDF (caracteres especiales)")

    with a3:
        wa_text = f"*COTIZACIÓN*\n*Cliente:* {nombre_cliente}\n*Ruta:* {orig}-{dest}\n*KM:* {km_final}\n\n*Total:* ${total_mxn_neto:,.2f} MXN (Libre de impuestos)"
        if total_cargo_adicional > 0:
            wa_text += f"\n*Incluye:* {tipo_cargo_adicional}"
            
        st.markdown(f'<a href="https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_text)}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 WhatsApp</button></a>', unsafe_allow_html=True)

with tab_hist:
    st.subheader("📜 Auditoría Detallada")
    if st.session_state.historial:
        df_full = pd.DataFrame(st.session_state.historial)
        st.dataframe(df_full, use_container_width=True)
        csv = df_full.to_csv(index=False).encode('utf-8')
        st.download_button("📊 Exportar Historial (CSV)", csv, "historial_completo.csv", "text/csv")
    else:
        st.info("Aún no hay cotizaciones guardadas.")
