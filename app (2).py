import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="ERP Marklogistic", layout="wide")

# ---------------------------------------------------------
# 1. INICIALIZACIÓN DE BASE DE DATOS (En memoria con Session State)
# ---------------------------------------------------------
if "materiales" not in st.session_state:
    st.session_state.materiales = pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Stock_Actual"])

if "movimientos" not in st.session_state:
    st.session_state.movimientos = pd.DataFrame(columns=["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen/Destino", "Fecha"])

if "ordenes_picking" not in st.session_state:
    st.session_state.ordenes_picking = []

if "guias_despacho" not in st.session_state:
    st.session_state.guias_despacho = []

# ---------------------------------------------------------
# 2. PANEL LATERAL / NAVEGACIÓN
# ---------------------------------------------------------
st.sidebar.title("📦 ERP Marklogistic")
menu = st.sidebar.radio(
    "Módulos del Sistema",
    [
        "1. Creación de Materiales",
        "2. Ingreso de Materiales",
        "3. Picking de Materiales",
        "4. Despacho y Guía",
        "5. Inventario",
        "6. Trazabilidad"
    ]
)

# ---------------------------------------------------------
# MÓDULO 1: CREACIÓN DE MATERIALES
# ---------------------------------------------------------
if menu == "1. Creación de Materiales":
    st.header("📋 Registro de Nuevos Materiales / Maestro de SKU")
    
    with st.form("form_nuevo_material"):
        col1, col2 = st.columns(2)
        with col1:
            sku = st.text_input("Código SKU / Material").strip().upper()
            nombre = st.text_input("Nombre / Descripción del Material")
        with col2:
            unidad = st.selectbox("Unidad de Medida", ["Unidades", "Cajas", "Pallets", "Kg", "Metros"])
            stock_inicial = st.number_input("Stock Inicial", min_value=0, value=0)
        
        submitted = st.form_submit_button("Guardar Material")
        if submitted:
            if sku and nombre:
                if sku in st.session_state.materiales["SKU"].values:
                    st.error(f"El SKU '{sku}' ya se encuentra registrado.")
                else:
                    nuevo_mat = pd.DataFrame([{"SKU": sku, "Nombre": nombre, "Unidad": unidad, "Stock_Actual": stock_inicial}])
                    st.session_state.materiales = pd.concat([st.session_state.materiales, nuevo_mat], ignore_index=True)
                    
                    if stock_inicial > 0:
                        mov = pd.DataFrame([{
                            "ID_Mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                            "Tipo": "STOCK_INICIAL",
                            "SKU": sku,
                            "Cantidad": stock_inicial,
                            "Origen/Destino": "Carga Inicial",
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
                        
                    st.success(f"Material {sku} creado correctamente.")
            else:
                st.warning("Completa los campos obligatorios (SKU y Nombre).")

    st.subheader("Maestro de Materiales Registrados")
    st.dataframe(st.session_state.materiales, use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 2: INGRESO DE MATERIALES
# ---------------------------------------------------------
elif menu == "2. Ingreso de Materiales":
    st.header("📥 Recepción e Ingreso a Bodega")
    
    if st.session_state.materiales.empty:
        st.info("Primero debe crear materiales en el Módulo 1.")
    else:
        with st.form("form_ingreso"):
            sku_ingreso = st.selectbox("Seleccionar Material (SKU)", st.session_state.materiales["SKU"])
            cant_ingreso = st.number_input("Cantidad a Ingresar", min_value=1, value=1)
            proveedor_origen = st.text_input("Proveedor / Procedencia", placeholder="Ej: Proveedor Central S.A.")
            
            btn_ingresar = st.form_submit_button("Registrar Ingreso")
            if btn_ingresar:
                # Actualizar Stock
                idx = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_ingreso].tolist()[0]
                st.session_state.materiales.loc[idx, "Stock_Actual"] += cant_ingreso
                
                # Registrar Movimiento
                mov = pd.DataFrame([{
                    "ID_Mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                    "Tipo": "INGRESO",
                    "SKU": sku_ingreso,
                    "Cantidad": cant_ingreso,
                    "Origen/Destino": proveedor_origen if proveedor_origen else "Recepción General",
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
                st.success(f"Se ingresaron {cant_ingreso} unidades del SKU {sku_ingreso}.")

# ---------------------------------------------------------
pip install streamlit pandas
streamlit run app.py
