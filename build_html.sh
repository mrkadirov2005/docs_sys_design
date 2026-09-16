#!/bin/sh
# Regenerate HTML pages from their markdown sources.
# Folders 4 and 5 were produced by a different generator and are not rebuilt here.
set -e
cd "$(dirname "$0")"
build() {
  python3 build_html.py "$1/README.md" "$1/index.html" "$2"
  sed -i '' 's|\(\.\./[^"]*\)/README\.md|\1/index.html|g' "$1/index.html"
}
build "1. OSI_LAYERS_1-2_PHYSICAL_DATALINK"                  "OSI Layers 1 & 2 — Physical & Data Link"
build "2. OSI_LAYERS_3-4_NETWORK_TRANSPORT"                  "OSI Layers 3 & 4 — Network & Transport"
build "3. OSI_LAYERS_5-6-7_SESSION_PRESENTATION_APPLICATION" "OSI Layers 5, 6 & 7 — Session, Presentation & Application"
build "6. REST_RESTFUL_API_BEST_PRACTICES"                   "REST, RESTful APIs & Best Practices"
build "7. PROTOBUF_GRPC_DEEP_DIVE"                            "Protocol Buffers & gRPC Deep Dive"
build "8. GRPC_PRACTICAL_PATTERNS_STREAMING"                  "gRPC Practical Patterns & Streaming"
echo "HTML regenerated."
