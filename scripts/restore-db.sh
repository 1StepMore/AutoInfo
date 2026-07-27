#!/usr/bin/env bash
# restore-db.sh — Restore an AutoInfo SQLite database from backup
#
# Uses Python's sqlite3 module for safe online restore.
#
# Usage: bash scripts/restore-db.sh backups/autoinfo-kb-<timestamp>.db
#        bash scripts/restore-db.sh backups/autoinfo-users-<timestamp>.db

set -euo pipefail

# --- Locate project root ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Source databases (originals) ---
KB_DB="$PROJECT_ROOT/autoinfo.db"
USER_DB="$PROJECT_ROOT/.autoinfo/users.db"

usage() {
    echo "Usage: $0 <backup-file>"
    echo ""
    echo "Restore a backed-up SQLite database to its original location."
    echo ""
    echo "Backup files are named as:"
    echo "  autoinfo-kb-<timestamp>.db    → restores to $KB_DB"
    echo "  autoinfo-users-<timestamp>.db → restores to $USER_DB"
    exit 1
}

# --- Validate argument ---
if [ $# -ne 1 ]; then
    usage
fi

BACKUP_FILE="$(realpath "$1")"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# --- Determine which database to restore ---
BASENAME="$(basename "$BACKUP_FILE")"

case "$BASENAME" in
    autoinfo-kb-*.db)
        TARGET_DB="$KB_DB"
        LABEL="KBStore index (autoinfo.db)"
        ;;
    autoinfo-users-*.db)
        TARGET_DB="$USER_DB"
        LABEL="User store (.autoinfo/users.db)"
        ;;
    *)
        echo "ERROR: Cannot determine target database from filename: $BASENAME"
        echo "Expected: autoinfo-kb-*.db or autoinfo-users-*.db"
        exit 1
        ;;
esac

# --- Show sizes ---
if [ -f "$TARGET_DB" ]; then
    TARGET_SIZE=$(du -h "$TARGET_DB" | cut -f1)
else
    TARGET_SIZE="(does not exist)"
fi
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

echo "========================================"
echo "  Database Restore"
echo "========================================"
echo "  Backup file : $BACKUP_FILE"
echo "  Backup size : $BACKUP_SIZE"
echo "  Target      : $TARGET_DB ($LABEL)"
echo "  Target size : $TARGET_SIZE"
echo "========================================"

# --- Confirm ---
read -r -p "Overwrite $LABEL with this backup? [y/N] " REPLY
if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

# --- Validate backup is a valid SQLite DB ---
if ! python3 -c "import sqlite3; sqlite3.connect('$BACKUP_FILE').execute('PRAGMA schema_version')" > /dev/null 2>&1; then
    echo "ERROR: Backup file is not a valid SQLite database: $BACKUP_FILE"
    exit 1
fi

# --- Restore using Python's backup (source → destination) ---
echo "Restoring $LABEL from backup ..."
python3 -c "
import sqlite3
src = sqlite3.connect('$BACKUP_FILE')
dst = sqlite3.connect('$TARGET_DB')
src.backup(dst, pages=-1)
src.close()
dst.close()
"

# --- Verify restore ---
if python3 -c "import sqlite3; sqlite3.connect('$TARGET_DB').execute('PRAGMA schema_version')" > /dev/null 2>&1; then
    echo "SUCCESS: $LABEL restored from $BACKUP_FILE"
else
    echo "ERROR: Restore completed but target database is not valid!"
    exit 1
fi
