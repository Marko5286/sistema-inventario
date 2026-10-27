import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO

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
        st.session_state.materiales = pd.read_excel(EXCEL_MATERIALES)
    else:
        st.session_state.materiales = pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual"])

if "movimientos" not in st.session_state:
    if os.path.exists(EXCEL_MOVIMIENTOS):
        st.session_state.movimientos = pd.read_excel(EXCEL_MOVIMIENTOS)
    else:
        st.session_state.movimientos = pd.DataFrame(columns=["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen/Destino", "Fecha"])

if "ordenes_picking" not in st.session_state:
    if os.path.exists(EXCEL_PICKING):
        df_pick = pd.read_excel(EXCEL_PICKING)
        st.session_state.ordenes_picking = df_pick.to_dict('records')
    else:
        st.session_state.ordenes_picking = []

if "guias_despacho" not in st.session_state:
    if os.path.exists(EXCEL_GUIAS):
        df_guias = pd.read_excel(EXCEL_GUIAS)
        st.session_state.guias_despacho = df_guias.to_dict('records')
    else:
        st.session_state.guias_despacho = []

def guardar_datos():
    st.session_state.materiales.to_excel(EXCEL_MATERIALES, index=False)
    st.session_state.movimientos.to_excel(EXCEL_MOVIMIENTOS, index=False)
    pd.DataFrame(st.session_state.ordenes_picking).to_excel(EXCEL_PICKING, index=False)
    pd.DataFrame(st.session_state.guias_despacho).to_excel(EXCEL_GUIAS, index=False)

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
        
    ]
)

# Botón de Copia de Seguridad en la barra lateral
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Copia de Seguridad")
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
# MÓDULO 1: CREACIÓN DE MATERIALES (Manual y Carga Masiva)
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
        st.write("Sube un archivo en formato **Excel (.xlsx)** o **CSV** con las columnas exactas:")
        st.code("SKU | Nombre | Unidad | Valor_Unitario | Stock_Actual")
        
        archivo_subido = st.file_uploader("Selecciona tu archivo de materiales", type=["csv", "xlsx"])
        
        if archivo_subido is not None:
            try:
                if archivo_subido.name.endswith('.csv'):
                    df_carga = pd.read_csv(archivo_subido)
                else:
                    df_carga = pd.read_excel(archivo_subido)
                
                columnas_requeridas = ["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual"]
                if all(col in df_carga.columns for col in columnas_requeridas):
                    st.write("Vista previa de los datos a cargar:")
                    st.dataframe(df_carga.head(), use_container_width=True)
                    
                    if st.button("Confirmar e Importar Materiales"):
                        for _, row in df_carga.iterrows():
                            sku_val = str(row["SKU"]).strip().upper()
                            if sku_val not in st.session_state.materiales["SKU"].values:
                                nuevo_row = pd.DataFrame([{
                                    "SKU": sku_val,
                                    "Nombre": str(row["Nombre"]),
                                    "Unidad": str(row["Unidad"]),
                                    "Valor_Unitario": float(row["Valor_Unitario"]),
                                    "Stock_Actual": int(row["Stock_Actual"])
                                }])
                                st.session_state.materiales = pd.concat([st.session_state.materiales, nuevo_row], ignore_index=True)
                                
                                if int(row["Stock_Actual"]) > 0:
                                    mov = pd.DataFrame([{
                                        "ID_Mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                                        "Tipo": "STOCK_INICIAL",
                                        "SKU": sku_val,
                                        "Cantidad": int(row["Stock_Actual"]),
                                        "Origen/Destino": "Carga Masiva Excel",
                                        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    }])
                                    st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
                        
                        guardar_datos()
                        st.success("¡Base de datos de materiales cargada y actualizada con éxito!")
                        st.rerun()
                else:
                    st.error(f"El archivo no tiene las columnas correctas. Deben llamarse: {columnas_requeridas}")
            except Exception as e:
                st.error(f"Ocurrió un error al procesar el archivo: {e}")

    st.subheader("Maestro de Materiales Registrados")
    st.dataframe(st.session_state.materiales, use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 2: INGRESO DE MATERIALES
# ---------------------------------------------------------
elif menu == "2. Ingreso de Materiales":
    st.header("📥 Recepción e Ingreso a Bodega")
    
    if st.session_state.materiales.empty:
        st.info("Primero debe crear materiales en el Módulo 1.")
    else:
        with st.form("form_ingreso"):
            sku_ingreso = st.selectbox("Seleccionar Material (SKU)", st.session_state.materiales["SKU"])
            cant_ingreso = st.number_input("Cantidad a Ingresar", min_value=1, value=1)
            proveedor_origen = st.text_input("Proveedor / Procedencia", placeholder="Ej: Proveedor Central S.A.")
            
            btn_ingresar = st.form_submit_button("Registrar Ingreso")
            if btn_ingresar:
                idx = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_ingreso].tolist()[0]
                st.session_state.materiales.loc[idx, "Stock_Actual"] += cant_ingreso
                
                mov = pd.DataFrame([{
                    "ID_Mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                    "Tipo": "INGRESO",
                    "SKU": sku_ingreso,
                    "Cantidad": cant_ingreso,
                    "Origen/Destino": proveedor_origen if proveedor_origen else "Recepción General",
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
                
                guardar_datos()
                st.success(f"Se ingresaron {cant_ingreso} unidades del SKU {sku_ingreso}.")

# ---------------------------------------------------------
# MÓDULO 3: PICKING DE MATERIALES
# ---------------------------------------------------------
elif menu == "3. Picking de Materiales":
    st.header("🛒 Generación y Preparación de Pedidos (Picking)")
    
    if st.session_state.materiales.empty:
        st.info("No hay materiales registrados.")
    else:
        st.subheader("Crear Nueva Orden de Picking")
        with st.form("form_picking"):
            cliente = st.text_input("Cliente / Destino")
            sku_pick = st.selectbox("Material a Extraer", st.session_state.materiales["SKU"])
            cant_pick = st.number_input("Cantidad a Preparar", min_value=1, value=1)
            
            btn_crear_pick = st.form_submit_button("Crear Orden de Picking")
            if btn_crear_pick:
                stock_disponible = st.session_state.materiales.loc[
                    st.session_state.materiales["SKU"] == sku_pick, "Stock_Actual"
                ].values[0]
                
                if cant_pick > stock_disponible:
                    st.error(f"Stock insuficiente. Stock disponible: {stock_disponible}")
                else:
                    id_ord = f"PICK-{len(st.session_state.ordenes_picking)+1:04d}"
                    st.session_state.ordenes_picking.append({
                        "ID_Picking": id_ord,
                        "Cliente": cliente,
                        "SKU": sku_pick,
                        "Cantidad": cant_pick,
                        "Estado": "Pendiente Despacho"
                    })
                    guardar_datos()
                    st.success(f"Orden {id_ord} registrada exitosamente.")

        st.subheader("Órdenes de Picking Actuales")
        if st.session_state.ordenes_picking:
            st.dataframe(pd.DataFrame(st.session_state.ordenes_picking), use_container_width=True)
        else:
            st.write("No hay órdenes de picking registradas.")

# ---------------------------------------------------------
# MÓDULO 4: DESPACHO Y GUÍA DE TRASLADO
# ---------------------------------------------------------
elif menu == "4. Despacho y Guía":
    st.header("🚚 Despacho y Emisión de Guía de Traslado")
    
    pendientes = [p for p in st.session_state.ordenes_picking if p["Estado"] == "Pendiente Despacho"]
    
    if not pendientes:
        st.info("No hay órdenes de picking pendientes por despachar.")
    else:
        df_pendientes = pd.DataFrame(pendientes)
        st.write("Seleccione la orden que desea despachar:")
        
        orden_sel = st.selectbox("Seleccionar Orden de Picking", df_pendientes["ID_Picking"])
        datos_orden = next(item for item in st.session_state.ordenes_picking if item["ID_Picking"] == orden_sel)
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            transporte = st.text_input("Empresa de Transporte")
            Nommbre conductor = st.text_imput("Nombre Conductor")
            Rut = st.text_imput("Rut")
            patente = st.text_input("Patente Vehículo / Placa")
        with col_d2:
            motivo = st.selectbox("Motivo de Traslado", ["Venta", "Traspaso entre bodegas", "Devolución", "Muestras"])
        
        if st.button("Confirmar Despacho y Generar Guía"):
            idx = st.session_state.materiales.index[st.session_state.materiales["SKU"] == datos_orden["SKU"]].tolist()[0]
            st.session_state.materiales.loc[idx, "Stock_Actual"] -= datos_orden["Cantidad"]
            
            datos_orden["Estado"] = "Despachado"
            
            mov = pd.DataFrame([{
                "ID_Mov": f"MOV-{len(st.session_state.movimientos)+1:04d}",
                "Tipo": "DESPACHO",
                "SKU": datos_orden["SKU"],
                "Cantidad": datos_orden["Cantidad"],
                "Origen/Destino": datos_orden["Cliente"],
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            st.session_state.movimientos = pd.concat([st.session_state.movimientos, mov], ignore_index=True)
            
            num_guia = f"GD-{len(st.session_state.guias_traslado)+1:04d}"
            guia_data = {
                "Numero_Guia": num_guia,
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Cliente": datos_orden["Cliente"],
                "SKU": datos_orden["SKU"],
                "Cantidad": datos_orden["Cantidad"],
                "Transporte": transporte,
                "Patente": patente,
                "Motivo": motivo
            }
            st.session_state.guias_traslado.append(guia_data)
            
            guardar_datos()
            st.success(f"¡Despacho realizado con éxito! Guía Generada: **{num_guia}**")
            st.session_state.ultima_guia = guia_data

    if "ultima_guia" in st.session_state:
        st.markdown("---")
        st.subheader(f"📄 DOCUMENTO: GUÍA DE TRASLADO N° {st.session_state.ultima_guia['Numero_Guia']}")
        
        guia = st.session_state.ultima_guia
        
        st.markdown("""
            <style>
            @media print {
                [data-testid="stSidebar"], header, .stButton {
                    display: none !important;
                }
                body {
                    background-color: white !important;
                }
            }
            </style>
        """, unsafe_allow_html=True)

        html_guia = f"""
        <div style="border: 2px solid #000; padding: 25px; font-family: Arial, sans-serif; background-color: white; color: black; border-radius: 5px;">
            <div style="text-align: center;">
                <img src="https://i.imgur.com/tu_logo_ejemplo.png" style="max-height: 80px; margin-bottom: 5px;">
                <h2 style="margin: 0;">WMS MARKLOGISTIC S.A.</h2>
                <p style="margin: 0; font-size: 13px;">R.U.T.: 76.543.210-K | Giro: Logística y Distribución</p>
            </div>
            <hr style="border: 1px solid #000;">
            <h3 style="text-align: right; color: #cc0000; margin: 0;">GUÍA DE TRASLADO</h3>
            <h3 style="text-align: right; margin: 0;">N° {guia['Numero_Guia']}</h3>
            <p><b>Fecha de Emisión:</b> {guia['Fecha']}</p>
            <p><b>Señor(es):</b> {guia['Cliente']}</p>
            <p><b>Transportista:</b> {guia['Transporte']} | <b>Patente:</b> {guia['Patente']}</p>
            <p><b>Motivo de Traslado:</b> {guia['Motivo']}</p>
            <br>
            <table style="width: 100%; border-collapse: collapse; border: 1px solid black;">
                <thead>
                    <tr style="background-color: #f2f2f2;">
                        <th style="border: 1px solid black; padding: 8px;">SKU</th>
                        <th style="border: 1px solid black; padding: 8px;">Cantidad</th>
                        <th style="border: 1px solid black; padding: 8px;">Descripción / Detalle</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="border: 1px solid black; padding: 8px; text-align: center;">{guia['SKU']}</td>
                        <td style="border: 1px solid black; padding: 8px; text-align: center;">{guia['Cantidad']}</td>
                        <td style="border: 1px solid black; padding: 8px;">Despacho operativo según orden de picking</td>
                    </tr>
                </tbody>
            </table>
            <br><br><br>
            <div style="display: flex; justify-content: space-between; text-align: center; font-size: 14px;">
                <div style="width: 40%;"><p>___________________________________<br><b>Firma Chofer / Transportista</b></p></div>
                <div style="width: 40%;"><p>___________________________________<br><b>Firma Recinto / Cliente Conforme</b></p></div>
            </div>
        </div>
        """
        st.markdown(html_guia, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 **Para imprimir o guardar en PDF:** Presiona las teclas **`Ctrl + P`** en tu teclado (o **`Cmd + P`** en Mac).")

# ---------------------------------------------------------
# MÓDULO 5: INVENTARIO
# ---------------------------------------------------------
elif menu == "5. Inventario":
    st.header("📊 Control de Inventario en Tiempo Real")
    
    col_k1, col_k2 = st.columns(2)
    with col_k1:
        st.metric("Total SKU Registrados", len(st.session_state.materiales))
    with col_k2:
        st.metric("Total Unidades en Stock", int(st.session_state.materiales["Stock_Actual"].sum()) if not st.session_state.materiales.empty else 0)
    
    st.subheader("Stock Actual y Valorización por Material")
    st.dataframe(st.session_state.materiales, use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 6: TRAZABILIDAD
# ---------------------------------------------------------
elif menu == "6. Trazabilidad":
    st.header("🔍 Trazabilidad e Historial de Movimientos")
    
    if st.session_state.movimientos.empty:
        st.info("No hay registro de movimientos.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            sku_filtro = st.selectbox("Filtrar por SKU", ["Todos"] + list(st.session_state.materiales["SKU"].unique()))
        with col_f2:
            tipo_filtro = st.selectbox("Filtrar por Tipo de Movimiento", ["Todos", "STOCK_INICIAL", "INGRESO", "DESPACHO"])
        
        df_traza = st.session_state.movimientos.copy()
        
        if sku_filtro != "Todos":
            df_traza = df_traza[df_traza["SKU"] == sku_filtro]
        if tipo_filtro != "Todos":
            df_traza = df_traza[df_traza["Tipo"] == tipo_filtro]
            
        st.dataframe(df_traza.sort_values(by="Fecha", ascending=False), use_container_width=True)

# ---------------------------------------------------------
# MÓDULO 7: ETIQUETAS DE MATERIALES
# ---------------------------------------------------------
elif menu == "7. Etiquetas":
    st.header("🏷️ Generación e Impresión de Etiquetas de Bodega")
    
    if st.session_state.materiales.empty:
        st.info("No hay materiales registrados para etiquetar.")
    else:
        sku_etiqueta = st.selectbox("Seleccionar Material para Etiquetar", st.session_state.materiales["SKU"])
        mat_info = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_etiqueta].iloc[0]
        
        cantidad_copias = st.number_input("Número de etiquetas a imprimir", min_value=1, value=1)
        
        if st.button("Generar Vista Previa de Etiqueta"):
            st.markdown("---")
            st.subheader("Vista Previa (Optimizado para Impresión)")
            
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
                    <h4 style="text-align: center; margin: 0 0 10px 0; font-size: 16px;">ERP MARKLOGISTIC</h4>
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
            
            st.info("💡 **Para imprimir:** Presiona las teclas **`Ctrl + P`** en tu teclado (o **`Cmd + P`** en Mac).")

# ---------------------------------------------------------
# MÓDULO 8: ELIMINAR TRANSACCIONES (NUEVO)
# ---------------------------------------------------------
elif menu == "8. Eliminar Transacciones":
    st.header("🗑️ Gestión y Anulación de Transacciones (Ingresos / Despachos)")
    
    if st.session_state.movimientos.empty:
        st.info("No hay transacciones registradas para eliminar.")
    else:
        st.write("Selecciona el movimiento que deseas eliminar o anular. **Nota:** Si eliminas un Ingreso o Despacho, el stock del material se ajustará automáticamente.")
        
        # Mostrar tabla de movimientos con opción de selección
        st.dataframe(st.session_state.movimientos, use_container_width=True)
        
        id_a_eliminar = st.selectbox("Seleccionar ID de Movimiento a Eliminar", st.session_state.movimientos["ID_Mov"])
        
        if st.button("🗑️ Eliminar Transacción Seleccionada", type="primary"):
            # Obtener datos del movimiento antes de borrarlo
            mov_reg = st.session_state.movimientos[st.session_state.movimientos["ID_Mov"] == id_a_eliminar].iloc[0]
            tipo_mov = mov_reg["Tipo"]
            sku_mov = mov_reg["SKU"]
            cant_mov = mov_reg["Cantidad"]
            
            # Revertir stock según el tipo de movimiento
            if sku_mov in st.session_state.materiales["SKU"].values:
                idx_mat = st.session_state.materiales.index[st.session_state.materiales["SKU"] == sku_mov].tolist()[0]
                
                if tipo_mov in ["INGRESO", "STOCK_INICIAL"]:
                    # Si se borra un ingreso, se resta del stock actual
                    st.session_state.materiales.loc[idx_mat, "Stock_Actual"] -= cant_mov
                elif tipo_mov == "DESPACHO":
                    # Si se borra un despacho, se devuelve al stock actual
                    st.session_state.materiales.loc[idx_mat, "Stock_Actual"] += cant_mov
            
            # Eliminar el movimiento del DataFrame
            st.session_state.movimientos = st.session_state.movimientos[st.session_state.movimientos["ID_Mov"] != id_a_eliminar].reset_index(drop=True)
            
            # Guardar cambios
            guardar_datos()
            st.success(f"✅ Transacción {id_a_eliminar} eliminada y stock actualizado correctamente.")
            st.rerun()

# ---------------------------------------------------------
# MÓDULO 9: ASISTENTE DE INTELIGENCIA ARTIFICIAL (GEMINI)
# ---------------------------------------------------------
elif menu == "9. Asistente IA":
    st.header("🤖 Asistente Inteligente de Bodega y Logística")
    st.write("Pregúntale al asistente sobre el stock, productos o el estado actual de tu ERP en lenguaje natural.")

    if "GEMINI_API_KEY" in st.secrets:
        try:
            from google import genai
            client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

            pregunta_usuario = st.text_input("¿Qué deseas consultar al sistema?", placeholder="Ej: ¿Qué productos tienen menos stock actual?")

            if st.button("Consultar a la IA") and pregunta_usuario:
                with st.spinner("Analizando la base de datos del ERP..."):
                    resumen_stock = st.session_state.materiales.to_string() if not st.session_state.materiales.empty else "No hay materiales."
                    resumen_movimientos = st.session_state.movimientos.tail(10).to_string() if not st.session_state.movimientos.empty else "No hay movimientos."

                    prompt_sistema = f"""
                    Eres un asistente logístico experto para el ERP Marklogistic. 
                    Tienes acceso a los siguientes datos actuales de la bodega:
                    
                    --- MATERIALES Y STOCK ---
                    {resumen_stock}
                    
                    --- ÚLTIMOS MOVIMIENTOS ---
                    {resumen_movimientos}
                    
                    Responde de forma clara, profesional y directa a la siguiente pregunta del usuario basándote exclusivamente en estos datos:
                    {pregunta_usuario}
                    """

                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt_sistema,
                    )

                    st.markdown("### 💡 Respuesta del Asistente:")
                    st.success(response.text)

        except Exception as e:
            st.error(f"Error al conectar con la Inteligencia Artificial: {e}")
    else:
        st.warning("⚠️ Para usar este módulo, debes configurar tu `GEMINI_API_KEY` en los secretos de Streamlit Cloud.")
