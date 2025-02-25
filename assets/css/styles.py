# Colores
PRIMARY_COLOR = "#f58033"
SECONDARY_COLOR = "#ffffff"
TEXT_COLOR = "#ffffff"
BUTTON_TEXT_COLOR = "#f58033"
INPUT_BG_COLOR = "#ffffff"
INPUT_FG_COLOR = "#000000"

BACKGROUND_COLOR_VIEWS = "#F1F3F7"


# Tamaños de fuente
FONT_LARGE = ("Arial", 14, "bold")
FONT_MEDIUM = ("Arial", 12)
FONT_SMALL = ("Arial", 10)
FONT_SMALL_UNDERLINED = ("Arial", 10, "underline")

# Tamaño de imágenes
LOGO_SIZE = (100, 100)

# Tamaño de inputs
INPUT_WIDTH = 25

# Estilos de botones
BUTTON_STYLE = {
    "bg": SECONDARY_COLOR,
    "fg": BUTTON_TEXT_COLOR,
    "activebackground": "#ffffff",
    "font": FONT_SMALL,
    "padx": 10,
    "pady": 5
}

# Estilos de etiquetas
LABEL_STYLE = {
    "bg": PRIMARY_COLOR,
    "fg": TEXT_COLOR,
    "font": FONT_MEDIUM
}

# Estilos de checkboxes
CHECKBOX_STYLE = {
    "bg": PRIMARY_COLOR,
    "fg": TEXT_COLOR,
    "activebackground": PRIMARY_COLOR,
    "font": FONT_SMALL_UNDERLINED,
    "selectcolor": "black",  # para ver el check
    "onvalue": True,
    "offvalue": False
}
