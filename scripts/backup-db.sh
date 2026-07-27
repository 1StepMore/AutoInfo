#!/usr/bin/env bash
# backup-db.sh — Automated SQLite backup for AutoInfo databases
#
# Backs up the KBStore SQLite index (autoinfo.db) and user store
# (.autoinfo/users.db) using Python's built-in sqlite3 module.
# Keeps only the last 7 backups per database prefix.
#
# Usage: bash scripts/backup-db.sh

set -euo pipefail

# --- Locate project root (scripts/ is one level deep) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Database paths ---
KB_DB="$PROJECT_ROOT/autoinfo.db"
USER_DB="$PROJECT_ROOT/.autoinfo/users.db"

# --- Backup destination ---
BACKUP_DIR="$PROJECT_ROOT/backups"
MAX_BACKUPS=7

timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

do_backup() {
    local db_path="$1"
    local label="$2"
    local backup_file="$BACKUP_DIR/autoinfo-${label}-$(date +%Y%m%d-%H%M%S).db"

    if [ ! -f "$db_path" ]; then
        echo "$(timestamp) [SKIP] $label — database not found at $db_path"
        return 0
    fi

    echo "$(timestamp) [BACKUP] $label → $backup_file"

    # Use Python's sqlite3.backup() — atomic, consistent
    python3 -c "
import sqlite3
src = sqlite3.connect('$db_path')
dst = sqlite3.connect('$backup_file')
src.backup(dst, pages=-1)
src.close()
dst.close()
" || {
        echo "$(timestamp) [FAIL] $label — backup failed"
        rm -f "$backup_file"
        return 1
    }

    # Verify backup is a valid SQLite database
    if ! python3 -c "import sqlite3; sqlite3.connect('$backup_file').execute('PRAGMA schema_version')" > /dev/null 2>&1; then
        echo "$(timestamp) [FAIL] $label — backup file is not a valid SQLite database"
        rm -f "$backup_file"
        return 1
    fi

    local size
    size=$(du -h "$backup_file" | cut -f1)
    echo "$(timestamp) [OK] $label — $size backed up"
}

# --- Create backup directory ---
mkdir -p "$BACKUP_DIR"

# --- Backup each database ---
overall_status=0

do_backup "$KB_DB" "kb" || overall_status=1
do_backup "$USER_DB" "users" || overall_status=1

# --- Rotate old backups: keep only last $MAX_BACKUPS per prefix ---
rotate_prefix() {
    local prefix="$1"
    while IFS= read -r -d '' f; do
        rm -f "$f"
        echo "$(timestamp) [ROTATE] Removed old backup: $(basename "$f")"
    done < <(find "$BACKUP_DIR" -maxdepth 1 -name "autoinfo-${prefix}-*.db" -printf '%T@ %p\0' \
        | sort -rnz \
        | tail -z -n +$((MAX_BACKUPS + 1)) \
        | cut -z -d' ' -f2-)
}

rotate_prefix "kb"
rotate_prefix "users"

# --- Summary ---
echo "$(timestamp) [DONE] Backups in: $BACKUP_DIR"
ls -1t "$BACKUP_DIR" 2>/dev/null | head -n "$MAX_BACKUPS" | while IFS= read -r f; do
    echo "       $f"
done

exit "$overall_status"
