import tkinter as tk
from assets.css.styles import PRIMARY_COLOR, TEXT_COLOR

class Footer(tk.Frame):
    """
    Barra inferior con fondo PRIMARY_COLOR.
    Puedes añadir lo que desees, un texto, enlaces, etc.
    """
    def __init__(self, master=None):
        super().__init__(master, bg=PRIMARY_COLOR)

        self.label = tk.Label(
            self,
            text="© 2025 Dropi Pro - Escaner",
            bg=PRIMARY_COLOR,
            fg=TEXT_COLOR
        )
        self.label.pack(pady=5, padx=10)
