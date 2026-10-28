import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import smtplib
from email.message import EmailMessage
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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
            st.session_state.materiales = pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual","Ubicaciones"])
    else:
        st.session_state.materiales = pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual","Ubicaciones"])

if "Ubicacion" not in st.session_state.materiales.columns:
    st.session_state.materiales["Ubicacion"] = "A-00-0"
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
def enviar_correo_respaldo(remitente, password_app, destinatario, archivo_excel_bytes):
    msg = marco.inostroza63.mi@gmail.com()
    msg['Subject'] = f"📊 Respaldo Automático WMS Marklogistic - {datetime.now().strftime('%Y-%m-%d')}"
    msg['From'] = remitente
    msg['To'] = destinatario
    msg.set_content("Adjunto encontrarás el reporte y respaldo automático con los movimientos y stock actual de la bodega.")
    
    msg.add_attachment(
        archivo_excel_bytes,
        maintype='application',
        subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        filename=f"respaldo_erp_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    )
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remitente, password_app)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"Error al enviar correo: {e}")
        return False

    
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
        "9. Asistente IA"
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
elif menu == "1. Creación de Materiales":
    st.header("📋 Registro y Carga Masiva de Materiales / Maestro de SKU")
    
    # 📌 Asegúrate de usar pestañas (tabs) o quita el 'with tab_masivo:' si no lo tienes definido arriba.
    # Si tienes definidas pestañas arriba (ej: tab_manual, tab_masivo = st.tabs(...)), 
    # todo el contenido de la pestaña debe llevar sangría (4 espacios):
    
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
                            if not sku_val or pd.isna(row["SKU"]):
                                continue
                            
                            if sku_val in st.session_state.materiales["SKU"].values:
                                idx_existente = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_val].tolist()[0]
                                st.session_state.materiales.loc[idx_existente, "Stock_Actual"] += int(row["Stock_Actual"])
                            else:
                                nuevo_row = pd.DataFrame([{
                                    "SKU": sku_val,
                                    "Nombre": str(row["Nombre"]),
                                    "Unidad": str(row["Unidad"]),
                                    "Valor_Unitario": float(row["Valor_Unitario"]),
                                    "Stock_Actual": int(row["Stock_Actual"]),
                                    "Ubicacion": "A-00-0"
                                }])
                                st.session_state.materiales = pd.concat([st.session_state.materiales, nuevo_row], ignore_index=True)
                                importados += 1
                                
                        guardar_datos()
                        st.success(f"¡Se importaron {importados} materiales!")
                        st.rerun()
                else:
                    st.error("El archivo no contiene las columnas requeridas.")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")

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
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
                guardar_datos()
                st.success(f"Ingresadas {cant_ingreso} unidades del SKU {sku_ingreso}.")


# ---------------------------------------------------------
# MÓDULO 3: PICKING DE MATERIALES
# ---------------------------------------------------------
# En el Módulo 3: Picking de Materiales
if not st.session_state.materiales.empty:
    with st.form("form_picking"):
        cliente = st.text_input("Cliente / Destino")
        sku_pick = st.selectbox("Material a Extraer", st.session_state.materiales["SKU"])
        
        # Obtener y mostrar la ubicación del SKU seleccionado
        mat_sel = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_pick].iloc[0]
        st.info(f"📍 **Ubicación en Bodega:** {mat_sel.get('Ubicacion', 'Sin asignar')} | **Stock Disponible:** {mat_sel['Stock_Actual']}")
        
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
                <p style="margin: 5px 0; font-size: 14px;"><b>Ubicación:</b> <span style="font-size: 16px; font-weight: bold;">{mat_info.get('Ubicacion', 'N/A')}</span></p>
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
