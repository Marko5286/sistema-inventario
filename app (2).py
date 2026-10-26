import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 1. Configuración de la página
st.set_page_config(page_title=" ERP Marklogistic", page_icon="📦", layout="wide")

# 2. Inicializar el estado de autenticación en la sesión
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# 3. Función de la pantalla de Login
def mostrar_login():
    st.subheader("🔐 Iniciar Sesión - Control de Inventario")
    
    USUARIOS_VALIDOS = {
        "admin": "12345",
        "operador": "password123"
    }

    with st.form("form_login"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit_login = st.form_submit_button("Ingresar")

        if submit_login:
            if usuario in USUARIOS_VALIDOS and USUARIOS_VALIDOS[usuario] == password:
                st.session_state.autenticado = True
                st.session_state.usuario_actual = usuario
                st.success(f"¡Bienvenido, {usuario}!")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")

# 4. Control de flujo
if not st.session_state.autenticado:
    mostrar_login()
else:
    # --- "ERP Marklogistic" ---
    
    st.sidebar.write(f"👤 Conectado como: **{st.session_state.usuario_actual}**")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    st.title("📦 ERP Marklogistic")

    # Archivos CSV
    FILE_PRODUCTOS = "productos.csv"
    FILE_MOVIMIENTOS = "movimientos.csv"

    def cargar_productos():
        if os.path.exists(FILE_PRODUCTOS):
            return pd.read_csv(FILE_PRODUCTOS)
        else:
            return pd.DataFrame(columns=["Código", "Nombre", "Categoría", "Stock Actual", "Stock Mínimo (Crítico)", "Precio Unitario ($)"])

    def guardar_productos(df):
        df.to_csv(FILE_PRODUCTOS, index=False)

    def cargar_movimientos():
        if os.path.exists(FILE_MOVIMIENTOS):
            return pd.read_csv(FILE_MOVIMIENTOS)
        else:
            return pd.DataFrame(columns=["Fecha", "Código", "Producto", "Tipo", "Cantidad", "Motivo"])

    def guardar_movimientos(df):
        df.to_csv(FILE_MOVIMIENTOS, index=False)

    df_productos = cargar_productos()
    df_movimientos = cargar_movimientos()

    # Menú de navegación actualizado con la Guía de Despacho
    menu = st.sidebar.selectbox("Menú de Navegación", [
        "📊 Dashboard y Stock", 
        "➕ Registrar Productos", 
        "📥 Registrar Entrada", 
        "📤 Registrar Salida", 
        "📄 Generar Guía de Despacho",
        "📜 Historial de Movimientos"
    ])

    # ----------------------------------------------------
    # 1. DASHBOARD Y STOCK CRÍTICO
    # ----------------------------------------------------
    if menu == "📊 Dashboard y Stock":
        st.subheader("📊 Estado General del Inventario")
        if not df_productos.empty:
            stock_critico = df_productos[df_productos["Stock Actual"] <= df_productos["Stock Mínimo (Crítico)"]]
            if not stock_critico.empty:
                st.warning("⚠️ **¡Atención! Hay productos con Stock Crítico o Agotado:**")
                st.dataframe(stock_critico[["Código", "Nombre", "Stock Actual", "Stock Mínimo (Crítico)"]], use_container_width=True)
            else:
                st.success("✅ Todos los niveles de stock se encuentran en rangos seguros.")
            
            st.divider()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Productos", len(df_productos))
            col2.metric("Unidades Totales", int(df_productos["Stock Actual"].sum()))
            valor_total = (df_productos["Stock Actual"] * df_productos["Precio Unitario ($)"]).sum()
            col3.metric("Valor del Inventario", f"${valor_total:,.2f}")
            
            st.subheader("📋 Inventario Actualizado")
            st.dataframe(df_productos, use_container_width=True)
        else:
            st.info("No hay productos registrados todavía.")

    # ----------------------------------------------------
    # 2. REGISTRAR NUEVOS PRODUCTOS
    # ----------------------------------------------------
    elif menu == "➕ Registrar Productos":
        st.subheader("➕ Agregar Nuevo Producto al Sistema")
        with st.form("form_nuevo_prod", clear_on_submit=True):
            codigo = st.text_input("Código o SKU Único")
            nombre = st.text_input("Nombre del Producto")
            categoria = st.selectbox("Categoría", ["Electrónica", "Alimentos", "Ropa", "Hogar", "Herramientas", "Otros"])
            stock_inicial = st.number_input("Stock Inicial", min_value=0, step=1)
            stock_minimo = st.number_input("Stock Mínimo (Alerta de Stock Crítico)", min_value=0, step=1, value=5)
            precio = st.number_input("Precio Unitario ($)", min_value=0.0, format="%.2f")
            btn_crear = st.form_submit_button("Guardar Producto")

            if btn_crear:
                if codigo and nombre:
                    if not df_productos.empty and codigo in df_productos["Código"].values:
                        st.error("❌ El código de producto ya existe.")
                    else:
                        nuevo_prod = pd.DataFrame([{
                            "Código": codigo, "Nombre": nombre, "Categoría": categoria, 
                            "Stock Actual": stock_inicial, "Stock Mínimo (Crítico)": stock_minimo, 
                            "Precio Unitario ($)": precio
                        }])
                        df_productos = pd.concat([df_productos, nuevo_prod], ignore_index=True)
                        guardar_productos(df_productos)
                        st.success(f"¡Producto '{nombre}' registrado con éxito!")
                else:
                    st.error("Por favor completa al menos el Código y el Nombre.")

    # ----------------------------------------------------
    # 3. REGISTRAR ENTRADA
    # ----------------------------------------------------
    elif menu == "📥 Registrar Entrada":
        st.subheader("📥 Registrar Ingreso de Mercadería")
        if df_productos.empty:
            st.warning("Primero debes registrar productos en el sistema.")
        else:
            with st.form("form_entrada", clear_on_submit=True):
                codigo_sel = st.selectbox("Selecciona el Producto", df_productos["Código"] + " - " + df_productos["Nombre"])
                cantidad_entrada = st.number_input("Cantidad a Ingresar", min_value=1, step=1)
                motivo = st.text_input("Motivo de Entrada")
                btn_entrada = st.form_submit_button("Confirmar Entrada")

                if btn_entrada:
                    codigo_limpio = codigo_sel.split(" - ")[0]
                    idx = df_productos[df_productos["Código"] == codigo_limpio].index[0]
                    df_productos.loc[idx, "Stock Actual"] += cantidad_entrada
                    guardar_productos(df_productos)
                    
                    nuevo_mov = pd.DataFrame([{
                        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                        "Código": codigo_limpio, "Producto": df_productos.loc[idx, "Nombre"], 
                        "Tipo": "ENTRADA", "Cantidad": cantidad_entrada, "Motivo": motivo if motivo else "Ingreso general"
                    }])
                    df_movimientos = pd.concat([df_movimientos, nuevo_mov], ignore_index=True)
                    guardar_movimientos(df_movimientos)
                    st.success(f"¡Se sumaron {cantidad_entrada} unidades!")

    # ----------------------------------------------------
    # 4. REGISTRAR SALIDA
    # ----------------------------------------------------
    elif menu == "📤 Registrar Salida":
        st.subheader("📤 Registrar Salida o Venta de Mercadería")
        if df_productos.empty:
            st.warning("No hay productos registrados.")
        else:
            with st.form("form_salida", clear_on_submit=True):
                codigo_sel = st.selectbox("Selecciona el Producto", df_productos["Código"] + " - " + df_productos["Nombre"])
                cantidad_salida = st.number_input("Cantidad a Retirar", min_value=1, step=1)
                motivo = st.text_input("Motivo de Salida (Ej: Venta, despacho)")
                btn_salida = st.form_submit_button("Confirmar Salida")

                if btn_salida:
                    codigo_limpio = codigo_sel.split(" - ")[0]
                    idx = df_productos[df_productos["Código"] == codigo_limpio].index[0]
                    stock_actual = df_productos.loc[idx, "Stock Actual"]
                    
                    if cantidad_salida > stock_actual:
                        st.error(f"❌ Stock insuficiente. Solo hay {stock_actual} disponibles.")
                    else:
                        df_productos.loc[idx, "Stock Actual"] -= cantidad_salida
                        guardar_productos(df_productos)
                        
                        nuevo_mov = pd.DataFrame([{
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                            "Código": codigo_limpio, "Producto": df_productos.loc[idx, "Nombre"], 
                            "Tipo": "SALIDA", "Cantidad": cantidad_salida, "Motivo": motivo if motivo else "Salida general"
                        }])
                        df_movimientos = pd.concat([df_movimientos, nuevo_mov], ignore_index=True)
                        guardar_movimientos(df_movimientos)
                        st.success(f"¡Se retiraron {cantidad_salida} unidades!")

    # ----------------------------------------------------
    # 5. GENERAR GUÍA DE DESPACHO / TRANSPORTE NUEVA
    # ----------------------------------------------------
    elif menu == "📄 Generar Guía de Despacho":
        st.subheader("📄 Generador de Guía de Transporte y Despacho")
        
        if df_productos.empty:
            st.warning("No hay productos en el inventario para despachar.")
        else:
            with st.form("form_guia"):
                st.markdown("### 🏢 Datos de Envío y Destino")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    destinatario = st.text_input("Nombre del Cliente / Destinatario")
                    rut_cliente = st.text_input("RUT / Identificación del Cliente")
                    direccion = st.text_input("Dirección de Destino")
                with col_d2:
                    transportista = st.text_input("Nombre del Transportista / Conductor")
                    patente = st.text_input("Patente / Placa del Vehículo")
                    motivo_traslado = st.selectbox("Motivo del Traslado", ["Venta", "Traslado entre bodegas", "Devolución", "Prestamo"])

                st.markdown("### 📦 Materiales a Despachar")
                
                # Campos dinámicos sencillos para armar la lista de la guía
                items_guia = []
                for i in range(3): # Permite agregar hasta 3 productos en una misma guía de forma rápida
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        prod_sel = st.selectbox(f"Producto #{i+1}", ["-- Seleccionar --"] + list(df_productos["Código"] + " - " + df_productos["Nombre"]), key=f"p_{i}")
                    with c2:
                        cant_sel = st.number_input(f"Cantidad #{i+1}", min_value=0, step=1, key=f"c_{i}")
                    
                    if prod_sel != "-- Seleccionar --" and cant_sel > 0:
                        codigo_p = prod_sel.split(" - ")[0]
                        nombre_p = prod_sel.split(" - ")[1]
                        items_guia.append({"Código": codigo_p, "Producto": nombre_p, "Cantidad": cant_sel})

                btn_generar = st.form_submit_button("Generar Documento de Guía")

            if btn_generar:
                if not destinatario or not direccion:
                    st.error("Por favor completa al menos el Nombre del Cliente y la Dirección de Destino.")
                elif len(items_guia) == 0:
                    st.error("Debes seleccionar al menos un producto con cantidad mayor a 0 para la guía.")
                else:
                    st.success("¡Guía de Despacho generada con éxito!")
                    st.divider()
                    
                    # --- DISEÑO VISUAL DE LA GUÍA LISTA PARA IMPRIMIR ---
                    st.markdown(f"""
                    <div style="border: 2px solid #ccc; padding: 20px; border-radius: 10px; background-color: white; color: black;">
                        <h2 style="text-align: center; color: #333;">GUÍA DE TRANSPORTE Y DESPACHO</h2>
                        <hr>
                        <p><b>Fecha de Emisión:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                        <p><b>Motivo del Traslado:</b> {motivo_traslado}</p>
                        <br>
                        <h4>📍 Datos del Destinatario:</h4>
                        <p><b>Cliente:</b> {destinatario} | <b>RUT/ID:</b> {rut_cliente}</p>
                        <p><b>Dirección de Entrega:</b> {direccion}</p>
                        <br>
                        <h4>🚚 Datos del Transporte:</h4>
                        <p><b>Transportista:</b> {transportista} | <b>Patente Vehículo:</b> {patente}</p>
                        <br>
                        <h4>📋 Detalle de Materiales:</h4>
                    """, unsafe_allow_html=True)

                    df_guia = pd.DataFrame(items_guia)
                    st.dataframe(df_guia, use_container_width=True)

                    st.markdown(f"""
                        <br><br>
                        <div style="display: flex; justify-content: space-between; margin-top: 50px;">
                            <div style="border-top: 1px solid black; width: 200px; text-align: center;">Firma Emisor</div>
                            <div style="border-top: 1px solid black; width: 200px; text-align: center;">Firma Conductor (Recibi Conforme)</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.info("💡 **Consejo:** Para imprimir esta guía en papel o guardarla como PDF, presiona las teclas `Ctrl + P` (o `Cmd + P` en Mac) en tu teclado y selecciona 'Guardar como PDF'.")

    # ----------------------------------------------------
    # 6. HISTORIAL DE MOVIMIENTOS
    # ----------------------------------------------------
    elif menu == "📜 Historial de Movimientos":
        st.subheader("📜 Bitácora de Entradas y Salidas")
        if not df_movimientos.empty:
            st.dataframe(df_movimientos.sort_values(by="Fecha", ascending=False), use_container_width=True)
            csv_mov = df_movimientos.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Historial en CSV", 
                data=csv_mov, 
                file_name="historial_movimientos.csv", 
                mime="text/csv"
            )
        else:
            st.info("Aún no se han registrado entradas ni salidas.")
