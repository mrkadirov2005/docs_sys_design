#!/bin/sh
# Regenerate the OSI HTML pages from their markdown sources.
set -e
python3 build_html.py OSI_LAYERS_1-2_PHYSICAL_DATALINK/README.md \
  OSI_LAYERS_1-2_PHYSICAL_DATALINK/index.html \
  "OSI Layers 1 & 2 — Physical & Data Link"
python3 build_html.py OSI_LAYERS_3-4_NETWORK_TRANSPORT/README.md \
  OSI_LAYERS_3-4_NETWORK_TRANSPORT/index.html \
  "OSI Layers 3 & 4 — Network & Transport"
python3 build_html.py OSI_LAYERS_5-6-7_SESSION_PRESENTATION_APPLICATION/README.md \
  OSI_LAYERS_5-6-7_SESSION_PRESENTATION_APPLICATION/index.html \
  "OSI Layers 5, 6 & 7 — Session, Presentation & Application"
for d in OSI_LAYERS_*; do
  sed -i '' 's|\(\.\./OSI_LAYERS_[^"]*\)/README\.md|\1/index.html|g' "$d/index.html"
done
echo "HTML regenerated."
