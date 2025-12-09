// Thinking Messages
const THINKING_MESSAGES = [
    "🕺 Galavanting...",
    "🧠 Confabulating...",
    "🫣 Unhiding...",
    "🧶 Byte-braiding...",
    "😌 Panic-taming...",
    "🚶‍♂️ Perambulating...",
    "🔮 Divining...",
    "🕵️‍♀️ Unconcealing...",
    "📏 Metric-massaging...",
    "🦘 Log-leaping...",
    "📡 Packet-probing...",
    "⛏️ Metric-mining...",
    "🤠 Log-lassoing...",
    "🧭 Trace-traversing...",
    "⚓ Data-dredging...",
    "🚀 Warming up the stream...",
    "🤔 Thinking deep thoughts...",
    "✨ Summoning Markdown magic...",
    "🧠 Crunching ideas...",
    "📡 Connecting to the source..."
];

// State
let currentSessionId = null;
let eventSource = null;
let thinkingInterval = null;

// DOM Elements
const sessionsList = document.getElementById('sessions-list');
const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const chatForm = document.getElementById('chat-form');
const newSessionBtn = document.getElementById('new-session-btn');
const newSessionModal = document.getElementById('new-session-modal');
const createSessionForm = document.getElementById('create-session-form');
const closeModalBtns = document.querySelectorAll('.btn-close, .btn-close-modal');
const currentSessionName = document.getElementById('current-session-name');
const currentSessionIdBadge = document.getElementById('current-session-id');
const exportBtn = document.getElementById('export-btn');
const timelineBtn = document.getElementById('timeline-btn');
const themeToggleBtn = document.getElementById('theme-toggle-btn');
const sunIcon = document.querySelector('.sun-icon');
const moonIcon = document.querySelector('.moon-icon');

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    fetchSessions();
    setupEventListeners();
});

// Event Listeners
function setupEventListeners() {
    // Modal
    newSessionBtn.addEventListener('click', () => {
        newSessionModal.classList.add('show');
    });

    closeModalBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const modal = e.target.closest('.modal');
            if (modal) {
                modal.classList.remove('show');
            }
        });
    });

    // Close on click outside
    window.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal')) {
            e.target.classList.remove('show');
        }
    });

    // Create Session
    createSessionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('session-name').value;
        const password = document.getElementById('session-password').value;
        const unsafe = document.getElementById('session-unsafe').checked;
        const verbose = document.getElementById('session-verbose').checked;

        try {
            const response = await fetch('/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, password, unsafe, verbose })
            });

            if (!response.ok) throw new Error('Failed to create session');

            const session = await response.json();
            newSessionModal.classList.remove('show');
            createSessionForm.reset();
            await fetchSessions();
            loadSession(session.id);
        } catch (error) {
            alert(error.message);
        }
    });

    // Chat
    messageInput.addEventListener('input', () => {
        sendBtn.disabled = !messageInput.value.trim();
        // Auto-resize
        messageInput.style.height = 'auto';
        messageInput.style.height = messageInput.scrollHeight + 'px';
    });

    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (messageInput.value.trim()) {
                chatForm.dispatchEvent(new Event('submit'));
            }
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message || !currentSessionId) return;

        // Add user message
        appendMessage(message, 'user');
        messageInput.value = '';
        messageInput.style.height = 'auto';
        sendBtn.disabled = true;

        // Show thinking animation
        showThinking();

        try {
            // Send to API
            // Note: For this demo, we assume unsafe/cached auth or simple passwordless for chat if session is active
            // In a real app, we'd handle auth better.
            const response = await fetch(`/sessions/${currentSessionId}/chat?unsafe=true`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });

            if (!response.ok) throw new Error('Failed to send message');
        } catch (error) {
            stopThinking();
            appendMessage(`Error: ${error.message}`, 'bot'); // Show error as bot message
        }
    });

    // Actions
    exportBtn.addEventListener('click', () => {
        if (currentSessionId) {
            window.open(`/sessions/${currentSessionId}/export?unsafe=true`, '_blank');
        }
    });

    timelineBtn.addEventListener('click', async () => {
        if (!currentSessionId) return;

        const timelineModal = document.getElementById('timeline-modal');
        const timelineContainer = document.getElementById('timeline-container');

        timelineModal.classList.add('show');
        timelineContainer.innerHTML = '<div class="loading-state">Generating timeline...</div>';

        try {
            const response = await fetch(`/sessions/${currentSessionId}/timeline?unsafe=true`);
            const data = await response.json();
            renderTimeline(data.timeline, timelineContainer);
        } catch (e) {
            timelineContainer.innerHTML = `<div class="loading-state" style="color: red">Error fetching timeline: ${e.message}</div>`;
        }
    });

    // Theme Toggle
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleTheme);
    }
}

// Theme Functions
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    // Default to dark if no preference, or if system prefers dark and no saved preference
    // Actually, let's default to saved, or system, or dark.
    let theme = 'dark';
    if (savedTheme) {
        theme = savedTheme;
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        theme = 'light';
    }

    setTheme(theme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);

    // Update Icons
    if (theme === 'light') {
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
    } else {
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
    }
}

// API Functions
async function fetchSessions() {
    try {
        const response = await fetch('/sessions');
        const sessions = await response.json();
        renderSessionsList(sessions);
    } catch (error) {
        console.error('Error fetching sessions:', error);
    }
}

function renderSessionsList(sessions) {
    sessionsList.innerHTML = '';
    sessions.forEach(session => {
        const li = document.createElement('li');
        li.className = `session-item ${session.id === currentSessionId ? 'active' : ''}`;
        li.onclick = () => loadSession(session.id);

        li.innerHTML = `
            <div class="session-name">${session.name || session.id}</div>
            <div class="session-date">${new Date(session.created).toLocaleDateString()}</div>
        `;
        sessionsList.appendChild(li);
    });
}

async function loadSession(sessionId) {
    if (currentSessionId === sessionId) return;

    // Cleanup old stream
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    stopThinking();

    currentSessionId = sessionId;

    // Update UI
    document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
    // Re-render list to update active state (lazy way)
    fetchSessions(); // Or just find the element and add class

    // Enable inputs
    messageInput.disabled = false;
    exportBtn.disabled = false;
    timelineBtn.disabled = false;

    // Get Metadata
    try {
        const response = await fetch(`/sessions/${sessionId}?unsafe=true`);
        const session = await response.json();
        currentSessionName.textContent = session.name || session.id;
        currentSessionIdBadge.textContent = session.id;
    } catch (e) {
        console.error(e);
    }

    // Clear chat
    chatContainer.innerHTML = '';

    // Connect to SSE
    connectStream(sessionId);
}

function connectStream(sessionId) {
    eventSource = new EventSource(`/sessions/${sessionId}/stream`);

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'text') {
            stopThinking(); // Stop thinking on first token

            // Check if last message is bot, if so append, else create new
            const lastMsg = chatContainer.lastElementChild;
            if (lastMsg && lastMsg.classList.contains('bot') && !lastMsg.dataset.complete) {
                updateLastBotMessage(data.content);
            } else {
                appendMessage(data.content, 'bot');
            }
        } else if (data.type === 'done') {
            stopThinking();
            const lastMsg = chatContainer.lastElementChild;
            if (lastMsg && lastMsg.classList.contains('bot')) {
                lastMsg.dataset.complete = "true";
            }
        } else if (data.type === 'error') {
            stopThinking();
            appendMessage(`Error: ${data.content}`, 'bot');
        }
    };

    eventSource.onerror = (err) => {
        console.error("EventSource failed:", err);
        // eventSource.close(); // Don't close, let it retry?
    };
}

function showThinking() {
    // Create a temporary thinking message
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot thinking';
    msgDiv.id = 'thinking-bubble';

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = '🤖';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = THINKING_MESSAGES[Math.floor(Math.random() * THINKING_MESSAGES.length)];

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(contentDiv);
    chatContainer.appendChild(msgDiv);
    scrollToBottom();

    // Cycle messages
    if (thinkingInterval) clearInterval(thinkingInterval);
    thinkingInterval = setInterval(() => {
        const bubble = document.getElementById('thinking-bubble');
        if (bubble) {
            const content = bubble.querySelector('.message-content');
            content.textContent = THINKING_MESSAGES[Math.floor(Math.random() * THINKING_MESSAGES.length)];
        }
    }, 2000);
}

function stopThinking() {
    if (thinkingInterval) {
        clearInterval(thinkingInterval);
        thinkingInterval = null;
    }
    const bubble = document.getElementById('thinking-bubble');
    if (bubble) {
        bubble.remove();
    }
}

function appendMessage(content, role) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'user' ? '👤' : '🤖';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Render Markdown
    if (role === 'bot') {
        // Store raw content for updates
        msgDiv.dataset.raw = content;
        contentDiv.innerHTML = parseSections(content);
    } else {
        contentDiv.textContent = content; // User messages are plain text usually
    }

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(contentDiv);

    chatContainer.appendChild(msgDiv);
    scrollToBottom();
}

function updateLastBotMessage(content) {
    const lastMsg = chatContainer.lastElementChild;
    const contentDiv = lastMsg.querySelector('.message-content');
    // For streaming, we might get chunks. 
    // If the API sends full text updates (accumulated), we replace.
    // If it sends chunks, we append.
    // The CLI implementation sends chunks.
    // But `marked.parse` expects full markdown.
    // So we need to accumulate locally if we want to render markdown properly during stream.
    // For now, let's assume the API sends chunks and we just append text, 
    // OR we store the full raw text in a data attribute and re-render.

    let currentText = lastMsg.dataset.raw || "";
    currentText += content;
    lastMsg.dataset.raw = currentText;
    contentDiv.innerHTML = parseSections(currentText);
    scrollToBottom();
}

function parseSections(text) {
    // Regex to find the sections
    const findingsRegex = /\*\*Section Findings:\*\*([\s\S]*?)(?=\*\*Section Decisions:\*\*|$)/;
    const decisionsRegex = /\*\*Section Decisions:\*\*([\s\S]*?)(?=\*\*Section Suggested actions:\*\*|$)/;
    const actionsRegex = /\*\*Section Suggested actions:\*\*([\s\S]*?)$/;

    const findingsMatch = text.match(findingsRegex);
    const decisionsMatch = text.match(decisionsRegex);
    const actionsMatch = text.match(actionsRegex);

    if (findingsMatch || decisionsMatch || actionsMatch) {
        let html = '';

        if (findingsMatch) {
            html += `<div class="section section-findings">
                <div class="section-header">🔍 Findings</div>
                <div class="section-body">${marked.parse(findingsMatch[1].trim())}</div>
            </div>`;
        }

        if (decisionsMatch) {
            html += `<div class="section section-decisions">
                <div class="section-header">🧠 Decisions</div>
                <div class="section-body">${marked.parse(decisionsMatch[1].trim())}</div>
            </div>`;
        }

        if (actionsMatch) {
            html += `<div class="section section-actions">
                <div class="section-header">🚀 Suggested Actions</div>
                <div class="section-body">${marked.parse(actionsMatch[1].trim())}</div>
            </div>`;
        }

        // Also handle any introductory text before the first section?
        // For now, we assume the format is strictly followed if any section is present.
        // But let's check if there is text BEFORE the first match
        const firstMatchIndex = Math.min(
            findingsMatch ? findingsMatch.index : Infinity,
            decisionsMatch ? decisionsMatch.index : Infinity,
            actionsMatch ? actionsMatch.index : Infinity
        );

        if (firstMatchIndex > 0 && firstMatchIndex !== Infinity) {
            const intro = text.substring(0, firstMatchIndex);
            if (intro.trim()) {
                html = `<div class="section section-intro">${marked.parse(intro)}</div>` + html;
            }
        }

        return html;
    } else {
        return marked.parse(text);
    }
}


function renderTimeline(timelineData, container) {
    if (!Array.isArray(timelineData) || timelineData.length === 0) {
        container.innerHTML = '<div class="loading-state">No timeline events found.</div>';
        return;
    }

    let html = '';
    timelineData.forEach(event => {
        const typeClass = `type-${event.type.toLowerCase()}`;
        html += `
            <div class="timeline-item ${typeClass}">
                <div class="timeline-marker"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-type">${event.type}</span>
                        <span class="timeline-timestamp">${event.timestamp}</span>
                    </div>
                    <div class="timeline-body">${marked.parse(event.description)}</div>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}
