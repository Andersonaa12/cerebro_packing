import os
import json
import tempfile
import requests
import win32api
import win32print
import traceback

# Archivo de configuración donde se guarda la impresora seleccionada.
PRINTER_CONFIG_FILE = "printer_config.json"

def load_printer_config():
    """
    Carga la impresora seleccionada desde el archivo JSON.
    Si no existe o hay error, se utilizará la impresora por defecto del sistema.
    """
    if not os.path.exists(PRINTER_CONFIG_FILE):
        print(f"[INFO] No se encontró '{PRINTER_CONFIG_FILE}'. Usando impresora por defecto.")
        return None
    try:
        with open(PRINTER_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            printer = data.get("selected_printer")
            print(f"[INFO] Impresora cargada desde config: {printer}")
            return printer
    except Exception as e:
        print(f"[ERROR] Error al leer la configuración de impresora: {e}")
        traceback.print_exc()
        return None

def print_document(file_path, printer):
    """
    Envía el documento especificado a la impresora.
    Se utiliza ShellExecute de win32api para realizar la impresión.
    """
    try:
        print(f"[INFO] Enviando '{file_path}' a la impresora: {printer}")
        win32api.ShellExecute(0, "print", file_path, f'/d:"{printer}"', ".", 0)
        print(f"[INFO] Documento enviado a la impresora: {printer}")
    except Exception as e:
        print(f"[ERROR] Error al enviar el documento a imprimir: {e}")
        traceback.print_exc()

def print_from_url(url):
    """
    Descarga el archivo desde la URL dada y lo imprime usando la impresora configurada.
    Se registran mensajes de información y error en la consola.
    """
    # Se obtiene la impresora desde el archivo JSON o la por defecto
    printer = load_printer_config() or win32print.GetDefaultPrinter()
    try:
        print(f"[INFO] Descargando archivo desde: {url}")
        response = requests.get(url)
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(response.content)
                temp_file = tmp.name
                print(f"[INFO] Archivo temporal creado: {temp_file}")
            print_document(temp_file, printer)
            os.remove(temp_file)
            print(f"[INFO] Archivo temporal eliminado: {temp_file}")
        else:
            print(f"[ERROR] Falló la descarga. Código de estado: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Excepción durante la impresión desde URL: {e}")
        traceback.print_exc()

# Ejemplo de uso: se puede llamar a print_from_url(url) desde cualquier parte de la aplicación.
if __name__ == "__main__":
    # Reemplaza este URL por uno real para pruebas.
    test_url = "http://example.com/sample.pdf"
    print_from_url(test_url)
