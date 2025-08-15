#!/usr/bin/env python
"""
Simple web application for AIrsenal using Flask
This file creates a basic web interface for the AIrsenal Fantasy Premier League optimization tool.
"""

from flask import Flask, render_template_string, request, jsonify
import subprocess
import json
import os
import sys
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the airsenal directory to the Python path
sys.path.insert(0, '/airsenal')

# Set up environment variables if not already set
if 'AIRSENAL_HOME' not in os.environ:
    os.environ['AIRSENAL_HOME'] = '/tmp'

app = Flask(__name__)

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AIrsenal - Fantasy Premier League Optimizer</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .container {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input, select {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
            margin-top: 10px;
        }
        button:hover {
            background-color: #45a049;
        }
        button:disabled {
            background-color: #cccccc;
            cursor: not-allowed;
        }
        .output {
            background-color: #f0f0f0;
            padding: 10px;
            border-radius: 4px;
            margin-top: 20px;
            white-space: pre-wrap;
            font-family: monospace;
            max-height: 400px;
            overflow-y: auto;
        }
        .error {
            color: red;
            margin-top: 10px;
        }
        .success {
            color: green;
            margin-top: 10px;
        }
        .spinner {
            display: none;
            margin-left: 10px;
        }
        .spinning {
            display: inline-block;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <h1>⚽ AIrsenal - Fantasy Premier League Optimizer</h1>
    
    <div class="container">
        <h2>Configuration</h2>
        <div class="form-group">
            <label for="fpl_team_id">FPL Team ID:</label>
            <input type="text" id="fpl_team_id" placeholder="Enter your FPL Team ID" value="{{ fpl_team_id }}">
        </div>
        
        <div class="form-group">
            <label for="weeks_ahead">Weeks to Look Ahead:</label>
            <select id="weeks_ahead">
                <option value="1">1 Week</option>
                <option value="2">2 Weeks</option>
                <option value="3" selected>3 Weeks</option>
                <option value="4">4 Weeks</option>
                <option value="5">5 Weeks</option>
            </select>
        </div>
    </div>
    
    <div class="container">
        <h2>Actions</h2>
        <button onclick="runCommand('setup')">🔧 Setup Initial Database</button>
        <button onclick="runCommand('update')">🔄 Update Database</button>
        <button onclick="runCommand('predict')">📊 Run Predictions</button>
        <button onclick="runCommand('optimize')">🎯 Run Optimization</button>
        <button onclick="runCommand('pipeline')">🚀 Run Full Pipeline</button>
        <span class="spinner" id="spinner">⏳ Processing...</span>
    </div>
    
    <div class="container">
        <h2>Output</h2>
        <div id="status"></div>
        <div id="output" class="output"></div>
    </div>
    
    <script>
        let isRunning = false;
        
        function runCommand(action) {
            if (isRunning) {
                alert('A process is already running. Please wait.');
                return;
            }
            
            const fplTeamId = document.getElementById('fpl_team_id').value;
            if (!fplTeamId && action !== 'setup') {
                alert('Please enter your FPL Team ID first!');
                return;
            }
            
            isRunning = true;
            document.getElementById('spinner').style.display = 'inline-block';
            document.getElementById('status').innerHTML = '';
            document.getElementById('output').innerHTML = 'Processing...';
            
            // Disable all buttons
            const buttons = document.querySelectorAll('button');
            buttons.forEach(btn => btn.disabled = true);
            
            const weeksAhead = document.getElementById('weeks_ahead').value;
            
            fetch('/run_command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    action: action,
                    fpl_team_id: fplTeamId,
                    weeks_ahead: weeksAhead
                })
            })
            .then(response => response.json())
            .then(data => {
                isRunning = false;
                document.getElementById('spinner').style.display = 'none';
                
                // Enable all buttons
                buttons.forEach(btn => btn.disabled = false);
                
                if (data.success) {
                    document.getElementById('status').innerHTML = '<div class="success">✓ ' + data.message + '</div>';
                    document.getElementById('output').innerHTML = data.output || 'Command completed successfully.';
                } else {
                    document.getElementById('status').innerHTML = '<div class="error">✗ Error: ' + data.error + '</div>';
                    document.getElementById('output').innerHTML = data.output || '';
                }
            })
            .catch(error => {
                isRunning = false;
                document.getElementById('spinner').style.display = 'none';
                buttons.forEach(btn => btn.disabled = false);
                document.getElementById('status').innerHTML = '<div class="error">✗ Error: ' + error + '</div>';
            });
        }
    </script>
</body>
</html>
"""

def run_command(command, description="Running command"):
    """Execute a shell command and return the output"""
    try:
        logger.info(f"Executing: {command}")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd='/airsenal',
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            error_msg = f"Command failed with exit code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "output": result.stdout}
        
        return {"success": True, "output": result.stdout}
    except subprocess.TimeoutExpired:
        error_msg = "Command timed out after 5 minutes"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Exception running command: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

@app.route('/')
def index():
    """Render the main page"""
    fpl_team_id = os.environ.get('FPL_TEAM_ID', '')
    return render_template_string(HTML_TEMPLATE, fpl_team_id=fpl_team_id)

@app.route('/run_command', methods=['POST'])
def handle_command():
    """Handle command execution requests"""
    data = request.json
    action = data.get('action')
    fpl_team_id = data.get('fpl_team_id')
    weeks_ahead = data.get('weeks_ahead', 3)
    
    # Set FPL_TEAM_ID environment variable if provided
    if fpl_team_id:
        os.environ['FPL_TEAM_ID'] = fpl_team_id
    
    # Define commands for each action
    commands = {
        'setup': 'airsenal_setup_initial_db',
        'update': 'airsenal_update_db',
        'predict': f'airsenal_run_prediction --weeks_ahead {weeks_ahead}',
        'optimize': f'airsenal_run_optimization --weeks_ahead {weeks_ahead}',
        'pipeline': f'airsenal_run_pipeline --weeks_ahead {weeks_ahead}'
    }
    
    if action not in commands:
        return jsonify({
            'success': False,
            'error': 'Invalid action',
            'message': 'Invalid action specified'
        })
    
    # Run the command
    result = run_command(commands[action], f"Running {action}")
    
    # Prepare response
    response = {
        'success': result['success'],
        'output': result.get('output', ''),
        'message': f"{action.capitalize()} completed successfully!" if result['success'] else f"{action.capitalize()} failed"
    }
    
    if not result['success']:
        response['error'] = result.get('error', 'Unknown error')
    
    return jsonify(response)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get('PORT', 5000))
    
    # Check if we're in production (Render) or development
    is_production = os.environ.get('RENDER', False)
    
    if is_production:
        # Production settings for Render
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Development settings
        app.run(host='127.0.0.1', port=port, debug=True)
