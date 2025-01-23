## Deployment Guide

### Prerequisites
- Python 3.12 or higher
- Docker and docker-compose
- Access to Anthropic API

### Environment Setup
1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate  # Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration
1. Copy `.env.sample` to `.env`
2. Set required environment variables:
   - `CLAUDE_API_KEY`: Your Anthropic API key
   - `LOG_LEVEL`: Desired logging level (DEBUG/INFO/WARNING/ERROR)
   - `STORAGE_DIR`: Directory for data persistence
   - `MAX_RETRIES`: Maximum API retry attempts

### Docker Deployment
1. Build the container:
   ```bash
   docker-compose build
   ```
2. Start services:
   ```bash
   docker-compose up -d
   ```
3. Verify deployment:
   ```bash
   curl http://localhost:8000/health
   ```

### Manual Deployment
1. Create required directories:
   ```bash
   mkdir -p logs config dist data/conversations
   ```
2. Start the server:
   ```bash
   python src/server.py
   ```

### Monitoring
- Health check endpoint: `GET /health`
- Metrics endpoint: `GET /metrics`
- Logs location: `logs/prompt_log_*.jsonl`

### Backup and Restore
1. Create backup:
   ```bash
   ./scripts/backup.sh
   ```
2. Restore from backup:
   ```bash
   ./scripts/restore.sh <backup_file>
   ```

### Updates and Rollbacks
1. Update to new version:
   ```bash
   git pull
   docker-compose up -d --build
   ```
2. Rollback to previous version:
   ```bash
   git checkout <previous_tag>
   docker-compose up -d --build
   ```

### Troubleshooting
- Check logs: `docker-compose logs -f`
- Verify permissions: `ls -l data/`
- Test API connection: `curl http://localhost:8000/api/v1/health`
- Monitor resources: `docker stats` 