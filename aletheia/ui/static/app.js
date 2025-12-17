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
    // Only append unsafe=true if we KNOW it's unsafe? 
    // Actually, backend needs either password OR unsafe=true.
    // We should probably store unsafe status in sessionPasswords or separate map.
    return params;
};

// Sidebar Elements
const infoSidebar = document.querySelector('.info-sidebar');
const toggleInfoBtn = document.getElementById('toggle-info-btn');
const chatWrapper = document.querySelector('.chat-wrapper');

console.log('Sidebar Elements:', { infoSessionName, infoSessionId, infoSessionCost, infoSessionStatus });


// Initialization
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initSidebar();
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

        // Add user message
        appendMessage(message, 'user');
        messageInput.value = '';
        messageInput.style.height = 'auto';
        sendBtn.disabled = true;

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
            appendMessage(`Error: ${error.message}`, 'bot'); // Show error as bot message
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

        timelineContainer.innerHTML = '<div class="loading-state">Generating timeline...</div>';

        try {
            const params = getAuthParams(currentSessionId);
            const response = await fetch(`/sessions/${currentSessionId}/timeline?${params.toString()}`);
            if (!response.ok) throw new Error('Unauthorized or failed');
            const data = await response.json();
            renderTimeline(data.timeline, timelineContainer);
        } catch (e) {
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

    currentSessionId = sessionId;

    // Update UI
    document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
    // Re-render list to update active state (lazy way)
    fetchSessions(); // Or just find the element and add class

    // Enable inputs
    messageInput.disabled = false;
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
            // Update session info (cost, etc) after interaction
            console.log('Stream finished (done event received). Refreshing session metadata...');
            fetchSessionMetadata(currentSessionId);

        } else if (data.type === 'error') {
            stopThinking();
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
    if (infoSessionName) infoSessionName.textContent = session.name || session.id;
    if (infoSessionId) infoSessionId.textContent = session.id;
    if (infoSessionCost) infoSessionCost.textContent = `€${(session.total_cost || 0).toFixed(6)}`;
    if (infoSessionStatus) infoSessionStatus.textContent = session.status;
}


function showThinking() {
    // Create a temporary thinking message
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot thinking';
    msgDiv.id = 'thinking-bubble';

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = '';
    avatar.style.backgroundImage = 'url(/static/icons/owl.png)';

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
    const contentDiv = lastMsg.querySelector('.message-content');

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

        // Update content with skills
        contentDiv.innerHTML = parseSections(displayContent, skills);
        makeCodeBlocksCollapsible(contentDiv);
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

            contentDiv.innerHTML = parseSections(displayContent, skills);
            makeCodeBlocksCollapsible(contentDiv);

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

function parseSections(text, skills = null) {
    console.log('parseSections input length:', text.length);
    console.log('parseSections text preview:', text.substring(0, 200));
    // Regex to find the sections with markdown headers
    // Support both new format (### 📊 Findings) and legacy format (## Findings)
    // More flexible - handle any whitespace between emoji and text
    const findingsRegex = /###?\s*(?:📊\s*)?\s*Findings\s*[\r\n]+([\s\S]*?)(?=###?\s*(?:🧠\s*)?\s*Decisions|###?\s*(?:⚡\s*)?\s*(?:Next Actions|Suggested Actions)|$)/i;
    const decisionsRegex = /###?\s*(?:🧠\s*)?\s*Decisions\s*[\r\n]+([\s\S]*?)(?=###?\s*(?:⚡\s*)?\s*(?:Next Actions|Suggested Actions)|###?\s*(?:📊\s*)?\s*Findings|$)/i;
    const actionsRegex = /###?\s*(?:⚡\s*)?\s*(?:Next Actions|Suggested Actions)\s*[\r\n]+([\s\S]*?)(?=###?\s*\w+|$)/i;

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

        if (findingsMatch) {
            // Create skill badge HTML if skills are provided
            let skillBadgeHtml = '';
            if (skills && skills.length > 0) {
                const badgeText = skills.length === 1 ? '🎯 Skill' : `🎯 ${skills.length} Skills`;
                const badgeTitle = skills.join(', ');
                skillBadgeHtml = `<span class="skill-indicator" title="${badgeTitle}">${badgeText}</span>`;
            }

            html += `<div class="section section-findings">
                <div class="section-header">
                    <span>🔍 Findings</span>
                    ${skillBadgeHtml}
                </div>
                <div class="section-body">${marked.parse(findingsMatch[1].trim())}</div>
            </div>`;
        }

        if (decisionsMatch) {
            const decisionsContent = renderDecisionsSection(decisionsMatch[1].trim());
            html += `<div class="section section-decisions">
                <div class="section-header">🧠 Decisions</div>
                <div class="section-body">${decisionsContent}</div>
            </div>`;
        }

        if (actionsMatch) {
            html += `<div class="section section-actions">
                <div class="section-header">🚀 Suggested Actions</div>
                <div class="section-body">${marked.parse(actionsMatch[1].trim())}</div>
            </div>`;
        }

        console.log('Returning HTML length:', html.length);
        return html;
    } else {
        console.log('Returning marked.parse(text)');
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

    // Extract each field
    const approachMatch = text.match(/\*\*Approach\*\*:\s*([^\n]+)/i);
    if (approachMatch) decisions.approach = approachMatch[1].trim();

    const toolsMatch = text.match(/\*\*Tools?\s+Used\*\*:\s*([^\n]+)/i);
    if (toolsMatch) {
        const toolsText = toolsMatch[1].trim();
        // Parse tools - can be comma-separated or in backticks
        decisions.tools_used = toolsText
            .split(/[,\n]/)
            .map(t => t.replace(/`/g, '').trim())
            .filter(t => t.length > 0 && t !== '-' && t !== 'None');
    }

    const skillsMatch = text.match(/\*\*Skills?\s+Loaded\*\*:\s*([^\n(]+?)(?:\s*\(via|[\r\n]|$)/im);
    if (skillsMatch) {
        const skillsText = skillsMatch[1].trim();
        decisions.skills_loaded = skillsText
            .split(',')
            .map(s => s.trim())
            .filter(s => s.length > 0 && s !== '-' && s !== '•' && s.toLowerCase() !== 'none');
    }

    const rationaleMatch = text.match(/\*\*Rationale\*\*:\s*([^\n]+)/i);
    if (rationaleMatch) decisions.rationale = rationaleMatch[1].trim();

    // Checklist might be in bullet list after Checklist header
    const checklistMatch = text.match(/\*\*Checklist\*\*:\s*([\s\S]*?)(?=\n\*\*|$)/i);
    if (checklistMatch) {
        const checklistText = checklistMatch[1];
        decisions.checklist = checklistText
            .split('\n')
            .map(line => line.replace(/^[\s\-\*•]+/, '').trim())
            .filter(line => line.length > 0);
    }

    return decisions;
}

/**
 * Render Decisions section with consistent structure
 */
function renderDecisionsSection(decisionsText) {
    const decisions = parseDecisionsSection(decisionsText);

    let html = '<div class="decisions-structured">';

    if (decisions.approach) {
        html += `
            <div class="decision-field">
                <div class="decision-label">Approach</div>
                <div class="decision-value">${decisions.approach}</div>
            </div>`;
    }

    if (decisions.tools_used.length > 0) {
        const toolsList = decisions.tools_used.map(t => `<code>${t}</code>`).join(', ');
        html += `
            <div class="decision-field">
                <div class="decision-label">Tools Used</div>
                <div class="decision-value">${toolsList}</div>
            </div>`;
    }

    if (decisions.skills_loaded.length > 0) {
        const skillsList = decisions.skills_loaded.map(s => `<span class="skill-tag">${s}</span>`).join(' ');
        html += `
            <div class="decision-field">
                <div class="decision-label">Skills Loaded</div>
                <div class="decision-value">${skillsList}</div>
            </div>`;
    }

    if (decisions.rationale) {
        html += `
            <div class="decision-field">
                <div class="decision-label">Rationale</div>
                <div class="decision-value">${decisions.rationale}</div>
            </div>`;
    }

    if (decisions.checklist.length > 0) {
        const checklistItems = decisions.checklist.map(item => `<li>${item}</li>`).join('');
        html += `
            <div class="decision-field">
                <div class="decision-label">Checklist</div>
                <div class="decision-value"><ul class="checklist">${checklistItems}</ul></div>
            </div>`;
    }

    html += '</div>';
    return html;
}

/**
 * Extract skill usage from agent response text
 * Looks for "Skills Loaded:" in the Decisions section
 * Returns array of skill names or null if no skills found
 */
function extractSkillUsage(text) {
    const decisions = parseDecisionsSection(text);
    return decisions.skills_loaded.length > 0 ? decisions.skills_loaded : null;
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
