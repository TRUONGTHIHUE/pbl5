idf_component_register(
    SRCS "main.c" "wifi_policy.c"
    INCLUDE_DIRS "."
    REQUIRES esp_wifi esp_event esp_netif nvs_flash json esp_timer esp_hw_support
             esp_driver_spi esp_driver_gpio esp_driver_uart
)
