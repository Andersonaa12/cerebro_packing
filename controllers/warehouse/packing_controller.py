from config.settings import API_BASE_URL, REQUEST_TIMEOUT
from services.api_client import ApiClient
from services.api_routes import API_ROUTES

class PackingController:
    def __init__(self, api_client):
        """
        Controlador para gestionar los procesos de packing.
        
        :param api_client: Instancia autenticada del ApiClient (normalmente proporcionada por el LoginController).
        """
        self.api_client = api_client

    def get_packing_processes(self, query=""):
        """
        Obtiene el listado de procesos de packing.
        
        :param query: Cadena de búsqueda opcional.
        :return: Lista de procesos o None si ocurre error.
        """
        url = f"{API_BASE_URL}{API_ROUTES['PACKING_LIST']}"
        if query:
            url += f"?q={query}"
        return self.api_client._make_get_request(url)

    def get_waiting_picking_processes(self):
        """
        Obtiene el listado de procesos de picking en espera.
        
        Se asume que existe una ruta en API_ROUTES llamada "PACKING_LIST_WAITING".
        Si no existe, se devuelve una lista simulada.
        
        :return: Lista de procesos de picking en espera o datos simulados.
        """
        waiting_endpoint = API_ROUTES.get("PACKING_LIST_WAITING", "")
        if waiting_endpoint:
            url = f"{API_BASE_URL}{waiting_endpoint}"
            return self.api_client._make_get_request(url)
        # Datos simulados en caso de que no exista la ruta
        return [
            {"id": 101, "name": "Picking 1", "num_ordenes": 3, "containers": [{"bar_code": "C123"}]},
            {"id": 102, "name": "Picking 2", "num_ordenes": 2, "containers": [{"bar_code": "C456"}, {"bar_code": "C789"}]}
        ]

    def print_test(self):
        """
        Llama al endpoint para imprimir un test.
        
        :return: Respuesta de la API o None.
        """
        endpoint = API_ROUTES.get("PACKING_PRINT", "")
        if endpoint:
            url = f"{API_BASE_URL}{endpoint}"
            return self.api_client._make_post_request(url, {})
        return None

    def create_packing_process(self, process_id):
        """
        Llama al endpoint para crear un proceso de packing a partir de un proceso de picking.
        
        :param process_id: ID del proceso de picking.
        :return: Resultado de la petición.
        """
        endpoint = API_ROUTES["PACKING_CREATE"].format(id=process_id)
        return self.api_client._make_post_request(endpoint, {})

    def view_packing_process(self, process_id):
        """
        Obtiene el detalle de un proceso de packing.
        
        :param process_id: ID del proceso.
        :return: Detalle del proceso (diccionario) o None.
        """
        endpoint = API_ROUTES["PACKING_VIEW"].format(id=process_id)
        return self.api_client._make_get_request(endpoint)
