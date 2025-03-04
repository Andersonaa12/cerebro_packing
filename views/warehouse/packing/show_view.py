import math
import os
import subprocess
import tempfile
import requests
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
import json  # [MODIFICADO] Para leer la config en JSON

import win32api  # [MODIFICADO] Se asume que estamos en Windows
import win32print  # [MODIFICADO]

# [NUEVO] Para manipular imágenes en Tkinter
from PIL import Image, ImageTk
from io import BytesIO

from config.settings import API_BASE_URL
from services.api_routes import API_ROUTES
from components.barcode_widget import create_barcode_widget
from assets.css.styles import PRIMARY_COLOR, BUTTON_STYLE

# [MODIFICADO] Archivo JSON donde se guarda la impresora seleccionada
JSON_CONFIG_FILE = "printer_config.json"


def load_printer_config():
    """
    Carga la impresora seleccionada desde un archivo JSON.
    Estructura esperada del JSON:
    {
        "selected_printer": "Nombre de la impresora"
    }
    """
    if not os.path.exists(JSON_CONFIG_FILE):
        # Si no existe el archivo, devolvemos None para usar la impresora por defecto
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
    Vista para mostrar el detalle del proceso de Packing, incluyendo:
      - Información general del proceso (nombre, fechas, usuario creador)
      - Datos del contenedor (si lo hubiera) y su código de barras
      - Panel para el escaneo de productos pendientes (con imagen del producto a la derecha)
      - Una tabla para listar las órdenes confirmadas con botón para ver detalles,
        con paginación y ordenamiento ascendente/descendente
      - Botón "Devolver" para regresar a la vista de listado
      - Al confirmar una orden, se descarga la etiqueta (archivo) a partir de la URL
        devuelta por la API, se imprime en la impresora configurada en printer_config.json
        y se elimina el archivo temporal. Si no existe 'label_url' en la respuesta,
        se informa al usuario que debe realizar el proceso desde la web, mostrando el Order ID.
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

        # [MODIFICADO] Cargamos la impresora seleccionada desde el JSON
        self.selected_printer = load_printer_config() or win32print.GetDefaultPrinter()
        print(f"[DEBUG] Impresora inicial (PackingShowView): {self.selected_printer}")

        # Variables para el escaneo
        self.pending_products = []
        self.confirmed_orders = []  # Lista de productos confirmados en la orden actual
        self.current_index = 0
        self.scanned_count = 0
        self.expected_quantity = 0

        # Variables para la tabla paginada y ordenada
        self.confirmed_orders_data = []  # Almacenará los datos de la tabla
        self.page_size = 10             # Registros por página
        self.current_page = 1
        self.total_pages = 1
        self.sort_directions = {}       # Para guardar la dirección de ordenamiento de cada columna

        # [NUEVO] Variable para guardar la imagen en Tk (para evitar que sea recolectada por el GC)
        self.product_image_tk = None

        self.create_widgets()
        self.fetch_process_detail()

    def show_list_view(self):
        """Callback para volver a la vista de listado."""
        self.destroy()
        from views.warehouse.packing.list_view import PackingListView
        list_view = PackingListView(master=self.master, login_controller=self.login_controller)
        list_view.pack(expand=True, fill="both")

    def draw_barcode(self, barcode_value):
        # Elimina widgets previos en el contenedor del código de barras
        for widget in self.canvas_barcode.winfo_children():
            widget.destroy()

        if barcode_value and barcode_value != "Sin código":
            # Crea el widget del código de barras y lo coloca dentro del canvas
            barcode_widget = create_barcode_widget(self.canvas_barcode, barcode_value)
            barcode_widget.pack(expand=True)
        else:
            # Si no hay código, muestra un mensaje
            label = tk.Label(self.canvas_barcode, text="Sin código", font=("Arial", 12), bg="white")
            label.pack(expand=True)

    def create_widgets(self):
        # Encabezado
        header_frame = tk.Frame(self, bg=PRIMARY_COLOR)
        header_frame.pack(fill="x", padx=10, pady=5)

        title_lbl = tk.Label(header_frame,
                             text="Detalle del Proceso - Packing",
                             font=("Arial", 16, "bold"),
                             bg=PRIMARY_COLOR,
                             fg="white")
        title_lbl.pack(side="left", padx=5)

        btn_container = tk.Frame(header_frame, bg=PRIMARY_COLOR, padx=5, pady=5)
        btn_container.pack(side="right", padx=2, pady=2)

        back_btn = tk.Button(btn_container,
                             text="Devolver",
                             command=self.show_list_view,
                             **BUTTON_STYLE)
        back_btn.pack()

        # Información del proceso y contenedor
        info_frame = tk.Frame(self, bg="white", bd=1, relief="solid")
        info_frame.pack(fill="x", padx=10, pady=5)

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

        right_frame = tk.Frame(info_frame, bg="white", bd=1, relief="solid")
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        self.lbl_container = tk.Label(right_frame, text="Contenedor: No hay contenedores asociados.", font=("Arial", 12), bg="white")
        self.lbl_container.pack(pady=10)
        self.canvas_barcode = tk.Canvas(right_frame, width=200, height=100, bg="white", highlightthickness=0)
        self.canvas_barcode.pack(pady=5)

        # Panel de escaneo (contenedor principal)
        self.scanning_frame = tk.Frame(self, bg="white", bd=1, relief="solid")
        self.scanning_frame.pack(fill="both", expand=True, padx=10, pady=10)

        scan_title = tk.Label(self.scanning_frame, text="Escaneo de Productos", font=("Arial", 14, "bold"), bg="white")
        scan_title.pack(pady=5)

        # [NUEVO] Frame interno para ubicar info del producto y la imagen lado a lado
        scanning_inner_frame = tk.Frame(self.scanning_frame, bg="white")
        scanning_inner_frame.pack(fill="x", expand=True, padx=10, pady=5)

        # Frame con la info de la orden/producto
        self.product_info_frame = tk.Frame(scanning_inner_frame, bg="white")
        self.product_info_frame.pack(side="left", fill="both", expand=True)

        self.lbl_current_product = tk.Label(self.product_info_frame, text="Cargando...", font=("Arial", 12), bg="white")
        self.lbl_current_product.pack(anchor="w", pady=2)
        self.lbl_expected_quantity = tk.Label(self.product_info_frame, text="Cantidad requerida: 0", font=("Arial", 12), bg="white")
        self.lbl_expected_quantity.pack(anchor="w", pady=2)
        self.lbl_scanned_count = tk.Label(self.product_info_frame, text="Escaneados: 0", font=("Arial", 12), bg="white")
        self.lbl_scanned_count.pack(anchor="w", pady=2)

        barcode_frame = tk.Frame(self.product_info_frame, bg="white")
        barcode_frame.pack(fill="x", pady=5)
        lbl_barcode = tk.Label(barcode_frame, text="Código de Barras:", font=("Arial", 12), bg="white")
        lbl_barcode.pack(side="left")
        self.entry_barcode = tk.Entry(barcode_frame, font=("Arial", 12))
        self.entry_barcode.pack(side="left", padx=5)
        self.entry_barcode.bind("<Return>", self.on_barcode_enter)

        self.lbl_scan_message = tk.Label(self.product_info_frame, text="", font=("Arial", 12), bg="white", fg="blue")
        self.lbl_scan_message.pack(pady=5)

        # [NUEVO] Frame para la imagen del producto
        self.product_image_frame = tk.Frame(scanning_inner_frame, bg="white", bd=1, relief="solid")
        self.product_image_frame.pack(side="right", fill="both", padx=10, pady=5)

        # Tabla de órdenes confirmadas
        confirmed_title = tk.Label(self.scanning_frame, text="Órdenes Confirmadas", font=("Arial", 14, "bold"), bg="white")
        confirmed_title.pack(pady=5)
        self.confirmed_orders_frame = tk.Frame(self.scanning_frame, bg="white")
        self.confirmed_orders_frame.pack(fill="both", padx=10, pady=5)
        self.create_confirmed_orders_table()

    def create_confirmed_orders_table(self):
        columns = ("Orden #", "Productos", "Inicio", "Fin", "Acciones")

        # Creamos el Treeview
        self.confirmed_tree = ttk.Treeview(
            self.confirmed_orders_frame,
            columns=columns,
            show="headings"
        )

        # Configuramos cada encabezado con la posibilidad de ordenar
        for col in columns:
            self.confirmed_tree.heading(col, text=col, command=lambda _col=col: self.sort_column(_col, False))
            self.confirmed_tree.column(col, anchor="center", width=150)
            self.sort_directions[col] = False  # Dirección de ordenamiento inicial

        # Creamos un scrollbar vertical
        scrollbar = ttk.Scrollbar(self.confirmed_orders_frame, orient="vertical", command=self.confirmed_tree.yview)
        self.confirmed_tree.configure(yscrollcommand=scrollbar.set)

        # Empaquetamos el scrollbar a la derecha, llenando todo el eje Y
        scrollbar.pack(side="right", fill="y")

        # Empaquetamos el Treeview expandiéndose y llenando todo el espacio disponible
        self.confirmed_tree.pack(expand=True, fill="both")

        # Vinculamos el evento de doble clic
        self.confirmed_tree.bind("<Double-1>", self.on_confirmed_order_double_click)


    @staticmethod
    def parse_date(date_str):
        try:
            # Se asume formato ISO; ajusta el formato si es necesario
            return datetime.fromisoformat(date_str)
        except Exception:
            # Si falla, retorna la fecha mínima para ordenar correctamente
            return datetime.min

    def sort_column(self, col, reverse):
        """
        Ordena los datos internos de la tabla (self.confirmed_orders_data) y refresca la página actual.
        """
        col_to_index = {
            "Orden #": 0,
            "Productos": 1,
            "Inicio": 2,
            "Fin": 3,
            "Acciones": 4
        }

        index = col_to_index.get(col)
        if index is None:
            return

        if col == "Orden #":
            try:
                self.confirmed_orders_data.sort(key=lambda t: int(t[index]), reverse=reverse)
            except ValueError:
                self.confirmed_orders_data.sort(key=lambda t: t[index], reverse=reverse)
        elif col in ("Inicio", "Fin"):
            self.confirmed_orders_data.sort(key=lambda t: PackingShowView.parse_date(t[index]), reverse=reverse)
        else:
            self.confirmed_orders_data.sort(key=lambda t: t[index], reverse=reverse)

        self.sort_directions[col] = not reverse
        self.refresh_table_page()

    def devolver(self):
        if self.on_back:
            self.on_back()

    def fetch_process_detail(self):
        endpoint = API_ROUTES["PACKING_VIEW"].format(id=self.process_id)
        print(f"[DEBUG] Consultando detalle en: {endpoint}")
        response = self.login_controller.api_client._make_get_request(endpoint)
        print("[DEBUG] Detalle del proceso:", response)
        if not response or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener el detalle del proceso.")
            return

        data = response.get("data", {})
        process = data.get("process", {})

        # Actualización de información del proceso
        self.lbl_nombre.config(text=f"Nombre: {process.get('name', 'N/A')}")
        self.lbl_iniciado.config(text=f"Iniciado: {process.get('started_at', 'N/A')}")
        finished_at = process.get("finished_at")
        finished_text = finished_at if finished_at else "En Proceso"
        self.lbl_finalizado.config(text=f"Finalizado: {finished_text}")
        # Ojo: la API envía "updated_by" / "CreatedBy", según tu ejemplo
        creador = process.get("created_by", "N/A")
        if isinstance(creador, dict):
            creador = creador.get("name", "N/A")
        self.lbl_creado_por.config(text=f"Creado por: {creador}")

        # Información del contenedor
        picking = process.get("picking_process", {})
        containers = picking.get("containers", [])
        if containers:
            container_info = containers[0].get("container", {})
            container_text = f"{container_info.get('bar_code', 'N/A')} - {container_info.get('name', 'N/A')}"
            self.lbl_container.config(text=f"{container_text}")
            barcode_value = container_info.get("bar_code", "")
        else:
            self.lbl_container.config(text="Contenedor: No hay contenedores asociados.")
            barcode_value = "Sin código"
        self.draw_barcode(barcode_value)

        # Verificar si el proceso ha finalizado
        packing_orders = process.get("packing_process_orders", [])
        all_orders_finished = (len(packing_orders) > 0 and all(o.get("finished_at") for o in packing_orders))
        if finished_at or all_orders_finished:
            self.lbl_current_product.config(text="El proceso de packing ha finalizado.")
            self.entry_barcode.config(state="disabled")
            self.update_confirmed_orders_table(data.get("confirmedOrders", {}))
            return

        # Determinar la orden pendiente actual
        self.pending_process_order = data.get("pendingProcessOrder")
        if not self.pending_process_order and packing_orders:
            self.pending_process_order = packing_orders[0]

        # [MODIFICADO] Actualizar los productos pendientes de la orden actual
        #  Según tu ejemplo, en "data" viene un array "pendingProducts" con la estructura:
        #  {"id", "name", "bar_code", "quantity", "image_url", ...}
        self.pending_products = data.get("pendingProducts", [])
        self.current_index = 0
        self.confirmed_orders = []  # Reiniciamos los productos confirmados para la orden actual

        if self.pending_products:
            self.update_scanning_ui()
        else:
            self.lbl_current_product.config(text="No hay productos pendientes para escanear.")

        # Actualizar la tabla de órdenes confirmadas usando confirmedOrders
        self.update_confirmed_orders_table(data.get("confirmedOrders", {}))

    def update_scanning_ui(self):
        """Actualiza la interfaz de escaneo con la info del producto actual y su imagen."""
        if self.current_index >= len(self.pending_products):
            self.lbl_current_product.config(text="Todos los productos han sido escaneados.")
            self.lbl_expected_quantity.config(text="Cantidad requerida: 0")
            self.lbl_scanned_count.config(text="Escaneados: 0")
            self.entry_barcode.config(state="disabled")
            # Confirmar la orden una vez completado el escaneo
            self.confirm_orders()
            return

        current_product = self.pending_products[self.current_index]
        product_name = current_product.get("name", "")
        self.lbl_current_product.config(text=f"Producto: {product_name}")
        self.expected_quantity = int(current_product.get("quantity", 0))
        self.scanned_count = 0
        self.lbl_expected_quantity.config(text=f"Cantidad requerida: {self.expected_quantity}")
        self.lbl_scanned_count.config(text=f"Escaneados: {self.scanned_count}")
        self.entry_barcode.config(state="normal")
        self.entry_barcode.delete(0, tk.END)
        self.entry_barcode.focus()
        self.lbl_scan_message.config(text="")

        # [NUEVO] Cargar la imagen del producto
        image_url = current_product.get("image_url")
        self.show_product_image(image_url)

    def show_product_image(self, url):
        """
        Descarga y muestra la imagen del producto dentro de self.product_image_frame.
        Si no hay URL o falla la descarga, muestra un texto indicando que no se pudo cargar.
        """
        # Limpiamos el frame de cualquier imagen previa
        for widget in self.product_image_frame.winfo_children():
            widget.destroy()

        if not url:
            # No hay URL, mostrar mensaje
            label = tk.Label(self.product_image_frame, text="Sin imagen", font=("Arial", 12), bg="white")
            label.pack(expand=True)
            return

        # Intentar descargar la imagen
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            image_data = resp.content

            pil_image = Image.open(BytesIO(image_data))
            
            # Redimensionar la imagen a 200x200 (cambia a tu gusto)
            pil_image = pil_image.resize((150, 150), Image.Resampling.LANCZOS)

            self.product_image_tk = ImageTk.PhotoImage(pil_image)
            img_label = tk.Label(self.product_image_frame,
                                image=self.product_image_tk,
                                borderwidth=2,
                                relief="solid",
                                bg="white")
            img_label.pack(expand=True, padx=5, pady=5)
        except Exception as e:
            # Fallback si falla la descarga
            print(f"[DEBUG] No se pudo cargar la imagen: {e}")
            label = tk.Label(self.product_image_frame, text="No se pudo cargar la imagen", font=("Arial", 12), bg="white")
            label.pack(expand=True)


    def on_barcode_enter(self, event):
        scanned_code = self.entry_barcode.get().strip()
        self.entry_barcode.delete(0, tk.END)
        current_product = self.pending_products[self.current_index]
        expected_code = current_product.get("bar_code", "")
        print(f"[DEBUG] Escaneado: {scanned_code} | Esperado: {expected_code}")

        if scanned_code == expected_code:
            self.scanned_count += 1
            self.lbl_scanned_count.config(text=f"Escaneados: {self.scanned_count}")
            self.lbl_scan_message.config(text=f"Código correcto. Escaneados: {self.scanned_count} de {self.expected_quantity}", fg="green")
            print(f"[DEBUG] Producto '{current_product.get('name', '')}' escaneado correctamente ({self.scanned_count}/{self.expected_quantity})")
            if self.scanned_count >= self.expected_quantity:
                self.confirmed_orders.append({
                    "name": current_product.get("name", ""),
                    "quantity": self.expected_quantity
                })
                messagebox.showinfo("Producto Completado", f"{current_product.get('name', '')} ha sido completado.")
                self.current_index += 1
                self.after(500, self.update_scanning_ui)
        else:
            print(f"[DEBUG] Código incorrecto para el producto '{current_product.get('name', '')}'.")
            messagebox.showerror("Error", "Código incorrecto. Intente nuevamente.")

    def confirm_orders(self):
        """
        Envía la confirmación de la orden a la API.
        Si la respuesta incluye 'label_url', se descarga la etiqueta, se imprime y se elimina el archivo temporal.
        Si no incluye 'label_url', se informa al usuario que debe realizar el proceso desde la web, mostrando el Order ID.
        """
        endpoint = API_ROUTES["PACKING_CONFIRM"].format(
            packingProcessOrder_id=self.pending_process_order.get("id"),
            packingProcess_id=self.process_id
        )
        print(f"[DEBUG] Confirmando orden en: {endpoint}")
        payload = {"completedProducts": self.confirmed_orders}
        print(f"[DEBUG] Payload de confirmación: {payload}")
        result = self.login_controller.api_client._make_post_request(endpoint, payload)
        if result and result.get("success"):
            orders_text = "\n".join([f"{p['name']} - Cantidad: {p['quantity']}" for p in self.confirmed_orders])
            messagebox.showinfo("Orden Confirmada", f"Órdenes confirmadas:\n{orders_text}")
            print("[DEBUG] Orden confirmada con éxito.")
            finished_at = result.get("data", {}).get("finished_at")
            if finished_at:
                self.lbl_finalizado.config(text=f"Finalizado: {finished_at}")
                messagebox.showinfo("Proceso Finalizado", "El proceso de packing ha finalizado.")
            label_url = result.get("label_url")
            if label_url:
                self.download_and_print_label(label_url)
            else:
                # Si no hay label_url, se informa al usuario y se pasa el order_id
                order_id = self.pending_process_order.get("order_id", "N/A")
                messagebox.showinfo("Acción Requerida",
                                    f"La etiqueta no se generó para impresión.\n"
                                    f"Por favor, realice el proceso desde la web con el Order ID: {order_id}")
            self.fetch_process_detail()
        else:
            messagebox.showerror("Error", "Ocurrió un error al confirmar la orden.")
            print("[DEBUG] Error al confirmar la orden.")

    def download_and_print_label(self, label_url):
        """
        Descarga el archivo de la etiqueta desde label_url, lo guarda en un archivo temporal,
        luego llama a self.print_document() para enviarlo a imprimir, y finalmente elimina el archivo temporal.
        """
        try:
            response = requests.get(label_url)
            if response.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(response.content)
                    temp_filename = tmp_file.name
                print(f"[DEBUG] Archivo temporal para etiqueta: {temp_filename}")
                self.print_document(temp_filename)
                os.remove(temp_filename)
            else:
                messagebox.showerror("Error", "No se pudo descargar la etiqueta para impresión.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al imprimir la etiqueta: {str(e)}")

    def print_document(self, file_path):
        """
        [MODIFICADO] Imprime el documento especificado usando la impresora seleccionada.
        """
        try:
            print(f"[DEBUG] Enviando {file_path} a la impresora: {self.selected_printer}")
            win32api.ShellExecute(0, "print", file_path, f'/d:"{self.selected_printer}"', ".", 0)
            messagebox.showinfo("Impresión", f"Documento enviado a {self.selected_printer}")
        except Exception as e:
            print(f"[DEBUG] Error al imprimir: {e}")
            messagebox.showerror("Error", f"Error al imprimir: {str(e)}")

    def update_confirmed_orders_table(self, confirmed):
        """
        Actualiza la tabla de órdenes confirmadas usando el diccionario confirmedOrders,
        configura la paginación y refresca la vista.
        """
        # Limpiar datos anteriores
        self.confirmed_orders_data = []
        # Si no hay órdenes confirmadas, mostrar una fila indicándolo
        if not confirmed:
            self.confirmed_orders_data.append(("Sin órdenes confirmadas", "", "", "", ""))
        else:
            for key, order in confirmed.items():
                order_id = order.get("order_id", "")
                products = order.get("products", [])
                prod_text = "; ".join([f"{p.get('name', '')} ({p.get('quantity', 0)})" for p in products])
                started_at = order.get("started_at", "-----")
                finished_at = order.get("finished_at", "Sin Finalizar")
                actions = "Ver Detalle"
                self.confirmed_orders_data.append((order_id, prod_text, started_at, finished_at, actions))

        # Configurar parámetros de paginación
        self.current_page = 1
        self.total_pages = (
            math.ceil(len(self.confirmed_orders_data) / self.page_size)
            if self.confirmed_orders_data else 1
        )

        self.refresh_table_page()
        self.create_pagination_controls()

    def refresh_table_page(self):
        """Refresca la tabla mostrando solo los datos de la página actual."""
        # Limpiar la tabla
        for row in self.confirmed_tree.get_children():
            self.confirmed_tree.delete(row)

        # Calcular el rango de índices para la página actual
        start_index = (self.current_page - 1) * self.page_size
        end_index = start_index + self.page_size
        page_data = self.confirmed_orders_data[start_index:end_index]

        # Insertar los datos de la página actual en la tabla
        for data in page_data:
            self.confirmed_tree.insert("", "end", values=data)

        # Actualizar la etiqueta de paginación (si existe)
        if hasattr(self, 'lbl_page_info'):
            self.lbl_page_info.config(text=f"Página {self.current_page} de {self.total_pages}")

    def create_pagination_controls(self):
        """Crea los controles de navegación para la paginación (botones y etiqueta)."""
        if not hasattr(self, 'pagination_frame'):
            self.pagination_frame = tk.Frame(self.scanning_frame, bg="white")
            self.pagination_frame.pack(fill="x", padx=10, pady=5)

            prev_btn = tk.Button(self.pagination_frame, text="Anterior", command=self.previous_page, **BUTTON_STYLE)
            prev_btn.pack(side="left", padx=5)

            self.lbl_page_info = tk.Label(self.pagination_frame, text="", font=("Arial", 12), bg="white")
            self.lbl_page_info.pack(side="left", padx=5)

            next_btn = tk.Button(self.pagination_frame, text="Siguiente", command=self.next_page, **BUTTON_STYLE)
            next_btn.pack(side="left", padx=5)

    def previous_page(self):
        """Navega a la página anterior si es posible."""
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_table_page()

    def next_page(self):
        """Navega a la siguiente página si es posible."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.refresh_table_page()

    def on_confirmed_order_double_click(self, event):
        """
        Al hacer doble clic en una orden confirmada, se llama al API GET_ORDER para obtener
        los detalles relevantes y se muestran en una ventana emergente.
        """
        try:
            item_id = self.confirmed_tree.selection()[0]
        except IndexError:
            messagebox.showerror("Error", "No se ha seleccionado ninguna orden confirmada.")
            return
        item = self.confirmed_tree.item(item_id)
        values = item["values"]
        order_id = values[0]
        self.show_order_detail(order_id)

    def show_order_detail(self, order_id):
        """
        Llama al endpoint GET_ORDER para obtener los detalles de la orden y los muestra en
        una ventana Toplevel.
        """
        endpoint = API_ROUTES["GET_ORDER"].format(id=order_id)
        print(f"[DEBUG] Obteniendo detalle de la orden en: {endpoint}")
        response = self.login_controller.api_client._make_get_request(endpoint)
        if not response or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener el detalle de la orden.")
            return
        data = response.get("data", [])
        if not data:
            messagebox.showinfo("Detalle Orden", "No hay datos disponibles para esta orden.")
            return
        # Se asume que la respuesta es una lista con un único elemento
        order = data[0]
        # Construir un string con los datos relevantes
        detail = f"Orden ID: {order.get('id', '')}\n"
        detail += f"Nombre: {order.get('name', '')}\n"
        detail += f"Email: {order.get('email', '')}\n"
        detail += f"Teléfono: {order.get('phone', '')}\n"
        detail += f"Dirección: {order.get('address', '')}\n"
        detail += f"Ciudad: {order.get('city', '')}\n"
        detail += f"Provincia: {order.get('province', '')}\n"
        detail += f"País: {order.get('country_code', '')}\n"
        detail += f"Confirmado: {order.get('confirmed_at', '')}\n"
        detail += f"Fulfilled: {order.get('fulfilled_at', '')}\n"
        lines = order.get("lines", [])
        if lines:
            detail += "\nLíneas:\n"
            for line in lines:
                detail += f"Producto: {line.get('product_name', '')} | Cantidad: {line.get('quantity', '')}\n"

        # Mostrar los detalles en una ventana Toplevel
        top = tk.Toplevel(self)
        top.title(f"Detalle de la Orden {order_id}")
        text = tk.Text(top, wrap="word", font=("Arial", 12))
        text.insert("1.0", detail)
        text.config(state="disabled")
        text.pack(expand=True, fill="both", padx=10, pady=10)

        close_btn = tk.Button(top, text="Cerrar", command=top.destroy, **BUTTON_STYLE)
        close_btn.pack(pady=5)


# NOTA: Si lo ejecutas directamente, puedes hacer pruebas, pero normalmente
#       esta vista se navega desde la vista principal en tu aplicación real.
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Packing Show View")
    root.geometry("1000x700")

    # A modo de ejemplo, pasamos process_id y login_controller nulos.
    # En tu aplicación real, debes pasarles los objetos adecuados.
    app = PackingShowView(master=root, process_id=123, login_controller=None)
    app.pack(expand=True, fill="both")

    root.mainloop()
