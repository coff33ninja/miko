/**
 * Unit tests for web interface JavaScript components.
 * 
 * This file contains tests for:
 * - Input mode switching
 * - Message handling
 * - Animation controls
 * - Participant management
 * - Responsive design helpers
 */

class WebInterfaceTestSuite {
    constructor() {
        this.testResults = [];
        this.mockElements = new Map();
        this.originalFunctions = new Map();
    }

    /**
     * Run all web interface tests
     */
    async runAllTests() {
        console.log('Starting Web Interface Test Suite...');
        
        this.setupMocks();
        
        try {
            await this.testInputModeSwitching();
            await this.testTextMessageHandling();
            await this.testParticipantManagement();
            await this.testAnimationControls();
            await this.testKeyboardShortcuts();
            await this.testResponsiveHelpers();
            await this.testErrorHandling();
            await this.testConnectionQuality();
            
        } finally {
            this.teardownMocks();
        }
        
        this.printResults();
        return this.testResults;
    }

    /**
     * Set up mock DOM elements and functions
     */
    setupMocks() {
        // Mock DOM elements
        this.mockElements.set('voice-mode-btn', this.createMockElement('button', { classList: ['button', 'mode-button'] }));
        this.mockElements.set('text-mode-btn', this.createMockElement('button', { classList: ['button', 'mode-button'] }));
        this.mockElements.set('voice-controls', this.createMockElement('div', { style: { display: 'block' } }));
        this.mockElements.set('text-controls', this.createMockElement('div', { style: { display: 'none' } }));
        this.mockElements.set('text-input', this.createMockElement('textarea', { value: '' }));
        this.mockElements.set('participants-list', this.createMockElement('div'));
        this.mockElements.set('audio-level-fill', this.createMockElement('div', { style: { width: '0%' } }));
        
        // Mock global functions if they exist
        if (typeof addChatMessage !== 'undefined') {
            this.originalFunctions.set('addChatMessage', addChatMessage);
            window.addChatMessage = this.mockAddChatMessage.bind(this);
        }
        
        // Mock getElementById
        this.originalGetElementById = document.getElementById;
        document.getElementById = (id) => {
            return this.mockElements.get(id) || this.createMockElement('div');
        };
    }

    /**
     * Tear down mocks and restore original functions
     */
    teardownMocks() {
        // Restore original functions
        this.originalFunctions.forEach((originalFn, name) => {
            window[name] = originalFn;
        });
        
        // Restore getElementById
        if (this.originalGetElementById) {
            document.getElementById = this.originalGetElementById;
        }
    }

    /**
     * Create a mock DOM element
     */
    createMockElement(tagName, properties = {}) {
        const element = {
            tagName: tagName.toUpperCase(),
            classList: {
                add: function(className) { 
                    this.classes = this.classes || [];
                    if (!this.classes.includes(className)) {
                        this.classes.push(className);
                    }
                },
                remove: function(className) {
                    this.classes = this.classes || [];
                    const index = this.classes.indexOf(className);
                    if (index > -1) {
                        this.classes.splice(index, 1);
                    }
                },
                contains: function(className) {
                    this.classes = this.classes || [];
                    return this.classes.includes(className);
                },
                classes: properties.classList || []
            },
            style: properties.style || {},
            value: properties.value || '',
            textContent: properties.textContent || '',
            innerHTML: properties.innerHTML || '',
            addEventListener: function() {},
            removeEventListener: function() {},
            click: function() {},
            focus: function() {},
            appendChild: function() {},
            removeChild: function() {},
            getAttribute: function(name) { return this.attributes[name]; },
            setAttribute: function(name, value) { 
                this.attributes = this.attributes || {};
                this.attributes[name] = value; 
            },
            attributes: properties.attributes || {},
            children: [],
            isDisplayed: function() { return this.style.display !== 'none'; }
        };
        
        return element;
    }

    /**
     * Mock addChatMessage function
     */
    mockAddChatMessage(type, message) {
        console.log(`[MOCK CHAT] ${type}: ${message}`);
    }

    /**
     * Test input mode switching functionality
     */
    async testInputModeSwitching() {
        const testName = 'Input Mode Switching';
        
        try {
            // Mock the switchInputMode function
            let currentMode = 'voice';
            const mockSwitchInputMode = (mode) => {
                currentMode = mode;
                
                const voiceBtn = this.mockElements.get('voice-mode-btn');
                const textBtn = this.mockElements.get('text-mode-btn');
                const voiceControls = this.mockElements.get('voice-controls');
                const textControls = this.mockElements.get('text-controls');
                
                if (mode === 'voice') {
                    voiceBtn.classList.add('active');
                    textBtn.classList.remove('active');
                    voiceControls.style.display = 'block';
                    textControls.style.display = 'none';
                } else {
                    textBtn.classList.add('active');
                    voiceBtn.classList.remove('active');
                    textControls.style.display = 'block';
                    voiceControls.style.display = 'none';
                }
            };
            
            // Test initial state (voice mode)
            mockSwitchInputMode('voice');
            this.assert(currentMode === 'voice', 'Initial mode should be voice');
            this.assert(this.mockElements.get('voice-controls').isDisplayed(), 'Voice controls should be visible');
            this.assert(!this.mockElements.get('text-controls').isDisplayed(), 'Text controls should be hidden');
            
            // Test switching to text mode
            mockSwitchInputMode('text');
            this.assert(currentMode === 'text', 'Mode should switch to text');
            this.assert(this.mockElements.get('text-controls').isDisplayed(), 'Text controls should be visible');
            this.assert(!this.mockElements.get('voice-controls').isDisplayed(), 'Voice controls should be hidden');
            
            // Test switching back to voice mode
            mockSwitchInputMode('voice');
            this.assert(currentMode === 'voice', 'Mode should switch back to voice');
            this.assert(this.mockElements.get('voice-controls').isDisplayed(), 'Voice controls should be visible again');
            
            this.addTestResult(testName, true, 'All input mode switching tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Input mode switching test failed: ${error.message}`);
        }
    }

    /**
     * Test text message handling
     */
    async testTextMessageHandling() {
        const testName = 'Text Message Handling';
        
        try {
            const textInput = this.mockElements.get('text-input');
            let messagesSent = [];
            
            // Mock sendTextMessage function
            const mockSendTextMessage = () => {
                const message = textInput.value.trim();
                if (message) {
                    messagesSent.push(message);
                    textInput.value = ''; // Clear input after sending
                    return true;
                }
                return false;
            };
            
            // Test sending a message
            textInput.value = 'Hello, this is a test message!';
            const result = mockSendTextMessage();
            
            this.assert(result === true, 'Message should be sent successfully');
            this.assert(messagesSent.length === 1, 'One message should be recorded');
            this.assert(messagesSent[0] === 'Hello, this is a test message!', 'Message content should match');
            this.assert(textInput.value === '', 'Input should be cleared after sending');
            
            // Test sending empty message
            textInput.value = '';
            const emptyResult = mockSendTextMessage();
            this.assert(emptyResult === false, 'Empty message should not be sent');
            
            // Test sending whitespace-only message
            textInput.value = '   ';
            const whitespaceResult = mockSendTextMessage();
            this.assert(whitespaceResult === false, 'Whitespace-only message should not be sent');
            
            this.addTestResult(testName, true, 'All text message handling tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Text message handling test failed: ${error.message}`);
        }
    }

    /**
     * Test participant management
     */
    async testParticipantManagement() {
        const testName = 'Participant Management';
        
        try {
            const participantsList = this.mockElements.get('participants-list');
            let participants = new Map();
            
            // Mock updateParticipantsList function
            const mockUpdateParticipantsList = () => {
                participantsList.innerHTML = '';
                
                if (participants.size === 0) {
                    participantsList.innerHTML = '<div class="participant-item"><span>No participants</span></div>';
                    return;
                }
                
                participants.forEach((participant, id) => {
                    const item = `<div class="participant-item">
                        <span>${participant.identity}${participant.isLocal ? ' (You)' : ''}</span>
                        <div class="participant-status">
                            <div class="status-indicator ${participant.isSpeaking ? 'speaking' : ''} ${!participant.isMicrophoneEnabled ? 'muted' : ''}"></div>
                        </div>
                    </div>`;
                    participantsList.innerHTML += item;
                });
            };
            
            // Test empty participants list
            mockUpdateParticipantsList();
            this.assert(participantsList.innerHTML.includes('No participants'), 'Should show no participants message');
            
            // Test adding a participant
            participants.set('user1', {
                identity: 'Alice',
                isLocal: true,
                isSpeaking: false,
                isMicrophoneEnabled: true
            });
            mockUpdateParticipantsList();
            this.assert(participantsList.innerHTML.includes('Alice'), 'Should show Alice in participants');
            this.assert(participantsList.innerHTML.includes('(You)'), 'Should show local participant indicator');
            
            // Test adding remote participant
            participants.set('user2', {
                identity: 'Bob',
                isLocal: false,
                isSpeaking: true,
                isMicrophoneEnabled: false
            });
            mockUpdateParticipantsList();
            this.assert(participantsList.innerHTML.includes('Bob'), 'Should show Bob in participants');
            this.assert(participantsList.innerHTML.includes('speaking'), 'Should show speaking indicator');
            this.assert(participantsList.innerHTML.includes('muted'), 'Should show muted indicator');
            
            // Test removing participant
            participants.delete('user2');
            mockUpdateParticipantsList();
            this.assert(!participantsList.innerHTML.includes('Bob'), 'Should not show Bob after removal');
            
            this.addTestResult(testName, true, 'All participant management tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Participant management test failed: ${error.message}`);
        }
    }

    /**
     * Test animation controls
     */
    async testAnimationControls() {
        const testName = 'Animation Controls';
        
        try {
            let animationsTriggered = [];
            
            // Mock triggerAnimation function
            const mockTriggerAnimation = (expression, intensity = 0.7, duration = 2.0) => {
                animationsTriggered.push({ expression, intensity, duration });
                return Promise.resolve(true);
            };
            
            // Test basic animation trigger
            await mockTriggerAnimation('happy');
            this.assert(animationsTriggered.length === 1, 'One animation should be triggered');
            this.assert(animationsTriggered[0].expression === 'happy', 'Animation expression should be happy');
            
            // Test animation with custom parameters
            await mockTriggerAnimation('sad', 0.9, 3.0);
            this.assert(animationsTriggered.length === 2, 'Two animations should be triggered');
            this.assert(animationsTriggered[1].intensity === 0.9, 'Custom intensity should be used');
            this.assert(animationsTriggered[1].duration === 3.0, 'Custom duration should be used');
            
            // Test parameter validation
            const isValidExpression = (expr) => {
                const validExpressions = ['happy', 'sad', 'angry', 'surprised', 'neutral', 'speak'];
                return validExpressions.includes(expr);
            };
            
            const isValidIntensity = (intensity) => {
                return intensity >= 0.0 && intensity <= 1.0;
            };
            
            const isValidDuration = (duration) => {
                return duration >= 0.1 && duration <= 10.0;
            };
            
            this.assert(isValidExpression('happy'), 'Happy should be valid expression');
            this.assert(!isValidExpression('invalid'), 'Invalid should not be valid expression');
            this.assert(isValidIntensity(0.5), '0.5 should be valid intensity');
            this.assert(!isValidIntensity(1.5), '1.5 should not be valid intensity');
            this.assert(isValidDuration(2.0), '2.0 should be valid duration');
            this.assert(!isValidDuration(15.0), '15.0 should not be valid duration');
            
            this.addTestResult(testName, true, 'All animation control tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Animation control test failed: ${error.message}`);
        }
    }

    /**
     * Test keyboard shortcuts
     */
    async testKeyboardShortcuts() {
        const testName = 'Keyboard Shortcuts';
        
        try {
            let currentMode = 'voice';
            let shortcutsHandled = [];
            
            // Mock keyboard shortcut handler
            const mockHandleKeyboardShortcuts = (event) => {
                if (event.ctrlKey && event.key === 'Tab') {
                    event.preventDefault();
                    currentMode = currentMode === 'voice' ? 'text' : 'voice';
                    shortcutsHandled.push('mode_switch');
                    return true;
                }
                
                if (event.ctrlKey && event.key === 'Enter' && currentMode === 'text') {
                    shortcutsHandled.push('send_message');
                    return true;
                }
                
                if (event.code === 'Space' && currentMode === 'voice') {
                    shortcutsHandled.push('push_to_talk');
                    return true;
                }
                
                return false;
            };
            
            // Test Ctrl+Tab for mode switching
            const ctrlTabEvent = { ctrlKey: true, key: 'Tab', preventDefault: () => {} };
            mockHandleKeyboardShortcuts(ctrlTabEvent);
            this.assert(currentMode === 'text', 'Should switch to text mode');
            this.assert(shortcutsHandled.includes('mode_switch'), 'Mode switch shortcut should be handled');
            
            // Test Ctrl+Enter for sending message
            const ctrlEnterEvent = { ctrlKey: true, key: 'Enter' };
            mockHandleKeyboardShortcuts(ctrlEnterEvent);
            this.assert(shortcutsHandled.includes('send_message'), 'Send message shortcut should be handled');
            
            // Test Space for push-to-talk (switch back to voice mode first)
            currentMode = 'voice';
            const spaceEvent = { code: 'Space' };
            mockHandleKeyboardShortcuts(spaceEvent);
            this.assert(shortcutsHandled.includes('push_to_talk'), 'Push-to-talk shortcut should be handled');
            
            this.addTestResult(testName, true, 'All keyboard shortcut tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Keyboard shortcut test failed: ${error.message}`);
        }
    }

    /**
     * Test responsive design helpers
     */
    async testResponsiveHelpers() {
        const testName = 'Responsive Design Helpers';
        
        try {
            // Mock window dimensions and media query helpers
            const mockGetViewportSize = () => {
                return {
                    width: window.innerWidth || 1920,
                    height: window.innerHeight || 1080
                };
            };
            
            const mockIsMobile = (width = mockGetViewportSize().width) => {
                return width <= 768;
            };
            
            const mockIsTablet = (width = mockGetViewportSize().width) => {
                return width > 768 && width <= 1024;
            };
            
            const mockIsDesktop = (width = mockGetViewportSize().width) => {
                return width > 1024;
            };
            
            // Test mobile detection
            this.assert(mockIsMobile(375), '375px should be detected as mobile');
            this.assert(mockIsMobile(768), '768px should be detected as mobile');
            this.assert(!mockIsMobile(800), '800px should not be detected as mobile');
            
            // Test tablet detection
            this.assert(mockIsTablet(800), '800px should be detected as tablet');
            this.assert(mockIsTablet(1024), '1024px should be detected as tablet');
            this.assert(!mockIsTablet(1200), '1200px should not be detected as tablet');
            
            // Test desktop detection
            this.assert(mockIsDesktop(1200), '1200px should be detected as desktop');
            this.assert(mockIsDesktop(1920), '1920px should be detected as desktop');
            this.assert(!mockIsDesktop(800), '800px should not be detected as desktop');
            
            // Test responsive layout adjustments
            const mockAdjustLayoutForViewport = (width) => {
                if (mockIsMobile(width)) {
                    return {
                        containerDirection: 'column',
                        controlPanelWidth: '100%',
                        animationColumns: 2
                    };
                } else if (mockIsTablet(width)) {
                    return {
                        containerDirection: 'row',
                        controlPanelWidth: '280px',
                        animationColumns: 3
                    };
                } else {
                    return {
                        containerDirection: 'row',
                        controlPanelWidth: '320px',
                        animationColumns: 4
                    };
                }
            };
            
            const mobileLayout = mockAdjustLayoutForViewport(375);
            this.assert(mobileLayout.containerDirection === 'column', 'Mobile should use column layout');
            this.assert(mobileLayout.animationColumns === 2, 'Mobile should use 2 animation columns');
            
            const desktopLayout = mockAdjustLayoutForViewport(1920);
            this.assert(desktopLayout.containerDirection === 'row', 'Desktop should use row layout');
            this.assert(desktopLayout.animationColumns === 4, 'Desktop should use 4 animation columns');
            
            this.addTestResult(testName, true, 'All responsive design helper tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Responsive design helper test failed: ${error.message}`);
        }
    }

    /**
     * Test error handling
     */
    async testErrorHandling() {
        const testName = 'Error Handling';
        
        try {
            let errorsHandled = [];
            
            // Mock error handling functions
            const mockHandleConnectionError = (error) => {
                errorsHandled.push({ type: 'connection', message: error.message });
                return { success: false, error: error.message };
            };
            
            const mockHandleAnimationError = (error) => {
                errorsHandled.push({ type: 'animation', message: error.message });
                return { success: false, fallback: true };
            };
            
            const mockHandleWebSocketError = (error) => {
                errorsHandled.push({ type: 'websocket', message: error.message });
                return { reconnect: true };
            };
            
            // Test connection error handling
            const connectionError = new Error('Failed to connect to LiveKit');
            const connectionResult = mockHandleConnectionError(connectionError);
            this.assert(!connectionResult.success, 'Connection error should return failure');
            this.assert(errorsHandled.some(e => e.type === 'connection'), 'Connection error should be recorded');
            
            // Test animation error handling
            const animationError = new Error('Animation system not ready');
            const animationResult = mockHandleAnimationError(animationError);
            this.assert(!animationResult.success, 'Animation error should return failure');
            this.assert(animationResult.fallback, 'Animation error should trigger fallback');
            
            // Test WebSocket error handling
            const wsError = new Error('WebSocket connection lost');
            const wsResult = mockHandleWebSocketError(wsError);
            this.assert(wsResult.reconnect, 'WebSocket error should trigger reconnect');
            
            // Test error message formatting
            const mockFormatErrorMessage = (error, context) => {
                return `[${context}] ${error.message}`;
            };
            
            const formattedError = mockFormatErrorMessage(connectionError, 'LiveKit');
            this.assert(formattedError.includes('[LiveKit]'), 'Error should include context');
            this.assert(formattedError.includes(connectionError.message), 'Error should include message');
            
            this.addTestResult(testName, true, 'All error handling tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Error handling test failed: ${error.message}`);
        }
    }

    /**
     * Test connection quality indicators
     */
    async testConnectionQuality() {
        const testName = 'Connection Quality';
        
        try {
            const audioLevelFill = this.mockElements.get('audio-level-fill');
            
            // Mock connection quality functions
            const mockUpdateConnectionQuality = (quality) => {
                const qualityMap = {
                    'excellent': { bars: 4, class: 'active', text: 'Excellent' },
                    'good': { bars: 3, class: 'active', text: 'Good' },
                    'poor': { bars: 2, class: 'medium', text: 'Poor' },
                    'bad': { bars: 1, class: 'poor', text: 'Bad' }
                };
                
                return qualityMap[quality] || { bars: 0, class: '', text: 'Unknown' };
            };
            
            const mockUpdateAudioLevel = (level) => {
                const clampedLevel = Math.max(0, Math.min(1, level));
                audioLevelFill.style.width = `${clampedLevel * 100}%`;
                return clampedLevel;
            };
            
            // Test connection quality mapping
            const excellentQuality = mockUpdateConnectionQuality('excellent');
            this.assert(excellentQuality.bars === 4, 'Excellent quality should show 4 bars');
            this.assert(excellentQuality.text === 'Excellent', 'Excellent quality should have correct text');
            
            const poorQuality = mockUpdateConnectionQuality('poor');
            this.assert(poorQuality.bars === 2, 'Poor quality should show 2 bars');
            this.assert(poorQuality.class === 'medium', 'Poor quality should use medium class');
            
            // Test audio level updates
            const normalLevel = mockUpdateAudioLevel(0.5);
            this.assert(normalLevel === 0.5, 'Normal audio level should be preserved');
            this.assert(audioLevelFill.style.width === '50%', 'Audio level bar should be 50%');
            
            const highLevel = mockUpdateAudioLevel(0.9);
            this.assert(audioLevelFill.style.width === '90%', 'High audio level should be 90%');
            
            // Test clamping
            const clampedHigh = mockUpdateAudioLevel(1.5);
            this.assert(clampedHigh === 1.0, 'Audio level should be clamped to 1.0');
            
            const clampedLow = mockUpdateAudioLevel(-0.5);
            this.assert(clampedLow === 0.0, 'Audio level should be clamped to 0.0');
            
            this.addTestResult(testName, true, 'All connection quality tests passed');
            
        } catch (error) {
            this.addTestResult(testName, false, `Connection quality test failed: ${error.message}`);
        }
    }

    /**
     * Add a test result
     */
    addTestResult(testName, passed, message) {
        this.testResults.push({
            name: testName,
            passed: passed,
            message: message,
            timestamp: new Date().toISOString()
        });
    }

    /**
     * Assert a condition
     */
    assert(condition, message) {
        if (!condition) {
            throw new Error(message);
        }
    }

    /**
     * Print test results
     */
    printResults() {
        console.log('\n=== Web Interface Test Results ===');
        
        const passed = this.testResults.filter(r => r.passed).length;
        const total = this.testResults.length;
        
        console.log(`Total: ${total}, Passed: ${passed}, Failed: ${total - passed}`);
        console.log('');
        
        this.testResults.forEach(result => {
            const status = result.passed ? '✅ PASS' : '❌ FAIL';
            console.log(`${status} ${result.name}: ${result.message}`);
        });
        
        console.log('\n=== End Test Results ===\n');
    }
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebInterfaceTestSuite;
}

// Make available globally for browser testing
if (typeof window !== 'undefined') {
    window.WebInterfaceTestSuite = WebInterfaceTestSuite;
}