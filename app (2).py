import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="ERP Marklogistic", layout="wide")

# ---------------------------------------------------------
# 0. CONFIGURACIÓN DE USUARIO Y AUTENTICACIÓN
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
    st.title("🔐 Acceso al ERP Marklogistic")
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
# 1. INICIALIZACIÓN DE BASE DE DATOS (Incluyendo 'Valor_Unitario')
# ---------------------------------------------------------
if "materiales" not in st.session_state:
    st.session_state.materiales = pd.DataFrame(columns=["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual"])

if "movimientos" not in st.session_state:
    st.session_state.movimientos = pd.DataFrame(columns=["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen/Destino", "Fecha"])

if "ordenes_picking" not in st.session_state:
    st.session_state.ordenes_picking = []

if "guias_despacho" not in st.session_state:
    st.session_state.guias_despacho = []

# ---------------------------------------------------------
# 2. PANEL LATERAL / NAVEGACIÓN
# ---------------------------------------------------------
st.sidebar.title("📦 ERP Marklogistic")
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
        "6. Trazabilidad"
    ]
)

# ---------------------------------------------------------
# MÓDULO 1: CREACIÓN DE MATERIALES (Con campo Valor Unitario)
# ---------------------------------------------------------
if menu == "1. Creación de Materiales":
    st.header("📋 Registro de Nuevos Materiales / Maestro de SKU")
    
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
                        
                    st.success(f"Material {sku} creado correctamente con valor unitario de ${valor_unitario:,.2f}.")

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
                    st.success(f"Orden {id_ord} registrada exitosamente.")

        st.subheader("Órdenes de Picking Actuales")
        if st.session_state.ordenes_picking:
            st.dataframe(pd.DataFrame(st.session_state.ordenes_picking), use_container_width=True)
        else:
            st.write("No hay órdenes de picking registradas.")

# ---------------------------------------------------------
# MÓDULO 4: DESPACHO Y GUÍA DE DESPACHO
# ---------------------------------------------------------
elif menu == "4. Despacho y Guía":
    st.header("🚚 Despacho y Emisión de Guía de Despacho")
    
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
            transporte = st.text_input("Empresa de Transporte / Chofer")
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
            
            num_guia = f"GD-{len(st.session_state.guias_despacho)+1:04d}"
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
            st.session_state.guias_despacho.append(guia_data)
            
            st.success(f"¡Despacho realizado con éxito! Guía Generada: **{num_guia}**")
            
            st.markdown("---")
            st.subheader(f"📄 GUÍA DE DESPACHO N° {num_guia}")
            st.write(f"**Empresa:** ERP Marklogistic")
            st.write(f"**Cliente:** {datos_orden['Cliente']}")
            st.write(f"**Fecha:** {guia_data['Fecha']}")
            st.write(f"**Transportista:** {transporte} | **Patente:** {patente}")
            
            df_detalle = pd.DataFrame([{
                "SKU": datos_orden["SKU"],
                "Cantidad Despachada": datos_orden["Cantidad"],
                "Motivo": motivo
            }])
            st.table(df_detalle)

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

