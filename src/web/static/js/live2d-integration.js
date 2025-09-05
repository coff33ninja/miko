/**
 * Live2D Animation Integration System
 * 
 * This module provides comprehensive Live2D model loading, rendering,
 * and animation control for the anime AI character system.
 */

const loadScript = async (src) => {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
};

class Live2DIntegration {
    constructor(canvasId, modelUrl) {
        this.canvas = document.getElementById(canvasId);
        this.modelUrl = modelUrl;
        this.gl = null;
        this.app = null; // Pixi.js Application
        this.live2dModel = null; // Live2D model instance
        this.framework = null;
        this.parameterMapping = new Live2DParameterMapping(); // Instantiate parameter mapping
        
        // Animation state
        this.currentExpression = 'neutral';
        this.isAnimating = false;
        this.animationQueue = [];
        
        // Mouth sync state
        this.isSpeaking = false;
        this.audioContext = null;
        this.analyser = null;
        this.mouthSyncInterval = null;
        
        // Parameter smoothing for natural animations
        this.parameterTargets = {};
        this.parameterCurrent = {};
        this.smoothingFactor = 0.1;
        
        this.initialize();
    }
    
    async initialize() {
        try {
            console.log('Initializing Live2D integration...');

            // Dynamically load scripts in order
            await loadScript('/static/js/pixi.min.js');
            await loadScript('/static/js/live2dcubismcore.min.js');
            await loadScript('/static/js/live2dcubismframework.js');
            await loadScript('/static/js/live2dcubismpixi.js');
            
            // Initialize Live2D framework
            await this.initializeLive2DFramework();
            
            // Load the model
            if (this.modelUrl) {
                await this.loadModel(this.modelUrl);
            }
            
            // Start render loop
            this.startRenderLoop();
            
            console.log('Live2D integration initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize Live2D:', error);
            throw error;
        }
    }
    
    async initializeLive2DFramework() {
        console.log('Initializing Live2D Cubism framework with Pixi.js...');

        // Initialize Pixi.js Application
        this.app = new PIXI.Application({
            view: this.canvas,
            width: this.canvas.width,
            height: this.canvas.height,
            autoDensity: true,
            backgroundAlpha: 0, // Make canvas background transparent
        });

        // Load Live2D Cubism Core
        await PIXI.live2d.Live2DBuilder.setupLive2D();

        // Initialize parameter tracking
        this.initializeParameters();
    }
    
    initializeParameters() {
        // Initialize common Live2D parameters with default values from parameter mapping
        const defaultParams = this.parameterMapping.getDefaultParameters();
        
        Object.keys(defaultParams).forEach(param => {
            this.parameterCurrent[param] = defaultParams[param];
            this.parameterTargets[param] = defaultParams[param];
        });
    }
    
    async loadModel(modelUrl) {
        try {
            console.log(`Loading Live2D model: ${modelUrl}`);

            // Load the Live2D model using Pixi-Live2D-Display
            this.live2dModel = await PIXI.live2d.Live2DModel.from(modelUrl);
            this.app.stage.addChild(this.live2dModel);

            // Scale and position the model to fit the canvas
            this.live2dModel.scale.set(0.2); // Adjust scale as needed
            this.live2dModel.x = this.canvas.width / 2;
            this.live2dModel.y = this.canvas.height / 2;
            this.live2dModel.anchor.set(0.5, 0.5); // Center the model

            console.log('Live2D model loaded successfully', this.live2dModel);

            // Optional: Load expressions if they are part of the model
            // This might need adjustment based on how expressions are defined in your model3.json
            if (this.live2dModel.expressions) {
                console.log('Expressions found:', this.live2dModel.expressions);
                // You might want to map these to your expressionMap or handle them differently
            }

        } catch (error) {
            console.error('Failed to load Live2D model:', error);
            throw error;
        }
    }
    
    async loadExpressions() {
        if (!this.model?.config?.FileReferences?.Expressions) {
            return;
        }
        
        console.log('Loading expressions...');
        
        for (const expr of this.model.config.FileReferences.Expressions) {
            try {
                const response = await fetch(`/static/expressions/${expr.File}`);
                if (response.ok) {
                    const expressionData = await response.json();
                    console.log(`Loaded expression: ${expr.Name}`, expressionData);
                }
            } catch (error) {
                console.warn(`Failed to load expression ${expr.Name}:`, error);
            }
        }
    }
    
    startRenderLoop() {
        // Use Pixi.js ticker for updates
        this.app.ticker.add(() => {
            this.update();
        });
    }
    
    update() {
        // Update parameter smoothing
        this.updateParameterSmoothing();
        
        // Update breathing animation
        this.updateBreathing();
        
        // Process animation queue
        this.processAnimationQueue();
        
        // Update mouth sync if speaking
        if (this.isSpeaking) {
            this.updateMouthSync();
        }
    }
    
    updateParameterSmoothing() {
        if (!this.live2dModel) return;

        Object.keys(this.parameterTargets).forEach(param => {
            const target = this.parameterTargets[param];
            const current = this.live2dModel.parameters.byName(param)?.value || 0.0;
            
            // Smooth interpolation towards target
            if (this.live2dModel.parameters.ids.includes(param)) {
                this.live2dModel.parameters.byName(param).value = current + (target - current) * this.smoothingFactor;
            }
        });
    }
    
    updateBreathing() {
        if (!this.live2dModel) return;

        // Add subtle breathing animation
        const time = Date.now() * 0.001;
        const breathValue = Math.sin(time * 2.0) * 0.1;
        
        if (this.live2dModel.parameters.ids.includes('ParamBreath')) {
            this.live2dModel.parameters.byName('ParamBreath').value = breathValue;
        }
    }
    
    processAnimationQueue() {
        if (this.animationQueue.length > 0 && !this.isAnimating) {
            const nextAnimation = this.animationQueue.shift();
            this.executeAnimation(nextAnimation);
        }
    }
    
    draw() {
        if (!this.live2dModel) {
            // If model not loaded, still clear canvas or draw placeholder
            this.drawPlaceholder();
            return;
        }

        // Apply parameters to Live2D model
        Object.keys(this.parameterCurrent).forEach(param => {
            if (this.live2dModel.parameters.ids.includes(param)) {
                this.live2dModel.parameters.values[this.live2dModel.parameters.ids.indexOf(param)] = this.parameterCurrent[param];
            }
        });

        // Update and render the Pixi.js application
        this.app.render();
    }
    
    getExpressionColor(expression) {
        const colors = {
            'happy': '#FFD700',
            'sad': '#87CEEB',
            'angry': '#FF6B6B',
            'surprised': '#FFA500',
            'neutral': '#DDD',
            'speak': '#90EE90'
        };
        return colors[expression] || '#DDD';
    }
    
    // Public API methods
    
    /**
     * Trigger an animation based on expression and intensity
     */
    async triggerAnimation(expression, intensity = 0.7, duration = 2.0) {
        console.log(`Triggering animation: ${expression} (${intensity}, ${duration}s)`);
        
        try {
            // Try to send animation request to server first
            const response = await fetch('/animate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    expression: expression,
                    intensity: intensity,
                    duration: duration,
                    priority: 'normal'
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('Server animation response:', result);
                
                // If server animation succeeded, also update local state
                if (result.success) {
                    this.executeAnimation({
                        expression,
                        intensity,
                        duration: duration * 1000,
                        startTime: Date.now()
                    });
                    return true;
                }
            } else {
                console.warn('Server animation failed, using local animation');
            }
        } catch (error) {
            console.warn('Failed to connect to server, using local animation:', error);
        }
        
        // Fallback to local animation
        const animation = {
            expression,
            intensity,
            duration: duration * 1000, // Convert to milliseconds
            startTime: Date.now()
        };
        
        this.animationQueue.push(animation);
        
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve(true);
            }, duration * 1000);
        });
    }
    
    executeAnimation(animation) {
        if (!this.live2dModel) return; // Ensure model is loaded

        this.isAnimating = true;
        this.currentExpression = animation.expression;

        // Find and set the expression on the Live2D model
        const expressionName = animation.expression;
        if (this.live2dModel.expressions && this.live2dModel.expressions.includes(expressionName)) {
            this.live2dModel.setExpression(expressionName);
        } else {
            console.warn(`Expression '${expressionName}' not found in Live2D model. Falling back to parameter mapping.`);
            // Fallback to manual parameter mapping if expression not found in model
            const expressionData = this.parameterMapping.getExpressionParameters(animation.expression, animation.intensity);
            if (expressionData) {
                Object.keys(expressionData).forEach(param => {
                    this.parameterTargets[param] = expressionData[param];
                });
            }
        }

        // Reset to neutral after duration
        setTimeout(() => {
            this.resetToNeutral();
            this.isAnimating = false;
        }, animation.duration);
    }
    
    resetToNeutral() {
        if (this.live2dModel && this.live2dModel.expressions && this.live2dModel.expressions.includes('neutral')) {
            this.live2dModel.setExpression('neutral');
        } else {
            // Fallback to manual parameter reset if 'neutral' expression not found in model
            const neutralData = this.parameterMapping.getExpressionParameters('neutral');
            Object.keys(neutralData).forEach(param => {
                this.parameterTargets[param] = neutralData[param];
            });
        }
        this.currentExpression = 'neutral';
    }
    
    /**
     * Start mouth synchronization with audio
     */
    startMouthSync(audioElement) {
        try {
            if (!this.audioContext) {
                // Use proper AudioContext constructor with fallback
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                if (AudioContextClass) {
                    this.audioContext = new AudioContextClass();
                } else {
                    throw new Error('AudioContext not supported');
                }
            }
            
            // Create audio analyser
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            
            // Connect audio source
            const source = this.audioContext.createMediaElementSource(audioElement);
            source.connect(this.analyser);
            this.analyser.connect(this.audioContext.destination);
            
            this.isSpeaking = true;
            
            console.log('Mouth sync started');
            
        } catch (error) {
            console.error('Failed to start mouth sync:', error);
        }
    }
    
    /**
     * Stop mouth synchronization
     */
    stopMouthSync() {
        this.isSpeaking = false;
        
        // Reset mouth parameters
        this.parameterTargets['ParamMouthOpenY'] = 0.0;
        this.parameterTargets['ParamMouthForm'] = 0.0;
        
        console.log('Mouth sync stopped');
    }
    
    updateMouthSync() {
        if (!this.analyser || !this.live2dModel) return;
        
        // Get audio frequency data
        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteFrequencyData(dataArray);
        
        // Calculate average volume
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
        }
        const average = sum / dataArray.length;
        
        // Map volume to mouth opening (0-255 -> 0-1)
        const mouthOpen = Math.min(average / 128.0, 1.0);
        
        // Apply mouth movement with some smoothing
        this.live2dModel.parameters.byName('ParamMouthOpenY').value = mouthOpen * 0.8;
        
        // Add slight mouth form variation for more natural movement
        const time = Date.now() * 0.01;
        this.live2dModel.parameters.byName('ParamMouthForm').value = Math.sin(time) * 0.2 * mouthOpen;
    }
    
    drawPlaceholder() {
        if (!this.app) return;

        // Clear the canvas
        this.app.renderer.clear();

        // Optionally, draw a simple message or shape
        const graphics = new PIXI.Graphics();
        graphics.beginFill(0xAAAAAA);
        graphics.drawRect(0, 0, this.canvas.width, this.canvas.height);
        graphics.endFill();

        const style = new PIXI.TextStyle({
            fill: 0xFFFFFF,
            fontSize: 24,
            align: 'center'
        });
        const message = new PIXI.Text('Live2D Model Not Loaded', style);
        message.anchor.set(0.5);
        message.x = this.canvas.width / 2;
        message.y = this.canvas.height / 2;

        this.app.stage.addChild(graphics);
        this.app.stage.addChild(message);
        this.app.render();

        // Remove them after rendering to keep the stage clean for when the model loads
        this.app.stage.removeChild(graphics);
        this.app.stage.removeChild(message);
    }
    
    /**
     * Map AI sentiment to animation expression
     */
    mapSentimentToExpression(sentiment, confidence = 0.7) {
        const sentimentMap = {
            'positive': 'happy',
            'negative': 'sad',
            'anger': 'angry',
            'surprise': 'surprised',
            'neutral': 'neutral',
            'joy': 'happy',
            'sadness': 'sad',
            'fear': 'surprised',
            'disgust': 'angry'
        };
        
        const expression = sentimentMap[sentiment.toLowerCase()] || 'neutral';
        
        // Trigger animation with confidence as intensity
        this.triggerAnimation(expression, confidence, 2.0);
        
        return expression;
    }
    
    /**
     * Get current animation state
     */
    getAnimationState() {
        return {
            currentExpression: this.currentExpression,
            isAnimating: this.isAnimating,
            isSpeaking: this.isSpeaking,
            queueLength: this.animationQueue.length,
            parameters: { ...this.parameterCurrent }
        };
    }
    
    /**
     * Set parameter value directly
     */
    setParameter(paramId, value, smooth = true) {
        if (!this.live2dModel || !this.live2dModel.parameters.ids.includes(paramId)) return;

        if (smooth) {
            this.parameterTargets[paramId] = value;
        } else {
            this.live2dModel.parameters.byName(paramId).value = value;
            this.parameterTargets[paramId] = value;
        }
    }
    
    /**
     * Get parameter value
     */
    getParameter(paramId) {
        return this.live2dModel?.parameters.byName(paramId)?.value || 0.0;
    }
}

// Export for use in other modules
window.Live2DIntegration = Live2DIntegration;