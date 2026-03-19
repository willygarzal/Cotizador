import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Cotizador Logístico Pro", page_icon="🚛")

# --- BASE DE DATOS DE RUTAS (Extraída de tu imagen) ---
datos_rutas = {
    'EXPO': [
        {'Origen': 'MTY-AREA METRO', 'Destino': 'NUEVO LAREDO', 'KM': 230, 'CPK': 26.00},
        {'Origen': 'SALTILLO - RAMOS', 'Destino': 'NUEVO Laredo', 'KM': 310, 'CPK': 24.00},
        {'Origen': 'DERRAMADERO', 'Destino': 'NUEVO LAREDO', 'KM': 380, 'CPK': 25.00},
    ],
    'IMPO': [
        {'Origen': 'NUEVO LAREDO', 'Destino': 'MTY-AREA METRO', 'KM': 230, 'CPK': 31.10},
        {'Origen': 'NUEVO LAREDO', 'Destino': 'SALTILLO - RAMOS', 'KM': 310, 'CPK': 28.00},
        {'Origen': 'NUEVO LAREDO', 'Destino': 'DERRAMADERO', 'KM': 380, 'CPK': 28.10},
    ]
}

# --- INTERFAZ DE USUARIO ---
st.title("🚛 Cotizador de Rutas v1.0")
st.markdown("---")

# Sidebar para ajustes globales
st.sidebar.header("Configuración de Costos")
tipo_cambio = st.sidebar.number_input("Tipo de Cambio (MXN/USD)", value=17.00, step=0.10)
margen_input = st.sidebar.slider("Margen de Utilidad (%)", 0, 100, 25)
margen_decimal = margen_input / 100

# Selección de Operación
tipo_op = st.radio("Selecciona Tipo de Operación:", ["EXPO", "IMPO"], horizontal=True)

# Filtrar rutas según operación
opciones_rutas = datos_rutas[tipo_op]

if tipo_op == "EXPO":
    origen_sel = st.selectbox("Punto de Origen:", [r['Origen'] for r in opciones_rutas])
    ruta_final = next(item for item in opciones_rutas if item["Origen"] == origen_sel)
else:
    destino_sel = st.selectbox("Punto de Destino:", [r['Destino'] for r in opciones_rutas])
    ruta_final = next(item for item in opciones_rutas if item["Destino"] == destino_sel)

# --- CÁLCULOS (Matemática de tu Excel) ---
km = ruta_final['KM']
cpk = ruta_final['CPK']
cruce = 0 # Puedes editar esto si hay gastos de puente

# Fórmula: Costo base / (1 - Margen)
tarifa_mx = (km * cpk) / (1 - margen_decimal) + cruce
tarifa_usd = tarifa_mx / tipo_cambio

# --- DISPLAY DE RESULTADOS ---
st.markdown("### Resumen de Cotización")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Distancia", f"{km} KM")
with col2:
    st.metric("Tarifa MXN", f"${tarifa_mx:,.2f}")
with col3:
    st.metric("Tarifa USD", f"${tarifa_usd:,.2f}")

# Detalle técnico para transparencia
with st.expander("Ver detalle de cálculo"):
    st.write(f"**Costo por KM (CPK):** ${cpk}")
    st.write(f"**Margen aplicado:** {margen_input}%")
    st.write(f"**Fórmula utilizada:** `(KM * CPK) / (1 - Margen)`")

if st.button("Generar Formato de Envío"):
    texto_cotizacion = f"""
    COTIZACIÓN LOGÍSTICA
    --------------------
    Operación: {tipo_op}
    Ruta: {ruta_final['Origen']} -> {ruta_final['Destino']}
    Distancia: {km} KM
    Total MXN: ${tarifa_mx:,.2f}
    Total USD: ${tarifa_usd:,.2f} (T.C. {tipo_cambio})
    """
    st.code(texto_cotizacion, language="text")
    st.success("¡Copia este texto para enviarlo por WhatsApp!")
