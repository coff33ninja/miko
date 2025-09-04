# Deployment Guide

This guide covers deployment options for the Anime AI Character system, from local development to production containerized deployment.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment Methods](#deployment-methods)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Python**: 3.8 or higher
- **Docker**: 20.10.0 or higher (for containerized deployment)
- **Docker Compose**: 2.0 or higher
- **Memory**: Minimum 4GB RAM (8GB recommended)
- **Storage**: 2GB free space (more for Live2D models)

### Required Services

1. **LiveKit Server**: Either LiveKit Cloud or self-hosted
2. **AI Provider**: Choose one:
   - **Ollama** (local): For privacy and offline operation
   - **Google Gemini** (cloud): For advanced capabilities
3. **Memory Service** (optional):
   - **Mem0**: For persistent conversation memory

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/coff33ninja/project-miko.git
cd project-miko

# Copy environment configuration
cp .env.example .env

# Edit .env with your configuration
# (See Configuration section below)
```

### 2. Choose Deployment Method

#### Option A: Docker (Recommended)

```bash
# Validate configuration
python scripts/validate_config.py

# Deploy with Docker
python scripts/deploy.py deploy

# Or use the batch script on Windows
scripts\deploy.bat deploy
```

#### Option B: Local Development

```bash
# Install dependencies with uv
uv add -r requirements.txt

# Validate configuration
python scripts/validate_config.py

# Run directly
python main.py
```

### 3. Access the Application

- **Web Interface**: http://localhost:5000
- **LiveKit Room**: Configured in your .env file
- **Logs**: Check `logs/` directory or `docker compose logs`

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure the following sections:

#### LiveKit Configuration (Required)

```env
LIVEKIT_URL=wss://your-livekit-server.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_ROOM_NAME=anime_room
```

**Getting LiveKit Credentials:**
1. Sign up at [LiveKit Cloud](https://cloud.livekit.io/)
2. Create a new project
3. Copy the URL, API Key, and API Secret

#### AI Provider Configuration

**Option 1: Ollama (Local)**
```env
USE_OLLAMA=true
OLLAMA_MODEL=llama3
OLLAMA_HOST=http://localhost:11434
```

**Option 2: Google Gemini (Cloud)**
```env
USE_OLLAMA=false
GEMINI_API_KEYS=your_key_1,your_key_2,your_key_3
GEMINI_CURRENT_KEY_INDEX=0
```

#### Memory Configuration (Optional)

```env
MEM0_API_KEY=your_mem0_api_key
MEM0_COLLECTION=anime_character
MEMORY_HISTORY_LIMIT=20
```

#### Personality Configuration

```env
PERSONALITY_PROMPT=You are a tsundere anime girl named Miko. You're tough on the outside but caring inside. Always respond with anime flair, like 'B-baka!' for embarrassment, and end with cute emotes like (*blush*). Stay in character no matter what.
```

### Configuration Validation

Always validate your configuration before deployment:

```bash
# Validate configuration
python scripts/validate_config.py

# Or use the deployment script
python scripts/deploy.py validate
```

## Deployment Methods

### Docker Deployment (Production)

#### Full Deployment

```bash
# Complete deployment with validation, build, and start
python scripts/deploy.py deploy

# With specific profiles (e.g., include Ollama service)
python scripts/deploy.py deploy --profile ollama

# Force rebuild without cache
python scripts/deploy.py deploy --no-cache
```

#### Individual Commands

```bash
# Build images only
python scripts/deploy.py build

# Start services
python scripts/deploy.py start

# Stop services
python scripts/deploy.py stop

# Restart services
python scripts/deploy.py restart

# View status
python scripts/deploy.py status

# View logs
python scripts/deploy.py logs

# Follow logs for specific service
python scripts/deploy.py logs anime-ai-character -f

# Cleanup (remove containers, images, volumes)
python scripts/deploy.py cleanup --volumes
```

#### Windows Batch Scripts

```cmd
REM Full deployment
scripts\deploy.bat deploy

REM Individual commands
scripts\deploy.bat validate
scripts\deploy.bat build
scripts\deploy.bat start
scripts\deploy.bat stop
scripts\deploy.bat status
scripts\deploy.bat logs
```

### Local Development

#### Using uv (Recommended)

```bash
# Install uv if not already installed
pip install uv

# Install dependencies
uv add -r requirements.txt

# Run the application
python main.py
```

#### Using pip

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Production Deployment

#### Docker Compose Production

```bash
# Use production configuration
export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml

# Deploy with production settings
docker compose up -d

# Or use the deployment script
python scripts/deploy.py deploy --profile production
```

#### Environment-Specific Configurations

Create environment-specific files:

- `.env.development` - Development settings
- `.env.staging` - Staging environment
- `.env.production` - Production settings

Load specific environment:

```bash
# Copy appropriate environment file
cp .env.production .env

# Deploy
python scripts/deploy.py deploy
```

## Monitoring and Maintenance

### Health Checks

The application includes built-in health checks:

```bash
# Check application health
curl http://localhost:5000/health

# Docker health status
docker compose ps
```

### Logs

#### Application Logs

```bash
# View all logs
docker compose logs

# Follow logs
docker compose logs -f

# Specific service logs
docker compose logs anime-ai-character

# Local development logs
tail -f logs/application.log
```

#### Log Levels

Configure logging in `.env`:

```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
DEBUG=false     # Enable debug mode
```

### Performance Monitoring

#### Resource Usage

```bash
# Docker resource usage
docker stats

# System resource usage
docker compose top
```

#### Memory Management

Monitor memory usage, especially for:
- AI model loading (Ollama)
- Conversation history (Mem0)
- Live2D model assets

### Backup and Recovery

#### Configuration Backup

```bash
# Backup configuration
cp .env .env.backup.$(date +%Y%m%d)

# Backup entire configuration directory
tar -czf config-backup-$(date +%Y%m%d).tar.gz .env static/models/
```

#### Data Backup

```bash
# Backup Docker volumes
docker compose down
docker run --rm -v project-miko_redis_data:/data -v $(pwd):/backup alpine tar czf /backup/redis-backup.tar.gz /data
docker compose up -d
```

### Updates and Maintenance

#### Application Updates

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
python scripts/deploy.py deploy --no-cache

# Or step by step
python scripts/deploy.py stop
python scripts/deploy.py build --no-cache
python scripts/deploy.py start
```

#### Dependency Updates

```bash
# Update Python dependencies
uv add --upgrade -r requirements.txt

# Rebuild Docker images
python scripts/deploy.py build --no-cache
```

## Troubleshooting

### Common Issues

#### Configuration Errors

**Problem**: `Configuration Error: Required environment variable LIVEKIT_URL is not set`

**Solution**:
```bash
# Check .env file exists
ls -la .env

# Validate configuration
python scripts/validate_config.py

# Copy from example if missing
cp .env.example .env
```

#### Docker Issues

**Problem**: `Docker is not installed or not accessible`

**Solution**:
```bash
# Install Docker Desktop or Docker Engine
# Verify installation
docker --version
docker compose version

# Start Docker service (Linux)
sudo systemctl start docker
```

**Problem**: `Port 5000 already in use`

**Solution**:
```bash
# Find process using port
lsof -i :5000  # Linux/Mac
netstat -ano | findstr :5000  # Windows

# Change port in .env
FLASK_PORT=5001

# Or stop conflicting service
docker compose down
```

#### AI Provider Issues

**Problem**: Ollama connection failed

**Solution**:
```bash
# Check Ollama is running
curl http://localhost:11434/api/version

# Start Ollama service
ollama serve

# Or use Docker Ollama
docker compose --profile ollama up -d
```

**Problem**: Gemini API key errors

**Solution**:
```bash
# Verify API keys in .env
echo $GEMINI_API_KEYS

# Test key rotation
python -c "
from src.config.settings import load_config
config = load_config()
print(f'Keys: {len(config.ai.gemini_api_keys)}')
print(f'Current: {config.ai.gemini_current_key_index}')
"
```

#### Memory Issues

**Problem**: Mem0 connection failed

**Solution**:
```bash
# Check Mem0 API key
echo $MEM0_API_KEY

# Test without Mem0 (session-only memory)
# Remove or comment out MEM0_API_KEY in .env
```

#### Live2D Issues

**Problem**: Live2D model not loading

**Solution**:
```bash
# Check model files exist
ls -la static/models/

# Verify model URL in .env
echo $LIVE2D_MODEL_URL

# Check file permissions
chmod 644 static/models/*
```

### Debug Mode

Enable debug mode for detailed logging:

```env
DEBUG=true
LOG_LEVEL=DEBUG
```

### Getting Help

1. **Check Logs**: Always check application and Docker logs first
2. **Validate Configuration**: Run `python scripts/validate_config.py`
3. **Test Components**: Test individual components (AI, LiveKit, etc.)
4. **Community**: Check GitHub issues and discussions

### Performance Optimization

#### Resource Limits

Configure Docker resource limits:

```yaml
# docker-compose.override.yml
services:
  anime-ai-character:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

#### Caching

Enable caching for better performance:

```env
# Redis caching (included in docker-compose.yml)
REDIS_URL=redis://redis:6379

# Model caching
OLLAMA_KEEP_ALIVE=24h
```

## Security Considerations

### API Key Security

- Never commit `.env` files to version control
- Use environment-specific configurations
- Rotate API keys regularly
- Use Docker secrets in production

### Network Security

```yaml
# docker-compose.prod.yml
services:
  anime-ai-character:
    networks:
      - internal
    ports:
      - "127.0.0.1:5000:5000"  # Bind to localhost only

networks:
  internal:
    driver: bridge
    internal: true
```

### Content Filtering

Configure appropriate content filtering:

```env
ENABLE_CONTENT_FILTER=true
CONTENT_FILTER_STRICT_MODE=true  # For production
```

This deployment guide should help you get the Anime AI Character system running in any environment. For additional help, check the project documentation and GitHub issues.