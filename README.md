# finger-web

A Flask web application that fronts a finger daemon, with a JSON API, a CLI client, and an MCP server for Claude integration.

## Components

| Path | Description |
|------|-------------|
| `app.py` | Flask web app and JSON API |
| `cli/finger.py` | Command-line client |
| `mcp/server.py` | MCP server for Claude |

---

## Web App

### Requirements

- Python 3.9+
- A `finger` binary available on the server's PATH

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

All settings are read from environment variables.

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | `dev-secret-key-change-in-production` |
| `FLASK_DEBUG` | Enable debug mode | `True` |
| `BASIC_AUTH_USERS` | Comma-separated `user:pass` pairs for upload auth | _(none — upload disabled)_ |
| `SCP_ENABLED` | Enable SCP transfer of uploaded plan files | `false` |
| `REMOTE_HOST` | Remote host for SCP | — |
| `REMOTE_USER` | Remote user for SCP | — |
| `REMOTE_PATH` | Remote path for SCP destination | — |
| `REMOTE_PORT` | Remote SSH port | `22` |
| `REMOTE_PRIVATE_KEY` | Path to SSH private key | — |

### Running

```bash
python app.py
# or with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker

```bash
docker-compose up -d
```

---

## API

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/finger` | GET/POST | — | Web UI finger query |
| `/finger/<username>` | GET | — | Web UI finger query (URL form) |
| `/api/finger` | GET | — | JSON: list logged-in users |
| `/api/finger/<username>` | GET | — | JSON: finger a specific user |
| `/api/upload` | POST | Basic | Upload a plan file |
| `/api/info` | GET | — | API metadata |

### Example

```bash
curl http://localhost:5000/api/finger/pete@peteftw.com
```

```json
{
  "status": "success",
  "username": "pete@peteftw.com",
  "result": "Login: pete\t\t\tName: Pete Blair\n..."
}
```

---

## CLI

### Installation

```bash
pip install -r cli/requirements.txt
```

### Configuration

```bash
export FINGER_WEB_URL=http://localhost:5000
export FINGER_USER=youruser      # only needed for plan uploads
export FINGER_PASS=yourpassword  # only needed for plan uploads
```

### Usage

```bash
# Finger a user
python cli/finger.py query pete@peteftw.com

# Upload your plan file
python cli/finger.py plan ~/.plan
```

---

## MCP Server

Exposes finger query and plan upload as tools for Claude.

### Installation

```bash
pip install -r mcp/requirements.txt
```

### Configuration

```bash
export FINGER_WEB_URL=http://localhost:5000
export FINGER_USER=youruser      # only needed for upload_plan tool
export FINGER_PASS=yourpassword  # only needed for upload_plan tool
```

### Running

```bash
python mcp/server.py
```

### Claude Desktop configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "finger": {
      "command": "python",
      "args": ["/path/to/finger-web/mcp/server.py"],
      "env": {
        "FINGER_WEB_URL": "http://localhost:5000",
        "FINGER_USER": "youruser",
        "FINGER_PASS": "yourpassword"
      }
    }
  }
}
```

### Available tools

| Tool | Description |
|------|-------------|
| `finger_user(username)` | Query finger info for a user, or leave empty to list logged-in users |
| `upload_plan(filename, content)` | Upload or update a plan file |
