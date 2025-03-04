import tkinter as tk
import json
from pathlib import Path
from assets.css.styles import PRIMARY_COLOR, BUTTON_STYLE

# Ruta de tu archivo de credenciales
CREDENTIALS_FILE = Path("config/credentials.json")

class Header(tk.Frame):
    def __init__(self, master=None, controller=None, on_back_callback=None, on_logout_callback=None):
        super().__init__(master, bg=PRIMARY_COLOR)
        self.controller = controller
        self.on_back_callback = on_back_callback
        self.on_logout_callback = on_logout_callback
        
        # Cargar credenciales y obtener el nombre del usuario
        self.credentials = self.load_credentials()
        user_name = self.credentials["token_data"]["user"]["name"]
        
        # Contenedor (izquierda) para el nombre de usuario
        user_container = tk.Frame(self, bg=PRIMARY_COLOR)
        user_container.pack(side="left", fill="x", expand=True, padx=10, pady=10)

        # Etiqueta que muestra el nombre del usuario
        self.lbl_user_name = tk.Label(
            user_container,
            text=f"Bienvenido, {user_name}",
            bg=PRIMARY_COLOR,
            fg="white",
            font=("Arial", 16, "bold")  # Fuente más grande y en negrita
        )

        self.lbl_user_name.pack(side="left")

        # Contenedor (derecha) para el botón de Cerrar sesión
        btn_container = tk.Frame(self, bg=PRIMARY_COLOR, padx=5, pady=5)
        btn_container.pack(side="right", padx=2, pady=2)

        # Botón "Cerrar sesión"
        self.btn_logout = tk.Button(
            btn_container,
            text="Cerrar sesión",
            command=self.handle_logout,
            **BUTTON_STYLE
        )
        self.btn_logout.pack()

    def load_credentials(self):
        """Lee y retorna los datos del archivo de credenciales JSON."""
        with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)

    def handle_logout(self):
        """Lógica para cerrar sesión (redirige a login o realiza las acciones que desees)."""
        if self.controller:
            self.controller.do_logout()
        if self.on_logout_callback:
            self.on_logout_callback()
