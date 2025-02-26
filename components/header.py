import tkinter as tk
from assets.css.styles import PRIMARY_COLOR, BUTTON_STYLE

class Header(tk.Frame):
    def __init__(self, master=None, controller=None, 
                 on_back_callback=None, on_logout_callback=None):
        super().__init__(master, bg=PRIMARY_COLOR)  # Fondo del header con PRIMARY_COLOR
        self.controller = controller
        self.on_back_callback = on_back_callback
        self.on_logout_callback = on_logout_callback

        # Contenedor exclusivo para el botón con fondo PRIMARY_COLOR
        btn_container = tk.Frame(self, bg=PRIMARY_COLOR, padx=5, pady=5)
        btn_container.pack(side="right", padx=2, pady=2)

        # Botón "Cerrar sesión" dentro del contenedor
        self.btn_logout = tk.Button(
            btn_container,  # Se coloca dentro del contenedor
            text="Cerrar sesión",
            command=self.handle_logout,
            **BUTTON_STYLE
        )
        self.btn_logout.pack()

    def handle_logout(self):
        """Cierra sesión y redirige a la pantalla de login."""
        if self.controller:
            self.controller.do_logout()
        if self.on_logout_callback:
            self.on_logout_callback()
