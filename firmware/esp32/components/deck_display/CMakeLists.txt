idf_component_register(SRCS "deck_spi.c" "ssd1322.c" "gp1294ai.c"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_driver_spi esp_driver_gpio deck_core)
