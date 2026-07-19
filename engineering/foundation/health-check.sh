#!/usr/bin/env bash
# ============================================================================
# Aego Cyber Cafe — Health Check Script
# Monitors all critical services and system health
# Runs every 15 minutes via systemd timer
# ============================================================================
set -uo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AEGO_HOME="/opt/aego"
AEGO_LOGS="$AEGO_HOME/logs/health"
HEALTH_LOG="$AEGO_LOGS/health.log"
HEALTH_STATE_FILE="$AEGO_LOGS/health-state.json"

# Thresholds
DISK_WARN_PERCENT=80
DISK_CRIT_PERCENT=90
TEMP_WARN_CELSIUS=70
TEMP_CRIT_CELSIUS=80
MEMORY_WARN_PERCENT=85
CPU_LOAD_WARN=4.0

# Services to check
declare -A SERVICES=(
    ["ollama"]="http://localhost:11434/api/tags"
    ["openclaw"]="http://localhost:3000/health"
    ["n8n"]="http://localhost:5678/healthz"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$HEALTH_LOG"
}

warn()  { log "⚠️  WARN: $*"; }
ok()    { log "✅ OK: $*"; }
crit()  { log "🔴 CRITICAL: $*"; }

# Result tracking
OVERALL_STATUS="healthy"
declare -A CHECK_RESULTS

set_status() {
    local check="$1" status="$2" detail="$3"
    CHECK_RESULTS["$check"]="$status|$detail"
    if [[ "$status" == "CRITICAL" ]]; then
        OVERALL_STATUS="critical"
        crit "$check: $detail"
    elif [[ "$status" == "WARN" && "$OVERALL_STATUS" != "critical" ]]; then
        OVERALL_STATUS="warning"
        warn "$check: $detail"
    else
        ok "$check: $detail"
    fi
}

# ---------------------------------------------------------------------------
# Ensure log directory exists
# ---------------------------------------------------------------------------
mkdir -p "$AEGO_LOGS"

log "========== Health Check Started =========="

# ---------------------------------------------------------------------------
# Check 1: Disk Space
# ---------------------------------------------------------------------------
check_disk() {
    local usage_percent
    usage_percent=$(df -h / | awk 'NR==2 {gsub(/%/,""); print $5}')

    if [[ "$usage_percent" -ge "$DISK_CRIT_PERCENT" ]]; then
        set_status "disk" "CRITICAL" "Disk usage at ${usage_percent}% (threshold: ${DISK_CRIT_PERCENT}%)"
    elif [[ "$usage_percent" -ge "$DISK_WARN_PERCENT" ]]; then
        set_status "disk" "WARN" "Disk usage at ${usage_percent}% (threshold: ${DISK_WARN_PERCENT}%)"
    else
        set_status "disk" "OK" "Disk usage at ${usage_percent}%"
    fi
}

# ---------------------------------------------------------------------------
# Check 2: CPU Temperature (Raspberry Pi thermal)
# ---------------------------------------------------------------------------
check_temperature() {
    local temp_raw temp_c

    # Try thermal zone (works on Pi)
    if [[ -f /sys/class/thermal/thermal_zone0/temp ]]; then
        temp_raw=$(cat /sys/class/thermal/thermal_zone0/temp)
        temp_c=$((temp_raw / 1000))
    # Try vcgencmd (Raspberry Pi specific)
    elif command -v vcgencmd &>/dev/null; then
        temp_raw=$(vcgencmd measure_temp 2>/dev/null | grep -oP '[\d.]+' || echo "0")
        temp_c=${temp_raw%.*}
    else
        set_status "temperature" "WARN" "Cannot read temperature (no sensor found)"
        return
    fi

    if [[ "$temp_c" -ge "$TEMP_CRIT_CELSIUS" ]]; then
        set_status "temperature" "CRITICAL" "CPU temperature at ${temp_c}°C — THERMAL THROTTLING LIKELY (threshold: ${TEMP_CRIT_CELSIUS}°C)"
    elif [[ "$temp_c" -ge "$TEMP_WARN_CELSIUS" ]]; then
        set_status "temperature" "WARN" "CPU temperature at ${temp_c}°C (threshold: ${TEMP_WARN_CELSIUS}°C)"
    else
        set_status "temperature" "OK" "CPU temperature at ${temp_c}°C"
    fi
}

# ---------------------------------------------------------------------------
# Check 3: Memory Usage
# ---------------------------------------------------------------------------
check_memory() {
    local mem_total mem_available mem_percent

    mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    mem_available=$(grep MemAvailable /proc/meminfo | awk '{print $2}')

    if [[ "$mem_total" -gt 0 ]]; then
        mem_percent=$(( (mem_total - mem_available) * 100 / mem_total ))

        if [[ "$mem_percent" -ge "$MEMORY_WARN_PERCENT" ]]; then
            set_status "memory" "WARN" "Memory usage at ${mem_percent}% ($(( mem_available / 1024 ))MB free of $(( mem_total / 1024 ))MB)"
        else
            set_status "memory" "OK" "Memory usage at ${mem_percent}% ($(( mem_available / 1024 ))MB free)"
        fi
    else
        set_status "memory" "WARN" "Cannot read memory info"
    fi
}

# ---------------------------------------------------------------------------
# Check 4: CPU Load
# ---------------------------------------------------------------------------
check_cpu_load() {
    local load_1m
    load_1m=$(awk '{print $1}' /proc/loadavg)

    local load_int=${load_1m%.*}
    if [[ "${load_int:-0}" -ge 4 ]]; then
        set_status "cpu_load" "WARN" "Load average: $load_1m (threshold: $CPU_LOAD_WARN)"
    else
        set_status "cpu_load" "OK" "Load average: $load_1m"
    fi
}

# ---------------------------------------------------------------------------
# Check 5: Services (Ollama, OpenClaw, n8n)
# ---------------------------------------------------------------------------
check_services() {
    for service in "${!SERVICES[@]}"; do
        local url="${SERVICES[$service]}"

        # Check if process is running
        local proc_running=false
        case "$service" in
            ollama)
                pgrep -x ollama &>/dev/null && proc_running=true
                ;;
            openclaw)
                pgrep -f "openclaw" &>/dev/null && proc_running=true
                ;;
            n8n)
                pgrep -f "n8n" &>/dev/null && proc_running=true
                ;;
        esac

        # Check HTTP endpoint
        local http_ok=false
        local http_code
        http_code=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$url" 2>/dev/null || echo "000")

        if [[ "$http_code" =~ ^2 ]]; then
            http_ok=true
        fi

        if $proc_running && $http_ok; then
            set_status "service:$service" "OK" "Running and responding (HTTP $http_code)"
        elif $proc_running && ! $http_ok; then
            set_status "service:$service" "WARN" "Process running but HTTP check failed (HTTP $http_code)"
        elif ! $proc_running && $http_ok; then
            set_status "service:$service" "OK" "Responding on HTTP (process check ambiguous)"
        else
            set_status "service:$service" "CRITICAL" "Not running and not responding"
        fi
    done
}

# ---------------------------------------------------------------------------
# Check 6: Internet Connectivity
# ---------------------------------------------------------------------------
check_internet() {
    # Try multiple endpoints
    local reachable=false

    for endpoint in "8.8.8.8" "1.1.1.1" "google.com"; do
        if ping -c 1 -W 3 "$endpoint" &>/dev/null; then
            reachable=true
            break
        fi
    done

    if $reachable; then
        # Check actual DNS + HTTP
        if curl -sf --connect-timeout 5 --max-time 10 "https://www.google.com" -o /dev/null 2>/dev/null; then
            set_status "internet" "OK" "Internet connectivity available"
        else
            set_status "internet" "WARN" "Ping works but HTTP blocked (possible captive portal)"
        fi
    else
        set_status "internet" "WARN" "No internet connectivity (offline mode — local AI still works)"
    fi
}

# ---------------------------------------------------------------------------
# Check 7: USB Drive (for backups)
# ---------------------------------------------------------------------------
check_usb() {
    local usb_found=false
    for usb_mount in "/media/usb" "/media/usb0" "/mnt/usb"; do
        if [[ -d "$usb_mount" ]] && mountpoint -q "$usb_mount" 2>/dev/null; then
            local usb_usage
            usb_usage=$(df -h "$usb_mount" | awk 'NR==2 {print $5}')
            set_status "usb_backup" "OK" "USB drive mounted at $usb_mount (usage: $usb_usage)"
            usb_found=true
            break
        fi
    done

    if ! $usb_found; then
        set_status "usb_backup" "WARN" "No USB drive mounted (backups only on SD card)"
    fi
}

# ---------------------------------------------------------------------------
# Check 8: Ollama Models
# ---------------------------------------------------------------------------
check_models() {
    local models_json
    models_json=$(curl -sf --connect-timeout 5 "http://localhost:11434/api/tags" 2>/dev/null)

    if [[ -n "$models_json" ]]; then
        local model_count
        model_count=$(echo "$models_json" | jq '.models | length' 2>/dev/null || echo "0")

        if [[ "$model_count" -gt 0 ]]; then
            local model_names
            model_names=$(echo "$models_json" | jq -r '.models[].name' 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
            set_status "models" "OK" "$model_count model(s) loaded: $model_names"
        else
            set_status "models" "WARN" "Ollama running but no models loaded"
        fi
    else
        set_status "models" "WARN" "Cannot check models (Ollama not responding)"
    fi
}

# ---------------------------------------------------------------------------
# Run All Checks
# ---------------------------------------------------------------------------
check_disk
check_temperature
check_memory
check_cpu_load
check_services
check_internet
check_usb
check_models

# ---------------------------------------------------------------------------
# Write State File (JSON)
# ---------------------------------------------------------------------------
{
    echo "{"
    echo "  \"timestamp\": \"$(date -Iseconds)\","
    echo "  \"overall\": \"$OVERALL_STATUS\","
    echo "  \"checks\": {"
    local first=true
    for check in "${!CHECK_RESULTS[@]}"; do
        IFS='|' read -r status detail <<< "${CHECK_RESULTS[$check]}"
        if $first; then first=false; else echo ","; fi
        printf '    "%s": {"status": "%s", "detail": "%s"}' "$check" "$status" "$detail"
    done
    echo ""
    echo "  }"
    echo "}"
} > "$HEALTH_STATE_FILE"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log "========== Health Check Complete =========="
log "Overall status: $OVERALL_STATUS"

# Return appropriate exit code
case "$OVERALL_STATUS" in
    healthy)  exit 0 ;;
    warning)  exit 0 ;;  # Still OK, just warnings
    critical) exit 1 ;;
esac
