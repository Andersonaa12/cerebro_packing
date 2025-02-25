import os
import json
from services.api_client import ApiClient
from services.api_routes import API_ROUTES

class LoginController:
    def __init__(self, 
                 on_token_expired_callback=None,
                 on_login_success_callback=None,
                 on_logout_callback=None,  # Callback para redirigir al login
                 credentials_file="config/credentials.json"):
        self.api_client = ApiClient(on_token_expired_callback=on_token_expired_callback)
        self.on_login_success_callback = on_login_success_callback
        self.on_logout_callback = on_logout_callback  # Guardamos la función para redirigir
        self.credentials_file = credentials_file

        self.saved_email = None
        self.saved_password = None
        self.token_data = None  # Aquí guardaremos toda la respuesta de login (incluye token, etc.)
        self._load_credentials()

        self.user_data = None

        # Intentar autologin si hay credenciales guardadas
        if self.saved_email and self.saved_password:
            success = self._login_internal(self.saved_email, self.saved_password)
            if success:
                print("Inicio de sesión automático exitoso.")
            else:
                print("No se pudo iniciar sesión automáticamente con credenciales guardadas.")

    def do_login(self, email, password, save_credentials=False):
        """
        Realiza el inicio de sesión y guarda credenciales y token en el archivo JSON si se indica.
        """
        success = self._login_internal(email, password)
        if success:
            if save_credentials:
                self._save_credentials(email, password)
            else:
                self._delete_credentials()

            # Llamar al callback si el login es exitoso
            if self.on_login_success_callback:
                self.on_login_success_callback(self.user_data)
        return success

    def _login_internal(self, email, password):
        """
        Realiza la solicitud de login al API, guarda y actualiza los datos de token y usuario.
        Se espera una respuesta similar a:
        {
            "access_token": "...",
            "token_type": "bearer",
            "expires_in": 86400,
            "user": { ... }
        }
        """
        payload = {"email": email, "password": password}
        print("DEBUG: Haciendo login con", payload)
        data = self.api_client._make_post_request(API_ROUTES["LOGIN"], payload)

        if data is None:
            return False

        # Guardamos toda la respuesta (token, token_type, expires_in y user) en token_data
        self.token_data = data

        token = data.get("access_token")
        if token:
            self.api_client.token = token
            self.api_client.email = email
            self.api_client.password = password
            self.user_data = data.get("user")
            print("DEBUG: user_data =", self.user_data)
            print("DEBUG: token_type =", data.get("token_type"))
            print("DEBUG: expires_in =", data.get("expires_in"))
            return True
        else:
            return False

    def do_logout(self):
        """
        Cierra sesión eliminando el token, las credenciales y actualiza el archivo.
        """
        self.api_client._make_post_request(API_ROUTES["LOGOUT"])
        self.api_client.token = None
        self.user_data = None
        self.token_data = None

        self._delete_credentials()
        print("Logout completado. Token y credenciales borradas.")

        if self.on_logout_callback:
            self.on_logout_callback()

    def get_logged_user(self):
        return self.user_data

    # ============ Manejo de credenciales ============
    def _save_credentials(self, email, password):
        """
        Guarda en el archivo credentials.json el email, la contraseña y el token_data obtenido en el login.
        """
        data = {
            "email": email,
            "password": password,
            "token_data": self.token_data  # Guarda toda la información del token
        }
        os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
        with open(self.credentials_file, "w") as f:
            json.dump(data, f)
        print("Credenciales y token guardados en", self.credentials_file)

    def _delete_credentials(self):
        """
        Elimina el archivo de credenciales si existe.
        """
        if os.path.exists(self.credentials_file):
            os.remove(self.credentials_file)
            print("Archivo de credenciales eliminado.")

    def _load_credentials(self):
        """
        Carga las credenciales y el token_data guardados.
        Si el archivo no existe, lo crea con valores vacíos.
        """
        if not os.path.exists(self.credentials_file):
            print("El archivo de credenciales no existe. Creándolo...")
            self._save_credentials("", "")  # Crea un archivo vacío

        try:
            with open(self.credentials_file, "r") as f:
                data = json.load(f)
                self.saved_email = data.get("email")
                self.saved_password = data.get("password")
                self.token_data = data.get("token_data")
                # Si token_data está presente, actualizar el token en el ApiClient
                if self.token_data and "access_token" in self.token_data:
                    self.api_client.token = self.token_data["access_token"]
        except json.JSONDecodeError:
            print("El archivo credentials.json está corrupto. Se eliminará.")
            self._delete_credentials()
