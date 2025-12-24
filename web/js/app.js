const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat`;
const socket = new WebSocket(wsUrl);

const chatHistory = document.getElementById('chat-history');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const thinkingIndicator = document.getElementById('thinking-indicator');
const visualLog = document.getElementById('visual-log');
const thoughtLog = document.getElementById('thought-log');
const visionFeed = document.getElementById('vision-feed');

// Status Elements
const elEquity = document.getElementById('val-equity');
const barEquity = document.getElementById('bar-equity');
const elProsperity = document.getElementById('val-prosperity');
const barProsperity = document.getElementById('bar-prosperity');
const elMode = document.getElementById('current-mode');
const elMouse = document.getElementById('mouse-coords');

// Autonomy Overlay Elements
const overlayAuto = document.getElementById('autonomy-overlay');
const timerAuto = document.getElementById('auto-timer');
const statusAuto = document.getElementById('auto-status');
const countAuto = document.getElementById('auto-action-count');
const btnCloseAuto = document.getElementById('close-auto-btn');

let manualOverlayClose = false;
let localRemainingTime = 0;
let timerInterval = null;

function startLocalTimer(seconds) {
    if (timerInterval) clearInterval(timerInterval);
    localRemainingTime = seconds;
    timerAuto.innerText = localRemainingTime;

    timerInterval = setInterval(() => {
        if (localRemainingTime > 0) {
            localRemainingTime--;
            timerAuto.innerText = localRemainingTime;
            // Update mode badge too
            elMode.innerText = `AUTO ${localRemainingTime}s`;
        } else {
            clearInterval(timerInterval);
        }
    }, 1000);
}

btnCloseAuto.onclick = () => {
    overlayAuto.classList.add('hidden');
    manualOverlayClose = true;
};

socket.onopen = () => {
    addSystemMessage("WebSocket Connected. Ready.");
};

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleEvent(data);
};

socket.onclose = () => {
    addSystemMessage("⚠️ Connection Lost. Will try to reconnect...");
    // Don't reload immediately - give LLM calls time to complete
    setTimeout(() => {
        if (socket.readyState === WebSocket.CLOSED) {
            window.location.reload();
        }
    }, 15000);  // Wait 15 seconds before reload
};

function handleEvent(data) {
    const payload = data.payload;

    switch (data.type) {
        case 'history':
            // Repopulate everything
            if (payload.chat) {
                chatHistory.innerHTML = ''; // Clear but then refill
                payload.chat.forEach(msg => addMessage(msg.role, msg.content, false));
            }
            if (payload.visual) {
                visualLog.innerHTML = '';
                payload.visual.forEach(log => {
                    // Extract text from log like "[12:34:56] Text"
                    const match = log.match(/\[(.*?)\] (.*)/);
                    if (match) logToTerminal(visualLog, match[2]);
                    else logToTerminal(visualLog, log);
                });
            }
            if (payload.thought) {
                thoughtLog.innerHTML = '';
                payload.thought.forEach(log => {
                    const match = log.match(/\[(.*?)\] (.*)/);
                    if (match) logToTerminal(thoughtLog, match[2]);
                    else logToTerminal(thoughtLog, log);
                });
            }
            if (payload.mode) {
                elMode.innerText = payload.mode.toUpperCase();
                if (payload.mode.startsWith("AUTO") || payload.autonomy) {
                    overlayAuto.classList.remove('hidden');
                }
            }
            scrollToBottom();
            break;

        case 'chat_response':
            hideThinking();
            addMessage(payload.role, payload.content);
            break;

        case 'system':
            hideThinking();
            addSystemMessage(payload.msg);
            break;

        case 'monitor_update':
            // Payload: { equity: 94.2, prosperity: 98.7, mode: 'chat' }
            if (payload.equity) {
                elEquity.innerText = payload.equity.toFixed(1) + "%";
                barEquity.style.width = payload.equity + "%";
            }
            if (payload.prosperity) {
                elProsperity.innerText = payload.prosperity.toFixed(1) + "%";
                barProsperity.style.width = payload.prosperity + "%";
            }
            if (payload.mode) {
                elMode.innerText = payload.mode.toUpperCase();

                // Overlay Logic
                const isAuto = payload.mode.startsWith("AUTO");

                if (isAuto) {
                    // Reset manual close if it's a "fresh" auto start (detected by very high seconds or manual trigger)
                    // (Actually we trust the backend logic to only send mode:AUTO when active)

                    if (!manualOverlayClose) {
                        overlayAuto.classList.remove('hidden');
                    }

                    const timePart = parseInt(payload.mode.replace("AUTO ", "").replace("s", ""));

                    // Only start/sync if difference is significant or it's a new auto start
                    if (Math.abs(localRemainingTime - timePart) > 2 || !timerInterval) {
                        startLocalTimer(timePart);
                    }

                    if (payload.action_count !== undefined) {
                        countAuto.innerText = payload.action_count;
                    }
                    if (payload.last_action) {
                        statusAuto.innerText = payload.last_action;
                    }
                } else {
                    // Not in auto mode anymore
                    overlayAuto.classList.add('hidden');
                    manualOverlayClose = false;
                    if (timerInterval) {
                        clearInterval(timerInterval);
                        timerInterval = null;
                    }
                }
            }
            break;

        case 'visual_log':
            logToTerminal(visualLog, payload.msg);
            break;

        case 'thought_log':
            logToTerminal(thoughtLog, payload.msg);
            break;

        case 'vision_frame':
            // Payload: { image: "base64..." }
            if (payload.image) {
                visionFeed.innerHTML = `<img src="data:image/png;base64,${payload.image}" />`;
            }
            break;

        case 'mouse_move':
            if (elMouse) {
                elMouse.innerText = `Mouse: ${payload.x}, ${payload.y}`;
            }
            break;
    }
}

function showThinking() {
    if (thinkingIndicator) {
        thinkingIndicator.classList.remove('hidden');
        // Move to bottom
        chatHistory.appendChild(thinkingIndicator);
        scrollToBottom();
    }
}

function hideThinking() {
    if (thinkingIndicator) {
        thinkingIndicator.classList.add('hidden');
    }
}

function addMessage(role, content, skipScroll = false) {
    const div = document.createElement('div');
    div.className = `message ${role.toLowerCase()}`;

    // Simple Markdown parsing could go here
    let htmlContent = content.replace(/\n/g, '<br>');

    div.innerHTML = `<div class="role-label">${role}</div><div class="content">${htmlContent}</div>`;

    // Insert before thinking indicator if it exists
    if (thinkingIndicator && thinkingIndicator.parentNode === chatHistory) {
        chatHistory.insertBefore(div, thinkingIndicator);
    } else {
        chatHistory.appendChild(div);
    }

    if (!skipScroll) scrollToBottom();
}

function addSystemMessage(text) {
    const div = document.createElement('div');
    div.className = 'message system';
    div.innerHTML = `<div class="content">${text}</div>`;

    if (thinkingIndicator && thinkingIndicator.parentNode === chatHistory) {
        chatHistory.insertBefore(div, thinkingIndicator);
    } else {
        chatHistory.appendChild(div);
    }
    scrollToBottom();
}

function logToTerminal(container, text) {
    const div = document.createElement('div');
    div.className = 'log-entry';
    const time = new Date().toLocaleTimeString();
    div.innerHTML = `<span class="log-time">[${time}]</span> ${text}`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Sending
function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    addMessage("USER", text);
    showThinking(); // Show animation
    socket.send(text);
    userInput.value = '';
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});
