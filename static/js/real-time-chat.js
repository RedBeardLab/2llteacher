/**
 * Real-time Chat Client for LLTeacher Conversations
 * Handles streaming chat functionality with AI tutors
 */
class RealTimeChatClient {
    // Constants
    static PASTE_WARNING_MESSAGE = "Pasting is against the spirit of this exercise. Please be aware that it was detected and will be reviewed.";
    static PASTE_WORD_THRESHOLD = 10;

    constructor(conversationId, csrfToken) {
        this.conversationId = conversationId;
        this.csrfToken = csrfToken;
        this.eventSource = null;
        this.isStreaming = false;
        this.currentStreamingMessage = null;

        this.initializeElements();
        this.bindEvents();
    }
    
    initializeElements() {
        this.form = document.getElementById('message-form');
        this.textarea = document.getElementById('content');
        this.sendButton = this.form.querySelector('button[type="submit"]');
        this.messageTypeRadios = this.form.querySelectorAll('input[name="message_type"]');
        this.conversationContainer = document.querySelector('.conversation-container');
        
        // Create typing indicator
        this.typingIndicator = document.createElement('div');
        this.typingIndicator.className = 'typing-indicator';
        this.typingIndicator.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> AI is thinking...';
        this.conversationContainer.appendChild(this.typingIndicator);
    }
    
    bindEvents() {
        // Override form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });
        
        // Handle Enter key for sending messages
        this.textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                if (e.shiftKey) {
                    // Shift+Enter: Allow new line (default behavior)
                    return;
                } else {
                    // Enter: Send message
                    e.preventDefault();
                    this.sendMessage();
                }
            }
        });
        
        // Auto-resize textarea
        this.textarea.addEventListener('input', () => {
            this.textarea.style.height = 'auto';
            this.textarea.style.height = this.textarea.scrollHeight + 'px';
        });

        // Handle message type changes for R Code styling
        this.messageTypeRadios.forEach(radio => {
            radio.addEventListener('change', () => {
                this.updateTextareaMode();
            });
        });

        // Handle paste detection for copy warning
        this.textarea.addEventListener('paste', (e) => {
            console.log("detect paste");
            this.handlePaste(e);
        });

        // Initialize textarea mode
        this.updateTextareaMode();
    }
    
    async sendMessage() {
        const content = this.textarea.value.trim();
        const messageType = this.getSelectedMessageType();
        
        if (!content || this.isStreaming) {
            return;
        }
        
        // Disable form and show loading state
        this.setLoadingState(true);
        
        try {
            // Start streaming connection
            await this.startStreaming(content, messageType);
            
            // Clear form
            this.textarea.value = '';
            this.textarea.style.height = 'auto';
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.showError('Failed to send message. Please try again.');
            this.setLoadingState(false);
        }
    }
    
    async startStreaming(content, messageType) {
        return new Promise((resolve, reject) => {
            this.isStreaming = true;
            this.showTypingIndicator(true);
            
            // Create EventSource for streaming
            const streamUrl = `/conversations/api/${this.conversationId}/stream/`;
            
            // Use fetch to POST data and get streaming response
            fetch(streamUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    content: content,
                    message_type: messageType
                })
            }).then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                const processStream = () => {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            this.handleStreamComplete();
                            resolve();
                            return;
                        }
                        
                        const chunk = decoder.decode(value);
                        const lines = chunk.split('\n');
                        
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    this.handleStreamEvent(data);
                                } catch (e) {
                                    console.error('Error parsing SSE data:', e);
                                }
                            }
                        }
                        
                        processStream();
                    }).catch(reject);
                };
                
                processStream();
            }).catch(reject);
        });
    }
    
    handleStreamEvent(data) {
        switch (data.type) {
            case 'user_message':
                this.addUserMessage(data.content, data.message_id, data.message_type || 'student');
                break;
                
            case 'ai_message_start':
                this.showTypingIndicator(false);
                this.startAIMessage(data.message_id);
                break;
                
            case 'ai_token':
                this.appendAIToken(data.token, data.message_id);
                break;
                
            case 'ai_message_complete':
                this.completeAIMessage(data.message_id, data.final_content);
                break;
                
            case 'error':
                this.showError(data.message);
                this.handleStreamComplete();
                break;
        }
    }
    
    addUserMessage(content, messageId, messageType = 'student') {
        let messageContentHtml;
        
        if (messageType === 'code') {
            // Create R code message with run button
            messageContentHtml = `
                <div class="r-code-container">
                    <div class="r-code-header">
                        <span class="r-code-label">
                            <i class="bi bi-code-slash"></i>
                            R Code
                        </span>
                        <button class="btn btn-sm btn-outline-primary r-run-button" 
                                data-message-id="${messageId}" 
                                ${window.rExecutionManager && window.rExecutionManager.isInitialized ? '' : 'disabled'}>
                            ${window.rExecutionManager && window.rExecutionManager.isInitialized ? 
                              '<i class="bi bi-play-fill"></i> Run Code' : 
                              '<i class="bi bi-hourglass-split"></i> Initializing...'}
                        </button>
                    </div>
                    <pre><code class="language-r">${this.escapeHtml(content)}</code></pre>
                    <div class="r-execution-output" id="r-output-${messageId}"></div>
                </div>
            `;
        } else {
            // Regular message
            messageContentHtml = `<md-block untrusted>${this.escapeHtml(content)}</md-block>`;
        }
        
        const messageHtml = `
            <div class="message-container message-chat mb-3" data-message-id="${messageId}">
                <div class="message-header">
                    <span class="badge bg-primary">Student</span>
                    <small class="text-muted">${this.formatTimestamp(new Date())}</small>
                </div>
                <div class="message-content p-3 rounded">
                    ${messageContentHtml}
                </div>
            </div>
        `;
        
        this.typingIndicator.insertAdjacentHTML('beforebegin', messageHtml);
        
        // If it's R code, bind the run button
        if (messageType === 'code') {
            this.bindRCodeButton(messageId);
        }
        
        this.scrollToBottom();
    }
    
    startAIMessage(messageId) {
        const messageHtml = `
            <div class="message-container message-ai ai-message-streaming mb-3" data-message-id="${messageId}">
                <div class="message-header">
                    <span class="badge bg-success">AI Tutor</span>
                    <small class="text-muted">${this.formatTimestamp(new Date())}</small>
                </div>
                <div class="message-content p-3 rounded">
                    <p><span class="streaming-cursor"></span></p>
                </div>
            </div>
        `;
        
        this.typingIndicator.insertAdjacentHTML('beforebegin', messageHtml);
        this.currentStreamingMessage = document.querySelector(`[data-message-id="${messageId}"]`);
        this.scrollToBottom();
    }
    
    appendAIToken(token, messageId) {
        if (this.currentStreamingMessage) {
            const contentP = this.currentStreamingMessage.querySelector('.message-content p');
            const cursor = contentP.querySelector('.streaming-cursor');
            
            // Insert token before cursor
            const tokenSpan = document.createElement('span');
            tokenSpan.textContent = token;
            cursor.parentNode.insertBefore(tokenSpan, cursor);
            
            this.scrollToBottom();
        }
    }
    
    completeAIMessage(messageId, finalContent) {
        if (this.currentStreamingMessage) {
            // Remove streaming class and cursor
            this.currentStreamingMessage.classList.remove('ai-message-streaming');
            const messageContent = this.currentStreamingMessage.querySelector('.message-content');
            
            // Replace the streaming content with md-block
            messageContent.innerHTML = `<md-block untrusted>${this.escapeHtml(finalContent)}</md-block>`;
            
            this.currentStreamingMessage = null;
        }
    }
    
    handleStreamComplete() {
        this.isStreaming = false;
        this.showTypingIndicator(false);
        this.setLoadingState(false);
        this.currentStreamingMessage = null;
    }
    
    showTypingIndicator(show) {
        if (show) {
            this.typingIndicator.classList.add('show');
        } else {
            this.typingIndicator.classList.remove('show');
        }
        this.scrollToBottom();
    }
    
    getSelectedMessageType() {
        for (const radio of this.messageTypeRadios) {
            if (radio.checked) {
                return radio.value;
            }
        }
        return 'student'; // Default fallback
    }
    
    setLoadingState(loading) {
        this.sendButton.disabled = loading;
        this.textarea.disabled = loading;
        
        // Disable/enable radio buttons
        this.messageTypeRadios.forEach(radio => {
            radio.disabled = loading;
        });
        
        if (loading) {
            this.sendButton.classList.add('send-button-loading');
            this.sendButton.innerHTML = '<i class="bi bi-hourglass-split"></i> Sending...';
        } else {
            this.sendButton.classList.remove('send-button-loading');
            this.sendButton.innerHTML = '<i class="bi bi-send"></i> Send Message';
        }
    }
    
    showError(message) {
        const errorHtml = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <i class="fas fa-exclamation-triangle"></i> ${this.escapeHtml(message)}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        this.form.insertAdjacentHTML('beforebegin', errorHtml);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const alert = this.form.previousElementSibling;
            if (alert && alert.classList.contains('alert')) {
                alert.remove();
            }
        }, 5000);
    }
    
    bindRCodeButton(messageId) {
        const button = document.querySelector(`[data-message-id="${messageId}"] .r-run-button`);
        if (button && window.rExecutionManager) {
            // Use the execution manager's binding system for consistency
            if (!button.hasAttribute('data-handler-bound')) {
                window.rExecutionManager.bindButtonClickHandler(button, messageId);
                button.setAttribute('data-handler-bound', 'true');
            }
        }
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.conversationContainer.scrollTop = this.conversationContainer.scrollHeight;
        }, 10);
    }
    
    formatTimestamp(date) {
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    updateTextareaMode() {
        const selectedType = this.getSelectedMessageType();
        
        if (selectedType === 'code') {
            // Switch to R Code mode
            this.textarea.classList.add('r-code-mode');
            this.textarea.placeholder = 'Enter your R code here...\n\n# Example:\ndata <- c(1, 2, 3, 4, 5)\nmean(data)';
        } else {
            // Switch to regular chat mode
            this.textarea.classList.remove('r-code-mode');
            this.textarea.placeholder = 'Type your message here... (Press Enter to send, Shift+Enter for new line)';
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Handle paste event to detect and warn about pasting long content
     */
    handlePaste(event) {
        // Get the pasted content
        const pastedText = (event.clipboardData || window.clipboardData).getData('text');

        // Count words in pasted text
        const wordCount = this.countWords(pastedText);

        // If more than threshold words, show warning and log to backend
        if (wordCount > RealTimeChatClient.PASTE_WORD_THRESHOLD) {
            // Show warning to user
            this.showPasteWarning(wordCount);

            // Log paste event to backend
            this.logPasteEvent(pastedText, wordCount);
        }
    }

    /**
     * Count words in a text string
     */
    countWords(text) {
        // Trim whitespace and split by whitespace
        const words = text.trim().split(/\s+/);
        // Filter out empty strings
        return words.filter(word => word.length > 0).length;
    }

    /**
     * Show warning message about paste detection
     */
    showPasteWarning(wordCount) {
        const warningHtml = `
            <div class="alert alert-danger alert-dismissible fade show paste-warning" role="alert">
                <i class="bi bi-exclamation-triangle-fill"></i>
                <strong>Paste Detected:</strong>
                ${RealTimeChatClient.PASTE_WARNING_MESSAGE}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        // Remove any existing paste warning first
        const existingWarning = document.querySelector('.paste-warning');
        if (existingWarning) {
            existingWarning.remove();
        }

        // Insert warning before the form
        this.form.insertAdjacentHTML('beforebegin', warningHtml);

        // Auto-dismiss after 10 seconds
        setTimeout(() => {
            const alert = document.querySelector('.paste-warning');
            if (alert) {
                alert.remove();
            }
        }, 10000);
    }

    /**
     * Log paste event to backend for review
     */
    async logPasteEvent(pastedText, wordCount) {
        try {
            const response = await fetch(`/conversations/api/${this.conversationId}/log-paste/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    pasted_content: pastedText,
                    word_count: wordCount,
                    content_length: pastedText.length,
                    timestamp: new Date().toISOString()
                })
            });

            if (!response.ok) {
                console.error('Failed to log paste event:', response.status);
            }
        } catch (error) {
            console.error('Error logging paste event:', error);
            // Fail silently - don't disrupt user experience
        }
    }

}

// Export for use in other modules
window.RealTimeChatClient = RealTimeChatClient;
