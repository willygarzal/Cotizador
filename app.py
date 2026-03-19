import streamlit as st
import pandas as pd
import googlemaps
import os
import urllib.parse
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
GMAPS_KEY = "AIzaSyDbSp-IUd-5eTyrKVTOX5oDtcB-_1C_PVc" 
gmaps = googlemaps.Client(key=GMAPS_KEY)

CSV_FILE = "historial_cotizaciones.csv"

# Función para cargar historial
def cargar_datos():
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    return pd.DataFrame(columns=["Fecha", "Cliente", "Operacion", "Origen", "Destino", "KM", "Tarifa_MXN"])

if 'df_rutas' not in st.session_state:
    st.session_state.df_rutas = cargar_datos()

# --- 2. SIDEBAR (Premisas) ---
st.sidebar.header("📊 Premisas Operativas")
tc = st.sidebar.number_input("Tipo de Cambio", value=17.50)
margen = st.sidebar.slider("Margen %", 5, 100, 20)
cpk = st.sidebar.number_input("Costo Fijo (CPK)", value=15.0)
diesel = st.sidebar.number_input("Costo Diesel", value=24.50)
rend = st.sidebar.number_input("Rendimiento (KM/L)", value=2.2)

# --- 3. INTERFAZ PRINCIPAL ---
st.title("🚛 Cotizador Logístico Pro")
tab1, tab2 = st.tabs(["🎯 Cotizador", "📜 Historial"])

with tab1:
    # 👤 Datos del Cliente
    nombre_cliente = st.text_input("👤 Nombre del Cliente / Empresa:", placeholder="Ej. Logística Global")
    
    # 🔄 Tipo de Operación y Modo
    col_op, col_modo = st.columns(2)
    with col_op:
        tipo_op = st.radio("Tipo de Operación:", ["EXPO", "IMPO"], horizontal=True)
    with col_modo:
        modo_ruta = st.toggle("Nueva ruta (Google Maps)", value=False)

    distancia = 0.0
    origen_final = ""
    destino_final = ""

    if modo_ruta:
        o_input = st.text_input("📍 Punto de Origen:")
        d_input = st.text_input("🏁 Punto de Destino:")
        
        if st.button("🔍 Calcular Trayecto"):
            try:
                # Directions API es la más precisa para rutas por carretera
                directions = gmaps.directions(o_input, d_input, mode="driving", region="mx", language="es")
                
                if directions:
                    leg = directions[0]['legs'][0]
                    # Guardamos TODO en el session_state para que no desaparezca
                    st.session_state['data_ruta'] = {
                        "km": leg['distance']['value'] / 1000,
                        "o_limpio": leg['start_address'],
                        "d_limpio": leg['end_address']
                    }
                    st.success("Ruta calculada con éxito.")
                else:
                    st.error("No se encontró una ruta válida.")
            except Exception as e:
                st.error(f"Error de Google: {e}")

        # Si ya se calculó, recuperamos los datos
        if 'data_ruta' in st.session_state:
            distancia = st.session_state['data_ruta']['km']
            origen_final = st.session_state['data_ruta']['o_limpio']
            destino_final = st.session_state['data_ruta']['d_limpio']
    else:
        # Modo: Seleccionar del historial/frecuentes
        if not st.session_state.df_rutas.empty:
            df_u = st.session_state.df_rutas.drop_duplicates(subset=['Origen', 'Destino']).copy()
            df_u["Etiqueta"] = df_u["Origen"] + " ➡️ " + df_u["Destino"]
            sel = st.selectbox("Selecciona ruta frecuente:", df_u["Etiqueta"])
            fila = df_u[df_u["Etiqueta"] == sel].iloc[0]
            distancia = fila["KM"]
            origen_final = fila["Origen"]
            destino_final = fila["Destino"]
        else:
            st.warning("No hay rutas guardadas. Usa 'Nueva ruta' primero.")

    # --- MOSTRAR RESULTADOS Y MAPA ---
    if distancia > 0:
        # Cálculos Financieros
        costo_comb = (distancia / rend) * diesel
        costo_op = (distancia * cpk) + costo_comb
        precio_mxn = costo_op * (1 + (margen / 100))
        precio_usd = precio_mxn / tc

        st.divider()
        st.subheader(f"Cotización: {nombre_cliente if nombre_cliente else 'Cliente Particular'}")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Distancia", f"{distancia:,.2f} KM")
        c2.metric("Precio MXN", f"${precio_mxn:,.2f}")
        c3.metric("Precio USD", f"${precio_usd:,.2f}")

        # --- MAPA SINCRONIZADO ---
        st.subheader("🗺️ Mapa de la Ruta")
        # Usamos las direcciones "limpias" de Google para que el mapa no se pierda
        map_url = (
            f"https://www.google.com/maps/embed/v1/directions"
            f"?key={GMAPS_KEY}"
            f"&origin={urllib.parse.quote(origen_final)}"
            f"&destination={urllib.parse.quote(destino_final)}"
            f"&mode=driving"
        )
        st.components.v1.html(f'<iframe width="100%" height="400" src="{map_url}" style="border:0; border-radius:10px;"></iframe>', height=410)

        # --- BOTONES DE GUARDADO Y WHATSAPP ---
        col_g, col_w = st.columns(2)
        with col_g:
            if st.button("💾 Guardar en Historial"):
                nueva = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Cliente": nombre_cliente if nombre_cliente else "N/A",
                    "Operacion": tipo_op,
                    "Origen": origen_final,
                    "Destino": destino_final,
                    "KM": round(distancia, 2),
                    "Tarifa_MXN": round(precio_mxn, 2)
                }])
                st.session_state.df_rutas = pd.concat([st.session_state.df_rutas, nueva], ignore_index=True)
                st.session_state.df_rutas.to_csv(CSV_FILE, index=False)
                st.success("¡Cotización guardada!")
        
        with col_w:
            tel = st.text_input("Teléfono (ej: 521...):")
            msg = f"*COTIZACIÓN LOGÍSTICA*\n👤 *Cliente:* {nombre_cliente}\n🛣️ *KM:* {distancia:,.2f}\n💰 *Tarifa:* ${precio_mxn:,.2f} MXN"
            st.link_button("🟢 Enviar por WhatsApp", f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}")

with tab2:
    st.subheader("📜 Historial de Cotizaciones")
    # Editor de datos para corregir o borrar
    st.session_state.df_rutas = st.data_editor(st.session_state.df_rutas, num_rows="dynamic")
    if st.button("Actualizar Historial"):
        st.session_state.df_rutas.to_csv(CSV_FILE, index=False)
        st.success("Cambios aplicados al archivo.")
