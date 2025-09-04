/**
 * Live2D Animation Integration System
 * 
 * This module provides comprehensive Live2D model loading, rendering,
 * and animation control for the anime AI character system.
 */

class Live2DIntegration {
    constructor(canvasId, modelUrl) {
        this.canvas = document.getElementById(canvasId);
        this.modelUrl = modelUrl;
        this.gl = null;
        this.model = null;
        this.framework = null;
        
        // Animation state
        this.currentExpression = 'neutral';
        this.isAnimating = false;
        this.animationQueue = [];
        
        // Mouth sync state
        this.isSpeaking = false;
        this.audioContext = null;
        this.analyser = null;
        this.mouthSyncInterval = null;
        
        // Expression mapping for sentiment analysis
        this.expressionMap = {
            'happy': { params: { 'ParamMouthForm': 1.0, 'ParamEyeLOpen': 1.0, 'ParamEyeROpen': 1.0 }, intensity: 0.8 },
            'sad': { params: { 'ParamMouthForm': -0.8, 'ParamEyeLOpen': 0.3, 'ParamEyeROpen': 0.3 }, intensity: 0.7 },
            'angry': { params: { 'ParamMouthForm': -0.5, 'ParamBrowLY': -0.8, 'ParamBrowRY': -0.8 }, intensity: 0.9 },
            'surprised': { params: { 'ParamMouthOpenY': 0.8, 'ParamEyeLOpen': 1.2, 'ParamEyeROpen': 1.2 }, intensity: 0.8 },
            'neutral': { params: { 'ParamMouthForm': 0.0, 'ParamEyeLOpen': 1.0, 'ParamEyeROpen': 1.0 }, intensity: 0.5 },
            'speak': { params: { 'ParamMouthOpenY': 0.6, 'ParamMouthForm': 0.3 }, intensity: 0.7 }
        };
        
        // Parameter smoothing for natural animations
        this.parameterTargets = {};
        this.parameterCurrent = {};
        this.smoothingFactor = 0.1;
        
        this.initialize();
    }
    
    async initialize() {
        try {
            console.log('Initializing Live2D integration...');
            
            // Initialize WebGL context
            this.gl = this.canvas.getContext('webgl') || this.canvas.getContext('experimental-webgl');
            if (!this.gl) {
                throw new Error('WebGL not supported');
            }
            
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
        // Initialize Live2D Cubism framework
        // This is a simplified initialization - in a real implementation,
        // you would use the actual Live2D Cubism SDK
        
        console.log('Initializing Live2D Cubism framework...');
        
        // Set up WebGL viewport
        this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
        this.gl.clearColor(0.0, 0.0, 0.0, 0.0);
        this.gl.enable(this.gl.BLEND);
        this.gl.blendFunc(this.gl.SRC_ALPHA, this.gl.ONE_MINUS_SRC_ALPHA);
        
        // Initialize parameter tracking
        this.initializeParameters();
    }
    
    initializeParameters() {
        // Initialize common Live2D parameters with default values
        const defaultParams = {
            'ParamAngleX': 0.0,
            'ParamAngleY': 0.0,
            'ParamAngleZ': 0.0,
            'ParamEyeLOpen': 1.0,
            'ParamEyeROpen': 1.0,
            'ParamEyeBallX': 0.0,
            'ParamEyeBallY': 0.0,
            'ParamBrowLY': 0.0,
            'ParamBrowRY': 0.0,
            'ParamMouthForm': 0.0,
            'ParamMouthOpenY': 0.0,
            'ParamBodyAngleX': 0.0,
            'ParamBodyAngleY': 0.0,
            'ParamBodyAngleZ': 0.0,
            'ParamBreath': 0.0
        };
        
        Object.keys(defaultParams).forEach(param => {
            this.parameterCurrent[param] = defaultParams[param];
            this.parameterTargets[param] = defaultParams[param];
        });
    }
    
    async loadModel(modelUrl) {
        try {
            console.log(`Loading Live2D model: ${modelUrl}`);
            
            // Fetch model configuration
            const response = await fetch(modelUrl);
            if (!response.ok) {
                throw new Error(`Failed to load model: ${response.status}`);
            }
            
            const modelConfig = await response.json();
            console.log('Model configuration loaded:', modelConfig);
            
            // In a real implementation, you would load the actual .moc3 file
            // and initialize the Live2D model here
            this.model = {
                config: modelConfig,
                loaded: true,
                expressions: modelConfig.FileReferences?.Expressions || []
            };
            
            // Load expressions
            await this.loadExpressions();
            
            console.log('Live2D model loaded successfully');
            
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
        const render = () => {
            this.update();
            this.draw();
            requestAnimationFrame(render);
        };
        
        requestAnimationFrame(render);
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
        Object.keys(this.parameterTargets).forEach(param => {
            const target = this.parameterTargets[param];
            const current = this.parameterCurrent[param];
            
            // Smooth interpolation towards target
            this.parameterCurrent[param] = current + (target - current) * this.smoothingFactor;
        });
    }
    
    updateBreathing() {
        // Add subtle breathing animation
        const time = Date.now() * 0.001;
        const breathValue = Math.sin(time * 2.0) * 0.1;
        this.parameterCurrent['ParamBreath'] = breathValue;
    }
    
    processAnimationQueue() {
        if (this.animationQueue.length > 0 && !this.isAnimating) {
            const nextAnimation = this.animationQueue.shift();
            this.executeAnimation(nextAnimation);
        }
    }
    
    draw() {
        // Clear canvas
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);
        
        // In a real implementation, this would render the Live2D model
        // For now, we'll draw a simple representation
        this.drawPlaceholder();
    }
    
    drawPlaceholder() {
        // Simple visual representation for testing
        const ctx = this.canvas.getContext('2d');
        if (!ctx) return;
        
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw character representation
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        
        // Head
        ctx.fillStyle = this.getExpressionColor(this.currentExpression);
        ctx.beginPath();
        ctx.arc(centerX, centerY - 50, 80, 0, Math.PI * 2);
        ctx.fill();
        
        // Eyes
        const eyeOpenness = this.parameterCurrent['ParamEyeLOpen'] || 1.0;
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.arc(centerX - 25, centerY - 70, 8 * eyeOpenness, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(centerX + 25, centerY - 70, 8 * eyeOpenness, 0, Math.PI * 2);
        ctx.fill();
        
        // Mouth
        const mouthOpen = this.parameterCurrent['ParamMouthOpenY'] || 0.0;
        const mouthForm = this.parameterCurrent['ParamMouthForm'] || 0.0;
        
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 3;
        ctx.beginPath();
        
        if (mouthOpen > 0.3) {
            // Open mouth (speaking)
            ctx.arc(centerX, centerY - 20, 10 + mouthOpen * 10, 0, Math.PI);
        } else {
            // Closed mouth with expression
            const mouthY = centerY - 20;
            const curve = mouthForm * 20;
            ctx.moveTo(centerX - 15, mouthY);
            ctx.quadraticCurveTo(centerX, mouthY + curve, centerX + 15, mouthY);
        }
        ctx.stroke();
        
        // Display current expression
        ctx.fillStyle = '#fff';
        ctx.font = '16px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(`Expression: ${this.currentExpression}`, centerX, this.canvas.height - 20);
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
        this.isAnimating = true;
        this.currentExpression = animation.expression;
        
        // Get expression parameters
        const expressionData = this.expressionMap[animation.expression];
        if (!expressionData) {
            console.warn(`Unknown expression: ${animation.expression}`);
            this.isAnimating = false;
            return;
        }
        
        // Set target parameters with intensity scaling
        Object.keys(expressionData.params).forEach(param => {
            const targetValue = expressionData.params[param] * animation.intensity;
            this.parameterTargets[param] = targetValue;
        });
        
        // Reset to neutral after duration
        setTimeout(() => {
            this.resetToNeutral();
            this.isAnimating = false;
        }, animation.duration);
    }
    
    resetToNeutral() {
        const neutralData = this.expressionMap['neutral'];
        Object.keys(neutralData.params).forEach(param => {
            this.parameterTargets[param] = neutralData.params[param];
        });
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
        if (!this.analyser) return;
        
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
        this.parameterTargets['ParamMouthOpenY'] = mouthOpen * 0.8;
        
        // Add slight mouth form variation for more natural movement
        const time = Date.now() * 0.01;
        this.parameterTargets['ParamMouthForm'] = Math.sin(time) * 0.2 * mouthOpen;
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
        if (smooth) {
            this.parameterTargets[paramId] = value;
        } else {
            this.parameterCurrent[paramId] = value;
            this.parameterTargets[paramId] = value;
        }
    }
    
    /**
     * Get parameter value
     */
    getParameter(paramId) {
        return this.parameterCurrent[paramId] || 0.0;
    }
}

// Export for use in other modules
window.Live2DIntegration = Live2DIntegration;