# ConfigSnap

ConfigSnap is a FastAPI service for capturing network-device configuration snapshots, listing them, and comparing the two latest snapshots.

## Features

- On-demand snapshots for configured devices
- Automatic snapshots on a configurable interval
- Snapshot listing and configuration diffs
- Netmiko device-type mapping and SSH autodetection
- API-key protection for snapshot and scheduler endpoints

## Requirements

- Python 3.9 or later
- SSH access to the network devices you configure

## Installation

```bash
git clone https://github.com/vsachin094/ConfigSnap.git
cd ConfigSnap
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp config/devices.example.yaml config/devices.yaml
cp config/credentials.example.json config/credentials.json
```

Edit `config/devices.yaml` and `config/credentials.json` for your environment. The example inventory uses documentation-only IP addresses and the example credentials are placeholders; replace both before use. These local files are ignored by Git.

Set an API key of at least 32 characters. For example, generate one with:

```bash
export CONFIGSNAP_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

The key must be set in the environment of the server process. ConfigSnap fails closed with HTTP 503 if it is missing or too short; requests without the matching `X-API-Key` header receive HTTP 401.

`config/config.json` contains the device-type mapping, file paths, and snapshot frequency in minutes. The scheduler starts automatically with the application.

## Run

From the `ConfigSnap` directory, start the service bound to the local machine:

```bash
uvicorn configsnap:app --host 127.0.0.1 --port 8000
```

The API is available at `http://127.0.0.1:8000`; interactive documentation is at `/docs`. For remote access, put the service behind a TLS-terminating reverse proxy and restrict network access. Do not expose the service directly to an untrusted network. If you intentionally bind to a non-loopback interface, retain API-key protection and configure firewall and TLS controls.

## API

All operational endpoints require the `X-API-Key` request header:

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/snapshot/{device_ip}` | Capture a snapshot for a configured device |
| `GET` | `/snapshots/{device_ip}` | List up to 10 recent snapshots |
| `GET` | `/diff/{device_ip}` | Compare the two most recent snapshots |
| `POST` | `/schedule-snapshot` | Start automatic snapshots if stopped |
| `POST` | `/stop-snapshot` | Stop future automatic snapshots |

Example:

```bash
curl -H "X-API-Key: $CONFIGSNAP_API_KEY" \
  -X POST http://127.0.0.1:8000/snapshot/192.0.2.10
```

Snapshots contain device configuration data and may include sensitive information. Protect the snapshot directory with appropriate filesystem permissions, backups, and retention policies. Never commit real credentials, device inventories, snapshots, or API keys.

## Contributing

Bug reports and pull requests are welcome. Please do not include real device credentials, device configuration output, or other sensitive information in issues or pull requests.

## License

ConfigSnap is distributed under the [MIT License](./LICENSE).
