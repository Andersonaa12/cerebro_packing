import os
import sys
import tkinter as tk
from views.auth.login_view import LoginView

def obtener_ruta_relativa(ruta_archivo):
    """ Retorna la ruta correcta para PyInstaller """
    if getattr(sys, 'frozen', False):  # Si está empaquetado como .exe
        base_path = sys._MEIPASS  # Carpeta temporal de PyInstaller
    else:
        base_path = os.path.abspath(".")  # Si se ejecuta como script normal

    return os.path.join(base_path, ruta_archivo)

def main():
    root = tk.Tk()
    root.title("Aplicación de Escaneo y Packing")

    # Obtener rutas absolutas de los íconos
    icono_ico = obtener_ruta_relativa("assets/img/favicon.ico")
    icono_png = obtener_ruta_relativa("assets/img/favicon.png")

    try:
        # Intentar usar el ícono .ico en Windows
        root.iconbitmap(icono_ico)
    except Exception as e:
        print(f"No se pudo cargar {icono_ico}, error: {e}")
        try:
            # Si falla, usar el PNG con iconphoto
            icono = tk.PhotoImage(file=icono_png)
            root.iconphoto(True, icono)
        except Exception as e:
            print(f"No se pudo cargar {icono_png}, error: {e}")

    # Iniciar en modo maximizado
    root.state("zoomed")
    root.resizable(True, True)

    login_view = LoginView(master=root)
    login_view.pack(fill="both", expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()
