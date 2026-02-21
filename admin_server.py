from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
import threading
import os
import markdown
import json
import time

app = FastAPI()

def get_session_manager():
    if not hasattr(app.state, "session_manager"):
        raise HTTPException(status_code=500, detail="Session Manager not initialized")
    return app.state.session_manager

def get_events():
    return getattr(app.state, "events", [])

def get_chat_history(chat_name=None, limit=100):
    log_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "chat_history.log"))
    if not os.path.exists(log_file):
        return []
    
    history = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in reversed(lines):
                if chat_name:
                    if f"[{chat_name}]" in line:
                        history.append(line.strip())
                else:
                    history.append(line.strip())
                if len(history) >= limit:
                    break
    except Exception as e:
        print(f">>> Error reading log history: {e}")
    return history

@app.get("/", response_class=HTMLResponse)
async def list_sessions():
    sessions = get_session_manager().active_sessions
    whatsapp = getattr(app.state, "whatsapp", None)
    events = get_events()
    
    html_content = """
    <html>
        <head>
            <title>WhatsApp Supervisor Admin</title>
            <style>
                body { font-family: sans-serif; margin: 2rem; background: #f4f7f6; }
                .container { max-width: 1200px; margin: auto; background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
                .session { margin: 1rem 0; padding: 1rem; border: 1px solid #ddd; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }
                .session.registered { border-left: 5px solid #28a745; }
                .session.group { border-left-color: #007bff; }
                .badge { padding: 0.2rem 0.5rem; border-radius: 10px; font-size: 0.8rem; font-weight: bold; }
                .badge-registered { background: #d4edda; color: #155724; }
                .badge-group { background: #cce5ff; color: #004085; }
                a { text-decoration: none; color: #007bff; }
                a:hover { text-decoration: underline; }
                h1, h2 { color: #333; }
                ul { list-style: none; padding: 0; }
                .event-log, .chat-log { background: #333; color: #0f0; padding: 1rem; border-radius: 5px; font-family: monospace; overflow-y: auto; white-space: pre-wrap; }
                .event-log { height: 200px; }
                .chat-log { height: 500px; color: #fff; background: #222; }
                .chat-sender { color: #007bff; font-weight: bold; }
                .chat-bot { color: #28a745; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>WhatsApp Supervisor Dashboard</h1>
                
                <div style="display: flex; gap: 2rem;">
                  <div style="flex: 2;">
                    <h2>Active Sessions (Registered)</h2>
                    <ul>
    """
    
    if not sessions:
         html_content += "<li>No active sessions. Send <code>/register</code> or <code>/agent</code> in a WhatsApp chat.</li>"
    else:
        for chat_name, path in sessions.items():
            html_content += f"""
                <li class="session registered">
                    <div>
                        <strong><a href="/session/{chat_name}">{chat_name}</a></strong><br>
                        <small>{path}</small>
                    </div>
                    <span class="badge badge-registered">Registered</span>
                </li>
            """
    
    html_content += """
                    </ul>
                    
                    <h2>All Channels (Detected)</h2>
                    <ul>
    """
    
    if whatsapp:
        try:
             all_chats = whatsapp.get_all_chats()
             if not all_chats:
                 html_content += "<li>No channels detected yet.</li>"
             for chat in all_chats:
                 name = chat.name
                 is_group = chat.is_group
                 is_registered = name in sessions
                 
                 extra_class = "group" if is_group else ""
                 
                 html_content += f"""
                    <li class="session {extra_class}">
                        <div>
                            {name} {f'<span class="badge badge-group">Group</span>' if is_group else ''}
                        </div>
                        {f'<span class="badge badge-registered">Registered</span>' if is_registered else ''}
                    </li>
                 """
        except Exception as e:
            html_content += f"<li>Error fetching channels: {e}</li>"
    else:
        html_content += "<li>WhatsApp instance not connected.</li>"

    html_content += f"""
                    </ul>
                  </div>
                  
                  
                  <div style="flex: 1;">
                    <h2>Detected Events</h2>
                    <div class="event-log">
                        {'<br>'.join([f"[{e['timestamp']}] {e['event']} - {e['chat']}" for e in reversed(events)]) if events else "No events recorded."}
                    </div>
                    
                    <h2>Recent Chat History</h2>
                    <div class="chat-log">
                        {('<br>'.join(get_chat_history(limit=50)) if get_chat_history() else "No history recorded yet.")}
                    </div>
                  </div>
                </div>
            </div>
        </body>
    </html>
    """
    return html_content

@app.get("/session/{chat_name}", response_class=HTMLResponse)
async def view_session(chat_name: str):
    manager = get_session_manager()
    if chat_name not in manager.active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    workspace_path = manager.active_sessions[chat_name]
    todo_path = os.path.join(workspace_path, "TODO.md")
    objective_path = os.path.join(workspace_path, "OBJECTIVE.md")
    error_log_path = os.path.join(workspace_path, "error.log")
    
    todo_content = "File not found"
    if os.path.exists(todo_path):
        with open(todo_path, "r", encoding="utf-8") as f:
            todo_content = markdown.markdown(f.read())
            
    objective_content = "File not found"
    if os.path.exists(objective_path):
        with open(objective_path, "r", encoding="utf-8") as f:
            objective_content = markdown.markdown(f.read())

    error_log_content = ""
    if os.path.exists(error_log_path):
        with open(error_log_path, "r", encoding="utf-8") as f:
            content = f.read()
            if content.strip():
                error_log_content = f"<pre>{content}</pre>"

    html_content = f"""
    <html>
        <head>
            <title>Session: {chat_name}</title>
            <style>
                body {{ font-family: sans-serif; margin: 2rem; background: #f4f7f6; }}
                .container {{ max-width: 1200px; margin: auto; background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .columns {{ display: flex; gap: 2rem; }}
                .column {{ flex: 1; padding: 1.5rem; border: 1px solid #eee; border-radius: 5px; background: #fff; }}
                h1, h2 {{ color: #333; }}
                h2 {{ border-bottom: 2px solid #eee; padding-bottom: 0.5rem; }}
                .error {{ color: #721c24; border: 1px solid #f5c6cb; padding: 1rem; margin-top: 1.5rem; background: #f8d7da; border-radius: 5px; }}
                .back-link {{ margin-bottom: 1rem; display: block; }}
                .chat-log {{ background: #222; color: #fff; padding: 1rem; border-radius: 5px; font-family: monospace; overflow-y: auto; white-space: pre-wrap; height: 400px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <a href="/" class="back-link">&larr; Back to Dashboard</a>
                <h1>Project: {chat_name}</h1>
                <p><small>Workspace: {workspace_path}</small></p>
                
                <div class="columns">
                    <div class="column">
                        <h2>Objective</h2>
                        {objective_content}
                    </div>
                    <div class="column">
                        <h2>TODO List</h2>
                        {todo_content}
                    </div>
                </div>
    """
    
    
    chat_history = get_chat_history(chat_name=chat_name, limit=50)
    if chat_history:
        html_content += f"""
            <div style="margin-top: 2rem;">
                <h2>Recent Chat History</h2>
                <div class="chat-log">
                    {'<br>'.join(chat_history)}
                </div>
            </div>
        """

    if error_log_content:
        html_content += f"""
            <div class="error">
                <h2>Error Log</h2>
                {error_log_content}
            </div>
        """
        
    html_content += """
            </div>
        </body>
    </html>
    """
    return html_content

@app.get("/send")
async def send_via_http(text: str, chat: str = None):
    """API endpoint to trigger a WhatsApp message via HTTP GET."""
    whatsapp = getattr(app.state, "whatsapp", None)
    if not whatsapp:
        raise HTTPException(status_code=503, detail="WhatsApp instance not initialized")
    
    from core.config import ADMIN_CHAT
    target = chat or ADMIN_CHAT
    if not target:
        raise HTTPException(status_code=400, detail="Target chat not specified and ADMIN_CHAT not configured")
    
    # We do this in a separate thread because send_message is blocking
    def op():
        whatsapp.send_message(target, text)
    
    threading.Thread(target=op).start()
    return {"status": "accepted", "chat": target, "message": text}


def start_server(session_manager, whatsapp_instance=None, events_list=None, port=8000):
    app.state.session_manager = session_manager
    app.state.whatsapp = whatsapp_instance
    app.state.events = events_list if events_list is not None else []
    # If server is already running, just update the state
    if hasattr(app.state, "started") and app.state.started:
        print(f">>> Admin UI already running. State updated.")
        return

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="error")
    server = uvicorn.Server(config)
    
    def serve():
        try:
            app.state.started = True
            server.run()
        except Exception as e:
            app.state.started = False
            print(f">>> Admin UI Error: {e}")

    thread = threading.Thread(target=serve)
    thread.daemon = True
    thread.start()
    print(f">>> Admin UI started at http://localhost:{port}")
    print(f">>> Example: http://localhost:{port}/send?text=TestMessage")
