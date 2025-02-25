API_ROUTES = {
    "LOGIN":           "/login",
    "LOGOUT":          "/logout",
    "VALIDATE_PROD":   "/product/validate/{barcode}",
    "VALIDATE_LOC":    "/location/validate/{barcode}",
    "ASSIGN_LOC":      "/assign/location",
    "MOVE_STOCK":      "/move/product/location/stock",
    "GET_LOC_PROD":    "/get_location_products",
    "DISCREPANCY":     "/get_discrepancy_stock_products",
    
    "PACKING_LIST":    "/packing/process",
    "PACKING_VIEW":    "/packing/process/view/{id}",
    "PACKING_CREATE":  "/packing/process/create/{id}",
    "PACKING_CONFIRM": "/packing/process/confirm/{packingProcessOrder_id}/{packingProcess_id}"
}
