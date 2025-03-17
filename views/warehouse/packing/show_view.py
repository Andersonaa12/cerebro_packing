import math
import os
import subprocess
import tempfile
import requests
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
import json
import winsound
import webbrowser
from playsound import playsound

import win32api
import win32print

from PIL import Image, ImageTk
from io import BytesIO
from config.settings import API_BASE_URL
from services.api_routes import API_ROUTES
from assets.css.styles import PRIMARY_COLOR, BACKGROUND_COLOR_VIEWS, LABEL_STYLE, BUTTON_STYLE
from components.print_component import print_from_url

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
    Vista de Packing con organización en la parte superior (3 columnas) y la parte inferior (2 filas).
    
    Parte superior (top_frame):
      - Columna 0 (Izquierda): Información del Pedido Actual
      - Columna 1 (Centro):    Escanear (SKU - Cod.barras)
      - Columna 2 (Derecha):   Información del Proceso + Barra de Órdenes

    Parte inferior (bottom_frame):
      - Fila 0: Tabla de Productos por Escanear (con imagen y columna REF)
                + Barra de Progreso de productos
      - Fila 1: Tabla de Órdenes Confirmadas

    Lógica:
      - Escaneo de productos (cuando se completa la cantidad de todos los productos,
        se confirma automáticamente la orden y pasa a la siguiente).
      - Doble clic en un producto abre una ventana de detalle con la imagen y datos del mismo.
      - Se emite beep solo en error (producto no pertenece, etc.).
      - Si el proceso finaliza por completo, se redirige a la vista anterior (on_back).
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
        self.pending_process_order = None   # Orden actual (packing_process_order)
        self.current_order_products = []    # Productos del pedido actual
        self.scanned_quantities = {}        # { product_id: {...} }
        self.confirmed_orders_data = []     # Lista de órdenes confirmadas
        self.total_orders_count = 0         # Cantidad total de pedidos en este packing
        self.completed_orders_count = 0     # Cuántas ya finalizadas

        # Diccionarios para imágenes y mapeo entre fila y producto
        self.product_images = {}            # Almacena PhotoImage de cada producto
        self.tree_row_to_product = {}       # Mapea row_id de la tabla a product_id

        # Config paginación Órdenes Confirmadas
        self.page_size = 10
        self.current_page = 1
        self.total_pages = 1
        self.sort_directions = {}

        # Referencias a barras de progreso y labels
        # PRODUCTOS -> estará en create_products_table_panel
        self.product_progress = None
        self.lbl_product_progress_info = None

        # ÓRDENES -> estará justo debajo del panel de información del proceso
        self.order_progress = None
        self.lbl_order_progress_info = None

        # Construye la interfaz
        self.create_widgets()
        # Carga datos iniciales
        self.fetch_process_detail()
    def play_error_sound(self):
            mp3_path = os.path.join("assets", "mp3", "error_alert.mp3")
            playsound(mp3_path)
    # --------------------------------------------------------------------------
    # Creación de widgets y distribución visual
    # --------------------------------------------------------------------------
    def create_widgets(self):
        """
        Layout:
          - Encabezado (barra naranja superior)
          - Sección superior (top_frame) con 3 columnas
            * order_container
            * scan_container
            * process_container + barra de órdenes
          - Sección inferior (bottom_frame + canvas):
            * Fila 0: productos
            * Fila 1: órdenes confirmadas
        """
        self.create_header()

        # Sección superior (con borde "doble")
        top_frame = tk.Frame(self, bg="white", bd=2, relief="ridge")
        top_frame.pack(fill="x", padx=10, pady=5)

        # Configuramos 3 columnas para top_frame
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)
        top_frame.columnconfigure(2, weight=1)

        # === Columna 0 (Izquierda): Información del Pedido Actual ===
        order_container = tk.Frame(top_frame, bg="white", bd=2, relief="ridge")
        order_container.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.create_current_order_info_panel(order_container)

        # === Columna 1 (Centro): Escanear (SKU - Cod.barras) ===
        scan_container = tk.Frame(top_frame, bg="white", bd=2, relief="ridge")
        scan_container.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.create_scan_panel(scan_container)

        # === Columna 2 (Derecha): Información del Proceso
        process_container = tk.Frame(top_frame, bg="white", bd=2, relief="ridge")
        process_container.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        self.create_process_info_panel(process_container)

        # === Barra de ÓRDENES justo debajo de la info del proceso ===
        self.create_order_progress_bar(process_container)

        # --------------------------
        # Sección inferior (scroll)
        # --------------------------
        bottom_frame = tk.Frame(self, bg="white", bd=2, relief="ridge")
        bottom_frame.pack(fill="both", expand=True, padx=10, pady=5)

        canvas = tk.Canvas(bottom_frame, bg="white")
        canvas.pack(side="left", fill="both", expand=True)

        scroll_y = ttk.Scrollbar(bottom_frame, orient="vertical", command=canvas.yview)
        scroll_y.pack(side="right", fill="y")

        canvas.configure(yscrollcommand=scroll_y.set)

        # Frame interno que contendrá las dos tablas (una encima de la otra)
        bottom_content_frame = tk.Frame(canvas, bg="white")
        canvas_window = canvas.create_window((0, 0), window=bottom_content_frame, anchor="nw")

        # Ajustar la región de scroll cuando cambie el tamaño interno
        def on_bottom_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        bottom_content_frame.bind("<Configure>", on_bottom_frame_configure)

        # También forzamos que el ancho del frame interno se adapte al ancho del canvas
        def on_canvas_configure(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)

        canvas.bind("<Configure>", on_canvas_configure)

        # Configurar el grid en bottom_content_frame
        bottom_content_frame.columnconfigure(0, weight=1)
        bottom_content_frame.rowconfigure(0, weight=1)
        bottom_content_frame.rowconfigure(1, weight=1)

        # Fila 0: Productos por escanear
        self.products_frame = tk.Frame(bottom_content_frame, bg="white", bd=2, relief="ridge")
        self.products_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.create_products_table_panel(self.products_frame)

        # Fila 1: Órdenes confirmadas
        self.confirmed_orders_frame = tk.Frame(bottom_content_frame, bg="white", bd=2, relief="ridge")
        self.confirmed_orders_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.create_confirmed_orders_table()

    def create_header(self):
        """
        Barra de encabezado superior con título y botón "Salir".
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
            text="Salir",
            command=self.on_back_button,
            **BUTTON_STYLE
        )
        back_btn.pack()

    # --------------------------------------------------------------------------
    # Panel: Información del Pedido Actual (Columna 0)
    # --------------------------------------------------------------------------
    def create_current_order_info_panel(self, container):
        tk.Label(
            container,
            text="Pedido Actual",
            font=("Arial", 14, "bold"),
            fg=PRIMARY_COLOR,
            bg="white"
        ).pack(pady=(10, 5))

        content_frame = tk.Frame(container, bg="white")
        content_frame.pack(fill="x", padx=5, pady=5)

        row_idx = 0
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

    # --------------------------------------------------------------------------
    # Panel: Escanear (SKU - Cod.barras) (Columna 1)
    # --------------------------------------------------------------------------
    def create_scan_panel(self, container):
        tk.Label(
            container,
            text="Código de Barras",
            font=("Arial", 14, "bold"),
            fg=PRIMARY_COLOR,
            bg="white"
        ).pack(pady=(10, 5))

        scan_frame = tk.Frame(container, bg="white")
        scan_frame.pack(fill="both", expand=True, padx=5, pady=5)

        style = ttk.Style()
        style.configure("Custom.TEntry", padding=5, relief="flat", font=("Arial", 12), foreground="black")
        
        self.entry_barcode = ttk.Entry(scan_frame, style="Custom.TEntry")
        self.entry_barcode.pack(side="left", padx=5, fill="x", expand=True)
        self.entry_barcode.bind("<Return>", self.on_barcode_enter)

        self.lbl_scan_message = tk.Label(scan_frame, text="", font=("Arial", 12), bg="white", fg="blue")
        self.lbl_scan_message.pack(side="left", padx=5)

    # --------------------------------------------------------------------------
    # Panel: Información del Proceso (Columna 2)
    # --------------------------------------------------------------------------
    def create_process_info_panel(self, container):
        tk.Label(
            container,
            text="Proceso Packing",
            font=("Arial", 14, "bold"),
            fg=PRIMARY_COLOR,
            bg="white"
        ).pack(pady=(10, 5))

        info_frame = tk.Frame(container, bg="white")
        info_frame.pack(fill="x", padx=10, pady=5)

        info_frame.columnconfigure(0, weight=1)
        info_frame.columnconfigure(1, weight=1)

        self.lbl_nombre = tk.Label(
            info_frame,
            text="Nombre: -",
            font=("Arial", 12),
            bg="white"
        )
        self.lbl_nombre.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.lbl_iniciado = tk.Label(
            info_frame,
            text="Iniciado: -",
            font=("Arial", 12),
            bg="white"
        )
        self.lbl_iniciado.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        self.lbl_finalizado = tk.Label(
            info_frame,
            text="Finalizado: -",
            font=("Arial", 12),
            bg="white"
        )
        self.lbl_finalizado.grid(row=1, column=0, sticky="w", padx=5, pady=5)

        self.lbl_creado_por = tk.Label(
            info_frame,
            text="Creado por: -",
            font=("Arial", 12),
            bg="white"
        )
        self.lbl_creado_por.grid(row=1, column=1, sticky="w", padx=5, pady=5)

    # --------------------------------------------------------------------------
    # Barra de progreso de ÓRDENES debajo de create_process_info_panel
    # --------------------------------------------------------------------------
    def create_order_progress_bar(self, container):
        """
        Crea la barra de progreso de órdenes y su Label,
        justo debajo de la info del proceso.
        """
        # Texto informativo
        self.lbl_order_progress_info = tk.Label(
            container,
            text="0/0 órdenes completadas",
            font=("Arial", 10, "bold"),
            bg="white",
            fg="#f58033"
        )
        self.lbl_order_progress_info.pack(pady=(5, 2))

        # 1) Crear/obtener un Style
        style = ttk.Style(container)  # container se usará como "master" del style

        # 2) Configurar un nuevo estilo (ej. "green.Horizontal.TProgressbar")
        style.configure(
            "green.Horizontal.TProgressbar",
            troughcolor="#f0f0f0",  # Color de fondo del canal (opcional)
            background="green"      # Color principal de la barra
        )

        # 3) Crear la Progressbar usando ese estilo
        self.order_progress = ttk.Progressbar(
            container,
            style="green.Horizontal.TProgressbar",
            orient="horizontal",
            length=200,
            mode="determinate"
        )
        self.order_progress.pack(padx=5, fill="x", pady=(0, 10))


    # --------------------------------------------------------------------------
    # Parte inferior, Fila 0: Productos (con su barra de progreso de productos)
    # --------------------------------------------------------------------------
    def create_products_table_panel(self, container):
        # 1) Crear un objeto Style (usando el contenedor como master)
        style = ttk.Style(container)
        # 2) Definir y configurar el estilo "greenProd.Horizontal.TProgressbar" 
        #    (puedes usar el nombre que quieras en lugar de "greenProd")
        style.configure(
            "greenProd.Horizontal.TProgressbar",
            troughcolor="#f0f0f0",  # Color del canal (opcional)
            background="green"      # Color principal de la barra
        )

        # Barra de progreso de productos escaneados (label)
        self.lbl_product_progress_info = tk.Label(
            container, 
            text="0/0 productos escaneados", 
            font=("Arial", 10, "bold"), 
            bg="white", 
            fg="#f58033"
        )
        self.lbl_product_progress_info.pack(pady=(5, 2))

        # 3) Crear la Progressbar asignando el estilo "greenProd.Horizontal.TProgressbar"
        self.product_progress = ttk.Progressbar(
            container,
            style="greenProd.Horizontal.TProgressbar",
            orient="horizontal",
            length=400,
            mode="determinate"
        )
        self.product_progress.pack(padx=5, fill="x", pady=(0, 10))

        tk.Label(container, text="Productos por Escanear", font=("Arial", 16, "bold"), bg="white").pack(pady=5)


        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 14), rowheight=40)
        style.configure("Treeview.Heading", font=("Arial", 14, "bold"))

        columns = ("Nombre", "Ref", "SKU", "Cantidad")
        self.current_order_tree = ttk.Treeview(
            container,
            columns=columns,
            show="tree headings",
            height=17
        )

        # Configurar encabezados
        self.current_order_tree.heading("#0", text="Imagen")
        self.current_order_tree.column("#0", width=100, anchor="center")

        self.current_order_tree.heading("Nombre", text="Nombre del Producto")
        self.current_order_tree.column("Nombre", width=300, anchor="center")

        self.current_order_tree.heading("Ref", text="Referencia")
        self.current_order_tree.column("Ref", width=300, anchor="center")

        self.current_order_tree.heading("SKU", text="SKU")
        self.current_order_tree.column("SKU", width=150, anchor="center")

        self.current_order_tree.heading("Cantidad", text="Escaneados")
        self.current_order_tree.column("Cantidad", width=150, anchor="center")

        self.current_order_tree.tag_configure("pending", background="white")
        self.current_order_tree.tag_configure("partial", background="orange")
        self.current_order_tree.tag_configure("complete", background="lightgreen")

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.current_order_tree.yview)
        self.current_order_tree.configure(yscrollcommand=scroll.set)

        self.current_order_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")

        self.current_order_tree.bind("<Double-1>", self.on_product_double_click)

    # --------------------------------------------------------------------------
    # Tabla de Órdenes Confirmadas
    # --------------------------------------------------------------------------
    def create_confirmed_orders_table(self):
        tk.Label(
            self.confirmed_orders_frame,
            text="Órdenes Confirmadas",
            font=("Arial", 14, "bold"),
            bg="white"
        ).pack(pady=5)

        self.lbl_orders_counter = tk.Label(
            self.confirmed_orders_frame,
            text="0/0",
            font=("Arial", 12, "bold"),
            bg="white"
        )
        self.lbl_orders_counter.pack()

        columns = ("Orden #", "Productos", "Duración (seg)", "Acciones")
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
            width = 200 if col == "Acciones" else 140
            self.confirmed_tree.column(col, anchor="center", width=width)

        scrollbar = ttk.Scrollbar(self.confirmed_orders_frame, orient="vertical", command=self.confirmed_tree.yview)
        self.confirmed_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.confirmed_tree.pack(expand=True, fill="both")

        self.confirmed_tree.bind("<Double-1>", self.on_confirmed_order_double_click)

        pag_frame = tk.Frame(self.confirmed_orders_frame, bg="white")
        pag_frame.pack(fill="x", padx=10, pady=5)

        prev_btn = tk.Button(pag_frame, text="Anterior", command=self.previous_page, **BUTTON_STYLE)
        prev_btn.pack(side="left", padx=5)

        self.lbl_page_info = tk.Label(pag_frame, text="", font=("Arial", 12), bg="white")
        self.lbl_page_info.pack(side="left", padx=5)

        next_btn = tk.Button(pag_frame, text="Siguiente", command=self.next_page, **BUTTON_STYLE)
        next_btn.pack(side="left", padx=5)

    # --------------------------------------------------------------------------
    # Botón "Salir"
    # --------------------------------------------------------------------------
    def on_back_button(self):
        if self.on_back:
            self.on_back()
        else:
            self.destroy()

    # --------------------------------------------------------------------------
    # Actualización de barras de progreso (productos + órdenes)
    # --------------------------------------------------------------------------
    def update_progress_bars(self):
        # PRODUCTOS
        total_required = sum(info["required"] for info in self.scanned_quantities.values())
        total_scanned = sum(info["scanned"] for info in self.scanned_quantities.values())

        if total_required > 0:
            prod_progress_value = (total_scanned / total_required) * 100
        else:
            prod_progress_value = 0
        if self.product_progress:
            self.product_progress["value"] = prod_progress_value
        if self.lbl_product_progress_info:
            self.lbl_product_progress_info.config(
                text=f"{total_scanned}/{total_required} productos escaneados"
            )

        # ÓRDENES
        if self.total_orders_count > 0:
            order_progress_value = (self.completed_orders_count / self.total_orders_count) * 100
        else:
            order_progress_value = 0

        if self.order_progress:
            self.order_progress["value"] = order_progress_value
        if self.lbl_order_progress_info:
            self.lbl_order_progress_info.config(
                text=f"{self.completed_orders_count}/{self.total_orders_count} órdenes completadas"
            )

    # --------------------------------------------------------------------------
    # Fetch data & Update UI
    # --------------------------------------------------------------------------
    def fetch_process_detail(self):
        endpoint = API_ROUTES["PACKING_VIEW"].format(id=self.process_id)
        response = self.login_controller.api_client._make_get_request(endpoint)
        if not response or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener el detalle del proceso de Packing.")
            return

        data = response.get("data", {})
        process = data.get("process", {})

        self.lbl_nombre.config(text=f"Nombre: {process.get('name', 'N/A')}")
        self.lbl_iniciado.config(text=f"Iniciado: {process.get('started_at', 'N/A')}")
        finished_at = process.get("finished_at")
        fin_text = finished_at if finished_at else "En Proceso"
        self.lbl_finalizado.config(text=f"Finalizado: {fin_text}")

        creador = process.get("created_by", "N/A")
        if isinstance(creador, dict):
            creador = creador.get("name", "N/A")
        self.lbl_creado_por.config(text=f"Creado por: {creador}")

        confirmed_orders = data.get("confirmedOrders", {})
        self.update_confirmed_orders_table(confirmed_orders)

        packing_orders = process.get("packing_process_orders", [])
        self.total_orders_count = len(packing_orders)

        finished_list = [po for po in packing_orders if po.get("finished_at")]
        self.completed_orders_count = len(finished_list)

        all_finished = (len(packing_orders) > 0 and all(o.get("finished_at") for o in packing_orders))

        if finished_at or all_finished:
            self.pending_process_order = None
            self.clear_current_order_table()
            self.lbl_order_id.config(text="Pedido ID: -- (Finalizado)")
            self.lbl_shipping_method.config(text="Método de envío: -- (Finalizado)", fg="black")
            self.entry_barcode.config(state="disabled")
            self.refresh_orders_counter_label()
            if self.on_back:
                self.on_back()
            return

        # Orden pendiente
        self.pending_process_order = data.get("pendingProcessOrder")
        if not self.pending_process_order:
            not_finished = [po for po in packing_orders if not po.get("finished_at")]
            if not_finished:
                self.pending_process_order = not_finished[0]

        if not self.pending_process_order:
            self.clear_current_order_table()
            self.refresh_orders_counter_label()
            return

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

        self.scanned_quantities = {}
        self.current_order_products = self.pending_process_order.get("packing_process_order_product", [])
        self.populate_current_order_products_table()

        self.entry_barcode.config(state="normal")
        self.entry_barcode.delete(0, tk.END)
        self.entry_barcode.focus()

        self.refresh_orders_counter_label()
        self.update_progress_bars()

    # --------------------------------------------------------------------------
    # Tabla de productos
    # --------------------------------------------------------------------------
    def clear_current_order_table(self):
        for row in self.current_order_tree.get_children():
            self.current_order_tree.delete(row)

    def populate_current_order_products_table(self):
        self.clear_current_order_table()
        self.tree_row_to_product = {}

        for line in self.current_order_products:
            product_data = line.get("product", {})
            p_id = product_data.get("id")
            p_name = product_data.get("name", "")
            p_sku = product_data.get("sku", "")
            p_bar = product_data.get("bar_code", "")
            p_qty = line.get("quantity", 0)
            warehouse_code = product_data.get("warehouse_code", "N/A")
            referencia = f"{warehouse_code} - {p_name} - {p_sku}"

            image_url = product_data.get("image_url")
            photo = None
            if image_url:
                try:
                    resp = requests.get(image_url)
                    if resp.status_code == 200:
                        image_data = BytesIO(resp.content)
                        pil_image = Image.open(image_data)
                        pil_image.thumbnail((50, 50))
                        photo = ImageTk.PhotoImage(pil_image)
                        self.product_images[p_id] = photo
                except Exception as e:
                    print(f"Error al cargar imagen {image_url}: {e}")

            row_id = self.current_order_tree.insert(
                "",
                "end",
                text="",
                image=photo,
                values=(p_name, referencia, p_sku, f"0/{p_qty}"),
                tags=("pending",)
            )
            self.scanned_quantities[p_id] = {
                "scanned": 0,
                "required": p_qty,
                "row_id": row_id,
                "sku": p_sku,
                "bar_code": p_bar,
                "image_url": image_url,
                "name": p_name,
                "warehouse_code": warehouse_code
            }
            self.tree_row_to_product[row_id] = p_id

    # --------------------------------------------------------------------------
    # Escaneo de productos
    # --------------------------------------------------------------------------
    def on_barcode_enter(self, event):
        scanned_code = self.entry_barcode.get().strip()
        self.entry_barcode.delete(0, tk.END)

        if not self.pending_process_order:
            return

        matched_id = self.find_product_id_by_scan(scanned_code)
        if matched_id is None:
            self.play_error_sound()
            self.lbl_scan_message.config(text="Producto NO pertenece al pedido.", fg="red")
            return

        info = self.scanned_quantities.get(matched_id)
        if not info:
            self.play_error_sound()
            self.lbl_scan_message.config(text="Error interno al escanear.", fg="red")
            return

        if info["scanned"] >= info["required"]:
            self.play_error_sound()
            self.lbl_scan_message.config(text="Este producto ya está completo.", fg="red")
            return

        info["scanned"] += 1
        self.update_product_row(matched_id)
        self.lbl_scan_message.config(text="")

        self.update_progress_bars()

        if self.all_products_complete():
            self.confirm_current_order()


    def find_product_id_by_scan(self, scanned_code):
        for p_id, info in self.scanned_quantities.items():
            if scanned_code == info.get("bar_code") or scanned_code == info.get("sku"):
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
        return all(info["scanned"] >= info["required"] for info in self.scanned_quantities.values())



    # --------------------------------------------------------------------------
    # Doble clic en un producto -> detalle
    # --------------------------------------------------------------------------
    def on_product_double_click(self, event):
        try:
            row_id = self.current_order_tree.selection()[0]
        except IndexError:
            return
        product_id = self.tree_row_to_product.get(row_id)
        if product_id is None:
            return
        self.show_product_detail(product_id)

    def show_product_detail(self, product_id):
        info = self.scanned_quantities.get(product_id)
        if not info:
            messagebox.showerror("Error", "Información del producto no disponible.")
            return

        top = tk.Toplevel(self)
        top.title(f"Detalle del Producto: {info.get('name', '')}")
        top.geometry("700x400")
        top.configure(bg="#f0f0f0")

        header_label = tk.Label(
            top,
            text=f"{info.get('name', '')}",
            font=("Arial", 14, "bold"),
            bg="#f0f0f0", fg="black"
        )
        header_label.pack(side="top", fill="x", pady=(10, 5))

        content_frame = tk.Frame(top, bg="white", bd=1, relief="solid")
        content_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        image_frame = tk.Frame(content_frame, bg="white")
        image_frame.pack(pady=10)

        photo = self.product_images.get(product_id)
        if photo:
            try:
                if isinstance(photo, ImageTk.PhotoImage):
                    img_label = tk.Label(image_frame, image=photo, bg="white")
                    img_label.image = photo
                    img_label.pack()
                else:
                    tk.Label(image_frame, text="No hay imagen disponible.", font=("Arial", 12), bg="white").pack()
            except:
                tk.Label(image_frame, text="No hay imagen disponible.", font=("Arial", 12), bg="white").pack()
        else:
            tk.Label(image_frame, text="No hay imagen disponible.", font=("Arial", 12), bg="white").pack()

        details_frame = tk.Frame(content_frame, bg="white")
        details_frame.pack(pady=10, fill="x")

        def add_info_row(parent, row_idx, label_text, value_text):
            lbl = tk.Label(parent, text=label_text, font=("Arial", 12, "bold"), 
                        bg="white", fg="black", width=15, anchor="e")
            lbl.grid(row=row_idx, column=0, sticky="e", padx=5, pady=5)
            val = tk.Label(parent, text=value_text, font=("Arial", 12), 
                        bg="white", fg="#555", anchor="w")
            val.grid(row=row_idx, column=1, sticky="w", padx=5, pady=5)

        row_idx = 0
        add_info_row(details_frame, row_idx, "Referencia:", 
                     f"{info.get('warehouse_code','N/A')} - {info.get('name','')} - {info.get('sku','')}"); row_idx += 1
        add_info_row(details_frame, row_idx, "SKU:", info.get("sku", "N/A")); row_idx += 1
        add_info_row(details_frame, row_idx, "Código de Barras:", info.get("bar_code", "N/A")); row_idx += 1
        add_info_row(details_frame, row_idx, "Escaneado:", str(info.get("scanned", 0))); row_idx += 1
        add_info_row(details_frame, row_idx, "Requerido:", str(info.get("required", 0))); row_idx += 1

        close_btn = tk.Button(top, text="Cerrar", command=top.destroy)
        close_btn.pack(pady=10)

    # --------------------------------------------------------------------------
    # Confirmar orden al completar todos los productos
    # --------------------------------------------------------------------------
    def confirm_current_order(self):
        if not self.pending_process_order:
            return
        order_data = self.pending_process_order.get("order", {})
        expected_tracking_code = order_data.get("tracking_code", "")

        if not self.verify_tracking_code(expected_tracking_code):
            return

        order_id = self.pending_process_order.get("id")
        endpoint = API_ROUTES["PACKING_CONFIRM"].format(
            packingProcessOrder_id=order_id,
            packingProcess_id=self.process_id
        )

        completed_products = []
        for p_id, info in self.scanned_quantities.items():
            completed_products.append({"product_id": p_id, "quantity": info["scanned"]})

        payload = {"completedProducts": completed_products}
        result = self.login_controller.api_client._make_post_request(endpoint, payload)
        if not result or not result.get("success"):
            messagebox.showerror("Error", "No se pudo confirmar la orden en la API.")
            return

        label_url = result.get("label_url")
        success_message = "La orden se ha completado correctamente."
        
        if label_url:
            try:
                if label_url == 0:
                    success_message += "\nPacking Finalizado!!!."
                else:
                    print_from_url(label_url)
                    success_message += "\nEtiqueta enviada a imprimir."
            except Exception as e:
                messagebox.showwarning(
                    "Advertencia", 
                    f"Orden completada pero error al imprimir etiqueta: {str(e)}"
                )

        self.completed_orders_count += 1
        # messagebox.showinfo("Pedido Finalizado", success_message)
        self.fetch_process_detail()

    # --------------------------------------------------------------------------
    # Verificación de Tracking Code
    # --------------------------------------------------------------------------
    def verify_tracking_code(self, expected_tracking_code):
        tracking_window = tk.Toplevel(self)
        tracking_window.title("Verificar Tracking Code")
        tracking_window.geometry("400x200")
        tracking_window.configure(bg="#f0f0f0")
        tracking_window.grab_set()
        tracking_window.transient(self.master)
        
        tracking_window.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (tracking_window.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (tracking_window.winfo_height() // 2)
        tracking_window.geometry(f"+{x}+{y}")
        
        tk.Label(
            tracking_window,
            text="Escanea el Codigo de Seguimiento:",
            font=("Arial", 12, "bold"),
            bg="#f0f0f0",
            fg="black"
        ).pack(pady=10)
        
        tracking_entry = ttk.Entry(tracking_window, font=("Arial", 12))
        tracking_entry.pack(pady=5, padx=10, fill="x")
        tracking_entry.focus_set()
        
        message_label = tk.Label(
            tracking_window,
            text=f"Esperado: '{expected_tracking_code}'" if expected_tracking_code else "Esperado: (vacío)",
            font=("Arial", 10),
            bg="#f0f0f0",
            fg="blue"
        )
        message_label.pack(pady=5)
        
        verification_result = {"success": False}
        
        def check_tracking_code(event=None):
            scanned_code = tracking_entry.get().strip()
            if scanned_code == expected_tracking_code:
                verification_result["success"] = True
                tracking_window.destroy()
            else:
                self.play_error_sound()
                message_label.config(text="Error: El tracking code no coincide", fg="red")
                tracking_entry.delete(0, tk.END)
        
        tracking_entry.bind("<Return>", check_tracking_code)
        
        verify_btn = tk.Button(
            tracking_window,
            text="Verificar",
            command=check_tracking_code,
            **BUTTON_STYLE
        )
        verify_btn.pack(pady=10)
        
        self.master.wait_window(tracking_window)
        return verification_result["success"]

    # --------------------------------------------------------------------------
    # Órdenes Confirmadas (FILA 1)
    # --------------------------------------------------------------------------
    def update_confirmed_orders_table(self, confirmed):
        self.confirmed_orders_data = []
        if not confirmed:
            self.confirmed_orders_data.append(("Sin órdenes confirmadas", "", "", ""))
        else:
            for _, order_info in confirmed.items():
                order_id = order_info.get("order_id", "")
                products = order_info.get("products", [])
                prod_text = "; ".join([f"{p.get('name','')}({p.get('quantity',0)})" for p in products])
                started_at = order_info.get("started_at", "")
                finished_at = order_info.get("finished_at", "")
                if started_at and finished_at:
                    try:
                        dt_start = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
                        dt_finish = datetime.strptime(finished_at, "%Y-%m-%d %H:%M:%S")
                        duration_seconds = int((dt_finish - dt_start).total_seconds())
                    except:
                        duration_seconds = "N/A"
                else:
                    duration_seconds = "N/A"

                actions = "Imprimir"
                self.confirmed_orders_data.append((order_id, prod_text, duration_seconds, actions))

        self.current_page = 1
        self.total_pages = max(1, math.ceil(len(self.confirmed_orders_data) / self.page_size))
        self.refresh_table_page()
        self.refresh_orders_counter_label()

    def refresh_orders_counter_label(self):
        self.lbl_orders_counter.config(
            text=f"{self.completed_orders_count}/{self.total_orders_count}"
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
        self.confirmed_tree.bind("<Button-1>", self.on_tree_click)

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
            "Duración (seg)": 2,
            "Acciones": 3
        }
        idx = col_map.get(col)
        if idx is None:
            return

        if col == "Orden #":
            try:
                self.confirmed_orders_data.sort(key=lambda t: int(t[idx]), reverse=reverse)
            except ValueError:
                self.confirmed_orders_data.sort(key=lambda t: t[idx], reverse=reverse)
        elif col == "Duración (seg)":
            self.confirmed_orders_data.sort(
                key=lambda t: int(t[idx]) if (isinstance(t[idx], int) or
                                              (isinstance(t[idx], str) and t[idx].isdigit()))
                else 0,
                reverse=reverse
            )
        else:
            self.confirmed_orders_data.sort(key=lambda t: t[idx], reverse=reverse)

        self.sort_directions[col] = not reverse
        self.refresh_table_page()

    def on_confirmed_order_double_click(self, event):
        try:
            sel_id = self.confirmed_tree.selection()[0]
        except IndexError:
            messagebox.showerror("Error", "No se ha seleccionado ninguna orden confirmada.")
            return
        item = self.confirmed_tree.item(sel_id)
        values = item["values"]
        order_val = values[0]
        order_str = str(order_val)
        if not order_str.isdigit():
            return
        self.show_order_detail(int(order_str))

    def on_tree_click(self, event):
        item = self.confirmed_tree.identify_row(event.y)
        column = self.confirmed_tree.identify_column(event.x)
        if not item or column != "#4":  # "#4" = columna "Acciones"
            return

        values = self.confirmed_tree.item(item, "values")
        order_id = values[0]
        if order_id.isdigit():
            self.print_order(int(order_id))

    def print_order(self, order_id):
        endpoint = API_ROUTES["PACKING_PRINT_ORDER"].format(order_id=order_id)
        response = self.login_controller.api_client._make_get_request(endpoint)
        if not response or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener la URL de impresión.")
            return

        label_url = response.get("label_url")
        if not label_url:
            messagebox.showerror("Error", "No se encontró la URL de la etiqueta en la respuesta.")
            return

        try:
            print_from_url(label_url)
            messagebox.showinfo("Éxito", f"Etiqueta de la orden #{order_id} enviada a la impresora.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al imprimir la orden #{order_id}: {str(e)}")

    def show_order_detail(self, order_id):
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

        top = tk.Toplevel(self)
        top.title(f"Detalle de la Orden #{order_id}")
        top.geometry("700x600")
        top.configure(bg="#f0f0f0")  

        header_label = tk.Label(
            top,
            text=f"Detalle de la Orden #{order_id}",
            font=("Arial", 14, "bold"),
            bg="#f0f0f0",
            fg="black"
        )
        header_label.pack(side="top", fill="x", pady=(10, 5))

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

        lines_container = tk.Frame(lines_frame, bg="white")
        lines_container.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(lines_container, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        canvas = tk.Canvas(lines_container, bg="white", yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=canvas.yview)

        lines_inner_frame = tk.Frame(canvas, bg="white")
        canvas.create_window((0,0), window=lines_inner_frame, anchor="nw")

        def on_frame_configure(event):
            canvas.config(scrollregion=canvas.bbox("all"))

        lines_inner_frame.bind("<Configure>", on_frame_configure)

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

        close_btn = tk.Button(
            top,
            text="Cerrar",
            command=top.destroy,
            **BUTTON_STYLE
        )
        close_btn.pack(side="bottom", pady=10)


# --------------------------------------------------------------------------
# Ejemplo local (Mock) para pruebas
# --------------------------------------------------------------------------
if __name__ == "__main__":
    class MockLoginController:
        class ApiClient:
            def _make_get_request(self, endpoint):
                return {"success": False}
            def _make_post_request(self, endpoint, payload):
                return {"success": True, "data": {"finished_at": "2025-03-05 16:42:08"}}

        api_client = ApiClient()

    root = tk.Tk()
    root.title("Aplicación de Escaneo y Packing")
    root.geometry("1200x800")

    def mock_on_back():
        messagebox.showinfo("Salir", "Regresando a la lista de procesos...")

    app = PackingShowView(master=root, process_id=123, login_controller=MockLoginController(), on_back=mock_on_back)
    app.pack(expand=True, fill="both")
    root.mainloop()
