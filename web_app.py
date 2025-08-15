#!/usr/bin/env python
"""
Simple web application for AIrsenal using Flask
This file creates a basic web interface for the AIrsenal Fantasy Premier League optimization tool.
"""

from flask import Flask, render_template_string, request, jsonify, Response
import subprocess
import json
import os
import sys
import threading
import logging
import queue
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the airsenal directory to the Python path
sys.path.insert(0, '/airsenal')

# Set up environment variables if not already set
if 'AIRSENAL_HOME' not in os.environ:
    os.environ['AIRSENAL_HOME'] = '/tmp'

app = Flask(__name__)

# Store active processes
active_processes = {}

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
        .warning {
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            color: #856404;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        .info {
            color: #0066cc;
            margin-top: 10px;
        }
        }
    </style>
</head>
<body>
    <h1>⚽ AIrsenal - Fantasy Premier League Optimizer</h1>
    
    <div class="container">
        <div class="warning">
            ⚠️ <strong>Note:</strong> The initial database setup can take 10-30 minutes as it downloads 3 seasons of data. 
            Please be patient. Other operations are typically faster.
        </div>
    </div>
    
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
        let eventSource = null;
        
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
            document.getElementById('status').innerHTML = '<div class="info">Starting ' + action + '...</div>';
            document.getElementById('output').innerHTML = 'Initializing...\n';
            
            // Disable all buttons
            const buttons = document.querySelectorAll('button');
            buttons.forEach(btn => btn.disabled = true);
            
            const weeksAhead = document.getElementById('weeks_ahead').value;
            
            // Start the command
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
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.process_id) {
                    // Start listening for updates
                    listenForUpdates(data.process_id);
                } else {
                    // Handle immediate error
                    handleComplete(false, data.error || 'Unknown error', '');
                }
            })
            .catch(error => {
                console.error('Error starting command:', error);
                handleComplete(false, 'Failed to start command: ' + error.toString(), '');
            });
        }
        
        function listenForUpdates(processId) {
            console.log('Listening for updates on process:', processId);
            
            // Use Server-Sent Events for real-time updates
            eventSource = new EventSource('/stream/' + processId);
            
            let outputLines = [];
            
            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.output) {
                        outputLines.push(data.output);
                        // Show last 50 lines
                        const displayLines = outputLines.slice(-50);
                        document.getElementById('output').innerHTML = escapeHtml(displayLines.join(''));
                        // Auto-scroll to bottom
                        const outputDiv = document.getElementById('output');
                        outputDiv.scrollTop = outputDiv.scrollHeight;
                    }
                    
                    if (data.status) {
                        document.getElementById('status').innerHTML = '<div class="info">Status: ' + escapeHtml(data.status) + '</div>';
                    }
                    
                    if (data.complete) {
                        eventSource.close();
                        eventSource = null;
                        handleComplete(data.success, data.error, outputLines.join(''));
                    }
                } catch (err) {
                    console.error('Error parsing SSE data:', err, 'Raw data:', event.data);
                }
            };
            
            eventSource.onerror = function(error) {
                console.error('SSE error:', error);
                if (eventSource) {
                    eventSource.close();
                    eventSource = null;
                }
                if (isRunning) {
                    handleComplete(false, 'Connection to server lost. The command may still be running.', outputLines.join(''));
                }
            };
        }
        
        function handleComplete(success, error, output) {
            isRunning = false;
            document.getElementById('spinner').style.display = 'none';
            
            // Enable all buttons
            const buttons = document.querySelectorAll('button');
            buttons.forEach(btn => btn.disabled = false);
            
            if (success) {
                document.getElementById('status').innerHTML = '<div class="success">✓ Command completed successfully!</div>';
            } else {
                document.getElementById('status').innerHTML = '<div class="error">✗ Error: ' + escapeHtml(error || 'Unknown error') + '</div>';
            }
            
            if (!output || output.trim() === '') {
                document.getElementById('output').innerHTML = 'No output captured.';
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Clean up on page unload
        window.addEventListener('beforeunload', function() {
            if (eventSource) {
                eventSource.close();
            }
        });
    </script>
</body>
</html>
"""

def run_command_with_streaming(command, process_id, timeout=1800):
    """Execute a shell command and stream output in real-time"""
    try:
        logger.info(f"Executing: {command}")
        
        # Store process info
        process_info = {
            'status': 'running',
            'output_queue': queue.Queue(),
            'success': False,
            'error': None,
            'complete': False
        }
        active_processes[process_id] = process_info
        
        # Start the process
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd='/airsenal',
            universal_newlines=True,
            bufsize=1
        )
        
        # Stream output line by line
        def stream_output():
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    
                    # Put line in queue for streaming
                    process_info['output_queue'].put(line)
                    logger.info(f"Output: {line.strip()}")
                
                # Wait for process to complete
                return_code = process.wait()
                
                if return_code == 0:
                    process_info['success'] = True
                    process_info['status'] = 'completed'
                    logger.info(f"Command completed successfully")
                else:
                    process_info['success'] = False
                    process_info['error'] = f"Command failed with exit code {return_code}"
                    process_info['status'] = 'failed'
                    logger.error(f"Command failed with exit code {return_code}")
                    
            except Exception as e:
                logger.error(f"Error in stream_output: {e}")
                process_info['success'] = False
                process_info['error'] = str(e)
                process_info['status'] = 'error'
            finally:
                # Mark as complete
                process_info['complete'] = True
                logger.info(f"Process {process_id} marked as complete")
        
        # Start streaming in a separate thread
        thread = threading.Thread(target=stream_output)
        thread.daemon = True
        thread.start()
        
        # Set a timeout to kill the process if it runs too long
        def timeout_handler():
            time.sleep(timeout)
            if not process_info['complete']:
                try:
                    process.kill()
                    process_info['error'] = f"Command timed out after {timeout/60} minutes"
                    process_info['status'] = 'timeout'
                    process_info['complete'] = True
                    logger.warning(f"Process {process_id} timed out")
                except:
                    pass
        
        timeout_thread = threading.Thread(target=timeout_handler)
        timeout_thread.daemon = True
        timeout_thread.start()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to start command: {str(e)}")
        active_processes[process_id] = {
            'status': 'error',
            'error': str(e),
            'complete': True,
            'success': False,
            'output_queue': queue.Queue()
        }
        return False

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
    
    # Define commands for each action with appropriate timeouts
    commands = {
        'setup': ('airsenal_setup_initial_db', 1800),  # 30 minutes for initial setup
        'update': ('airsenal_update_db', 600),  # 10 minutes for update
        'predict': (f'airsenal_run_prediction --weeks_ahead {weeks_ahead}', 900),  # 15 minutes
        'optimize': (f'airsenal_run_optimization --weeks_ahead {weeks_ahead}', 1200),  # 20 minutes
        'pipeline': (f'airsenal_run_pipeline --weeks_ahead {weeks_ahead}', 2400)  # 40 minutes
    }
    
    if action not in commands:
        return jsonify({
            'success': False,
            'error': 'Invalid action',
            'message': 'Invalid action specified'
        })
    
    # Get command and timeout
    command, timeout = commands[action]
    
    # Generate a unique process ID
    process_id = f"{action}_{int(time.time())}"
    
    # Start the command with streaming
    if run_command_with_streaming(command, process_id, timeout=timeout):
        return jsonify({'process_id': process_id})
    else:
        return jsonify({'success': False, 'error': 'Failed to start command'})

@app.route('/stream/<process_id>')
def stream_output(process_id):
    """Stream command output using Server-Sent Events"""
    def generate():
        try:
            if process_id not in active_processes:
                yield f"data: {json.dumps({'error': 'Process not found', 'complete': True})}\n\n"
                return
            
            process_info = active_processes[process_id]
            
            # Send initial status
            yield f"data: {json.dumps({'status': 'Command started...'})}\n\n"
            
            # Stream output lines
            while True:
                # Check for new output
                try:
                    while not process_info['output_queue'].empty():
                        line = process_info['output_queue'].get_nowait()
                        # Ensure line is properly escaped for JSON
                        safe_line = line.replace('\\', '\\\\').replace('"', '\\"').replace('\r', '\\r').replace('\n', '\\n')
                        yield f"data: {json.dumps({'output': line}, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    pass
                except Exception as e:
                    logger.error(f"Error getting output from queue: {e}")
                
                # Check if process is complete
                if process_info.get('complete', False):
                    result = {
                        'complete': True,
                        'success': process_info.get('success', False),
                        'error': process_info.get('error', None)
                    }
                    yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                    
                    # Clean up
                    try:
                        del active_processes[process_id]
                    except:
                        pass
                    break
                
                # Small delay to prevent busy waiting
                time.sleep(0.1)
        except GeneratorExit:
            logger.info(f"Client disconnected from stream {process_id}")
        except Exception as e:
            logger.error(f"Error in stream generation: {e}")
            yield f"data: {json.dumps({'error': str(e), 'complete': True})}\n\n"
    
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response

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
