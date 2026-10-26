import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 1. Configuración de la página (debe ser lo primero de Streamlit)
st.set_page_config(page_title="Control de Inventario", page_icon="📦", layout="wide")

# 2. Inicializar el estado de autenticación en la sesión
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# 3. Función de la pantalla de Login
def mostrar_login():
    st.subheader("🔐 Iniciar Sesión - Control de Inventario")
    
    # Credenciales de ejemplo (puedes modificarlas o ampliarlas)
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
                st.rerun() # Recarga la app para mostrar el sistema principal
            else:
                st.error("Usuario o contraseña incorrectos")

# 4. Control de flujo: Si no está autenticado, muestra el login; si lo está, muestra la app
if not st.session_state.autenticado:
    mostrar_login()
else:
    # --- SISTEMA PRINCIPAL DE INVENTARIO ---
    
    # Botón y datos de usuario en la barra lateral
    st.sidebar.write(f"👤 Conectado como: **{st.session_state.usuario_actual}**")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    st.title("📦 Sistema de Control de Inventario: Entradas, Salidas y Stock Crítico")

    # Archivos CSV para guardar la información por separado
    FILE_PRODUCTOS = "productos.csv"
    FILE_MOVIMIENTOS = "movimientos.csv"

    # Funciones para cargar y guardar datos
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

    # Cargar datos actuales
    df_productos = cargar_productos()
    df_movimientos = cargar_movimientos()

    # Menú de navegación lateral
    menu = st.sidebar.selectbox("Menú de Navegación", [
        "📊 Dashboard y Stock", 
        "➕ Registrar Productos", 
        "📥 Registrar Entrada", 
        "📤 Registrar Salida", 
        "📜 Historial de Movimientos"
    ])

    # ----------------------------------------------------
    # 1. DASHBOARD Y STOCK CRÍTICO
    # ----------------------------------------------------
    if menu == "📊 Dashboard y Stock":
        st.subheader("📊 Estado General del Inventario")
        if not df_productos.empty:
            # Alerta de Stock Crítico
            stock_critico = df_productos[df_productos["Stock Actual"] <= df_productos["Stock Mínimo (Crítico)"]]
            if not stock_critico.empty:
                st.warning("⚠️ **¡Atención! Hay productos con Stock Crítico o Agotado:**")
                st.dataframe(stock_critico[["Código", "Nombre", "Stock Actual", "Stock Mínimo (Crítico)"]], use_container_width=True)
            else:
                st.success("✅ Todos los niveles de stock se encuentran en rangos seguros.")
            
            st.divider()
            
            # Métricas principales
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Productos", len(df_productos))
            col2.metric("Unidades Totales", int(df_productos["Stock Actual"].sum()))
            valor_total = (df_productos["Stock Actual"] * df_productos["Precio Unitario ($)"]).sum()
            col3.metric("Valor del Inventario", f"${valor_total:,.2f}")
            
            st.subheader("📋 Inventario Actualizado")
            st.dataframe(df_productos, use_container_width=True)
        else:
            st.info("No hay productos registrados todavía. Ve a 'Registrar Productos' para empezar.")

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
                        st.error("❌ El código de producto ya existe. Utiliza uno diferente.")
                    else:
                        nuevo_prod = pd.DataFrame([{
                            "Código": codigo, 
                            "Nombre": nombre, 
                            "Categoría": categoria, 
                            "Stock Actual": stock_inicial, 
                            "Stock Mínimo (Crítico)": stock_minimo, 
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
                motivo = st.text_input("Motivo de Entrada (Ej: Compra a proveedor, devolución)")
                btn_entrada = st.form_submit_button("Confirmar Entrada")

                if btn_entrada:
                    codigo_limpio = codigo_sel.split(" - ")[0]
                    idx = df_productos[df_productos["Código"] == codigo_limpio].index[0]
                    
                    # Actualizar stock
                    df_productos.loc[idx, "Stock Actual"] += cantidad_entrada
                    guardar_productos(df_productos)
                    
                    # Registrar movimiento
                    nuevo_mov = pd.DataFrame([{
                        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                        "Código": codigo_limpio, 
                        "Producto": df_productos.loc[idx, "Nombre"], 
                        "Tipo": "ENTRADA", 
                        "Cantidad": cantidad_entrada, 
                        "Motivo": motivo if motivo else "Ingreso general"
                    }])
                    df_movimientos = pd.concat([df_movimientos, nuevo_mov], ignore_index=True)
                    guardar_movimientos(df_movimientos)
                    st.success(f"¡Se sumaron {cantidad_entrada} unidades al producto '{df_productos.loc[idx, 'Nombre']}'!")

    # ----------------------------------------------------
    # 4. REGISTRAR SALIDA
    # ----------------------------------------------------
    elif menu == "📤 Registrar Salida":
        st.subheader("📤 Registrar Salida o Venta de Mercadería")
        if df_productos.empty:
            st.warning("No hay productos registrados en el inventario.")
        else:
            with st.form("form_salida", clear_on_submit=True):
                codigo_sel = st.selectbox("Selecciona el Producto", df_productos["Código"] + " - " + df_productos["Nombre"])
                cantidad_salida = st.number_input("Cantidad a Retirar", min_value=1, step=1)
                motivo = st.text_input("Motivo de Salida (Ej: Venta, merma, uso interno)")
                btn_salida = st.form_submit_button("Confirmar Salida")

                if btn_salida:
                    codigo_limpio = codigo_sel.split(" - ")[0]
                    idx = df_productos[df_productos["Código"] == codigo_limpio].index[0]
                    stock_actual = df_productos.loc[idx, "Stock Actual"]
                    
                    if cantidad_salida > stock_actual:
                        st.error(f"❌ Stock insuficiente. Solo hay {stock_actual} unidades disponibles.")
                    else:
                        # Actualizar stock
                        df_productos.loc[idx, "Stock Actual"] -= cantidad_salida
                        guardar_productos(df_productos)
                        
                        # Registrar movimiento
                        nuevo_mov = pd.DataFrame([{
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                            "Código": codigo_limpio, 
                            "Producto": df_productos.loc[idx, "Nombre"], 
                            "Tipo": "SALIDA", 
                            "Cantidad": cantidad_salida, 
                            "Motivo": motivo if motivo else "Salida general"
                        }])
                        df_movimientos = pd.concat([df_movimientos, nuevo_mov], ignore_index=True)
                        guardar_movimientos(df_movimientos)
                        st.success(f"¡Se retiraron {cantidad_salida} unidades del producto '{df_productos.loc[idx, 'Nombre']}'!")

    # ----------------------------------------------------
    # 5. HISTORIAL DE MOVIMIENTOS
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
