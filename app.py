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
    st.error("⚠️ Error: Revisa tu archivo 'secrets.toml'.")

st.set_page_config(page_title="Cotizador Maestro Logístico", layout="wide")

if 'historial' not in st.session_state:
    st.session_state.historial = []

# --- 2. BASE DE DATOS DE REFERENCIA ---
datos_referencia = [
    ["EXPO", "MTY-AREA METRO", "NUEVO LAREDO", 230, 26.00, 34.67],
    ["EXPO", "SALTILLO - RAMOS", "NUEVO LAREDO", 310, 24.00, 32.00],
    ["EXPO", "DERRAMADERO", "NUEVO LAREDO", 380, 25.00, 33.33],
    ["IMPO", "NUEVO LAREDO", "MTY-AREA METRO", 230, 31.10, 41.46],
    ["IMPO", "NUEVO LAREDO", "SALTILLO - RAMOS", 310, 28.00, 37.33],
    ["IMPO", "NUEVO LAREDO", "DERRAMADERO", 380, 28.10, 37.47]
]
df_ref = pd.DataFrame(datos_referencia, columns=["Tipo", "Origen", "Destino", "KM_Ref", "CPK_Base", "IPK_Ref"])

# --- 3. BARRA LATERAL (PREMISAS) ---
with st.sidebar:
    st.header("👤 Datos del Cliente")
    nombre_cliente = st.text_input("Nombre del Cliente", "Cliente General")
    tipo_operacion = st.selectbox("Tipo de Operación", ["EXPO", "IMPO"])
    
    st.markdown("---")
    st.header("⚙️ Premisas de Venta")
    
    rutas_filtro = df_ref[df_ref["Tipo"] == tipo_operacion]
    ruta_sel = st.selectbox("Ruta de Referencia (Tabla)", 
                            rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"])
    
    datos_ruta = rutas_filtro[(rutas_filtro["Origen"] + " -> " + rutas_filtro["Destino"]) == ruta_sel].iloc[0]
    
    # Habilitar manipulación manual de CPK e IPK
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        cpk_manual = st.number_input("CPK Manual ($)", value=float(datos_ruta["CPK_Base"]), step=0.1)
    with col_p2:
        ipk_manual = st.number_input("IPK Manual ($)", value=float(datos_ruta["IPK_Ref"]), step=0.1)

    margen_utilidad = st.slider("Margen de Utilidad (%)", 0, 100, 25)
    tipo_cambio = st.number_input("Tipo de Cambio (USD/MXN)", value=17.00, step=0.1)
    
    st.markdown("---")
    telefono_wa = st.text_input("WhatsApp (ej: 521...)", "")

# --- 4. DISEÑO POR PESTAÑAS ---
tab_cotizador, tab_historial = st.tabs(["🎯 Cotizador", "📜 Historial Detallado"])

with tab_cotizador:
    st.header(f"Cotización {tipo_operacion}: {nombre_cliente}")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        origen_in = st.text_input("Origen", datos_ruta["Origen"])
    with col_r2:
        destino_in = st.text_input("Destino", datos_ruta["Destino"])

    distancia_km = 0
    if origen_in and destino_in:
        try:
            res = gmaps.directions(origen_in, destino_in, mode="driving")
            if res:
                distancia_km = res[0]['legs'][0]['distance']['value'] / 1000
                st.success(f"🛣️ Distancia Real Detectada: {distancia_km:.2f} km")
                
                # REINSTALACIÓN DEL MAPA
                map_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(origen_in)}&destination={urllib.parse.quote(destino_in)}&mode=driving"
                st.markdown(f'<iframe width="100%" height="400" frameborder="0" style="border:0" src="{map_url}" allowfullscreen></iframe>', unsafe_allow_html=True)
        except:
            distancia_km = float(datos_ruta["KM_Ref"])
            st.warning(f"No se pudo cargar el mapa. Usando KM de tabla: {distancia_km} km")

    st.markdown("---")
    
    with st.expander("💰 Gastos Adicionales"):
        gc1, gc2 = st.columns(2)
        with gc1:
            c_casetas = st.number_input("Casetas ($)", min_value=0.0)
            c_maniobras = st.number_input("Maniobras ($)", min_value=0.0)
            c_cpac = st.number_input("CPAC ($)", min_value=0.0)
        with gc2:
            e1_n = st.text_input("Concepto Extra 1", "Cruce"); e1_v = st.number_input("Monto Cruce", key="v1")
            e2_n = st.text_input("Concepto Extra 2", "Seguro"); e2_v = st.number_input("Monto Seguro", key="v2")

    # --- LÓGICA FINANCIERA ---
    # Si el usuario manipula el CPK manual, el flete se basa en ese valor + margen
    # O si prefiere guiarse puramente por el IPK manual
    flete_base = distancia_km * cpk_manual
    flete_con_margen = flete_base * (1 + (margen_utilidad / 100))
    
    # Calculamos el IPK resultante real
    ipk_final_real = flete_con_margen / distancia_km if distancia_km > 0 else 0
    
    suma_gastos = c_casetas + c_maniobras + c_cpac + e1_v + e2_v
    venta_total_mxn = flete_con_margen + suma_gastos
    venta_total_usd = venta_total_mxn / tipo_cambio

    # --- MÉTRICAS ---
    res_a, res_b, res_c = st.columns(3)
    res_a.metric("VENTA TOTAL MXN", f"${venta_total_mxn:,.2f}")
    res_b.metric("VENTA TOTAL USD", f"${venta_total_usd:,.2f}")
    
    # Delta comparativo con el IPK manual definido en premisas
    delta_ipk = ipk_final_real - ipk_manual
    res_c.metric("IPK REAL", f"${ipk_final_real:.2f}", delta=f"{delta_ipk:.2f} vs Objetivo")

    # --- ACCIONES ---
    st.markdown("### 📤 Finalizar")
    a1, a2, a3 = st.columns(3)
    
    with a1:
        if st.button("💾 Guardar en Historial", use_container_width=True):
            st.session_state.historial.insert(0, {
                "Fecha": datetime.now().strftime("%H:%M"),
                "Cliente": nombre_cliente,
                "Ruta": f"{origen_in}-{destino_in}",
                "IPK": f"${ipk_final_real:.2f}",
                "Total MXN": f"${venta_total_mxn:,.2f}"
            })
            st.toast("Guardado!")

    with a2:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f"COTIZACION: {nombre_cliente}", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 10, f"Ruta: {origen_in} a {destino_in} ({distancia_km} km)", ln=True)
        pdf.cell(0, 10, f"Flete Neto: ${flete_con_margen:,.2f} MXN", ln=True)
        pdf.cell(0, 10, f"Total con Gastos: ${venta_total_mxn:,.2f} MXN", ln=True)
        
        pdf_out = pdf.output(dest='S').encode('latin-1')
        st.download_button("📄 Descargar PDF", pdf_out, f"Cot_{nombre_cliente}.pdf", "application/pdf", use_container_width=True)

    with a3:
        wa_msg = f"*COTIZACIÓN*\n*Cliente:* {nombre_cliente}\n*Ruta:* {origen_in}-{destino_in}\n*Total:* ${venta_total_mxn:,.2f} MXN"
        st.markdown(f'<a href="https://wa.me/{telefono_wa}?text={urllib.parse.quote(wa_msg)}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; width:100%; cursor:pointer; font-weight:bold;">📲 Enviar WhatsApp</button></a>', unsafe_allow_html=True)

with tab_historial:
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
