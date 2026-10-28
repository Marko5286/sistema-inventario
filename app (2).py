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
# MÓDULO 16: GESTIÓN DE USUARIOS                           #
# --------------------------------------------------------- #
# (Asegúrate de tener tu barra lateral y menús previos aquí)

# ---------------------------------------------------------
# FUNCIONES DE AUTOMATIZACIÓN (PDF & CORREO)
# ---------------------------------------------------------
def generar_pdf_guia(guia):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "WMS MARKLOGISTIC S.A.")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, "R.U.T.: 76.543.210-K | Giro: Logística y Distribución")
    
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(550, 750, "GUÍA DE TRASLADO ")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(550, 735, f"N° {guia['Numero_Guia']}")
    
    c.line(50, 720, 550, 720)
    
    c.setFont("Helvetica", 11)
    c.drawString(50, 690, f"Fecha de Emisión: {guia['Fecha']}")
    c.drawString(50, 670, f"Señor(es): {guia['Cliente']}")
    c.drawString(350, 670, f"R.U.T.: {guia.get('Rut', 'N/A')}")
    
    c.drawString(50, 650, f"Transportista: {guia['Transporte']} ({guia.get('Conductor', '')})")
    c.drawString(350, 650, f"Patente: {guia['Patente']}")
    c.drawString(50, 630, f"Motivo de Traslado: {guia['Motivo']}")
    
    c.line(50, 610, 550, 610)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, 595, "SKU")
    c.drawString(150, 595, "CANTIDAD")
    c.drawString(250, 595, "DESCRIPCIÓN / DETALLE")
    c.line(50, 585, 550, 585)
    
    c.setFont("Helvetica", 10)
    c.drawString(60, 565, str(guia['SKU']))
    c.drawString(150, 565, str(guia['Cantidad']))
    c.drawString(250, 565, "Despacho operativo según orden de picking")
    
    c.line(50, 150, 220, 150)
    c.drawString(70, 135, "Firma Chofer / Transportista")
    
    c.line(380, 150, 550, 150)
    c.drawString(400, 135, "Firma Recinto / Cliente")
    
    c.save()
    buffer.seek(0)
    return buffer
def enviar_correo_respaldo(remitente, password, destinatario, excel_bytes):
    try:
        msg = MIMEMultipart()
        msg['From'] = remitente
        msg['To'] = destinatario
        msg['Subject'] = "Respaldo de Inventario - ERP"

        # Cuerpo del mensaje
        body = "Adjunto encontrarás el archivo Excel con el respaldo actualizado del inventario de la bodega."
        msg.attach(MIMEText(body, 'plain'))

        # Adjuntar archivo Excel
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(excel_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="respaldo_inventario.xlsx"')
        msg.attach(part)

        # Conexión segura usando SSL (Puerto 465, más estable en la nube)
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Error detallado: {e}")
        return False

# ---------------------------------------------------------
# 2. PANEL LATERAL / NAVEGACIÓN Y RESPALDO
# ---------------------------------------------------------
st.sidebar.title("📦 WMS Marklogistic")

try:
    st.sidebar.image("https://github.com/Marko5286/sistema-inventario/blob/main/logo.jpg.jpg?raw=true", width=200)
except:
    pass

st.sidebar.write(f"👤 Conectado como: **{st.session_state.get('usuario_actual', '')}**")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio(
    "Módulos del Sistema",
    [
        "1. Creación de Materiales",
        "2. Ingreso de Materiales",
        "3. Picking de Materiales",
        "4. Despacho y Guía",
        "5. Inventario",
        "6. Trazabilidad",
        "7. Etiquetas",
        "8. Eliminar Transacciones",
        "9. Asistente IA",
        "10. Fotografías de Respaldo",
        "11. Alertas de Stock",
        "12. Kardex de Movimientos",
        "13. Generadores QR/Barras",
        "14. Dashboard de Estadísticas",
        "15. Proveedores y Clientes",
        "16. Gestion de Usuarios"
    ]
)

# Automatización de Correo en la barra lateral
st.sidebar.markdown("---")
st.sidebar.subheader("📧 Envío Automático de Reportes")
correo_remitente = st.sidebar.text_input("marco.inostroza63.mi@gmail.com")
pass_remitente = st.sidebar.text_input("Contraseña de Aplicación", type="password")
correo_destino = st.sidebar.text_input("Correo Destino (Gerencia)", value="marco.inostroza63.mi@gmail.com")

if st.sidebar.button("Enviar Respaldo por Email"):
    if not correo_remitente or not pass_remitente or not correo_destino:
        st.sidebar.error("Completa todos los campos de correo.")
    else:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.materiales.to_excel(writer, sheet_name='materiales', index=False)
            st.session_state.movimientos.to_excel(writer, sheet_name='movimientos', index=False)
        excel_bytes = output.getvalue()
        
        if enviar_correo_respaldo(correo_remitente, pass_remitente, correo_destino, excel_bytes):
            st.sidebar.success("¡Correo de respaldo enviado con éxito!")
        else:
            st.sidebar.error("Error al enviar. Revisa tus credenciales.")

# Botón de Copia de Seguridad Local
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Descarga Manual Respaldo")
if not st.session_state.materiales.empty:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        st.session_state.materiales.to_excel(writer, sheet_name='materiales', index=False)
        st.session_state.movimientos.to_excel(writer, sheet_name='movimientos', index=False)
    
    excel_data = output.getvalue()
    st.sidebar.download_button(
        label="📥 Descargar Respaldo BD",
        data=excel_data,
        file_name=f"respaldo_erp_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ---------------------------------------------------------
# MÓDULO 1: CREACIÓN DE MATERIALES
# ---------------------------------------------------------
if menu == "1. Creación de Materiales":
    st.header("📋 Registro y Carga Masiva de Materiales / Maestro de SKU")
    
    tab_manual, tab_masivo = st.tabs(["➕ Registro Manual", "📂 Carga Masiva (Excel / CSV)"])
    
    with tab_manual:
        with st.form("form_nuevo_material"):
            col1, col2 = st.columns(2)
            with col1:
                sku = st.text_input("Código SKU / Material *").strip().upper()
                nombre = st.text_input("Nombre / Descripción del Material *")
                unidad = st.selectbox("Unidad de Medida", ["Unidades", "Cajas", "Pallets", "Kg", "Metros"])
            with col2:
                valor_unitario = st.number_input("Valor / Precio Unitario ($)", min_value=0.0, value=0.0, step=100.0)
                stock_inicial = st.number_input("Stock Inicial", min_value=0, value=0)
            
            submitted = st.form_submit_button("Guardar Material")
            if submitted:
                if not sku or not nombre:
                    st.error("⚠️ Los campos SKU y Nombre son obligatorios.")
                else:
                    if sku in st.session_state.materiales["SKU"].values:
                        st.error(f"El SKU '{sku}' ya se encuentra registrado.")
                    else:
                        nuevo_mat = pd.DataFrame([{
                            "SKU": sku, 
                            "Nombre": nombre, 
                            "Unidad": unidad, 
                            "Valor_Unitario": valor_unitario,
                            "Stock_Actual": stock_inicial
                        }])
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
                        
                        guardar_datos()
                        st.success(f"Material {sku} creado correctamente.")

    with tab_masivo:
        st.subheader("Carga Masiva desde Archivo")
        st.code("SKU | Nombre | Unidad | Valor_Unitario | Stock_Actual")
        archivo_subido = st.file_uploader("Selecciona tu archivo de materiales", type=["csv", "xlsx"])
        
        if archivo_subido is not None:
            try:
                if archivo_subido.name.endswith('.csv'):
                    df_carga = pd.read_csv(archivo_subido)
                else:
                    df_carga = pd.read_excel(archivo_subido)
                
                df_carga.columns = df_carga.columns.str.strip()
                columnas_requeridas = ["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual"]
                
                if all(col in df_carga.columns for col in columnas_requeridas):
                    st.dataframe(df_carga.head(), use_container_width=True)
                    if st.button("Confirmar e Importar Materiales"):
                        importados = 0
                        for _, row in df_carga.iterrows():
                            sku_val = str(row["SKU"]).strip().upper()
                            if not sku_val or pd.isna(row["SKU"]): continue
                            
                            if sku_val in st.session_state.materiales["SKU"].values:
                                idx_existente = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_val].tolist()[0]
                                st.session_state.materiales.loc[idx_existente, "Stock_Actual"] += int(row["Stock_Actual"])
                            else:
                                nuevo_row = pd.DataFrame([{
                                    "SKU": sku_val, "Nombre": str(row["Nombre"]), "Unidad": str(row["Unidad"]),
                                    "Valor_Unitario": float(row["Valor_Unitario"]), "Stock_Actual": int(row["Stock_Actual"])
                                }])
                                st.session_state.materiales = pd.concat([st.session_state.materiales, nuevo_row], ignore_index=True)
                            
                            importados += 1
                        guardar_datos()
                        st.success(f"¡Se importaron {importados} materiales!")
                        st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    st.subheader("Maestro de Materiales Registrados")
    st.dataframe(st.session_state.materiales, use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 2: INGRESO DE MATERIALES
# ---------------------------------------------------------
elif menu == "2. Ingreso de Materiales":
    st.header("📥 Recepción e Ingreso a Bodega")
    if st.session_state.materiales.empty:
        st.info("Primero debe crear materiales.")
    else:
        with st.form("form_ingreso"):
            sku_ingreso = st.selectbox("Seleccionar Material (SKU)", st.session_state.materiales["SKU"])
            cant_ingreso = st.number_input("Cantidad a Ingresar", min_value=1, value=1)
            proveedor_origen = st.text_input("Proveedor / Procedencia")
            
            if st.form_submit_button("Registrar Ingreso"):
                idx = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_ingreso].tolist()[0]
                st.session_state.materiales.loc[idx, "Stock_Actual"] += cant_ingreso
                
                mov = pd.DataFrame([{
                    "ID_Mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                    "Tipo": "INGRESO", "SKU": sku_ingreso, "Cantidad": cant_ingreso,
                    "Origen/Destino": proveedor_origen or "Recepción General",
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
                guardar_datos()
                st.success(f"Ingresadas {cant_ingreso} unidades del SKU {sku_ingreso}.")

# ---------------------------------------------------------
# MÓDULO 3: PICKING DE MATERIALES
# ---------------------------------------------------------
elif menu == "3. Picking de Materiales":
    st.header("🛒 Generación y Preparación de Pedidos (Picking)")
    if not st.session_state.materiales.empty:
        with st.form("form_picking"):
            cliente = st.text_input("Cliente / Destino")
            sku_pick = st.selectbox("Material a Extraer", st.session_state.materiales["SKU"])
            cant_pick = st.number_input("Cantidad a Preparar", min_value=1, value=1)
            
            if st.form_submit_button("Crear Orden de Picking"):
                stock_disponible = st.session_state.materiales.loc[st.session_state.materiales["SKU"] == sku_pick, "Stock_Actual"].values[0]
                if cant_pick > stock_disponible:
                    st.error(f"Stock insuficiente. Disponible: {stock_disponible}")
                else:
                    id_ord = f"PICK-{len(st.session_state.ordenes_picking)+1:04d}"
                    st.session_state.ordenes_picking.append({
                        "ID_Picking": id_ord, "Cliente": cliente, "SKU": sku_pick, "Cantidad": cant_pick, "Estado": "Pendiente Despacho"
                    })
                    guardar_datos()
                    st.success(f"Orden {id_ord} registrada.")
        if st.session_state.ordenes_picking:
            st.dataframe(pd.DataFrame(st.session_state.ordenes_picking), use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 4: DESPACHO Y GUÍA DE TRASLADO
# ---------------------------------------------------------
elif menu == "4. Despacho y Guía":
    st.header("🚚 Despacho y Emisión de Guía de Traslado")
    
    pendientes = [p for p in st.session_state.ordenes_picking if p["Estado"] == "Pendiente Despacho"]
    if not pendientes:
        st.info("No hay órdenes de picking pendientes.")
    else:
        df_pendientes = pd.DataFrame(pendientes)
        orden_sel = st.selectbox("Seleccionar Orden de Picking", df_pendientes["ID_Picking"])
        datos_orden = next(item for item in st.session_state.ordenes_picking if item["ID_Picking"] == orden_sel)
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            transporte = st.text_input("Empresa de Transporte")
            patente = st.text_input("Patente Vehículo")
            nombre_conductor = st.text_input("Nombre Conductor")
            rut_conductor = st.text_input("R.U.T. Conductor")
        with col_d2:
            rut_cliente = st.text_input("R.U.T. del Cliente")
            motivo = st.selectbox("Motivo de Traslado", ["Venta", "Traspaso entre bodegas", "Devolución", "Muestras"])
        
        if st.button("Confirmar Despacho y Generar Guía"):
            idx = st.session_state.materiales.index[st.session_state.materiales["SKU"] == datos_orden["SKU"]].tolist()[0]
            st.session_state.materiales.loc[idx, "Stock_Actual"] -= datos_orden["Cantidad"]
            datos_orden["Estado"] = "Despachado"
            
            mov = pd.DataFrame([{
                "ID_Mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                "Tipo": "DESPACHO", "SKU": datos_orden["SKU"], "Cantidad": datos_orden["Cantidad"],
                "Origen/Destino": datos_orden["Cliente"], "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
            
            num_guia = f"GD-{len(st.session_state.guias_despacho)+1:04d}"
            guia_data = {
                "Numero_Guia": num_guia, "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Cliente": datos_orden["Cliente"], "Rut": rut_cliente, "SKU": datos_orden["SKU"],
                "Cantidad": datos_orden["Cantidad"], "Transporte": transporte, "Conductor": nombre_conductor,
                "Rut_Conductor": rut_conductor, "Patente": patente, "Motivo": motivo
            }
            st.session_state.guias_despacho.append(guia_data)
            guardar_datos()
            st.success(f"¡Despacho realizado! Guía N° **{num_guia}**")
            st.session_state.ultima_guia = guia_data

    if "ultima_guia" in st.session_state:
        st.markdown("---")
        guia = st.session_state.ultima_guia
        st.subheader(f"📄 Descarga Directa: Guía N° {guia['Numero_Guia']}")
        
        pdf_buffer = generar_pdf_guia(guia)
        st.download_button(
            label="📥 Descargar Guía Oficial en PDF",
            data=pdf_buffer,
            file_name=f"Guia_{guia['Numero_Guia']}.pdf",
            mime="application/pdf"
        )

# ---------------------------------------------------------
# MÓDULO 5: INVENTARIO
# ---------------------------------------------------------
elif menu == "5. Inventario":
    st.header("📊 Control de Inventario en Tiempo Real")
    col_k1, col_k2 = st.columns(2)
    with col_k1: st.metric("Total SKU Registrados", len(st.session_state.materiales))
    with col_k2: st.metric("Total Unidades", int(st.session_state.materiales["Stock_Actual"].sum()) if not st.session_state.materiales.empty else 0)
    st.dataframe(st.session_state.materiales, use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 6: TRAZABILIDAD
# ---------------------------------------------------------
elif menu == "6. Trazabilidad":
    st.header("🔍 Historial de Movimientos")
    if not st.session_state.movimientos.empty:
        st.dataframe(st.session_state.movimientos.sort_values(by="Fecha", ascending=False), use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 7: ETIQUETAS
# ---------------------------------------------------------
elif menu == "7. Etiquetas":
    st.header("🏷️ Generación e Impresión de Etiquetas de Bodega")
    
    if st.session_state.materiales.empty:
        st.info("No hay materiales registrados para etiquetar.")
    else:
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            sku_etiqueta = st.selectbox("Seleccionar Material para Etiquetar", st.session_state.materiales["SKU"])
        with col_e2:
            cantidad_copias = st.number_input("Número de etiquetas a imprimir", min_value=1, value=1)
            
        mat_info = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_etiqueta].iloc[0]
        
        st.markdown("---")
        st.subheader("Vista Previa de Etiqueta (Optimizado para Impresión)")
        
        st.markdown("""
            <style>
            @media print {
                [data-testid="stSidebar"], header, .stButton, .stSelectbox, .stNumberInput {
                    display: none !important;
                }
                body {
                    background-color: white !important;
                }
            }
            .etiqueta-box {
                border: 2px dashed #000;
                width: 320px;
                padding: 15px;
                font-family: Arial, sans-serif;
                background: white;
                color: black;
                margin-bottom: 20px;
                border-radius: 8px;
            }
            </style>
        """, unsafe_allow_html=True)
        
        for i in range(cantidad_copias):
            html_etiqueta = f"""
            <div class="etiqueta-box">
                <h4 style="text-align: center; margin: 0 0 10px 0; font-size: 16px;">WMS MARKLOGISTIC</h4>
                <hr style="border: 1px solid #000; margin: 5px 0;">
                <p style="margin: 5px 0; font-size: 14px;"><b>SKU:</b> {mat_info['SKU']}</p>
                <p style="margin: 5px 0; font-size: 14px;"><b>Descripción:</b> {mat_info['Nombre']}</p>
                <p style="margin: 5px 0; font-size: 14px;"><b>Unidad:</b> {mat_info['Unidad']}</p>
                <p style="margin: 5px 0; font-size: 14px;"><b>Valor Unit.:</b> ${mat_info['Valor_Unitario']:,.0f}</p>
                <div style="text-align: center; margin-top: 10px; font-size: 12px; font-family: monospace;">
                    ||||| | |||| ||| || ||||
                </div>
            </div>
            """
            st.markdown(html_etiqueta, unsafe_allow_html=True)
        
        st.info("💡 **Para imprimir o guardar en PDF:** Presiona las teclas **`Ctrl + P`** en tu teclado (o **`Cmd + P`** en Mac).")

# ---------------------------------------------------------
# MÓDULO 8: ELIMINAR TRANSACCIONES
# ---------------------------------------------------------
elif menu == "8. Eliminar Transacciones":
    st.header("🗑️ Gestión y Anulación de Transacciones")
    if not st.session_state.movimientos.empty:
        st.dataframe(st.session_state.movimientos, use_container_width=True)
        id_eliminar = st.selectbox("ID de Movimiento a Eliminar", st.session_state.movimientos["ID_Mov"])
        if st.button("Eliminar Transacción"):
            mov_reg = st.session_state.movimientos[st.session_state.movimientos["ID_Mov"] == id_eliminar].iloc[0]
            sku_mov = mov_reg["SKU"]
            cant_mov = mov_reg["Cantidad"]
            tipo_mov = mov_reg["Tipo"]
            
            if sku_mov in st.session_state.materiales["SKU"].values:
                idx_mat = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_mov].tolist()[0]
                if tipo_mov in ["INGRESO", "STOCK_INICIAL"]:
                    st.session_state.materiales.loc[idx_mat, "Stock_Actual"] -= cant_mov
                elif tipo_mov == "DESPACHO":
                    st.session_state.materiales.loc[idx_mat, "Stock_Actual"] += cant_mov
            
            st.session_state.movimientos = st.session_state.movimientos[st.session_state.movimientos["ID_Mov"] != id_eliminar].reset_index(drop=True)
            guardar_datos()
            st.success("Transacción eliminada y stock revertido con éxito.")
            st.rerun()

# ---------------------------------------------------------
# MÓDULO 9: ASISTENTE IA
# ---------------------------------------------------------
elif menu == "9. Asistente IA":
    st.header("🤖 Asistente Inteligente")
    if "GEMINI_API_KEY" in st.secrets:
        try:
            from google import genai
            client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            pregunta = st.text_input("Consulta al WMS (Ej: ¿Qué productos tienen bajo stock?)")
            if st.button("Consultar IA") and pregunta:
                resumen = st.session_state.materiales.to_string()
                response = client.models.generate_content(
                    model='gemini-1.5-pro',
                    contents=f"Eres un experto en logística. Datos de bodega:\n{resumen}\nResponde a: {pregunta}"
                )
                st.success(response.text)
        except Exception as e:
            st.error(f"Error IA: {e}")
    else:
        st.warning("Configura tu GEMINI_API_KEY en los secretos.")

# ---------------------------------------------------------
# MÓDULO 10: FOTOGRAFÍAS DE RESPALDO
# ---------------------------------------------------------
elif menu == "10. Fotografías de Respaldo":
    st.markdown("## 📸 Respaldo Fotográfico de Bodega")
    st.write("Sube fotografías de productos, recepción de mercadería o evidencias de inventario.")

    import os
    CARPETA_FOTOS = "respaldos_fotos"
    
    if not os.path.exists(CARPETA_FOTOS):
        os.makedirs(CARPETA_FOTOS)

    # Widgets de carga
    archivo_subido = st.file_uploader("Elige una imagen...", type=["jpg", "jpeg", "png"], key="subir_foto_final")
    descripcion_foto = st.text_input("Descripción o motivo (ej: Lote dañado, Factura #123)", key="desc_foto_final")

    if archivo_subido is not None:
        st.image(archivo_subido, caption="Vista previa", use_column_width=True)
        
        if st.button("Guardar Fotografía", key="btn_guardar_definitivo"):
            ruta = os.path.join(CARPETA_FOTOS, archivo_subido.name)
            with open(ruta, "wb") as f:
                f.write(archivo_subido.getbuffer())
            st.success(f"¡Imagen guardada como: {archivo_subido.name}!")

    st.markdown("---")
    st.markdown("### 📁 Galería de Respaldos")
    
    if os.path.exists(CARPETA_FOTOS):
        archivos = [f for f in os.listdir(CARPETA_FOTOS) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if archivos:
            for arq in archivos:
                with st.expander(f"Ver: {arq}"):
                    st.image(os.path.join(CARPETA_FOTOS, arq), width=300)
        else:
            st.info("No hay fotografías guardadas todavía.")

# ---------------------------------------------------------
# MÓDULO 11: ALERTAS DE STOCK
# ---------------------------------------------------------
elif menu == "11. Alertas de Stock":
    st.header("⚠️ Control de Stock Crítico")
    st.write("Productos que se encuentran por debajo del mínimo establecido y necesitan reabastecimiento.")

    try:
        # Asegúrate de que 'df_inventario' sea tu variable de inventario principal
        if 'df_inventario' in locals() and not df_inventario.empty:
            
            # Verificar si existe la columna de stock mínimo, si no, crear una por defecto
            if 'Stock Mínimo' not in df_inventario.columns:
                df_inventario['Stock Mínimo'] = 5  # Valor por defecto

            # Filtrar productos con stock crítico
            stock_critico = df_inventario[df_inventario['Stock Actual'] <= df_inventario['Stock Mínimo']]

            if not stock_critico.empty:
                st.error(f"¡Atención! Hay {len(stock_critico)} producto(s) con stock crítico.")
                
                # Mostrar tabla resaltada
                st.dataframe(stock_critico, use_container_width=True)
                
                # Opción para descargar la lista de compras urgente
                csv_criticos = stock_critico.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Lista de Reabastecimiento (CSV)",
                    data=csv_criticos,
                    file_name="compras_urgentes.csv",
                    mime="text/csv",
                )
            else:
                st.success("¡Excelente! Todos los productos tienen niveles de stock saludables.")
        else:
            st.info("No se encontró una tabla de inventario activa o está vacía.")
            
    except Exception as e:
        st.error(f"Ocurrió un error al procesar las alertas: {e}")

# ---------------------------------------------------------
# MÓDULO 12: KARDEX DE MOVIMIENTOS (ENTRADAS Y SALIDAS)
# ---------------------------------------------------------
elif menu == "12. Kardex de Movimientos":
    st.header("📋 Kardex de Movimientos de Bodega")
    st.write("Registra y audita las entradas y salidas de productos con fecha, hora y usuario.")

    import pandas as pd
    from datetime import datetime

    # Archivo CSV local para guardar el historial de movimientos
    ARCHIVO_KARDEX = "kardex_movimientos.csv"

    # Cargar el kardex existente o crear uno nuevo si no existe
    if os.path.exists(ARCHIVO_KARDEX):
        df_kardex = pd.read_csv(ARCHIVO_KARDEX)
    else:
        df_kardex = pd.DataFrame(columns=[
            "Fecha/Hora", "Tipo Movimiento", "Producto", "Cantidad", "Responsable", "Observación"
        ])

    # Formulario para registrar un nuevo movimiento
    with st.form("form_kardex"):
        st.subheader("➕ Registrar Nuevo Movimiento")
        
        tipo_mov = st.selectbox("Tipo de Movimiento", ["Entrada (Compra/Recepción)", "Salida (Venta/Merma/Despacho)"])
        
        # Obtener lista de productos disponibles (si 'df_inventario' existe)
        lista_productos = []
        if 'df_inventario' in locals() and not df_inventario.empty and 'Producto' in df_inventario.columns:
            lista_productos = df_inventario['Producto'].tolist()
        
        if lista_productos:
            producto_sel = st.selectbox("Seleccionar Producto", lista_productos)
        else:
            producto_sel = st.text_input("Nombre del Producto")

        cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
        responsable = st.text_input("Responsable / Bodeguero")
        observacion = st.text_area("Observación o Motivo (opcional)")

        btn_registrar = st.form_submit_button("Registrar Movimiento")

        if btn_registrar:
            if producto_sel and responsable:
                # Obtener fecha y hora actual exacta
                fecha_hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Crear la nueva fila de movimiento
                nuevo_registro = pd.DataFrame([{
                    "Fecha/Hora": fecha_hora_actual,
                    "Tipo Movimiento": tipo_mov,
                    "Producto": producto_sel,
                    "Cantidad": cantidad,
                    "Responsable": responsable,
                    "Observación": observacion
                }])

                # Concatenar y guardar
                df_kardex = pd.concat([df_kardex, nuevo_registro], ignore_index=True)
                df_kardex.to_csv(ARCHIVO_KARDEX, index=False)

                st.success(f"¡Movimiento de '{tipo_mov}' registrado con éxito a las {fecha_hora_actual}!")
                st.rerun()
            else:
                st.error("Por favor, completa al menos el producto y el responsable.")

    st.markdown("---")
    st.subheader("📊 Historial de Movimientos")

    if not df_kardex.empty:
        # Filtro rápido por tipo de movimiento
        filtro_tipo = st.selectbox("Filtrar por tipo", ["Todos", "Entrada (Compra/Recepción)", "Salida (Venta/Merma/Despacho)"], key="filtro_kardex")
        
        if filtro_tipo != "Todos":
            df_mostrar = df_kardex[df_kardex["Tipo Movimiento"] == filtro_tipo]
        else:
            df_mostrar = df_kardex

        st.dataframe(df_mostrar, use_container_width=True)

        # Botón para descargar el kardex completo
        csv_kardex = df_kardex.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Kardex Completo (CSV)",
            data=csv_kardex,
            file_name="kardex_bodega.csv",
            mime="text/csv",
        )
    else:
        st.info("Aún no hay movimientos registrados en el Kardex.")

# ---------------------------------------------------------
# MÓDULO 13: GENERADOR DE CÓDIGOS QR Y BARRAS
# ---------------------------------------------------------
elif menu == "13. Generadores QR/Barras":
    st.header("🔲 Generador de Códigos QR y de Barras")
    st.write("Crea etiquetas con códigos QR o de barras para identificar tus productos rápidamente.")

    import qrcode
    from io import BytesIO

    # Pestañas para separar QR de Códigos de Barras
    tab1, tab2 = st.tabs(["Generador de Códigos QR", "Generador de Códigos de Barras"])

    with tab1:
        st.subheader("📲 Crear Código QR para Producto o Lote")
        
        # Opción para seleccionar producto del inventario si existe
        texto_qr = ""
        if 'df_inventario' in locals() and not df_inventario.empty and 'Producto' in df_inventario.columns:
            opcion_prod = st.selectbox("Seleccionar desde Inventario (Opcional)", ["-- Escribir manual --"] + df_inventario['Producto'].tolist(), key="select_qr_prod")
            if opcion_prod != "-- Escribir manual --":
                texto_qr = opcion_prod

        texto_ingresado = st.text_input("Texto o código a codificar en el QR", value=texto_qr, key="input_texto_qr")

        if st.button("Generar Código QR", key="btn_generar_qr"):
            if texto_ingresado:
                # Generar imagen QR con la librería qrcode
                img_qr = qrcode.make(texto_ingresado)
                
                # Convertir la imagen a bytes para mostrarla y descargarla
                buffer = BytesIO()
                img_qr.save(buffer, format="PNG")
                byte_im = buffer.getvalue()

                st.image(byte_im, caption=f"Código QR para: {texto_ingresado}", width=250)
                
                st.download_button(
                    label="📥 Descargar Imagen QR (PNG)",
                    data=byte_im,
                    file_name=f"qr_{texto_ingresado.replace(' ', '_')}.png",
                    mime="image/png"
                )
            else:
                st.warning("Por favor, ingresa un texto o selecciona un producto.")

    with tab2:
        st.subheader("📊 Crear Código de Barras")
        st.write("Utiliza códigos numéricos o alfanuméricos estándar (tipo Code128).")
        
        texto_barras = st.text_input("Código para las barras (ej: SKU-100234)", key="input_texto_barras")

        if st.button("Generar Código de Barras", key="btn_generar_barras"):
            if texto_barras:
                try:
                    import barcode
                    from barcode.writer import ImageWriter

                    # Usar Code128 que soporta letras y números
                    CODE = barcode.get_class('code128')
                    barcode_obj = CODE(texto_barras, writer=ImageWriter())

                    buffer_barras = BytesIO()
                    barcode_obj.write(buffer_barras)
                    byte_barras = buffer_barras.getvalue()

                    st.image(byte_barras, caption=f"Código de Barras: {texto_barras}", width=350)

                    st.download_button(
                        label="📥 Descargar Código de Barras (PNG)",
                        data=byte_barras,
                        file_name=f"barras_{texto_barras}.png",
                        mime="image/png"
                    )
                except ImportError:
                    st.error("Falta instalar la librería 'python-barcode'. Puedes añadirla a tu archivo requirements.txt.")
                except Exception as e:
                    st.error(f"Error al generar el código de barras: {e}")
            else:
                st.warning("Por favor, ingresa un código válido.")

# ---------------------------------------------------------
# MÓDULO 14: PANEL DE ESTADÍSTICAS (DASHBOARD)
# ---------------------------------------------------------
elif menu == "14. Dashboard de Estadísticas":
    st.header("📊 Panel de Control y Estadísticas")
    st.write("Resumen visual del estado de tu inventario y operaciones de bodega.")

    import pandas as pd

    # Verificamos si existe inventario para graficar
    if 'df_inventario' in locals() and not df_inventario.empty:
        
        # Métricas principales (KPIs superiores)
        total_productos = len(df_inventario)
        
        # Intentar calcular stock total y valorización si existen las columnas
        col_stock = 'Stock Actual' if 'Stock Actual' in df_inventario.columns else df_inventario.columns[1]
        col_precio = 'Precio' if 'Precio' in df_inventario.columns else None
        
        stock_total = df_inventario[col_stock].sum() if col_stock else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="📦 Total de Productos", value=total_productos)
        with col2:
            st.metric(label="📊 Unidades en Stock", value=int(stock_total))
        with col3:
            if col_precio:
                valor_inventario = (df_inventario[col_stock] * df_inventario[col_precio]).sum()
                st.metric(label="💰 Valor Total Inventario", value=f"${valor_inventario:,.0f}")
            else:
                st.metric(label="💰 Estado de Bodega", value="Activo")

        st.markdown("---")

        # Gráficos rápidos con las herramientas nativas de Streamlit
        st.subheader("📈 Distribución de Stock por Producto")
        if 'Producto' in df_inventario.columns and col_stock:
            # Crear un gráfico de barras interactivo nativo
            df_chart = df_inventario.set_index('Producto')[col_stock]
            st.bar_chart(df_chart)
        else:
            st.info("No se encontraron las columnas necesarias para graficar el inventario.")

    else:
        st.warning("⚠️ No hay datos de inventario registrados todavía para mostrar en el Dashboard.")

    # Sección de estadísticas del Kardex (si existe)
    ARCHIVO_KARDEX = "kardex_movimientos.csv"
    if os.path.exists(ARCHIVO_KARDEX):
        st.markdown("---")
        st.subheader("📋 Resumen de Movimientos Recientes (Kardex)")
        df_kardex_dash = pd.read_csv(ARCHIVO_KARDEX)
        
        if not df_kardex_dash.empty:
            conteo_movs = df_kardex_dash['Tipo Movimiento'].value_counts()
            st.bar_chart(conteo_movs)
        else:
            st.info("El Kardex está vacío, registra entradas o salidas para ver estadísticas de movimiento.")

# ---------------------------------------------------------
# MÓDULO 15: REGISTRO DE PROVEEDORES Y CLIENTES
# ---------------------------------------------------------
elif menu == "15. Proveedores y Clientes":
    st.header("📇 Directorio de Proveedores y Clientes")
    st.write("Gestiona la información de contacto de tus proveedores y clientes frecuentes.")

    import pandas as pd
    import os

    ARCHIVO_CONTACTOS = "directorio_contactos.csv"

    # Cargar o crear base de datos de contactos
    if os.path.exists(ARCHIVO_CONTACTOS):
        df_contactos = pd.read_csv(ARCHIVO_CONTACTOS)
    else:
        df_contactos = pd.DataFrame(columns=[
            "Tipo", "Nombre / Razón Social", "Identificación / RUT", "Teléfono", "Correo", "Dirección"
        ])

    # Pestañas para separar el registro de la visualización
    tab_reg, tab_ver = st.tabs(["➕ Registrar Nuevo Contacto", "📋 Ver Directorio"])

    with tab_reg:
        st.subheader("Registrar Proveedor o Cliente")
        
        with st.form("form_contacto"):
            tipo_contacto = st.selectbox("Tipo de Contacto", ["Proveedor", "Cliente"])
            nombre = st.text_input("Nombre / Razón Social")
            rut = st.text_input("Identificación / RUT")
            telefono = st.text_input("Teléfono de contacto")
            correo = st.text_input("Correo electrónico")
            direccion = st.text_area("Dirección comercial")

            btn_guardar_contacto = st.form_submit_button("Guardar Contacto")

            if btn_guardar_contacto:
                if nombre and rut:
                    nuevo_registro = pd.DataFrame([{
                        "Tipo": tipo_contacto,
                        "Nombre / Razón Social": nombre,
                        "Identificación / RUT": rut,
                        "Teléfono": telefono,
                        "Correo": correo,
                        "Dirección": direccion
                    }])

                    df_contactos = pd.concat([df_contactos, nuevo_registro], ignore_index=True)
                    df_contactos.to_csv(ARCHIVO_CONTACTOS, index=False)

                    st.success(f"¡{tipo_contacto} '{nombre}' guardado exitosamente!")
                    st.rerun()
                else:
                    st.error("Por favor, completa al menos el Nombre y la Identificación/RUT.")

    with tab_ver:
        st.subheader("Directorio Comercial")

        if not df_contactos.empty:
            # Filtro por tipo
            filtro_tipo_contacto = st.selectbox("Filtrar por categoría", ["Todos", "Proveedor", "Cliente"], key="filtro_contactos")
            
            if filtro_tipo_contacto != "Todos":
                df_mostrar_contactos = df_contactos[df_contactos["Tipo"] == filtro_tipo_contacto]
            else:
                df_mostrar_contactos = df_contactos

            st.dataframe(df_mostrar_contactos, use_container_width=True)

            # Botón de descarga
            csv_contactos = df_contactos.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Directorio Completo (CSV)",
                data=csv_contactos,
                file_name="directorio_proveedores_clientes.csv",
                mime="text/csv",
            )
        else:
            st.info("Aún no hay contactos registrados en el sistema.")

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
