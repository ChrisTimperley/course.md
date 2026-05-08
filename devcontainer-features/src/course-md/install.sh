#!/usr/bin/env bash
set -euo pipefail

COURSEMD_REF="${VERSION:-v0.1.0}"
SLIDES="${SLIDES:-true}"
OCR="${OCR:-false}"
LATEX="${LATEX:-false}"
LINTERS="${LINTERS:-true}"

MKDOCS_MATERIAL_VERSION="${MKDOCSMATERIALVERSION:-9.5.0}"
PRE_COMMIT_VERSION="${PRECOMMITVERSION:-3.4.0}"
MARKITDOWN_VERSION="${MARKITDOWNVERSION:-0.1.3}"
MARKDOWNLINTCLI_VERSION="${MARKDOWNLINTCLIVERSION:-0.45.0}"
PRETTIER_VERSION="${PRETTIERVERSION:-3.6.2}"
NODE_MAJOR_VERSION="${NODEMAJORVERSION:-22}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Script must be run as root."
    exit 1
fi

if [ ! -f /etc/os-release ]; then
    echo "Unsupported image: /etc/os-release is missing."
    exit 1
fi

. /etc/os-release

case "${ID:-}" in
    debian|ubuntu)
        ;;
    *)
        echo "Unsupported distribution '${ID:-unknown}'. This Feature currently supports Debian and Ubuntu images."
        exit 1
        ;;
esac

export DEBIAN_FRONTEND=noninteractive

apt_get_update_if_needed() {
    if [ ! -d /var/lib/apt/lists ] || [ -z "$(find /var/lib/apt/lists -mindepth 1 -maxdepth 1 2>/dev/null)" ]; then
        apt-get update
    fi
}

ensure_apt_packages() {
    local package
    local missing=()

    apt_get_update_if_needed

    for package in "$@"; do
        if ! dpkg -s "$package" >/dev/null 2>&1; then
            missing+=("$package")
        fi
    done

    if [ "${#missing[@]}" -gt 0 ]; then
        apt-get install -y --no-install-recommends "${missing[@]}"
    fi
}

ensure_base_packages() {
    ensure_apt_packages \
        ca-certificates \
        curl \
        fonts-noto-color-emoji \
        git-lfs \
        pandoc \
        python3-pip \
        sudo
}

ensure_slide_packages() {
    if [ "$SLIDES" = "true" ]; then
        ensure_apt_packages \
            bubblewrap \
            chromium
    fi

    if [ "$OCR" = "true" ]; then
        ensure_apt_packages tesseract-ocr
    fi

    if [ "$LATEX" = "true" ]; then
        ensure_apt_packages \
            latexmk \
            texlive-latex-base
    fi
}

ensure_python_tools() {
    python3 -m pip install --break-system-packages \
        "course.md[all] @ git+https://github.com/ChrisTimperley/coursemd.git@${COURSEMD_REF}" \
        "mkdocs-material>=${MKDOCS_MATERIAL_VERSION}" \
        "pre-commit==${PRE_COMMIT_VERSION}" \
        "markitdown[all]==${MARKITDOWN_VERSION}"
}

ensure_node_runtime() {
    if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
        return
    fi

    apt_get_update_if_needed
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR_VERSION}.x" | bash -
    apt-get install -y --no-install-recommends nodejs
}

ensure_node_tools() {
    if [ "$LINTERS" != "true" ]; then
        return
    fi

    ensure_node_runtime

    npm install -g \
        "markdownlint-cli@${MARKDOWNLINTCLI_VERSION}" \
        "prettier@${PRETTIER_VERSION}"
}

ensure_base_packages
ensure_slide_packages
ensure_python_tools
ensure_node_tools

git lfs install --system || true
rm -rf /var/lib/apt/lists/*
