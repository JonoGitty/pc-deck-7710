# DECK-7710 firmware. Build:
#
#   . $IDF_PATH/export.sh
#   idf.py set-target esp32
#   idf.py build
#
# Or, without knowing any of that, from the repo root:
#
#   python3 tools/deckctl.py build --display ssd1322
#
cmake_minimum_required(VERSION 3.16)

# The display target is a build-time decision, not a runtime one: it fixes the
# grid the whole UI is laid out on, and carrying every panel's driver in every
# image to choose between them at boot would be paying flash for a choice
# nobody changes. See docs/VERSIONING.md for why binaries are named after it.
if(NOT DEFINED DECK_DISPLAY)
  set(DECK_DISPLAY "ssd1322" CACHE STRING "panel: ssd1322 | gp1294ai")
endif()
add_compile_definitions(DECK_DISPLAY_$<UPPER_CASE:${DECK_DISPLAY}>=1)

# Flash size, and therefore which partition table. 16 MB is the recommended
# build; 8 MB exists because a 16 MB WROVER is easy to buy as a bare module and
# hard to buy as a board with pins on it. partitions-8mb.csv spells out what
# the smaller layout costs.
if(NOT DEFINED DECK_FLASH)
  set(DECK_FLASH "16" CACHE STRING "flash size in MB: 16 | 8")
endif()
if(DECK_FLASH STREQUAL "8")
  set(SDKCONFIG_DEFAULTS "sdkconfig.defaults;sdkconfig.8mb")
elseif(NOT DECK_FLASH STREQUAL "16")
  message(FATAL_ERROR "DECK_FLASH must be 16 or 8, not '${DECK_FLASH}'")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(deck7710)
