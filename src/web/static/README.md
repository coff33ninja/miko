# Live2D Static Assets

This directory contains static assets for the Live2D anime character:

## Directory Structure

```
static/
├── models/          # Live2D model files (.moc3, .model3.json)
├── textures/        # Texture files (.png)
├── motions/         # Motion files (.motion3.json)
├── expressions/     # Expression files (.exp3.json)
├── physics/         # Physics files (.physics3.json)
└── sounds/          # Audio files for character voices
```

## Supported File Types

- **Models**: `.moc3`, `.model3.json`
- **Textures**: `.png`, `.jpg`
- **Motions**: `.motion3.json`
- **Expressions**: `.exp3.json`
- **Physics**: `.physics3.json`
- **Audio**: `.wav`, `.mp3`, `.ogg`

## Usage

Place your Live2D model files in the appropriate directories. The Flask server will serve these files at `/static/<filename>`.
A nice link to look at https://booth.pm/en/search/live2D?max_price=0
Example model configuration in environment variables:
```
LIVE2D_MODEL_URL=/static/models/character.model3.json
```

## Sample Model Structure

For a complete Live2D character, you typically need:

1. **character.model3.json** - Main model configuration file
2. **character.moc3** - Compiled model file
3. **textures/texture_00.png** - Character texture
4. **motions/idle.motion3.json** - Idle animation
5. **expressions/happy.exp3.json** - Facial expressions
6. **physics/character.physics3.json** - Physics simulation

## Notes

- Ensure all file paths in the model3.json file are relative to the static directory
- The web interface will automatically load the model specified in LIVE2D_MODEL_URL
- For best performance, optimize texture sizes and use compressed formats when possible