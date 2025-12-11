"""Main entrypoint for BotAdmin."""
from interact import create_app, socketio

app = create_app()

if __name__ == "__main__":
    # 使用 socketio.run 启动，支持 WebSocket
    socketio.run(app, host="0.0.0.0", port=8780, debug=True, allow_unsafe_werkzeug=True)
