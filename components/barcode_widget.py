import io
import tkinter as tk
from PIL import Image, ImageTk, ImageFont
import barcode
from barcode.writer import ImageWriter
import os
import sys

def resource_path(relative_path):
    """ Obtiene la ruta del archivo correctamente si está empaquetado como .exe """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def create_barcode_widget(master, barcode_value, width=200, height=100):
    """
    Genera un widget (Label) que muestra el código de barras correspondiente a 'barcode_value'.
    """

    CODE128 = barcode.get_barcode_class('code128')

    # Intenta usar una fuente predeterminada
    try:
        font_path = resource_path("arial.ttf")  # Usa una fuente del sistema o agrega una a tu carpeta `assets/fonts/`
        font = ImageFont.truetype(font_path, 14)
    except IOError:
        font = None  # Si falla, deja que PIL use una fuente predeterminada

    # Generar código de barras con ImageWriter y fuente específica
    my_code = CODE128(barcode_value, writer=ImageWriter())
    my_code.default_writer_options['font_path'] = font_path if font else None

    # Guardar la imagen en memoria
    buffer = io.BytesIO()
    my_code.write(buffer)
    buffer.seek(0)

    # Abrir la imagen con PIL
    image = Image.open(buffer)
    image = image.resize((width, height), Image.LANCZOS)

    # Convertir la imagen para usarla en Tkinter
    photo = ImageTk.PhotoImage(image)
    label = tk.Label(master, image=photo)
    label.image = photo  # Evitar que sea eliminada por el recolector de basura

    return label
