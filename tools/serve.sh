#!/usr/bin/env sh
# Serve the browser preview.  sh tools/serve.sh  ->  http://127.0.0.1:7720
set -e
cd "$(dirname "$0")/.."
sh tools/build_wasm.sh
cd preview
printf 'preview on http://127.0.0.1:7720\n'
python3 -m http.server 7720 --bind 127.0.0.1
