const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat`;
let socket;
let reconnectAttempts = 0;
const MAX_RECONNECT_DELAY = 30000;

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

// Tactical Buttons v4.1
const btnVision = document.getElementById('btn-mode-vision');
const btnAuto = document.getElementById('btn-mode-auto');
const btnGamer = document.getElementById('btn-mode-gamer');
const btnStop = document.getElementById('btn-mode-stop');

// Nucleus Indicators v4.1
const barLoad = document.getElementById('bar-load');
const valSync = document.getElementById('val-sync');
const valMTrace = document.getElementById('val-mtrace');

let manualOverlayClose = false;
let localRemainingTime = 0;
let timerInterval = null;

// Button State Tracking
let isVisionActive = false;
let isAutonomyActive = false;
let isGamerActive = false;

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

function connect() {
    console.log(`[Cortex] Connecting to ${wsUrl}...`);
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log("[Cortex] Neural link established.");
        addSystemMessage("Neural link established. Ready.");
        document.body.classList.remove('disconnected');
        reconnectAttempts = 0;
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleEvent(data);
        } catch (e) {
            console.error("[Cortex] Error parsing frame:", e);
        }
    };

    socket.onclose = () => {
        console.warn("[Cortex] Neural link severed.");
        addSystemMessage("⚠️ Neural link severed. Reconnecting...");
        document.body.classList.add('disconnected');
        
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), MAX_RECONNECT_DELAY);
        reconnectAttempts++;
        setTimeout(connect, delay);
    };

    socket.onerror = (err) => {
        console.error("[Cortex] Connection error:", err);
    };
}

// Initial connection
connect();

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
                syncUIWithMode(payload.mode, payload.autonomy);
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
            // Payload: { equity: 94.2, prosperity: 98.7, mode: 'chat', load: 25 }
            if (payload.equity !== undefined) {
                elEquity.innerText = payload.equity.toFixed(1) + "%";
                barEquity.style.width = payload.equity + "%";
                updateBarColor(barEquity, payload.equity, true); // true = inverted (High = Green)
            }
            if (payload.prosperity !== undefined) {
                elProsperity.innerText = payload.prosperity.toFixed(1) + "%";
                barProsperity.style.width = payload.prosperity + "%";
                updateBarColor(barProsperity, payload.prosperity, true);
            }
            if (payload.load !== undefined) {
                barLoad.style.width = payload.load + "%";
                updateBarColor(barLoad, payload.load, false); // false = standard (High = Red)
            }
            if (payload.mode) {
                syncUIWithMode(payload.mode, payload.autonomy, payload.gamer);
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

        case 'vision_crop':
            // Payload: { image: "base64..." }
            const precisionCrop = document.getElementById('precision-crop');
            if (payload.image && precisionCrop) {
                precisionCrop.innerHTML = `<img src="data:image/png;base64,${payload.image}" />`;
            }
            break;

        case 'nucleus_update':
            // Payload: { load: 25, sync: 'ACTIVE', trace: '#F0A1' }
            if (payload.load !== undefined) {
                barLoad.style.width = payload.load + "%";
                updateBarColor(barLoad, payload.load, false);
            }
            if (payload.sync) valSync.innerText = payload.sync;
            if (payload.trace) valMTrace.innerText = payload.trace;
            break;

        case 'thought_stream':
            // Payload: { token: "...", is_thinking: true }
            const streamEl = document.getElementById('reflection-stream');
            if (streamEl) {
                if (payload.token === "<think>") streamEl.innerText = ""; // Clear on new thinking cycle
                streamEl.innerHTML += payload.token.replace(/\n/g, '<br>');
                streamEl.scrollTop = streamEl.scrollHeight;
            }
            break;
        case 'hitl_consultation':
            // Payload: { msg: "Should I click the 'Buy' button?" }
            addSystemMessage(`🛡️ **CONTROL HUMANO REQUERIDO:**\n${payload.msg}`);
            // Force a pulse on the neural reflection to show it's waiting
            const streamElHITL = document.getElementById('reflection-stream');
            if (streamElHITL) {
                streamElHITL.innerHTML = `<span style="color: var(--caution); animation: pulse 1s infinite; font-weight: bold;">[!] ESPERANDO APROBACIÓN HUMANA...</span><br><br>${payload.msg}`;
            }
            break;
    }
}

function syncUIWithMode(mode, autonomyActive, gamerActive) {
    const m = mode.toUpperCase();
    elMode.innerText = m;
    
    const m_low = mode.toLowerCase();
    
    // 1. VISION SYNC
    isVisionActive = m_low.includes("vision") || m_low.includes("gamer") || m_low.includes("auto");
    btnVision.classList.toggle('active', isVisionActive);

    // 2. AUTONOMY SYNC
    isAutonomyActive = autonomyActive || m_low.includes("auto");
    btnAuto.classList.toggle('active', isAutonomyActive);
    
    if (isAutonomyActive) {
        if (!manualOverlayClose) overlayAuto.classList.remove('hidden');
        // Timer Sync (e.g., "AUTO 120S")
        const timeMatch = m.match(/AUTO (\d+)S/);
        if (timeMatch) {
            const timePart = parseInt(timeMatch[1]);
            if (!isNaN(timePart) && (Math.abs(localRemainingTime - timePart) > 2 || !timerInterval)) {
                startLocalTimer(timePart);
            }
        }
    } else {
        overlayAuto.classList.add('hidden');
        manualOverlayClose = false;
        if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
    }

    // 3. GAMER SYNC
    isGamerActive = gamerActive || m_low.includes("gamer");
    btnGamer.classList.toggle('active', isGamerActive);
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

function updateBarColor(bar, value, inverted = false) {
    if (inverted) {
        // High = Green (Equity/Prosperity)
        if (value > 85) bar.style.background = 'var(--success)';
        else if (value > 50) bar.style.background = 'var(--caution)';
        else bar.style.background = 'var(--alert)';
    } else {
        // High = Red (Load)
        if (value < 50) bar.style.background = 'var(--success)';
        else if (value < 85) bar.style.background = 'var(--caution)';
        else bar.style.background = 'var(--alert)';
    }
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
    
    // Clear Stream panel for new thought
    const streamEl = document.getElementById('reflection-stream');
    if (streamEl) streamEl.innerText = "[Pensando...]";

    socket.send(text);
    userInput.value = '';
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// Helper for sending commands with immediate visual feedback
function sendCommand(text) {
    if (socket.readyState !== WebSocket.OPEN) {
        addSystemMessage("⚠️ Connection not ready. Please wait...");
        return;
    }

    // Add to chat history so user knows the click did something
    addMessage("USER", text);
    showThinking();
    socket.send(text);
}

// Tactical Button Toggle Logic v4.4
btnVision.onclick = () => {
    if (isVisionActive) sendCommand("/mode chat");
    else sendCommand("/mode vision");
};

btnAuto.onclick = () => {
    if (isAutonomyActive) sendCommand("/actua stop");
    else sendCommand("/actua 60");
};

btnGamer.onclick = () => {
    // Gamer mode is a toggle in backend usually, but we send /gamer
    sendCommand("/gamer");
};

btnStop.onclick = () => {
    // EMERGENCY STOP & RESET
    addSystemMessage("🛑 EMERGENCY STOP: Resetting System Mode...");
    sendCommand("/actua stop");

    // UI Local Reset
    manualOverlayClose = false;
    overlayAuto.classList.add('hidden');

    // Force deactivation of all buttons locally for instant feedback
    [btnVision, btnAuto, btnGamer].forEach(btn => btn.classList.remove('active'));
    isVisionActive = isAutonomyActive = isGamerActive = false;
};

// Neural Overclocking Interaction ⚡
if (barLoad && barLoad.parentElement) {
    barLoad.parentElement.addEventListener('click', (e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const width = rect.width;
        const powerPercent = Math.max(0, Math.min(100, (x / width) * 100));
        const powerLevel = (powerPercent / 10).toFixed(1); // 0.0 - 10.0
        
        console.log(`[Cortex] Tuning Power Level to ${powerLevel}`);
        socket.send(JSON.stringify({
            type: "set_power",
            payload: { level: parseFloat(powerLevel) }
        }));
        
        // Immediate local feedback
        barLoad.style.width = powerPercent + "%";
        updateBarColor(barLoad, powerPercent, false);
    });
}
