import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from assets.css.styles import PRIMARY_COLOR, BACKGROUND_COLOR_VIEWS, LABEL_STYLE, BUTTON_STYLE
from config.settings import API_BASE_URL
from services.api_routes import API_ROUTES

class PackingListView(tk.Frame):
    """
    Vista para listar los procesos de Packing y mostrar los procesos de Picking en espera.
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

    def create_widgets(self):
        # Encabezado con título y formulario de búsqueda
        header_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        header_frame.pack(fill="x", padx=10, pady=5)
        title_lbl = tk.Label(header_frame, text="Listado de Procesos - Packing", font=("Arial", 16, "bold"), bg=BACKGROUND_COLOR_VIEWS)
        title_lbl.pack(side="left")

        search_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        search_frame.pack(fill="x", padx=10, pady=5)
        search_lbl = tk.Label(search_frame, text="Buscar por nombre:", font=("Arial", 12), bg=BACKGROUND_COLOR_VIEWS)
        search_lbl.pack(side="left", padx=5)
        self.search_entry = tk.Entry(search_frame, font=("Arial", 12))
        self.search_entry.pack(side="left", padx=5)
        search_btn = tk.Button(search_frame, text="Buscar", font=("Arial", 12), command=self.search)
        search_btn.pack(side="left", padx=5)

        # Contenedor principal: dos columnas
        main_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        # Columna izquierda: tabla de procesos
        left_frame = tk.Frame(main_frame, bg="white", bd=1, relief="solid")
        left_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.create_table(left_frame)

        # Columna derecha: panel de procesos de Picking en espera
        right_frame = tk.Frame(main_frame, bg="white", bd=1, relief="solid")
        right_frame.pack(side="right", fill="both", expand=True, padx=5)
        self.create_waiting_panel(right_frame)

    def create_table(self, parent):
        columns = ("#", "Nombre", "Fecha Inicio", "Fecha Fin", "Estado", "Usuario", "Acciones")
        self.tree = ttk.Treeview(parent, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, anchor="center", width=100)
        self.tree.pack(expand=True, fill="both", padx=5, pady=5)
        self.tree.bind("<Double-1>", self.on_row_double_click)

    def create_waiting_panel(self, parent):
        title = tk.Label(parent, text="Procesos de Picking - En espera", font=("Arial", 14, "bold"), bg="white")
        title.pack(pady=10)
        self.waiting_frame = tk.Frame(parent, bg="white")
        self.waiting_frame.pack(expand=True, fill="both", padx=5, pady=5)

    def fetch_and_populate(self):
        # Llama al controlador para obtener el listado de procesos de packing
        print("Solicitando procesos de packing...")
        response = self.login_controller.api_client._make_get_request(API_ROUTES["PACKING_LIST"])
        print("Respuesta de packing:", response)
        if response is None or not isinstance(response, dict) or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener el listado de procesos.")
            return

        # Extraer la lista de procesos desde la estructura anidada
        data = response.get("data", {})
        packing_obj = data.get("packing_processes", {})
        processes = packing_obj.get("data", [])
        print("Procesos de packing obtenidos:", processes)

        # Limpiar la tabla
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Insertar los datos en la tabla
        for process in processes:
            pid = process.get("id", "")
            name = process.get("name", "")
            started_at = process.get("started_at", "")
            finished_at = process.get("finished_at", "")
            status = "Proceso Finalizado" if finished_at else "Packing - En Proceso"
            user = process.get("created_by", {}).get("name", "")  # Ajusta si la API no retorna info de usuario
            actions = "Ver Proceso"
            self.tree.insert("", "end", values=(pid, name, started_at, finished_at, status, user, actions))

        # Actualizar el panel de procesos de picking en espera
        self.populate_waiting_panel()

    def populate_waiting_panel(self):
        for widget in self.waiting_frame.winfo_children():
            widget.destroy()

        print("Solicitando procesos de picking en espera...")
        waiting_response = self.login_controller.api_client._make_get_request(API_ROUTES.get("PACKING_LIST_WAITING", ""))
        print("Respuesta de picking en espera:", waiting_response)
        waiting_data = []
        if waiting_response and isinstance(waiting_response, dict):
            data = waiting_response.get("data", {})
            picking_obj = data.get("picking_processes", {})
            waiting_data = picking_obj.get("data", [])

        if not waiting_data:
            print("No se han encontrado procesos de picking en espera.")
            no_content_label = tk.Label(self.waiting_frame, text="No hay procesos de picking en espera.", bg="white", font=("Arial", 10))
            no_content_label.pack(pady=10)
            return
        else:
            print("Procesos de picking en espera obtenidos:", waiting_data)

        for process in waiting_data:
            item_frame = tk.Frame(self.waiting_frame, bg="white", bd=1, relief="solid")
            item_frame.pack(fill="x", pady=5, padx=5)
            name_lbl = tk.Label(item_frame, text=f"Nombre: {process.get('name', '')}", bg="white", font=("Arial", 10))
            name_lbl.pack(anchor="w", padx=5)
            orders_lbl = tk.Label(item_frame, text=f"# Ordenes: {process.get('num_ordenes', 0)}", bg="white", font=("Arial", 10))
            orders_lbl.pack(anchor="w", padx=5)
            codes = ", ".join([c.get("bar_code", "") for c in process.get("containers", [])])
            codes_lbl = tk.Label(item_frame, text=f"Códigos de cesta: {codes}", bg="white", font=("Arial", 10))
            codes_lbl.pack(anchor="w", padx=5)
            btn_start = tk.Button(item_frame, text="Iniciar Proceso - Packing", font=("Arial", 10),
                                  command=lambda p=process: self.start_packing(p))
            btn_start.pack(anchor="e", padx=5, pady=5)

    def search(self):
        query = self.search_entry.get().strip()
        print(f"Buscando procesos con query: {query}")
        url = f"{API_ROUTES['PACKING_LIST']}?q={query}"
        response = self.login_controller.api_client._make_get_request(url)
        print("Respuesta de búsqueda:", response)
        if response is None or not isinstance(response, dict) or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener los resultados de búsqueda.")
            return

        # Extraer la lista de procesos desde la estructura anidada
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
            user = process.get("user", {}).get("name", "")
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
        """
        Destruye la vista actual y crea la vista de detalle para el proceso seleccionado.
        Se asume que PackingShowView está en 'views/warehouse/packing/show_view.py'
        y que existe un callback 'show_list_view' para regresar a la vista de listado.
        """
        # Destruir la vista de listado actual
        self.destroy()
        # Importar la vista de detalle
        from views.warehouse.packing.show_view import PackingShowView
        # Se asume que tienes un método o callback para volver a la lista, por ejemplo, 'show_list_view'
        detail_view = PackingShowView(master=self.master,
                                      process_id=process_id,
                                      login_controller=self.login_controller,
                                      on_back=self.show_list_view)
        detail_view.pack(expand=True, fill="both")

    def show_list_view(self):
        """
        Método callback para volver a la vista de listado.
        Se encarga de limpiar el contenedor y crear la vista de listado.
        """
        # Limpiar todos los widgets del contenedor (master)
        for widget in self.master.winfo_children():
            widget.destroy()
            
        from views.warehouse.packing.list_view import PackingListView
        list_view = PackingListView(master=self.master, login_controller=self.login_controller)
        list_view.pack(expand=True, fill="both")

