
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

from supabase import create_client, Client

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

from supabase import create_client, Client

# ---------------------------------------------------------
# 0. CONEXIÓN Y PERSISTENCIA CON SUPABASE
# ---------------------------------------------------------
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

def cargar_materiales_db():
    res = supabase.table("materiales").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        return df.rename(columns={
            "sku": "SKU", "nombre": "Nombre", "unidad": "Unidad", 
            "valor_unitario": "Valor_Unitario", "stock_actual": "Stock_Actual", 
            "ubicacion": "Ubicacion", "bodega": "Bodega"
        })
    return pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual", "Ubicacion", "Bodega"])

def cargar_movimientos_db():
    res = supabase.table("movimientos").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        return df.rename(columns={
            "id_mov": "ID_Mov", "tipo": "Tipo", "sku": "SKU", 
            "cantidad": "Cantidad", "origen_destino": "Origen/Destino", 
            "usuario": "Usuario", "fecha": "Fecha"
        })
    return pd.DataFrame(columns=["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen/Destino", "Fecha", "Usuario"])

# Inicializar estados cargando directamente desde la nube
if "materiales" not in st.session_state:
    st.session_state.materiales = cargar_materiales_db()
if "movimientos" not in st.session_state:
    st.session_state.movimientos = cargar_movimientos_db()
if "ordenes_picking" not in st.session_state:
    st.session_state.ordenes_picking = []
if "guias_despacho" not in st.session_state:
    st.session_state.guias_despacho = []

# ---------------------------------------------------------
# 0.1 AUTENTICACIÓN DE USUARIOS
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

if not st.session_state.autenticado:
    st.title("🔐 Acceso al WMS Marklogistic")
    st.markdown("Por favor, introduce tus credenciales para continuar.")
    with st.form("form_login"):
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        btn_login = st.form_submit_button("Iniciar Sesión")
        if btn_login:
            if verificar_credenciales(user_input, pass_input):
                st.session_state.autenticado = True
                st.session_state.usuario_actual = user_input
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()  # <--- Esto detiene la ejecución aquí si NO ha iniciado sesión

# =========================================================
# A PARTIR DE AQUÍ EL USUARIO YA ESTÁ LOGUEADO
# =========================================================

# ---------------------------------------------------------
# PANEL LATERAL / NAVEGACIÓN Y RESPALDO
# ---------------------------------------------------------
st.sidebar.title("📦 WMS Marklogistic")
st.sidebar.write(f"👤 Conectado como: **{st.session_state.get('usuario_actual', '')}**")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio("Módulos del Sistema", [
    "1. Creación de Materiales", "2. Ingreso de Materiales", "3. Picking de Materiales", 
    "4. Despacho y Guía", "5. Inventario", "6. Dashboard Gerencial", "7. Trazabilidad", 
    "8. Etiquetas", "9. Eliminar Transacciones", "10. Asistente IA", "11. Escáner de SKU", 
    "12. Gestión de Bodegas", "13. Auditoría y Logs", "14. Registro Fotográfico"
])
# ---------------------------------------------------------
# FUNCIONES DE AUTOMATIZACIÓN (PDF, CORREO Y SOPORTE)
# ---------------------------------------------------------
def enviar_correo_respaldo(remitente, password, destino, excel_bytes):
    try:
        msg = EmailMessage()
        msg['Subject'] = f"Respaldo Base de Datos ERP - {datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = remitente
        msg['To'] = destino
        msg.set_content("Adjunto encontrarás el respaldo actualizado en formato Excel de las tablas de materiales y movimientos de la bodega.")
        
        msg.add_attachment(
            excel_bytes,
            maintype='application',
            subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=f"respaldo_erp_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        )
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remitente, password)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"Error al enviar correo: {e}")
        return False

def generar_pdf_guia(guia):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "WMS MARKLOGISTIC S.A.")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, "R.U.T.: 76.543.210-K | Giro: Logística y Distribución")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(550, 750, "GUÍA DE TRASLADO")
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
    
    # Firmas
    c.line(50, 180, 220, 180)
    c.drawString(70, 165, "Firma Chofer / Transportista")
    c.line(380, 180, 550, 180)
    c.drawString(400, 165, "Firma Recinto / Cliente")
    
    if "Firma_Img" in guia and guia["Firma_Img"] is not None:
        try:
            img_array = guia["Firma_Img"]
            img_pil = Image.fromarray(img_array.astype('uint8'), 'RGBA')
            img_buffer = BytesIO()
            img_pil.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            c.drawImage(ImageReader(img_buffer), 380, 190, width=150, height=50, mask='auto')
        except:
            pass
    c.save()
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# PANEL LATERAL / NAVEGACIÓN Y RESPALDO
# ---------------------------------------------------------
st.sidebar.title("📦 WMS Marklogistic")
st.sidebar.write(f"👤 Conectado como: **{st.session_state.get('usuario_actual', '')}**")
if st.sidebar.button("Cerrar Sesión", key="btn_cerrar_sesion"):
    st.session_state.autenticado = False
    st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio("Módulos del Sistema", [
    "1. Creación de Materiales", "2. Ingreso de Materiales", "3. Picking de Materiales", 
    "4. Despacho y Guía", "5. Inventario", "6. Dashboard Gerencial", "7. Trazabilidad", 
    "8. Etiquetas", "9. Eliminar Transacciones", "10. Asistente IA", "11. Escáner de SKU", 
    "12. Gestión de Bodegas", "13. Auditoría y Logs", "14. Registro Fotográfico"
])

st.sidebar.markdown("---")
st.sidebar.subheader("📧 Envío Automático de Reportes")
correo_remitente = st.sidebar.text_input("Correo Remitente (Gmail)", value="marco.inostroza63.mi@gmail.com")
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

# ---------------------------------------------------------
# MÓDULO 1: CREACIÓN DE MATERIALES Y CARGA MASIVA
# ---------------------------------------------------------
if menu == "1. Creación de Materiales":
    st.header("📋 Registro y Carga Masiva de Materiales / Maestro de SKU")
    tab_manual, tab_masivo = st.tabs(["✍️ Registro Manual", "📂 Carga Masiva (Excel)"])
    
    with tab_manual:
        with st.form("form_nuevo_mat"):
            st.subheader("Registro Manual de Material")
            c1, c2 = st.columns(2)
            with c1:
                sku_m = st.text_input("SKU").strip().upper()
                nom_m = st.text_input("Nombre / Descripción")
                uni_m = st.selectbox("Unidad", ["Unidades", "Cajas", "Pallets", "Kg", "Metros"])
            with c2:
                ubi_m = st.text_input("Ubicación en Bodega", value="A-00-0").strip().upper()
                val_m = st.number_input("Valor Unitario ($)", min_value=0.0, value=0.0, step=100.0)
                stk_m = st.number_input("Stock Inicial", min_value=0, value=0)

            if st.form_submit_button("Guardar Material"):
                if not sku_m or not nom_m:
                    st.error("SKU y Nombre son obligatorios.")
                elif sku_m in st.session_state.materiales["SKU"].values:
                    st.error("El SKU ya existe.")
                else:
                    nuevo_registro = {
                        "sku": sku_m, "nombre": nom_m, "unidad": uni_m,
                        "valor_unitario": val_m, "stock_actual": stk_m,
                        "ubicacion": ubi_m, "bodega": "Bodega Central Antofagasta"
                    }
                    try:
                        supabase.table("materiales").insert(nuevo_registro).execute()
                        st.session_state.materiales = cargar_materiales_db()
                        st.success(f"Material {sku_m} guardado en Supabase correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar en Supabase: {e}")

    with tab_masivo:
        st.subheader("Carga Masiva de SKUs mediante Archivo Excel")
        st.markdown("Sube un archivo de Excel con las columnas: `SKU`, `Nombre`, `Unidad`, `Valor_Unitario`, `Stock_Actual`, `Ubicacion`.")
        archivo_subido = st.file_uploader("Seleccionar archivo Excel", type=["xlsx", "xls"])
        if archivo_subido is not None:
            try:
                df_carga = pd.read_excel(archivo_subido)
                st.write("Vista previa de los datos cargados:", df_carga.head())
                if st.button("Procesar e Insertar en Supabase"):
                    conteo_exitosos = 0
                    for _, row in df_carga.iterrows():
                        reg_masivo = {
                            "sku": str(row.get("SKU", "")).strip().upper(),
                            "nombre": str(row.get("Nombre", "")),
                            "unidad": str(row.get("Unidad", "Unidades")),
                            "valor_unitario": float(row.get("Valor_Unitario", 0.0)),
                            "stock_actual": int(row.get("Stock_Actual", 0)),
                            "ubicacion": str(row.get("Ubicacion", "A-00-0")).strip().upper(),
                            "bodega": "Bodega Central Antofagasta"
                        }
                        if reg_masivo["sku"]:
                            try:
                                supabase.table("materiales").upsert(reg_masivo).execute()
                                conteo_exitosos += 1
                            except Exception:
                                pass
                    st.session_state.materiales = cargar_materiales_db()
                    st.success(f"¡Carga masiva finalizada! Se procesaron {conteo_exitosos} registros correctamente en Supabase.")
                    st.rerun()
            except Exception as e:
                st.error(f"Error al leer el archivo Excel: {e}")

# ---------------------------------------------------------
# MÓDULO 2: INGRESO DE MATERIALES
# ---------------------------------------------------------
elif menu == "2. Ingreso de Materiales":
    st.header("📥 Recepción e Ingreso a Bodega")
    if st.session_state.materiales.empty:
        st.info("Primero debe crear materiales.")
    else:
        with st.form("form_ingreso"):
            sku_ingreso = st.selectbox("Seleccionar SKU a Ingresar", st.session_state.materiales["SKU"])
            cant_ingreso = st.number_input("Cantidad a Ingresar", min_value=1, value=1)
            proveedor_origen = st.text_input("Proveedor / Origen (Opcional)")
            if st.form_submit_button("Registrar Ingreso"):
                mat_actual = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_ingreso].iloc[0]
                stock_viejo = int(mat_actual["Stock_Actual"])
                nuevo_stock = stock_viejo + cant_ingreso
                try:
                    supabase.table("materiales").update({"stock_actual": nuevo_stock}).eq("sku", sku_ingreso).execute()
                    supabase.table("movimientos").insert({
                        "id_mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                        "tipo": "INGRESO", "sku": sku_ingreso, "cantidad": cant_ingreso,
                        "origen_destino": proveedor_origen or "Recepción General",
                        "usuario": st.session_state.get('usuario_actual', 'admin'),
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }).execute()
                    st.session_state.materiales = cargar_materiales_db()
                    st.session_state.movimientos = cargar_movimientos_db()
                    st.success(f"¡Ingreso registrado y guardado en Supabase!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar en Supabase: {e}")

# ---------------------------------------------------------
# MÓDULO 10: ASISTENTE IA
# ---------------------------------------------------------
elif menu == "10. Asistente IA":
    st.header("🤖 Asistente Inteligente")
    if "GEMINI_API_KEY" in st.secrets:
        try:
            from google import genai
            client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            pregunta = st.text_input("Consulta al ERP (Ej: ¿Qué productos tienen bajo stock?)")
            if st.button("Consultar IA") and pregunta:
                resumen = st.session_state.materiales.to_string()
                response = client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=f"Eres un experto en logística. Datos de bodega:\n{resumen}\nResponde a: {pregunta}"
                )
                st.success(response.text)
        except Exception as e:
            st.error(f"Error IA: {e}")
    else:
        st.warning("Configura tu GEMINI_API_KEY en los secretos de Streamlit.")

# ---------------------------------------------------------
# 0. CONEXIÓN Y PERSISTENCIA CON SUPABASE
# ---------------------------------------------------------
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

def cargar_materiales_db():
    res = supabase.table("materiales").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        return df.rename(columns={
            "sku": "SKU",
            "nombre": "Nombre",
            "unidad": "Unidad",
            "valor_unitario": "Valor_Unitario",
            "stock_actual": "Stock_Actual",
            "ubicacion": "Ubicacion",
            "bodega": "Bodega"
        })
    return pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual", "Ubicacion", "Bodega"])

def cargar_movimientos_db():
    res = supabase.table("movimientos").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        return df.rename(columns={
            "id_mov": "ID_Mov",
            "tipo": "Tipo",
            "sku": "SKU",
            "cantidad": "Cantidad",
            "origen_destino": "Origen/Destino",
            "usuario": "Usuario",
            "fecha": "Fecha"
        })
    return pd.DataFrame(columns=["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen/Destino", "Fecha", "Usuario"])

# Inicializar estados cargando directamente desde la nube
if "materiales" not in st.session_state:
    st.session_state.materiales = cargar_materiales_db()

if "movimientos" not in st.session_state:
    st.session_state.movimientos = cargar_movimientos_db()

if "ordenes_picking" not in st.session_state:
    st.session_state.ordenes_picking = []

if "guias_despacho" not in st.session_state:
    st.session_state.guias_despacho = []

# ---------------------------------------------------------
# 0.1 AUTENTICACIÓN DE USUARIOS
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

if not st.session_state.autenticado:
    st.title("🔐 Acceso al WMS Marklogistic")
    st.markdown("Por favor, introduce tus credenciales para continuar.")
    with st.form("form_login"):
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        btn_login = st.form_submit_button("Iniciar Sesión")
        if btn_login:
            if verificar_credenciales(user_input, pass_input):
                st.session_state.autenticado = True
                st.session_state.usuario_actual = user_input
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ---------------------------------------------------------
# FUNCIONES DE AUTOMATIZACIÓN (PDF CON FIRMA & CORREO)
# ---------------------------------------------------------

def generar_pdf_guia(guia):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "WMS MARKLOGISTIC S.A.")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, "R.U.T.: 76.543.210-K | Giro: Logística y Distribución")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(550, 750, "GUÍA DE TRASLADO")
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
    
    # Firmas
    c.line(50, 180, 220, 180)
    c.drawString(70, 165, "Firma Chofer / Transportista")
    c.line(380, 180, 550, 180)
    c.drawString(400, 165, "Firma Recinto / Cliente")
    
    # Estampar firma digital si existe
    if "Firma_Img" in guia and guia["Firma_Img"] is not None:
        try:
            img_array = guia["Firma_Img"]
            img_pil = Image.fromarray(img_array.astype('uint8'), 'RGBA')
            img_buffer = BytesIO()
            img_pil.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            c.drawImage(ImageReader(img_buffer), 380, 190, width=150, height=50, mask='auto')
        except:
            pass
            
    c.save()
    buffer.seek(0)
    return buffer
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
menu = st.sidebar.radio("Módulos del Sistema", [
    "1. Creación de Materiales", "2. Ingreso de Materiales", "3. Picking de Materiales", 
    "4. Despacho y Guía", "5. Inventario", "6. Dashboard Gerencial", "7. Trazabilidad", 
    "8. Etiquetas", "9. Eliminar Transacciones", "10. Asistente IA", "11. Escáner de SKU", 
    "12. Gestión de Bodegas", "13. Auditoría y Logs", "14. Registro Fotográfico"
])

st.sidebar.markdown("---")
st.sidebar.subheader("📧 Envío Automático de Reportes")
correo_remitente = st.sidebar.text_input("Correo Remitente (Gmail)", value="marco.inostroza63.mi@gmail.com")
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
# MÓDULO 1: CREACIÓN DE MATERIALES Y CARGA MASIVA
# ---------------------------------------------------------
if menu == "1. Creación de Materiales":
    st.header("📋 Registro y Carga Masiva de Materiales / Maestro de SKU")
    tab_manual, tab_masivo = st.tabs(["✍️ Registro Manual", "📂 Carga Masiva (Excel)"])
    
    with tab_manual:
        with st.form("form_nuevo_mat"):
            st.subheader("Registro Manual de Material")
            c1, c2 = st.columns(2)
            with c1:
                sku_m = st.text_input("SKU").strip().upper()
                nom_m = st.text_input("Nombre / Descripción")
                uni_m = st.selectbox("Unidad", ["Unidades", "Cajas", "Pallets", "Kg", "Metros"])
            with c2:
                ubi_m = st.text_input("Ubicación en Bodega", value="A-00-0").strip().upper()
                val_m = st.number_input("Valor Unitario ($)", min_value=0.0, value=0.0, step=100.0)
                stk_m = st.number_input("Stock Inicial", min_value=0, value=0)

            if st.form_submit_button("Guardar Material"):
                if not sku_m or not nom_m:
                    st.error("SKU y Nombre son obligatorios.")
                elif sku_m in st.session_state.materiales["SKU"].values:
                    st.error("El SKU ya existe.")
                else:
                    nuevo_registro = {
                        "sku": sku_m,
                        "nombre": nom_m,
                        "unidad": uni_m,
                        "valor_unitario": val_m,
                        "stock_actual": stk_m,
                        "ubicacion": ubi_m,
                        "bodega": "Bodega Central Antofagasta"
                    }
                    try:
                        supabase.table("materiales").insert(nuevo_registro).execute()
                        st.session_state.materiales = cargar_materiales_db()
                        st.success(f"Material {sku_m} guardado en Supabase correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar en Supabase: {e}")

    with tab_masivo:
        st.subheader("Carga Masiva de SKUs mediante Archivo Excel")
        st.markdown("Sube un archivo de Excel con las columnas: `SKU`, `Nombre`, `Unidad`, `Valor_Unitario`, `Stock_Actual`, `Ubicacion`.")
        
        archivo_subido = st.file_uploader("Seleccionar archivo Excel", type=["xlsx", "xls"])
        if archivo_subido is not None:
            try:
                df_carga = pd.read_excel(archivo_subido)
                st.write("Vista previa de los datos cargados:", df_carga.head())
                
                if st.button("Procesar e Insertar en Supabase"):
                    conteo_exitosos = 0
                    for _, row in df_carga.iterrows():
                        reg_masivo = {
                            "sku": str(row.get("SKU", "")).strip().upper(),
                            "nombre": str(row.get("Nombre", "")),
                            "unidad": str(row.get("Unidad", "Unidades")),
                            "valor_unitario": float(row.get("Valor_Unitario", 0.0)),
                            "stock_actual": int(row.get("Stock_Actual", 0)),
                            "ubicacion": str(row.get("Ubicacion", "A-00-0")).strip().upper(),
                            "bodega": "Bodega Central Antofagasta"
                        }
                        if reg_masivo["sku"]:
                            try:
                                supabase.table("materiales").upsert(reg_masivo).execute()
                                conteo_exitosos += 1
                            except Exception:
                                pass
                    
                    st.session_state.materiales = cargar_materiales_db()
                    st.success(f"¡Carga masiva finalizada! Se procesaron {conteo_exitosos} registros correctamente en Supabase.")
                    st.rerun()
            except Exception as e:
                st.error(f"Error al leer el archivo Excel: {e}")
# ---------------------------------------------------------
# MÓDULO 2: INGRESO DE MATERIALES
# ---------------------------------------------------------
elif menu == "2. Ingreso de Materiales":
    st.header("📥 Recepción e Ingreso a Bodega")
    if st.session_state.materiales.empty:
        st.info("Primero debe crear materiales.")
    else:
        with st.form("form_ingreso"):
            sku_ingreso = st.selectbox("Seleccionar SKU a Ingresar", st.session_state.materiales["SKU"])
            cant_ingreso = st.number_input("Cantidad a Ingresar", min_value=1, value=1)
            proveedor_origen = st.text_input("Proveedor / Origen (Opcional)")
            
            if st.form_submit_button("Registrar Ingreso"):
                mat_actual = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_ingreso].iloc[0]
                stock_viejo = int(mat_actual["Stock_Actual"])
                nuevo_stock = stock_viejo + cant_ingreso
                
                try:
                    # 1. Actualizar stock actual en la tabla 'materiales' de Supabase
                    supabase.table("materiales").update({"stock_actual": nuevo_stock}).eq("sku", sku_ingreso).execute()
                    
                    # 2. Registrar el movimiento en la tabla 'movimientos' de Supabase
                    supabase.table("movimientos").insert({
                        "id_mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                        "tipo": "INGRESO",
                        "sku": sku_ingreso,
                        "cantidad": cant_ingreso,
                        "origen_destino": proveedor_origen or "Recepción General",
                        "usuario": st.session_state.get('usuario_actual', 'admin'),
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }).execute()
                    
                    # 3. Recargar los datos desde la nube
                    st.session_state.materiales = cargar_materiales_db()
                    st.session_state.movimientos = cargar_movimientos_db()
                    
                    st.success(f"¡Ingreso de {cant_ingreso} unidades para el SKU {sku_ingreso} registrado y guardado en Supabase!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar en Supabase: {e}")
# ---------------------------------------------------------
# MÓDULO 3: PICKING DE MATERIALES
# ---------------------------------------------------------
elif menu == "3. Picking de Materiales":
    st.header("📦 Órdenes de Picking")
    if st.session_state.materiales.empty:
        st.info("No hay materiales registrados.")
    else:
        with st.form("form_picking"):
            cliente = st.text_input("Cliente / Destino")
            sku_pick = st.selectbox("Material a Extraer", st.session_state.materiales["SKU"])
            mat_sel = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_pick].iloc[0]
            st.info(f"📍 **Ubicación:** {mat_sel.get('Ubicacion', 'N/A')} | **Stock Disponible:** {mat_sel['Stock_Actual']}")
            cant_pick = st.number_input("Cantidad a Preparar", min_value=1, value=1)
            if st.form_submit_button("Crear Orden de Picking"):
                if cant_pick > mat_sel['Stock_Actual']:
                    st.error("Stock insuficiente.")
                else:
                    id_ord = f"PICK-{len(st.session_state.ordenes_picking)+1:04d}"
                    st.session_state.ordenes_picking.append({
                        "ID_Picking": id_ord,
                        "Cliente": cliente,
                        "SKU": sku_pick,
                        "Ubicacion": mat_sel.get('Ubicacion', 'N/A'),
                        "Cantidad": cant_pick,
                        "Estado": "Pendiente Despacho"
                    })
                    guardar_datos()
                    st.success(f"Orden {id_ord} creada con éxito.")
                    st.rerun()
        if st.session_state.ordenes_picking:
            st.markdown("---")
            st.subheader("Historial de Órdenes de Picking")
            st.dataframe(pd.DataFrame(st.session_state.ordenes_picking), use_container_width=True)
# ---------------------------------------------------------
# MÓDULO 4: DESPACHO Y GUÍA DE TRASLADO
# ---------------------------------------------------------
elif menu == "4. Despacho y Guía":
    st.header("🚚 Despacho y Generación de Guía de Traslado")
    
    if not st.session_state.ordenes_picking:
        st.info("No hay órdenes de picking disponibles para despachar. Primero genera una orden en el Módulo 3.")
    else:
        st.subheader("Historial de Órdenes de Picking")
        df_picking = pd.DataFrame(st.session_state.ordenes_picking)
        st.dataframe(df_picking, use_container_width=True)
        
        # Seleccionar orden pendiente de despacho
        ordenes_pendientes = [o["ID_Picking"] for o in st.session_state.ordenes_picking if o.get("Estado") == "Pendiente Despacho"]
        
        if not ordenes_pendientes:
            st.warning("Todas las órdenes de picking ya han sido despachadas.")
        else:
            id_sel = st.selectbox("Seleccionar Orden de Picking a Despachar", ordenes_pendientes)
            
            # Inicializamos de forma segura la variable antes de usarla
            datos_orden = next((o for o in st.session_state.ordenes_picking if o["ID_Picking"] == id_sel), None)
            
            if datos_orden:
                st.markdown("---")
                st.subheader(f"Datos de Despacho para Orden: `{id_sel}`")
                
                with st.form("form_despacho_guia"):
                    c_d1, c_d2 = st.columns(2)
                    with c_d1:
                        cliente = st.text_input("Cliente", value=datos_orden.get("Cliente", ""))
                        rut_cliente = st.text_input("R.U.T. Cliente", value="76.123.456-7")
                        transporte = st.text_input("Empresa de Transporte", value="Transportes Marklogistic")
                        nombre_conductor = st.text_input("Nombre del Conductor")
                    with c_d2:
                        rut_conductor = st.text_input("R.U.T. Conductor")
                        patente = st.text_input("Patente del Vehículo")
                        motivo = st.selectbox("Motivo de Traslado", ["Venta", "Traslado entre bodegas", "Devolución", "Préstamo"])
                    
                    st.markdown("---")
                    st.subheader("✍️ Firma Digital del Receptor / Transportista")
                    st.caption("Dibuja tu firma a continuación dentro del recuadro:")
                    
                    canvas_result = st_canvas(
                        fill_color="rgba(255, 255, 255, 0)",
                        stroke_width=2,
                        stroke_color="#000000",
                        background_color="#f0f2f6",
                        height=150,
                        width=400,
                        drawing_mode="freedraw",
                        key="canvas_firma",
                    )

                    btn_confirmar = st.form_submit_button("Confirmar Despacho y Generar Guía")

                if btn_confirmar:
                    firma_valida = False
                    if canvas_result is not None:
                        try:
                            if canvas_result.image_data is not None and (canvas_result.image_data[:, :, 3] > 0).any():
                                firma_valida = True
                        except RuntimeError:
                            firma_valida = False

                    if not firma_valida:
                        st.warning("⚠️ Debes registrar la firma en el recuadro antes de confirmar el despacho.")
                    else:
                        sku_afectado = datos_orden["SKU"]
                        cantidad_despacho = datos_orden["Cantidad"]
                        
                        # Actualizar stock
                        idx_mat = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_afectado].tolist()[0]
                        st.session_state.materiales.loc[idx_mat, "Stock_Actual"] -= cantidad_despacho
                        
                        # Cambiar estado de la orden de picking
                        for o in st.session_state.ordenes_picking:
                            if o["ID_Picking"] == id_sel:
                                o["Estado"] = "Despachado"
                        
                        # Registrar movimiento
                        mov = pd.DataFrame([{
                            "ID_Mov": f"MOV-{len(st.session_state.movimientos)+1:04d}", 
                            "Tipo": "DESPACHO", 
                            "SKU": sku_afectado, 
                            "Cantidad": cantidad_despacho, 
                            "Origen/Destino": cliente, 
                            "Usuario": st.session_state.get('usuario_actual', 'admin'), 
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
                        
                        # Generar guía
                        num_guia = f"GD-{len(st.session_state.guias_despacho)+1:04d}"
                        guia_data = {
                            "Numero_Guia": num_guia, 
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), 
                            "Cliente": cliente, 
                            "Rut": rut_cliente, 
                            "SKU": sku_afectado, 
                            "Cantidad": cantidad_despacho, 
                            "Transporte": transporte, 
                            "Conductor": nombre_conductor, 
                            "Rut_Conductor": rut_conductor, 
                            "Patente": patente, 
                            "Motivo": motivo, 
                            "Firma_Img": canvas_result.image_data
                        }
                        
                        st.session_state.guias_despacho.append(guia_data)
                        guardar_datos()
                        
                        st.success(f"¡Despacho realizado con éxito! Guía N° **{num_guia}** generada.")
                        st.session_state.ultima_guia = guia_data
                        st.rerun()

# ---------------------------------------------------------
# MÓDULO 5: INVENTARIO
# ---------------------------------------------------------
elif menu == "5. Inventario":
    st.header("📊 Control de Inventario en Tiempo Real")
    col_k1, col_k2 = st.columns(2)
    with col_k1:
        st.metric("Total SKU Registrados", len(st.session_state.materiales))
    with col_k2:
        st.metric("Total Unidades", int(st.session_state.materiales["Stock_Actual"].sum()) if not st.session_state.materiales.empty else 0)
    st.markdown("---")
    st.dataframe(st.session_state.materiales, use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 6: DASHBOARD GERENCIAL
# ---------------------------------------------------------
elif menu == "6. Dashboard Gerencial":
    st.header("📈 Dashboard Gerencial y Analítica de Bodega")
    if st.session_state.materiales.empty:
        st.info("No hay suficientes datos de materiales para generar el dashboard.")
    else:
        import plotly.express as px
        total_skus = len(st.session_state.materiales)
        stock_total = int(st.session_state.materiales["Stock_Actual"].sum())
        val_inventario = (st.session_state.materiales["Stock_Actual"] * st.session_state.materiales["Valor_Unitario"]).sum()
        
        col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
        col_kpi1.metric("📦 Total de SKUs", total_skus)
        col_kpi2.metric("📊 Unidades en Stock", f"{stock_total:,.0f}")
        col_kpi3.metric("💰 Valorización Total Inventario", f"${val_inventario:,.0f}")
        
        st.markdown("---")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("Top Productos con Mayor Stock")
            df_top_stock = st.session_state.materiales.sort_values(by="Stock_Actual", ascending=False).head(10)
            fig_stock = px.bar(df_top_stock, x="SKU", y="Stock_Actual", text="Stock_Actual", color="Stock_Actual", color_continuous_scale="Blues", title="Top 10 SKUs con Mayor Cantidad en Bodega")
            st.plotly_chart(fig_stock, use_container_width=True)
        with col_g2:
            st.subheader("Valorización por Producto")
            df_val = st.session_state.materiales.copy()
            df_val["Valor_Total"] = df_val["Stock_Actual"] * df_val["Valor_Unitario"]
            df_top_val = df_val.sort_values(by="Valor_Total", ascending=False).head(10)
            fig_val = px.pie(df_top_val, names="SKU", values="Valor_Total", title="Distribución del Valor en Inventario (Top SKU)", hole=0.4)
            st.plotly_chart(fig_val, use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 7: TRAZABILIDAD
# ---------------------------------------------------------
elif menu == "7. Trazabilidad":
    st.header("🔍 Historial de Movimientos")
    if st.session_state.movimientos.empty:
        st.info("No hay movimientos registrados.")
    else:
        st.dataframe(st.session_state.movimientos.sort_values(by="Fecha", ascending=False), use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 8: ETIQUETAS
# ---------------------------------------------------------
elif menu == "8. Etiquetas":
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
            [data-testid="stSidebar"], header, .stButton, .stSelectbox, .stNumberInput { display: none !important; }
            body { background-color: white !important; }
        }
        .etiqueta-box { border: 2px dashed #000; width: 320px; padding: 15px; font-family: Arial, sans-serif; background: white; color: black; margin-bottom: 20px; border-radius: 8px; }
        </style>
        """, unsafe_allow_html=True)

        for i in range(cantidad_copias):
            html_etiqueta = f"""
            <div class="etiqueta-box">
                <h4 style="text-align: center; margin: 0 0 10px 0; font-size: 16px;">WMS MARKLOGISTIC</h4>
                <hr style="border: 1px solid #000; margin: 5px 0;">
                <p style="margin: 5px 0; font-size: 14px;"><b>SKU:</b> {mat_info['SKU']}</p>
                <p style="margin: 5px 0; font-size: 14px;"><b>Descripción:</b> {mat_info['Nombre']}</p>
                <p style="margin: 5px 0; font-size: 14px;"><b>Ubicación:</b> <span style="font-size: 16px; font-weight: bold;">{mat_info.get('Ubicacion', 'N/A')}</span></p>
                <p style="margin: 5px 0; font-size: 14px;"><b>Bodega:</b> {mat_info.get('Bodega', 'N/A')}</p>
                <p style="margin: 5px 0; font-size: 14px;"><b>Unidad:</b> {mat_info['Unidad']}</p>
                <p style="margin: 5px 0; font-size: 14px;"><b>Valor Unit.:</b> ${mat_info['Valor_Unitario']:,.0f}</p>
                <div style="text-align: center; margin-top: 10px; font-size: 12px; font-family: monospace;">
                    ||||| | |||| ||| || ||||
                </div>
            </div>
            """
            st.markdown(html_etiqueta, unsafe_allow_html=True)
        st.info("💡 **Para imprimir o guardar en PDF:** Presiona las teclas **`Ctrl + P`** en tu teclado.")

# ---------------------------------------------------------
# MÓDULO 9: ELIMINAR TRANSACCIONES
# ---------------------------------------------------------
elif menu == "9. Eliminar Transacciones":
    st.header("🗑️ Gestión y Anulación de Transacciones")
    if st.session_state.movimientos.empty:
        st.info("No hay transacciones registradas.")
    else:
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
# MÓDULO 10: ASISTENTE IA
# ---------------------------------------------------------
elif menu == "10. Asistente IA":
    st.header("🤖 Asistente Inteligente")
    if "GEMINI_API_KEY" in st.secrets:
        try:
            from google import genai
            client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            pregunta = st.text_input("Consulta al ERP (Ej: ¿Qué productos tienen bajo stock?)")
            if st.button("Consultar IA") and pregunta:
                resumen = st.session_state.materiales.to_string()
                response = client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=f"Eres un experto en logística. Datos de bodega:\n{resumen}\nResponde a: {pregunta}"
                )
                st.success(response.text)
        except Exception as e:
            st.error(f"Error IA: {e}")
    else:
        st.warning("Configura tu GEMINI_API_KEY en los secretos.")

# ---------------------------------------------------------
# MÓDULO 11: ESCÁNER DE SKU
# ---------------------------------------------------------
elif menu == "11. Escáner de SKU":
    st.header("📷 Escáner de SKU (Cámara Web o USB)")
    tipo_escaneo = st.radio("Selecciona el método de lectura:", ["Pistola / Lector USB", "Cámara Web (QR / Barras)"])
    sku_detectado = None
    
    if tipo_escaneo == "Pistola / Lector USB":
        st.info("💡 Haz clic en el campo de abajo y dispara con tu pistola lectora.")
        sku_input = st.text_input("Esperando lectura de pistola USB...").strip().upper()
        if sku_input:
            sku_detectado = sku_input
    else:
        st.info("📸 Enfoca el código QR del producto con la cámara.")
        imagen_camara = st.camera_input("Capturar Código")
        if imagen_camara is not None:
            try:
                import cv2
                import numpy as np
                bytes_data = imagen_camara.getvalue()
                np_arr = np.frombuffer(bytes_data, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                detector = cv2.QRCodeDetector()
                data, bbox, _ = detector.detectAndDecode(img)
                if data:
                    sku_detectado = data.strip().upper()
                    st.success(f"¡Código detectado: **{sku_detectado}**!")
            except Exception as e:
                st.error(f"Error al procesar la cámara: {e}")

    if sku_detectado:
        st.markdown("---")
        st.subheader(f"🔍 Resultado para SKU: `{sku_detectado}`")
        if sku_detectado in st.session_state.materiales["SKU"].values:
            mat_info = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_detectado].iloc[0]
            st.success(f"**Material Encontrado:** {mat_info['Nombre']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Stock Actual", mat_info['Stock_Actual'])
            c2.metric("Ubicación", mat_info.get('Ubicacion', 'N/A'))
            c3.metric("Valor Unitario", f"${mat_info['Valor_Unitario']:,.0f}")
        else:
            st.error(f"⚠️ El SKU `{sku_detectado}` no se encuentra registrado.")

# ---------------------------------------------------------
# MÓDULO 12: GESTIÓN DE MÚLTIPLES BODEGAS
# ---------------------------------------------------------
elif menu == "12. Gestión de Bodegas":
    st.header("🏢 Gestión de Múltiples Centros de Distribución y Transferencias")
    bodegas_disponibles = ["Bodega Central Antofagasta", "Bodega Norte", "Bodega Tránsito", "Centro de Acopio Sur"]
    tab_crear_mat_bodega, tab_transferencias = st.tabs(["📝 Materiales por Bodega", "🔄 Transferencia Interna entre Bodegas"])
    
    with tab_crear_mat_bodega:
        if st.session_state.materiales.empty:
            st.info("No hay materiales creados.")
        else:
            with st.form("form_mat_bodega"):
                sku_asig = st.selectbox("Seleccionar SKU", st.session_state.materiales["SKU"])
                bodega_sel = st.selectbox("Seleccionar Bodega", bodegas_disponibles)
                if st.form_submit_button("Actualizar Bodega"):
                    idx = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_asig].tolist()[0]
                    st.session_state.materiales.loc[idx, "Bodega"] = bodega_sel
                    guardar_datos()
                    st.success(f"SKU `{sku_asig}` asignado a **{bodega_sel}**.")
                    st.rerun()
            st.dataframe(st.session_state.materiales, use_container_width=True)

    with tab_transferencias:
        if st.session_state.materiales.empty:
            st.info("No hay inventario disponible.")
        else:
            with st.form("form_transferencia"):
                sku_trans = st.selectbox("SKU a Transferir", st.session_state.materiales["SKU"])
                mat_row = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_trans].iloc[0]
                bodega_origen = mat_row.get("Bodega", "Bodega Central Antofagasta")
                stock_actual_origen = mat_row["Stock_Actual"]
                st.info(f"📍 **Origen:** `{bodega_origen}` | **Stock:** `{stock_actual_origen}`")
                bodega_destino = st.selectbox("Bodega de Destino", [b for b in bodegas_disponibles if b != bodega_origen])
                cant_transferir = st.number_input("Cantidad a Transferir", min_value=1, value=1)
                if st.form_submit_button("Ejecutar Transferencia"):
                    if cant_transferir > stock_actual_origen:
                        st.error("Supera el stock disponible.")
                    else:
                        idx_mat = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_trans].tolist()[0]
                        st.session_state.materiales.loc[idx_mat, "Stock_Actual"] -= cant_transferir
                        st.session_state.materiales.loc[idx_mat, "Bodega"] = bodega_destino
                        
                        mov = pd.DataFrame([{
                            "ID_Mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                            "Tipo": "TRANSFERENCIA",
                            "SKU": sku_trans,
                            "Cantidad": cant_transferir,
                            "Origen/Destino": f"De {bodega_origen} a {bodega_destino}",
                            "Usuario": st.session_state.get('usuario_actual', 'admin'),
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
                        guardar_datos()
                        st.success("¡Transferencia exitosa!")
                        st.rerun()

# ---------------------------------------------------------
# MÓDULO 13: AUDITORÍA Y LOGS
# ---------------------------------------------------------
elif menu == "13. Auditoría y Logs":
    st.header("📋 Auditoría y Registro de Actividad por Usuario")
    if st.session_state.movimientos.empty:
        st.info("No hay registros de actividad.")
    else:
        df_logs = st.session_state.movimientos.copy()
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            usuarios_unicos = ["Todos"] + list(df_logs["Usuario"].dropna().unique())
            filtro_usuario = st.selectbox("Filtrar por Usuario", usuarios_unicos)
        with col_f2:
            tipos_unicos = ["Todos"] + list(df_logs["Tipo"].dropna().unique())
            filtro_tipo = st.selectbox("Filtrar por Tipo de Transacción", tipos_unicos)
            
        if filtro_usuario != "Todos":
            df_logs = df_logs[df_logs["Usuario"] == filtro_usuario]
        if filtro_tipo != "Todos":
            df_logs = df_logs[df_logs["Tipo"] == filtro_tipo]
            
        st.markdown("---")
        st.metric("Total de Acciones Registradas", len(df_logs))
        st.dataframe(df_logs.sort_values(by="Fecha", ascending=False), use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 14: REGISTRO FOTOGRÁFICO
# ---------------------------------------------------------
elif menu == "14. Registro Fotográfico":
    st.header("📸 Registro Fotográfico y Datos Adjuntos")
    if "registro_fotos" not in st.session_state:
        st.session_state.registro_fotos = []
        
    with st.form("form_foto_adjunto"):
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            sku_foto = st.selectbox("SKU Asociado (Opcional)", ["N/Ninguno"] + list(st.session_state.materiales["SKU"]))
            tipo_evidencia = st.selectbox("Tipo de Evidencia", ["Recepción", "Merma", "Despacho", "Calidad", "Factura", "Otro"])
        with c_f2:
            referencia_doc = st.text_input("N° de Documento / Lote (Opcional)")
            observacion = st.text_area("Comentarios u Observaciones")
            
        usar_camara = st.checkbox("🟢 Activar la cámara web para tomar foto")
        foto_capturada = st.camera_input("Capturar Evidencia") if usar_camara else None
        archivo_adjunto = st.file_uploader("O adjuntar imagen (PNG, JPG)", type=["png", "jpg", "jpeg"])
        
        if st.form_submit_button("Guardar Evidencia"):
            imagen_final = foto_capturada if foto_capturada is not None else archivo_adjunto
            if imagen_final is None:
                st.error("⚠️ Debes capturar una foto o adjuntar un archivo.")
            else:
                nueva_foto = {
                    "ID_Foto": f"FOTO-{len(st.session_state.registro_fotos)+1:04d}",
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Usuario": st.session_state.get('usuario_actual', 'admin'),
                    "SKU": sku_foto if sku_foto != "N/Ninguno" else "GENERAL",
                    "Tipo": tipo_evidencia,
                    "Referencia": referencia_doc or "S/R",
                    "Comentarios": observacion or "Sin comentarios",
                    "Imagen": imagen_final
                }
                st.session_state.registro_fotos.append(nueva_foto)
                st.success("¡Evidencia registrada con éxito!")
                st.rerun()
