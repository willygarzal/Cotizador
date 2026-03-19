import streamlit as st
import pandas as pd
import googlemaps
import os
import urllib.parse
from datetime import datetime
from fpdf import FPDF

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
try:
    GMAPS_KEY = st.secrets["MAPS_API_KEY"]
except (FileNotFoundError, KeyError):
    st.error("⚠️ Falta configurar MAPS_API_KEY en los Secrets de Streamlit.")
    st.stop()

gmaps = googlemaps.Client(key=GMAPS_KEY)
CSV_FILE = "historial_cotizaciones.csv"

# --- FUNCIÓN PARA GENERAR EL PDF ---
def crear_pdf(cliente, origen, destino, km, extras, precio_mxn):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "COTIZACION DE SERVICIOS LOGISTICOS", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(10)
    
    pdf.set_font("helvetica", "", 12)
    cliente_str = cliente if cliente else "Cliente Particular"
    
    pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"Atencion a: {cliente_str}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.cell(0, 10, f"Origen: {origen[:60]}", new_x="LMARGIN", new_y="NEXT") 
    pdf.cell(0, 10, f"Destino: {destino[:60]}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"Distancia Total: {km:,.2f} KM", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"Cargos Adicionales (Casetas, etc): ${extras:,.2f} MXN", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, f"TARIFA TOTAL: ${precio_mxn:,.2f} MXN", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(20)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 10, "* Cotizacion sujeta a disponibilidad de unidades y cambios sin previo aviso.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "* Los precios no incluyen IVA.", new_x="LMARGIN", new_y="NEXT")
    
    return bytes(pdf.output())

# --- FUNCIÓN PARA CARGAR HISTORIAL ---
def cargar_datos():
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    return pd.DataFrame(columns=["Fecha", "Cliente", "Operacion", "Origen", "Destino", "KM", "Extras_MXN", "Tarifa_MXN"])

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
    nombre_cliente = st.text_input("👤 Nombre del Cliente / Empresa:", placeholder="Ej. Logística Global")
    
    col_op, col_modo = st.columns(2)
    with col_op:
        tipo_op = st.radio("Tipo de Operación:", ["EXPO", "IMPO"], horizontal=True)
    with col_modo:
        modo_ruta = st.toggle("Nueva ruta (Google Maps)", value=False)

    distancia = 0.0
    origen_final = ""
    destino_final = ""

    # SELECCIÓN DE RUTA
    if modo_ruta:
        o_input = st.text_input("📍 Punto de Origen:")
        d_input = st.text_input("🏁 Punto de Destino:")
        
        if st.button("🔍 Calcular Trayecto"):
            try:
                directions = gmaps.directions(o_input, d_input, mode="driving", region="mx", language="es")
                if directions:
                    leg = directions[0]['legs'][0]
                    st.session_state['data_ruta'] = {
                        "km": leg['distance']['value'] / 1000,
                        "o_limpio": leg['start_address'],
                        "d_limpio": leg['end_address']
                    }
                    st.success("✅ Ruta calculada con éxito.")
                else:
                    st.error("❌ No se encontró una ruta válida.")
            except Exception as e:
                st.error(f"Error de Google: {e}")

        if 'data_ruta' in st.session_state:
            distancia = st.session_state['data_ruta']['km']
            origen_final = st.session_state['data_ruta']['o_limpio']
            destino_final = st.session_state['data_ruta']['d_limpio']
            
    else:
        if not st.session_state.df_rutas.empty:
            df_u = st.session_state.df_rutas.drop_duplicates(subset=['Origen', 'Destino']).copy()
            df_u["Etiqueta"] = df_u["Origen"] + " ➡️ " + df_u["Destino"]
            sel = st.selectbox("Selecciona ruta frecuente:", df_u["Etiqueta"])
            fila = df_u[df_u["Etiqueta"] == sel].iloc[0]
            distancia = float(fila["KM"])
            origen_final = fila["Origen"]
            destino_final = fila["Destino"]
        else:
            st.warning("No hay rutas guardadas. Usa 'Nueva ruta' primero para guardar una.")

    # --- SECCIÓN: CARGOS ADICIONALES (Siempre visible) ---
    st.divider()
    st.subheader("➕ Cargos Adicionales (MXN)")
    col_ext1, col_ext2, col_ext3 = st.columns(3)
    
    with col_ext1:
        casetas = st.number_input("🛣️ Casetas / Peajes", min_value=0.0, value=0.0, step=50.0)
    with col_ext2:
        maniobras = st.number_input("🏗️ Maniobras", min_value=0.0, value=0.0, step=100.0)
    with col_ext3:
        seguro_otros = st.number_input("🛡️ Seguro / Otros", min_value=0.0, value=0.0, step=100.0)

    total_extras = casetas + maniobras + seguro_otros

    # --- MOSTRAR RESULTADOS Y BOTONES (Se activa al tener KM) ---
    if distancia > 0:
        costo_comb = (distancia / rend) * diesel
        costo_ruta_base = (distancia * cpk) + costo_comb
        costo_operativo_total = costo_ruta_base + total_extras
        
        precio_mxn = costo_operativo_total * (1 + (margen / 100))
        precio_usd = precio_mxn / tc

        st.divider()
        st.subheader(f"Cotización Final: {nombre_cliente if nombre_cliente else 'Cliente Particular'}")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Distancia", f"{distancia:,.2f} KM")
        c2.metric("Extras sumados", f"${total_extras:,.2f}")
        c3.metric("Precio MXN", f"${precio_mxn:,.2f}")
        c4.metric("Precio USD", f"${precio_usd:,.2f}")

        st.subheader("🗺️ Mapa de la Ruta")
        map_url = (
            f"https://www.google.com/maps/embed/v1/directions"
            f"?key={GMAPS_KEY}"
            f"&origin={urllib.parse.quote(origen_final)}"
            f"&destination={urllib.parse.quote(destino_final)}"
            f"&mode=driving"
        )
        st.components.v1.html(f'<iframe width="100%" height="400" src="{map_url}" style="border:0; border-radius:10px;"></iframe>', height=410)

        # --- AQUÍ ESTÁN LOS 3 BOTONES ---
        col_g, col_w, col_p = st.columns(3)
        with col_g:
            if st.button("💾 Guardar"):
                nueva = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Cliente": nombre_cliente if nombre_cliente else "N/A",
                    "Operacion": tipo_op,
                    "Origen": origen_final,
                    "Destino": destino_final,
                    "KM": round(distancia, 2),
                    "Extras_MXN": round(total_extras, 2),
                    "Tarifa_MXN": round(precio_mxn, 2)
                }])
                st.session_state.df_rutas = pd.concat([st.session_state.df_rutas, nueva], ignore_index=True)
                st.session_state.df_rutas.to_csv(CSV_FILE, index=False)
                st.success("¡Guardada!")
        
        with col_w:
            tel = st.text_input("Teléfono (ej: 521...):")
            msg = f"*COTIZACIÓN LOGÍSTICA*\n👤 *Cliente:* {nombre_cliente}\n🛣️ *Ruta:* {origen_final} a {destino_final}\n📏 *KM:* {distancia:,.2f}\n💰 *Tarifa Total:* ${precio_mxn:,.2f} MXN"
            st.link_button("🟢 Enviar WhatsApp", f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}")

        with col_p:
            pdf_bytes = crear_pdf(nombre_cliente, origen_final, destino_final, distancia, total_extras, precio_mxn)
            nombre_archivo = f"Cotizacion_{nombre_cliente.replace(' ', '_') if nombre_cliente else 'Particular'}.pdf"
            st.download_button(
                label="📄 Descargar PDF",
                data=pdf_bytes,
                file_name=nombre_archivo,
                mime="application/pdf",
                type="primary" 
            )

with tab2:
    st.subheader("📜 Historial de Cotizaciones")
    st.session_state.df_rutas = st.data_editor(st.session_state.df_rutas, num_rows="dynamic")
    if st.button("Actualizar Historial"):
        st.session_state.df_rutas.to_csv(CSV_FILE, index=False)
        st.success("Cambios guardados en el archivo CSV.")
