from flask import Flask, Response, render_template_string
import time
import threading

# 保留最近 50 筆 logs
MAX_LOGS = 50
log_history = []

app = Flask(__name__)

# ====== HTML Template（新版 UI） ======
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>IoT Live Logs</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 20px;
            background: #f0f2f5;
        }

        h2 {
            color: #333;
            margin-bottom: 20px;
        }

        #log-container {
            width: 700px;
            max-height: 600px;
            overflow-y: scroll;
            padding-right: 10px;
        }

        .log-entry {
            background: white;
            border-radius: 8px;
            padding: 12px 15px;
            margin-bottom: 10px;
            box-shadow: 0px 2px 5px rgba(0,0,0,0.15);
            border-left: 5px solid #4CAF50;
            font-size: 15px;
            line-height: 1.4em;
        }
    </style>
</head>

<body>
    <h2>IoT Live Logs Viewer</h2>

    <div id="log-container"></div>

    <script>
        const evtSource = new EventSource("/stream");

        evtSource.onmessage = function(event) {
            const logs = JSON.parse(event.data);
            const container = document.getElementById("log-container");
            container.innerHTML = "";

            logs.forEach(function(line) {
                const div = document.createElement("div");
                div.className = "log-entry";
                div.innerText = line;
                container.appendChild(div);
            });

            // 自動滾動到底部
            container.scrollTop = container.scrollHeight;
        };
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


@app.route("/stream")
def stream():
    def event_stream():
        last_snapshot = []
        while True:
            global log_history
            if log_history != last_snapshot:
                last_snapshot = list(log_history)
                yield f"data: {json.dumps(last_snapshot)}\n\n"
            time.sleep(1)

    import json
    return Response(event_stream(), mimetype="text/event-stream")


def set_log(msg: str):
    global log_history
    log_history.append(msg)

    # 只保留最近 MAX_LOGS 筆
    if len(log_history) > MAX_LOGS:
        log_history = log_history[-MAX_LOGS:]
