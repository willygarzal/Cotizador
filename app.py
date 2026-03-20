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

# --- 2. BARRA LATERAL (PREMISAS) ---
with st.sidebar:
    st.header("👤 Datos del Cliente")
    nombre_cliente = st.text_input("Nombre del Cliente", "Cliente General")
    tipo_operacion = st.selectbox("Tipo de Operación", ["EXPO", "IMPO"])
    
    st.markdown("---")
    st.header("⚙️ Premisas de Venta")
    cpk_objetivo = st.number_input("CPK Objetivo ($)", min_value=0.0, value=28.0, step=0.5)
    margen_utilidad = st.slider("Margen de Utilidad (%)", 0, 100, 25)
    tipo_cambio = st.number_input("Tipo de Cambio (USD/MXN)", value=18.50, step=0.1)
    
    st.markdown("---")
    st.subheader("📊 Tabla de Referencia")
    df_ref = pd.DataFrame([
        ["EXPO", "MTY-METRO", "N. LAREDO", 230, 26.0],
        ["EXPO", "SALTILLO", "N. LAREDO", 310, 24.0],
        ["IMPO", "N. LAREDO", "MTY-METRO", 230, 31.1],
        ["IMPO", "N. LAREDO", "SALTILLO", 310, 28.0]
    ], columns=["Tipo", "Origen", "Destino", "KM", "CPK"])
    st.dataframe(df_ref, hide_index=True)
    
    telefono_wa = st.text_input("WhatsApp (ej: 521...)", "")

# --- 3. DISEÑO POR PESTAÑAS ---
tab_cotizador, tab_historial = st.tabs(["🎯 Cotizador", "📜 Historial Detallado"])

with tab_cotizador:
    st.header(f"Cotización {tipo_operacion}: {nombre_cliente}")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        origen_in = st.text_input("Origen", "Monterrey, NL")
    with col_r2:
        destino_in = st.text_input("Destino", "Nuevo Laredo, Tamps")

    distancia_km = 0
    if origen_in and destino_in:
        try:
            res = gmaps.directions(origen_in, destino_in, mode="driving")
            if res:
                distancia_km = res[0]['legs'][0]['distance']['value'] / 1000
                st.success(f"🛣️ Distancia: {distancia_km:.2f} km")
                
                # Mapa de Google Maps
                map_url = f"https://www.google.com/maps/embed/v1/directions?key={api_key}&origin={urllib.parse.quote(origen_in)}&destination={urllib.parse.quote(destino_in)}&mode=driving"
                st.markdown(f'<iframe width="100%" height="400" frameborder="0" style="border:0" src="{map_url}" allowfullscreen></iframe>', unsafe_allow_html=True)
        except:
            st.warning("Verifica las ciudades para mostrar el mapa.")

    st.markdown("---")
    
    with st.expander("💰 Configurar Gastos y Cargos Adicionales (Opcional)"):
        gc1, gc2 = st.columns(2)
        with gc1:
            st.write
