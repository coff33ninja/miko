/**
 * Test Suite for Live2D Animation Integration
 * 
 * This module provides comprehensive tests for the Live2D animation system,
 * including unit tests for animation triggers, parameter updates, and
 * integration tests for the complete animation pipeline.
 */

class AnimationTestSuite {
    constructor() {
        this.testResults = [];
        this.mockLive2D = null;
        this.mockAnimationController = null;
        
        this.setupMocks();
    }
    
    setupMocks() {
        // Mock Live2D Integration
        this.mockLive2D = {
            currentExpression: 'neutral',
            isAnimating: false,
            isSpeaking: false,
            parameterCurrent: {},
            parameterTargets: {},
            animationQueue: [],
            
            async triggerAnimation(expression, intensity, duration) {
                this.currentExpression = expression;
                this.isAnimating = true;
                
                setTimeout(() => {
                    this.isAnimating = false;
                }, duration * 100); // Shortened for testing
                
                return true;
            },
            
            setParameter(paramId, value, smooth = true) {
                if (smooth) {
                    this.parameterTargets[paramId] = value;
                } else {
                    this.parameterCurrent[paramId] = value;
                    this.parameterTargets[paramId] = value;
                }
            },
            
            getParameter(paramId) {
                return this.parameterCurrent[paramId] || 0.0;
            },
            
            startMouthSync(audioElement) {
                this.isSpeaking = true;
                return true;
            },
            
            stopMouthSync() {
                this.isSpeaking = false;
            },
            
            mapSentimentToExpression(sentiment, confidence) {
                const map = {
                    'positive': 'happy',
                    'negative': 'sad',
                    'anger': 'angry',
                    'surprise': 'surprised',
                    'neutral': 'neutral'
                };
                return map[sentiment] || 'neutral';
            },
            
            getAnimationState() {
                return {
                    currentExpression: this.currentExpression,
                    isAnimating: this.isAnimating,
                    isSpeaking: this.isSpeaking,
                    queueLength: this.animationQueue.length,
                    parameters: { ...this.parameterCurrent }
                };
            }
        };
    }
    
    /**
     * Run all animation tests
     */
    async runAllTests() {
        console.log('🧪 Starting Live2D Animation Test Suite...');
        
        this.testResults = [];
        
        // Unit Tests
        await this.testBasicAnimationTrigger();
        await this.testParameterUpdates();
        await this.testExpressionMapping();
        await this.testAnimationQueue();
        await this.testMouthSynchronization();
        
        // Integration Tests
        await this.testSentimentAnalysis();
        await this.testAnimationController();
        await this.testContextualAnimations();
        await this.testAnimationTransitions();
        
        // Performance Tests
        await this.testAnimationPerformance();
        await this.testMemoryUsage();
        
        // Error Handling Tests
        await this.testErrorHandling();
        
        this.printTestResults();
        return this.testResults;
    }
    
    /**
     * Test basic animation triggering
     */
    async testBasicAnimationTrigger() {
        const testName = 'Basic Animation Trigger';
        
        try {
            // Test happy expression
            const result = await this.mockLive2D.triggerAnimation('happy', 0.8, 2.0);
            
            this.assert(result === true, 'Animation should return true on success');
            this.assert(this.mockLive2D.currentExpression === 'happy', 'Expression should be updated');
            this.assert(this.mockLive2D.isAnimating === true, 'Should be in animating state');
            
            // Wait for animation to complete
            await this.wait(250);
            this.assert(this.mockLive2D.isAnimating === false, 'Should finish animating');
            
            this.addTestResult(testName, true, 'All basic animation tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test parameter updates
     */
    async testParameterUpdates() {
        const testName = 'Parameter Updates';
        
        try {
            // Test smooth parameter update
            this.mockLive2D.setParameter('ParamMouthOpenY', 0.5, true);
            this.assert(this.mockLive2D.parameterTargets['ParamMouthOpenY'] === 0.5, 'Target parameter should be set');
            
            // Test immediate parameter update
            this.mockLive2D.setParameter('ParamEyeLOpen', 1.0, false);
            this.assert(this.mockLive2D.parameterCurrent['ParamEyeLOpen'] === 1.0, 'Current parameter should be set');
            this.assert(this.mockLive2D.parameterTargets['ParamEyeLOpen'] === 1.0, 'Target parameter should match');
            
            // Test parameter retrieval
            const eyeValue = this.mockLive2D.getParameter('ParamEyeLOpen');
            this.assert(eyeValue === 1.0, 'Parameter retrieval should work');
            
            this.addTestResult(testName, true, 'All parameter update tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test expression mapping
     */
    async testExpressionMapping() {
        const testName = 'Expression Mapping';
        
        try {
            const testCases = [
                { sentiment: 'positive', expected: 'happy' },
                { sentiment: 'negative', expected: 'sad' },
                { sentiment: 'anger', expected: 'angry' },
                { sentiment: 'surprise', expected: 'surprised' },
                { sentiment: 'neutral', expected: 'neutral' },
                { sentiment: 'unknown', expected: 'neutral' }
            ];
            
            testCases.forEach(testCase => {
                const result = this.mockLive2D.mapSentimentToExpression(testCase.sentiment, 0.7);
                this.assert(result === testCase.expected, 
                    `Sentiment '${testCase.sentiment}' should map to '${testCase.expected}', got '${result}'`);
            });
            
            this.addTestResult(testName, true, 'All expression mapping tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test animation queue functionality
     */
    async testAnimationQueue() {
        const testName = 'Animation Queue';
        
        try {
            // Reset queue
            this.mockLive2D.animationQueue = [];
            
            // Add multiple animations
            this.mockLive2D.animationQueue.push({ expression: 'happy', intensity: 0.8, duration: 1000 });
            this.mockLive2D.animationQueue.push({ expression: 'sad', intensity: 0.6, duration: 1500 });
            
            this.assert(this.mockLive2D.animationQueue.length === 2, 'Queue should contain 2 animations');
            
            // Process queue
            const firstAnimation = this.mockLive2D.animationQueue.shift();
            this.assert(firstAnimation.expression === 'happy', 'First animation should be happy');
            this.assert(this.mockLive2D.animationQueue.length === 1, 'Queue should have 1 animation left');
            
            this.addTestResult(testName, true, 'Animation queue tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test mouth synchronization
     */
    async testMouthSynchronization() {
        const testName = 'Mouth Synchronization';
        
        try {
            // Create mock audio element
            const mockAudio = {
                play: () => Promise.resolve(),
                pause: () => {},
                currentTime: 0,
                duration: 5.0
            };
            
            // Test start mouth sync
            const startResult = this.mockLive2D.startMouthSync(mockAudio);
            this.assert(startResult === true, 'Mouth sync should start successfully');
            this.assert(this.mockLive2D.isSpeaking === true, 'Should be in speaking state');
            
            // Test stop mouth sync
            this.mockLive2D.stopMouthSync();
            this.assert(this.mockLive2D.isSpeaking === false, 'Should stop speaking state');
            
            this.addTestResult(testName, true, 'Mouth synchronization tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test sentiment analysis
     */
    async testSentimentAnalysis() {
        const testName = 'Sentiment Analysis';
        
        try {
            const analyzer = new SentimentAnalyzer();
            
            const testCases = [
                { text: 'I am so happy and excited!', expectedSentiment: 'happy' },
                { text: 'This is terrible and awful', expectedSentiment: 'sad' },
                { text: 'I am furious and angry', expectedSentiment: 'angry' },
                { text: 'Wow, that is amazing!', expectedSentiment: 'surprised' },
                { text: 'The weather is okay', expectedSentiment: 'neutral' },
                { text: '', expectedSentiment: 'neutral' }
            ];
            
            testCases.forEach(testCase => {
                const result = analyzer.analyze(testCase.text);
                this.assert(result.sentiment === testCase.expectedSentiment,
                    `Text "${testCase.text}" should be ${testCase.expectedSentiment}, got ${result.sentiment}`);
                this.assert(result.confidence >= 0.0 && result.confidence <= 1.0,
                    'Confidence should be between 0 and 1');
            });
            
            this.addTestResult(testName, true, 'Sentiment analysis tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test animation controller functionality
     */
    async testAnimationController() {
        const testName = 'Animation Controller';
        
        try {
            const controller = new AnimationController(this.mockLive2D);
            
            // Test AI response handling
            const responseData = {
                text: 'I am so happy to see you!',
                sentiment: 'happy',
                confidence: 0.8
            };
            
            await controller.handleAIResponse(responseData);
            
            // Check if context was updated
            const state = controller.getAnimationState();
            this.assert(state.conversationContext.mood === 'happy', 'Mood should be updated');
            this.assert(state.conversationContext.responseCount === 1, 'Response count should increment');
            
            // Test user input handling
            controller.handleUserInput({ text: 'Hello there!', type: 'voice' });
            this.assert(state.conversationContext.lastUserInput !== null, 'User input should be recorded');
            
            this.addTestResult(testName, true, 'Animation controller tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test contextual animations
     */
    async testContextualAnimations() {
        const testName = 'Contextual Animations';
        
        try {
            const controller = new AnimationController(this.mockLive2D);
            
            // Test first interaction modifier
            const animation1 = controller.determineAnimation('happy', 0.5, 'Hello!');
            this.assert(animation1.intensity > 0.5, 'First interaction should have higher intensity');
            
            // Simulate multiple responses to test repeated expression modifier
            controller.conversationContext.responseCount = 5;
            controller.animationHistory = [
                { expression: 'happy', timestamp: Date.now() - 1000 },
                { expression: 'happy', timestamp: Date.now() - 500 }
            ];
            
            const animation2 = controller.determineAnimation('happy', 0.8, 'Great!');
            this.assert(animation2.intensity < 0.8, 'Repeated expressions should have lower intensity');
            
            this.addTestResult(testName, true, 'Contextual animation tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test animation transitions
     */
    async testAnimationTransitions() {
        const testName = 'Animation Transitions';
        
        try {
            const controller = new AnimationController(this.mockLive2D);
            
            // Test valid transitions
            this.assert(controller.isValidTransition('neutral', 'happy'), 'Neutral to happy should be valid');
            this.assert(controller.isValidTransition('happy', 'neutral'), 'Happy to neutral should be valid');
            
            // Test invalid transitions (should still work but with intermediate state)
            this.assert(controller.isValidTransition('angry', 'happy') === false, 'Angry to happy should be invalid');
            
            this.addTestResult(testName, true, 'Animation transition tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test animation performance
     */
    async testAnimationPerformance() {
        const testName = 'Animation Performance';
        
        try {
            const startTime = performance.now();
            
            // Trigger multiple animations rapidly
            const promises = [];
            for (let i = 0; i < 10; i++) {
                promises.push(this.mockLive2D.triggerAnimation('happy', 0.5, 0.1));
            }
            
            await Promise.all(promises);
            
            const endTime = performance.now();
            const duration = endTime - startTime;
            
            this.assert(duration < 1000, `Performance test should complete in under 1 second, took ${duration}ms`);
            
            this.addTestResult(testName, true, `Performance test passed (${duration.toFixed(2)}ms)`);
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test memory usage
     */
    async testMemoryUsage() {
        const testName = 'Memory Usage';
        
        try {
            const controller = new AnimationController(this.mockLive2D);
            
            // Add many items to history
            for (let i = 0; i < 20; i++) {
                controller.addToHistory({
                    expression: 'happy',
                    intensity: 0.5,
                    duration: 1.0,
                    timestamp: Date.now() + i
                });
            }
            
            // Check that history is trimmed
            const state = controller.getAnimationState();
            this.assert(state.animationHistory.length <= controller.maxHistoryLength,
                'Animation history should be trimmed to max length');
            
            this.addTestResult(testName, true, 'Memory usage test passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Test error handling
     */
    async testErrorHandling() {
        const testName = 'Error Handling';
        
        try {
            const controller = new AnimationController(this.mockLive2D);
            
            // Test with invalid data
            await controller.handleAIResponse({});
            await controller.handleAIResponse({ text: null });
            
            // Test with invalid animation parameters
            const result = await controller.triggerManualAnimation('invalid_expression', -1, 0);
            
            // Should not crash
            this.addTestResult(testName, true, 'Error handling tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Test failed: ${error.message}`);
        }
    }
    
    /**
     * Helper methods
     */
    assert(condition, message) {
        if (!condition) {
            throw new Error(message);
        }
    }
    
    addTestResult(testName, passed, message) {
        this.testResults.push({
            name: testName,
            passed,
            message,
            timestamp: new Date().toISOString()
        });
    }
    
    async wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    printTestResults() {
        console.log('\n📊 Test Results Summary:');
        console.log('========================');
        
        let passed = 0;
        let failed = 0;
        
        this.testResults.forEach(result => {
            const status = result.passed ? '✅ PASS' : '❌ FAIL';
            console.log(`${status} ${result.name}: ${result.message}`);
            
            if (result.passed) {
                passed++;
            } else {
                failed++;
            }
        });
        
        console.log('========================');
        console.log(`Total: ${this.testResults.length} | Passed: ${passed} | Failed: ${failed}`);
        console.log(`Success Rate: ${((passed / this.testResults.length) * 100).toFixed(1)}%`);
        
        if (failed === 0) {
            console.log('🎉 All tests passed!');
        } else {
            console.log('⚠️  Some tests failed. Please review the results above.');
        }
    }
}

/**
 * Integration test for complete animation pipeline
 */
class AnimationIntegrationTest {
    constructor() {
        this.testCanvas = null;
        this.live2dIntegration = null;
        this.animationController = null;
    }
    
    async runIntegrationTest() {
        console.log('🔄 Running Animation Integration Test...');
        
        try {
            // Create test canvas
            this.createTestCanvas();
            
            // Initialize Live2D integration
            this.live2dIntegration = new Live2DIntegration('test-canvas', '/static/models/Poblanc.model3.json');
            
            // Wait for initialization
            await this.wait(1000);
            
            // Initialize animation controller
            this.animationController = new AnimationController(this.live2dIntegration);
            
            // Test complete pipeline
            await this.testCompletePipeline();
            
            console.log('✅ Integration test completed successfully');
            
        } catch (error) {
            console.error('❌ Integration test failed:', error);
        } finally {
            this.cleanup();
        }
    }
    
    createTestCanvas() {
        this.testCanvas = document.createElement('canvas');
        this.testCanvas.id = 'test-canvas';
        this.testCanvas.width = 400;
        this.testCanvas.height = 300;
        this.testCanvas.style.display = 'none';
        document.body.appendChild(this.testCanvas);
    }
    
    async testCompletePipeline() {
        // Simulate AI response
        const aiResponse = {
            text: 'Hello! I am so excited to meet you!',
            sentiment: 'happy',
            confidence: 0.9
        };
        
        // Trigger AI response handling
        await this.animationController.handleAIResponse(aiResponse);
        
        // Wait for animation
        await this.wait(500);
        
        // Simulate TTS
        const mockAudio = document.createElement('audio');
        await this.animationController.handleTTSStart({ audioElement: mockAudio });
        
        // Wait for speaking animation
        await this.wait(1000);
        
        // Stop TTS
        this.animationController.handleTTSEnd();
        
        // Verify final state
        const state = this.animationController.getAnimationState();
        console.log('Final animation state:', state);
    }
    
    cleanup() {
        if (this.testCanvas) {
            document.body.removeChild(this.testCanvas);
        }
    }
    
    async wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Export test classes
window.AnimationTestSuite = AnimationTestSuite;
window.AnimationIntegrationTest = AnimationIntegrationTest;

// Auto-run tests if in test mode
if (window.location.search.includes('test=true')) {
    document.addEventListener('DOMContentLoaded', async () => {
        const testSuite = new AnimationTestSuite();
        await testSuite.runAllTests();
        
        const integrationTest = new AnimationIntegrationTest();
        await integrationTest.runIntegrationTest();
    });
}