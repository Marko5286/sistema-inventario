import os
import io
import sqlalchemy
import pandas as pd
import streamlit as st
from streamlit_drawable_canvas import st_canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# =========================================================
# 1. CONFIGURACIÓN INICIAL DE LA PÁGINA
# =========================================================
st.set_page_config(page_title="WMS MARKLOGISTIC", layout="wide")

# =========================================================
# 2. AUTENTICACIÓN Y SEGURIDAD (GEMINI API KEY)
# =========================================================
api_key = None
try:
    api_key = st.secrets.get("GEMINI_API_KEY") or st.secrets["general"].get("GEMINI_API_KEY")
except Exception:
    pass

if not api_key:
    api_key = os.getenv("GEMINI_API_KEY", "")

if not api_key:
    st.error("Configura tu GEMINI_API_KEY en los secretos.")
    st.stop()

# =========================================================
# 3. CONEXIÓN A BASE DE DATOS (SUPABASE / LOCAL)
# =========================================================
try:
    db_url = st.secrets["postgres"]["url"]
    engine = sqlalchemy.create_engine(db_url)
except Exception:
    engine = sqlalchemy.create_engine("sqlite:///wms_local.db")

# =========================================================
# 4. MENÚ DE NAVEGACIÓN PRINCIPAL
# =========================================================
st.sidebar.title("WMS MARKLOGISTIC")
menu_opcion = st.sidebar.selectbox(
    "Seleccione un Módulo", 
    [
        "Módulo 1: Control de Inventario",
        "Módulo 2: Recepciones (Entradas)",
        "Módulo 3: Proveedores y Clientes",
        "Módulo 4: Salidas y Despachos",
        "Módulo 5: Historial y Movimientos",
        "Módulo 6: Reportes y Analítica"
    ]
)

# =========================================================
# MÓDULO 1: CONTROL DE INVENTARIO
# =========================================================
if menu_opcion == "Módulo 1: Control de Inventario":
    st.header("📦 Módulo 1: Control de Inventario")
    st.write("Visualización y gestión de stock en tiempo real.")
    # Agrega aquí la lógica de tu inventario

# =========================================================
# MÓDULO 2: RECEPCIONES (ENTRADAS)
# =========================================================
elif menu_opcion == "Módulo 2: Recepciones (Entradas)":
    st.header("📥 Módulo 2: Ingreso de Mercancía")
    st.write("Formulario de recepción de insumos y materiales.")
    # Agrega aquí tu formulario de entradas

# =========================================================
# MÓDULO 3: PROVEEDORES Y CLIENTES
# =========================================================
elif menu_opcion == "Módulo 3: Proveedores y Clientes":
    st.header("👥 Módulo 3: Gestión de Terceros")
    st.write("Directorio de proveedores y clientes registrados.")
    # Agrega aquí tu gestión de proveedores/clientes

# =========================================================
# MÓDULO 4: SALIDAS Y DESPACHOS (CON FIRMA Y PDF)
# =========================================================
elif menu_opcion == "Módulo 4: Salidas y Despachos":
    st.header("📤 Módulo 4: Salidas y Despachos de Material")
    st.write("Complete la información de salida, registre la firma digital y genere la Guía de Despacho oficial.")

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
    
    # Canvas con validación segura de RuntimeError
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

    has_drawing = False
    signature_image_path = None
    if canvas_result is not None:
        try:
            if canvas_result.image_data is not None and (canvas_result.image_data[:, :, 3] > 0).any():
                has_drawing = True
                import numpy as np
                from PIL import Image
                img_data = canvas_result.image_data.astype(np.uint8)
                img = Image.fromarray(img_data)
                signature_image_path = "temp_firma.png"
                img.save(signature_image_path)
        except (RuntimeError, AttributeError, IndexError):
            has_drawing = False

    st.markdown("---")

    if st.button("💾 Guardar y Generar Guía de Despacho (PDF)", type="primary"):
        if not cliente_destino or not numero_guia or not material_desc:
            st.warning("⚠️ Por favor, complete los campos obligatorios: Cliente, N° de Guía y Materiales.")
        elif not has_drawing:
            st.warning("⚠️ El recuadro de firma no puede estar vacío. Se requiere la firma del receptor.")
        else:
            st.success(f"¡Despacho N° {numero_guia} procesado exitosamente!")

            # Generación de la Guía de Despacho en PDF
            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            elements = []
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                'TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#1A365D"), alignment=1, spaceAfter=15
            )
            normal_style = styles['Normal']

            elements.append(Paragraph("<b>MARKLOGISTIC - GUÍA DE DESPACHO</b>", title_style))
            elements.append(Paragraph(f"<b>N° de Guía:</b> {numero_guia}", normal_style))
            elements.append(Spacer(1, 10))

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

            elements.append(Paragraph("<b>Detalle de Materiales Entregados:</b>", styles['Heading3']))
            elements.append(Spacer(1, 5))
            elements.append(Paragraph(material_desc.replace('\n', '<br/>'), normal_style))
            elements.append(Spacer(1, 40))

            from reportlab.platypus import Image as RLImage
            signature_elements = [Paragraph("<b>Firma de Recepción Conforme:</b>", normal_style)]
            if signature_image_path:
                signature_elements.append(Spacer(1, 10))
                signature_elements.append(RLImage(signature_image_path, width=150, height=60))
            
            signature_elements.append(Spacer(1, 10))
            signature_elements.append(Paragraph("________________________________________", normal_style))
            signature_elements.append(Paragraph("Nombre y Rut del Receptor", normal_style))

            elements.append(Table([[signature_elements]], colWidths=[540]))

            doc.build(elements)
            pdf_buffer.seek(0)

            st.download_button(
                label="📥 Descargar Guía de Despacho en PDF",
                data=pdf_buffer,
                file_name=f"Guia_Despacho_{numero_guia}.pdf",
                mime="application/pdf",
                type="secondary"
            )

# =========================================================
# MÓDULO 5: HISTORIAL Y MOVIMIENTOS
# =========================================================
elif menu_opcion == "Módulo 5: Historial y Movimientos":
    st.header("📜 Módulo 5: Historial de Operaciones")
    st.write("Kárdex e inspección de entradas y salidas registradas.")
    # Agrega aquí tu historial

# =========================================================
# MÓDULO 6: REPORTES Y ANALÍTICA
# =========================================================
elif menu_opcion == "Módulo 6: Reportes y Analítica":
    st.header("📊 Módulo 6: Métricas y Reportes")
    st.write("Resumen consolidado y exportación de informes.")
    # Agrega aquí tus reportes

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
