#!/bin/bash

set -e

source dev-container-features-test-lib

check "coursemd" coursemd --help
check "tesseract" tesseract --version
check "latexmk" latexmk --version
check "chromium omitted" bash -c "! command -v chromium >/dev/null 2>&1"
check "markdownlint omitted" bash -c "! command -v markdownlint >/dev/null 2>&1"
check "prettier omitted" bash -c "! command -v prettier >/dev/null 2>&1"

reportResults