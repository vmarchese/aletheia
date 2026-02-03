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
const sessionPasswords = {}; // Cache for session passwords
const sessionMetadata = {}; // Cache for session metadata (including unsafe status)
let currentSessionId = null;
let eventSource = null;
let thinkingInterval = null;
let availableCommands = []; // Cache for available commands
let commandCompletionVisible = false;
let selectedCommandIndex = -1;
let currentNextRequests = []; // Store current next request suggestions
let isProcessing = false; // Track if agent is currently processing

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
const passwordModal = document.getElementById('password-modal');
const passwordForm = document.getElementById('password-form');
const passwordInput = document.getElementById('session-password-input');
const passwordTargetId = document.getElementById('password-target-session-id');
const passwordErrorMsg = document.getElementById('password-error-message');
const exportBtn = document.getElementById('export-btn');
const timelineBtn = document.getElementById('timeline-btn');
const scratchpadBtn = document.getElementById('scratchpad-btn');
const themeToggleBtn = document.getElementById('theme-toggle-btn');
const sunIcon = document.querySelector('.sun-icon');
const moonIcon = document.querySelector('.moon-icon');
const scratchpadSessionName = document.getElementById('scratchpad-session-name');
const scratchpadSessionId = document.getElementById('scratchpad-session-id');
const timelineSessionName = document.getElementById('timeline-session-name');
const timelineSessionId = document.getElementById('timeline-session-id');
const suggestionsContainer = document.getElementById('suggestions-container');

// Sidebar Info Elements
const infoSessionName = document.getElementById('info-session-name');
const infoSessionId = document.getElementById('info-session-id');
const infoSessionCost = document.getElementById('info-session-cost');
const infoSessionStatus = document.getElementById('info-session-status');

// API Helpers
const getSessionPassword = (sessionId) => sessionPasswords[sessionId] || null;
const getAuthParams = (sessionId) => {
    const pwd = getSessionPassword(sessionId);
    const params = new URLSearchParams();
    if (pwd) params.append('password', pwd);

    // Append unsafe=true if we know the session is unsafe
    const metadata = sessionMetadata[sessionId];
    if (metadata && (metadata.unsafe === true || metadata.unsafe === "True")) {
        params.append('unsafe', 'true');
    }

    return params;
};

// Sidebar Elements
const infoSidebar = document.querySelector('.info-sidebar');
const toggleInfoBtn = document.getElementById('toggle-info-btn');
const chatWrapper = document.querySelector('.chat-wrapper');

console.log('Sidebar Elements:', { infoSessionName, infoSessionId, infoSessionCost, infoSessionStatus });


// Initialization
document.addEventListener('DOMContentLoaded', () => {
    // Configure marked for better markdown rendering
    marked.setOptions({
        breaks: true,      // Convert \n to <br>
        gfm: true,         // GitHub Flavored Markdown (includes tables)
        tables: true,      // Enable table support
        sanitize: false,   // Don't sanitize HTML (we trust our content)
        smartLists: true,  // Better list parsing
        smartypants: false // Don't convert quotes/dashes
    });

    initTheme();
    initSidebar();
    fetchSessions();
    setupEventListeners();
    loadCommands(); // Load available commands for autocomplete
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

            // Cache password if created successfully
            if (password) {
                sessionPasswords[session.id] = password;
            }

            newSessionModal.classList.remove('show');
            createSessionForm.reset();
            await fetchSessions();
            loadSession(session.id);
        } catch (error) {
            alert(error.message);
        }
    });

    // Password Modal
    passwordForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const sessionId = passwordTargetId.value;
        const pwd = passwordInput.value;
        if (sessionId && pwd) {
            sessionPasswords[sessionId] = pwd;
            // Don't close modal yet, wait for success or failure
            // But loadSession is async. We can trigger it and let it handle UI.
            // Actually, we should probably show loading state in modal?
            // For now, let's just trigger loadSession.

            // Clear previous error
            passwordErrorMsg.style.display = 'none';
            passwordErrorMsg.textContent = '';

            loadSession(sessionId, true);
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

        // Hide autocomplete if visible
        hideCommandCompletion();

        // Add user message
        appendMessage(message, 'user');

        // Clear next request suggestions when user sends a message
        clearNextRequestSuggestions();

        messageInput.value = '';
        messageInput.style.height = 'auto';

        // Disable input while processing
        setProcessing(true);

        // Show thinking animation
        showThinking();

        try {
            // Send to API
            const body = { message };
            const pwd = getSessionPassword(currentSessionId);
            if (pwd) body.password = pwd;

            const response = await fetch(`/sessions/${currentSessionId}/chat?unsafe=false`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) throw new Error('Failed to send message');
        } catch (error) {
            stopThinking();
            setProcessing(false);
            appendMessage(`Error: ${error.message}`, 'bot'); // Show error as bot message
        }
    });

    // Command Autocomplete
    messageInput.addEventListener('input', (e) => {
        const value = messageInput.value;

        // Check if input starts with "/"
        if (value.startsWith('/')) {
            const commandPart = value.substring(1).toLowerCase();
            showCommandCompletion(commandPart);
        } else {
            hideCommandCompletion();
        }
    });

    messageInput.addEventListener('keydown', (e) => {
        // Handle autocomplete navigation when visible
        if (commandCompletionVisible) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                navigateCommandCompletion('down');
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                navigateCommandCompletion('up');
            } else if (e.key === 'Tab' || (e.key === 'Enter' && selectedCommandIndex >= 0)) {
                e.preventDefault();
                selectCommand();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                hideCommandCompletion();
            }
        }
    });

    // Actions
    exportBtn.addEventListener('click', () => {
        if (currentSessionId) {
            const params = getAuthParams(currentSessionId);
            window.open(`/sessions/${currentSessionId}/export?${params.toString()}`, '_blank');
        }
    });

    timelineBtn.addEventListener('click', async () => {
        if (!currentSessionId) return;

        const timelineModal = document.getElementById('timeline-modal');
        const timelineContainer = document.getElementById('timeline-container');

        timelineModal.classList.add('show');

        // Update header details
        if (timelineSessionName) timelineSessionName.textContent = currentSessionName.textContent;
        if (timelineSessionId) timelineSessionId.textContent = currentSessionId;

        timelineContainer.innerHTML = '<div class="loading-state">Generating timeline...</div>';

        try {
            const params = getAuthParams(currentSessionId);
            const url = `/sessions/${currentSessionId}/timeline?${params.toString()}`;
            console.log('[Timeline] Fetching timeline from:', url);
            console.log('[Timeline] Auth params:', params.toString());
            console.log('[Timeline] Session metadata:', sessionMetadata[currentSessionId]);

            const response = await fetch(url);
            if (!response.ok) {
                const errorText = await response.text();
                console.error('[Timeline] Response not OK:', response.status, errorText);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            const data = await response.json();
            console.log('[Timeline] Received data:', data);
            console.log('[Timeline] Timeline array:', data.timeline);

            renderTimeline(data.timeline, timelineContainer);
        } catch (e) {
            console.error('[Timeline] Error:', e);
            timelineContainer.innerHTML = `<div class="loading-state" style="color: red">Error fetching timeline: ${e.message}</div>`;
        }
    });

    scratchpadBtn.addEventListener('click', async () => {
        if (!currentSessionId) return;

        const scratchpadModal = document.getElementById('scratchpad-modal');
        const scratchpadContainer = document.getElementById('scratchpad-container');

        scratchpadModal.classList.add('show');

        // Update header details
        if (scratchpadSessionName) scratchpadSessionName.textContent = currentSessionName.textContent;
        if (scratchpadSessionId) scratchpadSessionId.textContent = currentSessionId;

        scratchpadContainer.innerHTML = '<div class="loading-state">Loading scratchpad...</div>';

        try {
            const params = getAuthParams(currentSessionId);
            const response = await fetch(`/sessions/${currentSessionId}/scratchpad?${params.toString()}`);
            if (!response.ok) throw new Error('Unauthorized or failed');
            const data = await response.json();

            // Check if content is empty
            if (!data.content) {
                scratchpadContainer.innerHTML = '<div class="empty-state">No scratchpad entries yet.</div>';
            } else {
                // Render markdown
                scratchpadContainer.innerHTML = marked.parse(data.content);
            }
        } catch (e) {
            scratchpadContainer.innerHTML = `<div class="loading-state" style="color: red">Error fetching scratchpad: ${e.message}</div>`;
        }
    });

    // Theme Toggle
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleTheme);
    }

    // Info Sidebar Toggle
    if (toggleInfoBtn) {
        toggleInfoBtn.addEventListener('click', toggleInfoSidebar);
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
function initSidebar() {
    const isCollapsed = localStorage.getItem('infoSidebarCollapsed') === 'true';
    if (isCollapsed) {
        infoSidebar.classList.add('collapsed');
        // Update chat wrapper width if needed, though flex should handle it
        // If we want chat wrapper to take full width:
        chatWrapper.style.maxWidth = '100%';
        chatWrapper.style.flex = '0 0 100%';
    }
}

function toggleInfoSidebar() {
    infoSidebar.classList.toggle('collapsed');
    const isCollapsed = infoSidebar.classList.contains('collapsed');
    localStorage.setItem('infoSidebarCollapsed', isCollapsed);

    if (isCollapsed) {
        chatWrapper.style.maxWidth = '100%';
        chatWrapper.style.flex = '0 0 100%';
    } else {
        chatWrapper.style.maxWidth = '80%';
        chatWrapper.style.flex = '0 0 80%';
    }
}

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

async function loadSession(sessionId, force = false) {
    if (currentSessionId === sessionId && !force) return;

    // Cleanup old stream
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    stopThinking();
    setProcessing(false);

    currentSessionId = sessionId;

    // Update UI
    document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
    // Re-render list to update active state (lazy way)
    fetchSessions(); // Or just find the element and add class

    // Enable inputs (setProcessing already handles messageInput)
    exportBtn.disabled = false;
    timelineBtn.disabled = false;
    scratchpadBtn.disabled = false;

    // Get Metadata
    try {
        const password = getSessionPassword(sessionId);
        // First try to check if we can access it (unsafe check is done in list, but let's see)
        // We do NOT send unsafe=true blindly anymore.

        let url = `/sessions/${sessionId}?ts=${Date.now()}`;
        if (password) {
            url += `&password=${encodeURIComponent(password)}`;
        }

        const response = await fetch(url);

        if (response.status === 401 || response.status === 400 || !response.ok) {
            // Likely needs password or password wrong
            // Check if session is actually unsafe from list?
            // But if we failed here, we probably need password.
            // Let's assume 400 with "password" related error means we need prompt.
            const errorText = await response.text(); // or json

            // If we don't have a password yet, show prompt
            if (!password) {
                showPasswordPrompt(sessionId);
                return;
            }

            // If we HAD a password but it failed, message depends on if we are forcing (user just entered it)
            if (password) {
                if (force) {
                    // User just entered this password and it failed.
                    // Show error in modal and keep it open.
                    if (passwordErrorMsg) {
                        passwordErrorMsg.textContent = "Incorrect password. Please try again.";
                        passwordErrorMsg.style.display = 'block';
                    }
                    // Ensure modal is open (should be already)
                    passwordModal.classList.add('show');
                    return;
                } else {
                    // Cached password failed? Clear it and prompt again.
                    alert("Session authentication failed. Please enter password again.");
                    delete sessionPasswords[sessionId];
                    showPasswordPrompt(sessionId);
                    return;
                }
            }
        }

        const session = await response.json();

        // Cache session metadata (including unsafe status)
        sessionMetadata[sessionId] = session;

        // Success! If we were forcing (modal open), close it now.
        if (force) {
            passwordModal.classList.remove('show');
            passwordForm.reset();
            // Clear passwords input too (already done by reset, but ensure)
            passwordInput.value = '';
        }

        console.log('Session loaded:', session);

        // Check if session is encrypted (safe) but we don't have a password.
        // The API returns basic metadata even for locked sessions.
        // Unsafe field is now boolean true/false, but handle string "False" for backward compat.
        if ((session.unsafe === false || session.unsafe === "False") && !password) {
            console.log('Session is encrypted and locked. Prompting for password.');
            showPasswordPrompt(sessionId);
            return;
        }

        currentSessionName.textContent = session.name || session.id;
        currentSessionIdBadge.textContent = session.id;

        updateSessionSidebar(session);

    } catch (e) {
        console.error(e);
        return; // Stop loading
    }

    // Clear chat
    chatContainer.innerHTML = '';

    // Connect to SSE
    connectStream(sessionId);
}

function showPasswordPrompt(sessionId) {
    passwordTargetId.value = sessionId;
    passwordInput.value = '';
    // Clear error
    if (passwordErrorMsg) {
        passwordErrorMsg.style.display = 'none';
        passwordErrorMsg.textContent = '';
    }
    passwordModal.classList.add('show');
    passwordInput.focus();
}

function connectStream(sessionId) {
    // There is no easy way to pass headers to EventSource.
    // We can pass password in URL query params.
    const pwd = getSessionPassword(sessionId);
    let url = `/sessions/${sessionId}/stream`;
    if (pwd) {
        url += `?password=${encodeURIComponent(pwd)}`;
    }

    eventSource = new EventSource(url);

    // Track function calls and timing
    let functionCalls = [];
    let sessionStartTime = Date.now();
    let messageStartTime = null;

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('[SSE] Received event:', data);

        if (data.type === 'function_call') {
            // Add function call in real-time to the thinking bubble
            console.log('[SSE] Function call event received:', data.content);
            functionCalls.push(data.content);
            addFunctionCallToThinking(data.content);

            // Start message timing on first function call
            if (!messageStartTime) {
                messageStartTime = Date.now();
            }
        } else if (data.type === 'text') {
            stopThinking(); // Stop thinking on first token

            // Check if last message is bot, if so append, else create new
            const lastMsg = chatContainer.lastElementChild;
            if (lastMsg && lastMsg.classList.contains('bot') && !lastMsg.dataset.complete) {
                updateLastBotMessage(data.content);
            } else {
                appendMessage(data.content, 'bot');
            }
        } else if (data.type === 'confidence') {
            stopThinking();
            updateStructuredResponse('confidence', data.content);
        } else if (data.type === 'agent') {
            updateStructuredResponse('agent', data.content);
        } else if (data.type === 'findings') {
            updateStructuredResponse('findings', data.content);
        } else if (data.type === 'decisions') {
            updateStructuredResponse('decisions', data.content);
        } else if (data.type === 'next_actions') {
            updateStructuredResponse('next_actions', data.content);
        } else if (data.type === 'errors') {
            updateStructuredResponse('errors', data.content);
        } else if (data.type === 'text_fallback') {
            // Fallback: JSON parsing failed, render raw content as markdown
            stopThinking();
            console.log('[SSE] Fallback text received, attempting to parse sections');

            // Try to parse sections from the text
            const fallbackHtml = parseSections(data.content);

            // If parseSections returned HTML with sections, use it
            if (fallbackHtml && fallbackHtml.includes('section-tabs')) {
                // Render as structured content with warning
                const lastMsg = chatContainer.lastElementChild;
                if (lastMsg && lastMsg.classList.contains('bot') && !lastMsg.dataset.complete) {
                    const contentDiv = lastMsg.querySelector('.message-content');
                    if (contentDiv) {
                        contentDiv.innerHTML = `
                            <div class="fallback-indicator" style="background: #fef3c7; border-left: 3px solid #f59e0b; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px; font-size: 0.9em;">
                                ⚠️ Displaying unstructured response
                            </div>
                            ${fallbackHtml}
                        `;
                    }
                } else {
                    appendMessage(`
                        <div class="fallback-indicator" style="background: #fef3c7; border-left: 3px solid #f59e0b; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px; font-size: 0.9em;">
                            ⚠️ Displaying unstructured response
                        </div>
                        ${fallbackHtml}
                    `, 'bot');
                }
            } else {
                // Fallback to plain markdown if no sections found
                const markdownHtml = marked.parse(data.content);
                const lastMsg = chatContainer.lastElementChild;
                if (lastMsg && lastMsg.classList.contains('bot') && !lastMsg.dataset.complete) {
                    const contentDiv = lastMsg.querySelector('.message-content');
                    if (contentDiv) {
                        contentDiv.innerHTML = `
                            <div class="fallback-indicator" style="background: #fef3c7; border-left: 3px solid #f59e0b; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px; font-size: 0.9em;">
                                ⚠️ Displaying unstructured response
                            </div>
                            ${markdownHtml}
                        `;
                    }
                } else {
                    appendMessage(`
                        <div class="fallback-indicator" style="background: #fef3c7; border-left: 3px solid #f59e0b; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px; font-size: 0.9em;">
                            ⚠️ Displaying unstructured response
                        </div>
                        ${markdownHtml}
                    `, 'bot');
                }
            }
        } else if (data.type === 'response_complete') {
            // Structured response completed successfully
            stopThinking();
            console.log('[SSE] Structured response complete');
            // Ensure the last bot message is marked as complete and visible
            const lastMsg = chatContainer.lastElementChild;
            if (lastMsg && lastMsg.classList.contains('bot')) {
                lastMsg.dataset.complete = "true";
                // If message is empty or hidden, log warning
                const contentDiv = lastMsg.querySelector('.message-content');
                if (contentDiv && !contentDiv.innerHTML.trim()) {
                    console.warn('[SSE] Response complete but message content is empty');
                }
            } else {
                console.warn('[SSE] Response complete but no bot message found in DOM');
            }
        } else if (data.type === 'done') {
            stopThinking();
            setProcessing(false);

            // Calculate elapsed times
            const messageElapsedMs = messageStartTime ? Date.now() - messageStartTime : 0;
            const messageElapsedSeconds = (messageElapsedMs / 1000).toFixed(0);

            const totalElapsedMs = Date.now() - sessionStartTime;
            const totalMinutes = Math.floor(totalElapsedMs / 60000);
            const totalSeconds = Math.floor((totalElapsedMs % 60000) / 1000);
            const totalTimeStr = `${totalMinutes}m ${totalSeconds}s`;

            finalizeThinkingBubble(messageElapsedSeconds, totalTimeStr);

            // Reset for next interaction
            functionCalls = [];
            messageStartTime = null;

            const lastMsg = chatContainer.lastElementChild;
            if (lastMsg && lastMsg.classList.contains('bot')) {
                lastMsg.dataset.complete = "true";
            }
            // Update session info (cost, etc) after interaction
            console.log('Stream finished (done event received). Refreshing session metadata...');
            fetchSessionMetadata(currentSessionId);

        } else if (data.type === 'error') {
            stopThinking();
            setProcessing(false);
            appendMessage(`Error: ${data.content}`, 'bot');
        } else if (data.type === 'usage') {
            // Update the last bot message with usage info
            console.log('Usage data received:', data.content);
            updateLastBotMessageUsage(data.content);
        }
    };

    eventSource.onerror = (err) => {
        console.error("EventSource failed:", err);
        // eventSource.close(); // Don't close, let it retry?
    };
}

async function fetchSessionMetadata(sessionId) {
    // Helper to refresh metadata silently
    if (!sessionId) return;
    try {
        const pwd = getSessionPassword(sessionId);
        let url = `/sessions/${sessionId}?ts=${Date.now()}`;
        if (pwd) url += `&password=${encodeURIComponent(pwd)}`;

        const response = await fetch(url);
        if (response.ok) {
            const session = await response.json();
            updateSessionSidebar(session);
        }
    } catch (e) {
        console.error("Failed to refresh session metadata", e);
    }
}

function updateSessionSidebar(session) {
    // Cache session metadata for auth params
    if (session.id) {
        sessionMetadata[session.id] = session;
    }

    if (infoSessionName) infoSessionName.textContent = session.name || session.id;
    if (infoSessionId) infoSessionId.textContent = session.id;
    if (infoSessionCost) infoSessionCost.textContent = `€${(session.total_cost || 0).toFixed(6)}`;
    if (infoSessionStatus) infoSessionStatus.textContent = session.status;
}


function showThinking() {
    // Create a temporary thinking message with collapsible function calls container
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot thinking';
    msgDiv.id = 'thinking-bubble';

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = '';
    avatar.style.backgroundImage = 'url(/static/icons/owl.png)';

    // Create the collapsible container structure
    const bodyWrapper = document.createElement('div');
    bodyWrapper.className = 'message-body-wrapper';

    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'function-calls-summary';
    summaryDiv.id = 'function-calls-container';

    const header = document.createElement('div');
    header.className = 'function-calls-header';
    header.innerHTML = `
        <span class="collapse-icon">▼</span>
        <span class="summary-text">${THINKING_MESSAGES[Math.floor(Math.random() * THINKING_MESSAGES.length)]}</span>
    `;

    const content = document.createElement('div');
    content.className = 'function-calls-content';
    content.id = 'function-calls-list';

    // Toggle collapse on header click
    header.addEventListener('click', () => {
        const isCollapsed = content.classList.contains('collapsed');
        content.classList.toggle('collapsed');
        header.querySelector('.collapse-icon').textContent = isCollapsed ? '▼' : '▶';
    });

    summaryDiv.appendChild(header);
    summaryDiv.appendChild(content);
    bodyWrapper.appendChild(summaryDiv);

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bodyWrapper);
    chatContainer.appendChild(msgDiv);
    scrollToBottom();

    // Cycle thinking messages
    if (thinkingInterval) clearInterval(thinkingInterval);
    thinkingInterval = setInterval(() => {
        const bubble = document.getElementById('thinking-bubble');
        if (bubble) {
            const summaryText = bubble.querySelector('.summary-text');
            if (summaryText && !bubble.dataset.finalized) {
                summaryText.textContent = THINKING_MESSAGES[Math.floor(Math.random() * THINKING_MESSAGES.length)];
            }
        }
    }, 2000);
}

function stopThinking() {
    if (thinkingInterval) {
        clearInterval(thinkingInterval);
        thinkingInterval = null;
    }
    // Don't remove the bubble anymore - it will be converted to the function calls summary
}

function setProcessing(processing) {
    isProcessing = processing;
    messageInput.disabled = processing;
    sendBtn.disabled = processing;
    if (processing) {
        messageInput.placeholder = "Agent is processing...";
    } else {
        messageInput.placeholder = "Describe the issue or ask a question...";
    }
}

function addFunctionCallToThinking(callData) {
    const functionCallsList = document.getElementById('function-calls-list');
    if (!functionCallsList) return;

    const { function_name, arguments: args } = callData;
    const argsFormatted = Object.entries(args || {})
        .map(([key, value]) => `${key}="${value}"`)
        .join(' ');

    const callDiv = document.createElement('div');
    callDiv.className = 'function-call-item';
    callDiv.textContent = `- ${function_name}(${argsFormatted})`;
    functionCallsList.appendChild(callDiv);

    scrollToBottom();
}

function finalizeThinkingBubble(elapsedSeconds, totalTimeStr) {
    const bubble = document.getElementById('thinking-bubble');
    if (!bubble) return;

    // Mark as finalized so the thinking message doesn't change anymore
    bubble.dataset.finalized = 'true';
    bubble.classList.remove('thinking');

    // Update the summary text to show both elapsed times
    const summaryText = bubble.querySelector('.summary-text');
    if (summaryText) {
        summaryText.textContent = `processed for ${elapsedSeconds}s (total time: ${totalTimeStr})`;
    }

    // Remove both IDs so they won't be found again in subsequent interactions
    bubble.removeAttribute('id');
    const functionCallsList = bubble.querySelector('#function-calls-list');
    if (functionCallsList) {
        functionCallsList.removeAttribute('id');
    }
    const container = bubble.querySelector('#function-calls-container');
    if (container) {
        container.removeAttribute('id');
    }
}

const AGENT_ICONS = {
    'kubernetes_data_fetcher': '/static/icons/k8s.png',
    'awsamp': '/static/icons/aws.png',
    'log_file_data_fetcher': '/static/icons/log.png',
    'pcap_file_data_fetcher': '/static/icons/pcap.png',
    'claude_code_analyzer': '/static/icons/code.png',
    'copilot_code_analyzer': '/static/icons/code.png',
    'aws': '/static/icons/aws.png',
    'azure': '/static/icons/azure.png',
    'network': '/static/icons/network.png',
    'security': '/static/icons/security.png',
    'securityagent': '/static/icons/security.png',
    'sysdiag': '/static/icons/sysdiag.png',
    'orchestrator': '/static/icons/owl.png',
    'default': '/static/icons/owl.png'
};

function getAgentIcon(agentName) {
    if (!agentName) return AGENT_ICONS['default'];
    // Normalize agent name (lowercase, remove extra spaces)
    const normalized = agentName.toLowerCase().trim();
    return AGENT_ICONS[normalized] || AGENT_ICONS['default'];
}

function parseFrontmatter(text) {
    // Try to match standard frontmatter with closing ---
    let match = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n/);

    // Fallback: Try to match frontmatter ended by double newline if no closing ---
    if (!match) {
        // Look for block starting with ---, containing key:value pairs, ending with double newline
        // We ensure newlines exists to avoid matching simple horizontal rules
        match = text.match(/^---\s*\n((?:.*?:.*\n)+)\n/);
    }

    if (!match) return { metadata: {}, content: text };

    const frontmatterRaw = match[1];
    // If strict match, use match[0].length. If fallback, we need to calculate length carefully
    // match[0] in fallback includes the trailing newline, so usage is safe?
    // Wait, regex 2 `^---\s*\n((?:.*?:.*\n)+)\n` matches `---` then lines then `\n`. 
    // It consumes the separator newline.
    const content = text.substring(match[0].length);
    const metadata = {};

    frontmatterRaw.split('\n').forEach(line => {
        const parts = line.split(':');
        if (parts.length >= 2) {
            const key = parts[0].trim();
            const value = parts.slice(1).join(':').trim();
            metadata[key] = value;
        }
    });

    return { metadata, content };
}


function appendMessage(content, role) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';

    // Default avatar
    let avatarIcon = role === 'user' ? '👤' : '/static/icons/owl.png';
    let displayContent = content;
    let agentName = null;

    if (role === 'bot') {
        const parsed = parseFrontmatter(content);
        displayContent = parsed.content;

        if (parsed.metadata.agent) {
            agentName = parsed.metadata.agent;
            avatarIcon = getAgentIcon(agentName);
        } else {
            // Fallback for old format or streaming partials
            const agentMatch = content.match(/^AGENT:\s*([a-zA-Z0-9_]+)\s*\n/);
            if (agentMatch) {
                agentName = agentMatch[1].trim();
                avatarIcon = getAgentIcon(agentName);
                displayContent = content.substring(agentMatch[0].length);
            }
        }

        // Store raw content for updates
        msgDiv.dataset.raw = content;

        // Detect skills first
        console.log('[Skill Detection] Checking response for skills...');
        console.log('[Skill Detection] Display content preview:', displayContent.substring(0, 500));
        const skills = extractSkillUsage(displayContent);
        console.log('[Skill Detection] Skills found:', skills);

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = parseSections(displayContent, skills);

        // Make code blocks collapsible after rendering
        makeCodeBlocksCollapsible(contentDiv);

        renderAvatar(avatar, avatarIcon, agentName || 'Bot');

        const bodyWrapper = document.createElement('div');
        bodyWrapper.className = 'message-body-wrapper';
        bodyWrapper.appendChild(contentDiv);

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(bodyWrapper);

        // Add metadata footer if available
        if (parsed.metadata && (parsed.metadata.usage || parsed.metadata.timestamp)) {
            const footerDiv = document.createElement('div');
            footerDiv.className = 'message-footer';
            let footerText = '';
            if (parsed.metadata.usage) footerText += `Usage: ${parsed.metadata.usage} `;
            if (parsed.metadata.timestamp) footerText += ` • ${parsed.metadata.timestamp}`;
            footerDiv.textContent = footerText;
            bodyWrapper.appendChild(footerDiv);
        }
    } else {
        avatar.textContent = avatarIcon; // User is still emoji/text for now
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = displayContent;

        const bodyWrapper = document.createElement('div');
        bodyWrapper.className = 'message-body-wrapper';
        bodyWrapper.appendChild(contentDiv);

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(bodyWrapper);
    }

    chatContainer.appendChild(msgDiv);
    scrollToBottom();
}

function renderAvatar(container, iconSource, title) {
    if (iconSource.startsWith('/')) {
        const img = document.createElement('img');
        img.src = iconSource;
        img.alt = title;
        if (title) container.title = title;
        container.innerHTML = '';
        container.appendChild(img);
    } else {
        container.textContent = iconSource;
    }
}

function updateLastBotMessage(content) {
    const lastMsg = chatContainer.lastElementChild;
    const avatar = lastMsg.querySelector('.avatar');
    let contentDiv = lastMsg.querySelector('.message-content');

    // If contentDiv doesn't exist (e.g., converting thinking bubble), create it
    if (!contentDiv) {
        contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        const bodyWrapper = lastMsg.querySelector('.message-body-wrapper');
        if (bodyWrapper) {
            bodyWrapper.appendChild(contentDiv);
        }
    }

    let currentText = lastMsg.dataset.raw || "";
    currentText += content;
    lastMsg.dataset.raw = currentText;

    const parsed = parseFrontmatter(currentText);

    console.log('updateLastBotMessage:', {
        textLength: currentText.length,
        metadata: parsed.metadata,
        contentLength: parsed.content.length
    });

    let displayContent = parsed.content;
    let agentName = null;

    if (parsed.metadata.agent) {
        agentName = parsed.metadata.agent;
        const icon = getAgentIcon(agentName);

        // Check if we need to update avatar
        const currentImg = avatar.querySelector('img');
        const currentSrc = currentImg ? currentImg.getAttribute('src') : null;

        if (currentSrc !== icon) {
            renderAvatar(avatar, icon, agentName);
        }

        // Update skill badge if skills detected
        console.log('[Skill Detection UPDATE] Checking for skills in updated content...');
        const skills = extractSkillUsage(displayContent);
        console.log('[Skill Detection UPDATE] Skills found:', skills);

        // Update content with skills - pass contentDiv for incremental updates
        const result = parseSections(displayContent, skills, contentDiv);
        if (result !== undefined) {
            // Only update innerHTML if parseSections returned HTML (initial creation)
            contentDiv.innerHTML = result;
            makeCodeBlocksCollapsible(contentDiv);
        }
        // If result is undefined, parseSections updated the tabs in place
    } else {
        // Fallback for streaming partials (frontmatter closing might not be arrived yet)
        // or old format
        const agentMatch = currentText.match(/^AGENT:\s*([a-zA-Z0-9_]+)\s*\n/);
        if (agentMatch) {
            agentName = agentMatch[1].trim();
            const icon = getAgentIcon(agentName);

            // Update skill badge for streaming
            console.log('[Skill Detection FALLBACK] Checking for skills...');
            const skills = extractSkillUsage(displayContent);
            console.log('[Skill Detection FALLBACK] Skills found:', skills);

            const result = parseSections(displayContent, skills, contentDiv);
            if (result !== undefined) {
                contentDiv.innerHTML = result;
                makeCodeBlocksCollapsible(contentDiv);
            }

            // Update footer (only timestamp from frontmatter now)

            let footerDiv = lastMsg.querySelector('.message-footer');
            if (parsed.metadata && parsed.metadata.timestamp) {
                if (!footerDiv) {
                    footerDiv = document.createElement('div');
                    footerDiv.className = 'message-footer';
                    // Append to wrapper if exists, else lastMsg (fallback)
                    const wrapper = lastMsg.querySelector('.message-body-wrapper');
                    if (wrapper) wrapper.appendChild(footerDiv);
                    else lastMsg.appendChild(footerDiv);
                }
                // Preserve usage if it was set by SSE
                const usageMatch = footerDiv.textContent.match(/Usage: \d+/);
                let footerText = '';
                if (usageMatch) footerText += usageMatch[0] + ' • ';
                footerText += parsed.metadata.timestamp;
                footerDiv.textContent = footerText;
            }

            scrollToBottom();
        } else {
            // No agent metadata or AGENT: prefix - handle plain content (e.g., command output)
            const skills = extractSkillUsage(displayContent);
            const result = parseSections(displayContent, skills, contentDiv);
            if (result !== undefined) {
                contentDiv.innerHTML = result;
                makeCodeBlocksCollapsible(contentDiv);
            }
            scrollToBottom();
        }
    }
}

function updateLastBotMessageUsage(usageData) {
    const lastMsg = chatContainer.lastElementChild;
    if (!lastMsg || !lastMsg.classList.contains('bot')) return;

    let footerDiv = lastMsg.querySelector('.message-footer');
    if (!footerDiv) {
        footerDiv = document.createElement('div');
        footerDiv.className = 'message-footer';
        const wrapper = lastMsg.querySelector('.message-body-wrapper');
        if (wrapper) wrapper.appendChild(footerDiv);
        else lastMsg.appendChild(footerDiv);
    }

    const usageStr = `Usage: ${usageData.total_tokens} (in: ${usageData.input_tokens}, out: ${usageData.output_tokens})`;

    // Append or replace usage in footer
    // If footer already has timestamp (from Frontmatter), keep it
    // Format: "Usage: ... • <timestamp>"

    let currentText = footerDiv.textContent;
    let timestamp = "";
    if (currentText.includes('•')) {
        timestamp = currentText.split('•')[1].trim();
    } else if (currentText.match(/^\d{4}-\d{2}-\d{2}/)) {
        // purely timestamp?
        timestamp = currentText;
    }

    if (timestamp) {
        footerDiv.textContent = `${usageStr} • ${timestamp}`;
    } else {
        footerDiv.textContent = usageStr;
    }
}

function updateStructuredResponse(fieldType, content) {
    console.log('[updateStructuredResponse] Called with fieldType:', fieldType, 'content:', content);
    const lastMsg = chatContainer.lastElementChild;

    // Create new message if needed - check if last message is a proper bot message with structured data
    // Also exclude thinking bubble which has ID 'thinking-bubble'
    const needsNewMessage = !lastMsg ||
                            lastMsg.classList.contains('user') ||
                            lastMsg.dataset.complete ||
                            !lastMsg.classList.contains('bot') ||
                            lastMsg.classList.contains('function-call-notification') ||
                            lastMsg.id === 'thinking-bubble';

    if (needsNewMessage) {
        console.log('[updateStructuredResponse] Creating new structured message, reason:', {
            noLastMsg: !lastMsg,
            isUser: lastMsg?.classList.contains('user'),
            isComplete: lastMsg?.dataset.complete,
            notBot: lastMsg && !lastMsg.classList.contains('bot'),
            isFunctionCall: lastMsg?.classList.contains('function-call-notification'),
            isThinking: lastMsg?.id === 'thinking-bubble'
        });
        createStructuredMessage();
    }

    const msgDiv = chatContainer.lastElementChild;
    if (!msgDiv.dataset.structuredData) {
        console.log('[updateStructuredResponse] Message has no structuredData, initializing');
        msgDiv.dataset.structuredData = JSON.stringify({});
    }

    const data = JSON.parse(msgDiv.dataset.structuredData);
    data[fieldType] = content;
    msgDiv.dataset.structuredData = JSON.stringify(data);

    console.log('[updateStructuredResponse] Updated data:', data);

    // Render the updated structured response
    renderStructuredMessage(msgDiv, data);
    console.log('[updateStructuredResponse] Rendered structured message');

    // Update suggestions if next_actions contains next_requests
    if (fieldType === 'next_actions' && content.next_requests && content.next_requests.length > 0) {
        currentNextRequests = content.next_requests;
        renderNextRequestSuggestions(currentNextRequests);
    }
}

function renderNextRequestSuggestions(suggestions) {
    console.log('[renderNextRequestSuggestions] Rendering suggestions:', suggestions);

    if (!suggestionsContainer) {
        console.warn('[renderNextRequestSuggestions] Suggestions container not found');
        return;
    }

    // Clear existing suggestions
    suggestionsContainer.innerHTML = '';

    // If no suggestions, hide container
    if (!suggestions || suggestions.length === 0) {
        suggestionsContainer.style.display = 'none';
        return;
    }

    // Show container and render suggestions
    suggestionsContainer.style.display = 'flex';

    // Create title
    const title = document.createElement('span');
    title.className = 'suggestions-title';
    title.textContent = 'Quick actions:';
    suggestionsContainer.appendChild(title);

    // Create wrapper for pills
    const pillsWrapper = document.createElement('div');
    pillsWrapper.className = 'suggestions-pills';

    // Create suggestion pills
    suggestions.forEach((suggestion) => {
        const pill = document.createElement('button');
        pill.type = 'button'; // Prevent form submission
        pill.className = 'suggestion-pill';
        pill.textContent = suggestion;
        pill.setAttribute('title', suggestion); // Tooltip for long text

        // Click handler
        pill.addEventListener('click', (e) => {
            e.preventDefault(); // Extra safety to prevent form submission
            if (messageInput && !messageInput.disabled) {
                messageInput.value = suggestion;
                messageInput.focus();
                // Trigger input event to adjust height
                messageInput.dispatchEvent(new Event('input', { bubbles: true }));
                // Auto-resize textarea
                messageInput.style.height = 'auto';
                messageInput.style.height = messageInput.scrollHeight + 'px';
            }
        });

        pillsWrapper.appendChild(pill);
    });

    suggestionsContainer.appendChild(pillsWrapper);
    scrollToBottom(); // Ensure suggestions are visible
}

function clearNextRequestSuggestions() {
    currentNextRequests = [];
    renderNextRequestSuggestions([]);
}

function createStructuredMessage() {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot';
    msgDiv.dataset.structuredData = JSON.stringify({});

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.style.backgroundImage = 'url(/static/icons/owl.png)';

    const bodyWrapper = document.createElement('div');
    bodyWrapper.className = 'message-body-wrapper';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    bodyWrapper.appendChild(contentDiv);

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bodyWrapper);

    // Attach tab click handler to msgDiv (which won't be replaced)
    msgDiv.addEventListener('click', (e) => {
        console.log('Click on msgDiv detected!', e.target);
        console.log('Target classes:', e.target.className);

        // Find the button element (could be the target or a parent)
        let target = e.target;
        while (target && target !== msgDiv) {
            console.log('Checking element:', target, 'has tab-btn?', target.classList?.contains('tab-btn'));
            if (target.classList && target.classList.contains('tab-btn')) {
                console.log('Found tab button! Tab name:', target.dataset.tab);
                e.preventDefault();
                e.stopPropagation();
                const tabName = target.dataset.tab;
                if (tabName) {
                    const contentDiv = msgDiv.querySelector('.message-content');
                    console.log('Switching to tab:', tabName);
                    switchStructuredTab(contentDiv, tabName);
                }
                return;
            }
            target = target.parentElement;
        }
        console.log('No tab button found in click path');
    });

    chatContainer.appendChild(msgDiv);
    scrollToBottom();
}

function renderStructuredMessage(msgDiv, data) {
    console.log('[renderStructuredMessage] Called with data:', data);
    const contentDiv = msgDiv.querySelector('.message-content');
    const avatar = msgDiv.querySelector('.avatar');

    if (!contentDiv) {
        console.error('[renderStructuredMessage] No .message-content found in msgDiv:', msgDiv);
        return;
    }

    let html = '';

    // Agent and confidence header
    if (data.agent || data.confidence) {
        const agentName = data.agent || 'Orchestrator';
        const agentIcon = getAgentIcon(agentName);
        if (avatar) {
            renderAvatar(avatar, agentIcon, agentName);
        } else {
            console.warn('[renderStructuredMessage] No avatar element found, skipping avatar render');
        }

        html += '<div class="response-header">';
        html += `<div class="agent-name"><strong>Agent:</strong> ${agentName}</div>`;
        if (data.confidence !== undefined) {
            const confidencePct = Math.round(data.confidence * 100);
            html += `<div class="confidence-meter">`;
            html += `<div class="confidence-label">Confidence: ${confidencePct}%</div>`;
            html += `<div class="confidence-bar">`;
            html += `<div class="confidence-fill" style="width: ${confidencePct}%"></div>`;
            html += `</div></div>`;
        }
        html += '</div>';
    }

    // Create tabs structure
    html += '<div class="section-tabs">';
    html += '<div class="tabs-nav">';

    const hasFindings = data.findings && Object.keys(data.findings).length > 0;
    const hasDecisions = data.decisions && Object.keys(data.decisions).length > 0;
    const hasActions = data.next_actions && data.next_actions.steps && data.next_actions.steps.length > 0;
    const hasErrors = data.errors && data.errors.length > 0;

    if (hasFindings) html += '<button class="tab-btn active" data-tab="findings">🔍 Findings</button>';
    if (hasDecisions) html += `<button class="tab-btn ${!hasFindings ? 'active' : ''}" data-tab="decisions">🎯 Decisions</button>`;
    if (hasActions) html += `<button class="tab-btn ${!hasFindings && !hasDecisions ? 'active' : ''}" data-tab="actions">📋 Next Actions</button>`;
    if (hasErrors) html += '<button class="tab-btn error-tab" data-tab="errors">⚠️ Errors</button>';

    html += '</div>';
    html += '<div class="tabs-content">';

    // Findings tab
    if (hasFindings) {
        html += '<div class="tab-pane active" id="findings">';
        if (data.findings.summary) {
            html += `<div class="section-summary"><strong>Summary:</strong> ${marked.parse(data.findings.summary)}</div>`;
        }
        if (data.findings.details) {
            html += `<div class="section-details">${marked.parse(data.findings.details)}</div>`;
        }
        if (data.findings.tool_outputs && Array.isArray(data.findings.tool_outputs) && data.findings.tool_outputs.length > 0) {
            html += `<div class="tool-outputs-container">`;
            html += `<h4 class="tool-outputs-title">Tool Outputs (${data.findings.tool_outputs.length})</h4>`;
            data.findings.tool_outputs.forEach((toolOutput, index) => {
                const toolName = typeof toolOutput.tool_name === 'string' ? toolOutput.tool_name : String(toolOutput.tool_name || 'Unknown');
                const command = typeof toolOutput.command === 'string' ? toolOutput.command : String(toolOutput.command || '');
                const output = typeof toolOutput.output === 'string' ? toolOutput.output : String(toolOutput.output || '');

                html += `<div class="tool-output-item">`;
                html += `<button class="tool-output-toggle" onclick="this.classList.toggle('collapsed'); this.nextElementSibling.classList.toggle('collapsed');">`;
                html += `<span class="toggle-icon">&#x25B6</span>`;
                html += `<div class="tool-output-header-content">`;
                html += `<strong>${index + 1}. ${escapeHtml(toolName)}</strong>`;
                html += `<code class="tool-command">${escapeHtml(command)}</code>`;
                html += `</div>`;
                html += `</button>`;
                html += `<pre class="tool-output-body collapsed">${escapeHtml(output)}</pre>`;
                html += `</div>`;
            });
            html += `</div>`;
        }
        if (data.findings.skill_used) {
            html += `<div class="skill-used-container">`;
            html += `<h4 class="skill-used-title">🎯 Skill Used</h4>`;
            html += `<div class="skill-used-badge">${escapeHtml(data.findings.skill_used)}</div>`;
            html += `</div>`;
        }
        if (data.findings.knowledge_searched) {
            const searchedText = data.findings.knowledge_searched ? 'Yes' : 'No';
            const searchedClass = data.findings.knowledge_searched ? 'knowledge-searched-yes' : 'knowledge-searched-no';
            html += `<div class="knowledge-searched-container">`;
            html += `<h4 class="knowledge-searched-title">📚 External Knowledge Searched</h4>`;
            html += `<div class="knowledge-searched-badge ${searchedClass}">${searchedText}</div>`;
            html += `</div>`;
        }
        if (data.findings.additional_output) {
            html += `<div class="additional-output"><strong>Additional Output:</strong><div class="additional-content">${marked.parse(data.findings.additional_output)}</div></div>`;
        }
        html += '</div>';
    }

    // Decisions tab
    if (hasDecisions) {
        html += `<div class="tab-pane ${!hasFindings ? 'active' : ''}" id="decisions">`;
        if (data.decisions.approach) {
            html += `<div class="decision-approach"><strong>Approach:</strong> ${escapeHtml(data.decisions.approach)}</div>`;
        }
        if (data.decisions.tools_used && data.decisions.tools_used.length > 0) {
            html += `<div class="tools-used"><strong>Tools Used:</strong> ${data.decisions.tools_used.join(', ')}</div>`;
        }
        if (data.decisions.skills_loaded && data.decisions.skills_loaded.length > 0) {
            html += `<div class="skills-loaded"><strong>Skills Loaded:</strong> ${data.decisions.skills_loaded.join(', ')}</div>`;
        }
        if (data.decisions.rationale) {
            html += `<div class="rationale"><strong>Rationale:</strong> ${marked.parse(data.decisions.rationale)}</div>`;
        }
        if (data.decisions.checklist && data.decisions.checklist.length > 0) {
            html += '<div class="checklist"><strong>Checklist:</strong><ul>';
            data.decisions.checklist.forEach(item => {
                html += `<li>${escapeHtml(item)}</li>`;
            });
            html += '</ul></div>';
        }
        if (data.decisions.additional_output) {
            html += `<div class="additional-output"><strong>Additional Output:</strong><div class="additional-content">${marked.parse(data.decisions.additional_output)}</div></div>`;
        }
        html += '</div>';
    }

    // Next Actions tab
    if (hasActions) {
        html += `<div class="tab-pane ${!hasFindings && !hasDecisions ? 'active' : ''}" id="actions">`;
        html += '<ol class="action-steps">';
        data.next_actions.steps.forEach(step => {
            html += `<li>${escapeHtml(step)}</li>`;
        });
        html += '</ol>';
        if (data.next_actions.additional_output) {
            html += `<div class="additional-output"><strong>Additional Output:</strong><div class="additional-content">${marked.parse(data.next_actions.additional_output)}</div></div>`;
        }
        html += '</div>';
    }

    // Errors tab
    if (hasErrors) {
        html += '<div class="tab-pane" id="errors">';
        html += '<ul class="error-list">';
        data.errors.forEach(error => {
            html += `<li class="error-item">${escapeHtml(error)}</li>`;
        });
        html += '</ul></div>';
    }

    html += '</div></div>';

    // Clear existing content before setting new HTML to prevent duplication
    contentDiv.innerHTML = '';
    console.log('[renderStructuredMessage] Setting HTML, length:', html.length);
    console.log('[renderStructuredMessage] HTML preview:', html.substring(0, 200));
    contentDiv.innerHTML = html;
    console.log('[renderStructuredMessage] HTML set successfully, contentDiv.innerHTML length:', contentDiv.innerHTML.length);
    scrollToBottom();
}

function switchStructuredTab(container, tabName) {
    console.log('switchStructuredTab called with container:', container, 'tabName:', tabName);

    const allBtns = container.querySelectorAll('.tab-btn');
    const allPanes = container.querySelectorAll('.tab-pane');

    console.log('Found buttons:', allBtns.length, 'Found panes:', allPanes.length);

    allBtns.forEach(btn => btn.classList.remove('active'));
    allPanes.forEach(pane => pane.classList.remove('active'));

    const targetBtn = container.querySelector(`[data-tab="${tabName}"]`);
    const targetPane = container.querySelector(`#${tabName}`);

    console.log('Target button:', targetBtn);
    console.log('Target pane:', targetPane);

    if (targetBtn) {
        targetBtn.classList.add('active');
        console.log('Added active to button');
    }
    if (targetPane) {
        targetPane.classList.add('active');
        console.log('Added active to pane');
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function parseSections(text, skills = null, contentDiv = null) {
    console.log('parseSections input length:', text.length);
    console.log('parseSections text preview:', text.substring(0, 200));
    // Regex to find the sections with markdown headers
    // Match based on header text only, ignore emojis
    // Findings: Stop at next ### Decisions or ### *Actions header
    // Decisions: Stop at next ### *Actions header
    // Actions: Last section, capture everything until end
    const findingsRegex = /###?\s*(?:📊\s*)?Findings\s*[\r\n]+([\s\S]*?)(?=###\s*(?:🧠\s*)?Decisions|###\s*(?:⚡\s*)?\S*\s*Actions|$)/i;
    const decisionsRegex = /###?\s*(?:🧠\s*)?Decisions\s*[\r\n]+([\s\S]*?)(?=###\s*(?:⚡\s*)?\S*\s*Actions|$)/i;
    const actionsRegex = /###?\s*(?:⚡\s*)?\S*\s*Actions\s*[\r\n]+([\s\S]*?)$/i;

    // Fallback for old format
    const oldFindingsRegex = /\*\*Section Findings:\*\*([\s\S]*?)(?=\*\*Section Decisions:\*\*|$)/;
    const oldDecisionsRegex = /\*\*Section Decisions:\*\*([\s\S]*?)(?=\*\*Section Suggested actions:\*\*|$)/;
    const oldActionsRegex = /\*\*Section Suggested actions:\*\*([\s\S]*?)$/;

    let findingsMatch = text.match(findingsRegex);
    let decisionsMatch = text.match(decisionsRegex);
    let actionsMatch = text.match(actionsRegex);

    console.log('Matches:', { findings: !!findingsMatch, decisions: !!decisionsMatch, actions: !!actionsMatch });
    console.log('Text preview:', text.substring(0, 500));

    // Try old format if new one fails for all
    if (!findingsMatch && !decisionsMatch && !actionsMatch) {
        findingsMatch = text.match(oldFindingsRegex);
        decisionsMatch = text.match(oldDecisionsRegex);
        actionsMatch = text.match(oldActionsRegex);
    }

    // If we have an existing contentDiv with tabs, update them incrementally
    if (contentDiv) {
        const existingTabs = contentDiv.querySelector('.section-tabs');
        if (existingTabs && (findingsMatch || decisionsMatch || actionsMatch)) {
            updateTabsContent(existingTabs, text, findingsMatch, decisionsMatch, actionsMatch, skills);
            return; // Don't return HTML, just update in place
        }

        // If tabs don't exist yet but we've detected section headers, create the structure early
        if (!existingTabs) {
            const hasSectionHeader = text.match(/###?\s*(?:📊\s*)?Findings|###?\s*(?:🧠\s*)?Decisions|###?\s*(?:⚡\s*)?\S*\s*Actions/i);
            if (hasSectionHeader) {
                // Create initial tab structure even if content isn't complete
                const initialHtml = createInitialTabStructure(text, findingsMatch, decisionsMatch, actionsMatch, skills);
                contentDiv.innerHTML = initialHtml;
                return; // Tab structure created, future updates will be incremental
            }
        }
    }
    if (findingsMatch || decisionsMatch || actionsMatch) {
        let html = '';

        // Find intro text (before first section)
        const firstIndex = Math.min(
            findingsMatch ? findingsMatch.index : Infinity,
            decisionsMatch ? decisionsMatch.index : Infinity,
            actionsMatch ? actionsMatch.index : Infinity
        );

        if (firstIndex > 0 && firstIndex !== Infinity) {
            const intro = text.substring(0, firstIndex);
            if (intro.trim()) {
                html += `<div class="section section-intro">${marked.parse(intro)}</div>`;
            }
        }

        // Create tabbed interface
        const tabId = `tabs-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;

        // Create skill badge HTML if skills are provided
        let skillBadgeHtml = '';
        if (skills && skills.length > 0) {
            const badgeText = skills.length === 1 ? '🎯 Skill' : `🎯 ${skills.length} Skills`;
            const badgeTitle = skills.join(', ');
            skillBadgeHtml = `<span class="skill-indicator" title="${badgeTitle}">${badgeText}</span>`;
        }

        html += `<div class="section-tabs" data-tab-id="${tabId}">`;

        // Tab navigation
        html += `<div class="tab-nav">`;
        if (findingsMatch) {
            html += `<button class="tab-button active" data-tab="findings" onclick="switchTab('${tabId}', 'findings')">
                🔍 Findings ${skillBadgeHtml}
            </button>`;
        }
        if (decisionsMatch) {
            html += `<button class="tab-button" data-tab="decisions" onclick="switchTab('${tabId}', 'decisions')">
                🧠 Decisions
            </button>`;
        }
        if (actionsMatch) {
            html += `<button class="tab-button" data-tab="actions" onclick="switchTab('${tabId}', 'actions')">
                🚀 Next Actions
            </button>`;
        }
        html += `</div>`;

        // Tab panels
        html += `<div class="tab-content">`;

        if (findingsMatch) {
            html += `<div class="tab-panel active" data-panel="findings">
                ${marked.parse(findingsMatch[1].trim())}
            </div>`;
        }

        if (decisionsMatch) {
            const decisionsContent = renderDecisionsSection(decisionsMatch[1].trim());
            html += `<div class="tab-panel" data-panel="decisions">
                ${decisionsContent}
            </div>`;
        }

        if (actionsMatch) {
            html += `<div class="tab-panel" data-panel="actions">
                ${marked.parse(actionsMatch[1].trim())}
            </div>`;
        }

        html += `</div>`; // Close tab-content
        html += `</div>`; // Close section-tabs

        console.log('Returning HTML length:', html.length);
        return html;
    } else {
        console.log('Returning marked.parse(text)');
        // Parse markdown content directly - marked will handle tables, lists, etc.
        return marked.parse(text);
    }
}

/**
 * Make code blocks collapsible for better UX
 * Wraps large code blocks (>10 lines or >500 chars) in collapsible containers
 */
function makeCodeBlocksCollapsible(element) {
    const codeBlocks = element.querySelectorAll('pre > code');

    codeBlocks.forEach((codeBlock, index) => {
        const pre = codeBlock.parentElement;
        const codeText = codeBlock.textContent || '';
        const lineCount = codeText.split('\n').length;
        const charCount = codeText.length;

        // Only make collapsible if it's reasonably large
        if (lineCount > 10 || charCount > 500) {
            // Determine if this looks like tool output
            const isToolOutput = codeText.includes('Name:') ||
                codeText.includes('Status:') ||
                codeText.includes('Namespace:') ||
                codeText.includes('"timestamp"') ||
                pre.previousElementSibling?.textContent?.includes('Tool Output');

            const title = isToolOutput ? 'Tool Output' : 'Code Block';
            const isLarge = lineCount > 50 || charCount > 2000;

            // Create wrapper
            const wrapper = document.createElement('div');
            wrapper.className = 'collapsible-wrapper' + (isLarge ? ' large-output' : '');

            // Create header
            const header = document.createElement('div');
            header.className = 'collapsible-header';
            header.innerHTML = `
                <div class="collapsible-header-left">
                    <span class="collapsible-toggle"></span>
                    <span class="collapsible-title">${title} ${index + 1}</span>
                </div>
                <span class="collapsible-size">${lineCount} lines, ${formatBytes(charCount)}</span>
            `;

            // Create content container
            const content = document.createElement('div');
            content.className = 'collapsible-content';

            // Move pre into content
            pre.parentElement.insertBefore(wrapper, pre);
            content.appendChild(pre);
            wrapper.appendChild(header);
            wrapper.appendChild(content);

            // Add click handler
            header.addEventListener('click', () => {
                wrapper.classList.toggle('collapsed');
            });

            // Start collapsed if very large
            if (isLarge) {
                wrapper.classList.add('collapsed');
            }
        }
    });
}

/**
 * Format bytes into human-readable string
 */
function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Parse Decisions section into structured format
 * Expected format:
 * - **Approach**: ...
 * - **Tools Used**: ...
 * - **Skills Loaded**: ...
 * - **Rationale**: ...
 * - **Checklist**: ... (optional)
 */
function parseDecisionsSection(text) {
    const decisions = {
        approach: null,
        tools_used: [],
        skills_loaded: [],
        rationale: null,
        checklist: []
    };

    // Extract each field - handle bulleted format (- **Field**: content)
    const approachMatch = text.match(/[-\*•]\s*\*\*Approach\*\*:\s*(.*?)(?=\n[-\*•]\s*\*\*(?:Tools?\s+Used|Skills?\s+Loaded|Rationale|Checklist)|$)/is);
    if (approachMatch) decisions.approach = approachMatch[1].trim();

    const toolsMatch = text.match(/[-\*•]\s*\*\*Tools?\s+Used\*\*:\s*(.*?)(?=\n[-\*•]\s*\*\*(?:Skills?\s+Loaded|Rationale|Checklist)|$)/is);
    if (toolsMatch) {
        const toolsText = toolsMatch[1].trim();
        // Parse tools - can be comma-separated, in backticks, or bulleted
        decisions.tools_used = toolsText
            .split(/[,\n]/)
            .map(t => t.replace(/^[\s\-\*•]+/, '').replace(/`/g, '').trim())
            .filter(t => t.length > 0 && t !== '-' && t.toLowerCase() !== 'none');
    }

    const skillsMatch = text.match(/[-\*•]\s*\*\*Skills?\s+Loaded\*\*:\s*(.*?)(?=\n[-\*•]\s*\*\*(?:Rationale|Checklist)|$)/is);
    if (skillsMatch) {
        const skillsText = skillsMatch[1].trim();
        decisions.skills_loaded = skillsText
            .split(/[,\n]/)
            .map(s => s.replace(/^[\s\-\*•]+/, '').trim())
            .filter(s => {
                if (s.length === 0) return false;
                const cleaned = s.trim().toLowerCase();
                return cleaned !== '' && cleaned !== 'none';
            });
    }

    const rationaleMatch = text.match(/[-\*•]\s*\*\*Rationale\*\*:\s*(.*?)(?=\n[-\*•]\s*\*\*Checklist|$)/is);
    if (rationaleMatch) decisions.rationale = rationaleMatch[1].trim();

    // Checklist has sub-bullets, so capture everything after the header
    const checklistMatch = text.match(/[-\*•]\s*\*\*Checklist\*\*:\s*([\s\S]*?)$/i);
    if (checklistMatch) {
        const checklistText = checklistMatch[1].trim();
        decisions.checklist = checklistText
            .split('\n')
            .map(line => line.replace(/^[\s\-\*•]+/, '').trim())
            .filter(line => line.length > 0);
    }

    return decisions;
}

/**
 * Render Decisions section as formatted markdown
 */
function renderDecisionsSection(decisionsText) {
    return marked.parse(decisionsText);
}

/**
 * Extract skill usage from agent response text
 * Handles multiple formats:
 * 1. **Skills Loaded:** \n - skill
 * 2. - **Skills Loaded:** \n `skill`  
 * 3. - **Skills Loaded**: skill (inline)
 */
function extractSkillUsage(text) {
    console.log('[Skill Debug] Input text preview:', text.substring(0, 500));

    // Try all possible patterns for Skills Loaded
    const patterns = [
        // Block format: **Skills Loaded:** followed by bulleted items
        /\*\*Skills?\s+Loaded\*\*:\s*\n((?:\s*[-\*•]\s*.+(?:\n|$))*)/i,
        // Inline with bullet: - **Skills Loaded:** `skill`
        /[-\*•]\s*\*\*Skills?\s+Loaded\*\*:\s*([^\n]+)/i,
        // Bulleted header with content on next line: - **Skills Loaded:** \n `skill`
        /[-\*•]\s*\*\*Skills?\s+Loaded\*\*:\s*\n\s*([^\n]+?)(?=\n[-\*•]\s*\*\*|$)/i,
        // Without bullet: **Skills Loaded:** content
        /\*\*Skills?\s+Loaded\*\*:\s*([^\n]+)/i,
    ];

    for (let i = 0; i < patterns.length; i++) {
        const match = text.match(patterns[i]);
        console.log(`[Skill Debug] Pattern ${i}:`, patterns[i], 'Match:', !!match);

        if (match) {
            let skillsText = match[1].trim();
            console.log(`[Skill Debug] Raw skills text:`, skillsText);

            let skills;
            if (skillsText.includes('\n')) {
                // Multi-line (bulleted format)
                skills = skillsText
                    .split('\n')
                    .map(line => line.replace(/^[\s\-\*•]+/, '').replace(/[`]/g, '').trim())
                    .filter(skill => skill.length > 0);
            } else {
                // Single line
                skills = skillsText
                    .replace(/[`]/g, '')
                    .split(',')
                    .map(s => s.trim())
                    .filter(skill => skill.length > 0);
            }

            // Filter out 'none'
            skills = skills.filter(skill => skill.toLowerCase() !== 'none');

            console.log(`[Skill Debug] Final skills:`, skills);

            if (skills.length > 0) return skills;
        }
    }

    console.log('[Skill Debug] No skills found');
    return null;
}

function renderTimeline(timelineData, container) {
    console.log('[renderTimeline] Called with timelineData:', timelineData);
    console.log('[renderTimeline] Container:', container);

    // Handle Timeline model format (with 'entries' field) or legacy array format
    let entries = timelineData;
    if (timelineData && typeof timelineData === 'object' && !Array.isArray(timelineData) && timelineData.entries) {
        console.log('[renderTimeline] Using entries field from timelineData');
        entries = timelineData.entries;
    }

    console.log('[renderTimeline] entries:', entries);
    console.log('[renderTimeline] Is Array?', Array.isArray(entries));
    console.log('[renderTimeline] Length:', entries ? entries.length : 'N/A');

    if (!Array.isArray(entries) || entries.length === 0) {
        console.log('[renderTimeline] No entries found, showing empty state');
        container.innerHTML = '<div class="loading-state">No timeline events found.</div>';
        return;
    }

    let html = '';
    entries.forEach((event, index) => {
        console.log(`[renderTimeline] Processing event ${index}:`, event);

        // Support both 'entry_type' (TimelineEntry model) and 'type' (legacy)
        const eventType = event.entry_type || event.type || 'INFO';
        const typeClass = `type-${eventType.toLowerCase()}`;
        // Support both 'content' (TimelineEntry model) and 'description' (legacy)
        const content = event.content || event.description || '';

        console.log(`[renderTimeline] Event ${index} - Type: ${eventType}, Content: ${content.substring(0, 50)}`);

        html += `
            <div class="timeline-item ${typeClass}">
                <div class="timeline-marker"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-type">${eventType}</span>
                        <span class="timeline-timestamp">${event.timestamp || ''}</span>
                    </div>
                    <div class="timeline-body">${marked.parse(content)}</div>
                </div>
            </div>
        `;
    });

    console.log('[renderTimeline] Generated HTML length:', html.length);
    console.log('[renderTimeline] HTML preview:', html.substring(0, 200));
    console.log('[renderTimeline] Setting container innerHTML');
    container.innerHTML = html;
    console.log('[renderTimeline] Done! Container innerHTML length:', container.innerHTML.length);
}

async function fetchSessionMetadata(sessionId) {
    try {
        const response = await fetch(`/sessions/${sessionId}?unsafe=true&ts=${Date.now()}`);
        const session = await response.json();
        updateSessionSidebar(session);
    } catch (e) {
        console.error("Failed to update session metadata", e);
    }
}

function updateSessionSidebar(session) {
    if (infoSessionName) infoSessionName.textContent = session.name || "-";
    if (infoSessionId) infoSessionId.textContent = session.id;
    if (infoSessionCost && session.total_cost !== undefined) {
        const costStr = `€${parseFloat(session.total_cost).toFixed(6)}`;
        console.log(`Updating session cost to: ${costStr}`);
        infoSessionCost.textContent = costStr;
    } else if (infoSessionCost) {
        infoSessionCost.textContent = "€0.000000";
    }

    // Unsafe Mode Handling
    const isUnsafe = session.unsafe === true || session.unsafe === "True"; // Handle bool or string from API
    if (isUnsafe) {
        document.body.classList.add('unsafe-mode');
        if (infoSessionStatus) infoSessionStatus.textContent = "Unsafe";
    } else {
        document.body.classList.remove('unsafe-mode');
        if (infoSessionStatus) infoSessionStatus.textContent = session.status || "Active";
    }
}

function scrollToBottom() {

    chatContainer.scrollTop = chatContainer.scrollHeight;
}

/**
 * Display a collapsible summary of function calls
 */

/**
 * Switch between tabs in a tabbed section
 */
function switchTab(tabId, tabName) {
    const container = document.querySelector(`[data-tab-id="${tabId}"]`);
    if (!container) return;

    // Update tab buttons
    const buttons = container.querySelectorAll('.tab-button');
    buttons.forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Update tab panels
    const panels = container.querySelectorAll('.tab-panel');
    panels.forEach(panel => {
        if (panel.dataset.panel === tabName) {
            panel.classList.add('active');
        } else {
            panel.classList.remove('active');
        }
    });
}

/**
 * Create initial tab structure when section headers are first detected
 */
function createInitialTabStructure(text, findingsMatch, decisionsMatch, actionsMatch, skills) {
    let html = '';

    // Find intro text (before first section)
    const firstIndex = Math.min(
        findingsMatch ? findingsMatch.index : Infinity,
        decisionsMatch ? decisionsMatch.index : Infinity,
        actionsMatch ? actionsMatch.index : Infinity,
        text.search(/###?\s*(?:📊\s*)?Findings|###?\s*(?:🧠\s*)?Decisions|###?\s*(?:⚡\s*)?\S*\s*Actions/i)
    );

    if (firstIndex > 0 && firstIndex !== Infinity) {
        const intro = text.substring(0, firstIndex);
        if (intro.trim()) {
            html += `<div class="section section-intro">${marked.parse(intro)}</div>`;
        }
    }

    // Detect which sections have headers (even if content isn't complete)
    const hasFindings = text.match(/###?\s*(?:📊\s*)?Findings/i);
    const hasDecisions = text.match(/###?\s*(?:🧠\s*)?Decisions/i);
    const hasActions = text.match(/###?\s*(?:⚡\s*)?\S*\s*Actions/i);

    const tabId = `tabs-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;

    // Create skill badge HTML if skills are provided
    let skillBadgeHtml = '';
    if (skills && skills.length > 0) {
        const badgeText = skills.length === 1 ? '🎯 Skill' : `🎯 ${skills.length} Skills`;
        const badgeTitle = skills.join(', ');
        skillBadgeHtml = `<span class="skill-indicator" title="${badgeTitle}">${badgeText}</span>`;
    }

    html += `<div class="section-tabs" data-tab-id="${tabId}">`;

    // Tab navigation - create buttons for detected headers
    html += `<div class="tab-nav">`;
    if (hasFindings) {
        html += `<button class="tab-button active" data-tab="findings" onclick="switchTab('${tabId}', 'findings')">
            🔍 Findings ${skillBadgeHtml}
        </button>`;
    }
    if (hasDecisions) {
        html += `<button class="tab-button${!hasFindings ? ' active' : ''}" data-tab="decisions" onclick="switchTab('${tabId}', 'decisions')">
            🧠 Decisions
        </button>`;
    }
    if (hasActions) {
        html += `<button class="tab-button${!hasFindings && !hasDecisions ? ' active' : ''}" data-tab="actions" onclick="switchTab('${tabId}', 'actions')">
            🚀 Next Actions
        </button>`;
    }
    html += `</div>`;

    // Tab panels - create empty panels for now
    html += `<div class="tab-content">`;

    if (hasFindings) {
        const content = findingsMatch ? marked.parse(findingsMatch[1].trim()) : '<div class="loading-state">Loading...</div>';
        html += `<div class="tab-panel active" data-panel="findings">${content}</div>`;
    }

    if (hasDecisions) {
        const content = decisionsMatch ? renderDecisionsSection(decisionsMatch[1].trim()) : '<div class="loading-state">Loading...</div>';
        html += `<div class="tab-panel${!hasFindings ? ' active' : ''}" data-panel="decisions">${content}</div>`;
    }

    if (hasActions) {
        const content = actionsMatch ? marked.parse(actionsMatch[1].trim()) : '<div class="loading-state">Loading...</div>';
        html += `<div class="tab-panel${!hasFindings && !hasDecisions ? ' active' : ''}" data-panel="actions">${content}</div>`;
    }

    html += `</div>`; // Close tab-content
    html += `</div>`; // Close section-tabs

    return html;
}

/**
 * Update existing tabs content incrementally without rebuilding structure
 */
function updateTabsContent(tabsContainer, fullText, findingsMatch, decisionsMatch, actionsMatch, skills) {
    const tabNav = tabsContainer.querySelector('.tab-nav');
    const tabContent = tabsContainer.querySelector('.tab-content');
    const tabId = tabsContainer.dataset.tabId;

    // Update skill badge if needed
    if (skills && skills.length > 0) {
        const findingsButton = tabsContainer.querySelector('[data-tab="findings"]');
        if (findingsButton) {
            let existingBadge = findingsButton.querySelector('.skill-indicator');
            const badgeText = skills.length === 1 ? '🎯 Skill' : `🎯 ${skills.length} Skills`;
            const badgeTitle = skills.join(', ');

            if (!existingBadge) {
                existingBadge = document.createElement('span');
                existingBadge.className = 'skill-indicator';
                findingsButton.appendChild(existingBadge);
            }
            existingBadge.textContent = badgeText;
            existingBadge.title = badgeTitle;
        }
    }

    // Update intro if it exists
    const firstIndex = Math.min(
        findingsMatch ? findingsMatch.index : Infinity,
        decisionsMatch ? decisionsMatch.index : Infinity,
        actionsMatch ? actionsMatch.index : Infinity
    );

    if (firstIndex > 0 && firstIndex !== Infinity) {
        const intro = fullText.substring(0, firstIndex);
        if (intro.trim()) {
            let introDiv = tabsContainer.previousElementSibling;
            if (!introDiv || !introDiv.classList.contains('section-intro')) {
                introDiv = document.createElement('div');
                introDiv.className = 'section section-intro';
                tabsContainer.parentElement.insertBefore(introDiv, tabsContainer);
            }
            introDiv.innerHTML = marked.parse(intro);
        }
    }

    // Helper to add missing tab button
    function ensureTabButton(tabName, label, isFirst) {
        let button = tabNav.querySelector(`[data-tab="${tabName}"]`);
        if (!button) {
            button = document.createElement('button');
            button.className = 'tab-button' + (isFirst ? ' active' : '');
            button.dataset.tab = tabName;
            button.onclick = () => switchTab(tabId, tabName);
            button.innerHTML = label;
            tabNav.appendChild(button);
        }
        return button;
    }

    // Helper to add missing tab panel
    function ensureTabPanel(tabName, isFirst) {
        let panel = tabContent.querySelector(`[data-panel="${tabName}"]`);
        if (!panel) {
            panel = document.createElement('div');
            panel.className = 'tab-panel' + (isFirst ? ' active' : '');
            panel.dataset.panel = tabName;
            panel.innerHTML = '<div class="loading-state">Loading...</div>';
            tabContent.appendChild(panel);
        }
        return panel;
    }

    // Check which tabs currently exist
    const hasFindings = tabNav.querySelector('[data-tab="findings"]');
    const hasDecisions = tabNav.querySelector('[data-tab="decisions"]');
    const hasActions = tabNav.querySelector('[data-tab="actions"]');

    // Add missing tabs as they're detected
    if (findingsMatch) {
        const isFirst = !hasFindings && !hasDecisions && !hasActions;
        ensureTabButton('findings', '🔍 Findings', isFirst);
        const panel = ensureTabPanel('findings', isFirst);
        panel.innerHTML = marked.parse(findingsMatch[1].trim());
        makeCodeBlocksCollapsible(panel);
    }

    if (decisionsMatch) {
        const isFirst = !hasFindings && !hasDecisions && !hasActions;
        ensureTabButton('decisions', '🧠 Decisions', isFirst);
        const panel = ensureTabPanel('decisions', isFirst);
        const decisionsContent = renderDecisionsSection(decisionsMatch[1].trim());
        panel.innerHTML = decisionsContent;
        makeCodeBlocksCollapsible(panel);
    }

    if (actionsMatch) {
        const isFirst = !hasFindings && !hasDecisions && !hasActions;
        ensureTabButton('actions', '🚀 Next Actions', isFirst);
        const panel = ensureTabPanel('actions', isFirst);
        panel.innerHTML = marked.parse(actionsMatch[1].trim());
        makeCodeBlocksCollapsible(panel);
    }
}

// ===================================
// Command Autocomplete Functions
// ===================================

async function loadCommands() {
    try {
        const response = await fetch('/commands');
        if (response.ok) {
            availableCommands = await response.json();
        }
    } catch (error) {
        console.error('Failed to load commands:', error);
        availableCommands = [];
    }
}

function createCommandCompletionElement() {
    const existingDropdown = document.getElementById('command-completion-dropdown');
    if (existingDropdown) {
        return existingDropdown;
    }

    const dropdown = document.createElement('div');
    dropdown.id = 'command-completion-dropdown';
    dropdown.className = 'command-completion-dropdown';
    document.body.appendChild(dropdown);
    return dropdown;
}

function showCommandCompletion(commandPart) {
    if (availableCommands.length === 0) {
        return; // Commands not loaded yet
    }

    // Filter commands based on typed text
    const filtered = availableCommands.filter(cmd =>
        cmd.name.toLowerCase().startsWith(commandPart)
    );

    if (filtered.length === 0) {
        hideCommandCompletion();
        return;
    }

    const dropdown = createCommandCompletionElement();
    dropdown.innerHTML = '';

    filtered.forEach((cmd, index) => {
        const item = document.createElement('div');
        item.className = 'command-completion-item';
        item.dataset.index = index;
        item.dataset.commandName = cmd.name;

        const nameSpan = document.createElement('span');
        nameSpan.className = 'command-name';
        nameSpan.textContent = `/${cmd.name}`;

        const descSpan = document.createElement('span');
        descSpan.className = 'command-description';
        descSpan.textContent = cmd.description;

        item.appendChild(nameSpan);
        item.appendChild(descSpan);

        // Click handler
        item.addEventListener('click', () => {
            selectedCommandIndex = index;
            selectCommand();
        });

        dropdown.appendChild(item);
    });

    // Position the dropdown relative to the textarea
    positionCommandCompletion();

    commandCompletionVisible = true;
    selectedCommandIndex = -1;
    dropdown.style.display = 'block';
}

function hideCommandCompletion() {
    const dropdown = document.getElementById('command-completion-dropdown');
    if (dropdown) {
        dropdown.style.display = 'none';
    }
    commandCompletionVisible = false;
    selectedCommandIndex = -1;
}

function navigateCommandCompletion(direction) {
    const dropdown = document.getElementById('command-completion-dropdown');
    if (!dropdown) return;

    const items = dropdown.querySelectorAll('.command-completion-item');
    if (items.length === 0) return;

    // Remove previous selection
    items.forEach(item => item.classList.remove('selected'));

    // Update index
    if (direction === 'down') {
        selectedCommandIndex = (selectedCommandIndex + 1) % items.length;
    } else if (direction === 'up') {
        selectedCommandIndex = selectedCommandIndex <= 0 ? items.length - 1 : selectedCommandIndex - 1;
    }

    // Add selection to new item
    items[selectedCommandIndex].classList.add('selected');
    items[selectedCommandIndex].scrollIntoView({ block: 'nearest' });
}

function selectCommand() {
    const dropdown = document.getElementById('command-completion-dropdown');
    if (!dropdown) return;

    const items = dropdown.querySelectorAll('.command-completion-item');
    if (selectedCommandIndex < 0 || selectedCommandIndex >= items.length) return;

    const selectedItem = items[selectedCommandIndex];
    const commandName = selectedItem.dataset.commandName;

    // Replace input with selected command
    messageInput.value = `/${commandName} `;
    messageInput.focus();

    // Trigger input event to update send button state
    messageInput.dispatchEvent(new Event('input'));

    hideCommandCompletion();
}

function positionCommandCompletion() {
    const dropdown = document.getElementById('command-completion-dropdown');
    if (!dropdown) return;

    const inputRect = messageInput.getBoundingClientRect();

    // Position above the input
    dropdown.style.left = `${inputRect.left}px`;
    dropdown.style.bottom = `${window.innerHeight - inputRect.top + 10}px`;
    dropdown.style.width = `${inputRect.width}px`;
}
