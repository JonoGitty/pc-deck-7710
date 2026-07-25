idf_component_register(
  SRCS "deck_main.c" "deck_config.c" "deck_diag.c" "deck_adc.c" "deck_audio.c"
       "deck_bt.c" "deck_i2s.c" "deck_source.c" "deck_tuner.c" "deck_hfp.c" "deck_input.c" "deck_swc.c" "deck_net.c" "deck_ui.c" "deck_selftest.c"
  INCLUDE_DIRS "."
  REQUIRES deck_core deck_display deck_movies
           nvs_flash bt esp_wifi esp_http_client json driver
           esp_timer app_update esp_partition esp_adc esp_driver_i2c espcoredump esp_netif esp-tls mbedtls)
