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

def enviar_correo_respaldo(remitente, password_app, destinatario, archivo_excel_bytes):
    msg = EmailMessage()
    msg['Subject'] = f"📊 Respaldo Automático WMS Marklogistic - {datetime.now().strftime('%Y-%m-%d')}"
    msg['From'] = remitente
    msg['To'] = destinatario
    msg.set_content("Adjunto encontrarás el reporte y respaldo automático con los movimientos y stock actual de la bodega.")
    msg.add_attachment(archivo_excel_bytes, maintype='application', subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=f"respaldo_erp_{datetime.now().strftime('%Y-%m-%d')}.xlsx")
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remitente, password_app)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"Error al enviar correo: {e}")
        return False

# ---------------------------------------------------------
# 2. PANEL LATERAL / NAVEGACIÓN Y PERMISOS
# ---------------------------------------------------------
st.sidebar.title("📦 WMS Marklogistic")
usuario_actual = st.session_state.get('usuario_actual', 'bodega')
st.sidebar.write(f"👤 Conectado como: **{usuario_actual}**")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

st.sidebar.markdown("---")
modulos_permitidos = PERMISOS_USUARIOS.get(usuario_actual, ["5. Inventario"])
menu = st.sidebar.radio("Módulos del Sistema", modulos_permitidos)

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
                    nuevo = pd.DataFrame([{
                        "SKU": sku_m,
                        "Nombre": nom_m,
                        "Unidad": uni_m,
                        "Valor_Unitario": val_m,
                        "Stock_Actual": stk_m,
                        "Ubicacion": ubi_m,
                        "Bodega": "Bodega Central Antofagasta"
                    }])
                    st.session_state.materiales = pd.concat([st.session_state.materiales, nuevo], ignore_index=True)
                    guardar_datos()
                    st.success(f"Material {sku_m} creado correctamente.")
                    st.rerun()

    with tab_masivo:
        st.subheader("Subir Planilla Excel de Materiales")
        st.info("💡 **Formato requerido del Excel:** La primera fila debe contener exactamente:\n\n `SKU`, `Nombre`, `Unidad`, `Valor_Unitario`, `Stock_Actual`, `Ubicacion`, `Bodega`")
        
        archivo_excel = st.file_uploader("Selecciona el archivo Excel (.xlsx)", type=["xlsx", "xls"])
        
        if archivo_excel is not None:
            try:
                df_cargado = pd.read_excel(archivo_excel)
                columnas_requeridas = ["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual", "Ubicacion", "Bodega"]
                
                if not all(col in df_cargado.columns for col in ["SKU", "Nombre"]):
                    st.error("⚠️ El archivo subido debe contener al menos las columnas 'SKU' y 'Nombre'.")
                else:
                    if "Unidad" not in df_cargado.columns: df_cargado["Unidad"] = "Unidades"
                    if "Valor_Unitario" not in df_cargado.columns: df_cargado["Valor_Unitario"] = 0
                    if "Stock_Actual" not in df_cargado.columns: df_cargado["Stock_Actual"] = 0
                    if "Ubicacion" not in df_cargado.columns: df_cargado["Ubicacion"] = "A-00-0"
                    if "Bodega" not in df_cargado.columns: df_cargado["Bodega"] = "Bodega Central Antofagasta"
                    
                    df_cargado["SKU"] = df_cargado["SKU"].astype(str).str.strip().str.upper()
                    st.write("🔍 **Vista previa de los datos a cargar:**")
                    st.dataframe(df_cargado[columnas_requeridas].head(10))
                    
                    if st.button("🚀 Confirmar e Importar Datos"):
                        skus_existentes = set(st.session_state.materiales["SKU"].tolist())
                        df_nuevos = df_cargado[~df_cargado["SKU"].isin(skus_existentes)][columnas_requeridas]
                        cant_duplicados = len(df_cargado) - len(df_nuevos)
                        
                        if df_nuevos.empty:
                            st.warning("⚠️ Todos los SKU del archivo ya existen en la base de datos.")
                        else:
                            st.session_state.materiales = pd.concat([st.session_state.materiales, df_nuevos], ignore_index=True)
                            guardar_datos()
                            st.success(f"¡Carga completada! Se importaron **{len(df_nuevos)}** nuevos materiales.")
                            if cant_duplicados > 0:
                                st.warning(f"Se omitieron **{cant_duplicados}** registros porque sus SKUs ya existían.")
                            st.rerun()
            except Exception as e:
                st.error(f"Error al procesar el archivo Excel: {e}")

    st.markdown("---")
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
                    "Tipo": "INGRESO",
                    "SKU": sku_ingreso,
                    "Cantidad": cant_ingreso,
                    "Origen/Destino": proveedor_origen or "Recepción General",
                    "Usuario": usuario_actual,
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
                guardar_datos()
                st.success(f"Ingresadas {cant_ingreso} unidades del SKU {sku_ingreso}.")
                st.rerun()

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
# MÓDULO 4: DESPACHO Y GUÍA
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

        st.markdown("---")
        st.subheader("✍️ Firma Digital del Receptor / Transportista")
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

        if st.button("Confirmar Despacho y Generar Guía"):
            if canvas_result.image_data is None or not (canvas_result.image_data[:, :, 3] > 0).any():
                st.warning("⚠️ Debes registrar la firma en el recuadro antes de confirmar el despacho.")
            else:
                idx = st.session_state.materiales.index[st.session_state.materiales["SKU"] == datos_orden["SKU"]].tolist()[0]
                st.session_state.materiales.loc[idx, "Stock_Actual"] -= datos_orden["Cantidad"]
                datos_orden["Estado"] = "Despachado"

                mov = pd.DataFrame([{
                    "ID_Mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                    "Tipo": "DESPACHO",
                    "SKU": datos_orden["SKU"],
                    "Cantidad": datos_orden["Cantidad"],
                    "Origen/Destino": datos_orden["Cliente"],
                    "Usuario": usuario_actual,
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)

                num_guia = f"GD-{len(st.session_state.guias_despacho)+1:04d}"
                guia_data = {
                    "Numero_Guia": num_guia,
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Cliente": datos_orden["Cliente"],
                    "Rut": rut_cliente,
                    "SKU": datos_orden["SKU"],
                    "Cantidad": datos_orden["Cantidad"],
                    "Transporte": transporte,
                    "Conductor": nombre_conductor,
                    "Rut_Conductor": rut_conductor,
                    "Patente": patente,
                    "Motivo": motivo,
                    "Firma_Img": canvas_result.image_data
                }
                
                st.session_state.guias_despacho.append(guia_data)
                guardar_datos()
                st.success(f"¡Despacho realizado con éxito! Guía N° **{num_guia}**")
                st.session_state.ultima_guia = guia_data
                st.rerun()

    if "ultima_guia" in st.session_state:
        st.markdown("---")
        st.subheader("📥 Descargar Guía de Traslado")
        pdf_buffer = generar_pdf_guia(st.session_state.ultima_guia)
        st.download_button(
            label="📄 Descargar Guía de Despacho en PDF",
            data=pdf_buffer,
            file_name=f"Guia_{st.session_state.ultima_guia['Numero_Guia']}.pdf",
            mime="application/pdf"
        )

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
        st.subheader("Vista Previa de Etiqueta")
        for i in range(cantidad_copias):
            html_etiqueta = f"""
            <div style="border: 2px dashed #000; width: 320px; padding: 15px; font-family: Arial; background: white; color: black; margin-bottom: 20px; border-radius: 8px;">
                <h4 style="text-align: center; margin: 0 0 10px 0;">WMS MARKLOGISTIC</h4>
                <p style="margin: 5px 0;"><b>SKU:</b> {mat_info['SKU']}</p>
                <p style="margin: 5px 0;"><b>Descripción:</b> {mat_info['Nombre']}</p>
                <p style="margin: 5px 0;"><b>Ubicación:</b> {mat_info.get('Ubicacion', 'N/A')}</p>
                <p style="margin: 5px 0;"><b>Bodega:</b> {mat_info.get('Bodega', 'N/A')}</p>
            </div>
            """
            st.markdown(html_etiqueta, unsafe_allow_html=True)

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
                    model='gemini-1.5-pro',
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
                else:
                    st.warning("⚠️ No se pudo leer ningún código QR en la imagen capturada.")
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
# MÓDULO 12: GESTIÓN DE BODEGAS
# ---------------------------------------------------------
elif menu == "12. Gestión de Bodegas":
    st.header("🏢 Gestión de Múltiples Bodegas y Transferencias")
    bodegas_disponibles = ["Bodega Central Antofagasta", "Bodega Norte", "Bodega Tránsito", "Centro de Acopio Sur"]
    
    with st.form("form_mat_bodega"):
        sku_asig = st.selectbox("Seleccionar SKU", st.session_state.materiales["SKU"])
        bodega_sel = st.selectbox("Seleccionar Bodega", bodegas_disponibles)
        if st.form_submit_button("Actualizar Bodega"):
            idx = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_asig].tolist()[0]
            st.session_state.materiales.loc[idx, "Bodega"] = bodega_sel
            guardar_datos()
            st.success(f"SKU `{sku_asig}` asignado a **{bodega_sel}**.")
            st.rerun()

# ---------------------------------------------------------
# MÓDULO 13: AUDITORÍA Y LOGS
# ---------------------------------------------------------
elif menu == "13. Auditoría y Logs":
    st.header("📋 Auditoría y Registro de Actividad por Usuario")
    if st.session_state.movimientos.empty:
        st.info("No hay registros de actividad.")
    else:
        st.dataframe(st.session_state.movimientos.sort_values(by="Fecha", ascending=False), use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 14: REGISTRO FOTOGRÁFICO
# ---------------------------------------------------------
elif menu == "14. Registro Fotográfico":
    st.header("📸 Registro Fotográfico")
    if "registro_fotos" not in st.session_state:
        st.session_state.registro_fotos = []
    
    with st.form("form_foto"):
        obs = st.text_area("Observación")
        foto = st.file_uploader("Adjuntar imagen", type=["png", "jpg"])
        if st.form_submit_button("Guardar"):
            if foto:
                st.session_state.registro_fotos.append({"Observacion": obs, "Imagen": foto})
                st.success("Guardado con éxito.")
                st.rerun()

# ---------------------------------------------------------
# MÓDULO 15: GESTIÓN DE PERMISOS (SOLO ADMIN)
# ---------------------------------------------------------
elif menu == "15. Gestión de Permisos":
    if usuario_actual != 'admin':
        st.error("⚠️ Acceso restringido exclusivamente para el Administrador.")
    else:
        st.header("🛡️ Control de Accesos y Permisos por Rol")
        st.info("A continuación se detallan los módulos habilitados para cada perfil de usuario en el WMS:")
        
        for rol, mods in PERMISOS_USUARIOS.items():
            with st.expander(f"Perfil: {rol.upper()} ({len(mods)} módulos habilitados)"):
                for m in mods:
                    st.write(f"- {m}")
