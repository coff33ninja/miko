# Live2D Animation Integration System

## Overview

The Live2D Animation Integration System provides comprehensive animation control for anime-style AI characters. It combines Live2D model rendering, sentiment-based animation triggers, mouth synchronization with TTS, and contextual animation management.

## Architecture

### Core Components

1. **Live2DIntegration** (`live2d-integration.js`)

   - Handles Live2D model loading and rendering
   - Manages animation parameters and transitions
   - Provides mouth synchronization with audio

2. **AnimationController** (`animation-controller.js`)

   - Coordinates AI responses with animations
   - Manages conversation context and animation history
   - Handles sentiment analysis and expression mapping

3. **Live2DParameterMapping** (`live2d-parameter-mapping.js`)

   - Defines expression parameter sets
   - Provides parameter validation and interpolation
   - Manages animation curves and transitions

4. **AnimationTestSuite** (`animation-tests.js`)
   - Comprehensive test suite for all animation components
   - Integration tests for complete animation pipeline
   - Performance and error handling tests

## Features

### Expression System

The system supports the following expressions:

- **Neutral**: Default resting state
- **Happy**: Positive emotions (smile, bright eyes)
- **Sad**: Negative emotions (downturned mouth, droopy eyes)
- **Angry**: Aggressive emotions (furrowed brow, tense expression)
- **Surprised**: Shock/amazement (wide eyes, open mouth)
- **Speaking**: Active conversation state with mouth movement

### Sentiment Analysis

Built-in sentiment analyzer that maps text to expressions:

```javascript
const analyzer = new SentimentAnalyzer();
const result = analyzer.analyze("I am so happy to see you!");
// Returns: { sentiment: 'happy', confidence: 0.8 }
```

### Mouth Synchronization

Real-time mouth movement synchronized with TTS audio:

```javascript
// Start mouth sync with audio element
live2dIntegration.startMouthSync(audioElement);

// Stop mouth sync
live2dIntegration.stopMouthSync();
```

### Context-Aware Animations

Animations adapt based on conversation context:

- First interaction intensity boost
- Repeated expression dampening
- Engagement level adjustments
- Animation history tracking

## Usage

### Basic Animation Trigger

```javascript
// Initialize the system
const live2d = new Live2DIntegration("canvas-id", "/static/models/model.json");
const controller = new AnimationController(live2d);

// Trigger an animation
await live2d.triggerAnimation("happy", 0.8, 2.0);
```

### AI Response Integration

```javascript
// Handle AI response with automatic animation
const responseData = {
  text: "Hello! I'm excited to meet you!",
  sentiment: "happy",
  confidence: 0.9,
};

await controller.handleAIResponse(responseData);
```

### Manual Parameter Control

```javascript
// Set specific Live2D parameters
live2d.setParameter("ParamMouthOpenY", 0.5, true); // Smooth transition
live2d.setParameter("ParamEyeLOpen", 0.0, false); // Immediate change
```

### Custom Expressions

```javascript
// Create custom expression
const parameterMapping = new Live2DParameterMapping();
parameterMapping.createCustomExpression("wink", {
  ParamEyeLOpen: 0.0,
  ParamEyeROpen: 1.0,
  ParamMouthForm: 0.3,
});
```

## API Reference

### Live2DIntegration Class

#### Constructor

```javascript
new Live2DIntegration(canvasId, modelUrl);
```

#### Methods

- `triggerAnimation(expression, intensity, duration)` - Trigger expression animation
- `startMouthSync(audioElement)` - Start mouth synchronization
- `stopMouthSync()` - Stop mouth synchronization
- `setParameter(paramId, value, smooth)` - Set Live2D parameter
- `getParameter(paramId)` - Get current parameter value
- `mapSentimentToExpression(sentiment, confidence)` - Map sentiment to expression

### AnimationController Class

#### Constructor

```javascript
new AnimationController(live2dIntegration);
```

#### Methods

- `handleAIResponse(responseData)` - Process AI response and trigger animation
- `handleUserInput(inputData)` - Process user input and update context
- `handleTTSStart(audioData)` - Handle TTS start event
- `handleTTSEnd()` - Handle TTS end event
- `triggerManualAnimation(expression, intensity, duration)` - Manual animation trigger
- `resetContext()` - Reset conversation context

### Live2DParameterMapping Class

#### Constructor

```javascript
new Live2DParameterMapping();
```

#### Methods

- `getExpressionParameters(expression, intensity)` - Get scaled expression parameters
- `validateParameter(paramId, value)` - Validate parameter bounds
- `calculateMouthSyncParameters(audioData, time)` - Calculate mouth sync parameters
- `interpolateParameters(fromParams, toParams, progress, easingType)` - Interpolate between parameter sets
- `createAnimationKeyframes(expression, duration, intensity)` - Create animation keyframes

## Configuration

### Expression Mapping

Expressions are defined in `Live2DParameterMapping`:

```javascript
this.expressions = {
  happy: {
    ParamMouthForm: 0.8,
    ParamEyeLOpen: 0.6,
    ParamEyeROpen: 0.6,
    ParamBrowLY: 0.3,
    ParamBrowRY: 0.3,
  },
  // ... other expressions
};
```

### Parameter Bounds

Live2D parameters have defined bounds:

```javascript
this.standardParameters = {
  ParamAngleX: { min: -30, max: 30, default: 0 },
  ParamEyeLOpen: { min: 0, max: 1, default: 1 },
  ParamMouthForm: { min: -1, max: 1, default: 0 },
  // ... other parameters
};
```

### Animation Settings

Customize animation behavior:

```javascript
// Animation timing
this.minAnimationInterval = 500; // Minimum time between animations (ms)

// Intensity modifiers
this.intensityModifiers = {
  first_interaction: 1.2,
  repeated_expression: 0.7,
  high_engagement: 1.1,
  low_engagement: 0.8,
};
```

## Events

The system uses custom events for communication:

### AI Response Event

```javascript
document.dispatchEvent(
  new CustomEvent("aiResponseReceived", {
    detail: { text, sentiment, confidence },
  })
);
```

### User Input Event

```javascript
document.dispatchEvent(
  new CustomEvent("userInputReceived", {
    detail: { text, type },
  })
);
```

### TTS Events

```javascript
// TTS started
document.dispatchEvent(
  new CustomEvent("ttsStarted", {
    detail: { audioElement },
  })
);

// TTS ended
document.dispatchEvent(new CustomEvent("ttsEnded"));
```

## Testing

### Running Tests

```javascript
// Run all animation tests
const testSuite = new AnimationTestSuite();
await testSuite.runAllTests();

// Run integration tests
const integrationTest = new AnimationIntegrationTest();
await integrationTest.runIntegrationTest();
```

### Test Categories

1. **Unit Tests**

   - Basic animation triggering
   - Parameter updates and validation
   - Expression mapping
   - Mouth synchronization

2. **Integration Tests**

   - Complete animation pipeline
   - AI response handling
   - Context-aware animations
   - Error handling

3. **Performance Tests**
   - Animation performance under load
   - Memory usage validation
   - Response time measurements

## Flask Integration

### Animation API Endpoint

```python
@app.route('/animate', methods=['POST'])
def animate():
    data = request.get_json()
    expression = data.get('expression', 'neutral')
    intensity = float(data.get('intensity', 0.5))
    duration = float(data.get('duration', 1.0))

    # Trigger animation and return response
    return jsonify({'success': True, 'animation': {...}})
```

### Async Animation Trigger

```python
async def trigger_animation(expression: str, intensity: float = 0.7, duration: float = 2.0) -> bool:
    """Trigger Live2D animation via HTTP API call."""
    # Make async HTTP request to Flask animation endpoint
    # Returns True if successful, False otherwise
```

## Live2D Model Requirements

### Model Structure

The system expects Live2D models with the following structure:

```
models/
├── ModelName.model3.json    # Model configuration
├── ModelName.moc3           # Model data
├── textures/
│   └── texture_00.png       # Model textures
├── expressions/
│   └── expression1.exp3.json # Expression definitions
└── physics/
    └── ModelName.physics3.json # Physics configuration
```

### Supported Parameters

Standard Live2D parameters supported:

- Head movement: `ParamAngleX`, `ParamAngleY`, `ParamAngleZ`
- Eyes: `ParamEyeLOpen`, `ParamEyeROpen`, `ParamEyeBallX`, `ParamEyeBallY`
- Eyebrows: `ParamBrowLY`, `ParamBrowRY`
- Mouth: `ParamMouthForm`, `ParamMouthOpenY`
- Body: `ParamBodyAngleX`, `ParamBodyAngleY`, `ParamBodyAngleZ`
- Breathing: `ParamBreath`

## Troubleshooting

### Common Issues

1. **WebGL Not Supported**

   - Ensure browser supports WebGL
   - Check hardware acceleration settings

2. **Model Loading Fails**

   - Verify model file paths
   - Check CORS settings for static files
   - Validate model JSON structure

3. **Animation Not Triggering**

   - Check console for JavaScript errors
   - Verify Flask animation endpoint is responding
   - Ensure Live2D integration is initialized

4. **Mouth Sync Not Working**
   - Check audio element is properly connected
   - Verify AudioContext is created successfully
   - Ensure audio has frequency data

### Debug Mode

Enable debug mode by adding `?debug=true` to the URL:

- Shows additional test controls
- Enables verbose logging
- Provides animation state information

## Performance Optimization

### Best Practices

1. **Animation Throttling**

   - Minimum interval between animations
   - Queue management for smooth transitions

2. **Parameter Smoothing**

   - Interpolation for natural movement
   - Configurable smoothing factors

3. **Memory Management**

   - Limited animation history
   - Automatic cleanup of old data

4. **Efficient Rendering**
   - 60 FPS render loop
   - Optimized parameter updates

## Future Enhancements

### Planned Features

1. **Advanced Expressions**

   - Emotion blending
   - Micro-expressions
   - Dynamic expression generation

2. **Enhanced Mouth Sync**

   - Phoneme-based lip sync
   - Multiple language support
   - Improved audio analysis

3. **Interactive Features**

   - Eye tracking
   - Mouse following
   - Touch interactions

4. **Performance Improvements**
   - WebGL optimization
   - Reduced memory footprint
   - Better mobile support

## License and Credits

This animation system is part of the Anime AI Character project and follows the same licensing terms. It integrates with the Live2D Cubism SDK and requires proper licensing for commercial use.
