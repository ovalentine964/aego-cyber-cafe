#!/usr/bin/env bash
# ============================================================================
# Aego Cyber Cafe — Raspberry Pi 5 Foundation Setup
# Location: Nyatike, Migori County, Kenya
# Target: Raspberry Pi 5 (8GB RAM), Raspberry Pi OS Bookworm (64-bit)
# ============================================================================
set -euo pipefail
IFS=$'\n\t'

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AEGO_HOME="/opt/aego"
AEGO_MODELS="$AEGO_HOME/models"
AEGO_DATA="$AEGO_HOME/data"
AEGO_LOGS="$AEGO_HOME/logs"
AEGO_SKILLS="$AEGO_HOME/skills"
SETUP_LOG="$AEGO_LOGS/setup-$(date +%Y%m%d-%H%M%S).log"
OPENCLAW_CONFIG_DIR="/home/${SUDO_USER:-$USER}/.openclaw"
PIPER_MODEL_DIR="$AEGO_MODELS/piper"
WHISPER_DIR="$AEGO_HOME/whisper.cpp"

# Model versions
OLLAMA_PRIMARY_MODEL="gemma4:4b"
OLLAMA_FALLBACK_MODEL="qwen3.5:3b"
PIPER_VOICE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/sw/ke/siwi/medium/sw_ke-siwi-medium.onnx"
PIPER_VOICE_CONFIG_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/sw/ke/siwi/medium/sw_ke-siwi-medium.onnx.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $*" | tee -a "$SETUP_LOG"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$SETUP_LOG"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" | tee -a "$SETUP_LOG"; }
info()  { echo -e "${BLUE}[INFO]${NC} $*" | tee -a "$SETUP_LOG"; }

die() {
    err "$*"
    err "Setup failed. Check log: $SETUP_LOG"
    exit 1
}

check_running_as_root() {
    if [[ $EUID -ne 0 ]]; then
        die "This script must be run as root. Use: sudo bash setup-pi.sh"
    fi
}

check_pi_model() {
    if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null && ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        warn "This doesn't appear to be a Raspberry Pi. Continuing anyway..."
    else
        local model
        model=$(cat /proc/device-tree/model 2>/dev/null || echo "unknown")
        log "Detected: $model"
    fi
}

check_disk_space() {
    local available_mb
    available_mb=$(df -BM / | awk 'NR==2 {gsub(/M/,"",$4); print $4}')
    if [[ "$available_mb" -lt 8000 ]]; then
        die "Need at least 8GB free disk space. Only ${available_mb}MB available."
    fi
    log "Disk space OK: ${available_mb}MB available"
}

# ---------------------------------------------------------------------------
# Step 1: System Update & Dependencies
# ---------------------------------------------------------------------------
step_system_update() {
    log "=== Step 1/8: System update and dependencies ==="

    apt-get update -y
    apt-get upgrade -y

    # Core dependencies
    apt-get install -y \
        curl wget git build-essential cmake \
        python3 python3-pip python3-venv \
        sqlite3 \
        jq \
        htop \
        iotop \
        net-tools \
        ufw \
        fail2ban \
        logrotate \
        usbmount \
        alsa-utils \
        pulseaudio \
        portaudio19-dev \
        libusb-1.0-0-dev \
        v4l-utils \
        ffmpeg \
        unzip \
        ca-certificates \
        gnupg \
        lsb-release

    # Node.js 20 LTS (required for n8n and OpenClaw)
    if ! command -v node &>/dev/null || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]]; then
        log "Installing Node.js 20 LTS..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
    else
        log "Node.js $(node -v) already installed"
    fi

    # npm global tools
    npm install -g npm@latest

    log "System update complete"
}

# ---------------------------------------------------------------------------
# Step 2: Create Directory Structure
# ---------------------------------------------------------------------------
step_create_directories() {
    log "=== Step 2/8: Creating directory structure ==="

    mkdir -p "$AEGO_HOME"/{models,data,logs,skills}
    mkdir -p "$PIPER_MODEL_DIR"
    mkdir -p "$AEGO_DATA"/{sqlite,backups}
    mkdir -p "$AEGO_LOGS"/{ollama,openclaw,n8n,health}
    mkdir -p "$OPENCLAW_CONFIG_DIR"

    # Set ownership to the original user (not root)
    local real_user="${SUDO_USER:-$USER}"
    chown -R "$real_user:$real_user" "$AEGO_HOME"
    chown -R "$real_user:$real_user" "$OPENCLAW_CONFIG_DIR"

    # Make directories world-readable for services
    chmod 755 "$AEGO_HOME"
    chmod 775 "$AEGO_LOGS"

    log "Directories created at $AEGO_HOME"
}

# ---------------------------------------------------------------------------
# Step 3: Install Ollama + Pull Models
# ---------------------------------------------------------------------------
step_install_ollama() {
    log "=== Step 3/8: Installing Ollama and pulling models ==="

    if command -v ollama &>/dev/null; then
        log "Ollama already installed: $(ollama --version 2>/dev/null || echo 'unknown version')"
    else
        log "Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
    fi

    # Start Ollama temporarily for model pull
    if ! pgrep -x ollama &>/dev/null; then
        log "Starting Ollama service..."
        systemctl start ollama 2>/dev/null || ollama serve &
        sleep 5
    fi

    # Pull models (these are large — may take a while on rural internet)
    log "Pulling $OLLAMA_PRIMARY_MODEL (primary model — this may take 30+ minutes)..."
    ollama pull "$OLLAMA_PRIMARY_MODEL" || warn "Failed to pull $OLLAMA_PRIMARY_MODEL — retry later with: ollama pull $OLLAMA_PRIMARY_MODEL"

    log "Pulling $OLLAMA_FALLBACK_MODEL (multilingual fallback)..."
    ollama pull "$OLLAMA_FALLBACK_MODEL" || warn "Failed to pull $OLLAMA_FALLBACK_MODEL — retry later with: ollama pull $OLLAMA_FALLBACK_MODEL"

    # Enable Ollama service for auto-start
    systemctl enable ollama 2>/dev/null || warn "Could not enable ollama systemd service"

    log "Ollama installed and models pulled"
}

# ---------------------------------------------------------------------------
# Step 4: Install OpenClaw Gateway
# ---------------------------------------------------------------------------
step_install_openclaw() {
    log "=== Step 4/8: Installing OpenClaw Gateway ==="

    if command -v openclaw &>/dev/null; then
        log "OpenClaw already installed: $(openclaw --version 2>/dev/null || echo 'unknown version')"
    else
        log "Installing OpenClaw Gateway..."
        curl -fsSL https://get.openclaw.ai | bash -s -- --yes 2>&1 | tee -a "$SETUP_LOG" || {
            warn "OpenClaw curl install failed. Trying npm install..."
            npm install -g openclaw
        }
    fi

    log "OpenClaw Gateway installed"
}

# ---------------------------------------------------------------------------
# Step 5: Install Piper TTS + Swahili Voice
# ---------------------------------------------------------------------------
step_install_piper() {
    log "=== Step 5/8: Installing Piper TTS ==="

    local piper_bin="/usr/local/bin/piper"

    if [[ -f "$piper_bin" ]]; then
        log "Piper already installed at $piper_bin"
    else
        log "Downloading Piper TTS binary..."
        local arch
        arch=$(uname -m)
        local piper_url

        case "$arch" in
            aarch64|arm64)
                piper_url="https://github.com/rhasspy/piper/releases/latest/download/piper_linux_aarch64.tar.gz"
                ;;
            x86_64)
                piper_url="https://github.com/rhasspy/piper/releases/latest/download/piper_linux_x86_64.tar.gz"
                ;;
            *)
                die "Unsupported architecture: $arch"
                ;;
        esac

        local tmp_dir
        tmp_dir=$(mktemp -d)
        curl -fsSL "$piper_url" -o "$tmp_dir/piper.tar.gz"
        tar -xzf "$tmp_dir/piper.tar.gz" -C "$tmp_dir"
        cp "$tmp_dir/piper/piper" "$piper_bin"
        chmod +x "$piper_bin"
        rm -rf "$tmp_dir"
        log "Piper binary installed to $piper_bin"
    fi

    # Download Swahili voice model
    log "Downloading Swahili (Kenya) voice model..."
    curl -fsSL "$PIPER_VOICE_URL" -o "$PIPER_MODEL_DIR/sw_ke-siwi-medium.onnx" || \
        warn "Failed to download Swahili voice model"
    curl -fsSL "$PIPER_VOICE_CONFIG_URL" -o "$PIPER_MODEL_DIR/sw_ke-siwi-medium.onnx.json" || \
        warn "Failed to download Swahili voice config"

    # Test Piper
    if [[ -f "$PIPER_MODEL_DIR/sw_ke-siwi-medium.onnx" ]]; then
        echo "Karibu Aego Cyber Cafe" | piper \
            --model "$PIPER_MODEL_DIR/sw_ke-siwi-medium.onnx" \
            --output_file "$AEGO_LOGS/piper-test.wav" 2>/dev/null && \
            log "Piper TTS test successful" || \
            warn "Piper TTS test failed — check audio output"
    fi

    log "Piper TTS installed"
}

# ---------------------------------------------------------------------------
# Step 6: Build whisper.cpp from Source
# ---------------------------------------------------------------------------
step_install_whisper() {
    log "=== Step 6/8: Building whisper.cpp ==="

    if [[ -f "$WHISPER_DIR/build/bin/whisper-cli" ]]; then
        log "whisper.cpp already built"
    else
        log "Cloning whisper.cpp..."
        git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git "$WHISPER_DIR" 2>/dev/null || \
            (cd "$WHISPER_DIR" && git pull)

        cd "$WHISPER_DIR"

        log "Building whisper.cpp (this may take 10-20 minutes on Pi 5)..."
        cmake -B build -DCMAKE_BUILD_TYPE=Release \
            -DGGML_CPU_AARCH64=ON 2>&1 | tee -a "$SETUP_LOG"
        cmake --build build -j4 2>&1 | tee -a "$SETUP_LOG"
    fi

    # Download tiny model
    log "Downloading whisper tiny model..."
    cd "$WHISPER_DIR"
    bash models/download-ggml-model.sh tiny 2>&1 | tee -a "$SETUP_LOG" || \
        warn "Model download failed — retry with: cd $WHISPER_DIR && bash models/download-ggml-model.sh tiny"

    # Create symlink for easy access
    ln -sf "$WHISPER_DIR/build/bin/whisper-cli" /usr/local/bin/whisper-cli 2>/dev/null || true

    log "whisper.cpp built and model downloaded"
}

# ---------------------------------------------------------------------------
# Step 7: Install n8n
# ---------------------------------------------------------------------------
step_install_n8n() {
    log "=== Step 7/8: Installing n8n ==="

    if command -v n8n &>/dev/null; then
        log "n8n already installed: $(n8n --version 2>/dev/null || echo 'unknown')"
    else
        log "Installing n8n globally..."
        npm install -g n8n 2>&1 | tee -a "$SETUP_LOG"
    fi

    # Create n8n data directory
    mkdir -p "$AEGO_DATA/n8n"
    chown -R "${SUDO_USER:-$USER}:${SUDO_USER:-$USER}" "$AEGO_DATA/n8n"

    log "n8n installed"
}

# ---------------------------------------------------------------------------
# Step 8: Systemd Services + Firewall
# ---------------------------------------------------------------------------
step_configure_services() {
    log "=== Step 8/8: Configuring services and firewall ==="

    local real_user="${SUDO_USER:-$USER}"

    # --- n8n systemd service ---
    cat > /etc/systemd/system/aego-n8n.service << N8N_SERVICE
[Unit]
Description=Aego n8n Workflow Automation
After=network.target

[Service]
Type=simple
User=$real_user
Environment=N8N_PORT=5678
Environment=N8N_PROTOCOL=http
Environment=N8N_LISTEN_ADDRESS=0.0.0.0
Environment=N8N_BASIC_AUTH_ACTIVE=true
Environment=N8N_BASIC_AUTH_USER=admin
Environment=N8N_BASIC_AUTH_PASSWORD=changeme-aego-2024
Environment=DB_TYPE=sqlite
Environment=DB_SQLITE_DATABASE=$AEGO_DATA/n8n/database.sqlite
Environment=N8N_USER_FOLDER=$AEGO_DATA/n8n
ExecStart=$(which n8n) start
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
N8N_SERVICE

    # --- Aego health check timer ---
    cat > /etc/systemd/system/aego-health-check.service << HEALTH_SERVICE
[Unit]
Description=Aego Cyber Cafe Health Check
After=network.target ollama.service

[Service]
Type=oneshot
User=$real_user
ExecStart=$AEGO_HOME/health-check.sh
StandardOutput=append:$AEGO_LOGS/health/health.log
StandardError=append:$AEGO_LOGS/health/health.log
HEALTH_SERVICE

    cat > /etc/systemd/system/aego-health-check.timer << HEALTH_TIMER
[Unit]
Description=Run Aego health check every 15 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
Persistent=true

[Install]
WantedBy=timers.target
HEALTH_TIMER

    # --- Aego daily backup timer ---
    cat > /etc/systemd/system/aego-backup.service << BACKUP_SERVICE
[Unit]
Description=Aego Daily Backup
After=network.target

[Service]
Type=oneshot
User=$real_user
ExecStart=$AEGO_HOME/backup.sh
BACKUP_SERVICE

    cat > /etc/systemd/system/aego-backup.timer << BACKUP_TIMER
[Unit]
Description=Run Aego backup daily at 2 AM

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
BACKUP_TIMER

    # Reload and enable services
    systemctl daemon-reload
    systemctl enable aego-n8n.service
    systemctl enable aego-health-check.timer
    systemctl enable aego-backup.timer
    systemctl start aego-health-check.timer
    systemctl start aego-backup.timer

    # --- Firewall ---
    log "Configuring firewall (UFW)..."

    # Reset and configure
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing

    # Allow local network only
    ufw allow from 192.168.0.0/16 to any port 22 comment "SSH LAN"
    ufw allow from 10.0.0.0/8 to any port 22 comment "SSH LAN"
    ufw allow from 172.16.0.0/12 to any port 22 comment "SSH LAN"

    # OpenClaw Gateway (local only)
    ufw allow from 192.168.0.0/16 to any port 3000 comment "OpenClaw LAN"
    ufw allow from 10.0.0.0/8 to any port 3000 comment "OpenClaw LAN"

    # n8n web UI (local only)
    ufw allow from 192.168.0.0/16 to any port 5678 comment "n8n LAN"
    ufw allow from 10.0.0.0/8 to any port 5678 comment "n8n LAN"

    # Ollama API (local only)
    ufw allow from 192.168.0.0/16 to any port 11434 comment "Ollama LAN"
    ufw allow from 10.0.0.0/8 to any port 11434 comment "Ollama LAN"

    ufw --force enable
    log "Firewall configured — only local network access allowed"

    # --- Log rotation ---
    cat > /etc/logrotate.d/aego << LOGROTATE
$AEGO_LOGS/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 $real_user $real_user
}

$AEGO_LOGS/**/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 $real_user $real_user
}
LOGROTATE

    log "Services and firewall configured"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║     Aego Cyber Cafe — Raspberry Pi 5 Foundation Setup      ║"
    echo "║     Nyatike, Migori County, Kenya                          ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    # Pre-flight checks
    check_running_as_root
    check_pi_model

    # Create log directory first
    mkdir -p "$AEGO_LOGS"

    log "Setup started at $(date)"
    log "Logging to: $SETUP_LOG"

    check_disk_space

    # Execute steps
    step_system_update
    step_create_directories
    step_install_ollama
    step_install_openclaw
    step_install_piper
    step_install_whisper
    step_install_n8n
    step_configure_services

    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    ✅ SETUP COMPLETE!                       ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  Services:                                                  ║"
    echo "║    • Ollama API    → http://localhost:11434                 ║"
    echo "║    • OpenClaw      → http://localhost:3000                  ║"
    echo "║    • n8n           → http://localhost:5678                  ║"
    echo "║                                                             ║"
    echo "║  Models:                                                    ║"
    echo "║    • Primary:   $OLLAMA_PRIMARY_MODEL                              ║"
    echo "║    • Fallback:  $OLLAMA_FALLBACK_MODEL                             ║"
    echo "║                                                             ║"
    echo "║  Directories:                                               ║"
    echo "║    • Home:    $AEGO_HOME                            ║"
    echo "║    • Models:  $AEGO_MODELS                              ║"
    echo "║    • Data:    $AEGO_DATA                                ║"
    echo "║    • Logs:    $AEGO_LOGS                                ║"
    echo "║                                                             ║"
    echo "║  Next steps:                                                ║"
    echo "║    1. Copy openclaw-config.yaml → ~/.openclaw/config.yaml  ║"
    echo "║    2. Configure WhatsApp bridge (see README.md)            ║"
    echo "║    3. Run: openclaw gateway start                          ║"
    echo "║    4. Test: curl http://localhost:11434/api/tags            ║"
    echo "║                                                             ║"
    echo "║  Log file: $SETUP_LOG                                       ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    log "Setup completed successfully at $(date)"
}

main "$@"
