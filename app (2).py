import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import smtplib
from email.message import EmailMessage
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from streamlit_drawable_canvas import st_canvas
from PIL import Image

st.set_page_config(page_title="WMS Marklogistic", layout="wide")

# ---------------------------------------------------------
# 0. CONFIGURACIÓN DE ARCHIVOS Y PERSISTENCIA (Base de Datos)
# ---------------------------------------------------------
EXCEL_MATERIALES = "db_materiales.xlsx"
EXCEL_MOVIMIENTOS = "db_movimientos.xlsx"
EXCEL_PICKING = "db_picking.xlsx"
EXCEL_GUIAS = "db_guias.xlsx"

if "materiales" not in st.session_state:
    if os.path.exists(EXCEL_MATERIALES):
        try:
            st.session_state.materiales = pd.read_excel(EXCEL_MATERIALES)
        except:
            st.session_state.materiales = pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual", "Ubicacion", "Bodega"])
    else:
        st.session_state.materiales = pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual", "Ubicacion", "Bodega"])

if "Bodega" not in st.session_state.materiales.columns:
    st.session_state.materiales["Bodega"] = "Bodega Central Antofagasta"
if "Ubicacion" not in st.session_state.materiales.columns:
    st.session_state.materiales["Ubicacion"] = "A-00-0"

if "movimientos" not in st.session_state:
    if os.path.exists(EXCEL_MOVIMIENTOS):
        try:
            st.session_state.movimientos = pd.read_excel(EXCEL_MOVIMIENTOS)
        except:
            st.session_state.movimientos = pd.DataFrame(columns=["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen/Destino", "Fecha", "Usuario"])
    else:
        st.session_state.movimientos = pd.DataFrame(columns=["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen/Destino", "Fecha", "Usuario"])

if "Usuario" not in st.session_state.movimientos.columns:
    st.session_state.movimientos["Usuario"] = "admin"

if "ordenes_picking" not in st.session_state:
    if os.path.exists(EXCEL_PICKING):
        try:
            df_pick = pd.read_excel(EXCEL_PICKING)
            st.session_state.ordenes_picking = df_pick.to_dict('records')
        except:
            st.session_state.ordenes_picking = []
    else:
        st.session_state.ordenes_picking = []

if "guias_despacho" not in st.session_state:
    if os.path.exists(EXCEL_GUIAS):
        try:
            df_guias = pd.read_excel(EXCEL_GUIAS)
            st.session_state.guias_despacho = df_guias.to_dict('records')
        except:
            st.session_state.guias_despacho = []
    else:
        st.session_state.guias_despacho = []

def guardar_datos():
    try:
        st.session_state.materiales.to_excel(EXCEL_MATERIALES, index=False)
        st.session_state.movimientos.to_excel(EXCEL_MOVIMIENTOS, index=False)
        pd.DataFrame(st.session_state.ordenes_picking).to_excel(EXCEL_PICKING, index=False)
        pd.DataFrame(st.session_state.guias_despacho).to_excel(EXCEL_GUIAS, index=False)
    except Exception as e:
        st.error(f"Error al guardar datos: {e}")

# ---------------------------------------------------------
# 0.1 AUTENTICACIÓN Y PERMISOS DE USUARIOS
# ---------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

def verificar_credenciales(usuario, clave):
    usuarios_permitidos = {
        "admin": "admin123",
        "bodega": "bodega2026",
        "logistica": "marko2026"
    }
    if usuario in usuarios_permitidos and usuarios_permitidos[usuario] == clave:
        return True
    return False

PERMISOS_USUARIOS = {
    "admin": [
        "1. Creación de Materiales", "2. Ingreso de Materiales", "3. Picking de Materiales", 
        "4. Despacho y Guía", "5. Inventario", "6. Dashboard Gerencial", "7. Trazabilidad", 
        "8. Etiquetas", "9. Eliminar Transacciones", "10. Asistente IA", "11. Escáner de SKU", 
        "12. Gestión de Bodegas", "13. Auditoría y Logs", "14. Registro Fotográfico", "15. Gestión de Permisos"
    ],
    "bodega": [
        "2. Ingreso de Materiales", "3. Picking de Materiales", "4. Despacho y Guía", 
        "5. Inventario", "8. Etiquetas", "11. Escáner de SKU", "14. Registro Fotográfico"
    ],
    "logistica": [
        "3. Picking de Materiales", "4. Despacho y Guía", "5. Inventario", 
        "6. Dashboard Gerencial", "7. Trazabilidad", "12. Gestión de Bodegas"
    ]
}

if not st.session_state.autenticado:
    st.title("🔐 Acceso al WMS Marklogistic")
    st.markdown("Por favor, introduce tus credenciales para continuar.")
    with st.form("form_login"):
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        btn_login = st.form_
