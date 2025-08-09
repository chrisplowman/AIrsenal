#!/usr/bin/env python3
"""
Simple web interface for AIrsenal
"""

import os
import subprocess
import threading
import time
from datetime import datetime
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# Global variables to track status
pipeline_status = "Not started"
last_run = None
output_log = []

def run_airsenal_pipeline():
    """Run the AIrsenal pipeline in background"""
    global pipeline_status, last_run, output_log
    
    try:
        pipeline_status = "Running..."
        output_log.append(f"[{datetime.now()}] Starting AIrsenal pipeline...")
        
        # Run the AIrsenal pipeline
        result = subprocess.run(
            ["airsenal_run_pipeline"],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if result.returncode == 0:
            pipeline_status = "Completed successfully"
            output_log.append(f"[{datetime.now()}] Pipeline completed successfully")
        else:
            pipeline_status = f"Failed with code {result.returncode}"
            output_log.append(f"[{datetime.now()}] Pipeline failed: {result.stderr}")
        
        last_run = datetime.now()
        
    except subprocess.TimeoutExpired:
        pipeline_status = "Timed out"
        output_log.append(f"[{datetime.now()}] Pipeline timed out after 1 hour")
    except Exception as e:
        pipeline_status = f"Error: {str(e)}"
        output_log.append(f"[{datetime.now()}] Error: {str(e)}")

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AIrsenal Dashboard</title>
    <meta name="robots" content="noindex">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        .status { padding: 15px; border-radius: 5px; margin: 20px 0; font-weight: bold; }
        .status.running { background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; }
        .status.success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        .status.error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        .status.not-started { background: #e2e3e5; border: 1px solid #d6d8db; color: #383d41; }
        button { background: #3498db; color: white; padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin: 10px 5px; }
        button:hover { background: #2980b9; }
        button:disabled { background: #bdc3c7; cursor: not-allowed; }
        .log { background: #2c3e50; color: #ecf0f1; padding: 20px; border-radius: 5px; font-family: monospace; max-height: 400px; overflow-y: auto; white-space: pre-wrap; }
        .info { background: #e8f4fd; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db; margin: 20px 0; }
        .refresh { float: right; font-size: 14px; }
    </style>
    <meta http-equiv="refresh" content="30">
</head>
<body>
    <div class="container">
        <h1>AIrsenal Dashboard</h1>
        
        <div class="info">
            <strong>FPL Team ID:</strong> {{ fpl_team_id or 'Not configured' }}<br>
            <strong>Server Time:</strong> {{ current_time }}<br>
            <strong>Last Pipeline Run:</strong> {{ last_run or 'Never' }}
        </div>
        
        <div class="status {{ status_class }}">
            <strong>Pipeline Status:</strong> {{ pipeline_status }}
        </div>
        
        <button onclick="runPipeline()" id="runBtn" {{ 'disabled' if pipeline_status == 'Running...' else '' }}>
            {% if pipeline_status == 'Running...' %}
                🔄 Running...
            {% else %}
                ▶️ Run Pipeline
            {% endif %}
        </button>
        
        <button onclick="location.reload()" class="refresh">🔄 Refresh</button>
        
        <h3>📋 Recent Activity</h3>
        <div class="log">{{ log_output }}</div>
        
        <div class="info">
            <strong>About AIrsenal:</strong> This dashboard runs the AIrsenal Fantasy Premier League analysis pipeline. 
            The pipeline fetches the latest FPL data, updates predictions, and generates transfer suggestions.
            <br><br>
            <strong>Note:</strong> The pipeline may take several minutes to complete depending on the amount of data to process.
        </div>
    </div>
    
    <script>
        function runPipeline() {
            document.getElementById('runBtn').disabled = true;
            document.getElementById('runBtn').innerHTML = '🔄 Starting...';
            
            fetch('/run-pipeline', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    setTimeout(() => location.reload(), 2000);
                })
                .catch(error => {
                    console.error('Error:', error);
                    setTimeout(() => location.reload(), 2000);
                });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Main dashboard page"""
    global pipeline_status, last_run, output_log
    
    # Determine status class for styling
    status_class = "not-started"
    if "Running" in pipeline_status:
        status_class = "running"
    elif "success" in pipeline_status.lower() or "Completed" in pipeline_status:
        status_class = "success"
    elif "Error" in pipeline_status or "Failed" in pipeline_status or "Timed out" in pipeline_status:
        status_class = "error"
    
    # Get recent log entries (last 20)
    recent_logs = output_log[-20:] if output_log else ["No activity yet"]
    log_output = "\n".join(recent_logs)
    
    return render_template_string(
        HTML_TEMPLATE,
        pipeline_status=pipeline_status,
        status_class=status_class,
        last_run=last_run.strftime("%Y-%m-%d %H:%M:%S") if last_run else None,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        fpl_team_id=os.getenv('FPL_TEAM_ID'),
        log_output=log_output
    )

@app.route('/run-pipeline', methods=['POST'])
def run_pipeline():
    """API endpoint to trigger pipeline run"""
    global pipeline_status
    
    if "Running" in pipeline_status:
        return jsonify({"status": "error", "message": "Pipeline already running"})
    
    # Start pipeline in background thread
    thread = threading.Thread(target=run_airsenal_pipeline)
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "success", "message": "Pipeline started"})

@app.route('/status')
def get_status():
    """API endpoint to get current status"""
    return jsonify({
        "status": pipeline_status,
        "last_run": last_run.isoformat() if last_run else None,
        "log_count": len(output_log)
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    # Add startup message
    output_log.append(f"[{datetime.now()}] AIrsenal web interface started")
    
    # Get port from environment variable (Render sets this automatically)
    port = int(os.environ.get('PORT', 10000))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=False)
