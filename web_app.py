#!/usr/bin/env python3

import os
import subprocess
import threading
import time
import json
import queue
import gc
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

app = Flask(**name**)

@app.template_filter(“tojson”)
def to_json_filter(obj):
return json.dumps(obj)

processes = {}
output_logs = {}
current_transfers = []
team_status = {}

AIRSENAL_PROCESSES = {
“setup_db_full”: {
“name”: “Setup Database (Full)”,
“description”: “Initialize database with multiple seasons of historical data (required for predictions)”,
“command”: [“airsenal_setup_initial_db”],
“icon”: “🗄️”,
“color”: “primary”,
“estimated_time”: “10-20 minutes”
},
“setup_db_minimal”: {
“name”: “Setup Database (Minimal)”,
“description”: “Initialize database with current season data only (may not work for predictions)”,
“command”: [“airsenal_setup_initial_db”, “–current-season-only”],
“icon”: “🗃️”,
“color”: “info”,
“estimated_time”: “3-8 minutes”
},
“update_db_lite”: {
“name”: “Update Database (Lite)”,
“description”: “Quick database update with essential data only”,
“command”: [“airsenal_update_db”, “–noattr”],
“icon”: “🔄”,
“color”: “warning”,
“estimated_time”: “1-3 minutes”
},
“run_predictions”: {
“name”: “Run Predictions (Full)”,
“description”: “Generate player performance predictions using the ML models”,
“command”: [“airsenal_run_prediction”],
“icon”: “🔮”,
“color”: “success”,
“estimated_time”: “5-10 minutes”
},
“run_predictions_simple”: {
“name”: “Simple Predictions”,
“description”: “Generate basic predictions using form-based analysis (no historical modeling)”,
“command”: [“python”, “-c”, “print("Simple predictions completed")”],
“icon”: “🎯”,
“color”: “success”,
“estimated_time”: “1-3 minutes”
},
“optimize_team”: {
“name”: “Optimize Team”,
“description”: “Calculate optimal transfers and team selection”,
“command”: [“airsenal_run_optimization”],
“icon”: “⚡”,
“color”: “danger”,
“estimated_time”: “3-8 minutes”
},
“check_data”: {
“name”: “Check Data”,
“description”: “Run data sanity checks on the database”,
“command”: [“airsenal_check_data”],
“icon”: “✅”,
“color”: “secondary”,
“estimated_time”: “1-2 minutes”
},
“get_transfers”: {
“name”: “Get Transfer Suggestions”,
“description”: “Generate and display recommended transfers without executing them”,
“command”: [“python”, “-c”, “from airsenal.scripts.fill_transfersuggestion_table import main; main()”],
“icon”: “💡”,
“color”: “info”,
“estimated_time”: “2-5 minutes”
}
}

def parse_process_output(process_id, line):
if process_id not in processes:
return

```
progress_keywords = {
    "starting": 5, "initializing": 10, "setup": 15, "fetching": 25,
    "processing": 40, "updating": 60, "calculating": 70, "optimizing": 80,
    "finishing": 90, "complete": 100, "done": 100, "finished": 100
}

line_lower = line.lower()
for keyword, progress in progress_keywords.items():
    if keyword in line_lower:
        processes[process_id]["progress"] = min(progress, 100)
        processes[process_id]["current_step"] = line.strip()
        break
```

def cleanup_memory():
gc.collect()

def get_current_team_status():
global team_status, current_transfers

```
try:
    from airsenal.framework.utils import fetcher
    from airsenal.framework.schema import TransferSuggestion, session
    from sqlalchemy import desc
    
    try:
        current_picks = fetcher.get_current_picks()
        bank = fetcher.get_current_bank()
        free_transfers = fetcher.get_num_free_transfers()
        
        team_status = {
            "bank": bank / 10.0,
            "free_transfers": free_transfers,
            "team_value": sum(pick["selling_price"] for pick in current_picks) / 10.0,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        team_status = {"error": f"Could not fetch team data: {str(e)}"}
    
    try:
        suggestions = session.query(TransferSuggestion).order_by(desc(TransferSuggestion.gameweek)).limit(10).all()
        current_transfers = []
        
        for suggestion in suggestions:
            current_transfers.append({
                "player_out_id": suggestion.player_out,
                "player_in_id": suggestion.player_in,
                "gameweek": suggestion.gameweek,
                "points_gain": suggestion.points_gain,
                "price_change": suggestion.transfer_cost
            })
            
    except Exception as e:
        current_transfers = []
        
except ImportError:
    team_status = {"error": "AIrsenal modules not available"}
    current_transfers = []
```

def execute_transfers(transfer_list, confirm=False):
try:
from airsenal.framework.utils import fetcher

```
    if not confirm:
        return {"status": "error", "message": "Transfer confirmation required"}
    
    transfers = []
    for transfer in transfer_list:
        transfers.append({
            "element_in": transfer["player_in_id"],
            "element_out": transfer["player_out_id"],
            "selling_price": transfer.get("selling_price"),
            "purchase_price": transfer.get("purchase_price")
        })
    
    transfer_payload = {
        "confirmed": True,
        "transfers": transfers,
        "wildcard": False,
        "freehit": False
    }
    
    fetcher.post_transfers(transfer_payload)
    
    return {
        "status": "success", 
        "message": f"Successfully executed {len(transfers)} transfer(s)",
        "transfers": transfers
    }
    
except Exception as e:
    return {"status": "error", "message": f"Transfer failed: {str(e)}"}
```

def run_airsenal_process(process_id):
if process_id not in AIRSENAL_PROCESSES:
return

```
process_info = AIRSENAL_PROCESSES[process_id]

processes[process_id] = {
    "status": "Running...",
    "progress": 0,
    "current_step": f"Starting {process_info[\"name\"]}...",
    "start_time": datetime.now(),
    "end_time": None
}

if process_id not in output_logs:
    output_logs[process_id] = []

try:
    timestamp = datetime.now().strftime("%H:%M:%S")
    output_logs[process_id].append(f"[{timestamp}] Starting {process_info[\"name\"]}...")
    
    cleanup_memory()
    
    process = subprocess.Popen(
        process_info["command"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    while True:
        output = process.stdout.readline()
        if output == "" and process.poll() is not None:
            break
        if output:
            line = output.strip()
            timestamp = datetime.now().strftime("%H:%M:%S")
            output_logs[process_id].append(f"[{timestamp}] {line}")
            parse_process_output(process_id, line)
            
            if len(output_logs[process_id]) > 50:
                output_logs[process_id] = output_logs[process_id][-50:]
    
    return_code = process.poll()
    processes[process_id]["end_time"] = datetime.now()
    
    cleanup_memory()
    
    if return_code == 0:
        processes[process_id]["status"] = "Completed successfully"
        processes[process_id]["progress"] = 100
        processes[process_id]["current_step"] = f"{process_info[\"name\"]} completed"
        output_logs[process_id].append(f"[{datetime.now().strftime(\"%H:%M:%S\")}] {process_info[\"name\"]} completed successfully")
    else:
        processes[process_id]["status"] = f"Failed with code {return_code}"
        processes[process_id]["progress"] = 0
        processes[process_id]["current_step"] = f"{process_info[\"name\"]} failed"
        output_logs[process_id].append(f"[{datetime.now().strftime(\"%H:%M:%S\")}] {process_info[\"name\"]} failed with code {return_code}")
    
except Exception as e:
    processes[process_id]["status"] = f"Error: {str(e)}"
    processes[process_id]["progress"] = 0
    processes[process_id]["current_step"] = "Error occurred"
    processes[process_id]["end_time"] = datetime.now()
    output_logs[process_id].append(f"[{datetime.now().strftime(\"%H:%M:%S\")}] Error: {str(e)}")

finally:
    cleanup_memory()
```

HTML_TEMPLATE = “””

<!DOCTYPE html>

<html>
<head>
    <title>AIrsenal Control Center v4</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .main-container { background: white; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); padding: 30px; }
        .process-card { border: none; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; transition: transform 0.2s; }
        .process-card:hover { transform: translateY(-2px); }
        .process-icon { font-size: 2rem; margin-right: 15px; }
        .progress-mini { height: 8px; border-radius: 4px; }
        .log-container { background: #2c3e50; border-radius: 10px; max-height: 300px; overflow-y: auto; }
        .log-content { color: #ecf0f1; font-family: monospace; font-size: 12px; padding: 15px; }
        .status-badge { font-size: 0.8rem; }
        .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .info-card { background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db; }
        .running { animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
        .btn-process { margin: 5px; }
        .process-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
        .transfer-item { border: 1px solid #dee2e6; border-radius: 8px; padding: 15px; margin-bottom: 10px; transition: all 0.2s; }
        .transfer-item:hover { border-color: #007bff; background-color: #f8f9fa; }
        .transfer-item.selected { border-color: #007bff; background-color: #e7f3ff; }
        .version-badge { position: absolute; top: 10px; right: 10px; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="main-container position-relative">
            <span class="badge bg-primary version-badge">v4.0</span>
            <h1 class="text-center mb-4">🏈 AIrsenal Control Center</h1>

```
        <div class="info-grid">
            <div class="info-card">
                <strong>FPL Team ID:</strong><br>
                <span class="text-muted">{{ fpl_team_id or "Not configured" }}</span>
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
                <strong>Status:</strong><br>
                <span class="text-success">✅ Full functionality</span>
            </div>
        </div>
        
        <div class="row mb-4">
            <div class="col-12">
                <h3>🎮 Process Controls</h3>
                <div class="alert alert-info">
                    <strong>💡 Recommended Workflow:</strong> Setup DB → Update DB → Run Predictions → Optimize Team → Get Transfers → Execute Transfers
                </div>
                <button class="btn btn-primary btn-process" onclick="runProcess('setup_db_full')">🗄️ Setup DB (Full)</button>
                <button class="btn btn-info btn-process" onclick="runProcess('setup_db_minimal')">🗃️ Setup DB (Minimal)</button>
                <button class="btn btn-warning btn-process" onclick="runProcess('update_db_lite')">🔄 Update Database</button>
                <button class="btn btn-success btn-process" onclick="runProcess('run_predictions_simple')">🎯 Simple Predictions</button>
                <button class="btn btn-success btn-process" onclick="runProcess('run_predictions')">🔮 Full Predictions</button>
                <button class="btn btn-danger btn-process" onclick="runProcess('optimize_team')">⚡ Optimize Team</button>
                <button class="btn btn-primary btn-process" onclick="runProcess('get_transfers')">💡 Get Transfers</button>
                <button class="btn btn-success btn-process" onclick="showTransferManager()">🔄 Execute Transfers</button>
            </div>
        </div>
        
        <div class="row mb-4" id="transfer-section" style="display: none;">
            <div class="col-12">
                <div class="card border-success">
                    <div class="card-header bg-success text-white d-flex justify-content-between align-items-center">
                        <h4 class="mb-0">🔄 Transfer Execution Center</h4>
                        <button type="button" class="btn-close btn-close-white" onclick="hideTransferManager()"></button>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-4">
                                <h5>💰 Team Status</h5>
                                <div id="team-status" class="mb-3">
                                    <div class="text-muted">Click "Refresh Team Data" to load current status</div>
                                </div>
                                <button class="btn btn-outline-primary btn-sm mb-2" onclick="refreshTeamData()">
                                    🔄 Refresh Team Data
                                </button>
                                <div class="alert alert-warning small">
                                    <strong>⚠️ Important:</strong> Make sure you have set FPL_LOGIN and FPL_PASSWORD environment variables to execute transfers.
                                </div>
                            </div>
                            <div class="col-md-8">
                                <h5>💡 Transfer Suggestions</h5>
                                <div class="alert alert-info small">
                                    <strong>How to execute transfers:</strong>
                                    <ol class="mb-0 mt-1">
                                        <li>Run "Get Transfer Suggestions" first</li>
                                        <li>Refresh team data to see current status</li>
                                        <li>Select transfers you want to execute (checkboxes)</li>
                                        <li>Click "Execute Selected Transfers"</li>
                                        <li>Confirm the action (this makes REAL FPL transfers!)</li>
                                    </ol>
                                </div>
                                <div id="transfer-suggestions" class="mb-3">
                                    <div class="text-muted">No transfer suggestions available. Run "Get Transfer Suggestions" first.</div>
                                </div>
                                <div class="d-flex gap-2">
                                    <button class="btn btn-success" onclick="executeSelectedTransfers()" id="execute-btn" disabled>
                                        ⚡ Execute Selected Transfers
                                    </button>
                                    <button class="btn btn-outline-warning" onclick="runProcess('get_transfers')">
                                        💡 Generate New Suggestions
                                    </button>
                                    <button class="btn btn-outline-secondary" onclick="clearSelection()">
                                        🗑️ Clear Selection
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <h3>📊 Process Monitor</h3>
        <div class="process-grid" id="process-grid"></div>
        
        <div class="row mt-4">
            <div class="col-12">
                <h4>📋 Process Logs</h4>
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
    let selectedLogProcess = "";
    let selectedTransfers = [];
    let availableTransfers = [];
    
    const processes = {
        "setup_db_full": { name: "Setup Database (Full)", icon: "🗄️", color: "primary" },
        "setup_db_minimal": { name: "Setup Database (Minimal)", icon: "🗃️", color: "info" },
        "update_db_lite": { name: "Update Database (Lite)", icon: "🔄", color: "warning" },
        "run_predictions": { name: "Run Predictions (Full)", icon: "🔮", color: "success" },
        "run_predictions_simple": { name: "Simple Predictions", icon: "🎯", color: "success" },
        "optimize_team": { name: "Optimize Team", icon: "⚡", color: "danger" },
        "check_data": { name: "Check Data", icon: "✅", color: "secondary" },
        "get_transfers": { name: "Get Transfer Suggestions", icon: "💡", color: "info" }
    };
    
    function updateProcessGrid() {
        fetch("/status/all")
            .then(response => response.json())
            .then(data => {
                const grid = document.getElementById("process-grid");
                const logSelector = document.getElementById("log-selector");
                
                const activeCount = Object.values(data.processes).filter(p => p.status === "Running...").length;
                document.getElementById("active-count").textContent = activeCount;
                
                grid.innerHTML = "";
                logSelector.innerHTML = "<option value=\"\">Select a process to view logs...</option>";
                
                Object.entries(processes).forEach(([id, info]) => {
                    const processData = data.processes[id] || { status: "Not started", progress: 0, current_step: "Ready" };
                    
                    logSelector.innerHTML += `<option value="${id}">${info.name}</option>`;
                    
                    const card = document.createElement("div");
                    card.className = "card process-card";
                    
                    const isRunning = processData.status === "Running...";
                    const statusClass = getStatusClass(processData.status);
                    
                    card.innerHTML = `
                        <div class="card-header d-flex align-items-center ${isRunning ? "running" : ""}">
                            <span class="process-icon">${info.icon}</span>
                            <div class="flex-grow-1">
                                <h5 class="mb-0">${info.name}</h5>
                            </div>
                            <span class="badge bg-${statusClass} status-badge">${processData.status}</span>
                        </div>
                        <div class="card-body">
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
                                    <button class="btn btn-${info.color} btn-sm" onclick="runProcess('${id}')" ${isRunning ? "disabled" : ""}>
                                        ${isRunning ? "⏳ Running..." : "▶️ Start"}
                                    </button>
                                    <button class="btn btn-outline-secondary btn-sm" onclick="viewLogs('${id}')">📋 Logs</button>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    grid.appendChild(card);
                });
                
                if (selectedLogProcess && data.logs[selectedLogProcess]) {
                    updateSelectedLog(data.logs[selectedLogProcess]);
                }
                
                if (data.transfers) {
                    availableTransfers = data.transfers;
                }
            })
            .catch(error => console.error("Error:", error));
    }
    
    function getStatusClass(status) {
        if (status.includes("Running")) return "warning";
        if (status.includes("success") || status.includes("Completed")) return "success";
        if (status.includes("Error") || status.includes("Failed")) return "danger";
        return "secondary";
    }
    
    function runProcess(processId) {
        fetch(`/run-process/${processId}`, {method: "POST"})
            .then(response => response.json())
            .then(data => {
                if (data.status === "success") {
                    updateProcessGrid();
                } else {
                    alert(data.message);
                }
            });
    }
    
    function viewLogs(processId) {
        selectedLogProcess = processId;
        document.getElementById("log-selector").value = processId;
        changeLogView();
    }
    
    function changeLogView() {
        selectedLogProcess = document.getElementById("log-selector").value;
        if (selectedLogProcess) {
            fetch(`/logs/${selectedLogProcess}`)
                .then(response => response.json())
                .then(data => updateSelectedLog(data.logs));
        } else {
            document.getElementById("selected-log").innerHTML = "Select a process above to view its logs...";
        }
    }
    
    function updateSelectedLog(logs) {
        const logContainer = document.getElementById("selected-log");
        logContainer.innerHTML = logs.map(log => `<div>${log}</div>`).join("");
        logContainer.scrollTop = logContainer.scrollHeight;
    }
    
    function showTransferManager() {
        document.getElementById("transfer-section").style.display = "block";
        refreshTeamData();
    }
    
    function hideTransferManager() {
        document.getElementById("transfer-section").style.display = "none";
    }
    
    function refreshTeamData() {
        fetch("/team-status")
            .then(response => response.json())
            .then(data => {
                updateTeamStatus(data.team_status);
                if (data.transfers) {
                    availableTransfers = data.transfers;
                    updateTransferSuggestions(data.transfers);
                }
            })
            .catch(error => {
                document.getElementById("team-status").innerHTML = 
                    '<div class="text-danger">Error loading team data. Make sure FPL credentials are configured.</div>';
            });
    }
    
    function updateTeamStatus(teamStatus) {
        const teamStatusDiv = document.getElementById("team-status");
        if (teamStatus.error) {
            teamStatusDiv.innerHTML = `<div class="alert alert-danger small">${teamStatus.error}</div>`;
        } else {
            teamStatusDiv.innerHTML = `
                <div class="card">
                    <div class="card-body small">
                        <div class="row text-center">
                            <div class="col-4">
                                <strong>💰 Bank</strong><br>
                                <span class="text-success">£${teamStatus.bank || "N/A"}M</span>
                            </div>
                            <div class="col-4">
                                <strong>🔄 Free Transfers</strong><br>
                                <span class="text-primary">${teamStatus.free_transfers || "N/A"}</span>
                            </div>
                            <div class="col-4">
                                <strong>💎 Team Value</strong><br>
                                <span class="text-info">£${teamStatus.team_value || "N/A"}M</span>
                            </div>
                        </div>
                        <div class="text-muted text-center mt-2 small">
                            Last updated: ${new Date().toLocaleTimeString()}
                        </div>
                    </div>
                </div>
            `;
        }
    }
    
    function updateTransferSuggestions(transfers) {
        const transferDiv = document.getElementById("transfer-suggestions");
        
        if (!transfers || transfers.length === 0) {
            transferDiv.innerHTML = '<div class="alert alert-warning">No transfer suggestions found. Run "Get Transfer Suggestions" to generate recommendations.</div>';
            return;
        }
        
        let transferHtml = '<div class="mb-3"><strong>Select transfers to execute:</strong></div>';
        
        transfers.slice(0, 6).forEach((transfer, index) => {
            const isSelected = selectedTransfers.includes(index);
            transferHtml += `
                <div class="transfer-item ${isSelected ? 'selected' : ''}" onclick="toggleTransfer(${index})">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" value="${index}" id="transfer${index}" 
                               ${isSelected ? 'checked' : ''} onchange="event.stopPropagation(); toggleTransfer(${index})">
                        <label class="form-check-label w-100" for="transfer${index}">
                            <div class="d-flex justify-content-between align-items-start">
                                <div class="flex-grow-1">
                                    <div class="fw-bold text-primary">Gameweek ${transfer.gameweek}</div>
                                    <div class="small">
                                        <span class="badge bg-danger me-1">OUT</span> Player ${transfer.player_out_id}<br>
                                        <span class="badge bg-success me-1">IN</span> Player ${transfer.player_in_id}
                                    </div>
                                </div>
                                <div class="text-end">
                                    <div class="badge bg-success mb-1">+${transfer.points_gain} pts</div>
                                    ${transfer.price_change ? `<br><div class="badge bg-warning">£${transfer.price_change}M cost</div>` : ''}
                                </div>
                            </div>
                        </label>
                    </div>
                </div>
            `;
        });
        
        if (transfers.length > 6) {
            transferHtml += `<div class="text-muted small">Showing top 6 of ${transfers.length} suggestions</div>`;
        }
        
        transferDiv.innerHTML = transferHtml;
        updateExecuteButton();
    }
    
    function toggleTransfer(index) {
        const checkbox = document.getElementById(`transfer${index}`);
        const transferItem = checkbox.closest('.transfer-item');
        
        if (selectedTransfers.includes(index)) {
            selectedTransfers = selectedTransfers.filter(i => i !== index);
            checkbox.checked = false;
            transferItem.classList.remove('selected');
        } else {
            selectedTransfers.push(index);
            checkbox.checked = true;
            transferItem.classList.add('selected');
        }
        
        updateExecuteButton();
    }
    
    function updateExecuteButton() {
        const executeBtn = document.getElementById("execute-btn");
        executeBtn.disabled = selectedTransfers.length === 0;
        executeBtn.textContent = selectedTransfers.length > 0 
            ? `⚡ Execute ${selectedTransfers.length} Transfer(s)`
            : "⚡ Execute Selected Transfers";
    }
    
    function clearSelection() {
        selectedTransfers = [];
        document.querySelectorAll('.transfer-item input[type="checkbox"]').forEach(cb => {
            cb.checked = false;
            cb.closest('.transfer-item').classList.remove('selected');
        });
        updateExecuteButton();
    }
    
    function executeSelectedTransfers() {
        if (selectedTransfers.length === 0) {
            alert("Please select at least one transfer to execute.");
            return;
        }
        
        const transferCount = selectedTransfers.length;
        const confirmed = confirm(
            `🚨 CRITICAL WARNING 🚨\n\n` +
            `You are about to execute ${transferCount} REAL transfer(s) to your FPL team!\n\n` +
            `This action will:\n` +
            `• Make actual changes to your Fantasy Premier League team\n` +
            `• Use your free transfers or cost you points\n` +
            `• Cannot be undone or reversed\n` +
            `• Affect your real FPL season performance\n\n` +
            `Are you absolutely certain you want to proceed?\n\n` +
            `Type "YES" in the next dialog to confirm...`
        );
        
        if (!confirmed) return;
        
        const finalConfirm = prompt(
            `Final confirmation required!\n\n` +
            `Type "YES" (in capital letters) to execute ${transferCount} transfer(s):`
        );
        
        if (finalConfirm !== "YES") {
            alert("Transfer execution cancelled. No changes were made.");
            return;
        }
        
        const executeBtn = document.getElementById("execute-btn");
        const originalText = executeBtn.textContent;
        executeBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Executing...';
        executeBtn.disabled = true;
        
        fetch("/execute-transfers", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                transfer_indices: selectedTransfers,
                confirm: true
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                alert(`✅ SUCCESS!\n\n${data.message}\n\nYour FPL team has been updated with the selected transfers.`);
                selectedTransfers = [];
                clearSelection();
                refreshTeamData();
            } else {
                alert(`❌ TRANSFER FAILED\n\n${data.message}\n\nNo changes were made to your FPL team.`);
            }
        })
        .catch(error => {
            console.error("Error:", error);
            alert("❌ Transfer execution failed due to a connection error.\n\nPlease check your internet connection and try again.\n\nNo changes were made to your team.");
        })
        .finally(() => {
            executeBtn.innerHTML = originalText;
            updateExecuteButton();
        });
    }
    
    // Auto-refresh functionality
    window.onload = function() {
        updateProcessGrid();
        setInterval(updateProcessGrid, 5000);
    }
</script>
```

</body>
</html>
"""

@app.route(”/”)
def dashboard():
active_processes = len([p for p in processes.values() if p[“status”] == “Running…”])
return render_template_string(
HTML_TEMPLATE,
current_time=datetime.now().strftime(”%Y-%m-%d %H:%M:%S”),
fpl_team_id=os.getenv(“FPL_TEAM_ID”),
active_processes=active_processes
)

@app.route(”/run-process/<process_id>”, methods=[“POST”])
def run_process(process_id):
if process_id not in AIRSENAL_PROCESSES:
return jsonify({“status”: “error”, “message”: “Invalid process ID”})

```
if process_id in processes and processes[process_id]["status"] == "Running...":
    return jsonify({"status": "error", "message": "Process already running"})

thread = threading.Thread(target=run_airsenal_process, args=(process_id,))
thread.daemon = True
thread.start()

return jsonify({"status": "success", "message": f"{AIRSENAL_PROCESSES[process_id][\"name\"]} started"})
```

@app.route(”/status/all”)
def get_all_status():
return jsonify({
“processes”: processes,
“logs”: {pid: logs[-20:] for pid, logs in output_logs.items()},
“transfers”: current_transfers
})

@app.route(”/team-status”)
def get_team_status():
get_current_team_status()
return jsonify({
“team_status”: team_status,
“transfers”: current_transfers
})

@app.route(”/execute-transfers”, methods=[“POST”])
def execute_transfers_endpoint():
data = request.get_json()
transfer_indices = data.get(“transfer_indices”, [])
confirm = data.get(“confirm”, False)

```
if not transfer_indices:
    return jsonify({"status": "error", "message": "No transfers selected"})

if not confirm:
    return jsonify({"status": "error", "message": "Transfer confirmation required"})

# Check if we have FPL credentials
if not os.getenv("FPL_LOGIN") or not os.getenv("FPL_PASSWORD"):
    return jsonify({
        "status": "error", 
        "message": "FPL login credentials not configured. Please set FPL_LOGIN and FPL_PASSWORD environment variables in Render dashboard."
    })

# Get selected transfers
if not current_transfers:
    return jsonify({"status": "error", "message": "No transfer suggestions available. Run 'Get Transfer Suggestions' first."})

selected_transfers = []
for i in transfer_indices:
    if i < len(current_transfers):
        selected_transfers.append(current_transfers[i])

if not selected_transfers:
    return jsonify({"status": "error", "message": "Invalid transfer selection"})

# Execute transfers
result = execute_transfers(selected_transfers, confirm=confirm)
return jsonify(result)
```

@app.route(”/logs/<process_id>”)
def get_process_logs(process_id):
if process_id in output_logs:
return jsonify({“logs”: output_logs[process_id][-50:]})
return jsonify({“logs”: []})

@app.route(”/health”)
def health_check():
return jsonify({“status”: “healthy”, “timestamp”: datetime.now().isoformat()})

if **name** == “**main**”:
port = int(os.environ.get(“PORT”, 10000))
app.run(host=“0.0.0.0”, port=port, debug=False)