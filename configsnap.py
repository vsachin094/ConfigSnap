import difflib
import hmac
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional

import yaml
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader

from device_manager import DeviceManager

app = FastAPI(title="ConfigSnap")

config_file = "config/config.json"
with open(config_file, "r") as file:
    config = json.load(file)

log_dir = config["log_dir"]
snapshot_dir = config["snapshot_dir"]
auto_snapshot_frequency = config.get("auto_snapshot_frequency", 30)
os.makedirs(log_dir, exist_ok=True)
os.makedirs(snapshot_dir, exist_ok=True)
log_filename = f"{log_dir}/app_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

DEVICE_TYPE_MAPPING = config["device_type_mapping"]
DEFAULT_DEVICE_TYPE = DEVICE_TYPE_MAPPING.get("default", "autodetect")
DEVICE_FILE_PATH = config["devices_file"]

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_scheduler_lock = threading.Lock()
_scheduler_wakeup = threading.Event()
_scheduler_shutdown = threading.Event()
_scheduler_thread: Optional[threading.Thread] = None
_schedule_enabled = False
_next_snapshot_at: Optional[float] = None


def require_api_key(api_key: Optional[str] = Depends(api_key_header)) -> None:
    configured_key = os.environ.get("CONFIGSNAP_API_KEY")
    if not configured_key or len(configured_key) < 32:
        raise HTTPException(
            status_code=503,
            detail="Set CONFIGSNAP_API_KEY to a value of at least 32 characters.",
        )
    if api_key is None or not hmac.compare_digest(api_key, configured_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


def load_yaml(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


def load_json(file_path):
    with open(file_path, "r") as file:
        return json.load(file)


def build_device_list(devices_file, credentials_file, commands_file, device_type_mapping):
    devices = load_yaml(devices_file)
    credentials = load_json(credentials_file)
    commands = load_json(commands_file)

    device_list = []
    for device_group, device_ips in devices.items():
        device_type = device_type_mapping.get(device_group, DEFAULT_DEVICE_TYPE)
        group_credentials = credentials.get(device_group, credentials["default"])
        group_commands = commands.get(device_group, commands["default"])

        for ip in device_ips:
            device_list.append(
                {
                    "device_ip": ip,
                    "device_type": device_type,
                    "credentials": group_credentials,
                    "commands": group_commands,
                }
            )
    return device_list


def take_snapshot(device):
    device_ip = device["device_ip"]
    device_type = device["device_type"]
    credentials = device["credentials"]
    commands = device["commands"]
    device_manager = DeviceManager(device_ip, device_type, credentials)

    try:
        device_manager.connect()
        output = device_manager.run_show_command(commands)
        snapshot_file = os.path.join(
            snapshot_dir, f"{device_ip}_snapshot_{time.time_ns()}.txt"
        )

        with open(snapshot_file, "w") as file:
            file.write(output)
        logging.info("Snapshot taken for %s and saved as %s.", device_ip, snapshot_file)
        return {"status": "success", "snapshot_file": snapshot_file}
    except Exception as exc:
        logging.error(
            "Failed to capture a snapshot for %s (%s).",
            device_ip,
            type(exc).__name__,
        )
        return {"status": "error", "message": f"Failed to capture snapshot for {device_ip}."}
    finally:
        if device_manager.connection:
            try:
                device_manager.disconnect()
            except Exception as exc:
                logging.error(
                    "Failed to disconnect from %s (%s).",
                    device_ip,
                    type(exc).__name__,
                )


def execute_snapshots(device_ip=None):
    device_list = build_device_list(
        DEVICE_FILE_PATH,
        config["credentials_file"],
        config["commands_file"],
        DEVICE_TYPE_MAPPING,
    )
    if device_ip:
        device = next((item for item in device_list if item["device_ip"] == device_ip), None)
        if device:
            return take_snapshot(device)
        logging.error("Device with IP %s not found.", device_ip)
        return {"status": "error", "message": f"Device with IP {device_ip} not found."}

    results = {}
    for device in device_list:
        results[device["device_ip"]] = take_snapshot(device)
    return results


def auto_snapshot():
    logging.info("Auto-snapshot job started.")
    try:
        execute_snapshots()
    except Exception as exc:
        logging.error("Auto-snapshot job failed (%s).", type(exc).__name__)


def run_scheduler():
    global _next_snapshot_at
    while not _scheduler_shutdown.is_set():
        with _scheduler_lock:
            next_snapshot_at = _next_snapshot_at if _schedule_enabled else None

        if next_snapshot_at is None:
            _scheduler_wakeup.wait()
            _scheduler_wakeup.clear()
            continue

        timeout = max(0, next_snapshot_at - time.monotonic())
        if _scheduler_wakeup.wait(timeout):
            _scheduler_wakeup.clear()
            continue

        with _scheduler_lock:
            should_run = (
                _schedule_enabled
                and _next_snapshot_at is not None
                and _next_snapshot_at <= time.monotonic()
            )
            if should_run:
                _next_snapshot_at = time.monotonic() + auto_snapshot_frequency * 60

        if should_run:
            auto_snapshot()


def start_snapshot_schedule():
    global _schedule_enabled, _next_snapshot_at
    with _scheduler_lock:
        if _schedule_enabled:
            return False
        _schedule_enabled = True
        _next_snapshot_at = time.monotonic() + auto_snapshot_frequency * 60
        _scheduler_wakeup.set()
    return True


def stop_snapshot_schedule():
    global _schedule_enabled, _next_snapshot_at
    with _scheduler_lock:
        _schedule_enabled = False
        _next_snapshot_at = None
        _scheduler_wakeup.set()


@app.on_event("startup")
async def start_scheduler_worker():
    global _scheduler_thread
    if auto_snapshot_frequency <= 0:
        raise RuntimeError("auto_snapshot_frequency must be greater than zero.")

    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        _scheduler_shutdown.clear()
        _scheduler_thread = threading.Thread(
            target=run_scheduler,
            name="configsnap-scheduler",
            daemon=True,
        )
        _scheduler_thread.start()
    start_snapshot_schedule()


@app.on_event("shutdown")
async def stop_scheduler_worker():
    stop_snapshot_schedule()
    _scheduler_shutdown.set()
    _scheduler_wakeup.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=5)


@app.post("/snapshot/{device_ip}", dependencies=[Depends(require_api_key)])
def manual_snapshot(device_ip: str):
    return execute_snapshots(device_ip=device_ip)


@app.get("/snapshots/{device_ip}", dependencies=[Depends(require_api_key)])
def get_snapshots(device_ip: str):
    prefix = f"{device_ip}_snapshot_"
    snapshots = sorted(
        (
            filename
            for filename in os.listdir(snapshot_dir)
            if filename.startswith(prefix) and filename.endswith(".txt")
        ),
        reverse=True,
    )
    return {"snapshots": snapshots[:10]}


@app.get("/diff/{device_ip}", dependencies=[Depends(require_api_key)])
def diff_snapshots(device_ip: str):
    prefix = f"{device_ip}_snapshot_"
    snapshots = sorted(
        (
            filename
            for filename in os.listdir(snapshot_dir)
            if filename.startswith(prefix) and filename.endswith(".txt")
        ),
        reverse=True,
    )
    if len(snapshots) < 2:
        return {"status": "error", "message": "Not enough snapshots to generate a diff."}

    with open(os.path.join(snapshot_dir, snapshots[0]), "r") as latest, open(
        os.path.join(snapshot_dir, snapshots[1]), "r"
    ) as previous:
        diff = difflib.unified_diff(previous.readlines(), latest.readlines())

    changes = {"added": [], "removed": [], "updated": []}
    for line in diff:
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("+"):
            changes["added"].append(line[1:].rstrip("\r\n"))
        elif line.startswith("-"):
            changes["removed"].append(line[1:].rstrip("\r\n"))

    if not changes["added"] and not changes["removed"]:
        return {"status": "success", "changes": "no changes detected on the device"}
    return {"status": "success", "changes": changes}


@app.post("/schedule-snapshot", dependencies=[Depends(require_api_key)])
def schedule_snapshot_endpoint():
    started = start_snapshot_schedule()
    message = (
        f"Snapshots scheduled every {auto_snapshot_frequency} minutes."
        if started
        else "Snapshot schedule is already running."
    )
    logging.info(message)
    return {"status": "success", "message": message}


@app.post("/stop-snapshot", dependencies=[Depends(require_api_key)])
def stop_snapshot_endpoint():
    stop_snapshot_schedule()
    logging.info("Automatic snapshots stopped.")
    return {"status": "success", "message": "Automatic snapshots stopped."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
