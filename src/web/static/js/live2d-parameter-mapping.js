/**
 * Live2D Parameter Mapping System
 * 
 * This module provides comprehensive parameter mapping for Live2D models,
 * including expression definitions, parameter validation, and animation
 * parameter calculations based on sentiment and context.
 */

class Live2DParameterMapping {
    constructor() {
        // Standard Live2D parameter definitions
        this.standardParameters = {
            // Head movement
            'ParamAngleX': { min: -30, max: 30, default: 0 },
            'ParamAngleY': { min: -30, max: 30, default: 0 },
            'ParamAngleZ': { min: -30, max: 30, default: 0 },
            
            // Eyes
            'ParamEyeLOpen': { min: 0, max: 1, default: 1 },
            'ParamEyeROpen': { min: 0, max: 1, default: 1 },
            'ParamEyeBallX': { min: -1, max: 1, default: 0 },
            'ParamEyeBallY': { min: -1, max: 1, default: 0 },
            
            // Eyebrows
            'ParamBrowLY': { min: -1, max: 1, default: 0 },
            'ParamBrowRY': { min: -1, max: 1, default: 0 },
            
            // Mouth
            'ParamMouthForm': { min: -1, max: 1, default: 0 },
            'ParamMouthOpenY': { min: 0, max: 1, default: 0 },
            
            // Body
            'ParamBodyAngleX': { min: -10, max: 10, default: 0 },
            'ParamBodyAngleY': { min: -10, max: 10, default: 0 },
            'ParamBodyAngleZ': { min: -10, max: 10, default: 0 },
            
            // Breathing
            'ParamBreath': { min: 0, max: 1, default: 0 },
            
            // Custom parameters (model-specific)
            'Param12': { min: 0, max: 1, default: 0 } // From expression file
        };
        
        // Expression parameter sets
        this.expressions = {
            'neutral': {
                'ParamMouthForm': 0.0,
                'ParamEyeLOpen': 1.0,
                'ParamEyeROpen': 1.0,
                'ParamBrowLY': 0.0,
                'ParamBrowRY': 0.0,
                'ParamMouthOpenY': 0.0,
                'ParamEyeBallX': 0.0,
                'ParamEyeBallY': 0.0
            },
            
            'happy': {
                'ParamMouthForm': 0.8,
                'ParamEyeLOpen': 0.6,
                'ParamEyeROpen': 0.6,
                'ParamBrowLY': 0.3,
                'ParamBrowRY': 0.3,
                'ParamMouthOpenY': 0.2,
                'ParamEyeBallY': -0.1
            },
            
            'sad': {
                'ParamMouthForm': -0.6,
                'ParamEyeLOpen': 0.8,
                'ParamEyeROpen': 0.8,
                'ParamBrowLY': -0.5,
                'ParamBrowRY': -0.5,
                'ParamMouthOpenY': 0.0,
                'ParamEyeBallY': 0.2,
                'ParamAngleZ': -2.0
            },
            
            'angry': {
                'ParamMouthForm': -0.4,
                'ParamEyeLOpen': 0.4,
                'ParamEyeROpen': 0.4,
                'ParamBrowLY': -0.8,
                'ParamBrowRY': -0.8,
                'ParamMouthOpenY': 0.1,
                'ParamEyeBallX': 0.0,
                'ParamEyeBallY': -0.2
            },
            
            'surprised': {
                'ParamMouthForm': 0.0,
                'ParamEyeLOpen': 1.2,
                'ParamEyeROpen': 1.2,
                'ParamBrowLY': 0.6,
                'ParamBrowRY': 0.6,
                'ParamMouthOpenY': 0.8,
                'ParamEyeBallY': -0.3
            },
            
            'speak': {
                'ParamMouthOpenY': 0.6,
                'ParamMouthForm': 0.2,
                'ParamEyeLOpen': 1.0,
                'ParamEyeROpen': 1.0
            },
            
            'blink': {
                'ParamEyeLOpen': 0.0,
                'ParamEyeROpen': 0.0
            },
            
            'wink_left': {
                'ParamEyeLOpen': 0.0,
                'ParamEyeROpen': 1.0,
                'ParamMouthForm': 0.3
            },
            
            'wink_right': {
                'ParamEyeLOpen': 1.0,
                'ParamEyeROpen': 0.0,
                'ParamMouthForm': 0.3
            }
        };
        
        // Animation curves for smooth transitions
        this.easingFunctions = {
            'linear': (t) => t,
            'easeInOut': (t) => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t,
            'easeOut': (t) => t * (2 - t),
            'easeIn': (t) => t * t,
            'bounce': (t) => {
                if (t < 1/2.75) {
                    return 7.5625 * t * t;
                } else if (t < 2/2.75) {
                    return 7.5625 * (t -= 1.5/2.75) * t + 0.75;
                } else if (t < 2.5/2.75) {
                    return 7.5625 * (t -= 2.25/2.75) * t + 0.9375;
                } else {
                    return 7.5625 * (t -= 2.625/2.75) * t + 0.984375;
                }
            }
        };
        
        // Sentiment to expression intensity mapping
        this.sentimentIntensityMap = {
            'happy': { base: 0.7, variance: 0.3 },
            'sad': { base: 0.6, variance: 0.2 },
            'angry': { base: 0.8, variance: 0.2 },
            'surprised': { base: 0.9, variance: 0.1 },
            'neutral': { base: 0.5, variance: 0.1 },
            'speak': { base: 0.6, variance: 0.2 }
        };
    }
    
    /**
     * Get expression parameters with intensity scaling
     */
    getExpressionParameters(expression, intensity = 0.7) {
        const baseParams = this.expressions[expression];
        if (!baseParams) {
            console.warn(`Unknown expression: ${expression}`);
            return this.expressions['neutral'];
        }
        
        const scaledParams = {};
        
        Object.keys(baseParams).forEach(paramId => {
            const baseValue = baseParams[paramId];
            const paramDef = this.standardParameters[paramId];
            
            if (paramDef) {
                // Scale the parameter value by intensity
                let scaledValue = baseValue * intensity;
                
                // Clamp to parameter bounds
                scaledValue = Math.max(paramDef.min, Math.min(paramDef.max, scaledValue));
                
                scaledParams[paramId] = scaledValue;
            } else {
                // Unknown parameter, use as-is but scaled
                scaledParams[paramId] = baseValue * intensity;
            }
        });
        
        return scaledParams;
    }
    
    /**
     * Validate parameter value against bounds
     */
    validateParameter(paramId, value) {
        const paramDef = this.standardParameters[paramId];
        if (!paramDef) {
            console.warn(`Unknown parameter: ${paramId}`);
            return value;
        }
        
        return Math.max(paramDef.min, Math.min(paramDef.max, value));
    }
    
    /**
     * Get default parameter values
     */
    getDefaultParameters() {
        const defaults = {};
        
        Object.keys(this.standardParameters).forEach(paramId => {
            defaults[paramId] = this.standardParameters[paramId].default;
        });
        
        return defaults;
    }
    
    /**
     * Calculate mouth sync parameters based on audio data
     */
    calculateMouthSyncParameters(audioData, time) {
        if (!audioData || audioData.length === 0) {
            return {
                'ParamMouthOpenY': 0.0,
                'ParamMouthForm': 0.0
            };
        }
        
        // Calculate average volume
        let sum = 0;
        for (let i = 0; i < audioData.length; i++) {
            sum += audioData[i];
        }
        const average = sum / audioData.length;
        
        // Normalize to 0-1 range
        const normalizedVolume = Math.min(average / 128.0, 1.0);
        
        // Add some variation for more natural movement
        const variation = Math.sin(time * 0.01) * 0.1;
        const mouthOpen = normalizedVolume * 0.8 + variation;
        
        // Calculate mouth form based on frequency content
        const highFreqSum = audioData.slice(audioData.length * 0.7).reduce((a, b) => a + b, 0);
        const highFreqAvg = highFreqSum / (audioData.length * 0.3);
        const mouthForm = (highFreqAvg / 128.0) * 0.3;
        
        return {
            'ParamMouthOpenY': this.validateParameter('ParamMouthOpenY', mouthOpen),
            'ParamMouthForm': this.validateParameter('ParamMouthForm', mouthForm)
        };
    }
    
    /**
     * Generate breathing animation parameters
     */
    generateBreathingParameters(time, intensity = 0.5) {
        const breathCycle = Math.sin(time * 0.002) * intensity;
        const bodyMovement = Math.sin(time * 0.0015) * intensity * 0.3;
        
        return {
            'ParamBreath': this.validateParameter('ParamBreath', (breathCycle + 1) * 0.5),
            'ParamBodyAngleY': this.validateParameter('ParamBodyAngleY', bodyMovement),
            'ParamAngleZ': this.validateParameter('ParamAngleZ', bodyMovement * 0.5)
        };
    }
    
    /**
     * Generate idle animation parameters
     */
    generateIdleParameters(time) {
        const blinkCycle = Math.sin(time * 0.003);
        const eyeMovement = Math.sin(time * 0.001) * 0.1;
        const headMovement = Math.sin(time * 0.0008) * 2.0;
        
        return {
            'ParamEyeLOpen': blinkCycle < -0.95 ? 0.0 : 1.0, // Occasional blinks
            'ParamEyeROpen': blinkCycle < -0.95 ? 0.0 : 1.0,
            'ParamEyeBallX': this.validateParameter('ParamEyeBallX', eyeMovement),
            'ParamEyeBallY': this.validateParameter('ParamEyeBallY', eyeMovement * 0.5),
            'ParamAngleX': this.validateParameter('ParamAngleX', headMovement),
            'ParamAngleY': this.validateParameter('ParamAngleY', headMovement * 0.7)
        };
    }
    
    /**
     * Interpolate between two parameter sets
     */
    interpolateParameters(fromParams, toParams, progress, easingType = 'easeInOut') {
        const easingFunc = this.easingFunctions[easingType] || this.easingFunctions['linear'];
        const t = easingFunc(Math.max(0, Math.min(1, progress)));
        
        const interpolated = {};
        
        // Get all unique parameter IDs
        const allParams = new Set([...Object.keys(fromParams), ...Object.keys(toParams)]);
        
        allParams.forEach(paramId => {
            const fromValue = fromParams[paramId] || 0;
            const toValue = toParams[paramId] || 0;
            
            interpolated[paramId] = fromValue + (toValue - fromValue) * t;
        });
        
        return interpolated;
    }
    
    /**
     * Create animation keyframes for complex expressions
     */
    createAnimationKeyframes(expression, duration = 2000, intensity = 0.7) {
        const targetParams = this.getExpressionParameters(expression, intensity);
        const neutralParams = this.getExpressionParameters('neutral', 0.5);
        
        const keyframes = [];
        const frameCount = Math.ceil(duration / 16.67); // 60 FPS
        
        // Ease in phase (0-25%)
        for (let i = 0; i <= frameCount * 0.25; i++) {
            const progress = (i / (frameCount * 0.25));
            const params = this.interpolateParameters(neutralParams, targetParams, progress, 'easeOut');
            keyframes.push({
                time: (i / frameCount) * duration,
                parameters: params
            });
        }
        
        // Hold phase (25-75%)
        for (let i = Math.ceil(frameCount * 0.25); i <= frameCount * 0.75; i++) {
            keyframes.push({
                time: (i / frameCount) * duration,
                parameters: { ...targetParams }
            });
        }
        
        // Ease out phase (75-100%)
        for (let i = Math.ceil(frameCount * 0.75); i <= frameCount; i++) {
            const progress = ((i - frameCount * 0.75) / (frameCount * 0.25));
            const params = this.interpolateParameters(targetParams, neutralParams, progress, 'easeIn');
            keyframes.push({
                time: (i / frameCount) * duration,
                parameters: params
            });
        }
        
        return keyframes;
    }
    
    /**
     * Get sentiment-based parameter adjustments
     */
    getSentimentAdjustments(sentiment, confidence, textLength = 0) {
        const intensityMap = this.sentimentIntensityMap[sentiment] || this.sentimentIntensityMap['neutral'];
        
        // Base intensity from sentiment
        let intensity = intensityMap.base;
        
        // Adjust based on confidence
        intensity *= confidence;
        
        // Adjust based on text length (longer text = more emphasis)
        const lengthFactor = Math.min(textLength / 100, 1.5);
        intensity *= (0.8 + lengthFactor * 0.4);
        
        // Add some variance for natural feel
        const variance = (Math.random() - 0.5) * intensityMap.variance;
        intensity += variance;
        
        // Clamp to valid range
        intensity = Math.max(0.1, Math.min(1.0, intensity));
        
        return {
            intensity,
            duration: 1500 + (textLength * 10), // Longer text = longer animation
            easingType: sentiment === 'surprised' ? 'bounce' : 'easeInOut'
        };
    }
    
    /**
     * Create custom expression from parameters
     */
    createCustomExpression(name, parameters) {
        // Validate all parameters
        const validatedParams = {};
        
        Object.keys(parameters).forEach(paramId => {
            validatedParams[paramId] = this.validateParameter(paramId, parameters[paramId]);
        });
        
        this.expressions[name] = validatedParams;
        
        return validatedParams;
    }
    
    /**
     * Get available expressions
     */
    getAvailableExpressions() {
        return Object.keys(this.expressions);
    }
    
    /**
     * Get parameter information
     */
    getParameterInfo(paramId) {
        return this.standardParameters[paramId] || null;
    }
    
    /**
     * Export expression data for saving
     */
    exportExpression(expression) {
        const params = this.expressions[expression];
        if (!params) {
            return null;
        }
        
        return {
            name: expression,
            parameters: { ...params },
            timestamp: new Date().toISOString()
        };
    }
    
    /**
     * Import expression data
     */
    importExpression(expressionData) {
        if (!expressionData.name || !expressionData.parameters) {
            throw new Error('Invalid expression data format');
        }
        
        this.expressions[expressionData.name] = { ...expressionData.parameters };
        
        return true;
    }
}

// Export for use in other modules
window.Live2DParameterMapping = Live2DParameterMapping;