#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CV_SRC="/home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/sample_cvs/Nguyen_Van_A_Frontend_Developer.docx"

docker cp "$DIR/seed.py" speakcv_backend:/app/_demo_seed.py
docker cp "$CV_SRC" speakcv_backend:/app/_demo_cv.docx
docker exec -w /app speakcv_backend python /app/_demo_seed.py
