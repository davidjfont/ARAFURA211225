import asyncio
import json
import threading
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Intentamos importar uvicorn para cuando se ejecute directo
try:
    import uvicorn
except ImportError:
    uvicorn = None

# Global orchestrator reference (injected by launcher)
ORCHESTRATOR = None

app = FastAPI()

# Mount static files
base_path = Path(__file__).resolve().parent.parent
web_path = base_path / "web"
web_path.mkdir(exist_ok=True) # Ensure it exists
app.mount("/static", StaticFiles(directory=str(web_path)), name="static")

# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Bridge: Orchestrator -> WebSocket
def orchestrator_callback(event_type: str, payload: dict):
    """Callback sync called by Orchestrator thread. Schedules async broadcast."""
    # We need to run the async broadcast in the main loop
    # For simplicity in this demo, we assume thread-safe broadcast or fire-and-forget
    # Actually, running async from sync thread is tricky. 
    # Solution: Use run_coroutine_threadsafe if we had the loop, 
    # BUT simplest is to queue it or use a thread-safe implementation.
    # FastAPI/Uvicorn runs in an event loop.
    
    # Quick Hack: Create a new loop for the send? No.
    # Correct way: use the loop attached to the app. 
    # Since we don't have easy access to the running loop instance here globally, 
    # we will rely on a thread-safe queue OR just print for now if complex.
    
    # BETTER: The Orchestrator calls this. We can use asyncio.run() if it's a quick send?
    # No, asyncio.run() creates a NEW loop.
    
    # Let's try to get the running loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(manager.broadcast({"type": event_type, "payload": payload}), loop)
    else:
        # Fallback if called from a thread where no loop is running (background thread)
        # We need to find the MAIN server loop.
        # For Phase 1, we will skip complex async bridging and just print to console 
        # that we WOULD send it, or try a fire-and-forget approach.
        pass

# BUT we can store the loop when app starts!
APP_LOOP = None

@app.on_event("startup")
async def startup_event():
    global APP_LOOP
    APP_LOOP = asyncio.get_running_loop()

def thread_safe_emit(event_type: str, payload: dict):
    if APP_LOOP:
        asyncio.run_coroutine_threadsafe(manager.broadcast({"type": event_type, "payload": payload}), APP_LOOP)

@app.get("/")
async def get():
    # Return index.html
    index_file = web_path / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding='utf-8'))
    return "Arafura Web Interface Loading..."

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial status & history
        if ORCHESTRATOR:
            # 1. Chat History
            chat_hist = ORCHESTRATOR.memory.get_recent_history(limit=20)
            # 2. Vision/Thought Logs
            vis_hist = ORCHESTRATOR.visual_log[-20:]
            thought_hist = ORCHESTRATOR.thought_log[-20:]
            
            await websocket.send_json({
                "type": "history", 
                "payload": {
                    "chat": chat_hist,
                    "visual": vis_hist,
                    "thought": thought_hist,
                    "mode": getattr(ORCHESTRATOR, 'system_mode', 'chat'),
                    "autonomy": getattr(ORCHESTRATOR, 'autonomy_active', False)
                }
            })
            
            await websocket.send_json({
                "type": "system", 
                "payload": {"msg": "Connected to ARAFURA Core. History Sync Complete."}
            })
            
        while True:
            data = await websocket.receive_text()
            # User Input from Web
            if ORCHESTRATOR:
                # Run process_input in a thread to not block WS loop
                # We assume process_input returns the string response
                # But we want the RESPONSE to also flow back via the callback?
                # The CLI flow was: response = process_input()...
                # Here:
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, ORCHESTRATOR.process_input, data)
                
                # Send response back directly (User-Request -> Response)
                await websocket.send_json({
                    "type": "chat_response",
                    "payload": {"role": "ARAFURA", "content": response}
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def start_server(orchestrator, host="0.0.0.0", port=8000):
    global ORCHESTRATOR
    ORCHESTRATOR = orchestrator
    # Hook callback
    ORCHESTRATOR.event_callback = thread_safe_emit
    
    if uvicorn:
        uvicorn.run(app, host=host, port=port, log_level="info")
    else:
        print("Uvicorn not installed.")
