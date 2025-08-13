#!/usr/bin/env python3
"""
Simplified AIrsenal web interface (no psutil dependency)
"""

import os
import subprocess
import threading
import time
import json
import queue
import gc
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# Global variables to track status
processes = {}
output_logs = {}
current_transfers = []
team_status = {}

# AIrsenal process definitions
AIRSENAL_PROCESSES = {
    'setup_db_minimal': {
        'name': 'Setup Database (Minimal)',
        'description': 'Initialize database with current season data only (memory efficient)',
        'command': ['airsenal_setup_initial_db'],
        'icon': '🗄️',
        'color': 'info',
        'estimated_time': '3-8 minutes'
    },
    'update_db_lite': {
        'name': 'Update Database (Lite)',
        'description': 'Quick database update with essential data only',
        'command': ['airsenal_update_db', '--noattr'],
        'icon': '🔄',
        'color': 'warning',
        'estimated_time': '1-3 minutes'
    },
    'run_predictions': {
        'name': 'Run Predictions',
        'description': 'Generate player performance predictions using the ML models',
        'command': ['airsenal_run_prediction'],
        'icon': '🔮',
        'color': 'success',
        'estimated_time': '5-10 minutes'
    },
    'optimize_team': {
        'name': 'Optimize Team',
        'description': 'Calculate optimal transfers and team selection',
        'command': ['airsenal_run_optimization'],
        'icon': '⚡',
        'color': 'danger',
        'estimated_time': '3-8 minutes'
    },
    'check_data': {
        'name': 'Check Data',
        'description': 'Run data sanity checks on the database',
        'command': ['airsenal_check_data'],
        'icon': '✅',
        'color': 'secondary',
        'estimated_time': '1-2 minutes'
    },
    'get_transfers': {
        'name': 'Get Transfer Suggestions',
        'description': 'Generate and display recommended transfers without executing them',
        'command': ['python', '-c', 'from airsenal.scripts.fill_transfersuggestion_table import main; main()'],
        'icon': '💡',
        'color': 'info',
        'estimated_time': '2-5 minutes'
    }
}

def parse_process_output(process_id, line):
    """Parse process output to extract progress information"""
    if process_id not in processes:
        return
    
    # Look for common progress indicators
    progress_keywords = {
        'starting': 5, 'initializing': 10, 'setup': 15, 'fetching': 25,
        'processing': 40, 'updating': 60, 'calculating': 70, 'optimizing': 80,
        'finishing': 90, 'complete': 100, 'done': 100, 'finished': 100
    }
    
    line_lower = line.lower()
    for keyword, progress in progress_keywords.items():
        if keyword in line_lower:
            processes[process_id]['progress'] = min(progress, 100)
            processes[process_id]['current_step'] = line.strip()
            break

def cleanup_memory():
    """Force garbage collection to free memory"""
    gc.collect()

def get_current_team_status():
    """Get current team information and transfer suggestions"""
    global team_status, current_transfers
    
    try:
        from airsenal.framework.utils import fetcher
        from airsenal.framework.schema import TransferSuggestion, session
        from sqlalchemy import desc
        
        # Get current team data
        try:
            current_picks = fetcher.get_current_picks()
            bank = fetcher.get_current_bank()
            free_transfers = fetcher.get_num_free_transfers()
            
            team_status = {
                'bank': bank / 10.0,  # Convert to millions
                'free_transfers': free_transfers,
                'team_value': sum(pick['selling_price'] for pick in current_picks) / 10.0,
                'last_updated': datetime.now()
            }
        except Exception as e:
            team_status = {'error': f'Could not fetch team data: {str(e)}'}
        
        # Get latest transfer suggestions
        try:
            suggestions = session.query(TransferSuggestion).order_by(desc(TransferSuggestion.gameweek)).limit(10).all()
            current_transfers = []
            
            for suggestion in suggestions:
                current_transfers.append({
                    'player_out_id': suggestion.player_out,
                    'player_in_id': suggestion.player_in,
                    'gameweek': suggestion.gameweek,
                    'points_gain': suggestion.points_gain,
                    'price_change': suggestion.transfer_cost
                })
                
        except Exception as e:
            current_transfers = []
            
    except ImportError:
        team_status = {'error': 'AIrsenal modules not available'}
        current_transfers = []

def execute_transfers(transfer_list, confirm=False):
    """Execute transfers through the FPL API"""
    try:
        from airsenal.framework.utils import fetcher
        
        if not confirm:
            return {'status': 'error', 'message': 'Transfer confirmation required'}
        
        # Prepare transfer payload for FPL API
        transfers = []
        for transfer in transfer_list:
            transfers.append({
                'element_in': transfer['player_in_id'],
                'element_out': transfer['player_out_id'],
                'selling_price': transfer.get('selling_price'),
                'purchase_price': transfer.get('purchase_price')
            })
        
        transfer_payload = {
            'confirmed': True,
            'transfers': transfers,
            'wildcard': False,
            'freehit': False
        }
        
        # Execute the transfers
        fetcher.post_transfers(transfer_payload)
        
        return {
            'status': 'success', 
            'message': f'Successfully executed {len(transfers)} transfer(s)',
            'transfers': transfers
        }
        
    except Exception as e:
        return {'status': 'error', 'message': f'Transfer failed: {str(e)}'}

def run_airsenal_process(process_id):
    """Run a specific AIrsenal process with progress tracking"""
    if process_id not in AIRSENAL_PROCESSES:
        return
    
    process_info = AIRSENAL_PROCESSES[process_id]
    
    # Initialize process state
    processes[process_id] = {
        'status': 'Running...',
        'progress': 0,
        'current_step': f'Starting {process_info["name"]}...',
        'start_time': datetime.now(),
        'end_time': None
    }
    
    if process_id not in output_logs:
        output_logs[process_id] = []
    
    try:
        timestamp = datetime.now().strftime('%H:%M:%S')
        output_logs[process_id].append(f"[{timestamp}] 🚀 Starting {process_info['name']}...")
        
        # Clean up memory before starting
        cleanup_memory()
        
        # Start the subprocess
        process = subprocess.Popen(
            process_info['command'],
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
                output_logs[process_id].append(f"[{timestamp}] {line}")
                parse_process_output(process_id, line)
                
                # Keep only last 50 log entries per process to save memory
                if len(output_logs[process_id]) > 50:
                    output_logs[process_id] = output_logs[process_id][-50:]
        
        # Check result
        return_code = process.poll()
        processes[process_id]['end_time'] = datetime.now()
        
        # Clean up memory after completion
        cleanup_memory()
        
        if return_code == 0:
            processes[process_id]['status'] = 'Completed successfully'
            processes[process_id]['progress'] = 100
            processes[process_id]['current_step'] = f'{process_info["name"]} completed'
            output_logs[process_id].append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {process_info['name']} completed successfully")
        else:
            processes[process_id]['status'] = f'Failed with code {return_code}'
            processes[process_id]['progress'] = 0
            processes[process_id]['current_step'] = f'{process_info["name"]} failed'
            output_logs[process_id].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {process_info['name']} failed with code {return_code}")
        
    except Exception as e:
        processes[process_id]['status'] = f'Error: {str(e)}'
        processes[process_id]['progress'] = 0
        processes[process_id]['current_step'] = 'Error occurred'
        processes[process_id]['end_time'] = datetime.now()
        output_logs[process_id].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {str(e)}")
    
    finally:
        # Final memory cleanup
        cleanup_memory()

# Simple HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AIrsenal Control Center</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .main-container { background: white; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); padding: 30px; }
        .process-card { border: none; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; transition: transform 0.2s; }
        .process-card:hover { transform: translateY(-2px); }
        .process-icon { font-size: 2rem; margin-right: 15px; }
        .progress-mini { height: 8px; border-radius: 4px; }
        .log-container { background: #2c3e50; border-radius: 10px; max-height: 300px; overflow-y: auto; }
        .log-content { color: #ecf0f1; font-family: 'Courier New', monospace; font-size: 12px; padding: 15px; }
        .status-badge { font-size: 0.8rem; }
        .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .info-card { background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db; }
        .running { animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
        .btn-process { margin: 5px; }
        .process-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="main-container">
            <h1 class="text-center mb-4">🏈 AIrsenal Control Center</h1>
            
            <div class="info-grid">
                <div class="info-card">
                    <strong>FPL Team ID:</strong><br>
                    <span class="text-muted">{{ fpl_team_id or 'Not configured' }}</span>
                </div>
                <div class="info-card">
                    <strong>Server Time:</strong><br>
                    <span class="text-muted">{{ current_time }}</span>
                </div>
                <div class="info-card">
                    <strong>Active Processes:</strong><br>
                    <span class="text-muted" id="active-count">{{ active_processes }}</span>
                </div>
                <div class="info-card">
                    <strong>Memory Optimized:</strong><br>
                    <span class="text-success">✅ Lightweight mode</span>
                </div>
            </div>
            
            <div class="row mb-4">
                <div class="col-12">
                    <h3>🎮 Memory-Optimized Actions</h3>
                    <div class="alert alert-info">
                        <strong>💡 Tip:</strong> Run processes individually to avoid memory issues. Wait for each to complete before starting the next.
                    </div>
                    <button class="btn btn-info btn-process" onclick="runProcess('setup_db_minimal')">🗄️ Setup Database</button>
                    <button class="btn btn-warning btn-process" onclick="runProcess('update_db_lite')">🔄 Update Database</button>
                    <button class="btn btn-success btn-process" onclick="runProcess('run_predictions')">🔮 Run Predictions</button>
                    <button class="btn btn-danger btn-process" onclick="runProcess('optimize_team')">⚡ Optimize Team</button>
                    <button class="btn btn-primary btn-process" onclick="runProcess('get_transfers')">💡 Get Transfers</button>
                    <button class="btn btn-outline-secondary btn-process" onclick="clearAllLogs()">🗑️ Clear Logs</button>
                </div>
            </div>
            
            <h3>📊 Process Monitor</h3>
            <div class="process-grid" id="process-grid">
                <!-- Process cards will be populated by JavaScript -->
            </div>
            
            <div class="row mt-4">
                <div class="col-12">
                    <h4>📋 Selected Process Log</h4>
                    <div class="mb-2">
                        <select class="form-select" id="log-selector" onchange="changeLogView()">
                            <option value="">Select a process to view logs...</option>
                        </select>
                    </div>
                    <div class="log-container">
                        <div class="log-content" id="selected-log">Select a process above to view its logs...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let autoRefresh = true;
        let refreshInterval;
        let selectedLogProcess = '';
        
        const processes = {{ processes | tojsonfilter }};
        
        function updateProcessGrid() {
            fetch('/status/all')
                .then(response => response.json())
                .then(data => {
                    const grid = document.getElementById('process-grid');
                    const logSelector = document.getElementById('log-selector');
                    
                    // Update active process count
                    const activeCount = Object.values(data.processes).filter(p => p.status === 'Running...').length;
                    document.getElementById('active-count').textContent = activeCount;
                    
                    // Clear and rebuild process grid
                    grid.innerHTML = '';
                    logSelector.innerHTML = '<option value="">Select a process to view logs...</option>';
                    
                    Object.entries(processes).forEach(([id, info]) => {
                        const processData = data.processes[id] || { status: 'Not started', progress: 0, current_step: 'Ready' };
                        
                        // Add to log selector
                        logSelector.innerHTML += `<option value="${id}">${info.name}</option>`;
                        
                        // Create process card
                        const card = document.createElement('div');
                        card.className = 'card process-card';
                        
                        const isRunning = processData.status === 'Running...';
                        const statusClass = getStatusClass(processData.status);
                        
                        card.innerHTML = `
                            <div class="card-header d-flex align-items-center ${isRunning ? 'running' : ''}">
                                <span class="process-icon">${info.icon}</span>
                                <div class="flex-grow-1">
                                    <h5 class="mb-0">${info.name}</h5>
                                    <small class="text-muted">${info.estimated_time}</small>
                                </div>
                                <span class="badge bg-${statusClass} status-badge">${processData.status}</span>
                            </div>
                            <div class="card-body">
                                <p class="card-text text-muted mb-3">${info.description}</p>
                                <div class="mb-2">
                                    <small class="text-muted">Current Step:</small><br>
                                    <span class="fw-bold">${processData.current_step}</span>
                                </div>
                                <div class="progress progress-mini mb-3">
                                    <div class="progress-bar bg-${info.color}" style="width: ${processData.progress}%"></div>
                                </div>
                                <div class="d-flex justify-content-between align-items-center">
                                    <small class="text-muted">${processData.progress}% Complete</small>
                                    <div>
                                        <button class="btn btn-${info.color} btn-sm" 
                                                onclick="runProcess('${id}')" 
                                                ${isRunning ? 'disabled' : ''}>
                                            ${isRunning ? '⏳ Running...' : '▶️ Start'}
                                        </button>
                                        <button class="btn btn-outline-secondary btn-sm" 
                                                onclick="viewLogs('${id}')">
                                            📋 Logs
                                        </button>
                                    </div>
                                </div>
                            </div>
                        `;
                        
                        grid.appendChild(card);
                    });
                    
                    // Update selected log view
                    if (selectedLogProcess && data.logs[selectedLogProcess]) {
                        updateSelectedLog(data.logs[selectedLogProcess]);
                    }
                })
                .catch(error => console.error('Error:', error));
        }
        
        function getStatusClass(status) {
            if (status.includes('Running')) return 'warning';
            if (status.includes('success') || status.includes('Completed')) return 'success';
            if (status.includes('Error') || status.includes('Failed')) return 'danger';
            return 'secondary';
        }
        
        function runProcess(processId) {
            fetch(`/run-process/${processId}`, {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        updateProcessGrid();
                    } else {
                        alert(data.message);
                    }
                })
                .catch(error => console.error('Error:', error));
        }
        
        function viewLogs(processId) {
            selectedLogProcess = processId;
            document.getElementById('log-selector').value = processId;
            changeLogView();
        }
        
        function changeLogView() {
            selectedLogProcess = document.getElementById('log-selector').value;
            if (selectedLogProcess) {
                fetch(`/logs/${selectedLogProcess}`)
                    .then(response => response.json())
                    .then(data => {
                        updateSelectedLog(data.logs);
                    })
                    .catch(error => console.error('Error:', error));
            } else {
                document.getElementById('selected-log').innerHTML = 'Select a process above to view its logs...';
            }
        }
        
        function updateSelectedLog(logs) {
            const logContainer = document.getElementById('selected-log');
            logContainer.innerHTML = logs.map(log => `<div>${log}</div>`).join('');
            logContainer.scrollTop = logContainer.scrollHeight;
        }
        
        function clearAllLogs() {
            if (confirm('Are you sure you want to clear all logs?')) {
                fetch('/clear-logs', {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        alert(data.message);
                        updateProcessGrid();
                    })
                    .catch(error => console.error('Error:', error));
            }
        }
        
        // Start auto-refresh when page loads
        window.onload = function() {
            updateProcessGrid();
            refreshInterval = setInterval(updateProcessGrid, 5000);
        }
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Main dashboard page"""
    active_processes = len([p for p in processes.values() if p['status'] == 'Running...'])
    
    return render_template_string(
        HTML_TEMPLATE,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        fpl_team_id=os.getenv('FPL_TEAM_ID'),
        active_processes=active_processes,
        processes=AIRSENAL_PROCESSES
    )

@app.route('/run-process/<process_id>', methods=['POST'])
def run_process(process_id):
    """API endpoint to trigger a specific process"""
    if process_id not in AIRSENAL_PROCESSES:
        return jsonify({"status": "error", "message": "Invalid process ID"})
    
    if process_id in processes and processes[process_id]['status'] == 'Running...':
        return jsonify({"status": "error", "message": "Process already running"})
    
    # Start process in background thread
    thread = threading.Thread(target=run_airsenal_process, args=(process_id,))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "success", "message": f"{AIRSENAL_PROCESSES[process_id]['name']} started"})

@app.route('/status/all')
def get_all_status():
    """API endpoint to get status of all processes"""
    return jsonify({
        "processes": processes,
        "logs": {pid: logs[-20:] for pid, logs in output_logs.items()}
    })

@app.route('/logs/<process_id>')
def get_process_logs(process_id):
    """API endpoint to get logs for a specific process"""
    if process_id in output_logs:
        return jsonify({"logs": output_logs[process_id][-50:]})
    return jsonify({"logs": []})

@app.route('/clear-logs', methods=['POST'])
def clear_all_logs():
    """API endpoint to clear all logs"""
    global output_logs
    output_logs = {}
    return jsonify({"status": "success", "message": "All logs cleared"})

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    # Get port from environment variable
    port = int(os.environ.get('PORT', 10000))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=False)
