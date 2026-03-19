import streamlit as st
import pandas as pd
import googlemaps
import os
import urllib.parse
from datetime import datetime
from fpdf import FPDF

# --- 1. CONFIGURACIÓN DE APIS ---
try:
    GMAPS_KEY = st.secrets["MAPS_API_KEY"]
except FileNotFoundError:
    st.error("❌ No se encontró la carpeta .streamlit o el archivo secrets.toml.")
    st.stop()
except KeyError:
    st.error("❌ El archivo secrets.toml existe, pero NO contiene la variable 'MAPS_API_KEY'.")
    st.stop()

gmaps = googlemaps.Client(key=GMAPS_KEY)

CSV_FILE = "historial_cotizaciones.csv"
# Añadimos las columnas para los extras en el historial
COLUMNAS = ["Fecha", "Cliente", "Operacion", "Origen", "Destino", "Distancia_KM", "Extra_Desc", "Extra_MXN", "Tarifa_MXN"]

def cargar_datos():
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        for col in COLUMNAS:
            if col not in df.columns:
                df[col] = ""
        return df
    return pd.DataFrame(columns=COLUMNAS)

if 'df_rutas' not in st.session_state:
    st.session_state.df_rutas = cargar_datos()

# --- FUNCION PARA GENERAR PDF ---
def generar_pdf(cliente, origen, destino, distancia, desc_extra, monto_extra, precio_mxn, precio_usd):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Cotizacion de Servicios Logisticos", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    # Datos Generales
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 8, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Cliente: {cliente if cliente else 'No especificado'}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Origen: {origen}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Destino: {destino}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Distancia estimada: {distancia:,.1f} KM", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    # Desglose de Costos
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, "Desglose de Tarifa:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 12)
    
    precio_base_mxn = precio_mxn - monto_extra
    pdf.cell(0, 8, f"Flete Base: ${precio_base_mxn:,.2f} MXN", new_x="LMARGIN", new_y="NEXT")
    
    if monto_extra > 0:
        pdf.cell(0, 8, f"Cargo Extra ({desc_extra}): ${monto_extra:,.2f} MXN", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, f"TOTAL MXN: ${precio_mxn:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"TOTAL USD: ${precio_usd:,.2f}", new_x="LMARGIN", new_y="NEXT")
    
    # Retorna los bytes del PDF
    return bytes(pdf.output())

# --- 2. SIDEBAR ---
st.sidebar.header("📊 Premisas de Cotización")
tipo_cambio = st.sidebar.number_input("Tipo de Cambio (MXN/USD)", value=17.50)
margen_porcentaje = st.sidebar.slider("Margen de Utilidad (%)", 5, 100, 20)

st.sidebar.divider()
cpk = st.sidebar.number_input("Costo Fijo por KM (CPK)", value=15.0)
costo_diesel = st.sidebar.number_input("Costo Diesel", value=24.50)
rendimiento = st.sidebar.number_input("Rendimiento (KM/L)", value=2.2)

# --- 3. INTERFAZ ---
st.title("🚛 Cotizador Logístico Pro")
tab1, tab2 = st.tabs(["🎯 Cotizador", "📜 Historial de Rutas"])

with tab1:
    nombre_cliente = st.text_input("👤 Nombre del Cliente / Empresa:", placeholder="Ej. Logística Global S.A.")
    
    col_op, col_modo = st.columns(2)
    with col_op:
        tipo_op = st.radio("Operación:", ["EXPO", "IMPO"], horizontal=True)
    with col_modo:
        modo_ruta = st.toggle("Nueva ruta (Google Maps)", value=False)

    distancia = 0.0
    origen_final = ""
    destino_final = ""

    if modo_ruta:
        orig_input = st.text_input("Origen:")
        dest_input = st.text_input("Destino:")
        
        if st.button("🔍 Calcular Distancia"):
            try:
                res = gmaps.distance_matrix(orig_input, dest_input, mode="driving")
                if res['rows'][0]['elements'][0]['status'] == "OK":
                    distancia = res['rows'][0]['elements'][0]['distance']['value'] / 1000
                    st.session_state['dist_temp'] = distancia
                    st.session_state['o_temp'] = orig_input
                    st.session_state['d_temp'] = dest_input
                else:
                    st.error("Ruta no encontrada.")
            except Exception as e:
                st.error(f"Error: {e}")
        
        if 'dist_temp' in st.session_state:
            distancia = st.session_state['dist_temp']
            origen_final = st.session_state['o_temp']
            destino_final = st.session_state['d_temp']
    else:
        rutas_fil = st.session_state.df_rutas.copy()
        if not rutas_fil.empty:
            rutas_fil["Etiqueta"] = rutas_fil["Origen"] + " ➡️ " + rutas_fil["Destino"]
            opciones = rutas_fil["Etiqueta"].unique()
            sel = st.selectbox("Selecciona ruta frecuente:", opciones)
            fila = rutas_fil[rutas_fil["Etiqueta"] == sel].iloc[0]
            distancia = fila["Distancia_KM"]
            origen_final = fila["Origen"]
            destino_final = fila["Destino"]
        else:
            st.info("No hay rutas guardadas aún. Activa 'Nueva ruta' para empezar.")

    if distancia > 0:
        st.divider()
        st.subheader("➕ Cargos Adicionales (Opcional)")
        col_ext1, col_ext2 = st.columns(2)
        with col_ext1:
            desc_extra = st.text_input("Descripción del cargo:", placeholder="Ej. Maniobras, Seguro, Autopistas")
        with col_ext2:
            monto_extra = st.number_input("Monto extra (MXN):", min_value=0.0, value=0.0, step=100.0)

        # CÁLCULOS
        combustible = (distancia / rendimiento) * costo_diesel
        costo_op = (distancia * cpk) + combustible
        precio_base_mxn = costo_op * (1 + (margen_porcentaje / 100))
        
        # Sumamos el cargo extra al total
        precio_mxn = precio_base_mxn + monto_extra
        precio_usd = precio_mxn / tipo_cambio

        st.divider()
        st.subheader(f"Resumen para: {nombre_cliente if nombre_cliente else 'Cliente Particular'}")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Distancia", f"{distancia:,.1f} KM")
        c2.metric("Precio MXN", f"${precio_mxn:,.2f}")
        c3.metric("Precio USD", f"${precio_usd:,.2f}")

        # BOTONES DE ACCIÓN (Guardar y Descargar PDF)
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("💾 Guardar Cotización"):
                fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
                nueva_fila = pd.DataFrame([{
                    "Fecha": fecha_hoy,
                    "Cliente": nombre_cliente if nombre_cliente else "N/A",
                    "Operacion": tipo_op,
                    "Origen": origen_final,
                    "Destino": destino_final,
                    "Distancia_KM": distancia,
                    "Extra_Desc": desc_extra if monto_extra > 0 else "N/A",
                    "Extra_MXN": monto_extra,
                    "Tarifa_MXN": round(precio_mxn, 2)
                }])
                st.session_state.df_rutas = pd.concat([st.session_state.df_rutas, nueva_fila], ignore_index=True)
                st.session_state.df_rutas.to_csv(CSV_FILE, index=False)
                st.success("✅ Cotización guardada.")

        with col_btn2:
            # Generamos el PDF en memoria
            pdf_bytes = generar_pdf(nombre_cliente, origen_final, destino_final, distancia, desc_extra, monto_extra, precio_mxn, precio_usd)
            nombre_archivo_pdf = f"Cotizacion_{nombre_cliente.replace(' ', '_') if nombre_cliente else 'Logistica'}_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            st.download_button(
                label="📄 Descargar Cotización en PDF",
                data=pdf_bytes,
                file_name=nombre_archivo_pdf,
                mime="application/pdf"
            )

        # MAPA
        map_url = f"https://www.google.com/maps/embed/v1/directions?key={GMAPS_KEY}&origin={urllib.parse.quote(origen_final)}&destination={urllib.parse.quote(destino_final)}&mode=driving"
        st.components.v1.html(f'<iframe width="100%" height="400" frameborder="0" style="border:0; border-radius:10px;" src="{map_url}" allowfullscreen></iframe>', height=410)
        
        st.divider()
        tel = st.text_input("Teléfono (ej: 521...):")
        cliente_str = f"👤 *Cliente:* {nombre_cliente}\n" if nombre_cliente else ""
        texto_extra_wa = f"➕ *Extra ({desc_extra}):* ${monto_extra:,.2f} MXN\n" if monto_extra > 0 else ""
        texto_wa = f"🚛 *COTIZACIÓN LOGÍSTICA*\n{cliente_str}📍 *Origen:* {origen_final}\n🏁 *Destino:* {destino_final}\n🛣️ *Distancia:* {distancia:,.1f} KM\n\n{texto_extra_wa}💰 *Total MXN:* ${precio_mxn:,.2f}\n💵 *Total USD:* ${precio_usd:,.2f}\n_(T.C. {tipo_cambio})_"
        st.link_button("🟢 Enviar por WhatsApp", f"https://wa.me/{tel}?text={urllib.parse.quote(texto_wa)}")

with tab2:
    st.subheader("📜 Historial Completo")
    df_edit = st.data_editor(st.session_state.df_rutas, num_rows="dynamic")
    if st.button("Actualizar Archivo"):
        st.session_state.df_rutas = df_edit
        df_edit.to_csv(CSV_FILE, index=False)
        st.success("Archivo actualizado.")
