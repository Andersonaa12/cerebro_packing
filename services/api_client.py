import requests
from config.settings import API_BASE_URL, REQUEST_TIMEOUT
from services.api_routes import API_ROUTES

class ApiClient:
    """
    Cliente HTTP genérico que se encarga de:
    - Manejar el token en headers (self.token).
    - Hacer reintentos automáticos si se recibe un 401 (y se tienen credenciales).
    - Ofrecer métodos genéricos _make_get_request y _make_post_request
      para que los controladores hagan las peticiones que necesiten.
    """
    def __init__(self, on_token_expired_callback=None):
        self.token = None
        self.email = None
        self.password = None
        self.on_token_expired_callback = on_token_expired_callback

    def _make_get_request(self, endpoint):
        url = f"{API_BASE_URL}{endpoint}"
        headers = self._get_headers()
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 401:
                if not self._try_auto_relogin():
                    if self.on_token_expired_callback:
                        self.on_token_expired_callback()
                    return None
                headers = self._get_headers()
                response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error GET {url}: {e}")
            return None


    def _make_post_request(self, endpoint, payload=None):
        url = f"{API_BASE_URL}{endpoint}"
        headers = self._get_headers()
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            if response.status_code == 401:
                if not self._try_auto_relogin():
                    if self.on_token_expired_callback:
                        self.on_token_expired_callback()
                    return None
                headers = self._get_headers()
                response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error POST {url}: {e}")
            return None

    def _get_headers(self):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _try_auto_relogin(self):
        """
        Si tenemos email y password guardados, reintentamos login automático
        antes de repetir la petición. Devuelve True si logró relogearse.
        """
        if self.email and self.password:
            print("Intentando relogin automático con credenciales guardadas...")
            return self._login_internal(self.email, self.password)
        return False

    def _login_internal(self, email, password):
            payload = {"email": email, "password": password}
            data = self._make_post_request(API_ROUTES["LOGIN"], payload)
            if data is None:
                return False
            token = data.get("access_token")
            if token:
                self.token = token
                self.email = email
                self.password = password
                return True
            return False