import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import smtplib
from email.message import EmailMessage
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from PIL import Image
import sqlite3
import bcrypt

st.set_page_config(page_title="WMS Marklogistic", layout="wide")

# --------------------------------------------------------- #
# 0. CONFIGURACIÓN DE ARCHIVOS Y PERSISTENCIA (Base de Datos) #
# --------------------------------------------------------- #
EXCEL_MATERIALES = "db_materiales.xlsx"
EXCEL_MOVIMIENTOS = "db_movimientos.xlsx"
EXCEL_PICKING = "db_picking.xlsx"
EXCEL_GUIAS = "db_guias.xlsx"

if "materiales" not in st.session_state:
    if os.path.exists(EXCEL_MATERIALES):
        try:
            st.session_state.materiales = pd.read_excel(EXCEL_MATERIALES)
        except:
            st.session_state.materiales = pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual"])
    else:
        st.session_state.materiales = pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual"])

if "movimientos" not in st.session_state:
    if os.path.exists(EXCEL_MOVIMIENTOS):
        try:
            st.session_state.movimientos = pd.read_excel(EXCEL_MOVIMIENTOS)
        except:
            st.session_state.movimientos = pd.DataFrame(columns=["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen/Destino", "Fecha"])
    else:
        st.session_state.movimientos = pd.DataFrame(columns=["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen/Destino", "Fecha"])

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

# --------------------------------------------------------- #
# 0.1 BASE DE DATOS Y GESTIÓN DE USUARIOS (SQLite + Bcrypt) #
# --------------------------------------------------------- #
DB_PATH = "usuarios_wms.db"

def obtener_conexion():
    return sqlite3.connect(DB_PATH)

def inicializar_bd_usuarios():
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            rol TEXT NOT NULL
        )
    """)
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        salt = bcrypt.gensalt()
        pass_hash = bcrypt.hashpw("admin123".encode('utf-8'), salt)
        cursor.execute("INSERT INTO usuarios (usuario, password_hash, rol) VALUES (?, ?, ?)", ("admin", pass_hash, "Administrador"))
        conn.commit()
        st.toast("🔑 Usuario inicial creado: admin / admin123")
    conn.close()

def verificar_credenciales_bd(usuario, password):
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, rol FROM usuarios WHERE usuario = ?", (usuario,))
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        hash_almacenado, rol = resultado
        if bcrypt.checkpw(password.encode('utf-8'), hash_almacenado):
            return True, rol
    return False, None

def registrar_nuevo_usuario(usuario, password, rol="Usuario"):
    salt = bcrypt.gensalt()
    pass_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (usuario, password_hash, rol) VALUES (?, ?, ?)", (usuario, pass_hash, rol))
        conn.commit()
        conn.close()
        return True, "Usuario registrado exitosamente."
    except sqlite3.IntegrityError:
        return False, f"El usuario '{usuario}' ya existe."
    except Exception as e:
        return False, f"Error al registrar: {e}"

inicializar_bd_usuarios()

# --------------------------------------------------------- #
# INTERFAZ DE LOGIN DE STREAMLIT                           #
# --------------------------------------------------------- #
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acceso al WMS Marklogistic")
    st.markdown("Por favor, introduce tus credenciales para continuar.")
    with st.form("form_login"):
        user_input = st.text_input("Usuario").strip()
        pass_input = st.text_input("Contraseña", type="password")
        btn_login = st.form_submit_button("Iniciar Sesión")
        if btn_login:
            es_valido, rol = verificar_credenciales_bd(user_input, pass_input)
            if es_valido:
                st.session_state.autenticado = True
                st.session_state.usuario_actual = user_input
                st.session_state.rol_usuario = rol
                st.success(f"Bienvenido {user_input}")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()
