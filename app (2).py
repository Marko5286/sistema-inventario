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
import sqlalchemy
import io
import streamlit as st
from streamlit_drawable_canvas import st_canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


st.set_page_config(page_title="WMS Marklogistic", layout="wide")

# =========================================================
# 1. VERIFICACIÓN DE CLAVES SECRETAS 
# =========================================================
api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
if not api_key:
    st.error("Configura tu GEMINI_API_KEY en los secretos.")
    st.stop()

# Conexión a Supabase
try:
    db_url = st.secrets["postgres"]["url"]
    engine = sqlalchemy.create_engine(db_url)
except Exception:
    engine = sqlalchemy.create_engine("sqlite:///wms_local.db")

def cargar_tabla_desde_nube(tabla, columnas_default):
    try:
        df = pd.read_sql(f"SELECT * FROM {tabla}", con=engine)
        return df
    except Exception:
        return pd.DataFrame(columns=columnas_default)

# Cargar datos iniciales desde la Base de Datos
st.session_state.materiales = cargar_tabla_desde_nube("materiales", ["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual", "Ubicacion", "Bodega"])
st.session_state.movimientos = cargar_tabla_desde_nube("movimientos", ["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen/Destino", "Fecha", "Usuario"])
st.session_state.ordenes_picking = cargar_tabla_desde_nube("ordenes_picking", ["ID_Picking", "Cliente", "SKU", "Ubicacion", "Cantidad", "Estado"]).to_dict('records')
st.session_state.guias_despacho = cargar_tabla_desde_nube("guias_despacho", ["Numero_Guia", "Fecha", "Cliente", "Rut", "SKU", "Cantidad", "Transporte", "Conductor", "Rut_Conductor", "Patente", "Motivo"]).to_dict('records')

# Validaciones de columnas básicas por seguridad
if "Bodega" not in st.session_state.materiales.columns:
    st.session_state.materiales["Bodega"] = "Bodega Central Antofagasta"
if "Ubicacion" not in st.session_state.materiales.columns:
    st.session_state.materiales["Ubicacion"] = "A-00-0"
if "Usuario" not in st.session_state.movimientos.columns:
    st.session_state.movimientos["Usuario"] = "admin"

def guardar_datos():
    """Guarda automáticamente todos los DataFrames en la base de datos PostgreSQL de Supabase"""
    try:
        st.session_state.materiales.to_sql("materiales", con=engine, if_exists="replace", index=False)
        st.session_state.movimientos.to_sql("movimientos", con=engine, if_exists="replace", index=False)
        pd.DataFrame(st.session_state.ordenes_picking).to_sql("ordenes_picking", con=engine, if_exists="replace", index=False)
        pd.DataFrame(st.session_state.guias_despacho).to_sql("guias_despacho", con=engine, if_exists="replace", index=False)
    except Exception as e:
        st.error(f"Error al sincronizar con la base de datos en la nube: {e}")

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
                    "Usuario": st.session_state.get('usuario_actual', 'admin'),
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
            


# =========================================================
# MÓDULO DE SALIDAS, DESPACHOS Y GUÍA IMPRESA
# =========================================================
st.header("📤 Salidas y Despachos de Material")
st.write("Complete la información de salida, registre la firma digital y genere la Guía de Despacho oficial.")

# 1. Formulario de Datos del Despacho
col1, col2 = st.columns(2)
with col1:
    cliente_destino = st.text_input("Cliente / Destino final", placeholder="Ej: Constructora del Norte")
    numero_guia = st.text_input("N° de Guía de Despacho", placeholder="GD-2026-001")
    material_desc = st.text_area("Detalle de los Materiales / Productos", placeholder="Ej: 50x Cajas de pernos, 10x Tubos PVC")
with col2:
    encargado = st.text_input("Responsable del despacho", placeholder="Tu Nombre")
    vehiculo_patente = st.text_input("Patente del vehículo / Transportista", placeholder="ABCD-12")

st.markdown("---")
st.subheader("✍️ Firma Digital del Receptor")
st.info("Por favor, solicite al receptor que firme en el recuadro inferior.")

# 2. Componente de Firma (Canvas con validación segura de RuntimeError)
canvas_result = st_canvas(
    fill_color="rgba(255, 165, 0, 0.3)",
    stroke_width=2,
    stroke_color="#000000",
    background_color="#FFFFFF",
    height=160,
    width=450,
    drawing_mode="freedraw",
    key="canvas_firma_despacho_pdf",
)

# Verificación de que el usuario haya dibujado algo de manera segura
has_drawing = False
signature_image_path = None
if canvas_result is not None:
    try:
        if canvas_result.image_data is not None and (canvas_result.image_data[:, :, 3] > 0).any():
            has_drawing = True
            # Guardamos temporalmente la imagen de la firma para el PDF
            import numpy as np
            from PIL import Image
            img_data = canvas_result.image_data.astype(np.uint8)
            img = Image.fromarray(img_data)
            signature_image_path = "temp_firma.png"
            img.save(signature_image_path)
    except (RuntimeError, AttributeError, IndexError):
        has_drawing = False

st.markdown("---")

# 3. Acciones de Validación y Generación de PDF
if st.button("💾 Guardar y Generar Guía de Despacho (PDF)", type="primary"):
    if not cliente_destino or not numero_guia or not material_desc:
        st.warning("⚠️ Por favor, complete los campos obligatorios: Cliente, N° de Guía y Materiales.")
    elif not has_drawing:
        st.warning("⚠️ El recuadro de firma no puede estar vacío. Se requiere la firma del receptor.")
    else:
        st.success(f"¡Despacho N° {numero_guia} procesado exitosamente!")

        # 4. Generación automática del archivo PDF (Guía de Despacho)
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        # Estilos personalizados
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor("#1A365D"),
            alignment=1, # Centrado
            spaceAfter=15
        )
        
        normal_style = styles['Normal']

        # Contenido del PDF
        elements.append(Paragraph("<b>MARKLOGISTIC - GUÍA DE DESPACHO</b>", title_style))
        elements.append(Paragraph(f"<b>N° de Guía:</b> {numero_guia}", normal_style))
        elements.append(Spacer(1, 10))

        # Tabla de datos generales
        data_tabla = [
            [Paragraph(f"<b>Cliente / Destino:</b> {cliente_destino}", normal_style), 
             Paragraph(f"<b>Responsable:</b> {encargado}", normal_style)],
            [Paragraph(f"<b>Transporte / Patente:</b> {vehiculo_patente}", normal_style), 
             Paragraph(f"<b>Fecha:</b> 2026-10-31", normal_style)]
        ]
        t = Table(data_tabla, colWidths=[270, 270])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E0")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('PADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 15))

        # Detalle de materiales
        elements.append(Paragraph("<b>Detalle de Materiales Entregados:</b>", styles['Heading3']))
        elements.append(Spacer(1, 5))
        elements.append(Paragraph(material_desc.replace('\n', '<br/>'), normal_style))
        elements.append(Spacer(1, 40))

        # Sección de Firma en el PDF
        from reportlab.platypus import Image as RLImage
        signature_elements = [Paragraph("<b>Firma de Recepción Conforme:</b>", normal_style)]
        if signature_image_path:
            # Insertar la firma dibujada en el PDF
            signature_elements.append(Spacer(1, 10))
            signature_elements.append(RLImage(signature_image_path, width=150, height=60))
        
        signature_elements.append(Spacer(1, 10))
        signature_elements.append(Paragraph("________________________________________", normal_style))
        signature_elements.append(Paragraph("Nombre y Rut del Receptor", normal_style))

        elements.append(Table([[signature_elements]], colWidths=[540]))

        # Construir el PDF
        doc.build(elements)
        pdf_buffer.seek(0)

        # 5. Botón de descarga directa en Streamlit
        st.download_button(
            label="📥 Descargar Guía de Despacho en PDF",
            data=pdf_buffer,
            file_name=f"Guia_Despacho_{numero_guia}.pdf",
            mime="application/pdf",
            type="secondary"
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
        
        # 1. GENERAR EL HTML DE LAS ETIQUETAS
        html_etiquetas = ""
        for i in range(cantidad_copias):
            html_etiquetas += f"""
            <div style="
                border: 2px dashed #000;
                width: 320px;
                padding: 15px;
                font-family: Arial, sans-serif;
                background: white;
                color: black;
                margin: 0 auto 20px auto;
                border-radius: 8px;
            ">
                <h4 style="text-align: center; margin: 0 0 10px 0; font-size: 16px; color: black;">WMS MARKLOGISTIC</h4>
                <hr style="border: 1px solid #000; margin: 5px 0;">
                <p style="margin: 5px 0; font-size: 14px; color: black;"><b>SKU:</b> {mat_info['SKU']}</p>
                <p style="margin: 5px 0; font-size: 14px; color: black;"><b>Descripción:</b> {mat_info['Nombre']}</p>
                <p style="margin: 5px 0; font-size: 14px; color: black;"><b>Ubicación:</b> <span style="font-size: 16px; font-weight: bold;">{mat_info.get('Ubicacion', 'N/A')}</span></p>
                <p style="margin: 5px 0; font-size: 14px; color: black;"><b>Bodega:</b> {mat_info.get('Bodega', 'N/A')}</p>
                <p style="margin: 5px 0; font-size: 14px; color: black;"><b>Unidad:</b> {mat_info['Unidad']}</p>
                <p style="margin: 5px 0; font-size: 14px; color: black;"><b>Valor Unit.:</b> ${mat_info['Valor_Unitario']:,.0f}</p>
                <div style="text-align: center; margin-top: 10px; font-size: 12px; font-family: monospace; color: black;">
                    ||||| | |||| ||| || ||||
                </div>
            </div>
            """

        # 2. RENDERIZAR VISTA PREVIA NORMAL EN LA APP
        st.markdown(html_etiquetas, unsafe_allow_html=True)

        # 3. BOTÓN CON COMPONENTE HTML AISLADO (ABRE VENTANA AISLADA DE IMPRESIÓN)
        import streamlit.components.v1 as components
        
        script_impresion = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script>
                function imprimirEtiquetas() {{
                    var ventana = window.open('', '_blank', 'width=450,height=600');
                    ventana.document.write('<html><head><title>Imprimir Etiquetas</title></head><body style="margin:20px;">');
                    ventana.document.write(`{html_etiquetas}`);
                    ventana.document.write('</body></html>');
                    ventana.document.close();
                    ventana.focus();
                    setTimeout(function() {{
                        ventana.print();
                        ventana.close();
                    }}, 250);
                }}
            </script>
        </head>
        <body style="margin:0; padding:0; background:transparent;">
            <button onclick="imprimirEtiquetas()" style="
                background-color: #ff4b4b;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                font-family: Arial, sans-serif;
            ">
                🖨️ Imprimir Etiquetas Ahora
            </button>
        </body>
        </html>
        """
        
        components.html(script_impresion, height=60)

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
