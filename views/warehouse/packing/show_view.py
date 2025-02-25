import tkinter as tk
from tkinter import messagebox, ttk
from config.settings import API_BASE_URL
from services.api_routes import API_ROUTES
from components.barcode_widget import create_barcode_widget

class PackingShowView(tk.Frame):
    """
    Vista para mostrar el detalle del proceso de Packing, incluyendo:
      - Información general del proceso (nombre, fechas, usuario creador)
      - Datos del contenedor (si lo hubiera) y, opcionalmente, su código de barras
      - Panel para el escaneo de productos pendientes
      - Botón "Devolver" para regresar a la vista de listado (PackingListView)
    """
    def __init__(self, master=None, process_id=None, login_controller=None, on_back=None):
        """
        :param master: ventana o frame padre.
        :param process_id: ID del proceso a mostrar.
        :param login_controller: instancia de LoginController con el ApiClient autenticado.
        :param on_back: callback para volver a la vista de listado.
        """
        super().__init__(master, bg="white")
        self.master = master
        self.process_id = process_id
        self.login_controller = login_controller
        self.on_back = on_back

        # Variables para el panel de escaneo
        self.pending_products = []
        self.confirmed_orders = []
        self.current_index = 0
        self.scanned_count = 0
        self.expected_quantity = 0

        self.create_widgets()
        self.fetch_process_detail()
    def show_list_view(self):
        """
        Método callback para volver a la vista de listado.
        Se encarga de destruir la vista actual y crear la vista de listado.
        """
        # Destruir la vista actual (la de detalle)
        self.destroy()
        # Aquí se instanciaría PackingListView nuevamente, por ejemplo:
        from views.warehouse.packing.list_view import PackingListView
        list_view = PackingListView(master=self.master, login_controller=self.login_controller)
        list_view.pack(expand=True, fill="both")
    def draw_barcode(self, barcode_value):
        """Dibuja un código de barras usando el componente reutilizable en el canvas."""
        # Limpia el canvas
        self.canvas_barcode.delete("all")
        # Crea el widget del código de barras (un Label con la imagen)
        barcode_widget = create_barcode_widget(self.canvas_barcode, barcode_value, width=200, height=100)
        # Inserta el widget en el canvas usando create_window
        self.canvas_barcode.create_window(0, 0, anchor="nw", window=barcode_widget, width=200, height=100)

    def create_widgets(self):
        # Encabezado: título y botón "Devolver"
        header_frame = tk.Frame(self, bg="white")
        header_frame.pack(fill="x", padx=10, pady=5)
        title_lbl = tk.Label(header_frame, text="Detalle del Proceso - Packing", font=("Arial", 16, "bold"), bg="white")
        title_lbl.pack(side="left", padx=(0, 20))
        back_btn = tk.Button(header_frame, text="Devolver", font=("Arial", 12), command=self.devolver)
        back_btn.pack(side="right")

        # Información del proceso y del contenedor
        info_frame = tk.Frame(self, bg="white", bd=1, relief="solid")
        info_frame.pack(fill="x", padx=10, pady=5)
        
        # Información del proceso (izquierda)
        left_frame = tk.Frame(info_frame, bg="white")
        left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.lbl_nombre = tk.Label(left_frame, text="Nombre: ", font=("Arial", 12), bg="white")
        self.lbl_nombre.pack(anchor="w", pady=2)
        self.lbl_iniciado = tk.Label(left_frame, text="Iniciado: ", font=("Arial", 12), bg="white")
        self.lbl_iniciado.pack(anchor="w", pady=2)
        self.lbl_finalizado = tk.Label(left_frame, text="Finalizado: ", font=("Arial", 12), bg="white")
        self.lbl_finalizado.pack(anchor="w", pady=2)
        self.lbl_creado_por = tk.Label(left_frame, text="Creado por: ", font=("Arial", 12), bg="white")
        self.lbl_creado_por.pack(anchor="w", pady=2)

        # Información del contenedor (derecha)
        right_frame = tk.Frame(info_frame, bg="white", bd=1, relief="solid")
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        self.lbl_container = tk.Label(right_frame, text="Contenedor: No hay contenedores asociados.", font=("Arial", 12), bg="white")
        self.lbl_container.pack(pady=10)
        self.canvas_barcode = tk.Canvas(right_frame, width=200, height=100, bg="white", highlightthickness=0)
        self.canvas_barcode.pack(pady=5)

        # Panel de escaneo de productos
        self.scanning_frame = tk.Frame(self, bg="white", bd=1, relief="solid")
        self.scanning_frame.pack(fill="both", expand=True, padx=10, pady=10)
        scan_title = tk.Label(self.scanning_frame, text="Escaneo de Productos", font=("Arial", 14, "bold"), bg="white")
        scan_title.pack(pady=5)

        # Información del producto actual
        self.product_info_frame = tk.Frame(self.scanning_frame, bg="white")
        self.product_info_frame.pack(fill="x", padx=10, pady=5)
        self.lbl_current_product = tk.Label(self.product_info_frame, text="Cargando...", font=("Arial", 12), bg="white")
        self.lbl_current_product.pack(anchor="w", pady=2)
        self.lbl_expected_quantity = tk.Label(self.product_info_frame, text="Cantidad requerida: 0", font=("Arial", 12), bg="white")
        self.lbl_expected_quantity.pack(anchor="w", pady=2)
        self.lbl_scanned_count = tk.Label(self.product_info_frame, text="Escaneados: 0", font=("Arial", 12), bg="white")
        self.lbl_scanned_count.pack(anchor="w", pady=2)

        # Campo para ingresar el código de barras
        barcode_frame = tk.Frame(self.scanning_frame, bg="white")
        barcode_frame.pack(fill="x", padx=10, pady=5)
        lbl_barcode = tk.Label(barcode_frame, text="Código de Barras:", font=("Arial", 12), bg="white")
        lbl_barcode.pack(side="left")
        self.entry_barcode = tk.Entry(barcode_frame, font=("Arial", 12))
        self.entry_barcode.pack(side="left", padx=5)
        self.entry_barcode.bind("<Return>", self.on_barcode_enter)

        # Mensaje para feedback en el escaneo
        self.lbl_scan_message = tk.Label(self.scanning_frame, text="", font=("Arial", 12), bg="white", fg="blue")
        self.lbl_scan_message.pack(pady=5)

        # Área para mostrar órdenes confirmadas (si aplica)
        self.confirmed_orders_frame = tk.Frame(self.scanning_frame, bg="white")
        self.confirmed_orders_frame.pack(fill="both", padx=10, pady=5)

    def devolver(self):
        """Invoca el callback para volver a la vista de listado."""
        if self.on_back:
            self.on_back()

    def fetch_process_detail(self):
        """Consulta el API para obtener el detalle del proceso y actualiza la UI."""
        endpoint = API_ROUTES["PACKING_VIEW"].format(id=self.process_id)
        print(f"Consultando detalle en: {endpoint}")
        response = self.login_controller.api_client._make_get_request(endpoint)
        print("Detalle del proceso:", response)
        if not response or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener el detalle del proceso.")
            return

        data = response.get("data", {})
        process = data.get("process", {})

        # Actualiza la información del proceso
        self.lbl_nombre.config(text=f"Nombre: {process.get('name', 'N/A')}")
        self.lbl_iniciado.config(text=f"Iniciado: {process.get('started_at', 'N/A')}")
        finished_at = process.get("finished_at")
        finished_text = finished_at if finished_at else "En Proceso"
        self.lbl_finalizado.config(text=f"Finalizado: {finished_text}")
        creador = process.get("CreatedBy", {}).get("name", "N/A")
        self.lbl_creado_por.config(text=f"Creado por: {creador}")

        # Información del contenedor (derecha)
        picking = process.get("picking_process", {})
        containers = picking.get("containers", [])
        if containers:
            container_info = containers[0].get("container", {})  # La clave es "container"
            container_text = f"{container_info.get('bar_code', 'N/A')} - {container_info.get('name', 'N/A')}"
            self.lbl_container.config(text=f"Contenedor: {container_text}")
            barcode_value = container_info.get("bar_code", "")
        else:
            self.lbl_container.config(text="Contenedor: No hay contenedores asociados.")
            barcode_value = "Sin código"

        # Llamamos siempre a draw_barcode para dibujar el código (ya sea el real o el valor por defecto)
        self.draw_barcode(barcode_value)


        # Guarda el id de la orden pendiente (si se requiere confirmar)
        self.pending_process_order_id = process.get("pendingProcessOrder_id")

        # Cargar los productos pendientes para escaneo
        self.pending_products = data.get("pendingProducts", [])
        if self.pending_products:
            self.current_index = 0
            self.confirmed_orders = []
            self.update_scanning_ui()
        else:
            self.lbl_current_product.config(text="No hay productos pendientes para escanear.")

    def draw_barcode(self, barcode_value):
        """Dibuja un código de barras (simplificado) en el canvas."""
        self.canvas_barcode.delete("all")
        if barcode_value:
            # Se muestra simplemente el valor del código en el canvas.
            self.canvas_barcode.create_text(100, 50, text=barcode_value, font=("Arial", 16))
        else:
            self.canvas_barcode.create_text(100, 50, text="Sin código", font=("Arial", 12))

    def update_scanning_ui(self):
        """Actualiza la interfaz para mostrar el producto actual a escanear."""
        if self.current_index >= len(self.pending_products):
            self.lbl_current_product.config(text="Todos los productos han sido escaneados.")
            self.lbl_expected_quantity.config(text="Cantidad requerida: 0")
            self.lbl_scanned_count.config(text="Escaneados: 0")
            self.entry_barcode.config(state="disabled")
            self.confirm_orders()
            return

        current_product = self.pending_products[self.current_index]
        self.lbl_current_product.config(text=f"Producto: {current_product.get('name', '')}")
        self.expected_quantity = int(current_product.get("quantity", 0))
        self.scanned_count = 0
        self.lbl_expected_quantity.config(text=f"Cantidad requerida: {self.expected_quantity}")
        self.lbl_scanned_count.config(text=f"Escaneados: {self.scanned_count}")
        self.entry_barcode.config(state="normal")
        self.entry_barcode.delete(0, tk.END)
        self.entry_barcode.focus()
        self.lbl_scan_message.config(text="")

    def on_barcode_enter(self, event):
        """Valida el código de barras ingresado para el producto actual."""
        scanned_code = self.entry_barcode.get().strip()
        self.entry_barcode.delete(0, tk.END)
        current_product = self.pending_products[self.current_index]
        expected_code = current_product.get("bar_code", "")

        if scanned_code == expected_code:
            self.scanned_count += 1
            self.lbl_scanned_count.config(text=f"Escaneados: {self.scanned_count}")
            self.lbl_scan_message.config(text=f"Código correcto. Escaneados: {self.scanned_count} de {self.expected_quantity}", fg="green")
            if self.scanned_count >= self.expected_quantity:
                # Se agrega el producto a la lista de confirmados
                self.confirmed_orders.append({
                    "name": current_product.get("name", ""),
                    "quantity": self.expected_quantity
                })
                messagebox.showinfo("Producto Completado", f"{current_product.get('name', '')} ha sido completado.")
                self.current_index += 1
                self.after(500, self.update_scanning_ui)
        else:
            messagebox.showerror("Error", "Código incorrecto. Intente nuevamente.")

    def confirm_orders(self):
        """Envía la confirmación de la orden al API al terminar el escaneo."""
        if not self.pending_process_order_id:
            messagebox.showinfo("Confirmación", "No se requiere confirmar la orden.")
            return

        endpoint = API_ROUTES["PACKING_CONFIRM"].format(
            packingProcessOrder_id=self.pending_process_order_id,
            packingProcess_id=self.process_id
        )
        print("Confirmando orden en:", endpoint)
        payload = {"completedProducts": self.confirmed_orders}
        result = self.login_controller.api_client._make_post_request(endpoint, payload)
        if result and result.get("success"):
            orders_text = "\n".join([f"{p['name']} - Cantidad: {p['quantity']}" for p in self.confirmed_orders])
            messagebox.showinfo("Orden Confirmada", f"Órdenes confirmadas:\n{orders_text}")
        else:
            messagebox.showerror("Error", "Ocurrió un error al confirmar la orden.")
