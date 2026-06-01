document.addEventListener('zero-md-rendered', function(e) {
  const links = e.target.shadowRoot?.querySelectorAll('.markdown-body a[href*="/materials/"]');
  if (links) {
    links.forEach(function(link) { link.setAttribute('target', '_blank'); });
  }
});

class CourseChatClient {
    constructor(streamUrl, csrfToken) {
        this.streamUrl = streamUrl;
        this.csrfToken = csrfToken;
        this.isStreaming = false;
        this.currentMsgEl = null;
        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        this.form = document.getElementById('message-form');
        this.textarea = document.getElementById('content');
        this.sendBtn = document.getElementById('send-button');
        this.container = document.getElementById('message-container');
        this.typingIndicator = document.getElementById('typing-indicator');
    }

    bindEvents() {
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });
        this.textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.textarea.addEventListener('input', () => {
            this.textarea.style.height = 'auto';
            this.textarea.style.height = this.textarea.scrollHeight + 'px';
        });
    }

    sendMessage() {
        const content = this.textarea.value.trim();
        if (!content || this.isStreaming) return;

        this.isStreaming = true;
        this.sendBtn.disabled = true;
        this.textarea.disabled = true;
        this.sendBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Sending...';
        this.typingIndicator.classList.add('show');

        fetch(this.streamUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
            },
            body: JSON.stringify({ content: content }),
        }).then(response => {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            this.textarea.value = '';
            this.textarea.style.height = 'auto';
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            const processStream = () => {
                reader.read().then(({ done, value }) => {
                    if (done) { this.handleStreamComplete(); return; }
                    const chunk = decoder.decode(value);
                    for (const line of chunk.split('\n')) {
                        if (line.startsWith('data: ')) {
                            try { this.handleEvent(JSON.parse(line.slice(6))); }
                            catch (e) { console.error('Parse error:', e); }
                        }
                    }
                    processStream();
                }).catch(err => {
                    console.error('Stream error:', err);
                    this.showError('Connection lost. Please try again.');
                    this.handleStreamComplete();
                });
            };
            processStream();
        }).catch(err => {
            console.error('Fetch error:', err);
            this.showError('Failed to send message.');
            this.handleStreamComplete();
        });
    }

    handleEvent(data) {
        switch (data.type) {
            case 'user_message':
                this.addUserMessage(data.content, data.message_id);
                break;
            case 'ai_message_start':
                this.typingIndicator.classList.remove('show');
                this.startAIMessage(data.message_id);
                break;
            case 'ai_token':
                this.appendToken(data.token, data.message_id);
                break;
            case 'ai_message_complete':
                this.completeMessage(data.final_content, data.message_id);
                break;
            case 'chat_title_updated':
                this.updateTitle(data.title, data.chat_id);
                break;
            case 'error':
                this.showError(data.message);
                this.handleStreamComplete();
                break;
        }
    }

    updateTitle(title, chatId) {
        const header = document.querySelector('.card-header h5');
        if (header) header.textContent = title;
        const link = document.querySelector(`.list-group-item[href*="${chatId}"] .chat-title`);
        if (link) link.textContent = title;
    }

    addUserMessage(content, messageId) {
        const html = `
            <div class="message-container mb-3" data-message-id="${messageId}">
                <div class="message-header">
                    <span class="badge bg-primary">You</span>
                    <small class="text-muted">${new Date().toLocaleString()}</small>
                </div>
                <div class="message-content p-3 rounded">
                    <zero-md src="data:text/markdown;charset=utf-8,${encodeURIComponent(content)}">
                        <template data-append><style>.markdown-body { background-color: transparent !important; }</style></template>
                    </zero-md>
                </div>
            </div>`;
        this.typingIndicator.insertAdjacentHTML('beforebegin', html);
        this.scrollToBottom();
    }

    startAIMessage(messageId) {
        const html = `
            <div class="message-container mb-3" data-message-id="${messageId}">
                <div class="message-header">
                    <span class="badge bg-success">AI Tutor</span>
                    <small class="text-muted">${new Date().toLocaleString()}</small>
                </div>
                <div class="message-content p-3 rounded">
                    <p><span class="streaming-cursor"></span></p>
                </div>
            </div>`;
        this.typingIndicator.insertAdjacentHTML('beforebegin', html);
        this.currentMsgEl = document.querySelector(`[data-message-id="${messageId}"]`);
        this.scrollToBottom();
    }

    appendToken(token, messageId) {
        if (this.currentMsgEl) {
            const contentP = this.currentMsgEl.querySelector('.message-content p');
            const cursor = contentP.querySelector('.streaming-cursor');
            const span = document.createElement('span');
            span.textContent = token;
            cursor.parentNode.insertBefore(span, cursor);
            this.scrollToBottom();
        }
    }

    completeMessage(finalContent, messageId) {
        if (this.currentMsgEl) {
            const contentDiv = this.currentMsgEl.querySelector('.message-content');
            contentDiv.innerHTML = `<zero-md src="data:text/markdown;charset=utf-8,${encodeURIComponent(finalContent)}"><template data-append><style>.markdown-body { background-color: transparent !important; }</style></template></zero-md>`;
            this.currentMsgEl = null;
        }
    }

    handleStreamComplete() {
        this.isStreaming = false;
        this.typingIndicator.classList.remove('show');
        this.sendBtn.disabled = false;
        this.textarea.disabled = false;
        this.sendBtn.innerHTML = '<i class="bi bi-send"></i> Send';
        this.currentMsgEl = null;
    }

    showError(message) {
        const html = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>`;
        this.form.insertAdjacentHTML('beforebegin', html);
        setTimeout(() => {
            const alert = this.form.previousElementSibling;
            if (alert && alert.classList.contains('alert')) alert.remove();
        }, 5000);
    }

    scrollToBottom() {
        setTimeout(() => {
            this.container.scrollTop = this.container.scrollHeight;
        }, 10);
    }
}

window.CourseChatClient = CourseChatClient;
