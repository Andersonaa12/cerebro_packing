import tkinter as tk
from views.auth.login_view import LoginView

def main():
    root = tk.Tk()
    root.title("Aplicación de Escaneo y Packing")

    # Ocupar toda la pantalla (modo maximizado)
    root.state("zoomed")
    # root.attributes("-fullscreen", True)  # Alternativa

    login_view = LoginView(master=root)
    login_view.pack(fill="both", expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()
