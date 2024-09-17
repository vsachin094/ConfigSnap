# ConfigSnap: A Network Configuration Snapshot Tool

**Introduction**

ConfigSnap is a powerful tool designed to simplify the process of capturing and managing network device configurations. Built on the FastAPI framework, ConfigSnap provides a user-friendly API for automating snapshotting tasks and integrating with existing automation workflows. 

**Key Features**

* **FastAPI-Based API:** Enjoy the benefits of a high-performance, asynchronous API for efficient configuration management.
* **Automatic and Manual Snapshots:** Capture network device configurations at regular intervals or on demand.
* **Scheduled Snapshots:** Set up recurring snapshot schedules to ensure consistent configuration tracking.
* **Running Config Capture:** Capture the current running configuration of network devices.
* **Auto and Manual Configuration Capture:** Capture both auto and manual configurations.
* **Netmiko Device Type Mapping:** ConfigSnap supports a wide range of network devices by automatically mapping device types to Netmiko-compatible classes.

**Installation**

1. **Prerequisites:** Ensure you have Python installed (version 3.6 or later) and the required dependencies listed in the `requirements.txt` file.
2. **Clone the Repository:** Clone the ConfigSnap repository from GitHub: `git clone https://github.com/sachin0987/ConfigSnap.git`
3. **Install Dependencies:** Navigate to the project directory and run `pip install -r requirements.txt` to install the necessary dependencies.

**Configuration**

* **Device Configuration:** Create a YAML file (`devices.yaml`) to define device groups and their corresponding IP addresses.
* **Credentials:** Create a JSON file (`credentials.json`) to store device credentials (e.g., username, password, enable password).
* **Commands:** Create a JSON file (`commands.json`) to specify the commands that will be executed on the devices to capture their configurations.
* **Configuration File:** Modify the `config.json` file to set the appropriate values for the `log_dir`, `snapshot_dir`, `device_type_mapping`, `devices_file`, `credentials_file`, `commands_file`, and `auto_snapshot_frequency`.

**Running the Tool**

1. **Start the FastAPI Server:** Run the following command to start the ConfigSnap server: `uvicorn main:app --reload`
2. **Access the API:** The API will be available at the specified URL (usually `http://127.0.0.1:8000`).

**API Endpoints**

* **`/snapshot/{device_ip}` (POST):** Triggers a manual snapshot for a specific device.
* **`/snapshots/{device_ip}` (GET):** Returns a list of available snapshot files for a specific device.
* **`/diff/{device_ip}` (GET):** Generates a diff between the two most recent snapshots for a specific device.
* **`/schedule-snapshot` (POST):** Starts the automatic snapshot scheduling.
* **`/stop-snapshot` (POST):** Stops the automatic snapshot scheduling.

**Usage**

1. **Manual Snapshots:** Use the API endpoints to manually trigger snapshots for specific devices.
2. **Scheduled Snapshots:** Configure the `auto_snapshot_frequency` in the `config.json` file to automatically take snapshots at regular intervals.

**Contributing**

We welcome contributions to ConfigSnap! Please refer to our [CONTRIBUTING.md] file for guidelines on how to report issues, submit pull requests, and contribute to the project.

**License**

ConfigSnap is released under the [MIT License](https://opensource.org/licenses/MIT).

Note: Contributors are most welcome
