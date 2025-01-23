#!/bin/bash

# Backup script for Anthropic Agent data

# Default values
BACKUP_DIR="/tmp/anthropic-backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="backup_${DATE}.tar.gz"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --daily)
            BACKUP_NAME="daily_backup_${DATE}.tar.gz"
            shift
            ;;
        --manual)
            BACKUP_NAME="${2}_${DATE}.tar.gz"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Create backup
tar -czf "${BACKUP_DIR}/${BACKUP_NAME}" \
    data/conversations \
    logs \
    config \
    .env

# Verify backup
if [ $? -eq 0 ]; then
    echo "Backup created successfully: ${BACKUP_DIR}/${BACKUP_NAME}"
    echo "Backup size: $(du -h ${BACKUP_DIR}/${BACKUP_NAME} | cut -f1)"
else
    echo "Backup failed!"
    exit 1
fi

# Cleanup old backups (keep last 7 days)
find "${BACKUP_DIR}" -name "daily_backup_*.tar.gz" -mtime +7 -delete

exit 0 