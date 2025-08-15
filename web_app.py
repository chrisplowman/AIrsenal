#!/usr/bin/env python
"""
Web application for AIrsenal using Streamlit
This file creates a web interface for the AIrsenal Fantasy Premier League optimization tool.
"""

import streamlit as st
import subprocess
import json
import os
import sys
import time
import pandas as pd
from pathlib import Path
import threading
import queue
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the airsenal directory to the Python path
sys.path.insert(0, '/airsenal')

# Set up environment variables if not already set
if 'AIRSENAL_HOME' not in os.environ:
    os.environ['AIRSENAL_HOME'] = '/tmp'

# Page configuration
st.set_page_config(
    page_title="AIrsenal - Fantasy Premier League Optimizer",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'process_running' not in st.session_state:
    st.session_state.process_running = False
if 'results' not in st.session_state:
    st.session_state.results = None
if 'error' not in st.session_state:
    st.session_state.error = None
if 'log_messages' not in st.session_state:
    st.session_state.log_messages = []

def run_command(command, description="Running command"):
    """Execute a shell command and return the output"""
    try:
        logger.info(f"Executing: {command}")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd='/airsenal'
        )
        
        if result.returncode != 0:
            error_msg = f"Command failed: {result.stderr}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        return {"success": True, "output": result.stdout}
    except Exception as e:
        error_msg = f"Exception running command: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

def setup_database():
    """Initialize the AIrsenal database"""
    with st.spinner("Setting up database... This may take a few minutes"):
        result = run_command("airsenal_setup_initial_db", "Setting up database")
        if result["success"]:
            st.success("Database initialized successfully!")
        else:
            st.error(f"Database setup failed: {result['error']}")
        return result

def update_database():
    """Update the AIrsenal database with latest data"""
    with st.spinner("Updating database with latest data..."):
        result = run_command("airsenal_update_db", "Updating database")
        if result["success"]:
            st.success("Database updated successfully!")
        else:
            st.error(f"Database update failed: {result['error']}")
        return result

def run_prediction(weeks_ahead):
    """Run the prediction model"""
    with st.spinner(f"Running predictions for {weeks_ahead} weeks ahead..."):
        command = f"airsenal_run_prediction --weeks_ahead {weeks_ahead}"
        result = run_command(command, "Running predictions")
        if result["success"]:
            st.success("Predictions completed successfully!")
        else:
            st.error(f"Prediction failed: {result['error']}")
        return result

def run_optimization(weeks_ahead, chips=None):
    """Run the optimization to find best transfers"""
    chip_args = ""
    if chips:
        for chip, week in chips.items():
            if week > 0:
                chip_args += f" --{chip}_week {week}"
    
    with st.spinner(f"Running optimization for {weeks_ahead} weeks ahead..."):
        command = f"airsenal_run_optimization --weeks_ahead {weeks_ahead}{chip_args}"
        result = run_command(command, "Running optimization")
        if result["success"]:
            st.success("Optimization completed successfully!")
            # Parse and display results
            parse_optimization_results(result["output"])
        else:
            st.error(f"Optimization failed: {result['error']}")
        return result

def parse_optimization_results(output):
    """Parse and display optimization results"""
    if output:
        st.text_area("Optimization Results", output, height=400)

def run_pipeline_process(fpl_team_id, weeks_ahead, progress_queue):
    """Run the full AIrsenal pipeline in a separate thread"""
    processes = [
        {"name": "Database Update", "command": "airsenal_update_db"},
        {"name": "Predictions", "command": f"airsenal_run_prediction --weeks_ahead {weeks_ahead}"},
        {"name": "Optimization", "command": f"airsenal_run_optimization --weeks_ahead {weeks_ahead}"}
    ]
    
    total_steps = len(processes)
    
    for i, process_info in enumerate(processes):
        # Fix: Changed from escaped quotes to single quotes
        progress_queue.put({
            "current_step": f"Starting {process_info['name']}...",
            "progress": i / total_steps
        })
        
        result = subprocess.run(
            process_info['command'],
            shell=True,
            capture_output=True,
            text=True,
            cwd='/airsenal'
        )
        
        if result.returncode != 0:
            progress_queue.put({
                "error": f"{process_info['name']} failed: {result.stderr}",
                "progress": -1
            })
            return
        
        progress_queue.put({
            "current_step": f"Completed {process_info['name']}",
            "progress": (i + 1) / total_steps,
            "output": result.stdout
        })
    
    progress_queue.put({
        "current_step": "Pipeline completed successfully!",
        "progress": 1.0,
        "complete": True
    })

def main():
    # Title and description
    st.title("⚽ AIrsenal - Fantasy Premier League Optimizer")
    st.markdown("""
    Welcome to AIrsenal! This tool uses machine learning to optimize your Fantasy Premier League team.
    Configure your settings in the sidebar and run the optimization pipeline.
    """)
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        # FPL Team ID
        fpl_team_id = st.text_input(
            "FPL Team ID",
            value=os.environ.get("FPL_TEAM_ID", ""),
            help="Your Fantasy Premier League team ID"
        )
        
        if fpl_team_id:
            os.environ["FPL_TEAM_ID"] = fpl_team_id
        
        # Optional credentials
        with st.expander("Optional Credentials"):
            fpl_login = st.text_input(
                "FPL Login (Email)",
                value=os.environ.get("FPL_LOGIN", ""),
                type="password",
                help="Only needed for automated transfers"
            )
            fpl_password = st.text_input(
                "FPL Password",
                value=os.environ.get("FPL_PASSWORD", ""),
                type="password",
                help="Only needed for automated transfers"
            )
            
            if fpl_login:
                os.environ["FPL_LOGIN"] = fpl_login
            if fpl_password:
                os.environ["FPL_PASSWORD"] = fpl_password
        
        # Optimization settings
        st.header("Optimization Settings")
        weeks_ahead = st.slider(
            "Weeks to look ahead",
            min_value=1,
            max_value=5,
            value=3,
            help="Number of gameweeks to optimize for"
        )
        
        # Chip usage
        with st.expander("Chip Usage (Optional)"):
            use_wildcard = st.checkbox("Use Wildcard")
            wildcard_week = st.number_input("Wildcard Week", min_value=0, value=0) if use_wildcard else 0
            
            use_free_hit = st.checkbox("Use Free Hit")
            free_hit_week = st.number_input("Free Hit Week", min_value=0, value=0) if use_free_hit else 0
            
            use_triple_captain = st.checkbox("Use Triple Captain")
            triple_captain_week = st.number_input("Triple Captain Week", min_value=0, value=0) if use_triple_captain else 0
            
            use_bench_boost = st.checkbox("Use Bench Boost")
            bench_boost_week = st.number_input("Bench Boost Week", min_value=0, value=0) if use_bench_boost else 0
    
    # Main content area
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("Quick Actions")
        
        if st.button("🔧 Setup Initial Database", disabled=st.session_state.process_running):
            if not fpl_team_id:
                st.error("Please enter your FPL Team ID first!")
            else:
                setup_database()
        
        if st.button("🔄 Update Database", disabled=st.session_state.process_running):
            if not fpl_team_id:
                st.error("Please enter your FPL Team ID first!")
            else:
                update_database()
        
        if st.button("📊 Run Predictions Only", disabled=st.session_state.process_running):
            if not fpl_team_id:
                st.error("Please enter your FPL Team ID first!")
            else:
                run_prediction(weeks_ahead)
        
        if st.button("🎯 Run Optimization Only", disabled=st.session_state.process_running):
            if not fpl_team_id:
                st.error("Please enter your FPL Team ID first!")
            else:
                chips = {
                    "wildcard": wildcard_week,
                    "free_hit": free_hit_week,
                    "triple_captain": triple_captain_week,
                    "bench_boost": bench_boost_week
                }
                run_optimization(weeks_ahead, chips)
    
    with col2:
        st.header("Full Pipeline")
        
        if st.button(
            "🚀 Run Full Pipeline",
            disabled=st.session_state.process_running,
            help="Updates database, runs predictions, and optimizes transfers"
        ):
            if not fpl_team_id:
                st.error("Please enter your FPL Team ID first!")
            else:
                st.session_state.process_running = True
                st.session_state.error = None
                
                # Create a progress container
                progress_container = st.container()
                
                with progress_container:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    output_area = st.empty()
                    
                    # Create a queue for progress updates
                    progress_queue = queue.Queue()
                    
                    # Start the pipeline in a separate thread
                    pipeline_thread = threading.Thread(
                        target=run_pipeline_process,
                        args=(fpl_team_id, weeks_ahead, progress_queue)
                    )
                    pipeline_thread.start()
                    
                    # Monitor progress
                    outputs = []
                    while pipeline_thread.is_alive() or not progress_queue.empty():
                        try:
                            update = progress_queue.get(timeout=0.1)
                            
                            if "error" in update:
                                st.session_state.error = update["error"]
                                st.error(update["error"])
                                st.session_state.process_running = False
                                break
                            
                            if "current_step" in update:
                                status_text.text(update["current_step"])
                            
                            if "progress" in update and update["progress"] >= 0:
                                progress_bar.progress(update["progress"])
                            
                            if "output" in update:
                                outputs.append(update["output"])
                                # Display accumulated output
                                output_area.text_area(
                                    "Pipeline Output",
                                    "\n".join(outputs[-5:]),  # Show last 5 outputs
                                    height=200
                                )
                            
                            if update.get("complete", False):
                                st.success("Pipeline completed successfully!")
                                st.balloons()
                                st.session_state.process_running = False
                                break
                                
                        except queue.Empty:
                            continue
                    
                    pipeline_thread.join()
                    st.session_state.process_running = False
    
    # Results section
    st.header("Results")
    
    if st.session_state.results:
        st.subheader("Optimization Results")
        st.json(st.session_state.results)
    
    if st.session_state.error:
        st.error(f"Error: {st.session_state.error}")
    
    # Information section
    with st.expander("ℹ️ About AIrsenal"):
        st.markdown("""
        AIrsenal is a machine learning-powered tool for optimizing Fantasy Premier League teams.
        
        **Features:**
        - Statistical modeling of player and team performance
        - Optimization of transfers and team selection
        - Support for chip usage (Wildcard, Free Hit, etc.)
        - Automated team management
        
        **How it works:**
        1. **Database Setup**: Downloads historical data from the FPL API
        2. **Predictions**: Uses statistical models to predict player points
        3. **Optimization**: Finds the best transfer strategy given constraints
        
        **Tips:**
        - Run the full pipeline weekly before the gameweek deadline
        - Consider the optimization suggestions but use your judgment
        - The tool works best when looking 3 weeks ahead
        
        For more information, visit the [AIrsenal GitHub repository](https://github.com/alan-turing-institute/AIrsenal)
        """)

if __name__ == "__main__":
    main()
