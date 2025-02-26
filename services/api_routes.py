API_ROUTES = {
    "LOGIN":           "/login",
    "LOGOUT":          "/logout",
    "VALIDATE_PROD":   "/product/validate/{barcode}",
    "VALIDATE_LOC":    "/location/validate/{barcode}",
    "GET_ORDER":      "/getOrder/{id}",
    "PACKING_LIST":    "/packing/process",
    "PACKING_VIEW":    "/packing/process/view/{id}",
    "PACKING_CREATE":  "/packing/process/create/{id}",
    "PACKING_CONFIRM": "/packing/process/confirm/{packingProcessOrder_id}/{packingProcess_id}"
}