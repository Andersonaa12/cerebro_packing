import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import subprocess
import os
import tempfile
import requests
import traceback
import win32print
import win32api
import socket
import json  # Import necesario para usar JSON

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

# Puedes cambiar esta ruta a donde quieras guardar tu JSON
JSON_CONFIG_FILE = "printer_config.json"

def log_message(message):
    """Logs debug messages a 'print_debug.log' y lo muestra en consola."""
    try:
        with open("print_debug.log", "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception as log_ex:
        print("Error writing to log:", log_ex)
    print(message)

def load_printer_config():
    """
    Carga la impresora seleccionada desde un archivo JSON.
    Estructura esperada del JSON:
    {
        "selected_printer": "Nombre de la impresora"
    }
    """
    if not os.path.exists(JSON_CONFIG_FILE):
        log_message("No existe archivo de configuración JSON. Se usará la impresora por defecto.")
        return None
    
    try:
        with open(JSON_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            printer_name = data.get("selected_printer", None)
            log_message(f"Impresora cargada desde JSON: {printer_name}")
            return printer_name
    except Exception as e:
        log_message("No se pudo cargar la impresora desde JSON: " + str(e))
        return None

def save_printer_config(printer_name):
    """
    Guarda la impresora seleccionada en un archivo JSON.
    Estructura que se guarda:
    {
        "selected_printer": "Nombre de la impresora"
    }
    """
    data = {
        "selected_printer": printer_name
    }
    try:
        with open(JSON_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        log_message(f"Impresora '{printer_name}' guardada en {JSON_CONFIG_FILE}")
    except Exception as e:
        log_message("Error al guardar la impresora en JSON: " + str(e))

class PackingListView(tk.Frame):
    def __init__(self, master=None, user_data=None, login_controller=None, on_logout=None):
        super().__init__(master, bg=BACKGROUND_COLOR_VIEWS)
        self.master = master
        self.user_data = user_data or {}
        self.login_controller = login_controller
        self.on_logout = on_logout

        # Se carga la impresora guardada desde JSON o, si no existe, la default del sistema
        loaded_printer = load_printer_config()
        self.selected_printer = loaded_printer or win32print.GetDefaultPrinter()
        log_message("Impresora inicial: " + self.selected_printer)

        self.pack(expand=True, fill="both")
        self.create_widgets()
        self.fetch_and_populate()

    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self, bg=PRIMARY_COLOR)
        header_frame.pack(fill="x", padx=10, pady=5)
        title_lbl = tk.Label(header_frame, text="Listado de Procesos - Packing",
                             font=("Arial", 16, "bold"), bg=PRIMARY_COLOR, fg="white")
        title_lbl.pack(side="left", padx=5)
        my_header = Header(master=header_frame, controller=self.login_controller,
                           on_logout_callback=self.handle_logout)
        my_header.pack(side="right")

        # Selección de impresora
        printer_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        printer_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(printer_frame, text="Selecciona Impresora:", bg=BACKGROUND_COLOR_VIEWS,
                 font=("Arial", 12)).pack(side="left", padx=5)
        self.printer_combobox = ttk.Combobox(printer_frame, state="readonly")
        self.printer_combobox.pack(side="left", padx=5)

        # Obtiene la lista de impresoras y setea la impresora inicial
        self.populate_printer_list()
        self.printer_combobox.bind("<<ComboboxSelected>>", self.on_printer_selected)

        # Botón para imprimir prueba
        test_print_btn = tk.Button(printer_frame, text="Prueba Impresión", command=self.test_print, **BUTTON_STYLE)
        test_print_btn.pack(side="left", padx=5)

        # Botón para guardar configuración de la impresora
        save_config_btn = tk.Button(printer_frame, text="Guardar Configuración", command=self.save_printer_settings, **BUTTON_STYLE)
        save_config_btn.pack(side="left", padx=5)

        # Panel de búsqueda
        search_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        search_frame.pack(fill="x", padx=10, pady=5)

        search_lbl = tk.Label(search_frame, text="Buscar por nombre:", font=("Arial", 12),
                              bg=BACKGROUND_COLOR_VIEWS)
        search_lbl.pack(side="left", padx=5)
        self.search_entry = tk.Entry(search_frame, font=("Arial", 12))
        self.search_entry.pack(side="left", padx=5)
        search_btn = tk.Button(search_frame, text="Buscar", command=self.search, **BUTTON_STYLE)
        search_btn.pack(side="left", padx=5)

        # Área principal
        main_frame = tk.Frame(self, bg=BACKGROUND_COLOR_VIEWS)
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        left_frame = tk.Frame(main_frame, bg="white", bd=1, relief="solid")
        left_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.create_table(left_frame)

        right_frame = tk.Frame(main_frame, bg="white", bd=1, relief="solid")
        right_frame.pack(side="right", fill="y", padx=5)
        self.create_waiting_panel(right_frame)

    def populate_printer_list(self):
        """Lista las impresoras instaladas y establece la selección."""
        printer_list, default_printer = self.listar_impresoras()

        # Si la impresora cargada no está en la lista, usar la default
        if self.selected_printer not in printer_list:
            self.selected_printer = default_printer

        self.printer_combobox['values'] = printer_list

        # Establece la selección actual
        try:
            index = printer_list.index(self.selected_printer)
        except ValueError:
            index = 0
        self.printer_combobox.current(index)

        log_message("Impresoras disponibles: " + str(printer_list))
        log_message("Impresora actualmente seleccionada: " + self.selected_printer)

    def on_printer_selected(self, event):
        selected = self.printer_combobox.get()
        self.selected_printer = selected
        log_message(f"Impresora seleccionada (combo): {selected}")

    def save_printer_settings(self):
        """
        Guarda la impresora seleccionada en el archivo JSON.
        De esta manera, otras vistas o métodos pueden usar la impresora guardada.
        """
        save_printer_config(self.selected_printer)
        messagebox.showinfo("Configuración", f"La impresora '{self.selected_printer}' se ha guardado correctamente.")

    def test_print(self):
        """Genera un archivo de prueba y lo envía a la impresora seleccionada."""
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as temp_file:
                temp_file.write("Impresión de prueba desde PackingListView.\n")
                temp_file.write("Esta es una impresión de prueba para verificar que la impresora seleccionada funcione correctamente.\n")
                temp_file.write("Si aparece, significa que se imprimió correctamente.\n")
                temp_file_path = temp_file.name

            log_message(f"Archivo de prueba creado en: {temp_file_path}")
            self.print_document(temp_file_path)
        except Exception as e:
            log_message("Error en la impresión de prueba: " + str(e))
            messagebox.showerror("Error", f"Error en la impresión de prueba: {str(e)}")

    def listar_impresoras(self):
        try:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printers = win32print.EnumPrinters(flags)
            printer_list = [printer[2] for printer in printers]
            default_printer = win32print.GetDefaultPrinter()
            log_message("Impresoras enumeradas: " + str(printer_list))
            log_message("Impresora por defecto: " + str(default_printer))
            return printer_list, default_printer
        except Exception as e:
            log_message("Error listando impresoras: " + str(e))
            return [], None

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

            codes = ", ".join([
                c.get("container", {}).get("bar_code", "") for c in process.get("containers", [])
            ])
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
            log_message(f"Proceso de packing iniciado para id: {process_id}")
            messagebox.showinfo("Proceso Iniciado", f"Se inició el proceso de packing para el proceso id {process_id}.")
            self.fetch_and_populate()
        else:
            log_message(f"Error al iniciar el proceso de packing para id: {process_id}")
            messagebox.showerror("Error", "No se pudo iniciar el proceso de packing.")

    def search(self):
        query = self.search_entry.get().strip()
        log_message(f"Buscando procesos con query: {query}")
        url = f"{API_ROUTES['PACKING_LIST']}?q={query}"
        response = self.login_controller.api_client._make_get_request(url)
        log_message(f"Respuesta de búsqueda: {response}")

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
        log_message(f"Iniciando proceso de packing para id: {process_id}")
        endpoint = API_ROUTES["PACKING_CREATE"].format(id=process_id)
        result = self.login_controller.api_client._make_post_request(endpoint, {})
        log_message(f"Resultado de iniciar packing: {result}")

        if result:
            log_message(f"Proceso de packing iniciado para: {process.get('name')}")
            messagebox.showinfo("Proceso Iniciado", f"Se inició el proceso de packing para {process.get('name')}.")
            self.fetch_and_populate()
        else:
            log_message(f"Error al iniciar el proceso de packing para id: {process_id}")
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
        log_message(f"Mostrando detalles para el proceso id: {process_id}")
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

    def print_document(self, file_path):
        """
        Imprime el documento especificado usando la impresora seleccionada.
        Se utiliza win32api.ShellExecute para enviar la orden de impresión.
        """
        try:
            log_message(f"Enviando {file_path} a la impresora: {self.selected_printer}")
            win32api.ShellExecute(0, "print", file_path, f'/d:"{self.selected_printer}"', ".", 0)
            messagebox.showinfo("Impresión", f"Documento enviado a {self.selected_printer}")
        except Exception as e:
            log_message(f"Error al imprimir: {e}")
            messagebox.showerror("Error", f"Error al imprimir: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Packing List View")
    root.geometry("800x600")
    app = PackingListView(master=root)
    root.mainloop()
