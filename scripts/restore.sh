#!/bin/bash

# Restore script for Anthropic Agent data

# Check arguments
if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

BACKUP_FILE="$1"

# Verify backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo "Using temporary directory: ${TEMP_DIR}"

# Extract backup
echo "Extracting backup..."
tar -xzf "${BACKUP_FILE}" -C "${TEMP_DIR}"

if [ $? -ne 0 ]; then
    echo "Failed to extract backup!"
    rm -rf "${TEMP_DIR}"
    exit 1
fi

# Verify backup contents
required_dirs=("data/conversations" "logs" "config")
for dir in "${required_dirs[@]}"; do
    if [ ! -d "${TEMP_DIR}/${dir}" ]; then
        echo "Missing required directory in backup: ${dir}"
        rm -rf "${TEMP_DIR}"
        exit 1
    fi
done

# Create backup of current data
DATE=$(date +%Y%m%d_%H%M%S)
CURRENT_BACKUP="pre_restore_${DATE}.tar.gz"
echo "Creating backup of current data: ${CURRENT_BACKUP}"
tar -czf "${CURRENT_BACKUP}" data/conversations logs config .env

# Restore data
echo "Restoring data..."
for dir in "${required_dirs[@]}"; do
    rm -rf "${dir}"
    mkdir -p "$(dirname "${dir}")"
    cp -r "${TEMP_DIR}/${dir}" "$(dirname "${dir}")/"
done

# Restore .env if it exists in backup
if [ -f "${TEMP_DIR}/.env" ]; then
    cp "${TEMP_DIR}/.env" .env
fi

# Cleanup
rm -rf "${TEMP_DIR}"

echo "Restore completed successfully!"
echo "Previous data backed up to: ${CURRENT_BACKUP}"

exit 0 