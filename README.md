# Anime AI Character

A real-time interactive anime-style AI character using Live2D visuals, LiveKit for voice/video streaming, and persistent memory with Mem0.

## Features

- 🎭 **Live2D Animation**: Expressive 2D anime character with real-time animations
- 🗣️ **Voice Interaction**: Real-time voice chat using LiveKit's STT/TTS
- 🧠 **Persistent Memory**: Cross-session memory using Mem0 for contextual conversations
- 🤖 **Flexible AI**: Support for both local (Ollama) and cloud (Gemini) AI providers
- 🔄 **API Key Rotation**: Automatic Gemini API key rotation for rate limit handling
- 🛡️ **Content Filtering**: Provider-specific content policies
- ⚙️ **Configuration-Driven**: Fully configurable via environment variables

## Project Structure

```
anime-ai-character/
├── src/
│   ├── config/           # Configuration management
│   ├── ai/              # AI provider abstractions
│   ├── memory/          # Memory management (Mem0)
│   ├── web/             # Flask web server & Live2D
│   └── agent/           # LiveKit agent
├── static/
│   └── models/          # Live2D model files (.moc3, textures)
├── tests/               # Unit and integration tests
├── logs/                # Application logs
├── .env                 # Environment configuration (create from .env.example)
├── .env.example         # Example configuration
├── requirements.txt     # Python dependencies
└── main.py             # Application entry point
```

## Quick Start

### Option 1: Docker Deployment (Recommended)

```bash
# Clone the repository
git clone https://github.com/coff33ninja/miko.git
cd miko

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys and settings

# Validate configuration
python scripts/validate_config.py

# Deploy with Docker
python scripts/deploy.py deploy
# Or on Windows: scripts\deploy.bat deploy

# Access at http://localhost:5000
```

### Option 2: Local Development

```bash
# Clone and setup
git clone https://github.com/coff33ninja/miko.git
cd miko

# Install dependencies with uv (recommended)
pip install uv
uv add -r requirements.txt

# Or use pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and settings

# Validate configuration
python scripts/validate_config.py

# Run the application
python main.py
```

## Deployment

### Docker Deployment

The project includes comprehensive Docker support for easy deployment:

```bash
# Full deployment (validate + build + start)
python scripts/deploy.py deploy

# Individual commands
python scripts/deploy.py validate    # Validate configuration
python scripts/deploy.py build      # Build Docker images
python scripts/deploy.py start      # Start services
python scripts/deploy.py stop       # Stop services
python scripts/deploy.py status     # Show service status
python scripts/deploy.py logs       # View logs
python scripts/deploy.py cleanup    # Clean up resources
```

#### Windows Users

Use the batch script for easier deployment:

```cmd
scripts\deploy.bat deploy     # Full deployment
scripts\deploy.bat validate   # Validate only
scripts\deploy.bat start      # Start services
scripts\deploy.bat stop       # Stop services
scripts\deploy.bat status     # Show status
```

### Configuration Validation

Always validate your configuration before deployment:

```bash
python scripts/validate_config.py
```

This checks:

- Python version compatibility
- Required files and directories
- Environment variable configuration
- AI provider settings
- LiveKit credentials
- Network connectivity

### Production Deployment

For production deployment, see the comprehensive [DEPLOYMENT.md](DEPLOYMENT.md) guide which covers:

- Environment-specific configurations
- Security considerations
- Monitoring and maintenance
- Performance optimization
- Troubleshooting

## Configuration

Copy the example configuration and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your API keys and settings:

```env
# Required: LiveKit credentials
LIVEKIT_URL=wss://your-livekit-server.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_secret

# Choose AI provider
USE_OLLAMA=true  # or false for Gemini

# For Ollama (local)
OLLAMA_MODEL=llama3

# For Gemini (cloud) - supports multiple keys for rotation
GEMINI_API_KEYS=key1,key2,key3

# Optional: Memory persistence
MEM0_API_KEY=your_mem0_key

# Customize personality
PERSONALITY_PROMPT=You are a tsundere anime girl named Miko...
```

## Configuration Options

### AI Providers

**Ollama (Local)**

- Runs locally, no API costs
- No content restrictions
- Requires Ollama installation and model download

**Gemini (Cloud)**

- Cloud-based, API costs apply
- Built-in content filtering
- Supports multiple API keys with automatic rotation

### Content Filtering

- **Ollama**: Unrestricted content processing
- **Gemini**: Automatic content filtering with character-appropriate rejection messages

### Memory System

- **With Mem0**: Persistent memory across sessions with intelligent context retrieval
- **Without Mem0**: Session-only memory (conversations reset on restart)

### Live2D Models

To use a Live2D model, place its entire folder (containing the `model3.json` and associated assets like `.moc3`, textures, etc.) into the `static/models/` directory.

For example, if your model folder is `miara_pro_en`, place it at `static/models/miara_pro_en/`.

Once your model is in place, use the setup script to configure its path in your `.env` file:

```bash
python scripts/setup_live2d_model.py <your_model_folder_name>
```

Replace `<your_model_folder_name>` with the name of your model's directory (e.g., `miara_pro_en`). This script will automatically find the primary `model3.json` file within your model's folder and set the `LIVE2D_MODEL_CONFIG_PATH` environment variable in your `.env` file.

Free models available from:

- [Live2D Official Samples](https://www.live2d.com/en/download/sample-data/)
- [Booth.pm](https://booth.pm/) (search "Live2D free")

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/ tests/
flake8 src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Logging

The system provides structured logging for:

- **Application logs**: `logs/application.log`
- **Content filtering incidents**: `logs/content_filter.log`
- **System events**: `logs/system_events.log` (API key rotation, errors, etc.)

## API Key Rotation

When using Gemini with multiple API keys:

1. Configure multiple keys: `GEMINI_API_KEYS=key1,key2,key3`
2. System automatically rotates when rate limits are hit
3. Rotation events are logged for monitoring
4. Manual rotation available via configuration API

## Troubleshooting

### Common Issues

1. **Missing LiveKit credentials**: Check your `.env` file has valid LiveKit settings
2. **Ollama connection failed**: Ensure Ollama is running and model is downloaded
3. **Gemini rate limits**: Add more API keys to `GEMINI_API_KEYS` for rotation
4. **Live2D model not found**: Check model files are in `static/models/`

### Debug Mode

Enable debug logging:

```env
DEBUG=true
LOG_LEVEL=DEBUG
```

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]