import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import subprocess  # Se usará para ejecutar el comando WMIC

from assets.css.styles import PRIMARY_COLOR, BACKGROUND_COLOR_VIEWS, LABEL_STYLE, BUTTON_STYLE
from config.settings import API_BASE_URL
from services.api_routes import API_ROUTES
from components.header import Header
from components.barcode_widget import create_barcode_widget  # Se utiliza para mostrar el código de barras

# Estilo extra para centrar texto en las etiquetas.
CENTERED_LABEL_STYLE = {
    "bg": "white",
    "font": ("Arial", 10),
    "anchor": "center",
    "justify": "center"
}

class PackingListView(tk.Frame):
    """
    Vista para listar los procesos de Packing y mostrar los procesos de Picking en espera.
    Al ingresar a la vista se verifica automáticamente el estado de la impresora Zebra (ZD220)
    y se muestra un botón para validar la conexión, junto con una etiqueta que indica el estado.
    """
    def __init__(self, master=None, user_data=None, login_controller=None, on_logout=None):
        """
        :param master: ventana o frame padre.
        :param user_data: diccionario con datos del usuario (ej: {"name": "Almacén"}).
        :param login_controller: instancia de LoginController con el ApiClient autenticado.
        :param on_logout: callback para redirigir al LoginView al cerrar sesión.
        """
        super().__init__(master, bg=BACKGROUND_COLOR_VIEWS)
        self.master = master
        self.user_data = user_data or {}
        self.login_controller = login_controller
        self.on_logout = on_logout

        self.pack(expand=True, fill="both")
        self.create_widgets()
        self.fetch_and_populate()
        # Realizar verificación de impresora automáticamente al entrar a la vista
        self.after(100, self.validate_printer)

    def create_widgets(self):
        # Encabezado
        header_frame = tk.Frame(self, bg=PRIMARY_COLOR)
        header_frame.pack(fill="x", padx=10, pady=5)

        title_lbl = tk.Label(
            header_frame,
            text="Listado de Procesos - Packing",
            font=("Arial", 16, "bold"),
            bg=PRIMARY_COLOR,
            fg="white"
        )
        title_lbl.pack(side="left", padx=5)

        my_header = Header(
            master=header_frame,
            controller=self.login_controller,
            on_logout_callback=self.handle_logout  # Se asigna el callback de logout
        )
        my_header.pack(side="right")

        # Panel para verificación de impresora Zebra
        printer_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        printer_frame.pack(fill="x", padx=10, pady=5)
        
        self.printer_button = tk.Button(
            printer_frame,
            text="Validar Impresora Zebra",
            command=self.validate_printer,
            **BUTTON_STYLE
        )
        self.printer_button.pack(side="left", padx=5)
        
        self.printer_status_lbl = tk.Label(
            printer_frame,
            text="",
            font=("Arial", 12),
            bg=BACKGROUND_COLOR_VIEWS
        )
        self.printer_status_lbl.pack(side="left", padx=5)

        # Panel de búsqueda (por nombre)
        search_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        search_frame.pack(fill="x", padx=10, pady=5)

        search_lbl = tk.Label(
            search_frame,
            text="Buscar por nombre:",
            font=("Arial", 12),
            bg=BACKGROUND_COLOR_VIEWS
        )
        search_lbl.pack(side="left", padx=5)

        self.search_entry = tk.Entry(search_frame, font=("Arial", 12))
        self.search_entry.pack(side="left", padx=5)

        search_btn = tk.Button(
            search_frame,
            text="Buscar",
            command=self.search,
            **BUTTON_STYLE
        )
        search_btn.pack(side="left", padx=5)

        # Contenedor principal con dos columnas
        main_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        # Tabla de procesos de packing (columna izquierda)
        left_frame = tk.Frame(main_frame, bg="white", bd=1, relief="solid")
        left_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.create_table(left_frame)

        # Panel de picking en espera (columna derecha) – widget más angosto
        right_frame = tk.Frame(main_frame, bg="white", bd=1, relief="solid")
        right_frame.pack(side="right", fill="y", padx=5)
        self.create_waiting_panel(right_frame)

    def validate_printer(self):
        """
        Método para validar si la impresora Zebra (ZD220) está activa y conectada.
        Actualiza la etiqueta de estado debajo del botón.
        """
        is_active = self.check_printer_status()
        if is_active:
            self.printer_status_lbl.config(text="Activa", fg="green")
        else:
            self.printer_status_lbl.config(text="Inactiva", fg="red")

    def check_printer_status(self):
        """
        Verifica si la impresora Zebra ZD220 está conectada vía USB usando el comando WMIC.
        Se buscan dispositivos cuyo PNPDeviceID contenga los IDs típicos de Zebra:
        Vendor: 0A5F y Product: 0044.
        
        Esta solución funciona en Windows sin necesidad de librerías externas.
        """
        VENDOR_ID = "0A5F"
        PRODUCT_ID = "0044"
        try:
            # Ejecuta el comando WMIC para buscar dispositivos con los IDs indicados
            cmd = (
                'wmic path Win32_PnPEntity where "PNPDeviceID like \'%VID_{0}&PID_{1}%\'" get Name'
                .format(VENDOR_ID, PRODUCT_ID)
            )
            output = subprocess.check_output(cmd, shell=True, universal_newlines=True)
            # Se filtra la salida (se ignora la cabecera y líneas vacías)
            lines = [line.strip() for line in output.splitlines() if line.strip() and "Name" not in line]
            return len(lines) > 0
        except Exception as e:
            print("Error al verificar la impresora:", e)
            return False

    def create_table(self, parent):
        columns = ("#", "Nombre", "Fecha Inicio", "Fecha Fin", "Estado", "Usuario", "Acciones")
        self.tree = ttk.Treeview(parent, columns=columns, show="headings")

        for col in columns:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, anchor="center", width=100)

        self.tree.pack(expand=True, fill="both", padx=5, pady=5)
        self.tree.bind("<Double-1>", self.on_row_double_click)

    def create_waiting_panel(self, parent):
        title = tk.Label(
            parent,
            text="Procesos de Picking - En espera",
            font=("Arial", 14, "bold"),
            bg="white"
        )
        title.pack(pady=10)

        # Panel para ingresar el código de barras (creación directa del proceso)
        barcode_frame = tk.Frame(parent, bg="white")
        barcode_frame.pack(fill="x", padx=5, pady=5)

        barcode_lbl = tk.Label(
            barcode_frame,
            text="Código de cesta:",
            font=("Arial", 12),
            bg="white"
        )
        barcode_lbl.pack(side="left", padx=5)

        self.barcode_entry = tk.Entry(barcode_frame, font=("Arial", 12))
        self.barcode_entry.pack(side="left", padx=5)
        # Al presionar Enter se crea el proceso de packing directamente
        self.barcode_entry.bind("<Return>", lambda event: self.search_by_barcode())

        barcode_btn = tk.Button(
            barcode_frame,
            text="Crear Proceso",
            command=self.search_by_barcode,
            **BUTTON_STYLE
        )
        barcode_btn.pack(side="left", padx=5)

        # Canvas con scrollbar para mostrar los procesos de picking en espera
        self.waiting_canvas = tk.Canvas(parent, bg="white", width=200)
        self.waiting_canvas.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(parent, orient="vertical", command=self.waiting_canvas.yview)
        scrollbar.pack(side="right", fill="y")

        self.waiting_canvas.configure(yscrollcommand=scrollbar.set)

        self.waiting_frame = tk.Frame(self.waiting_canvas, bg="white")
        self.waiting_canvas.create_window((0, 0), window=self.waiting_frame, anchor="nw")

        self.waiting_frame.bind(
            "<Configure>",
            lambda e: self.waiting_canvas.configure(scrollregion=self.waiting_canvas.bbox("all"))
        )

    def fetch_and_populate(self):
        # Obtener procesos de packing
        print("Solicitando procesos de packing...")
        response = self.login_controller.api_client._make_get_request(API_ROUTES["PACKING_LIST"])
        print("Respuesta de packing:", response)

        if response is None or not isinstance(response, dict) or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener el listado de procesos.")
            return

        data = response.get("data", {})
        packing_obj = data.get("packing_processes", {})
        processes = packing_obj.get("data", [])
        print("Procesos de packing obtenidos:", processes)

        # Limpiamos la tabla
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Insertamos nuevos registros en la tabla
        for process in processes:
            pid = process.get("id", "")
            name = process.get("name", "")
            started_at = process.get("started_at", "")
            finished_at = process.get("finished_at", "")
            status = "Proceso Finalizado" if finished_at else "Packing - En Proceso"
            user = process.get("created_by", {}).get("name", "")
            actions = "Ver Proceso"
            self.tree.insert("", "end", values=(pid, name, started_at, finished_at, status, user, actions))

        self.populate_waiting_panel()

    def populate_waiting_panel(self):
        # Limpiar el frame interno del canvas
        for widget in self.waiting_frame.winfo_children():
            widget.destroy()

        print("Solicitando procesos de picking en espera...")
        waiting_response = self.login_controller.api_client._make_get_request(API_ROUTES["PACKING_LIST"])
        print("Respuesta de picking en espera:", waiting_response)

        waiting_data = []
        if waiting_response and isinstance(waiting_response, dict):
            data = waiting_response.get("data", {})
            waiting_data = data.get("picking_processes", [])

        self.waiting_data = waiting_data

        if not waiting_data:
            print("No se han encontrado procesos de picking en espera.")
            no_content_label = tk.Label(
                self.waiting_frame,
                text="No hay procesos de picking en espera.",
                bg="white",
                font=("Arial", 10),
                anchor="center",
                justify="center"
            )
            no_content_label.pack(pady=10)
            return
        else:
            print("Procesos de picking en espera obtenidos:", waiting_data)

        # Mostramos cada proceso en un frame independiente
        for process in waiting_data:
            item_frame = tk.Frame(self.waiting_frame, bg="white", bd=1, relief="solid")
            item_frame.pack(fill="x", pady=5, padx=5)

            name_lbl = tk.Label(
                item_frame,
                text=f"Nombre: {process.get('name', '')}",
                **CENTERED_LABEL_STYLE
            )
            name_lbl.pack(anchor="center", padx=5, pady=2)

            orders_lbl = tk.Label(
                item_frame,
                text=f"# Órdenes: {process.get('num_ordenes', 0)}",
                **CENTERED_LABEL_STYLE
            )
            orders_lbl.pack(anchor="center", padx=5, pady=2)

            codes = ", ".join([c.get("container", {}).get("bar_code", "")
                               for c in process.get("containers", [])])
            codes_lbl = tk.Label(
                item_frame,
                text=f"Código de cesta: {codes}",
                **CENTERED_LABEL_STYLE
            )
            codes_lbl.pack(anchor="center", padx=5, pady=2)

            if process.get("containers"):
                first_barcode = process.get("containers")[0].get("container", {}).get("bar_code", "")
                if first_barcode:
                    barcode_w = create_barcode_widget(item_frame, first_barcode)
                    barcode_w.pack(anchor="center", padx=5, pady=5)

            btn_start = tk.Button(
                item_frame,
                text="Iniciar Proceso - Packing",
                command=lambda p=process: self.start_packing(p),
                **BUTTON_STYLE
            )
            btn_start.pack(anchor="center", padx=5, pady=5)

    def search_by_barcode(self):
        barcode_value = self.barcode_entry.get().strip()
        if not barcode_value:
            messagebox.showwarning("Advertencia", "Por favor ingresa un código de barras.")
            return

        print(f"Buscando proceso de picking con código de barras: {barcode_value}")
        process_to_pack = None
        for process in self.waiting_data:
            containers = process.get("containers", [])
            for container in containers:
                bar_code = container.get("container", {}).get("bar_code", "")
                if bar_code == barcode_value:
                    process_to_pack = process
                    break
            if process_to_pack:
                break

        if not process_to_pack:
            messagebox.showerror("Error", f"No se encontró proceso de picking con el código de barras: {barcode_value}.")
            return

        process_id = process_to_pack.get("id")
        print(f"Creando proceso de packing para el id del proceso de picking: {process_id}")

        endpoint = API_ROUTES["PACKING_CREATE"].format(id=process_id)
        result = self.login_controller.api_client._make_post_request(endpoint, {})

        if result:
            messagebox.showinfo("Proceso Iniciado", f"Se inició el proceso de packing para el proceso id {process_id}.")
            self.fetch_and_populate()
        else:
            messagebox.showerror("Error", "No se pudo iniciar el proceso de packing.")

    def search(self):
        query = self.search_entry.get().strip()
        print(f"Buscando procesos con query: {query}")
        url = f"{API_ROUTES['PACKING_LIST']}?q={query}"
        response = self.login_controller.api_client._make_get_request(url)
        print("Respuesta de búsqueda:", response)

        if response is None or not isinstance(response, dict) or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener los resultados de búsqueda.")
            return

        data = response.get("data", {})
        packing_obj = data.get("packing_processes", {})
        processes = packing_obj.get("data", [])
        print("Procesos encontrados:", processes)

        for row in self.tree.get_children():
            self.tree.delete(row)

        for process in processes:
            pid = process.get("id", "")
            name = process.get("name", "")
            started_at = process.get("started_at", "")
            finished_at = process.get("finished_at", "")
            status = "Proceso Finalizado" if finished_at else "Packing - En Proceso"
            user = process.get("created_by", {}).get("name", "")
            actions = "Ver Proceso"
            self.tree.insert("", "end", values=(pid, name, started_at, finished_at, status, user, actions))

    def start_packing(self, process):
        process_id = process.get("id")
        print(f"Iniciando proceso de packing para id: {process_id}")
        endpoint = API_ROUTES["PACKING_CREATE"].format(id=process_id)
        result = self.login_controller.api_client._make_post_request(endpoint, {})
        print("Resultado de iniciar packing:", result)

        if result:
            messagebox.showinfo("Proceso Iniciado", f"Se inició el proceso de packing para {process.get('name')}.")
            self.fetch_and_populate()
        else:
            messagebox.showerror("Error", "No se pudo iniciar el proceso de packing.")

    def on_row_double_click(self, event):
        try:
            item_id = self.tree.selection()[0]
        except IndexError:
            print("No se ha seleccionado ningún elemento.")
            return

        item = self.tree.item(item_id)
        values = item["values"]
        process_id = values[0]
        print(f"Mostrando detalles para el proceso id: {process_id}")
        self.on_show_detail(process_id)

    def on_show_detail(self, process_id):
        self.destroy()
        from views.warehouse.packing.show_view import PackingShowView
        detail_view = PackingShowView(
            master=self.master,
            process_id=process_id,
            login_controller=self.login_controller,
            on_back=self.show_list_view
        )
        detail_view.pack(expand=True, fill="both")

    def show_list_view(self):
        for widget in self.master.winfo_children():
            widget.destroy()
        from views.warehouse.packing.list_view import PackingListView
        list_view = PackingListView(master=self.master, login_controller=self.login_controller)
        list_view.pack(expand=True, fill="both")
    
    def handle_logout(self):
        """
        Función que se ejecuta al cerrar sesión.
        Destruye la ventana actual y llama al callback de logout para mostrar el login.
        """
        # Destruir todos los widgets de la ventana principal
        for widget in self.master.winfo_children():
            widget.destroy()
        if self.on_logout:
            self.on_logout()
