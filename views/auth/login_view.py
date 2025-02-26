import os
import sys 
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

from controllers.auth.login_controller import LoginController
from views.warehouse.packing.list_view import PackingListView
from assets.css.styles import (
    PRIMARY_COLOR, LABEL_STYLE, BUTTON_STYLE, CHECKBOX_STYLE,
    INPUT_WIDTH, INPUT_BG_COLOR, INPUT_FG_COLOR, LOGO_SIZE
)
def obtener_ruta_relativa(ruta_archivo):
    """ Retorna la ruta correcta para PyInstaller """
    if getattr(sys, 'frozen', False):  # Si está empaquetado como .exe
        base_path = sys._MEIPASS  # Carpeta temporal donde PyInstaller extrae los archivos
    else:
        base_path = os.path.abspath(".")  # Si se ejecuta como script normal

    return os.path.join(base_path, ruta_archivo)
class LoginView(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master, bg=PRIMARY_COLOR)
        self.master = master

        # Controlador con callback (SOLO para login manual)
        self.controller = LoginController(
            on_token_expired_callback=self.on_token_expired,
            on_login_success_callback=self._login_success_callback
        )
        
        self.pack(expand=True, fill="both")

        self.container = tk.Frame(self, bg=PRIMARY_COLOR)
        self.container.place(relx=0.5, rely=0.5, anchor="center")
        
        self.logo_image = self._load_image(obtener_ruta_relativa("assets/img/favicon.png"))
        self.create_widgets()

        # Si el autologin tuvo éxito en el constructor,
        # self.controller.user_data no será None
        if self.controller.get_logged_user() is not None:
            # Diferimos para que Tkinter termine de cargar la vista de login
            self.after(0, lambda: self._login_success_callback(self.controller.get_logged_user()))
            
    def _load_image(self, path):
            try:
                img = Image.open(path)
                img = img.resize(LOGO_SIZE, Image.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Error cargando la imagen {path}: {e}")
                return None

    def create_widgets(self):
        self.logo_label = tk.Label(self.container, image=self.logo_image, bg=PRIMARY_COLOR)
        self.logo_label.pack(pady=10)

        form_frame = tk.Frame(self.container, bg=PRIMARY_COLOR)
        form_frame.pack(pady=10)

        self.label_user = tk.Label(form_frame, text="Usuario (email):", **LABEL_STYLE)
        self.label_user.grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.entry_user = tk.Entry(form_frame, width=INPUT_WIDTH, bg=INPUT_BG_COLOR, fg=INPUT_FG_COLOR)
        self.entry_user.grid(row=0, column=1, padx=5, pady=5)

        self.label_password = tk.Label(form_frame, text="Contraseña:", **LABEL_STYLE)
        self.label_password.grid(row=1, column=0, padx=5, pady=5, sticky="e")

        self.entry_password = tk.Entry(form_frame, show="*", width=INPUT_WIDTH, bg=INPUT_BG_COLOR, fg=INPUT_FG_COLOR)
        self.entry_password.grid(row=1, column=1, padx=5, pady=5)

        self.save_credentials_var = tk.BooleanVar(value=True)
        self.chk_save_credentials = tk.Checkbutton(
            form_frame,
            text="Guardar credenciales",
            variable=self.save_credentials_var,
            **CHECKBOX_STYLE
        )
        self.chk_save_credentials.grid(row=2, column=0, columnspan=2, pady=10)

        self.login_button = tk.Button(
            self.container,
            text="Ingresar",
            command=self.handle_login,
            **BUTTON_STYLE
        )
        self.login_button.pack(pady=20)

    def handle_login(self):
        email = self.entry_user.get()
        password = self.entry_password.get()

        print("DEBUG: handle_login invocado con:", email, password)
        success = self.controller.do_login(email, password, save_credentials=self.save_credentials_var.get())

        if not success:
            messagebox.showerror("Error", "Credenciales inválidas o error en el servidor")
        else:
            messagebox.showinfo("Éxito", "Inicio de sesión correcto")
            # on_login_success_callback se dispara desde do_login

    def _login_success_callback(self, user_data):
        """
        El controlador llama a esta función cuando el login es exitoso (manual).
        O si detectamos user_data != None, la llamamos con 'after(0, ...)' para autologin.
        """
        print("DEBUG: _login_success_callback con user_data =", user_data)
        self.go_to_warehouse(user_data)

    def go_to_warehouse(self, user_data):
        self.pack_forget()
        
        # Función local para recrear LoginView tras logout, si es necesario
        def create_login():
            # Limpia el contenedor principal en vez de destruir todos los widgets de self.master
            for widget in self.master.winfo_children():
                widget.destroy()
            login_view = LoginView(master=self.master)
            login_view.pack(expand=True, fill="both")

        
        from views.warehouse.packing.list_view import PackingListView
        PackingListView(
            master=self.master,
            user_data=user_data,
            login_controller=self.controller,
            on_logout=create_login
        )
    def on_token_expired(self):
        print("El token expiró, vuelve a iniciar sesión.")
        messagebox.showwarning("Sesión expirada", "Tu sesión expiró, vuelve a iniciar sesión.")

    def _load_image(self, path):
        try:
            from PIL import Image, ImageTk
            img = Image.open(path)
            img = img.resize(LOGO_SIZE, Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error cargando la imagen {path}: {e}")
            return None
