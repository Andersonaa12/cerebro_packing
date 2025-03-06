import math
import os
import subprocess
import tempfile
import requests
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
import json
import winsound  # Para reproducir sonidos de alerta en Windows

import win32api
import win32print

from PIL import Image, ImageTk
from io import BytesIO

# Ajusta las rutas a tu proyecto real
from config.settings import API_BASE_URL
from services.api_routes import API_ROUTES
from components.barcode_widget import create_barcode_widget
from assets.css.styles import PRIMARY_COLOR, BACKGROUND_COLOR_VIEWS, LABEL_STYLE, BUTTON_STYLE


JSON_CONFIG_FILE = "printer_config.json"


def load_printer_config():
    """
    Carga la impresora seleccionada desde un archivo JSON.
    Estructura esperada:
    {
        "selected_printer": "NombreDeLaImpresora"
    }
    """
    if not os.path.exists(JSON_CONFIG_FILE):
        return None

    try:
        with open(JSON_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("selected_printer", None)
    except Exception as e:
        print(f"Error al cargar la impresora desde {JSON_CONFIG_FILE}: {e}")
        return None


class PackingShowView(tk.Frame):
    """
    Vista de Packing con una organización en 2 filas (arriba/abajo) y varias columnas.
    Arriba:
      - Esquina sup. izq.: "Información del Proceso" + "Información del Pedido" (en formato de dos columnas).
      - Esquina sup. der.: Campo de escaneo (SKU/BarCode).
    Abajo:
      - Izquierda: Tabla de productos por escanear (1/3 del ancho)
      - Derecha: Órdenes confirmadas (2/3 del ancho).
    
    Lógica:
      - Escaneo de productos (cuando se completa la cantidad de todos los productos,
        se confirma automáticamente la orden y pasa a la siguiente).
      - Doble clic en producto => muestra detalle (placeholder).
      - Doble clic en orden confirmada => muestra detalle.
      - Beep solo en error (producto que no pertenece, etc.).
      - Se elimina la lógica de "etiqueta de envío" para agilizar el flujo.
    """
    def __init__(self, master=None, process_id=None, login_controller=None, on_back=None):
        super().__init__(master, bg="white")
        self.master = master
        self.process_id = process_id
        self.login_controller = login_controller
        self.on_back = on_back

        # Carga impresora seleccionada o default
        self.selected_printer = load_printer_config() or win32print.GetDefaultPrinter()
        print(f"[DEBUG] Impresora inicial (PackingShowView): {self.selected_printer}")

        # Variables de estado
        self.pending_process_order = None   # Orden actual
        self.current_order_products = []    # Productos del pedido actual
        self.scanned_quantities = {}        # { product_id: {"scanned", "required", "row_id", "sku", "bar_code"} }
        self.confirmed_orders_data = []     # Lista de órdenes confirmadas
        self.total_orders_count = 0         # Cantidad total de pedidos en este packing
        self.completed_orders_count = 0     # Cuántas ya finalizadas

        # Tabla de órdenes confirmadas config
        self.page_size = 10
        self.current_page = 1
        self.total_pages = 1
        self.sort_directions = {}

        # Para que la imagen no sea recolectada (si en algún momento se usa)
        self.product_image_tk = None

        # Construye la interfaz
        self.create_widgets()
        # Carga datos iniciales
        self.fetch_process_detail()

    # --------------------------------------------------------------------------
    # Creación de widgets y distribución visual
    # --------------------------------------------------------------------------
    def create_widgets(self):
        """
        Layout:
          - Encabezado (barra naranja superior)
          - top_frame (Info Proceso + Info Pedido + Campo Escaneo)
          - bottom_frame (Tabla de Productos a la izq. y Órdenes Confirmadas a la der.)
        """
        self.create_header()

        # Frame superior (info proceso, info pedido, campo escaneo)
        top_frame = tk.Frame(self, bg="white", bd=1, relief="solid")
        top_frame.pack(fill="x", padx=10, pady=5)

        # Frame para la información principal (proceso + pedido) en 2 columnas, parte superior izq
        info_frame = tk.Frame(top_frame, bg="white")
        info_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        # "Información del Proceso" (fila 0, col 0)
        self.process_info_frame = tk.Frame(info_frame, bg="white")
        self.process_info_frame.grid(row=0, column=0, sticky="nw", padx=5, pady=5)

        # "Información del Pedido" (fila 0, col 1)
        self.order_info_frame = tk.Frame(info_frame, bg="white", bd=1, relief="solid")
        self.order_info_frame.grid(row=0, column=1, sticky="nw", padx=5, pady=5)

        # Crea paneles
        self.create_process_info_panel(self.process_info_frame)
        self.create_current_order_info_panel(self.order_info_frame)

        # Frame superior derecho (campo de escaneo)
        scan_frame = tk.Frame(top_frame, bg="white", bd=1, relief="solid")
        scan_frame.pack(side="right", fill="y", padx=5, pady=5)
        self.create_scan_panel(scan_frame)

        # Frame inferior
        bottom_frame = tk.Frame(self, bg="white", bd=1, relief="solid")
        bottom_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Izquierda => Tabla de productos
        self.products_frame = tk.Frame(bottom_frame, bg="white")
        self.products_frame.pack(side="left", fill="both", expand=False, padx=5, pady=5)
        self.create_products_table_panel(self.products_frame)

        # Derecha => Órdenes confirmadas
        self.confirmed_orders_frame = tk.Frame(bottom_frame, bg="white", bd=1, relief="solid")
        self.confirmed_orders_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.create_confirmed_orders_table()

    def create_header(self):
        """
        Barra de encabezado superior con título y botón "Devolver".
        """
        header_frame = tk.Frame(self, bg=PRIMARY_COLOR)
        header_frame.pack(fill="x", padx=10, pady=5)

        title_lbl = tk.Label(
            header_frame,
            text="Detalle del Proceso - Packing",
            font=("Arial", 16, "bold"),
            bg=PRIMARY_COLOR,
            fg="white"
        )
        title_lbl.pack(side="left", padx=5)

        btn_container = tk.Frame(header_frame, bg=PRIMARY_COLOR, padx=5, pady=5)
        btn_container.pack(side="right", padx=2, pady=2)

        back_btn = tk.Button(
            btn_container,
            text="Devolver",
            command=self.on_back_button,
            **BUTTON_STYLE
        )
        back_btn.pack()

    def create_process_info_panel(self, container):
        """
        Info del Proceso (Nombre, Iniciado, Finalizado, Creador).
        """
        tk.Label(container, text="Información del Proceso", font=("Arial", 14, "bold"), fg=PRIMARY_COLOR).pack(pady=5)

        self.lbl_nombre = tk.Label(container, text="Nombre: -", font=("Arial", 12), bg="white")
        self.lbl_nombre.pack(anchor="w", pady=2)

        self.lbl_iniciado = tk.Label(container, text="Iniciado: -", font=("Arial", 12), bg="white")
        self.lbl_iniciado.pack(anchor="w", pady=2)

        self.lbl_finalizado = tk.Label(container, text="Finalizado: -", font=("Arial", 12), bg="white")
        self.lbl_finalizado.pack(anchor="w", pady=2)

        self.lbl_creado_por = tk.Label(container, text="Creado por: -", font=("Arial", 12), bg="white")
        self.lbl_creado_por.pack(anchor="w", pady=2)

    def create_current_order_info_panel(self, container):
        """
        Info del Pedido Actual (ID, Cliente, Dirección, etc.) en 2 columnas (grid)
        """
        tk.Label(container, text="Información del Pedido Actual", font=("Arial", 14, "bold"), fg=PRIMARY_COLOR).pack(pady=5)

        content_frame = tk.Frame(container, bg="white")
        content_frame.pack(fill="x", padx=5, pady=5)

        row_idx = 0
        # Creamos las labels y las ubicamos en 2 columnas
        self.lbl_order_id = tk.Label(content_frame, text="Pedido ID: -", font=("Arial", 12), bg="white")
        self.lbl_order_id.grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        self.lbl_order_name = tk.Label(content_frame, text="Cliente: -", font=("Arial", 12), bg="white")
        self.lbl_order_name.grid(row=row_idx, column=1, sticky="w", padx=5, pady=2)
        row_idx += 1

        self.lbl_order_address = tk.Label(content_frame, text="Dirección: -", font=("Arial", 12), bg="white")
        self.lbl_order_address.grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        self.lbl_order_city = tk.Label(content_frame, text="Ciudad: -", font=("Arial", 12), bg="white")
        self.lbl_order_city.grid(row=row_idx, column=1, sticky="w", padx=5, pady=2)
        row_idx += 1

        self.lbl_order_province = tk.Label(content_frame, text="Provincia: -", font=("Arial", 12), bg="white")
        self.lbl_order_province.grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        self.lbl_order_zip = tk.Label(content_frame, text="C.P.: -", font=("Arial", 12), bg="white")
        self.lbl_order_zip.grid(row=row_idx, column=1, sticky="w", padx=5, pady=2)
        row_idx += 1

        self.lbl_order_country = tk.Label(content_frame, text="País: -", font=("Arial", 12), bg="white")
        self.lbl_order_country.grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        self.lbl_shipping_method = tk.Label(
            content_frame,
            text="Método de envío: -",
            font=("Arial", 14, "bold"),
            fg="red",
            bg="white"
        )
        self.lbl_shipping_method.grid(row=row_idx, column=1, sticky="w", padx=5, pady=2)

    def create_scan_panel(self, container):
        """
        Esquina superior derecha: Campo de escaneo (SKU/barcode).
        """
        tk.Label(container, text="Escanear (SKU - Cod.barras): ", font=("Arial", 14, "bold"), fg=PRIMARY_COLOR).pack(pady=5)

        scan_frame = tk.Frame(container, bg="white")
        scan_frame.pack(fill="both", expand=True, padx=5, pady=5)

        lbl_barcode = tk.Label(scan_frame, text="Código de Barras:", font=("Arial", 12), bg="white")
        lbl_barcode.pack(side="left", padx=5)

        self.entry_barcode = tk.Entry(scan_frame, font=("Arial", 12))
        self.entry_barcode.pack(side="left", padx=5, fill="x", expand=True)
        self.entry_barcode.bind("<Return>", self.on_barcode_enter)

        self.lbl_scan_message = tk.Label(scan_frame, text="", font=("Arial", 12), bg="white", fg="blue")
        self.lbl_scan_message.pack(side="left", padx=5)

    def create_products_table_panel(self, container):
        """
        Tabla de productos (1/3 ancho) en la parte inferior izquierda.
        Doble clic en producto => ver detalle.
        """
        tk.Label(container, text="Productos por Escanear", font=("Arial", 14, "bold"), bg="white").pack(pady=5)

        columns = ("Imagen", "Nombre", "SKU", "Cantidad")
        self.current_order_tree = ttk.Treeview(
            container,
            columns=columns,
            show="headings",
            height=15
        )
        self.current_order_tree.heading("Imagen", text="Imagen")
        self.current_order_tree.heading("Nombre", text="Nombre")
        self.current_order_tree.heading("SKU", text="SKU")
        self.current_order_tree.heading("Cantidad", text="Escaneados/Total")

        # Ajustar columnas
        self.current_order_tree.column("Imagen", width=80, anchor="center")
        self.current_order_tree.column("Nombre", width=150, anchor="center")
        self.current_order_tree.column("SKU", width=120, anchor="center")
        self.current_order_tree.column("Cantidad", width=100, anchor="center")

        # Colores
        self.current_order_tree.tag_configure("pending", background="white")
        self.current_order_tree.tag_configure("partial", background="orange")
        self.current_order_tree.tag_configure("complete", background="lightgreen")

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.current_order_tree.yview)
        self.current_order_tree.configure(yscrollcommand=scroll.set)

        self.current_order_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")

        # Doble clic en un producto
        self.current_order_tree.bind("<Double-1>", self.on_product_double_click)

    def create_confirmed_orders_table(self):
        """
        Parte inferior derecha: Órdenes confirmadas + paginación
        """
        tk.Label(
            self.confirmed_orders_frame,
            text="Órdenes Confirmadas",
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=5)

        self.lbl_orders_counter = tk.Label(
            self.confirmed_orders_frame,
            text="Pedidos completados: 0/0",
            font=("Arial", 12, "bold"),
            bg="white"
        )
        self.lbl_orders_counter.pack()

        columns = ("Orden #", "Productos", "Inicio", "Fin", "Acciones")
        self.confirmed_tree = ttk.Treeview(
            self.confirmed_orders_frame,
            columns=columns,
            show="headings"
        )
        for col in columns:
            self.confirmed_tree.heading(
                col,
                text=col,
                command=lambda _col=col: self.sort_column(_col, False)
            )
            self.confirmed_tree.column(col, anchor="center", width=140)
            self.sort_directions[col] = False

        scrollbar = ttk.Scrollbar(self.confirmed_orders_frame, orient="vertical", command=self.confirmed_tree.yview)
        self.confirmed_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.confirmed_tree.pack(expand=True, fill="both")

        self.confirmed_tree.bind("<Double-1>", self.on_confirmed_order_double_click)

        # Paginación
        pag_frame = tk.Frame(self.confirmed_orders_frame, bg="white")
        pag_frame.pack(fill="x", padx=10, pady=5)

        prev_btn = tk.Button(pag_frame, text="Anterior", command=self.previous_page, **BUTTON_STYLE)
        prev_btn.pack(side="left", padx=5)

        self.lbl_page_info = tk.Label(pag_frame, text="", font=("Arial", 12), bg="white")
        self.lbl_page_info.pack(side="left", padx=5)

        next_btn = tk.Button(pag_frame, text="Siguiente", command=self.next_page, **BUTTON_STYLE)
        next_btn.pack(side="left", padx=5)

    # --------------------------------------------------------------------------
    # Botón "Devolver"
    # --------------------------------------------------------------------------
    def on_back_button(self):
        if self.on_back:
            self.on_back()
        else:
            self.destroy()

    # --------------------------------------------------------------------------
    # Fetch data & Update UI
    # --------------------------------------------------------------------------
    def fetch_process_detail(self):
        """
        Llama al endpoint PACKING_VIEW para obtener info del proceso,
        setea la orden pendiente y refresca la interfaz.
        """
        endpoint = API_ROUTES["PACKING_VIEW"].format(id=self.process_id)
        response = self.login_controller.api_client._make_get_request(endpoint)
        if not response or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener el detalle del proceso de Packing.")
            return

        data = response.get("data", {})
        process = data.get("process", {})

        # Info general del proceso
        self.lbl_nombre.config(text=f"Nombre: {process.get('name', 'N/A')}")
        self.lbl_iniciado.config(text=f"Iniciado: {process.get('started_at', 'N/A')}")
        finished_at = process.get("finished_at")
        fin_text = finished_at if finished_at else "En Proceso"
        self.lbl_finalizado.config(text=f"Finalizado: {fin_text}")

        creador = process.get("created_by", "N/A")
        if isinstance(creador, dict):
            creador = creador.get("name", "N/A")
        self.lbl_creado_por.config(text=f"Creado por: {creador}")

        # Órdenes confirmadas
        confirmed_orders = data.get("confirmedOrders", {})
        self.update_confirmed_orders_table(confirmed_orders)

        # Cantidad total de pedidos
        packing_orders = process.get("packing_process_orders", [])
        self.total_orders_count = len(packing_orders)

        # Cuántos finalizados
        finished_list = [po for po in packing_orders if po.get("finished_at")]
        self.completed_orders_count = len(finished_list)

        # Si ya está todo finalizado
        all_finished = (len(packing_orders) > 0 and all(o.get("finished_at") for o in packing_orders))
        if finished_at or all_finished:
            # Bloqueamos y limpiamos
            self.pending_process_order = None
            self.clear_current_order_table()
            self.lbl_order_id.config(text="Pedido ID: -- (Finalizado)")
            self.lbl_shipping_method.config(text="Método de envío: -- (Finalizado)", fg="black")
            self.entry_barcode.config(state="disabled")
            self.refresh_orders_counter_label()
            return

        # Buscamos la orden pendiente
        self.pending_process_order = data.get("pendingProcessOrder")
        if not self.pending_process_order:
            # Fallback: primer pedido no finalizado
            not_finished = [po for po in packing_orders if not po.get("finished_at")]
            if not_finished:
                self.pending_process_order = not_finished[0]

        if not self.pending_process_order:
            # No hay pedido pendiente
            self.clear_current_order_table()
            self.refresh_orders_counter_label()
            return

        # Info del pedido actual
        order_data = self.pending_process_order.get("order", {})
        self.lbl_order_id.config(text=f"Pedido ID: {order_data.get('id', '')}")
        self.lbl_order_name.config(text=f"Cliente: {order_data.get('name', '')}")

        address_line = order_data.get("address", "")
        address_line_2 = order_data.get("address_2", "")
        if address_line_2:
            address_line += f" / {address_line_2}"
        self.lbl_order_address.config(text=f"Dirección: {address_line}")
        self.lbl_order_city.config(text=f"Ciudad: {order_data.get('city', '')}")
        self.lbl_order_province.config(text=f"Provincia: {order_data.get('province', '')}")
        self.lbl_order_zip.config(text=f"C.P.: {order_data.get('zip', '')}")
        self.lbl_order_country.config(text=f"País: {order_data.get('country_code', '')}")

        shipping_method = order_data.get("shipping_method_name", "N/A")
        self.lbl_shipping_method.config(text=f"Método de envío: {shipping_method}", fg="red")

        # Reiniciamos escaneos
        self.scanned_quantities = {}

        # Cargamos productos
        self.current_order_products = self.pending_process_order.get("packing_process_order_product", [])
        self.populate_current_order_products_table()

        # Habilitamos entry de escaneo
        self.entry_barcode.config(state="normal")
        self.entry_barcode.delete(0, tk.END)
        self.entry_barcode.focus()

        # Actualizamos contadores
        self.refresh_orders_counter_label()

    # --------------------------------------------------------------------------
    # Tabla de productos
    # --------------------------------------------------------------------------
    def clear_current_order_table(self):
        for row in self.current_order_tree.get_children():
            self.current_order_tree.delete(row)

    def populate_current_order_products_table(self):
        """
        Llena la tabla con la lista de productos.
        """
        self.clear_current_order_table()
        for line in self.current_order_products:
            product_data = line.get("product", {})
            p_id = product_data.get("id")
            p_name = product_data.get("name", "")
            p_sku = product_data.get("sku", "")
            p_bar = product_data.get("bar_code", "")
            p_qty = line.get("quantity", 0)

            row_id = self.current_order_tree.insert(
                "",
                "end",
                values=("No Img", p_name, p_sku, f"0/{p_qty}"),
                tags=("pending",)
            )
            self.scanned_quantities[p_id] = {
                "scanned": 0,
                "required": p_qty,
                "row_id": row_id,
                "sku": p_sku,
                "bar_code": p_bar
            }

    # --------------------------------------------------------------------------
    # Escaneo
    # --------------------------------------------------------------------------
    def on_barcode_enter(self, event):
        scanned_code = self.entry_barcode.get().strip()
        self.entry_barcode.delete(0, tk.END)

        if not self.pending_process_order:
            return

        # Buscar producto
        matched_id = self.find_product_id_by_scan(scanned_code)
        if matched_id is None:
            # Error
            self.play_error_sound()
            self.lbl_scan_message.config(text="Producto NO pertenece al pedido.", fg="red")
            return

        info = self.scanned_quantities.get(matched_id)
        if not info:
            self.play_error_sound()
            self.lbl_scan_message.config(text="Error interno al escanear.", fg="red")
            return

        # Verificar sobre-escaneo
        if info["scanned"] >= info["required"]:
            self.play_error_sound()
            self.lbl_scan_message.config(text="Este producto ya está completo.", fg="red")
            return

        # Correcto => aumentar
        info["scanned"] += 1
        self.update_product_row(matched_id)

        # Sin beep => escaneo correcto
        self.lbl_scan_message.config(text="")

        # Si se han completado todos => confirmamos y pasamos al siguiente
        if self.all_products_complete():
            self.confirm_current_order()

    def find_product_id_by_scan(self, scanned_code):
        """
        Retorna product_id si coincide con bar_code o sku, None si no existe.
        """
        for p_id, info in self.scanned_quantities.items():
            bar_code = info.get("bar_code", "")
            sku = info.get("sku", "")

            if bar_code and scanned_code == bar_code:
                return p_id
            if scanned_code == sku:
                return p_id
        return None

    def update_product_row(self, product_id):
        info = self.scanned_quantities.get(product_id)
        if not info:
            return

        row_id = info["row_id"]
        scanned = info["scanned"]
        required = info["required"]

        old_vals = self.current_order_tree.item(row_id, "values")
        new_col = f"{scanned}/{required}"
        new_values = (old_vals[0], old_vals[1], old_vals[2], new_col)

        if scanned == 0:
            tag = "pending"
        elif scanned < required:
            tag = "partial"
        else:
            tag = "complete"

        self.current_order_tree.item(row_id, values=new_values, tags=(tag,))

    def all_products_complete(self):
        """
        True si scanned >= required para todos.
        """
        for _, info in self.scanned_quantities.items():
            if info["scanned"] < info["required"]:
                return False
        return True

    def play_error_sound(self):
        winsound.Beep(1000, 300)

    # --------------------------------------------------------------------------
    # Doble clic en un producto => placeholder de detalle
    # --------------------------------------------------------------------------
    def on_product_double_click(self, event):
        """
        Cuando se hace doble clic en un producto de la tabla,
        mostramos un placeholder con info del producto.
        """
        try:
            item_id = self.current_order_tree.selection()[0]
        except IndexError:
            return

        values = self.current_order_tree.item(item_id, "values")
        # (Imagen, Nombre, SKU, 0/2)
        product_name = values[1]
        product_sku = values[2]
        quantity_text = values[3]

        detail_text = f"Producto: {product_name}\nSKU: {product_sku}\nCantidad: {quantity_text}\n\n(Detalle extra...)"

        top = tk.Toplevel(self)
        top.title(f"Detalle del Producto: {product_name}")

        text = tk.Text(top, wrap="word", font=("Arial", 12))
        text.insert("1.0", detail_text)
        text.config(state="disabled")
        text.pack(expand=True, fill="both", padx=10, pady=10)

        btn_close = tk.Button(top, text="Cerrar", command=top.destroy, **BUTTON_STYLE)
        btn_close.pack(pady=5)

    # --------------------------------------------------------------------------
    # Confirmar automáticamente la orden
    # --------------------------------------------------------------------------
    def confirm_current_order(self):
        """
        Llama al endpoint PACKING_CONFIRM en cuanto se completan todos los productos
        y pasa a la siguiente orden.
        """
        if not self.pending_process_order:
            return

        order_id = self.pending_process_order.get("id")
        endpoint = API_ROUTES["PACKING_CONFIRM"].format(
            packingProcessOrder_id=order_id,
            packingProcess_id=self.process_id
        )

        # Armar payload completedProducts
        completed_products = []
        for p_id, info in self.scanned_quantities.items():
            completed_products.append({
                "product_id": p_id,
                "quantity": info["scanned"]
            })

        payload = {"completedProducts": completed_products}
        result = self.login_controller.api_client._make_post_request(endpoint, payload)

        if not result or not result.get("success"):
            messagebox.showerror("Error", "No se pudo confirmar la orden en la API.")
            return

        data_r = result.get("data", {})
        if data_r.get("finished_at"):
            self.completed_orders_count += 1
            messagebox.showinfo("Pedido Finalizado", "La orden se ha completado correctamente.")

        # label_url = result.get("label_url")
        # if label_url:
        #     self.download_and_print_label(label_url)

        # Refrescar la vista para traer la siguiente orden
        self.fetch_process_detail()

    # --------------------------------------------------------------------------
    # Órdenes Confirmadas
    # --------------------------------------------------------------------------
    def update_confirmed_orders_table(self, confirmed):
        self.confirmed_orders_data = []
        if not confirmed:
            # Si no hay órdenes confirmadas
            self.confirmed_orders_data.append(("Sin órdenes confirmadas", "", "", "", ""))
        else:

            for _, order_info in confirmed.items():
                order_id = "49186"
                products = order_info.get("products", [])
                prod_text = "; ".join([f"{p.get('name','')}({p.get('quantity',0)})" for p in products])

                started_at = order_info.get("started_at", "-----")
                finished_at = order_info.get("finished_at", "Sin Finalizar")
                actions = "Ver Detalle"

                self.confirmed_orders_data.append((order_id, prod_text, started_at, finished_at, actions))


        self.current_page = 1
        self.total_pages = max(1, math.ceil(len(self.confirmed_orders_data) / self.page_size))
        self.refresh_table_page()
        self.refresh_orders_counter_label()

    def refresh_orders_counter_label(self):
        self.lbl_orders_counter.config(
            text=f"Pedidos completados: {self.completed_orders_count}/{self.total_orders_count}"
        )

    def refresh_table_page(self):
        for row in self.confirmed_tree.get_children():
            self.confirmed_tree.delete(row)

        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        page_data = self.confirmed_orders_data[start_idx:end_idx]

        for data in page_data:
            self.confirmed_tree.insert("", "end", values=data)

        self.lbl_page_info.config(text=f"Página {self.current_page} de {self.total_pages}")

    def previous_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_table_page()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.refresh_table_page()

    def sort_column(self, col, reverse):
        col_map = {
            "Orden #": 0,
            "Productos": 1,
            "Inicio": 2,
            "Fin": 3,
            "Acciones": 4
        }
        idx = col_map.get(col)
        if idx is None:
            return

        if col == "Orden #":
            try:
                self.confirmed_orders_data.sort(key=lambda t: int(t[idx]), reverse=reverse)
            except ValueError:
                self.confirmed_orders_data.sort(key=lambda t: t[idx], reverse=reverse)
        elif col in ("Inicio", "Fin"):
            self.confirmed_orders_data.sort(key=lambda t: self.parse_date(t[idx]), reverse=reverse)
        else:
            self.confirmed_orders_data.sort(key=lambda t: t[idx], reverse=reverse)

        self.sort_directions[col] = not reverse
        self.refresh_table_page()

    @staticmethod
    def parse_date(date_str):
        try:
            return datetime.fromisoformat(date_str)
        except Exception:
            return datetime.min

    def on_confirmed_order_double_click(self, event):
        """
        Doble clic en la tabla de Órdenes Confirmadas => mostrar detalle de la orden.
        """
        try:
            sel_id = self.confirmed_tree.selection()[0]
        except IndexError:
            messagebox.showerror("Error", "No se ha seleccionado ninguna orden confirmada.")
            return

        item = self.confirmed_tree.item(sel_id)
        values = item["values"]
        order_val = values[0]  # Esto puede ser un int o un string

        # Convertimos a string para chequear si es numérico o si es "Sin órdenes confirmadas"
        order_str = str(order_val)
        if not order_str.isdigit():
            # Aquí evitamos mostrar el modal si, por ejemplo, el texto es "Sin órdenes confirmadas".
            return

        # Si pasa el chequeo, convertimos a entero para pasarlo a la función de detalle
        order_id = int(order_str)
        self.show_order_detail(order_id)


    def show_order_detail(self, order_id):
        """
        Llama a la API para mostrar detalle de la orden en un Toplevel,
        con un diseño visual más agradable.
        """
        endpoint = API_ROUTES["GET_ORDER"].format(id=order_id)
        resp = self.login_controller.api_client._make_get_request(endpoint)
        if not resp or not resp.get("success"):
            messagebox.showerror("Error", "No se pudo obtener el detalle de la orden.")
            return

        data = resp.get("data", [])
        if not data:
            messagebox.showinfo("Detalle Orden", "No hay datos disponibles para esta orden.")
            return

        order = data[0]

        # Creamos la ventana toplevel
        top = tk.Toplevel(self)
        top.title(f"Detalle de la Orden #{order_id}")
        # Ajusta el tamaño (ancho x alto), lo puedes modificar a tu gusto
        top.geometry("700x600")
        top.configure(bg="#f0f0f0")  

        # Encabezado
        header_label = tk.Label(
            top,
            text=f"Detalle de la Orden #{order_id}",
            font=("Arial", 14, "bold"),
            bg="#f0f0f0",
            fg="black"
        )
        header_label.pack(side="top", fill="x", pady=(10, 5))

        # ----------------------------------------------------------------------------
        # Sección: Información General
        # ----------------------------------------------------------------------------
        info_frame = tk.Frame(top, bg="white", bd=1, relief="solid")
        info_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        section_title = tk.Label(
            info_frame,
            text="Información General",
            font=("Arial", 12, "bold"),
            bg="white",
            fg="#333"
        )
        section_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 10))

        # Función auxiliar para crear fila Label-Valor en grid
        def add_info_row(parent, row_idx, label_text, value_text):
            label_widget = tk.Label(
                parent, text=label_text,
                font=("Arial", 10, "bold"),
                bg="white", fg="black"
            )
            label_widget.grid(row=row_idx, column=0, sticky="e", padx=10, pady=3)

            value_widget = tk.Label(
                parent, text=value_text,
                font=("Arial", 10),
                bg="white", fg="#555"
            )
            value_widget.grid(row=row_idx, column=1, sticky="w", padx=10, pady=3)

        # Agregamos filas con la info
        row_index = 1
        add_info_row(info_frame, row_index, "Orden ID:", str(order.get("id", ""))); row_index += 1
        add_info_row(info_frame, row_index, "Nombre:", order.get("name", "")); row_index += 1
        add_info_row(info_frame, row_index, "Email:", order.get("email", "")); row_index += 1
        add_info_row(info_frame, row_index, "Teléfono:", order.get("phone", "")); row_index += 1
        add_info_row(info_frame, row_index, "Dirección:", order.get("address", "")); row_index += 1
        add_info_row(info_frame, row_index, "Ciudad:", order.get("city", "")); row_index += 1
        add_info_row(info_frame, row_index, "Provincia:", order.get("province", "")); row_index += 1
        add_info_row(info_frame, row_index, "País:", order.get("country_code", "")); row_index += 1

        confirmed_at = order.get("confirmed_at") or "No Confirmado"
        fulfilled_at = order.get("fulfilled_at") or "No Fulfilled"
        add_info_row(info_frame, row_index, "Confirmado:", confirmed_at); row_index += 1
        add_info_row(info_frame, row_index, "Fulfilled:", fulfilled_at); row_index += 1

        # ----------------------------------------------------------------------------
        # Sección: Líneas de Pedido
        # ----------------------------------------------------------------------------
        lines_frame = tk.Frame(top, bg="white", bd=1, relief="solid")
        lines_frame.pack(fill="both", expand=True, padx=10, pady=5)

        lines_title = tk.Label(
            lines_frame,
            text="Líneas de Pedido (Productos):",
            font=("Arial", 12, "bold"),
            bg="white",
            fg="#333"
        )
        lines_title.pack(anchor="w", padx=10, pady=(5, 10))

        # Creamos un frame contenedor para poder agregar scrollbar si hay muchas líneas
        lines_container = tk.Frame(lines_frame, bg="white")
        lines_container.pack(fill="both", expand=True)

        # Scrollbar vertical
        scrollbar = ttk.Scrollbar(lines_container, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        # Canvas para poder hacer scroll en los elementos
        canvas = tk.Canvas(lines_container, bg="white", yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=canvas.yview)

        # Frame interno que contendrá todas las líneas de pedido
        lines_inner_frame = tk.Frame(canvas, bg="white")
        canvas.create_window((0,0), window=lines_inner_frame, anchor="nw")

        # Ajuste para que el frame se redibuje y calcule el scroll cuando cambiamos tamaño
        def on_frame_configure(event):
            canvas.config(scrollregion=canvas.bbox("all"))

        lines_inner_frame.bind("<Configure>", on_frame_configure)

        # Cargamos las líneas
        lines = order.get("lines", [])
        if not lines:
            no_lines_label = tk.Label(
                lines_inner_frame,
                text="No hay productos en la orden.",
                font=("Arial", 10),
                bg="white",
                fg="red"
            )
            no_lines_label.pack(anchor="w", padx=20, pady=5)
        else:
            for idx, line in enumerate(lines, start=1):
                product_name = line.get("product_name", "Producto desconocido")
                quantity = line.get("quantity", 0)
                line_label = tk.Label(
                    lines_inner_frame,
                    text=f"{idx}. {product_name} (x{quantity})",
                    font=("Arial", 10),
                    bg="white",
                    fg="#555"
                )
                line_label.pack(anchor="w", padx=20, pady=2)

        # ----------------------------------------------------------------------------
        # Botón de Cerrar
        # ----------------------------------------------------------------------------
        close_btn = tk.Button(
            top,
            text="Cerrar",
            command=top.destroy,
            **BUTTON_STYLE
        )
        close_btn.pack(side="bottom", pady=10)



    # --------------------------------------------------------------------------
    # Impresión (PDF)
    # --------------------------------------------------------------------------
    def download_and_print_label(self, label_url):
        """
        Ejemplo de descarga de PDF e impresión.
        """
        try:
            resp = requests.get(label_url)
            if resp.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(resp.content)
                    temp_filename = tmp.name
                self.print_document(temp_filename)
                os.remove(temp_filename)
            else:
                messagebox.showerror("Error", "No se pudo descargar la etiqueta para imprimir.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al imprimir la etiqueta: {str(e)}")

    def print_document(self, file_path):
        """
        Envía un PDF a la impresora seleccionada.
        """
        try:
            win32api.ShellExecute(0, "print", file_path, f'/d:"{self.selected_printer}"', ".", 0)
            messagebox.showinfo("Impresión", f"Documento enviado a {self.selected_printer}")
        except Exception as e:
            messagebox.showerror("Error de Impresión", f"Ocurrió un error: {str(e)}")


# ------------------------------------------------------------------------------
# Ejemplo local (Mock)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    class MockLoginController:
        class ApiClient:
            def _make_get_request(self, endpoint):
                # Simula respuesta fallida
                return {"success": False}
            def _make_post_request(self, endpoint, payload):
                # Simula respuesta exitosa
                return {"success": True, "data": {"finished_at": "2025-03-05 16:42:08"}}

        api_client = ApiClient()

    root = tk.Tk()
    root.title("Aplicación de Escaneo y Packing")
    root.geometry("1200x800")

    app = PackingShowView(master=root, process_id=123, login_controller=MockLoginController())
    app.pack(expand=True, fill="both")
    root.mainloop()
