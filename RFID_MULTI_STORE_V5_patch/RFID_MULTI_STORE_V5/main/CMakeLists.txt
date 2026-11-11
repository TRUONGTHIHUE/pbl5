idf_component_register(
    SRCS "main.c" "store_codec.c"
    INCLUDE_DIRS "."
    REQUIRES esp_wifi esp_event esp_netif nvs_flash json esp_driver_spi esp_driver_gpio esp_driver_uart
)
