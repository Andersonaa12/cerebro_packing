import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from assets.css.styles import PRIMARY_COLOR, BACKGROUND_COLOR_VIEWS, LABEL_STYLE, BUTTON_STYLE
from config.settings import API_BASE_URL
from services.api_routes import API_ROUTES
from components.header import Header
from components.barcode_widget import create_barcode_widget

CENTERED_LABEL_STYLE = {
    "bg": "white",
    "font": ("Arial", 10),
    "anchor": "center",
    "justify": "center"
}

def log_message(message):
    """Logs debug messages to 'print_debug.log' and console."""
    try:
        with open("print_debug.log", "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception as log_ex:
        print("Error writing to log:", log_ex)
    print(message)

class PackingListView(tk.Frame):
    def __init__(self, master=None, user_data=None, login_controller=None, on_logout=None):
        super().__init__(master, bg=BACKGROUND_COLOR_VIEWS)
        self.master = master
        self.user_data = user_data or {}
        self.login_controller = login_controller
        self.on_logout = on_logout

        self.pack(expand=True, fill="both")
        self.create_widgets()
        self.fetch_and_populate()

    def create_widgets(self):
        header_frame = tk.Frame(self, bg=PRIMARY_COLOR)
        header_frame.pack(fill="x", padx=10, pady=5)
        title_lbl = tk.Label(header_frame, text="Listado de Procesos - Packing",
                             font=("Arial", 16, "bold"), bg=PRIMARY_COLOR, fg="white")
        title_lbl.pack(side="left", padx=5)
        my_header = Header(master=header_frame, controller=self.login_controller,
                           on_logout_callback=self.handle_logout)
        my_header.pack(side="right")

        options_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        options_frame.pack(fill="x", padx=10, pady=5)

        self.settings_button = tk.Button(options_frame, text="Ajustes",
                                         command=self.open_settings, **BUTTON_STYLE)
        self.settings_button.pack(side="left", padx=5)

        search_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        search_frame.pack(fill="x", padx=10, pady=5)
        search_lbl = tk.Label(search_frame, text="Buscar por nombre:", font=("Arial", 12),
                              bg=BACKGROUND_COLOR_VIEWS)
        search_lbl.pack(side="left", padx=5)
        self.search_entry = tk.Entry(search_frame, font=("Arial", 12))
        self.search_entry.pack(side="left", padx=5)
        search_btn = tk.Button(search_frame, text="Buscar", command=self.search, **BUTTON_STYLE)
        search_btn.pack(side="left", padx=5)

        main_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)
        left_frame = tk.Frame(main_frame, bg="white", bd=1, relief="solid")
        left_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.create_table(left_frame)
        right_frame = tk.Frame(main_frame, bg="white", bd=1, relief="solid")
        right_frame.pack(side="right", fill="y", padx=5)
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
        title = tk.Label(parent, text="Procesos de Picking - En espera",
                         font=("Arial", 14, "bold"), bg="white")
        title.pack(pady=10)

        barcode_frame = tk.Frame(parent, bg="white")
        barcode_frame.pack(fill="x", padx=5, pady=5)
        barcode_lbl = tk.Label(barcode_frame, text="Código de cesta:",
                               font=("Arial", 12), bg="white")
        barcode_lbl.pack(side="left", padx=5)

        self.barcode_entry = tk.Entry(barcode_frame, font=("Arial", 12))
        self.barcode_entry.pack(side="left", padx=5)
        self.barcode_entry.bind("<Return>", lambda event: self.search_by_barcode())

        barcode_btn = tk.Button(barcode_frame, text="Crear Proceso",
                                command=self.search_by_barcode, **BUTTON_STYLE)
        barcode_btn.pack(side="left", padx=5)

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
        log_message("Solicitando procesos de packing...")
        response = self.login_controller.api_client._make_get_request(API_ROUTES["PACKING_LIST"])
        log_message("Respuesta de packing: " + str(response))

        if response is None or not isinstance(response, dict) or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener el listado de procesos.")
            return

        data = response.get("data", {})
        packing_obj = data.get("packing_processes", {})
        processes = packing_obj.get("data", [])
        log_message("Procesos de packing obtenidos: " + str(processes))

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

        self.populate_waiting_panel()

    def populate_waiting_panel(self):
        for widget in self.waiting_frame.winfo_children():
            widget.destroy()

        log_message("Solicitando procesos de picking en espera...")
        waiting_response = self.login_controller.api_client._make_get_request(API_ROUTES["PACKING_LIST"])
        log_message("Respuesta de picking en espera: " + str(waiting_response))

        waiting_data = []
        if waiting_response and isinstance(waiting_response, dict):
            data = waiting_response.get("data", {})
            waiting_data = data.get("picking_processes", [])
        self.waiting_data = waiting_data

        if not waiting_data:
            log_message("No se han encontrado procesos de picking en espera.")
            no_content_label = tk.Label(
                self.waiting_frame, text="No hay procesos de picking en espera.",
                bg="white", font=("Arial", 10), anchor="center", justify="center"
            )
            no_content_label.pack(pady=10)
            return
        else:
            log_message("Procesos de picking en espera obtenidos: " + str(waiting_data))

        for process in waiting_data:
            item_frame = tk.Frame(self.waiting_frame, bg="white", bd=1, relief="solid")
            item_frame.pack(fill="x", pady=5, padx=(120, 0))

            name_lbl = tk.Label(item_frame, text=f"Nombre: {process.get('name', '')}",
                                **CENTERED_LABEL_STYLE)
            name_lbl.pack(anchor="center", padx=5, pady=2)

            orders_lbl = tk.Label(item_frame, text=f"# Órdenes: {process.get('num_ordenes', 0)}",
                                  **CENTERED_LABEL_STYLE)
            orders_lbl.pack(anchor="center", padx=5, pady=2)

            codes = ", ".join([c.get("container", {}).get("bar_code", "") for c in process.get("containers", [])])
            codes_lbl = tk.Label(item_frame, text=f"Código de cesta: {codes}",
                                 **CENTERED_LABEL_STYLE)
            codes_lbl.pack(anchor="center", padx=5, pady=2)

            if process.get("containers"):
                first_barcode = process.get("containers")[0].get("container", {}).get("bar_code", "")
                if first_barcode:
                    barcode_w = create_barcode_widget(item_frame, first_barcode)
                    barcode_w.pack(anchor="center", padx=5, pady=5)

            btn_start = tk.Button(item_frame, text="Iniciar Proceso - Packing",
                                  command=lambda p=process: self.start_packing(p), **BUTTON_STYLE)
            btn_start.pack(anchor="center", padx=5, pady=5)

    def search_by_barcode(self):
        barcode_value = self.barcode_entry.get().strip()
        if not barcode_value:
            messagebox.showwarning("Advertencia", "Por favor ingresa un código de barras.")
            return

        log_message("Buscando proceso de picking con código de barras: " + barcode_value)
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
            log_message("No se encontró proceso de picking con el código: " + barcode_value)
            messagebox.showerror("Error", f"No se encontró proceso de picking con el código de barras: {barcode_value}.")
            return

        process_id = process_to_pack.get("id")
        log_message("Creando proceso de packing para id: " + str(process_id))
        endpoint = API_ROUTES["PACKING_CREATE"].format(id=process_id)
        result = self.login_controller.api_client._make_post_request(endpoint, {})

        if result:
            log_message("Proceso de packing iniciado para id: " + str(process_id))
            messagebox.showinfo("Proceso Iniciado", f"Se inició el proceso de packing para el proceso id {process_id}.")
            self.fetch_and_populate()
        else:
            log_message("Error al iniciar el proceso de packing para id: " + str(process_id))
            messagebox.showerror("Error", "No se pudo iniciar el proceso de packing.")

    def search(self):
        query = self.search_entry.get().strip()
        log_message("Buscando procesos con query: " + query)
        url = f"{API_ROUTES['PACKING_LIST']}?q={query}"
        response = self.login_controller.api_client._make_get_request(url)
        log_message("Respuesta de búsqueda: " + str(response))

        if response is None or not isinstance(response, dict) or not response.get("success"):
            messagebox.showerror("Error", "No se pudo obtener los resultados de búsqueda.")
            return

        data = response.get("data", {})
        packing_obj = data.get("packing_processes", {})
        processes = packing_obj.get("data", [])
        log_message("Procesos encontrados: " + str(processes))

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
        log_message("Iniciando proceso de packing para id: " + str(process_id))
        endpoint = API_ROUTES["PACKING_CREATE"].format(id=process_id)
        result = self.login_controller.api_client._make_post_request(endpoint, {})
        log_message("Resultado de iniciar packing: " + str(result))

        if result:
            log_message("Proceso de packing iniciado para: " + str(process.get("name")))
            messagebox.showinfo("Proceso Iniciado", f"Se inició el proceso de packing para {process.get('name')}.")
            self.fetch_and_populate()
        else:
            log_message("Error al iniciar el proceso de packing para id: " + str(process_id))
            messagebox.showerror("Error", "No se pudo iniciar el proceso de packing.")

    def on_row_double_click(self, event):
        try:
            item_id = self.tree.selection()[0]
        except IndexError:
            log_message("No se ha seleccionado ningún elemento.")
            return

        item = self.tree.item(item_id)
        values = item["values"]
        process_id = values[0]
        log_message("Mostrando detalles para el proceso id: " + str(process_id))
        self.on_show_detail(process_id)

    def on_show_detail(self, process_id):
        self.destroy()
        from views.warehouse.packing.show_view import PackingShowView
        detail_view = PackingShowView(master=self.master, process_id=process_id,
                                      login_controller=self.login_controller,
                                      on_back=self.show_list_view)
        detail_view.pack(expand=True, fill="both")

    def show_list_view(self):
        for widget in self.master.winfo_children():
            widget.destroy()
        from views.warehouse.packing.list_view import PackingListView
        list_view = PackingListView(master=self.master, login_controller=self.login_controller)
        list_view.pack(expand=True, fill="both")

    def handle_logout(self):
        for widget in self.master.winfo_children():
            widget.destroy()
        if self.on_logout:
            self.on_logout()

    def open_settings(self):
        self.destroy()
        from views.warehouse.packing.general_setting import GeneralSettingsView
        settings_view = GeneralSettingsView(master=self.master, login_controller=self.login_controller,
                                            on_back=self.show_list_view)
        settings_view.pack(expand=True, fill="both")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Packing List View")
    root.geometry("800x600")
    app = PackingListView(master=root)
    root.mainloop()