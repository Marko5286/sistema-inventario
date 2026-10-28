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

# --------------------------------------------------------- #
# MENÚ LATERAL Y NAVEGACIÓN PRINCIPAL                      #
# --------------------------------------------------------- #
st.sidebar.success(f"👤 Conectado como: **{st.session_state.usuario_actual}** ({st.session_state.rol_usuario})")

if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

menu = st.sidebar.selectbox("Menú Principal", [
    "1. Gestión de Materiales",
    "2. Movimientos de Stock",
    "3. Órdenes de Picking",
    "4. Guías de Despacho",
    "16. Gestión de Usuarios"
])

# --------------------------------------------------------- #
# MÓDULO 1: GESTIÓN DE MATERIALES                          #
# --------------------------------------------------------- #
if menu == "1. Gestión de Materiales":
    st.header("📦 Gestión de Materiales e Inventario")
    
    with st.form("form_material"):
        col1, col2, col3 = st.columns(3)
        with col1:
            sku = st.text_input("SKU / Código").strip()
        with col2:
            nombre = st.text_input("Nombre del Material").strip()
        with col3:
            unidad = st.selectbox("Unidad de Medida", ["Unidades", "Kg", "Litros", "Metros", "Cajas"])
        
        col4, col5 = st.columns(2)
        with col4:
            valor = st.number_input("Valor Unitario", min_value=0.0, value=0.0)
        with col5:
            stock = st.number_input("Stock Inicial", min_value=0.0, value=0.0)
            
        btn_guardar_mat = st.form_submit_button("Registrar / Actualizar Material")
        
        if btn_guardar_mat:
            if not sku or not nombre:
                st.error("El SKU y el Nombre son obligatorios.")
            else:
                df = st.session_state.materiales
                if sku in df['SKU'].values:
                    df.loc[df['SKU'] == sku, ['Nombre', 'Unidad', 'Valor_Unitario', 'Stock_Actual']] = [nombre, unidad, valor, stock]
                    st.success(f"Material {sku} actualizado correctamente.")
                else:
                    nuevo_row = pd.DataFrame([{"SKU": sku, "Nombre": nombre, "Unidad": unidad, "Valor_Unitario": valor, "Stock_Actual": stock}])
                    st.session_state.materiales = pd.concat([df, nuevo_row], ignore_index=True)
                    st.success(f"Material {sku} registrado correctamente.")
                guardar_datos()
                st.rerun()

    st.markdown("---")
    st.subheader("📋 Inventario Actual")
    st.dataframe(st.session_state.materiales, use_container_width=True)

# --------------------------------------------------------- #
# MÓDULO 2: MOVIMIENTOS DE STOCK                            #
# --------------------------------------------------------- #
elif menu == "2. Movimientos de Stock":
    st.header("🔄 Movimientos de Entrada y Salida")
    
    if st.session_state.materiales.empty:
        st.warning("⚠️ Primero debes registrar materiales en el Módulo 1.")
    else:
        with st.form("form_movimiento"):
            tipo = st.selectbox("Tipo de Movimiento", ["Entrada", "Salida", "Ajuste"])
            sku_sel = st.selectbox("Seleccionar SKU", st.session_state.materiales['SKU'].tolist())
            cantidad = st.number_input("Cantidad", min_value=0.1, value=1.0)
            origen_destino = st.text_input("Origen / Destino / Motivo").strip()
            
            btn_mov = st.form_submit_button("Registrar Movimiento")
            
            if btn_mov:
                idx = st.session_state.materiales.index[st.session_state.materiales['SKU'] == sku_sel][0]
                stock_actual = st.session_state.materiales.at[idx, 'Stock_Actual']
                
                if tipo == "Salida" and cantidad > stock_actual:
                    st.error(f"Stock insuficiente. Stock actual disponible: {stock_actual}")
                else:
                    # Actualizar stock
                    if tipo == "Entrada":
                        nuevo_stock = stock_actual + cantidad
                    elif tipo == "Salida":
                        nuevo_stock = stock_actual - cantidad
                    else:
                        nuevo_stock = cantidad # Ajuste directo
                        
                    st.session_state.materiales.at[idx, 'Stock_Actual'] = nuevo_stock
                    
                    # Registrar movimiento
                    id_mov = f"MOV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    nuevo_mov = pd.DataFrame([{
                        "ID_Mov": id_mov,
                        "Tipo": tipo,
                        "SKU": sku_sel,
                        "Cantidad": cantidad,
                        "Origen/Destino": origen_destino,
                        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    st.session_state.movimientos = pd.concat([st.session_state.movimientos, nuevo_mov], ignore_index=True)
                    guardar_datos()
                    st.success(f"Movimiento {id_mov} registrado con éxito.")
                    st.rerun()

    st.markdown("---")
    st.subheader("📜 Historial de Movimientos")
    st.dataframe(st.session_state.movimientos, use_container_width=True)

# --------------------------------------------------------- #
# MÓDULO 3: ÓRDENES DE PICKING                             #
# --------------------------------------------------------- #
elif menu == "3. Órdenes de Picking":
    st.header("📋 Órdenes de Picking")
    st.info("Módulo de preparación de pedidos y despachos.")
    if st.session_state.ordenes_picking:
        st.write(st.session_state.ordenes_picking)
    else:
        st.write("No hay órdenes de picking registradas.")

# --------------------------------------------------------- #
# MÓDULO 4: GUÍAS DE DESPACHO                              #
# --------------------------------------------------------- #
elif menu == "4. Guías de Despacho":
    st.header("📄 Guías de Despacho")
    st.info("Módulo de emisión de guías y documentos de transporte.")
    if st.session_state.guias_despacho:
        st.write(st.session_state.guias_despacho)
    else:
        st.write("No hay guías de despacho emitidas.")

# --------------------------------------------------------- #
# MÓDULO 16: GESTIÓN DE USUARIOS                           #
# --------------------------------------------------------- #
elif menu == "16. Gestión de Usuarios":
    st.header("👤 Administración y Registro de Usuarios")

    if st.session_state.get("rol_usuario") != "Administrador":
        st.warning("⚠️ No tienes permisos de administrador para acceder a este módulo.")
    else:
        with st.form("form_registro_usuario"):
            st.subheader("➕ Crear Nuevo Usuario")
            nuevo_user = st.text_input("Nuevo Usuario").strip()
            nuevo_pass = st.text_input("Contraseña", type="password")
            nuevo_rol = st.selectbox("Rol del Usuario", ["Bodeguero", "Logística", "Administrador"])
            btn_crear = st.form_submit_button("Registrar Usuario")

            if btn_crear:
                if not nuevo_user or not nuevo_pass:
                    st.error("Completa todos los campos obligatorios.")
                else:
                    exito, mensaje = registrar_nuevo_usuario(nuevo_user, nuevo_pass, nuevo_rol)
                    if exito:
                        st.success(mensaje)
                    else:
                        st.error(mensaje)

        st.markdown("---")
        st.subheader("📋 Usuarios Registrados")
        conn = obtener_conexion()
        df_users = pd.read_sql_query("SELECT id, usuario, rol FROM usuarios", conn)
        conn.close()
        st.dataframe(df_users, use_container_width=True)
