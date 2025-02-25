import tkinter as tk
from assets.css.styles import PRIMARY_COLOR, BUTTON_STYLE

class Header(tk.Frame):
    def __init__(self, master=None, controller=None, 
                 on_back_callback=None, on_logout_callback=None):
        super().__init__(master)
        self.controller = controller
        self.on_back_callback = on_back_callback
        self.on_logout_callback = on_logout_callback

        # Contenedor exclusivo para el botón (con fondo separado)
        btn_container = tk.Frame(self, bg=PRIMARY_COLOR, bd=2)  # Fondo blanco, borde y relieve
        btn_container.pack(side="right", padx=10, pady=5)

        # Botón "Cerrar sesión" dentro del contenedor
        self.btn_logout = tk.Button(
            btn_container,  # Se coloca dentro del contenedor con fondo blanco
            text="Cerrar sesión",
            command=self.handle_logout,
            **BUTTON_STYLE
        )
        self.btn_logout.pack(padx=5, pady=5)  # Espaciado interno

    def handle_logout(self):
        """Cierra sesión y redirige a la pantalla de login."""
        if self.controller:
            self.controller.do_logout()
        if self.on_logout_callback:
            self.on_logout_callback()
