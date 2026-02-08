#!/bin/sh
# Aletheia Installation Script
# Usage: curl -fsSL https://raw.githubusercontent.com/vmarchese/aletheia/main/install.sh | sh
#
# Environment variables:
#   ALETHEIA_INSTALL_DIR - Installation directory (default: XDG-compliant per OS)
#   ALETHEIA_VERSION     - Git tag/branch to install (default: main)

set -e

# Colors and formatting (matching Rich module colors from banner.txt)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color
# Banner colors
BRIGHT_WHITE='\033[97m'
GOLD='\033[38;5;220m'
BRIGHT_CYAN='\033[96m'
ITALIC='\033[3m'

# Helper functions
info() {
    printf "${BLUE}==>${NC} ${BOLD}%s${NC}\n" "$1"
}

success() {
    printf "${GREEN}==>${NC} ${BOLD}%s${NC}\n" "$1"
}

warn() {
    printf "${YELLOW}Warning:${NC} %s\n" "$1"
}

error() {
    printf "${RED}Error:${NC} %s\n" "$1" >&2
    exit 1
}

check_cmd() {
    command -v "$1" >/dev/null 2>&1
}

# Banner
print_banner() {
    echo ""
    printf "${BRIGHT_WHITE} █  █████████████ █ ${NC}\n"
    printf "${BRIGHT_WHITE}  ██    █   █    █  ${NC}\n"
    printf "${BRIGHT_WHITE}  █  ██  █ █  ██  █ ${NC} ${GOLD} █████╗ ██╗     ███████╗████████╗██╗  ██╗███████╗██╗ █████╗  ${NC}\n"
    printf "${BRIGHT_WHITE}   █    ██ ██    █  ${NC} ${GOLD}██╔══██╗██║     ██╔════╝╚══██╔══╝██║  ██║██╔════╝██║██╔══██╗ ${NC}\n"
    printf "${BRIGHT_WHITE}  █ ████  █  ██████ ${NC} ${GOLD}██║  ██║██║     ██║        ██║   ██║  ██║██║     ██║██║  ██║ ${NC}\n"
    printf "${BRIGHT_WHITE}  █           █████ ${NC} ${GOLD}███████║██║     █████╗     ██║   ███████║█████╗  ██║███████║ ${NC}\n"
    printf "${BRIGHT_WHITE}   ██          ████ ${NC} ${GOLD}██╔══██║██║     ██╔══╝     ██║   ██╔══██║██╔══╝  ██║██╔══██║ ${NC}\n"
    printf "${BRIGHT_WHITE}     ████        █  ${NC} ${GOLD}██║  ██║███████╗███████╗   ██║   ██║  ██║███████╗██║██║  ██║ ${NC}\n"
    printf "${BRIGHT_WHITE}          ████████  ${NC} ${GOLD}╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝╚═╝  ╚═╝ ${NC}\n"
    echo ""
    printf "                     ${BRIGHT_CYAN}* Un-hide incidents - Explain the why *${NC}\n"
    printf "${ITALIC}"
    echo ""
    echo "  Aletheia may confidently explain the wrong thing -- verify before you change"
    echo "  anything, and keep your rollback nearby. Happy Troubleshooting!"
    printf "${NC}"
    echo ""
}

# Detect OS
detect_os() {
    OS="$(uname -s)"
    case "$OS" in
        Linux*)     OS_TYPE="linux";;
        Darwin*)    OS_TYPE="macos";;
        CYGWIN*|MINGW*|MSYS*)
            error "Windows is not supported. Please use WSL2 instead."
            ;;
        *)
            error "Unsupported operating system: $OS"
            ;;
    esac
}

# Get XDG-compliant install directory
get_install_dir() {
    if [ -n "$ALETHEIA_INSTALL_DIR" ]; then
        INSTALL_DIR="$ALETHEIA_INSTALL_DIR"
    elif [ "$OS_TYPE" = "macos" ]; then
        INSTALL_DIR="$HOME/Library/Application Support/aletheia"
    else
        INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/aletheia"
    fi
}

# Get config directory
get_config_dir() {
    if [ "$OS_TYPE" = "macos" ]; then
        CONFIG_DIR="$HOME/Library/Application Support/aletheia"
    else
        CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/aletheia"
    fi
}

# Check Python version
check_python() {
    info "Checking Python installation..."

    # Try python3.12 first, then python3.11, python3.10, then python3
    for py in python3.12 python3.11 python3.10 python3; do
        if check_cmd "$py"; then
            PYTHON_VERSION=$("$py" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
            PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

            if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
                PYTHON_CMD="$py"
                success "Found Python $PYTHON_VERSION"
                return 0
            fi
        fi
    done

    error "Python 3.10 or higher is required. Please install Python 3.10+ and try again.

    Installation instructions:
    - macOS: brew install python@3.12
    - Ubuntu/Debian: sudo apt install python3.12
    - Fedora: sudo dnf install python3.12"
}

# Check and install uv
check_uv() {
    info "Checking uv package manager..."

    if check_cmd uv; then
        success "Found uv"
        return 0
    fi

    info "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Source the cargo env to get uv in PATH
    if [ -f "$HOME/.cargo/env" ]; then
        . "$HOME/.cargo/env"
    fi

    # Also check common install locations
    if [ -f "$HOME/.local/bin/uv" ]; then
        export PATH="$HOME/.local/bin:$PATH"
    fi

    if check_cmd uv; then
        success "uv installed successfully"
    else
        error "Failed to install uv. Please install it manually: https://docs.astral.sh/uv/getting-started/installation/"
    fi
}

# Check Git
check_git() {
    info "Checking Git installation..."

    if check_cmd git; then
        success "Found Git"
    else
        error "Git is required but not installed.

    Installation instructions:
    - macOS: xcode-select --install
    - Ubuntu/Debian: sudo apt install git
    - Fedora: sudo dnf install git"
    fi
}

# Clone or update repository
clone_repository() {
    VERSION="${ALETHEIA_VERSION:-main}"
    REPO_URL="https://github.com/vmarchese/aletheia.git"

    if [ -d "$INSTALL_DIR/.git" ]; then
        info "Updating existing installation..."
        cd "$INSTALL_DIR"
        git fetch origin
        git checkout "$VERSION"
        git pull origin "$VERSION" 2>/dev/null || true
    else
        info "Cloning Aletheia repository..."
        mkdir -p "$(dirname "$INSTALL_DIR")"
        git clone --branch "$VERSION" "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi

    success "Repository ready at $INSTALL_DIR"
}

# Create virtual environment and install
install_package() {
    info "Creating Python virtual environment..."
    cd "$INSTALL_DIR"

    uv venv --python python3.12 2>/dev/null || uv venv --python python3.11 2>/dev/null || uv venv --python python3.10 2>/dev/null || uv venv

    info "Installing Aletheia..."
    uv pip install -e . --prerelease=allow

    success "Aletheia installed successfully"
}

# Setup configuration
setup_config() {
    info "Setting up configuration..."

    mkdir -p "$CONFIG_DIR"
    mkdir -p "$CONFIG_DIR/skills"
    mkdir -p "$CONFIG_DIR/commands"
    mkdir -p "$CONFIG_DIR/instructions"
    mkdir -p "$CONFIG_DIR/agents"

    # Copy example config if it doesn't exist
    if [ ! -f "$CONFIG_DIR/config.yaml" ] && [ -f "$INSTALL_DIR/config.yaml.example" ]; then
        cp "$INSTALL_DIR/config.yaml.example" "$CONFIG_DIR/config.yaml"
        success "Created config file at $CONFIG_DIR/config.yaml"
    fi

    # Copy .env.example if it doesn't exist
    if [ ! -f "$CONFIG_DIR/.env" ] && [ -f "$INSTALL_DIR/.env.example" ]; then
        cp "$INSTALL_DIR/.env.example" "$CONFIG_DIR/.env"
        success "Created .env file at $CONFIG_DIR/.env"
    fi
}

# Create shell wrapper
create_wrapper() {
    info "Creating shell wrapper..."

    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"

    WRAPPER="$BIN_DIR/aletheia"

    cat > "$WRAPPER" << EOF
#!/bin/sh
# Aletheia wrapper script
INSTALL_DIR="$INSTALL_DIR"
. "\$INSTALL_DIR/.venv/bin/activate"
exec python -m aletheia.cli "\$@"
EOF

    chmod +x "$WRAPPER"
    success "Created wrapper at $WRAPPER"
}


# Print success message
print_success() {
    SHELL_NAME="$(basename "$SHELL")"

    echo ""
    printf "${GREEN}${BOLD}"
    echo "============================================"
    echo "  Aletheia installed successfully!"
    echo "============================================"
    printf "${NC}"
    echo ""
    echo "Installation directory: $INSTALL_DIR"
    echo "Configuration directory: $CONFIG_DIR"
    echo ""
    printf "${BOLD}Next steps:${NC}\n"
    echo ""
    echo "1. Add ~/.local/bin to your PATH by adding this to your shell config:"
    echo ""
    case "$SHELL_NAME" in
        zsh)
            printf "   ${BLUE}echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc${NC}\n"
            ;;
        bash)
            printf "   ${BLUE}echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc${NC}\n"
            ;;
        fish)
            printf "   ${BLUE}echo 'set -gx PATH \$HOME/.local/bin \$PATH' >> ~/.config/fish/config.fish${NC}\n"
            ;;
        *)
            printf "   ${BLUE}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}\n"
            ;;
    esac
    echo ""
    echo "2. Configure your LLM API key in $CONFIG_DIR/config.yaml"
    echo "   or set the environment variable:"
    printf "   ${BLUE}export OPENAI_API_KEY='your-api-key'${NC}\n"
    echo ""
    echo "3. Restart your terminal or run:"
    case "$SHELL_NAME" in
        zsh)
            printf "   ${BLUE}source ~/.zshrc${NC}\n"
            ;;
        bash)
            printf "   ${BLUE}source ~/.bashrc${NC}\n"
            ;;
        fish)
            printf "   ${BLUE}source ~/.config/fish/config.fish${NC}\n"
            ;;
        *)
            echo "   (restart your terminal)"
            ;;
    esac
    echo ""
    echo "4. Start Aletheia:"
    printf "   ${BLUE}aletheia start${NC}           # Start the gateway\n"
    printf "   ${BLUE}aletheia status${NC}          # Check status\n"
    echo ""
    echo "5. Connect with a channel (in a new terminal):"
    printf "   ${BLUE}python -m aletheia.channels.tui${NC}   # Terminal UI\n"
    printf "   ${BLUE}python -m aletheia.channels.web${NC}   # Web UI at http://localhost:8000\n"
    echo ""
    echo "For more information, visit:"
    echo "https://github.com/vmarchese/aletheia"
    echo ""
}

# Main installation flow
main() {
    print_banner

    detect_os
    get_install_dir
    get_config_dir

    info "Installing Aletheia..."
    echo "  Install directory: $INSTALL_DIR"
    echo "  Config directory: $CONFIG_DIR"
    echo ""

    check_python
    check_git
    check_uv

    clone_repository
    install_package
    setup_config
    create_wrapper

    print_success
}

main "$@"
