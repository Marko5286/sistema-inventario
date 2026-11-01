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
import io

st.set_page_config(page_title="WMS Marklogistic", layout="wide")

# PANTALLA DE LOGIN SI NO ESTÁ AUTENTICADO
if not st.session_state.autenticado:
    
    # Columnas para centrar estéticamente el logo y el título
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Reemplaza "logo.png" por el nombre exacto de tu archivo si es distinto (ej: "logo.jpg")
        try:
            st.image("https://github.com/Marko5286/sistema-inventario/blob/main/logo.jpg.jpg?raw=true", width=220)
        except Exception:
            st.markdown("<h1 style='text-align: center;'>📦</h1>", unsafe_allow_html=True)   
            
        st.markdown("<h2 style='text-align: center;'>WMS MARKLOGISTIC</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Sistema de Gestión de Almacenes</p>", unsafe_allow_html=True)
    
    # Formulario de credenciales
    with st.form("form_login"):
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        btn_login = st.form_submit_button("Iniciar Sesión", use_container_width=True)
        
        if btn_login:
            datos_usuario = verificar_login(user_input, pass_input)
            if datos_usuario:
                st.session_state.autenticado = True
                st.session_state.usuario = user_input
                st.session_state.rol = datos_usuario["rol"]
                st.session_state.nombre_usuario = datos_usuario["nombre_completo"]
                st.success(f"¡Bienvenido, {datos_usuario['nombre_completo']}!")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
                
    st.stop()

from supabase import create_client, Client
try:
    from barcode import Code128
    from barcode.writer import ImageWriter
    HAS_BARCODE = True
except ImportError:
    HAS_BARCODE = False

import streamlit as st
import pandas as pd
# (Tus demás importaciones de Supabase, Plotly, etc.)

# ---------------------------------------------------------
# 1. GESTIÓN DE SESIÓN Y LOGIN
# ---------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.rol = None

# Función para verificar credenciales contra Supabase
def verificar_login(username, password):
    try:
        # Consulta a tu tabla de usuarios en Supabase usando st.connection o supabase-py
        # Ejemplo genérico usando pandas/supabase:
        query = f"SELECT * FROM usuarios WHERE username = '{username}' AND password = '{password}'"
        # Supongamos que ejecutas tu consulta y obtienes un DataFrame `df_user`:
        # df_user = conn.query(query, ttl=0)
        
        # --- SIMULACIÓN DE PRUEBA (Reemplaza esto con tu consulta real a Supabase) ---
        if username == "admin" and password == "admin123":
            return {"nombre_completo": "Administrador General", "rol": "Administrador"}
        elif username == "bodega" and password == "bodega123":
            return {"nombre_completo": "Operario de Bodega", "rol": "Bodeguero"}
        return None
    except Exception as e:
        st.error(f"Error al conectar con la base de datos de usuarios: {e}")
        return None

# PANTALLA DE LOGIN SI NO ESTÁ AUTENTICADO
if not st.session_state.autenticado:
    st.title("📦 WMS MARKLOGISTIC - Acceso al Sistema")
    st.markdown("Por favor, inicia sesión con tus credenciales.")
    
    with st.form("form_login"):
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        btn_login = st.form_submit_button("Iniciar Sesión")
        
        if btn_login:
            datos_usuario = verificar_login(user_input, pass_input)
            if datos_usuario:
                st.session_state.autenticado = True
                st.session_state.usuario = user_input
                st.session_state.rol = datos_usuario["rol"]
                st.session_state.nombre_usuario = datos_usuario["nombre_completo"]
                st.success(f"¡Bienvenido, {datos_usuario['nombre_completo']}!")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
                
    # Detenemos la ejecución aquí para que no muestre los módulos si no hay sesión
    st.stop()

# 🛡️ 2. FUNCIÓN DE GENERACIÓN DE CÓDIGO DE BARRAS
def generar_codigo_barras(sku_texto):
    if not HAS_BARCODE:
        return None
    try:
        rv = io.BytesIO()
        code = Code128(str(sku_texto), writer=ImageWriter())
        code.write(rv, options={"write_text": True, "module_width": 0.3, "module_height": 12.0})
        rv.seek(0)
        return rv
    except Exception:
        return None


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
    st.stop()

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
# MENÚ LATERAL DINÁMICO SEGÚN EL ROL
# ---------------------------------------------------------
st.sidebar.title("📦 WMS MARKLOGISTIC")
st.sidebar.image("https://github.com/Marko5286/sistema-inventario/blob/main/logo.jpg.jpg?raw=true", width=200)
st.sidebar.write(f"👤 **Usuario:** {st.session_state.get('nombre_usuario', 'N/A')}")
st.sidebar.write(f"🔑 **Rol:** {st.session_state.get('rol', 'N/A')}")
st.sidebar.markdown("---")

rol_actual = st.session_state.get("rol", "Bodeguero")

# Lista completa de los 17 módulos para el Administrador
if rol_actual == "Administrador":
    lista_modulos = [
        "1. Creación de Materiales", 
        "2. Ingreso de Materiales", 
        "3. Picking de Materiales", 
        "4. Despacho y Guía", 
        "5. Inventario", 
        "6. Dashboard Gerencial",       
        "7. Trazabilidad",              
        "8. Etiquetas", 
        "9. Eliminar Transacciones", 
        "10. Asistente IA", 
        "11. Escáner de SKU", 
        "12. Gestión de Bodegas",       
        "13. Auditoría y Logs",         
        "14. Registro Fotográfico",
        "15. Emisión de Guías de Despacho",
        "16. Alertas de Stock",
        "17. Quiebre de Stock"
    ]
else:
    # Módulos reducidos para el personal operativo (Bodeguero)
    lista_modulos = [
        "2. Ingreso de Materiales", 
        "3. Picking de Materiales", 
        "4. Despacho y Guía", 
        "5. Inventario", 
        "8. Etiquetas", 
        "11. Escáner de SKU", 
        "14. Registro Fotográfico",
        "15. Emisión de Guías de Despacho",
        "16. Alertas de Stock",
        "17. Quiebre de Stock"
    ]

# Renderizar el menú lateral
menu = st.sidebar.radio("Módulos del Sistema", lista_modulos, key="menu_principal_navegacion")

# Botón de Cerrar Sesión
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.rol = None
    st.rerun()
#---------------------------------------------------------
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
                    st.success("¡Ingreso registrado y guardado en Supabase!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar en Supabase: {e}")

# ---------------------------------------------------------
# MÓDULO 3: PICKING DE MATERIALES
# ---------------------------------------------------------
elif menu == "3. Picking de Materiales":
    st.header("🛒 Órdenes de Picking")
    if st.session_state.materiales.empty:
        st.info("No hay materiales cargados.")
    else:
        sku_pick = st.selectbox("SKU a Preparar", st.session_state.materiales["SKU"], key="pick_sku")
        cant_pick = st.number_input("Cantidad para Picking", min_value=1, value=1, key="pick_cant")
        cliente_dest = st.text_input("Cliente / Destino")
        if st.button("Generar Orden de Picking"):
            mat_row = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_pick].iloc[0]
            if cant_pick > int(mat_row["Stock_Actual"]):
                st.error("Stock insuficiente para realizar el picking.")
            else:
                st.success(f"Orden de Picking generada para {cant_pick} unidades de {sku_pick} con destino a {cliente_dest or 'Cliente General'}.")

# ---------------------------------------------------------
# MÓDULO 4: DESPACHO Y GUÍA
# ---------------------------------------------------------
elif menu == "4. Despacho y Guía":
    st.header("🚚 Despacho y Emisión de Guías")
    if st.session_state.materiales.empty:
        st.info("No hay materiales disponibles para despachar.")
    else:
        with st.form("form_despacho"):
            sku_d = st.selectbox("SKU a Despachar", st.session_state.materiales["SKU"])
            cant_d = st.number_input("Cantidad", min_value=1, value=1)
            cliente_d = st.text_input("Nombre Cliente / Destinatario")
            rut_d = st.text_input("RUT Cliente")
            transporte_d = st.selectbox("Transportista", ["Flota Propia", "Transportes Starken", "Chilexpress", "Externo"])
            patente_d = st.text_input("Patente del Vehículo", value="ABCD-12")
            motivo_d = st.selectbox("Motivo de Traslado", ["Venta", "Traslado entre bodegas", "Devolución", "Préstamo"])
            
            if st.form_submit_button("Despachar y Actualizar Stock"):
                mat_actual = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_d].iloc[0]
                stock_actual = int(mat_actual["Stock_Actual"])
                if cant_d > stock_actual:
                    st.error("No hay suficiente stock para este despacho.")
                else:
                    nuevo_stock = stock_actual - cant_d
                    num_guia_gen = f"G-{len(st.session_state.get('guias_despacho', []))+1:05d}"
                    try:
                        supabase.table("materiales").update({"stock_actual": nuevo_stock}).eq("sku", sku_d).execute()
                        supabase.table("movimientos").insert({
                            "id_mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                            "tipo": "DESPACHO", "sku": sku_d, "cantidad": cant_d,
                            "origen_destino": cliente_d or "Cliente Final",
                            "usuario": st.session_state.get('usuario_actual', 'admin'),
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }).execute()
                        st.session_state.materiales = cargar_materiales_db()
                        st.session_state.movimientos = cargar_movimientos_db()
                        st.success(f"¡Despacho completado! Guía generada: {num_guia_gen}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar el despacho en Supabase: {e}")

# ---------------------------------------------------------
# MÓDULO 5: INVENTARIO
# ---------------------------------------------------------
elif menu == "5. Inventario":
    st.header("📊 Inventario Actual de Bodega")
    st.dataframe(st.session_state.materiales, use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 6: DASHBOARD GERENCIAL
# ---------------------------------------------------------
elif menu == "6. Dashboard Gerencial":
    st.header("📊 Dashboard Gerencial y Métricas")
    st.markdown("Resumen general del rendimiento del inventario de Marklogistic.")
    
    # Verificamos si existe la librería Plotly importada arriba en tu archivo. 
    # Si no la tienes, aseguras tener 'import plotly.express as px' al inicio de tu app.py
    import plotly.express as px
    
    if "materiales" in st.session_state and not st.session_state.materiales.empty:
        df_dash = st.session_state.materiales.copy()
        
        # Asegurar tipos numéricos para los cálculos
        df_dash["Stock_Actual"] = pd.to_numeric(df_dash["Stock_Actual"], errors="coerce").fillna(0)
        if "Valor_Unitario" in df_dash.columns:
            df_dash["Valor_Unitario"] = pd.to_numeric(df_dash["Valor_Unitario"], errors="coerce").fillna(0)
            df_dash["Valor_Total"] = df_dash["Stock_Actual"] * df_dash["Valor_Unitario"]
        else:
            df_dash["Valor_Total"] = 0
            
        # Métricas superiores del Dashboard
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📦 SKUs Totales", len(df_dash))
        with col2:
            st.metric("📊 Stock Total Físico", int(df_dash["Stock_Actual"].sum()))
        with col3:
            total_valor = df_dash["Valor_Total"].sum()
            st.metric("💰 Valorización Inventario", f"${total_valor:,.0f}")
            
        st.divider()
        
        # Gráficos interactivos con Plotly
        c_graf1, c_graf2 = st.columns(2)
        
        with c_graf1:
            st.subheader("Top Productos por Stock")
            if "Nombre" in df_dash.columns and len(df_dash) > 0:
                top_stock = df_dash.nlargest(5, "Stock_Actual")
                fig1 = px.bar(top_stock, x="Nombre", y="Stock_Actual", text="Stock_Actual", color="Stock_Actual")
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("No hay suficientes datos para graficar.")
                
        with c_graf2:
            st.subheader("Distribución de Stock")
            if len(df_dash) > 0:
                fig2 = px.pie(df_dash, names="Nombre" if "Nombre" in df_dash.columns else "SKU", values="Stock_Actual")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No hay datos para el gráfico circular.")
                
    else:
        st.info("⚠️ No hay materiales registrados en el sistema para generar el dashboard.")

# ---------------------------------------------------------
# MÓDULO 7: TRAZABILIDAD
# ---------------------------------------------------------
elif menu == "7. Trazabilidad":
    st.header("🔍 Historial y Trazabilidad de Movimientos")
    st.dataframe(st.session_state.movimientos, use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 8: ETIQUETAS CON CÓDIGO DE BARRAS
# ---------------------------------------------------------
elif menu == "8. Etiquetas":
    st.header("8. Generación de Etiquetas con Código de Barras")
    st.markdown("Selecciona un producto para visualizar su etiqueta oficial y su código de barras listo para impresión.")
    
    if "materiales" in st.session_state and not st.session_state.materiales.empty:
        df_et = st.session_state.materiales.copy()
        
        # Selector de SKU
        sku_et = st.selectbox("Seleccione SKU para generar etiqueta", df_et["SKU"], key="sel_etiqueta_mod8")
        prod_et = df_et[df_et["SKU"] == sku_et].iloc[0]
        
        st.divider()
        
        # Contenedor visual simulando el formato de una etiqueta física
        st.markdown("### 🖨️ Vista Previa de Etiqueta")
        
        col_etiq1, col_etiq2 = st.columns([2, 1])
        
        with col_etiq1:
            st.markdown(f"**Empresa:** WMS Marklogistic")
            st.markdown(f"**Producto:** {prod_et.get('Nombre', 'N/A')}")
            st.markdown(f"**Categoría:** {prod_et.get('Categoria', 'N/A')}")
            st.markdown(f"**Bodega:** {prod_et.get('Bodega', 'N/A')}")
            st.markdown(f"**Stock Actual:** {prod_et.get('Stock_Actual', 0)}")
            
        with col_etiq2:
            st.markdown(f"**SKU:** `{sku_et}`")
            
        st.markdown("---")
        
        # Generar y mostrar el código de barras centrado
        if HAS_BARCODE:
            img_bar = generar_codigo_barras(sku_et)
            if img_bar:
                st.image(img_bar, caption=f"Código de Barras SKU: {sku_et}", width=350)
            else:
                st.error("No se pudo renderizar el código de barras para este SKU.")
        else:
            st.warning("⚠️ La librería `python-barcode` no está disponible en este entorno.")
            
        # Botón opcional de simulación de impresión
        if st.button("🖨️ Enviar a Imprimir Etiqueta", key="btn_imprimir_etiqueta"):
            st.success(f"Etiqueta del producto **{prod_et.get('Nombre')}** enviada a cola de impresión.")
            
    else:
        st.info("⚠️ No hay materiales registrados en el sistema para generar etiquetas.")
# ---------------------------------------------------------
# MÓDULO 9: ELIMINAR TRANSACCIONES
# ---------------------------------------------------------
elif menu == "9. Eliminar Transacciones":
    st.header("🗑️ Gestión y Supresión de Registros")
    st.warning("Zona de administración avanzada.")
    if not st.session_state.materiales.empty:
        sku_del = st.selectbox("Seleccionar SKU a Eliminar de la Base de Datos", st.session_state.materiales["SKU"], key="del_sku")
        if st.button("Eliminar Material"):
            try:
                supabase.table("materiales").delete().eq("sku", sku_del).execute()
                st.session_state.materiales = cargar_materiales_db()
                st.success(f"Material {sku_del} eliminado correctamente de Supabase.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")

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

# ---------------------------------------------------------
# MÓDULO 11: ESCÁNER DE SKU (CÁMARA Y CÓDIGOS)
# ---------------------------------------------------------
elif menu == "11. Escáner de SKU":
    st.header("📷 Escáner de SKU y Códigos")
    
    tab_manual_esc, tab_camara_nativa = st.tabs(["⌨️ Búsqueda Manual / Pistola", "📸 Captura con Cámara del Dispositivo"])
    
    with tab_manual_esc:
        sku_buscar = st.text_input("Ingrese o pistolee el código SKU:").strip().upper()
        if sku_buscar:
            res_busqueda = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_buscar]
            if not res_busqueda.empty:
                st.success("¡Material encontrado!")
                st.dataframe(res_busqueda, use_container_width=True)
            else:
                st.warning("No se encontró ningún material con ese SKU.")

    with tab_camara_nativa:
        st.markdown("Utiliza la cámara para tomar una foto clara del código de barras, etiqueta o código QR del producto:")
        
        # Componente nativo de Streamlit para usar la cámara en la nube de forma segura
        imagen_camara = st.camera_input("Apunta al código y toma la foto", key="camara_sku_nativa")
        
        if imagen_camara is not None:
            st.success("¡Fotografía de la etiqueta capturada con éxito!")
            st.info("💡 **Consejo:** Ingresa el SKU correspondiente a esta etiqueta en el buscador manual de la pestaña anterior para validar o actualizar su stock de inmediato.")

# ---------------------------------------------------------
# MÓDULO 12: GESTIÓN DE BODEGAS
# ---------------------------------------------------------
elif menu == "12. Gestión de Bodegas":
    st.header("🏢 Configuración y Zonas de Bodega")
    st.info("Bodega Activa: Bodega Central Antofagasta")
    st.markdown("- **Zona A:** Recepción y Cross-Docking\n- **Zona B:** Almacenamiento General\n- **Zona C:** Picking y Despachos")

# ---------------------------------------------------------
# MÓDULO 13: AUDITORÍA Y LOGS
# ---------------------------------------------------------
elif menu == "13. Auditoría y Logs":
    st.header("📋 Auditoría de Actividad del Sistema")
    st.dataframe(st.session_state.movimientos, use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 14: REGISTRO FOTOGRÁFICO
# ---------------------------------------------------------
elif menu == "14. Registro Fotográfico":
    st.header("📸 Evidencia y Registro Fotográfico de Carga")
    foto_subida = st.file_uploader("Subir foto de evidencia", type=["png", "jpg", "jpeg"])
    if foto_subida is not None:
        st.image(foto_subida, caption="Evidencia registrada en sistema", use_container_width=True)
        st.success("Fotografía cargada correctamente para el expediente.")


# ---------------------------------------------------------
# MÓDULO 15: EMISIÓN DE GUÍAS DE DESPACHO OFICIALES
# ---------------------------------------------------------
elif menu == "15. Emisión de Guías de Despacho":
    st.header("📄 Generador de Guías de Despacho / Traslado")
    st.markdown("Crea, visualiza y genera el comprobante formal de despacho de mercadería.")
    st.sidebar.image("logo.jpg.jpg", width=150)
    
    if st.session_state.materiales.empty:
        st.info("No hay materiales cargados en el sistema.")
    else:
        with st.form("form_guia_oficial"):
            st.subheader("1. Datos del Cliente / Destinatario")
            c_razon = st.text_input("Razón Social / Nombre del Cliente")
            c_rut = st.text_input("RUT del Cliente", placeholder="Ej: 76.543.210-k")
            c_dir = st.text_input("Dirección de Despacho")
            c_ciudad = st.text_input("Ciudad / Comuna", value="Antofagasta")
            
            st.subheader("2. Detalle del Producto a Despachar")
            sku_guia = st.selectbox("Seleccionar SKU", st.session_state.materiales["SKU"], key="g_sku")
            cant_guia = st.number_input("Cantidad", min_value=1, value=1, key="g_cant")
            
            st.subheader("3. Datos de Traslado y Transporte")
            motivo_traslado = st.selectbox("Motivo del Traslado", [
                "Venta", "Traslado entre bodegas", "Devolución de mercadería", 
                "Préstamo", "Trabajos a realizar", "Otros"
            ])
            chofer = st.text_input("Nombre del Chofer / Transportista")
            patente_camion = st.text_input("Patente del Vehículo")
            
            btn_generar_guia = st.form_submit_button("Generar Documento de Guía")
            
            if btn_generar_guia:
                if not c_razon or not c_rut or not c_dir:
                    st.error("Por favor completa los datos obligatorios del cliente (Razón Social, RUT y Dirección).")
                else:
                    mat_row = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_guia].iloc[0]
                    stock_actual = int(mat_row["Stock_Actual"])
                    
                    if cant_guia > stock_actual:
                        st.error(f"Stock insuficiente. Stock disponible actual para {sku_guia}: {stock_actual}")
                    else:
                        val_unit = float(mat_row["Valor_Unitario"])
                        subtotal = val_unit * cant_guia
                        iva = subtotal * 0.19
                        total = subtotal + iva
                        num_guia_id = f"GD-{len(st.session_state.get('historial_guias', [])) + 1:05d}"
                        
                        st.session_state.ultima_guia = {
                            "numero": num_guia_id,
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "cliente": c_razon,
                            "rut": c_rut,
                            "direccion": c_dir,
                            "ciudad": c_ciudad,
                            "sku": sku_guia,
                            "descripcion": mat_row["Nombre"],
                            "cantidad": cant_guia,
                            "precio_unit": val_unit,
                            "subtotal": subtotal,
                            "iva": iva,
                            "total": total,
                            "motivo": motivo_traslado,
                            "chofer": chofer or "No especificado",
                            "patente": patente_camion or "Sin registro"
                        }
                        
                        nuevo_stock = stock_actual - cant_guia
                        try:
                            supabase.table("materiales").update({"stock_actual": nuevo_stock}).eq("sku", sku_guia).execute()
                            supabase.table("movimientos").insert({
                                "id_mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                                "tipo": "GUIA_DESPACHO", 
                                "sku": sku_guia, 
                                "cantidad": cant_guia,
                                "origen_destino": f"Guía {num_guia_id} - {c_razon}",
                                "usuario": st.session_state.get('usuario_actual', 'admin'),
                                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }).execute()
                            
                            st.session_state.materiales = cargar_materiales_db()
                            st.session_state.movimientos = cargar_movimientos_db()
                            st.success(f"¡Guía de Despacho **{num_guia_id}** generada con éxito y stock descontado!")
                        except Exception as e:
                            st.error(f"Error al sincronizar con Supabase: {e}")

    # Visualización limpia de la Guía Generada
    if "ultima_guia" in st.session_state:
        g = st.session_state.ultima_guia
        st.markdown("---")
        st.subheader("👁️ Vista Previa del Documento Tributario (Guía de Despacho)")
        
        html_guia = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: sans-serif; background-color: #ffffff; color: #000000; margin: 0; padding: 10px; }}
                .guia-container {{ border: 2px solid #2c3e50; padding: 25px; border-radius: 8px; background-color: #ffffff; }}
                .header-flex {{ display: flex; justify-content: space-between; border-bottom: 2px solid #2c3e50; padding-bottom: 15px; }}
                .box-titulo {{ text-align: right; border: 2px solid #e74c3c; padding: 10px; border-radius: 5px; }}
                .info-box {{ margin-top: 15px; font-size: 14px; background: #f8f9fa; padding: 10px; border-radius: 5px; }}
                table {{ width: 100%; margin-top: 20px; border-collapse: collapse; font-size: 14px; }}
                th {{ background-color: #2c3e50; color: white; padding: 8px; text-align: left; }}
                td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                .totales-wrapper {{ display: flex; justify-content: flex-end; margin-top: 20px; }}
                .totales-box {{ width: 250px; font-size: 14px; background: #f8f9fa; padding: 10px; border-radius: 5px; }}
                .fila-total {{ display: flex; justify-content: space-between; margin: 4px 0; }}
                .firmas {{ margin-top: 40px; display: flex; justify-content: space-between; font-size: 12px; text-align: center; }}
                .linea-firma {{ border-top: 1px solid #000; width: 200px; padding-top: 5px; margin: 0 auto; }}

                @media print {{
                    body * {{
                        visibility: hidden;
                    }}
                    .guia-container, .guia-container * {{
                        visibility: visible;
                    }}
                    .guia-container {{
                        position: absolute;
                        left: 0;
                        top: 0;
                        width: 100%;
                        border: none !important;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="guia-container">
                <div class="header-flex">
                    <div>
                        <h2 style="margin: 0; color: #2c3e50;">WMS MARKLOGISTIC</h2>
                        <p style="margin: 2px 0; font-size: 13px;">Bodega Central Antofagasta<br>Operaciones Logísticas</p>
                    </div>
                    <div class="box-titulo">
                        <h3 style="margin: 0; color: #e74c3c;">GUÍA DE DESPACHO</h3>
                        <p style="margin: 2px 0; font-size: 16px; font-weight: bold;">N° {g['numero']}</p>
                        <p style="margin: 2px 0; font-size: 12px;">R.U.T.: 76.123.456-7</p>
                    </div>
                </div>
                
                <div class="info-box">
                    <p style="margin: 4px 0;"><b>Fecha de Emisión:</b> {g['fecha']}</p>
                    <p style="margin: 4px 0;"><b>Señor(es):</b> {g['cliente']} &nbsp;&nbsp;&nbsp;&nbsp; <b>R.U.T.:</b> {g['rut']}</p>
                    <p style="margin: 4px 0;"><b>Dirección:</b> {g['direccion']}, {g['ciudad']}</p>
                    <p style="margin: 4px 0;"><b>Motivo Traslado:</b> {g['motivo']} &nbsp;&nbsp;&nbsp;&nbsp; <b>Transportista:</b> {g['chofer']} (Patente: {g['patente']})</p>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>SKU</th>
                            <th>Descripción</th>
                            <th style="text-align: center;">Cantidad</th>
                            <th style="text-align: right;">Precio Unit.</th>
                            <th style="text-align: right;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>{g['sku']}</td>
                            <td>{g['descripcion']}</td>
                            <td style="text-align: center;">{g['cantidad']}</td>
                            <td style="text-align: right;">${g['precio_unit']:,.2f}</td>
                            <td style="text-align: right;">${g['subtotal']:,.2f}</td>
                        </tr>
                    </tbody>
                </table>
                
                <div class="totales-wrapper">
                    <div class="totales-box">
                        <div class="fila-total"><span>Neto:</span> <span>${g['subtotal']:,.2f}</span></div>
                        <div class="fila-total"><span>I.V.A. (19%):</span> <span>${g['iva']:,.2f}</span></div>
                        <hr style="border: 0; border-top: 1px solid #ccc; margin: 6px 0;">
                        <div class="fila-total" style="font-weight: bold; font-size: 16px;"><span>TOTAL:</span> <span>${g['total']:,.2f}</span></div>
                    </div>
                </div>
                
                <div class="firmas">
                    <div><div class="linea-firma"></div>Nombre y RUT Recinto Receptor</div>
                    <div><div class="linea-firma"></div>Firma y Timbre Conductor</div>
                </div>
            </div>
        </body>
        </html>
        """
        
        import streamlit.components.v1 as components
        components.html(html_guia, height=520, scrolling=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🖨️ Imprimir / Guardar Guía en PDF"):
            st.info("💡 Consejo: Se abrirá la ventana de impresión de tu navegador. Selecciona 'Guardar como PDF' en la opción de impresora.")   
            
  # ---------------------------------------------------------
# MÓDULO 16: ALERTAS DE STOCK
# ---------------------------------------------------------
elif menu == "16. Alertas de Stock":
    st.header("🚨 Panel de Alertas de Stock")
    st.markdown("Monitoreo en tiempo real de productos bajo el stock mínimo.")
    
    if "materiales" in st.session_state and not st.session_state.materiales.empty:
        df_mat = st.session_state.materiales.copy()
        if "Stock_Minimo" not in df_mat.columns:
            df_mat["Stock_Minimo"] = 5  # Valor por defecto si no existe la columna
            
        df_mat["Stock_Actual"] = pd.to_numeric(df_mat["Stock_Actual"], errors="coerce").fillna(0)
        df_mat["Stock_Minimo"] = pd.to_numeric(df_mat["Stock_Minimo"], errors="coerce").fillna(5)
        
        criticos = df_mat[df_mat["Stock_Actual"] <= df_mat["Stock_Minimo"]]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Catálogo", len(df_mat))
        with col2:
            st.metric("Productos en Riesgo", len(criticos))
            
        st.divider()
        
        if len(criticos) > 0:
            st.warning(f"Hay {len(criticos)} productos que necesitan atención.")
            st.dataframe(criticos[["SKU", "Nombre", "Stock_Actual", "Stock_Minimo"]], use_container_width=True, hide_index=True)
        else:
            st.success("¡Todo en orden! No hay alertas de stock.")
    else:
        st.info("No hay materiales registrados.")

# ---------------------------------------------------------
# MÓDULO 17: QUIEBRE DE STOCK
# ---------------------------------------------------------
elif menu == "17. Quiebre de Stock":
    st.header("📉 Análisis de Quiebre de Stock")
    st.markdown("Gestión y sugerencias de reposición para inventario crítico.")
    
    if "materiales" in st.session_state and not st.session_state.materiales.empty:
        df_mat = st.session_state.materiales.copy()
        if "Stock_Minimo" not in df_mat.columns:
            df_mat["Stock_Minimo"] = 5
            
        df_mat["Stock_Actual"] = pd.to_numeric(df_mat["Stock_Actual"], errors="coerce").fillna(0)
        df_mat["Stock_Minimo"] = pd.to_numeric(df_mat["Stock_Minimo"], errors="coerce").fillna(5)
        
        criticos = df_mat[df_mat["Stock_Actual"] <= df_mat["Stock_Minimo"]]
        
        if len(criticos) > 0:
            st.error(f"¡Atención! {len(criticos)} productos se encuentran en quiebre o nivel crítico.")
            st.dataframe(criticos[["SKU", "Nombre", "Stock_Actual", "Stock_Minimo"]], use_container_width=True, hide_index=True)
            
            st.subheader("🛒 Sugerencia de Compra")
            sku_sel = st.selectbox("Seleccionar SKU para calcular reposición", criticos["SKU"], key="sel_quiebre_17")
            prod = criticos[criticos["SKU"] == sku_sel].iloc[0]
            
            sugerido = (int(prod["Stock_Minimo"]) * 3) - int(prod["Stock_Actual"])
            st.info(f"Se recomienda reabastecer **{sugerido} unidades** del producto **{prod['Nombre']}**.")
        else:
            st.success("🎉 No hay quiebres de stock en este momento.")
    else:
        st.info("No hay materiales registrados.")          
            
                                
