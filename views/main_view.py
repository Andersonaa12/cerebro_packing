import tkinter as tk
from tkinter import messagebox

class MainView(tk.Frame):
    def __init__(self, master=None, api_service=None):
        super().__init__(master)
        self.master = master
        self.api_service = api_service  # Pasado desde LoginController
        self.create_widgets()

    def create_widgets(self):
        self.label_title = tk.Label(self, text="Escanear código de barras")
        self.label_title.pack(pady=10)

        self.entry_barcode = tk.Entry(self)
        self.entry_barcode.pack()

        self.btn_validate = tk.Button(self, text="Validar", command=self.validate_barcode)
        self.btn_validate.pack(pady=5)

    def validate_barcode(self):
        barcode = self.entry_barcode.get()
        result = self.api_service.validate_product_barcode(barcode)
        if result:
            # Asume result = { "valid": True, "product": "XYZ" } ...
            if result.get("valid"):
                product_name = result.get("product", "Desconocido")
                messagebox.showinfo("Código Válido", f"Producto: {product_name}")
            else:
                messagebox.showwarning("Inválido", "Código no encontrado.")
        else:
            messagebox.showerror("Error", "Error en la validación del código.")
