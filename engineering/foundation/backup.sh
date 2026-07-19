#!/usr/bin/env bash
# ============================================================================
# Aego Cyber Cafe — Daily Backup Script
# Backs up SQLite databases, OpenClaw config, and n8n data
# Rotates old backups (keeps 7 days)
# ============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AEGO_HOME="/opt/aego"
AEGO_DATA="$AEGO_HOME/data"
AEGO_BACKUP_DIR="$AEGO_DATA/backups"
AEGO_LOGS="$AEGO_HOME/logs"
BACKUP_LOG="$AEGO_LOGS/backup.log"
RETENTION_DAYS=7
DATE_STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_NAME="aego-backup-$DATE_STAMP"
BACKUP_FILE="$AEGO_BACKUP_DIR/$BACKUP_NAME.tar.gz"
OPENCLAW_CONFIG_DIR="${HOME}/.openclaw"

# USB drive mount points to check
USB_MOUNT_POINTS=("/media/usb" "/media/usb0" "/mnt/usb" "/run/media/$USER")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$BACKUP_LOG"
}

err() {
    log "ERROR: $*"
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
mkdir -p "$AEGO_BACKUP_DIR"
mkdir -p "$(dirname "$BACKUP_LOG")"

log "=== Backup started: $BACKUP_NAME ==="

# ---------------------------------------------------------------------------
# Step 1: Create temporary staging directory
# ---------------------------------------------------------------------------
STAGING_DIR=$(mktemp -d)
trap 'rm -rf "$STAGING_DIR"' EXIT

log "Staging backup in $STAGING_DIR"

# ---------------------------------------------------------------------------
# Step 2: Backup SQLite databases
# ---------------------------------------------------------------------------
log "Backing up SQLite databases..."
DB_COUNT=0

# Find all .sqlite and .db files under /opt/aego/data
while IFS= read -r -d '' db_file; do
    if [[ -f "$db_file" ]]; then
        db_rel="${db_file#$AEGO_DATA/}"
        db_dest="$STAGING_DIR/databases/$db_rel"
        mkdir -p "$(dirname "$db_dest")"

        # Use sqlite3 .backup for safe hot backup
        if command -v sqlite3 &>/dev/null; then
            sqlite3 "$db_file" ".backup '$db_dest'" 2>/dev/null && {
                log "  ✓ $db_rel (sqlite3 backup)"
                ((DB_COUNT++))
            } || {
                # Fallback: copy if sqlite3 backup fails
                cp "$db_file" "$db_dest" && {
                    log "  ✓ $db_rel (file copy)"
                    ((DB_COUNT++))
                }
            }
        else
            cp "$db_file" "$db_dest" && {
                log "  ✓ $db_rel (file copy)"
                ((DB_COUNT++))
            }
        fi
    fi
done < <(find "$AEGO_DATA" -type f \( -name "*.sqlite" -o -name "*.db" \) -print0 2>/dev/null)

# Also check OpenClaw's database if it exists
if [[ -d "$OPENCLAW_CONFIG_DIR" ]]; then
    while IFS= read -r -d '' db_file; do
        db_rel="${db_file#$OPENCLAW_CONFIG_DIR/}"
        db_dest="$STAGING_DIR/openclaw-db/$db_rel"
        mkdir -p "$(dirname "$db_dest")"
        cp "$db_file" "$db_dest" && {
            log "  ✓ openclaw/$db_rel"
            ((DB_COUNT++))
        }
    done < <(find "$OPENCLAW_CONFIG_DIR" -type f \( -name "*.sqlite" -o -name "*.db" \) -print0 2>/dev/null)
fi

log "Backed up $DB_COUNT database files"

# ---------------------------------------------------------------------------
# Step 3: Backup OpenClaw configuration
# ---------------------------------------------------------------------------
log "Backing up OpenClaw configuration..."

if [[ -d "$OPENCLAW_CONFIG_DIR" ]]; then
    mkdir -p "$STAGING_DIR/openclaw-config"

    # Copy config files (skip large model/session data)
    for item in config.yaml config.json agents/ identity/ credentials/; do
        if [[ -e "$OPENCLAW_CONFIG_DIR/$item" ]]; then
            cp -r "$OPENCLAW_CONFIG_DIR/$item" "$STAGING_DIR/openclaw-config/" 2>/dev/null || true
            log "  ✓ openclaw/$item"
        fi
    done
else
    log "  ⚠ OpenClaw config directory not found at $OPENCLAW_CONFIG_DIR"
fi

# ---------------------------------------------------------------------------
# Step 4: Backup n8n workflows
# ---------------------------------------------------------------------------
log "Backing up n8n data..."

if [[ -d "$AEGO_DATA/n8n" ]]; then
    mkdir -p "$STAGING_DIR/n8n"

    # Backup n8n database and workflows
    for item in database.sqlite workflows; do
        if [[ -e "$AEGO_DATA/n8n/$item" ]]; then
            cp -r "$AEGO_DATA/n8n/$item" "$STAGING_DIR/n8n/" 2>/dev/null || true
            log "  ✓ n8n/$item"
        fi
    done
fi

# ---------------------------------------------------------------------------
# Step 5: Backup Aego skills
# ---------------------------------------------------------------------------
log "Backing up skills..."

if [[ -d "$AEGO_HOME/skills" ]] && [[ -n "$(ls -A "$AEGO_HOME/skills" 2>/dev/null)" ]]; then
    cp -r "$AEGO_HOME/skills" "$STAGING_DIR/skills"
    log "  ✓ skills/"
fi

# ---------------------------------------------------------------------------
# Step 6: Create compressed archive
# ---------------------------------------------------------------------------
log "Creating backup archive: $BACKUP_FILE"

tar -czf "$BACKUP_FILE" -C "$STAGING_DIR" . 2>/dev/null

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Backup archive created: $BACKUP_SIZE"

# ---------------------------------------------------------------------------
# Step 7: Copy to USB drive if connected
# ---------------------------------------------------------------------------
log "Checking for USB drives..."

USB_BACKED_UP=false
for usb_mount in "${USB_MOUNT_POINTS[@]}"; do
    if [[ -d "$usb_mount" ]] && mountpoint -q "$usb_mount" 2>/dev/null; then
        # Find the actual USB device (usually first subdirectory)
        usb_dest=$(find "$usb_mount" -maxdepth 1 -type d | head -2 | tail -1)
        if [[ -n "$usb_dest" && "$usb_dest" != "$usb_mount" ]]; then
            log "USB drive detected at $usb_dest"
            mkdir -p "$usb_dest/aego-backups"
            cp "$BACKUP_FILE" "$usb_dest/aego-backups/" && {
                log "  ✓ Backup copied to USB: $usb_dest/aego-backups/"
                USB_BACKED_UP=true
            } || {
                err "Failed to copy to USB drive"
            }
            break
        fi
    fi
done

if [[ "$USB_BACKED_UP" == "false" ]]; then
    log "  ⚠ No USB drive detected — backup only on local storage"
fi

# ---------------------------------------------------------------------------
# Step 8: Rotate old backups (keep last 7 days)
# ---------------------------------------------------------------------------
log "Rotating old backups (keeping last $RETENTION_DAYS days)..."

DELETED_COUNT=0
while IFS= read -r -d '' old_backup; do
    rm -f "$old_backup" && ((DELETED_COUNT++))
done < <(find "$AEGO_BACKUP_DIR" -name "aego-backup-*.tar.gz" -mtime +"$RETENTION_DAYS" -print0 2>/dev/null)

log "Deleted $DELETED_COUNT old backup(s)"

# Also rotate USB backups
for usb_mount in "${USB_MOUNT_POINTS[@]}"; do
    if [[ -d "$usb_mount" ]]; then
        usb_dest=$(find "$usb_mount" -maxdepth 1 -type d | head -2 | tail -1)
        if [[ -d "$usb_dest/aego-backups" ]]; then
            find "$usb_dest/aego-backups" -name "aego-backup-*.tar.gz" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
        fi
    fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
TOTAL_BACKUPS=$(find "$AEGO_BACKUP_DIR" -name "aego-backup-*.tar.gz" 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$AEGO_BACKUP_DIR" 2>/dev/null | cut -f1)

log "=== Backup complete ==="
log "  Archive: $BACKUP_FILE ($BACKUP_SIZE)"
log "  Databases: $DB_COUNT files"
log "  USB copy: $USB_BACKED_UP"
log "  Total backups on disk: $TOTAL_BACKUPS ($TOTAL_SIZE)"
log "  Retention: $RETENTION_DAYS days"
