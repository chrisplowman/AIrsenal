#!/usr/bin/env python3
"""
Enhanced web interface for AIrsenal with real-time progress tracking
"""

import os
import subprocess
import threading
import time
import json
import queue
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# Global variables to track status
pipeline_status = "Not started"
pipeline_progress = 0
current_step = ""
last_run = None
output_log = []
progress_queue = queue.Queue()

# Pipeline steps for progress tracking
PIPELINE_STEPS = [
    "Initializing database connection",
    "Fetching FPL summary data", 
    "Updating player data",
    "Fetching fixture data",
    "Processing team data",
    "Updating player scores",
    "Running predictions",
    "Calculating transfer suggestions",
    "Finalizing results"
]

def parse_pipeline_output(line):
    """Parse pipeline output to extract progress information"""
    global pipeline_progress, current_step
    
    # Look for common AIrsenal output patterns
    progress_indicators = {
        "Setting up": 10,
        "Fetching": 20,
        "Processing": 40,
        "Updating": 60,
        "Calculating": 80,
        "Finished": 100,
        "Done": 100,
        "Complete": 100
    }
    
    # Update current step based on output
    line_lower = line.lower()
    for keyword, progress in progress_indicators.items():
        if keyword.lower() in line_lower:
            pipeline_progress = min(progress, 100)
            current_step = line.strip()
            break
    
    # Look for specific AIrsenal messages
    if "bootstrap-static" in line_lower:
        current_step = "Fetching FPL summary data"
        pipeline_progress = 15
    elif "player" in line_lower and "score" in line_lower:
        current_step = "Processing player scores"
        pipeline_progress = 50
    elif "fixture" in line_lower:
        current_step = "Fetching fixture data"
        pipeline_progress = 25
    elif "prediction" in line_lower:
        current_step = "Running predictions"
        pipeline_progress = 70
    elif "transfer" in line_lower:
        current_step = "Calculating transfer suggestions"
        pipeline_progress = 85

def run_airsenal_pipeline():
    """Run the AIrsenal pipeline with progress tracking"""
    global pipeline_status, last_run, output_log, pipeline_progress, current_step
    
    try:
        pipeline_status = "Running..."
        pipeline_progress = 0
        current_step = "Starting pipeline..."
        output_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting AIrsenal pipeline...")
        
        # Start the subprocess
        process = subprocess.Popen(
            ["airsenal_run_pipeline"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Read output line by line
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                line = output.strip()
                timestamp = datetime.now().strftime('%H:%M:%S')
                output_log.append(f"[{timestamp}] {line}")
                parse_pipeline_output(line)
                
                # Keep only last 50 log entries
                if len(output_log) > 50:
                    output_log = output_log[-50:]
        
        # Check result
        return_code = process.poll()
        if return_code == 0:
            pipeline_status = "Completed successfully"
            pipeline_progress = 100
            current_step = "Pipeline completed"
            output_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Pipeline completed successfully")
        else:
            pipeline_status = f"Failed with code {return_code}"
            pipeline_progress = 0
            current_step = "Pipeline failed"
            output_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Pipeline failed with code {return_code}")
        
        last_run = datetime.now()
        
    except Exception as e:
        pipeline_status = f"Error: {str(e)}"
        pipeline_progress = 0
        current_step = "Error occurred"
        output_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {str(e)}")

# Enhanced HTML template with progress bar and real-time updates
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AIrsenal Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 15px; margin-bottom: 30px; }
        .status-card { padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 5px solid; }
        .status.running { background: #fff3cd; border-left-color: #ffc107; }
        .status.success { background: #d4edda; border-left-color: #28a745; }
        .status.error { background: #f8d7da; border-left-color: #dc3545; }
        .status.not-started { background: #e2e3e5; border-left-color: #6c757d; }
        
        .progress-container { margin: 20px 0; }
        .progress-bar { width: 100%; height: 25px; background: #e9ecef; border-radius: 15px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #28a745, #20c997); transition: width 0.5s ease; border-radius: 15px; }
        .progress-text { text-align: center; margin-top: 10px; font-weight: bold; color: #495057; }
        .current-step { background: #e8f4fd; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #3498db; }
        
        button { background: linear-gradient(45deg, #3498db, #2980b9); color: white; padding: 12px 25px; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; margin: 10px 5px; transition: all 0.3s; }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
        button:disabled { background: #bdc3c7; cursor: not-allowed; transform: none; }
        
        .log-container { background: #2c3e50; border-radius: 10px; margin: 20px 0; overflow: hidden; }
        .log-header { background: #34495e; padding: 15px; color: white; font-weight: bold; }
        .log { color: #ecf0f1; padding: 20px; font-family: 'Courier New', monospace; max-height: 400px; overflow-y: auto; font-size: 14px; line-height: 1.4; }
        
        .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .info-card { background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db; }
        .info-label { font-weight: bold; color: #495057; display: block; }
        .info-value { color: #6c757d; }
        
        .controls { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .auto-refresh { margin-left: auto; display: flex; align-items: center; gap: 10px; }
        
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        .running .progress-fill { animation: pulse 2s infinite; }
        
        .log-line { margin: 2px 0; }
        .log-line.error { color: #e74c3c; }
        .log-line.success { color: #27ae60; }
        .log-line.warning { color: #f39c12; }
    </style>
    <script>
        let autoRefresh = true;
        let refreshInterval;
        
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    // Update progress bar
                    document.getElementById('progress-fill').style.width = data.progress + '%';
                    document.getElementById('progress-text').textContent = data.progress + '%';
                    
                    // Update current step
                    document.getElementById('current-step').textContent = data.current_step || 'Waiting...';
                    
                    // Update status
                    document.getElementById('pipeline-status').textContent = data.status;
                    
                    // Update status card class
                    const statusCard = document.querySelector('.status-card');
                    statusCard.className = 'status-card status ' + getStatusClass(data.status);
                    
                    // Update button state
                    const runBtn = document.getElementById('runBtn');
                    if (data.status.includes('Running')) {
                        runBtn.disabled = true;
                        runBtn.innerHTML = '🔄 Running...';
                    } else {
                        runBtn.disabled = false;
                        runBtn.innerHTML = '▶️ Run Pipeline';
                    }
                    
                    // Update logs
                    if (data.logs) {
                        document.getElementById('log-output').innerHTML = data.logs.map(log => 
                            `<div class="log-line">${log}</div>`
                        ).join('');
                        
                        // Auto-scroll to bottom
                        const logContainer = document.getElementById('log-output');
                        logContainer.scrollTop = logContainer.scrollHeight;
                    }
                })
                .catch(error => console.error('Error:', error));
        }
        
        function getStatusClass(status) {
            if (status.includes('Running')) return 'running';
            if (status.includes('success') || status.includes('Completed')) return 'success';
            if (status.includes('Error') || status.includes('Failed')) return 'error';
            return 'not-started';
        }
        
        function runPipeline() {
            fetch('/run-pipeline', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    updateStatus();
                })
                .catch(error => console.error('Error:', error));
        }
        
        function toggleAutoRefresh() {
            autoRefresh = !autoRefresh;
            const checkbox = document.getElementById('auto-refresh');
            
            if (autoRefresh) {
                refreshInterval = setInterval(updateStatus, 2000);
                checkbox.checked = true;
            } else {
                clearInterval(refreshInterval);
                checkbox.checked = false;
            }
        }
        
        // Start auto-refresh when page loads
        window.onload = function() {
            updateStatus();
            refreshInterval = setInterval(updateStatus, 2000);
            document.getElementById('auto-refresh').checked = true;
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>🏈 AIrsenal Dashboard</h1>
        
        <div class="info-grid">
            <div class="info-card">
                <span class="info-label">FPL Team ID</span>
                <span class="info-value">{{ fpl_team_id or 'Not configured' }}</span>
            </div>
            <div class="info-card">
                <span class="info-label">Server Time</span>
                <span class="info-value">{{ current_time }}</span>
            </div>
            <div class="info-card">
                <span class="info-label">Last Run</span>
                <span class="info-value">{{ last_run or 'Never' }}</span>
            </div>
        </div>
        
        <div class="status-card status {{ status_class }}">
            <strong>Status:</strong> <span id="pipeline-status">{{ pipeline_status }}</span>
        </div>
        
        <div class="current-step">
            <strong>Current Step:</strong> <span id="current-step">{{ current_step or 'Waiting...' }}</span>
        </div>
        
        <div class="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill" style="width: {{ pipeline_progress }}%"></div>
            </div>
            <div class="progress-text" id="progress-text">{{ pipeline_progress }}%</div>
        </div>
        
        <div class="controls">
            <button onclick="runPipeline()" id="runBtn" {{ 'disabled' if 'Running' in pipeline_status else '' }}>
                {% if 'Running' in pipeline_status %}
                    🔄 Running...
                {% else %}
                    ▶️ Run Pipeline
                {% endif %}
            </button>
            
            <button onclick="updateStatus()">🔄 Refresh Now</button>
            
            <div class="auto-refresh">
                <input type="checkbox" id="auto-refresh" onchange="toggleAutoRefresh()">
                <label for="auto-refresh">Auto-refresh (2s)</label>
            </div>
        </div>
        
        <div class="log-container">
            <div class="log-header">📋 Pipeline Output</div>
            <div class="log" id="log-output">{{ log_output }}</div>
        </div>
        
        <div class="info-card">
            <strong>About:</strong> This dashboard runs the AIrsenal Fantasy Premier League analysis pipeline. 
            The pipeline fetches the latest FPL data, updates predictions, and generates transfer suggestions.
            Progress is updated in real-time during execution.
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Main dashboard page"""
    global pipeline_status, last_run, output_log, pipeline_progress, current_step
    
    # Determine status class for styling
    status_class = "not-started"
    if "Running" in pipeline_status:
        status_class = "running"
    elif "success" in pipeline_status.lower() or "Completed" in pipeline_status:
        status_class = "success"
    elif "Error" in pipeline_status or "Failed" in pipeline_status:
        status_class = "error"
    
    # Get recent log entries
    recent_logs = output_log[-30:] if output_log else ["No activity yet"]
    log_output = "\n".join(recent_logs)
    
    return render_template_string(
        HTML_TEMPLATE,
        pipeline_status=pipeline_status,
        status_class=status_class,
        pipeline_progress=pipeline_progress,
        current_step=current_step,
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
    """API endpoint to get current status with progress"""
    return jsonify({
        "status": pipeline_status,
        "progress": pipeline_progress,
        "current_step": current_step,
        "last_run": last_run.isoformat() if last_run else None,
        "logs": output_log[-20:] if output_log else []
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    # Add startup message
    output_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 AIrsenal web interface started")
    
    # Get port from environment variable (Render sets this automatically)
    port = int(os.environ.get('PORT', 10000))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=False)
