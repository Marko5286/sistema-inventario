from datetime import datetime
import pytz
import streamlit as st

# --- CONFIGURACIÓN DE PÁGINA O MENÚ ---
st.title("📦 ERP Marklogistic")
st.subheader("📷 Salida de Material con Capturadora de Código de Barras")

# Inicializar inventario de prueba en la sesión si no existe
if "inventario" not in st.session_state:
  st.session_state.inventario = {
      "SKU-1001": {"nombre": "Caja Cartón Grande", "stock": 50},
      "SKU-1002": {"nombre": "Pallet Madera Estándar", "stock": 20},
      "SKU-1003": {"nombre": "Cinta Embalaje 45m", "stock": 100},
  }

# Inicializar datos del cliente y carrito de salida
if "cliente_actual" not in st.session_state:
  st.session_state.cliente_actual = ""
if "carrito_salida" not in st.session_state:
  st.session_state.carrito_salida = []

# --- 1. DATOS GENERALES DEL DESPACHO ---
col_c1, col_c2 = st.columns(2)
with col_c1:
  st.session_state.cliente_actual = st.text_input(
      "Cliente / Destinatario",
      value=st.session_state.cliente_actual,
      placeholder="Ej: Comercial del Norte SpA",
  )
with col_c2:
  motivo_traslado = st.selectbox(
      "Motivo del Traslado",
      ["Venta", "Traspaso entre bodegas", "Devolución", "Muestras"],
  )

st.divider()

# --- 2. CAMPO PARA LA CAPTURADORA DE CÓDIGO DE BARRAS ---
st.markdown("### 🎯 Escanear Producto")
st.caption(
    "Haz clic en el cuadro de abajo y dispara la capturadora sobre el código de"
    " barra."
)


# Función que se ejecuta automáticamente cuando la capturadora presiona ENTER
def procesar_escaneo():
  codigo_leido = st.session_state.codigo_capturado.strip()

  if codigo_leido:
    # Verificar si el SKU existe en el inventario
    if codigo_leido in st.session_state.inventario:
      prod = st.session_state.inventario[codigo_leido]

      if prod["stock"] > 0:
        # Agregar al carrito temporal
        st.session_state.carrito_salida.append({
            "sku": codigo_leido,
            "nombre": prod["nombre"],
            "cantidad": 1,
        })
        st.toast(
            f"✅ Capurado: {prod['nombre']} ({codigo_leido})", icon="📦"
        )
      else:
        st.error(f"❌ El producto {codigo_leido} no tiene stock disponible.")
    else:
      st.warning(f"⚠️ El código {codigo_leido} no existe en la base de datos.")

    # Limpiar el campo para la siguiente lectura automática
    st.session_state.codigo_capturado = ""


# Campo de texto donde la capturadora "escribe" el código
st.text_input(
    "Lector de Código de Barras / QR",
    key="codigo_capturado",
    on_change=procesar_escaneo,
    placeholder="Pistola lista para escanear...",
)

# --- 3. TABLA CON PRODUCTOS ESCANNEADOS ---
if st.session_state.carrito_salida:
  st.markdown("#### Lista de Ítems a Despachar")

  # Mostrar la lista de ítems capturados
  for idx, item in enumerate(st.session_state.carrito_salida):
    col_i1, col_i2, col_i3 = st.columns([2, 4, 2])
    col_i1.write(f"**SKU:** {item['sku']}")
    col_i2.write(f"**Producto:** {item['nombre']}")
    col_i3.write(f"**Cant:** {item['cantidad']} ud.")

  st.divider()

  # --- 4. CONFIRMAR SALIDA Y GENERAR GUÍA ---
  if st.button("🚀 Confirmar Salida y Generar Guía de Despacho"):
    if not st.session_state.cliente_actual:
      st.error(
          "⚠️ Ingresa el nombre del cliente antes de confirmar la salida."
      )
    else:
      # Descontar stock real
      for item in st.session_state.carrito_salida:
        st.session_state.inventario[item["sku"]]["stock"] -= item["cantidad"]

      # Fecha y hora oficial de Chile
      zona_cl = pytz.timezone("America/Santiago")
      fecha_guia_str = datetime.now(zona_cl).strftime("%d/%m/%Y %H:%M:%S")
      folio_guia = f"GD-2026-{datetime.now().strftime('%H%M%S')}"

      # Guardar la guía generada
      st.session_state.guia_activa = {
          "folio": folio_guia,
          "fecha": fecha_guia_str,
          "cliente": st.session_state.cliente_actual,
          "motivo": motivo_traslado,
          "items": list(st.session_state.carrito_salida),
      }

      # Limpiar carrito
      st.session_state.carrito_salida = []
      st.success("¡Salida registrada y stock actualizado correctamente!")
      st.rerun()

# --- 5. MOSTRAR LA GUÍA DE DESPACHO EN PANTALLA ---
if "guia_activa" in st.session_state:
  g = st.session_state.guia_activa

  st.divider()
  st.markdown("### 📄 Guía de Despacho Generada")

  # Construir filas HTML dinámicas para cada producto capturado
  filas_html = ""
  for item in g["items"]:
    filas_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{item['sku']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{item['nombre']}</td>
            <td style="padding: 8px; text-align: right; border-bottom: 1px solid #eee;"><b>{item['cantidad']}</b></td>
        </tr>
        """

  # Render del documento
  st.markdown(
      f"""
    <div style="border: 2px solid #ccc; padding: 25px; border-radius: 10px; background-color: white; color: black; font-family: sans-serif;">
        <h2 style="text-align: center; color: #1f77b4; margin-bottom: 0;">MARKLOGISTIC ERP</h2>
        <p style="text-align: center; color: #555; font-size: 13px; margin-top: 5px;">GUÍA DE TRANSPORTE Y DESPACHO DE BODEGA</p>
        <hr style="border: 1px solid #ddd;">
        
        <table style="width: 100%; font-size: 14px; margin-bottom: 15px;">
            <tr>
                <td style="width: 50%;"><b>N° de Guía / Folio:</b> {g['folio']}</td>
                <td><b>Fecha y Hora (Chile):</b> {g['fecha']}</td>
            </tr>
            <tr>
                <td><b>Cliente:</b> {g['cliente']}</td>
                <td><b>Motivo:</b> {g['motivo']}</td>
            </tr>
        </table>
        
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <tr style="background-color: #f8f9fa; border-bottom: 2px solid #dee2e6;">
                <th style="padding: 8px; text-align: left;">SKU</th>
                <th style="padding: 8px; text-align: left;">Descripción</th>
                <th style="padding: 8px; text-align: right;">Cantidad</th>
            </tr>
            {filas_html}
        </table>
        
        <p style="font-size: 11px; color: #777; text-align: center; margin-top: 25px;">
            Comprobante oficial emitido por el sistema de gestión de bodegas Marklogistic.
        </p>
    </div>
    """,
      unsafe_allow_html=True,
  )

  col_b1, col_b2 = st.columns(2)
  with col_b1:
    if st.button("🖨️ Imprimir / PDF"):
      st.info("Presiona **Ctrl + P** para guardar o imprimir.")
  with col_b2:
    if st.button("🔄 Nueva Lectura"):
      del st.session_state.guia_activa
      st.rerun()
