# core/ is pulled in from the repo root unmodified — the same source the
# browser preview compiles to WASM and the verifier diffs against the legacy
# JavaScript. It is deliberately not copied here: a copy would drift, and the
# moment it drifts the preview stops telling the truth about the panel.
set(CORE "${CMAKE_CURRENT_LIST_DIR}/../../../../core")

idf_component_register(
  SRCS
    "${CORE}/fb.c" "${CORE}/font.c" "${CORE}/text.c" "${CORE}/art.c"
    "${CORE}/out.c" "${CORE}/trig.c" "${CORE}/movie.c"
    "${CORE}/screens/spectrum.c" "${CORE}/screens/mirror.c"
    "${CORE}/screens/scope.c" "${CORE}/screens/city.c"
    "${CORE}/screens/waterfall.c" "${CORE}/screens/vu.c"
    "${CORE}/screens/spectrum3d.c" "${CORE}/screens/cover.c"
    "${CORE}/screens/lyrics.c" "${CORE}/screens/ocean.c"
  INCLUDE_DIRS "${CORE}"
)

# core/ is -Werror clean and stays that way; it is the one part of this
# project that is verified, so a warning here is a real signal.
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
