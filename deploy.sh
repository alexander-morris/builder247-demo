#!/bin/bash

# Deployment script for Anthropic Agent

# Create required directories
mkdir -p logs config dist data/conversations

# Set up Python environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Set up configuration
if [ ! -f ".env" ]; then
    cp .env.sample .env
    chmod 600 .env
fi

# Build application
python3 setup.py build
cp -r build/* dist/

# Set up logging
touch logs/prompt_log.jsonl
chmod 644 logs/prompt_log.jsonl

# Set up configuration
cp config.sample.json config/config.json
chmod 644 config/config.json

# Set permissions
chmod 755 scripts/*.sh
chmod -R 755 dist
chmod -R 755 logs
chmod -R 755 config
chmod -R 755 data

echo "Deployment completed successfully!"
exit 0 