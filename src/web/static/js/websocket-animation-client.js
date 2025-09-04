/**
 * WebSocket Animation Client
 * 
 * Handles real-time animation synchronization between the server and Live2D client.
 * Provides WebSocket communication for animation events, timing synchronization,
 * and real-time parameter updates.
 */

class WebSocketAnimationClient {
    constructor(live2dIntegration, animationController) {
        this.live2d = live2dIntegration;
        this.animationController = animationController;
        
        // WebSocket connection
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.maxReconnectDelay = 30000; // Max 30 seconds
        
        // Connection configuration
        this.wsUrl = this.getWebSocketUrl();
        this.clientId = null;
        
        // Animation synchronization
        this.animationQueue = [];
        this.currentSequence = null;
        this.syncTimingData = null;
        this.audioSyncActive = false;
        
        // Performance tracking
        this.latencyMeasurements = [];
        this.maxLatencyMeasurements = 20;
        this.lastPingTime = 0;
        
        // Event handlers
        this.eventHandlers = {
            'connection_established': this.handleConnectionEstablished.bind(this),
            'animation_event': this.handleAnimationEvent.bind(this),
            'heartbeat': this.handleHeartbeat.bind(this),
            'pong': this.handlePong.bind(this),
            'sync_timing': this.handleSyncTiming.bind(this)
        };
        
        // Auto-connect
        this.connect();
        
        // Set up periodic tasks
        this.setupPeriodicTasks();
    }
    
    /**
     * Get WebSocket URL based on current page location
     */
    getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname || '127.0.0.1';
        const port = 8765;
        const url = `${protocol}//${host}:${port}`;
        console.log('Configured WebSocket URL:', url);
        return url;
    }
    
    /**
     * Connect to WebSocket server with enhanced connection handling
     */
    async connect() {
        if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
            console.log('WebSocket connection already in progress');
            return;
        }
        
        try {
            console.log(`Connecting to WebSocket server: ${this.wsUrl}`);
            
            // Reset connection state
            this.intentionalClose = false;
            this.lastError = null;
            this.connectionStartTime = Date.now();
            
            // Create WebSocket with error handling
            this.ws = new WebSocket(this.wsUrl);
            
            // Set connection timeout
            this.connectionTimeout = setTimeout(() => {
                if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
                    console.error('WebSocket connection timeout');
                    this.ws.close(4000, 'Connection timeout');
                    this.handleError(new Error('Connection timeout'));
                }
            }, 10000); // 10 second timeout
            
            // Add event listeners
            this.ws.onopen = (event) => {
                clearTimeout(this.connectionTimeout);
                this.handleOpen(event);
            };
            
            this.ws.onmessage = (event) => {
                try {
                    this.handleMessage(event);
                } catch (error) {
                    console.error('Error handling message:', error);
                    this.handleError(error);
                }
            };
            
            this.ws.onclose = (event) => {
                clearTimeout(this.connectionTimeout);
                this.handleClose(event);
            };
            
            this.ws.onerror = (error) => {
                clearTimeout(this.connectionTimeout);
                this.handleError(error);
            };
            
            // Log connection attempt
            console.debug('WebSocket connection attempt:', {
                url: this.wsUrl,
                timestamp: new Date().toISOString(),
                reconnectAttempts: this.reconnectAttempts
            });
            
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.handleError(error);
            this.scheduleReconnect();
        }
    }
    
    /**
     * Handle WebSocket connection open
     */
    handleOpen(event) {
        console.log('WebSocket connected successfully');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        
        // Start ping/pong for latency measurement
        this.startLatencyMeasurement();
        
        // Dispatch connection event
        this.dispatchEvent('websocketConnected', { clientId: this.clientId });
    }
    
    /**
     * Handle incoming WebSocket messages with improved error handling and type validation
     */
    handleMessage(event) {
        try {
            // Store raw message for debugging
            this.lastReceivedMessage = {
                timestamp: Date.now(),
                data: event.data
            };
            
            // Parse JSON with type validation
            const data = JSON.parse(event.data);
            
            // Validate message structure
            if (!data || typeof data !== 'object') {
                throw new Error('Invalid message format: Expected object');
            }
            
            const messageType = data.type;
            if (!messageType || typeof messageType !== 'string') {
                throw new Error('Invalid message format: Missing or invalid type');
            }
            
            // Special handling for animation events
            if (messageType === 'animation_event') {
                this._validateAnimationEvent(data);
            }
            
            // Handle message based on type
            if (this.eventHandlers[messageType]) {
                // Log message receipt
                console.debug(`Received ${messageType} message:`, {
                    timestamp: new Date().toISOString(),
                    type: messageType,
                    size: event.data.length,
                    hasPayload: !!data.event || !!data.data
                });
                
                // Process message
                this.eventHandlers[messageType](data);
                
                // Update connection health metrics
                this._updateConnectionHealth(true);
            } else {
                console.warn(`Unknown WebSocket message type: ${messageType}`, data);
            }
            
        } catch (error) {
            console.error('Error handling WebSocket message:', error);
            
            // Log problematic message for debugging
            console.debug('Problematic message:', {
                raw: event.data,
                timestamp: new Date().toISOString(),
                error: error.message
            });
            
            // Update connection health metrics
            this._updateConnectionHealth(false);
            
            // Dispatch error event
            this.dispatchEvent('messageError', {
                error: error,
                rawMessage: event.data
            });
        }
    }
    
    /**
     * Validate animation event structure
     */
    _validateAnimationEvent(data) {
        const event = data.event;
        if (!event) {
            throw new Error('Invalid animation_event: Missing event data');
        }
        
        const requiredFields = ['event_type', 'timestamp', 'data'];
        const missingFields = requiredFields.filter(field => !(field in event));
        
        if (missingFields.length > 0) {
            throw new Error(`Invalid animation_event: Missing required fields: ${missingFields.join(', ')}`);
        }
        
        // Validate event_type
        if (event.event_type && typeof event.event_type === 'object') {
            if (!event.event_type.type || !event.event_type.value) {
                throw new Error('Invalid animation_event: Malformed event_type');
            }
        }
    }
    
    /**
     * Update connection health metrics
     */
    _updateConnectionHealth(success) {
        const now = Date.now();
        
        if (success) {
            this.lastSuccessfulMessage = now;
            this.consecutiveErrors = 0;
        } else {
            this.consecutiveErrors = (this.consecutiveErrors || 0) + 1;
            
            // Consider reconnection if too many consecutive errors
            if (this.consecutiveErrors > 5) {
                console.warn('Too many consecutive message errors - considering reconnection');
                this.scheduleReconnect();
            }
        }
    }
    
    /**
     * Handle WebSocket connection close
     */
    handleClose(event) {
        console.log('WebSocket connection closed:', event.code, event.reason);
        this.isConnected = false;
        this.clientId = null;
        
        // Dispatch disconnection event
        this.dispatchEvent('websocketDisconnected', { code: event.code, reason: event.reason });
        
        // Schedule reconnection if not intentional close
        if (event.code !== 1000) { // 1000 = normal closure
            this.scheduleReconnect();
        }
    }
    
    /**
     * Handle WebSocket errors with improved error recovery
     */
    handleError(error) {
        console.error('WebSocket error:', error);
        
        // Log detailed error information
        const errorInfo = {
            error: error,
            timestamp: new Date().toISOString(),
            connectionState: this.getConnectionStatus(),
            lastMessage: this.lastReceivedMessage,
            lastPingTime: this.lastPingTime
        };
        
        console.debug('WebSocket error details:', errorInfo);
        
        // Dispatch error event with detailed info
        this.dispatchEvent('websocketError', errorInfo);
        
        // Check if we should attempt reconnection
        if (this.isConnected && !this.intentionalClose) {
            console.log('Unexpected error - scheduling reconnection...');
            this.scheduleReconnect();
        }
        
        // Notify any active animations of the error
        if (this.currentSequence) {
            this.dispatchEvent('animationError', {
                sequenceId: this.currentSequence,
                error: error,
                recovery: 'attempting_reconnect'
            });
        }
    }
    
    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached. Giving up.');
            this.dispatchEvent('websocketReconnectFailed', { attempts: this.reconnectAttempts });
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), this.maxReconnectDelay);
        
        console.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);
        
        setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    /**
     * Send message to WebSocket server
     */
    sendMessage(data) {
        if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('Cannot send message: WebSocket not connected');
            return false;
        }
        
        try {
            this.ws.send(JSON.stringify(data));
            return true;
        } catch (error) {
            console.error('Error sending WebSocket message:', error);
            return false;
        }
    }
    
    /**
     * Handle connection established message
     */
    handleConnectionEstablished(data) {
        this.clientId = data.client_id;
        console.log(`WebSocket connection established with client ID: ${this.clientId}`);
        
        // Restore any current animation state if provided
        if (data.current_animation) {
            console.log('Restoring animation state:', data.current_animation);
            this.handleAnimationEvent({ event: data.current_animation });
        }
    }
    
    /**
     * Handle animation event from server
     */
    async handleAnimationEvent(data) {
        const event = data.event;
        const eventType = event.event_type;
        
        console.log(`Received animation event: ${eventType}`, event);
        
        try {
            switch (eventType) {
                case 'expression_change':
                    await this.handleExpressionChange(event);
                    break;
                    
                case 'mouth_sync_start':
                    await this.handleMouthSyncStart(event);
                    break;
                    
                case 'mouth_sync_update':
                    await this.handleMouthSyncUpdate(event);
                    break;
                    
                case 'mouth_sync_stop':
                    await this.handleMouthSyncStop(event);
                    break;
                    
                case 'parameter_update':
                    await this.handleParameterUpdate(event);
                    break;
                    
                case 'sync_timing':
                    await this.handleSyncTiming(event);
                    break;
                    
                default:
                    console.warn(`Unknown animation event type: ${eventType}`);
            }
            
            // Send completion notification if sequence_id is provided
            if (event.sequence_id) {
                this.sendAnimationComplete(event.sequence_id);
            }
            
        } catch (error) {
            console.error(`Error handling animation event ${eventType}:`, error);
        }
    }
    
    /**
     * Handle expression change event
     */
    async handleExpressionChange(event) {
        const { expression, intensity, duration, transition, interrupt_current } = event.data;
        
        // Interrupt current animation if requested
        if (interrupt_current && this.live2d.isAnimating) {
            console.log('Interrupting current animation for new expression');
        }
        
        // Apply transition if specified
        if (transition) {
            await this.applyExpressionTransition(transition);
        } else {
            // Direct expression change
            await this.live2d.triggerAnimation(expression, intensity, duration);
        }
        
        console.log(`Expression changed to: ${expression} (${intensity}, ${duration}s)`);
    }
    
    /**
     * Apply smooth expression transition
     */
    async applyExpressionTransition(transition) {
        const { from_expression, to_expression, duration, easing_type, blend_factor } = transition;
        
        // Implement smooth transition between expressions
        const steps = 20; // Number of interpolation steps
        const stepDuration = (duration * 1000) / steps; // Duration per step in ms
        
        for (let i = 0; i <= steps; i++) {
            const progress = i / steps;
            
            // Apply easing function
            let easedProgress = progress;
            if (easing_type === 'easeInOut') {
                easedProgress = progress < 0.5 
                    ? 2 * progress * progress 
                    : 1 - Math.pow(-2 * progress + 2, 2) / 2;
            }
            
            // Interpolate between expressions
            await this.interpolateExpressions(from_expression, to_expression, easedProgress, blend_factor);
            
            if (i < steps) {
                await new Promise(resolve => setTimeout(resolve, stepDuration));
            }
        }
    }
    
    /**
     * Interpolate between two expressions
     */
    async interpolateExpressions(fromExpr, toExpr, progress, blendFactor = 1.0) {
        const fromParams = this.live2d.expressionMap[fromExpr]?.params || {};
        const toParams = this.live2d.expressionMap[toExpr]?.params || {};
        
        // Blend parameters
        const allParams = new Set([...Object.keys(fromParams), ...Object.keys(toParams)]);
        
        allParams.forEach(param => {
            const fromValue = fromParams[param] || 0.0;
            const toValue = toParams[param] || 0.0;
            
            // Linear interpolation with blend factor
            const interpolatedValue = fromValue + (toValue - fromValue) * progress * blendFactor;
            
            this.live2d.setParameter(param, interpolatedValue, false);
        });
    }
    
    /**
     * Handle mouth sync start event
     */
    async handleMouthSyncStart(event) {
        const { text, audio_duration, sync_config } = event.data;
        
        this.audioSyncActive = true;
        
        // Configure mouth sync parameters
        if (sync_config) {
            this.live2d.mouth_sync_config = {
                ...this.live2d.mouth_sync_config,
                ...sync_config
            };
        }
        
        // Start mouth synchronization
        this.live2d.isSpeaking = true;
        
        // If audio duration is provided, schedule automatic stop
        if (audio_duration) {
            setTimeout(() => {
                if (this.audioSyncActive) {
                    this.handleMouthSyncStop({ data: { return_to_neutral: true } });
                }
            }, audio_duration * 1000);
        }
        
        console.log(`Mouth sync started for text: "${text}" (${audio_duration}s)`);
    }
    
    /**
     * Handle mouth sync parameter update
     */
    async handleMouthSyncUpdate(event) {
        const { mouth_open, mouth_form, audio_level } = event.data;
        
        if (!this.audioSyncActive) {
            return;
        }
        
        // Update mouth parameters with real-time audio data
        this.live2d.setParameter('ParamMouthOpenY', mouth_open, true);
        this.live2d.setParameter('ParamMouthForm', mouth_form, true);
        
        // Optional: Add visual feedback for audio level
        if (audio_level > 0.1) {
            // Slight head movement based on audio intensity
            const headMovement = (audio_level - 0.1) * 0.1;
            this.live2d.setParameter('ParamAngleY', Math.sin(Date.now() * 0.01) * headMovement, true);
        }
    }
    
    /**
     * Handle mouth sync stop event
     */
    async handleMouthSyncStop(event) {
        const { return_to_neutral } = event.data;
        
        this.audioSyncActive = false;
        this.live2d.isSpeaking = false;
        
        // Reset mouth parameters
        this.live2d.setParameter('ParamMouthOpenY', 0.0, true);
        this.live2d.setParameter('ParamMouthForm', 0.0, true);
        this.live2d.setParameter('ParamAngleY', 0.0, true);
        
        // Return to neutral expression if requested
        if (return_to_neutral) {
            setTimeout(() => {
                this.live2d.triggerAnimation('neutral', 0.5, 1.0);
            }, 200);
        }
        
        console.log('Mouth sync stopped');
    }
    
    /**
     * Handle parameter update event
     */
    async handleParameterUpdate(event) {
        const parameters = event.data;
        
        Object.keys(parameters).forEach(param => {
            this.live2d.setParameter(param, parameters[param], true);
        });
        
        console.log(`Updated ${Object.keys(parameters).length} parameters`);
    }
    
    /**
     * Handle sync timing event
     */
    async handleSyncTiming(event) {
        this.syncTimingData = event.data;
        
        // Use timing data to synchronize animations with audio
        const { audio_start_time, audio_duration, animation_start_time, tts_processing_delay } = this.syncTimingData;
        
        console.log('Received sync timing data:', this.syncTimingData);
        
        // Calculate timing offsets for precise synchronization
        const currentTime = Date.now() / 1000;
        const audioDelay = Math.max(0, audio_start_time - currentTime);
        
        // Schedule animation to start at the right time
        if (audioDelay > 0) {
            setTimeout(() => {
                this.dispatchEvent('audioSyncReady', this.syncTimingData);
            }, audioDelay * 1000);
        } else {
            this.dispatchEvent('audioSyncReady', this.syncTimingData);
        }
    }
    
    /**
     * Handle heartbeat message
     */
    handleHeartbeat(data) {
        // Respond to heartbeat to maintain connection
        this.sendMessage({
            type: 'heartbeat_response',
            timestamp: Date.now(),
            client_id: this.clientId
        });
        
        // Optional: Update UI with server status
        this.dispatchEvent('serverHeartbeat', {
            queue_length: data.queue_length,
            current_animation: data.current_animation
        });
    }
    
    /**
     * Handle pong response for latency measurement
     */
    handlePong(data) {
        const now = Date.now();
        const latency = now - data.timestamp;
        
        this.recordLatency(latency);
        
        console.log(`WebSocket latency: ${latency}ms`);
    }
    
    /**
     * Send animation completion notification
     */
    sendAnimationComplete(sequenceId) {
        this.sendMessage({
            type: 'animation_complete',
            sequence_id: sequenceId,
            timestamp: Date.now(),
            client_id: this.clientId
        });
    }
    
    /**
     * Send parameter feedback to server
     */
    sendParameterFeedback() {
        if (!this.live2d) return;
        
        const parameters = this.live2d.parameterCurrent;
        
        this.sendMessage({
            type: 'parameter_feedback',
            parameters: parameters,
            timestamp: Date.now(),
            client_id: this.clientId
        });
    }
    
    /**
     * Start latency measurement with ping/pong
     */
    startLatencyMeasurement() {
        const pingInterval = 10000; // Ping every 10 seconds
        
        setInterval(() => {
            if (this.isConnected) {
                this.lastPingTime = Date.now();
                this.sendMessage({
                    type: 'ping',
                    timestamp: this.lastPingTime,
                    client_id: this.clientId
                });
            }
        }, pingInterval);
    }
    
    /**
     * Record latency measurement
     */
    recordLatency(latency) {
        this.latencyMeasurements.push(latency);
        
        // Keep only recent measurements
        if (this.latencyMeasurements.length > this.maxLatencyMeasurements) {
            this.latencyMeasurements.shift();
        }
        
        // Send latency data to server
        this.sendMessage({
            type: 'latency_measurement',
            latency: latency,
            average_latency: this.getAverageLatency(),
            client_id: this.clientId
        });
    }
    
    /**
     * Get average latency
     */
    getAverageLatency() {
        if (this.latencyMeasurements.length === 0) return 0;
        
        const sum = this.latencyMeasurements.reduce((a, b) => a + b, 0);
        return sum / this.latencyMeasurements.length;
    }
    
    /**
     * Set up periodic tasks
     */
    setupPeriodicTasks() {
        // Send parameter feedback every 5 seconds
        setInterval(() => {
            if (this.isConnected) {
                this.sendParameterFeedback();
            }
        }, 5000);
        
        // Clean up old measurements every minute
        setInterval(() => {
            const cutoffTime = Date.now() - 300000; // 5 minutes ago
            this.latencyMeasurements = this.latencyMeasurements.filter(
                measurement => measurement.timestamp > cutoffTime
            );
        }, 60000);
    }
    
    /**
     * Dispatch custom event
     */
    dispatchEvent(eventName, detail) {
        const event = new CustomEvent(eventName, { detail });
        document.dispatchEvent(event);
    }
    
    /**
     * Get connection status
     */
    getConnectionStatus() {
        return {
            isConnected: this.isConnected,
            clientId: this.clientId,
            reconnectAttempts: this.reconnectAttempts,
            averageLatency: this.getAverageLatency(),
            audioSyncActive: this.audioSyncActive,
            wsUrl: this.wsUrl
        };
    }
    
    /**
     * Manually trigger reconnection
     */
    reconnect() {
        if (this.ws) {
            this.ws.close();
        }
        
        this.reconnectAttempts = 0;
        this.connect();
    }
    
    /**
     * Close WebSocket connection
     */
    disconnect() {
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
        }
        
        this.isConnected = false;
        this.clientId = null;
    }
    
    /**
     * Request animation trigger from server
     */
    requestAnimation(expression, intensity = 0.7, duration = 2.0, priority = 'normal') {
        return this.sendMessage({
            type: 'request_animation',
            data: {
                expression,
                intensity,
                duration,
                priority
            },
            client_id: this.clientId,
            timestamp: Date.now()
        });
    }
    
    /**
     * Request TTS synchronization
     */
    requestTTSSync(text, expression = 'speak', audioElement = null) {
        const audioData = {};
        
        if (audioElement) {
            audioData.audio_duration = audioElement.duration;
            audioData.has_audio_element = true;
        }
        
        return this.sendMessage({
            type: 'request_tts_sync',
            data: {
                text,
                expression,
                ...audioData
            },
            client_id: this.clientId,
            timestamp: Date.now()
        });
    }
}

// Export for use in other modules
window.WebSocketAnimationClient = WebSocketAnimationClient; 