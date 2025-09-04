/**
 * Animation Controller for Live2D Character
 * 
 * This module handles the coordination between AI responses, sentiment analysis,
 * and Live2D animations. It provides intelligent animation triggering based on
 * conversation context and emotional analysis.
 */

class AnimationController {
    constructor(live2dIntegration) {
        this.live2d = live2dIntegration;
        this.sentimentAnalyzer = new SentimentAnalyzer();
        
        // Animation timing and queue management
        this.lastAnimationTime = 0;
        this.minAnimationInterval = 500; // Minimum time between animations (ms)
        this.animationHistory = [];
        this.maxHistoryLength = 10;
        
        // Context-aware animation settings
        this.conversationContext = {
            mood: 'neutral',
            energy: 0.5,
            engagement: 0.5,
            lastUserInput: null,
            responseCount: 0
        };
        
        // Animation intensity modifiers
        this.intensityModifiers = {
            'first_interaction': 1.2,
            'repeated_expression': 0.7,
            'high_engagement': 1.1,
            'low_engagement': 0.8
        };
        
        // Expression transition rules
        this.transitionRules = {
            'happy': ['neutral', 'surprised', 'speak'],
            'sad': ['neutral', 'angry'],
            'angry': ['neutral', 'sad'],
            'surprised': ['happy', 'neutral'],
            'neutral': ['happy', 'sad', 'surprised', 'angry', 'speak'],
            'speak': ['neutral', 'happy']
        };
        
        // Initialize event listeners
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Listen for AI response events
        document.addEventListener('aiResponseReceived', (event) => {
            this.handleAIResponse(event.detail);
        });
        
        // Listen for user input events
        document.addEventListener('userInputReceived', (event) => {
            this.handleUserInput(event.detail);
        });
        
        // Listen for TTS events
        document.addEventListener('ttsStarted', (event) => {
            this.handleTTSStart(event.detail);
        });
        
        document.addEventListener('ttsEnded', () => {
            this.handleTTSEnd();
        });
    }
    
    /**
     * Handle AI response and trigger appropriate animation
     */
    async handleAIResponse(responseData) {
        try {
            const { text, sentiment, confidence } = responseData;
            
            // Analyze sentiment if not provided
            let analyzedSentiment = sentiment;
            let sentimentConfidence = confidence || 0.7;
            
            if (!analyzedSentiment) {
                const analysis = this.sentimentAnalyzer.analyze(text);
                analyzedSentiment = analysis.sentiment;
                sentimentConfidence = analysis.confidence;
            }
            
            // Update conversation context
            this.updateConversationContext(text, analyzedSentiment, sentimentConfidence);
            
            // Determine animation based on sentiment and context
            const animation = this.determineAnimation(analyzedSentiment, sentimentConfidence, text);
            
            // Trigger animation with context-aware intensity
            await this.triggerContextualAnimation(animation);
            
            console.log(`AI Response Animation: ${animation.expression} (${animation.intensity})`);
            
        } catch (error) {
            console.error('Error handling AI response:', error);
        }
    }
    
    /**
     * Handle user input and update context
     */
    handleUserInput(inputData) {
        const { text, type } = inputData; // type: 'voice' or 'text'
        
        this.conversationContext.lastUserInput = {
            text,
            type,
            timestamp: Date.now()
        };
        
        // Analyze user engagement
        const engagement = this.analyzeUserEngagement(text);
        this.conversationContext.engagement = engagement;
        
        // Trigger subtle acknowledgment animation for voice input
        if (type === 'voice') {
            this.triggerListeningAnimation();
        }
    }
    
    /**
     * Handle TTS start - begin mouth sync animation
     */
    async handleTTSStart(audioData) {
        try {
            // Start speaking animation
            await this.live2d.triggerAnimation('speak', 0.6, 0.5);
            
            // Start mouth synchronization if audio element is provided
            if (audioData.audioElement) {
                this.live2d.startMouthSync(audioData.audioElement);
            }
            
        } catch (error) {
            console.error('Error starting TTS animation:', error);
        }
    }
    
    /**
     * Handle TTS end - stop mouth sync
     */
    handleTTSEnd() {
        this.live2d.stopMouthSync();
        
        // Return to neutral expression after speaking
        setTimeout(() => {
            this.live2d.triggerAnimation('neutral', 0.5, 1.0);
        }, 500);
    }
    
    /**
     * Determine animation based on sentiment analysis and context
     */
    determineAnimation(sentiment, confidence, text) {
        // Base expression mapping
        const baseExpression = this.live2d.mapSentimentToExpression(sentiment, confidence);
        
        // Adjust intensity based on context
        let intensity = confidence;
        
        // Apply context modifiers
        if (this.conversationContext.responseCount === 0) {
            intensity *= this.intensityModifiers.first_interaction;
        }
        
        if (this.conversationContext.engagement > 0.7) {
            intensity *= this.intensityModifiers.high_engagement;
        } else if (this.conversationContext.engagement < 0.3) {
            intensity *= this.intensityModifiers.low_engagement;
        }
        
        // Check for repeated expressions
        const recentExpressions = this.animationHistory.slice(-3);
        const repeatedCount = recentExpressions.filter(h => h.expression === baseExpression).length;
        if (repeatedCount >= 2) {
            intensity *= this.intensityModifiers.repeated_expression;
        }
        
        // Clamp intensity
        intensity = Math.max(0.3, Math.min(1.0, intensity));
        
        // Determine duration based on text length and sentiment
        const baseDuration = 2.0;
        const textLengthFactor = Math.min(text.length / 100, 2.0);
        const duration = baseDuration + (textLengthFactor * 0.5);
        
        return {
            expression: baseExpression,
            intensity: intensity,
            duration: duration,
            sentiment: sentiment,
            confidence: confidence
        };
    }
    
    /**
     * Trigger animation with context awareness
     */
    async triggerContextualAnimation(animation) {
        const now = Date.now();
        
        // Check minimum interval
        if (now - this.lastAnimationTime < this.minAnimationInterval) {
            console.log('Animation throttled - too soon after last animation');
            return false;
        }
        
        // Check if transition is valid
        if (!this.isValidTransition(this.live2d.currentExpression, animation.expression)) {
            console.log(`Invalid transition from ${this.live2d.currentExpression} to ${animation.expression}`);
            // Use neutral as intermediate state
            await this.live2d.triggerAnimation('neutral', 0.5, 0.5);
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        
        // Trigger the animation
        const success = await this.live2d.triggerAnimation(
            animation.expression,
            animation.intensity,
            animation.duration
        );
        
        if (success) {
            // Update history
            this.addToHistory(animation);
            this.lastAnimationTime = now;
        }
        
        return success;
    }
    
    /**
     * Check if expression transition is valid
     */
    isValidTransition(fromExpression, toExpression) {
        if (!fromExpression || fromExpression === 'neutral') {
            return true; // Can transition from neutral to any expression
        }
        
        const allowedTransitions = this.transitionRules[fromExpression] || [];
        return allowedTransitions.includes(toExpression);
    }
    
    /**
     * Trigger subtle listening animation
     */
    async triggerListeningAnimation() {
        // Subtle eye movement to indicate listening
        this.live2d.setParameter('ParamEyeBallY', -0.2, true);
        
        setTimeout(() => {
            this.live2d.setParameter('ParamEyeBallY', 0.0, true);
        }, 1000);
    }
    
    /**
     * Update conversation context based on AI response
     */
    updateConversationContext(text, sentiment, confidence) {
        // Update mood based on sentiment
        this.conversationContext.mood = sentiment;
        
        // Update energy based on text characteristics
        const exclamationCount = (text.match(/!/g) || []).length;
        const questionCount = (text.match(/\?/g) || []).length;
        const capsRatio = (text.match(/[A-Z]/g) || []).length / text.length;
        
        this.conversationContext.energy = Math.min(1.0, 
            0.5 + (exclamationCount * 0.1) + (questionCount * 0.05) + (capsRatio * 0.3)
        );
        
        // Increment response count
        this.conversationContext.responseCount++;
    }
    
    /**
     * Analyze user engagement based on input
     */
    analyzeUserEngagement(text) {
        if (!text) return 0.5;
        
        let engagement = 0.5;
        
        // Length factor
        if (text.length > 50) engagement += 0.2;
        if (text.length > 100) engagement += 0.1;
        
        // Question factor
        if (text.includes('?')) engagement += 0.1;
        
        // Emotional indicators
        const emotionalWords = ['love', 'hate', 'amazing', 'terrible', 'excited', 'sad', 'happy'];
        const emotionalCount = emotionalWords.filter(word => 
            text.toLowerCase().includes(word)
        ).length;
        engagement += emotionalCount * 0.05;
        
        // Personal pronouns (indicates personal engagement)
        const personalPronouns = ['i', 'me', 'my', 'myself'];
        const pronounCount = personalPronouns.filter(pronoun =>
            text.toLowerCase().split(' ').includes(pronoun)
        ).length;
        engagement += pronounCount * 0.03;
        
        return Math.max(0.1, Math.min(1.0, engagement));
    }
    
    /**
     * Add animation to history
     */
    addToHistory(animation) {
        this.animationHistory.push({
            ...animation,
            timestamp: Date.now()
        });
        
        // Trim history to max length
        if (this.animationHistory.length > this.maxHistoryLength) {
            this.animationHistory.shift();
        }
    }
    
    /**
     * Get current animation state
     */
    getAnimationState() {
        return {
            currentExpression: this.live2d.currentExpression,
            isAnimating: this.live2d.isAnimating,
            conversationContext: { ...this.conversationContext },
            animationHistory: [...this.animationHistory],
            lastAnimationTime: this.lastAnimationTime
        };
    }
    
    /**
     * Reset conversation context
     */
    resetContext() {
        this.conversationContext = {
            mood: 'neutral',
            energy: 0.5,
            engagement: 0.5,
            lastUserInput: null,
            responseCount: 0
        };
        
        this.animationHistory = [];
        this.lastAnimationTime = 0;
        
        // Return to neutral expression
        this.live2d.triggerAnimation('neutral', 0.5, 1.0);
    }
    
    /**
     * Manual animation trigger with validation
     */
    async triggerManualAnimation(expression, intensity = 0.7, duration = 2.0) {
        const animation = {
            expression,
            intensity,
            duration,
            sentiment: expression,
            confidence: intensity
        };
        
        return await this.triggerContextualAnimation(animation);
    }
}

/**
 * Simple sentiment analyzer for client-side analysis
 */
class SentimentAnalyzer {
    constructor() {
        // Simple keyword-based sentiment analysis
        this.positiveWords = [
            'happy', 'joy', 'love', 'great', 'awesome', 'amazing', 'wonderful',
            'excellent', 'fantastic', 'good', 'nice', 'beautiful', 'perfect',
            'smile', 'laugh', 'excited', 'thrilled', 'delighted'
        ];
        
        this.negativeWords = [
            'sad', 'angry', 'hate', 'terrible', 'awful', 'horrible', 'bad',
            'worst', 'disgusting', 'annoying', 'frustrated', 'disappointed',
            'upset', 'mad', 'furious', 'depressed', 'miserable'
        ];
        
        this.surpriseWords = [
            'wow', 'amazing', 'incredible', 'unbelievable', 'shocking',
            'surprising', 'unexpected', 'astonishing', 'remarkable'
        ];
    }
    
    analyze(text) {
        if (!text) {
            return { sentiment: 'neutral', confidence: 0.5 };
        }
        
        const words = text.toLowerCase().split(/\W+/);
        
        let positiveScore = 0;
        let negativeScore = 0;
        let surpriseScore = 0;
        
        words.forEach(word => {
            if (this.positiveWords.includes(word)) positiveScore++;
            if (this.negativeWords.includes(word)) negativeScore++;
            if (this.surpriseWords.includes(word)) surpriseScore++;
        });
        
        // Determine dominant sentiment
        const maxScore = Math.max(positiveScore, negativeScore, surpriseScore);
        
        if (maxScore === 0) {
            return { sentiment: 'neutral', confidence: 0.5 };
        }
        
        let sentiment = 'neutral';
        if (positiveScore === maxScore) {
            sentiment = 'happy';
        } else if (negativeScore === maxScore) {
            sentiment = negativeScore > 2 ? 'angry' : 'sad';
        } else if (surpriseScore === maxScore) {
            sentiment = 'surprised';
        }
        
        // Calculate confidence based on score and text length
        const confidence = Math.min(0.9, 0.5 + (maxScore / words.length) * 2);
        
        return { sentiment, confidence };
    }
}

// Export for use in other modules
window.AnimationController = AnimationController;
window.SentimentAnalyzer = SentimentAnalyzer;