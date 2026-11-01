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

# Inicializar estados
if "materiales" not in st.session_state:
    st.session_state.materiales = cargar_materiales_db()
if "movimientos" not in st.session_state:
    st.session_state.movimientos = cargar_movimientos_db()

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
    st.stop()  # Detiene la ejecución aquí si no ha iniciado sesión

# ---------------------------------------------------------
# FUNCIONES AUXILIARES (CORREO Y PDF)
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

# ---------------------------------------------------------
# PANEL LATERAL / NAVEGACIÓN (ÚNICO BLOQUE)
# ---------------------------------------------------------
st.sidebar.title("📦 WMS Marklogistic")
st.sidebar.write(f"👤 Conectado como: **{st.session_state.get('usuario_actual', '')}**")

if st.sidebar.button("Cerrar Sesión", key="btn_cerrar_sesion_unico"):
    st.session_state.autenticado = False
    st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio(
    "Módulos del Sistema", 
    [
        "1. Creación de Materiales", "2. Ingreso de Materiales", "3. Picking de Materiales", 
        "4. Despacho y Guía", "5. Inventario", "6. Dashboard Gerencial", "7. Trazabilidad", 
        "8. Etiquetas", "9. Eliminar Transacciones", "10. Asistente IA", "11. Escáner de SKU", 
        "12. Gestión de Bodegas", "13. Auditoría y Logs", "14. Registro Fotográfico"
    ],
    key="menu_principal_navegacion"
)

st.sidebar.markdown("---")
st.sidebar.subheader("📧 Envío Automático de Reportes")
correo_remitente = st.sidebar.text_input("Correo Remitente (Gmail)", value="marco.inostroza63.mi@gmail.com", key="input_remitente")
pass_remitente = st.sidebar.text_input("Contraseña de Aplicación", type="password", key="input_pass")
correo_destino = st.sidebar.text_input("Correo Destino (Gerencia)", value="marco.inostroza63.mi@gmail.com", key="input_destino")

if st.sidebar.button("Enviar Respaldo por Email", key="btn_respaldo_email"):
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
                if st.button("Procesar e Insertar en Supabase", key="btn_procesar_carga"):
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
# MÓDULO 10: ASISTENTE IA
# ---------------------------------------------------------
elif menu == "10. Asistente IA":
    st.header("🤖 Asistente Inteligente")
    if "GEMINI_API_KEY" in st.secrets:
        try:
            from google import genai
            client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            pregunta = st.text_input("Consulta al ERP (Ej: ¿Qué productos tienen bajo stock?)")
            if st.button("Consultar IA", key="btn_consultar_ia") and pregunta:
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
