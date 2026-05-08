#!/bin/bash

set -e

source dev-container-features-test-lib

check "coursemd" coursemd --help
check "python import" bash -c "python3 -c 'import coursemd'"
check "git-lfs" git-lfs --version
check "pandoc" pandoc --version
check "pre-commit" pre-commit --version
check "chromium" chromium --version
check "markdownlint" markdownlint --version
check "prettier" prettier --version

reportResults