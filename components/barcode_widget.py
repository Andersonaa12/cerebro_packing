import io
import tkinter as tk
from PIL import Image, ImageTk
import barcode
from barcode.writer import ImageWriter

def create_barcode_widget(master, barcode_value, width=200, height=100):
    """
    Genera un widget (Label) que muestra el código de barras correspondiente a 'barcode_value'.

    :param master: Widget padre de Tkinter.
    :param barcode_value: Valor (string) del código de barras.
    :param width: Ancho deseado de la imagen.
    :param height: Alto deseado de la imagen.
    :return: Un Label de Tkinter que contiene la imagen del código de barras.
    """
    # Obtener la clase para Code128 (puedes elegir otro formato)
    CODE128 = barcode.get_barcode_class('code128')
    # Generar el código de barras con ImageWriter para obtener una imagen
    my_code = CODE128(barcode_value, writer=ImageWriter())
    # Guardar la imagen en un objeto BytesIO en memoria
    buffer = io.BytesIO()
    my_code.write(buffer)
    buffer.seek(0)
    # Abrir la imagen con PIL
    image = Image.open(buffer)
    # Redimensionar la imagen según los parámetros dados
    image = image.resize((width, height), Image.ANTIALIAS)
    # Convertir la imagen para que Tkinter la pueda usar
    photo = ImageTk.PhotoImage(image)
    # Crear un Label que contenga la imagen
    label = tk.Label(master, image=photo)
    # Es importante guardar una referencia a la imagen para evitar que sea recolectada por el GC
    label.image = photo
    return label
