import os
import time
import json
import yaml
import logging
import schedule
import difflib
import threading
from fastapi import FastAPI, BackgroundTasks
from device_manager import DeviceManager
from datetime import datetime
from pathlib import Path

app = FastAPI()

# Configure logging
config_file = 'config/config.json'
with open(config_file, 'r') as file:
    config = json.load(file)

log_dir = config['log_dir']
snapshot_dir = config['snapshot_dir']
auto_snapshot_frequency = config.get('auto_snapshot_frequency', 30)  # Default to 30 minutes if not set
os.makedirs(log_dir, exist_ok=True)
os.makedirs(snapshot_dir, exist_ok=True)
log_filename = f"{log_dir}/app_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

# Configure the logging
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DEVICE_TYPE_MAPPING = config['device_type_mapping']
DEFAULT_DEVICE_TYPE = config['device_type_mapping'].get("default", "autodetect")
DEVICE_FILE_PATH = config['devices_file']

# Helper Functions
def load_yaml(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def load_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def build_device_list(devices_file, credentials_file, commands_file, device_type_mapping):
    devices = load_yaml(devices_file)
    credentials = load_json(credentials_file)
    commands = load_json(commands_file)
    
    device_list = []
    for device_group, device_ips in devices.items():
        device_type = device_type_mapping.get(device_group, DEFAULT_DEVICE_TYPE)
        group_credentials = credentials.get(device_group, credentials['default'])
        group_commands = commands.get(device_group, commands['default'])

        for ip in device_ips:
            device_dict = {
                "device_ip": ip,
                "device_type": device_type,
                "credentials": group_credentials,
                "commands": group_commands
            }
            device_list.append(device_dict)
    return device_list

def take_snapshot(device):
    device_ip = device['device_ip']
    device_type = device['device_type']
    credentials = device['credentials']
    commands = device['commands']
    
    try:
        device_manager = DeviceManager(device_ip, device_type, credentials)
        device_manager.connect()
        output = device_manager.run_show_command(commands)

        # Generate unique snapshot filename with epoch timestamp
        epoch_timestamp = str(int(time.time()))
        snapshot_file = os.path.join(snapshot_dir, f"{device_ip}_snapshot_{epoch_timestamp}.txt")
        
        # Save snapshot
        with open(snapshot_file, 'w') as file:
            file.write(output)
        logging.info(f"Snapshot taken for {device_ip} and saved as {snapshot_file}.")
        
        device_manager.disconnect()
        return {"status": "success", "snapshot_file": snapshot_file}
    
    except Exception as e:
        logging.error(f"Failed to connect or execute command on {device_ip}: {str(e)}")
        return {"status": "error", "message": f"Failed to connect or execute command on {device_ip}"}

def execute_snapshots(device_ip=None):
    device_list = build_device_list(DEVICE_FILE_PATH, config['credentials_file'], config['commands_file'], DEVICE_TYPE_MAPPING)
    if device_ip:
        device = next((d for d in device_list if d['device_ip'] == device_ip), None)
        if device:
            return take_snapshot(device)
        else:
            logging.error(f"Device with IP {device_ip} not found.")
            return {"status": "error", "message": f"Device with IP {device_ip} not found."}
    else:
        results = {}
        for device in device_list:
            result = take_snapshot(device)
            results[device['device_ip']] = result
        return results

# Scheduler Function
def run_scheduler():
    """Run the scheduler in a separate thread."""
    while True:
        schedule.run_pending()
        time.sleep(1)

# Schedule auto snapshots
def auto_snapshot():
    logging.info("Auto-snapshot job started...")
    execute_snapshots()

@app.on_event("startup")
async def schedule_snapshot():
    schedule.every(auto_snapshot_frequency).minutes.do(auto_snapshot)
    
    # Start the scheduler in a new thread
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True  # Ensure it exits when the main thread does
    scheduler_thread.start()

# APIs for snapshot functionality

@app.post("/snapshot/{device_ip}")
def manual_snapshot(device_ip: str):
    result = execute_snapshots(device_ip=device_ip)
    return result

@app.get("/snapshots/{device_ip}")
def get_snapshots(device_ip: str):
    snapshots = [f for f in os.listdir(snapshot_dir) if device_ip in f]
    return {"snapshots": snapshots}

@app.get("/diff/{device_ip}")
def diff_snapshots(device_ip: str):
    snapshots = sorted([f for f in os.listdir(snapshot_dir) if device_ip in f], reverse=True)
    if len(snapshots) < 2:
        return {"status": "error", "message": "Not enough snapshots to generate a diff."}
    
    with open(os.path.join(snapshot_dir, snapshots[0]), 'r') as f1, open(os.path.join(snapshot_dir, snapshots[1]), 'r') as f2:
        diff = list(difflib.unified_diff(f1.readlines(), f2.readlines()))
    return {"status": "success", "diff": ''.join(diff)}

@app.post("/schedule-snapshot")
async def schedule_snapshot_endpoint(background_tasks: BackgroundTasks):
    logging.info(f"Scheduled auto-snapshots every {auto_snapshot_frequency} minutes.")
    background_tasks.add_task(run_scheduler)
    return {"status": "success", "message": "Auto-snapshot task scheduled."}

@app.post("/stop-snapshot")
async def stop_snapshot_endpoint():
    schedule.clear()
    return {"status": "success", "message": "Auto-snapshot task stopped."}

# Run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)