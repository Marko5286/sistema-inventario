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
import sqlite3

st.set_page_config(page_title="WMS Marklogistic", layout="wide")

# ---------------------------------------------------------
# 0. CONFIGURACIÓN DE BASE DE DATOS SQLITE (Persistencia Robusta)
# ---------------------------------------------------------
DB_FILE = "wms_marklogistic.db"

def inicializar_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materiales (
            SKU TEXT PRIMARY KEY,
            Nombre TEXT,
            Unidad TEXT,
            Valor_Unitario REAL,
            Stock_Actual INTEGER,
            Stock_Minimo INTEGER,
            Ubicacion TEXT,
            Bodega TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimientos (
            ID_Mov TEXT PRIMARY KEY,
            Tipo TEXT,
            SKU TEXT,
            Cantidad INTEGER,
            Origen_Destino TEXT,
            Fecha TEXT,
            Usuario TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS picking (
            ID_Picking TEXT PRIMARY KEY,
            Cliente TEXT,
            SKU TEXT,
            Ubicacion TEXT,
            Cantidad INTEGER,
            Estado TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guias (
            Numero_Guia TEXT PRIMARY KEY,
            Fecha TEXT,
            Cliente TEXT,
            Rut TEXT,
            SKU TEXT,
            Cantidad INTEGER,
            Transporte TEXT,
            Conductor TEXT,
            Rut_Conductor TEXT,
            Patente TEXT,
            Motivo TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

inicializar_db()

# Cargar datos desde SQLite a st.session_state al iniciar
if "materiales" not in st.session_state:
    conn = sqlite3.connect(DB_FILE)
    st.session_state.materiales = pd.read_sql("SELECT * FROM materiales", conn)
    st.session_state.movimientos = pd.read_sql("SELECT * FROM movimientos", conn)
    
    df_pick = pd.read_sql("SELECT * FROM picking", conn)
    st.session_state.ordenes_picking = df_pick.to_dict('records') if not df_pick.empty else []
    
    df_guias = pd.read_sql("SELECT * FROM guias", conn)
    st.session_state.guias_despacho = df_guias.to_dict('records') if not df_guias.empty else []
    conn.close()

def guardar_datos():
    try:
        conn = sqlite3.connect(DB_FILE)
        st.session_state.materiales.to_sql("materiales", conn, if_exists="replace", index=False)
        st.session_state.movimientos.to_sql("movimientos", conn, if_exists="replace", index=False)
        
        if st.session_state.ordenes_picking:
            pd.DataFrame(st.session_state.ordenes_picking).to_sql("picking", conn, if_exists="replace", index=False)
        else:
            pd.DataFrame(columns=["ID_Picking", "Cliente", "SKU", "Ubicacion", "Cantidad", "Estado"]).to_sql("picking", conn, if_exists="replace", index=False)
            
        if st.session_state.guias_despacho:
            df_g_sql = pd.DataFrame(st.session_state.guias_despacho).drop(columns=["Firma_Img"], errors="ignore")
            df_g_sql.to_sql("guias", conn, if_exists="replace", index=False)
        else:
            pd.DataFrame(columns=["Numero_Guia", "Fecha", "Cliente", "Rut", "SKU", "Cantidad", "Transporte", "Conductor", "Rut_Conductor", "Patente", "Motivo"]).to_sql("guias", conn, if_exists="replace", index=False)
            
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error al guardar en la base de datos: {e}")

# ---------------------------------------------------------
# FUNCIÓN PARA GENERAR EL PDF DE LA GUÍA DE DESPACHO
# ---------------------------------------------------------
def generar_pdf_guia(guia):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    c.drawString(50, height - 50, f"GUÍA DE DESPACHO: {guia['Numero_Guia']}")
    c.drawString(50, height - 70, f"Fecha: {guia['Fecha']}")
    c.drawString(50, height - 90, f"Cliente: {guia['Cliente']} (RUT: {guia['Rut']})")
    c.drawString(50, height - 110, f"SKU: {guia['SKU']} | Cantidad: {guia['Cantidad']}")
    c.drawString(50, height - 130, f"Transporte: {guia['Transporte']} | Patente: {guia['Patente']}")
    c.drawString(50, height - 150, f"Conductor: {guia['Conductor']} (RUT: {guia['Rut_Conductor']})")
    c.drawString(50, height - 170, f"Motivo: {guia['Motivo']}")
    
    if "Firma_Img" in guia and guia["Firma_Img"] is not None:
        try:
            img = Image.fromarray(guia["Firma_Img"].astype('uint8'), 'RGBA')
            img_reader = ImageReader(img)
            c.drawImage(img_reader, 50, height - 320, width=200, height=100)
        except Exception:
            pass
            
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# SISTEMA DE AUTENTICACIÓN Y BARRA LATERAL
# ---------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 WMS Marklogistic - Iniciar Sesión")
    usuario_ingresado = st.text_input("Usuario")
    password_ingresado = st.text_input("Contraseña", type="password")
    
    if st.button("Ingresar"):
        if (usuario_ingresado == "admin" and password_ingresado == "admin123") or \
           (usuario_ingresado == "bodega" and password_ingresado == "bodega123") or \
           (usuario_ingresado == "logistica" and password_ingresado == "logistica123"):
            st.session_state.autenticado = True
            st.session_state.usuario_actual = usuario_ingresado
            st.success("¡Bienvenido!")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")
    menu = None
else:
    usuario_actual = st.session_state.get("usuario_actual", "bodega")

    st.sidebar.title("📦 WMS Marklogistic")
    st.sidebar.write(f"Usuario: **{usuario_actual}**")
    
    # Resumen Rápido en Barra Lateral (UX)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Estado Rápido")
    if "materiales" in st.session_state and not st.session_state.materiales.empty:
        total_items = len(st.session_state.materiales)
        if "Stock_Minimo" in st.session_state.materiales.columns:
            criticos = len(st.session_state.materiales[st.session_state.materiales["Stock_Actual"] <= st.session_state.materiales["Stock_Minimo"]])
        else:
            criticos = 0
            
        st.sidebar.metric("📦 SKUs Totales", total_items)
        if criticos > 0:
            st.sidebar.metric("⚠️ Alertas Stock", criticos, delta=-criticos, delta_color="inverse")
        else:
            st.sidebar.metric("✅ Alertas Stock", 0)
    st.sidebar.markdown("---")
    
    opciones_menu = [
        "1. Creación de Materiales",
        "2. Ingresos de Stock",
        "3. Picking y Salidas",
        "4. Despacho y Guía",
        "5. Inventario",
        "6. Dashboard Gerencial",
        "7. Trazabilidad",
        "8. Etiquetas"
    ]
    
    if usuario_actual == "admin":
        opciones_menu.append("9. Eliminar Transacciones")
        
    menu = st.sidebar.selectbox("Seleccione Módulo", opciones_menu)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# ---------------------------------------------------------
# MÓDULOS DE LA APLICACIÓN
# ---------------------------------------------------------
if st.session_state.get("autenticado", False) and menu:

    # ---------------------------------------------------------
    # MÓDULO 1: CREACIÓN DE MATERIALES
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
                    stk_min_m = st.number_input("Stock Mínimo de Alerta", min_value=0, value=5)
                
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
                            "Stock_Minimo": stk_min_m,
                            "Ubicacion": ubi_m,
                            "Bodega": "Bodega Central Antofagasta"
                        }])
                        st.session_state.materiales = pd.concat([st.session_state.materiales, nuevo], ignore_index=True)
                        guardar_datos()
                        st.success(f"Material {sku_m} creado correctamente.")
                        st.rerun()

        with tab_masivo:
            st.subheader("Subir Planilla Excel de Materiales")
            archivo_excel = st.file_uploader("Selecciona el archivo Excel (.xlsx)", type=["xlsx", "xls"])
            if archivo_excel is not None:
                try:
                    df_cargado = pd.read_excel(archivo_excel)
                    columnas_requeridas = ["SKU", "Nombre", "Unidad", "Valor_Unitario", "Stock_Actual", "Stock_Minimo", "Ubicacion", "Bodega"]
                    if not all(col in df_cargado.columns for col in ["SKU", "Nombre"]):
                        st.error("⚠️ El archivo subido debe contener al menos las columnas 'SKU' y 'Nombre'.")
                    else:
                        if "Unidad" not in df_cargado.columns: df_cargado["Unidad"] = "Unidades"
                        if "Valor_Unitario" not in df_cargado.columns: df_cargado["Valor_Unitario"] = 0
                        if "Stock_Actual" not in df_cargado.columns: df_cargado["Stock_Actual"] = 0
                        if "Stock_Minimo" not in df_cargado.columns: df_cargado["Stock_Minimo"] = 5
                        if "Ubicacion" not in df_cargado.columns: df_cargado["Ubicacion"] = "A-00-0"
                        if "Bodega" not in df_cargado.columns: df_cargado["Bodega"] = "Bodega Central Antofagasta"
                        
                        df_cargado["SKU"] = df_cargado["SKU"].astype(str).str.strip().str.upper()
                        st.dataframe(df_cargado[columnas_requeridas].head(10))
                        
                        if st.button("🚀 Confirmar e Importar Datos"):
                            skus_existentes = set(st.session_state.materiales["SKU"].tolist())
                            df_nuevos = df_cargado[~df_cargado["SKU"].isin(skus_existentes)][columnas_requeridas]
                            if not df_nuevos.empty:
                                st.session_state.materiales = pd.concat([st.session_state.materiales, df_nuevos], ignore_index=True)
                                guardar_datos()
                                st.success(f"¡Carga completada! Se importaron **{len(df_nuevos)}** materiales.")
                                st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("---")
        st.subheader("Maestro de Materiales Registrados")
        st.dataframe(st.session_state.materiales, use_container_width=True)

    # ---------------------------------------------------------
    # MÓDULO 2: INGRESOS DE STOCK
    # ---------------------------------------------------------
    elif menu == "2. Ingresos de Stock":
        st.header("📥 Ingresos de Stock a Bodega")
        if st.session_state.materiales.empty:
            st.warning("Primero debes registrar materiales en el Módulo 1.")
        else:
            with st.form("form_ingreso"):
                sku_ing = st.selectbox("Seleccione SKU", st.session_state.materiales["SKU"].tolist())
                cant_ing = st.number_input("Cantidad a Ingresar", min_value=1, value=1)
                origen_ing = st.text_input("Proveedor / Origen", value="Compra Proveedor")
                
                if st.form_submit_button("Registrar Ingreso"):
                    idx = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_ing].index[0]
                    st.session_state.materiales.loc[idx, "Stock_Actual"] += cant_ing
                    
                    nuevo_mov = pd.DataFrame([{
                        "ID_Mov": f"ING-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "Tipo": "Ingreso",
                        "SKU": sku_ing,
                        "Cantidad": cant_ing,
                        "Origen_Destino": origen_ing,
                        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Usuario": usuario_actual
                    }])
                    st.session_state.movimientos = pd.concat([st.session_state.movimientos, nuevo_mov], ignore_index=True)
                    guardar_datos()
                    st.success(f"¡Ingreso registrado con éxito! Stock actualizado para {sku_ing}.")
                    st.rerun()

    # ---------------------------------------------------------
    # MÓDULO 3: PICKING Y SALIDAS
    # ---------------------------------------------------------
    elif menu == "3. Picking y Salidas":
        st.header("📦 Órdenes de Picking y Salidas de Material")
        if st.session_state.materiales.empty:
            st.warning("No hay materiales en el inventario.")
        else:
            with st.form("form_picking"):
                cliente_pk = st.text_input("Cliente / Destino")
                sku_pk = st.selectbox("SKU a Despachar", st.session_state.materiales["SKU"].tolist())
                cant_pk = st.number_input("Cantidad Requerida", min_value=1, value=1)
                
                if st.form_submit_button("Generar Orden de Picking"):
                    stock_disp = int(st.session_state.materiales.loc[st.session_state.materiales["SKU"] == sku_pk, "Stock_Actual"].values[0])
                    if cant_pk > stock_disp:
                        st.error(f"Stock insuficiente. Disponible actual: {stock_disp}")
                    else:
                        ubicacion_sku = st.session_state.materiales.loc[st.session_state.materiales["SKU"] == sku_pk, "Ubicacion"].values[0]
                        nueva_orden = {
                            "ID_Picking": f"PK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                            "Cliente": cliente_pk,
                            "SKU": sku_pk,
                            "Ubicacion": ubicacion_sku,
                            "Cantidad": cant_pk,
                            "Estado": "Pendiente"
                        }
                        st.session_state.ordenes_picking.append(nueva_orden)
                        guardar_datos()
                        st.success("Orden de Picking generada correctamente.")
                        st.rerun()

            st.markdown("---")
            st.subheader("Órdenes de Picking Registradas")
            if st.session_state.ordenes_picking:
                df_pk = pd.DataFrame(st.session_state.ordenes_picking)
                st.dataframe(df_pk, use_container_width=True)
            else:
                st.info("No hay órdenes de picking creadas.")

    # ---------------------------------------------------------
    # MÓDULO 4: DESPACHO Y GUÍA
    # ---------------------------------------------------------
    elif menu == "4. Despacho y Guía":
        st.header("🚚 Emisión de Guías de Despacho y Documentación")
        if not st.session_state.ordenes_picking:
            st.warning("No hay órdenes de picking disponibles para despachar.")
        else:
            pendientes = [o["ID_Picking"] for o in st.session_state.ordenes_picking if o["Estado"] == "Pendiente"]
            if not pendientes:
                st.info("No hay órdenes pendientes de despacho.")
            else:
                pk_sel = st.selectbox("Seleccionar Orden de Picking", pendientes)
                orden_act = next(o for o in st.session_state.ordenes_picking if o["ID_Picking"] == pk_sel)
                
                with st.form("form_guia"):
                    st.write(f"**Cliente:** {orden_act['Cliente']} | **SKU:** {orden_act['SKU']} | **Cant:** {orden_act['Cantidad']}")
                    num_guia = st.text_input("Número de Guía de Despacho", value=f"GD-{datetime.now().strftime('%Y%m%d%H%M')}")
                    rut_cli = st.text_input("RUT Cliente")
                    transporte = st.text_input("Empresa de Transporte")
                    conductor = st.text_input("Nombre Conductor")
                    rut_cond = st.text_input("RUT Conductor")
                    patente = st.text_input("Patente Vehículo")
                    motivo = st.selectbox("Motivo del Despacho", ["Venta", "Traslado", "Devolución", "Muestras"])
                    
                    if st.form_submit_button("Emitir Guía y Descontar Stock"):
                        sku_g = orden_act["SKU"]
                        cant_g = orden_act["Cantidad"]
                        
                        idx = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_g].index[0]
                        st.session_state.materiales.loc[idx, "Stock_Actual"] -= cant_g
                        
                        for o in st.session_state.ordenes_picking:
                            if o["ID_Picking"] == pk_sel:
                                o["Estado"] = "Completado"
                                
                        nuevo_mov = pd.DataFrame([{
                            "ID_Mov": f"SAL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                            "Tipo": "Salida/Despacho",
                            "SKU": sku_g,
                            "Cantidad": cant_g,
                            "Origen_Destino": orden_act["Cliente"],
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Usuario": usuario_actual
                        }])
                        st.session_state.movimientos = pd.concat([st.session_state.movimientos, nuevo_mov], ignore_index=True)
                        
                        nueva_g = {
                            "Numero_Guia": num_guia,
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Cliente": orden_act["Cliente"],
                            "Rut": rut_cli,
                            "SKU": sku_g,
                            "Cantidad": cant_g,
                            "Transporte": transporte,
                            "Conductor": conductor,
                            "Rut_Conductor": rut_cond,
                            "Patente": patente,
                            "Motivo": motivo
                        }
                        st.session_state.guias_despacho.append(nueva_g)
                        guardar_datos()
                        st.success("¡Guía emitida con éxito y stock descontado!")
                        st.rerun()

    # ---------------------------------------------------------
    # MÓDULO 5: INVENTARIO
    # ---------------------------------------------------------
    elif menu == "5. Inventario":
        st.header("📊 Control de Inventario y Alertas de Stock")
        if st.session_state.materiales.empty:
            st.info("No hay materiales registrados en el inventario.")
        else:
            df_inv = st.session_state.materiales.copy()
            quiebres = df_inv[df_inv["Stock_Actual"] <= df_inv["Stock_Minimo"]] if "Stock_Minimo" in df_inv.columns else pd.DataFrame()
            
            col_k1, col_k2, col_k3 = st.columns(3)
            with col_k1:
                st.metric("Total SKU Registrados", len(df_inv))
            with col_k2:
                st.metric("Total Unidades", int(df_inv["Stock_Actual"].sum()))
            with col_k3:
                st.metric("⚠️ SKUs en Stock Crítico", len(quiebres), delta=-len(quiebres) if len(quiebres) > 0 else 0, delta_color="inverse")
            
            if not quiebres.empty:
                st.warning("⚠️ **Atención:** Productos en o por debajo de su stock mínimo:")
                st.dataframe(quiebres[["SKU", "Nombre", "Stock_Actual", "Stock_Minimo", "Ubicacion"]], use_container_width=True)
            
            st.markdown("---")
            st.subheader("🔍 Filtros y Búsqueda Avanzada")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                busqueda_texto = st.text_input("Filtrar por SKU o Nombre").strip().upper()
            with col_f2:
                bodegas_disponibles = ["Todas"] + list(df_inv["Bodega"].unique()) if "Bodega" in df_inv.columns else ["Todas"]
                filtro_bodega = st.selectbox("Filtrar por Bodega", bodegas_disponibles)
                
            df_filtrado = df_inv.copy()
            if busqueda_texto:
                df_filtrado = df_filtrado[
                    df_filtrado["SKU"].str.upper().str.contains(busqueda_texto) | 
                    df_filtrado["Nombre"].str.upper().str.contains(busqueda_texto)
                ]
            if filtro_bodega != "Todas":
                df_filtrado = df_filtrado[df_filtrado["Bodega"] == filtro_bodega]
                
            st.dataframe(df_filtrado, use_container_width=True)

    # ---------------------------------------------------------
    # MÓDULO 6: DASHBOARD GERENCIAL
    # ---------------------------------------------------------
    elif menu == "6. Dashboard Gerencial":
        st.header("📈 Dashboard Gerencial y Kpis de Bodega")
        if st.session_state.materiales.empty:
            st.info("No hay datos suficientes para mostrar el dashboard.")
        else:
            df_m = st.session_state.materiales
            valor_total_inv = (df_m["Stock_Actual"] * df_m["Valor_Unitario"]).sum()
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Valorización Total Inventario", f"${valor_total_inv:,.0f}")
            with c2:
                st.metric("Total Movimientos Registrados", len(st.session_state.movimientos))
            with c3:
                st.metric("Guías Emitidas", len(st.session_state.guias_despacho))

    # ---------------------------------------------------------
    # MÓDULO 7: TRAZABILIDAD
    # ---------------------------------------------------------
    elif menu == "7. Trazabilidad":
        st.header("🔎 Trazabilidad de Movimientos por SKU")
        if st.session_state.movimientos.empty:
            st.info("No hay movimientos registrados.")
        else:
            sku_traza = st.selectbox("Seleccione SKU para Auditar", st.session_state.materiales["SKU"].tolist())
            df_movs = st.session_state.movimientos
            df_filtrado_mov = df_movs[df_movs["SKU"] == sku_traza]
            st.dataframe(df_filtrado_mov, use_container_width=True)

    # ---------------------------------------------------------
    # MÓDULO 8: ETIQUETAS
    # ---------------------------------------------------------
    elif menu == "8. Etiquetas":
        st.header("🏷️ Generación e Impresión de Etiquetas de SKU y Ubicación")
        if st.session_state.materiales.empty:
            st.info("No hay materiales para etiquetar.")
        else:
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                sku_etiq = st.selectbox("Seleccione SKU para Etiqueta", st.session_state.materiales["SKU"].tolist())
            with col_e2:
                copias = st.number_input("Cantidad de copias", min_value=1, value=1)
                
            mat_sel = st.session_state.materiales[st.session_state.materiales["SKU"] == sku_etiq].iloc[0]
            
            st.markdown("---")
            st.subheader("👁️ Vista Previa de la Etiqueta")
            
            st.markdown(f"""
            <div style="border: 3px dashed #333; padding: 20px; border-radius: 10px; background-color: white; color: black; max-width: 400px; font-family: monospace;">
                <h3 style="margin: 0; color: #000;">📦 WMS MARKLOGISTIC</h3>
                <hr style="border: 1px solid #333;">
                <p style="font-size: 18px; margin: 5px 0;"><b>SKU:</b> {mat_sel['SKU']}</p>
                <p style="font-size: 16px; margin: 5px 0;"><b>Descripción:</b> {mat_sel['Nombre']}</p>
                <p style="font-size: 16px; margin: 5px 0;"><b>Ubicación:</b> <span style="background-color: #eee; padding: 2px 6px; border-radius: 4px;"><b>{mat_sel['Ubicacion']}</b></span></p>
                <p style="font-size: 14px; margin: 5px 0; color: #555;">Bodega: {mat_sel['Bodega']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            def generar_pdf_etiqueta(mat, n_copias):
                buffer = BytesIO()
                c = canvas.Canvas(buffer, pagesize=(300, 200))
                for i in range(n_copias):
                    if i > 0:
                        c.showPage()
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(15, 175, "WMS MARKLOGISTIC - ETIQUETA")
                    c.line(15, 165, 285, 165)
                    c.setFont("Helvetica-Bold", 14)
                    c.drawString(15, 135, f"SKU: {mat['SKU']}")
                    c.setFont("Helvetica", 11)
                    c.drawString(15, 110, f"Nombre: {str(mat['Nombre'])[:35]}")
                    c.setFont("Helvetica-Bold", 13)
                    c.drawString(15, 80, f"UBICACIÓN: {mat['Ubicacion']}")
                    c.setFont("Helvetica", 9)
                    c.drawString(15, 50, f"Bodega: {mat['Bodega']}")
                    c.drawString(15, 35, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                c.save()
                buffer.seek(0)
                return buffer

            pdf_buffer = generar_pdf_etiqueta(mat_sel, copias)
            
            st.download_button(
                label="🖨️ Descargar Etiqueta en PDF (Lista para Imprimir)",
                data=pdf_buffer,
                file_name=f"etiqueta_{mat_sel['SKU']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

    # ---------------------------------------------------------
    # MÓDULO 9: ELIMINAR TRANSACCIONES (ADMIN)
    # ---------------------------------------------------------
    elif menu == "9. Eliminar Transacciones" and usuario_actual == "admin":
        st.header("⚙️ Panel de Administración - Resetear o Eliminar Datos")
        if st.button("⚠️ Borrar Todos los Movimientos"):
            st.session_state.movimientos = pd.DataFrame(columns=["ID_Mov", "Tipo", "SKU", "Cantidad", "Origen_Destino", "Fecha", "Usuario"])
            guardar_datos()
            st.success("Movimientos eliminados.")
            st.rerun()
