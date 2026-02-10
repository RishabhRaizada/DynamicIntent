# Flight Disruption – Auto Recovery System

---

## 1. Overview

This project implements a **Flight Disruption Auto-Recovery System** that automatically determines the best recovery option for passengers whose flights are disrupted.

The system performs the following steps:

1. Accepts passenger details (PNR + last name)
2. Validates whether the passenger is eligible for auto-recovery
3. Fetches alternate flights and seats
4. Invokes an AI Agent to decide the optimal recovery
5. Returns a structured recovery decision

This repository contains **backend services, MCP tooling, and a frontend UI** that together form the complete flow.

---

## 2. High-Level Architecture

The system consists of four running components:

1. **MCP Server**  
   Exposes recovery tools using Model Context Protocol

2. **FastAPI Backend**  
   Orchestrates MCP + AI Agent invocation

3. **Azure AI Agent**  
   Applies business rules and selects flight + seat

4. **Frontend UI**  
   Allows users to trigger the recovery flow

Each component is started independently and communicates over HTTP.

---

## 3. Prerequisites

### 3.1 System Requirements

- Python **3.10 or higher**
- Node.js **18 or higher**
- npm **9 or higher**
- Azure CLI installed

### 3.2 Python Dependencies

Install all required Python packages:

```bash
pip install -r requirements.txt
```

---

## 4. Authentication Model (IMPORTANT)

### 4.1 Azure Authentication

Azure authentication is handled **exclusively via Azure CLI**.

No Azure credentials are stored in:
- Code
- Config files
- Environment variables

Before running the system, authenticate once:

```bash
az login
```

The application uses `DefaultAzureCredential`, which automatically picks up the Azure CLI session.

> If Azure authentication fails, re-run `az login`.

---

### 4.2 External API Authentication (Required)

External flight and seat APIs require authentication using **environment variables**.

These values **must exist locally** but **must never be committed**.

---

## 5. Configuration & Environment Files

### 5.1 Configuration File (Non-Secrets)

**File:** `config/config.yaml`

This file contains **non-sensitive configuration only**, such as:
- Ports
- Hosts
- API base URLs
- Agent identifiers

```yaml
server:
  host: 127.0.0.1
  mcp_port: <port>
  api_port: <port>
  mcp_path: /mcp

azure:
  project_endpoint: <AZURE_PROJECT_ENDPOINT>
  agent_id: <AZURE_AGENT_ID>

external_api:
  flight_search_url: <FLIGHT_SEARCH_API_URL>
  seat_map_url: <SEAT_MAP_API_URL>
```

This file **must be present** for the system to start.

---

### 5.2 Environment File (Secrets)

#### `.env` (LOCAL ONLY – DO NOT COMMIT)

Create a `.env` file at the project root.

This file stores **only required secrets**:

```env
EXTERNAL_API_KEY=<external-api-key>
EXTERNAL_API_TOKEN=<external-api-token>
```

Add `.env` to `.gitignore`.

---

#### `.env.example` (COMMITTED)

This file documents required environment variables:

```env
EXTERNAL_API_KEY=<external-api-key>
EXTERNAL_API_TOKEN=<external-api-token>
```

---

## 6. Agent Configuration

- The AI Agent is **pre-created** in Azure.
- The Agent ID is **not hardcoded**.
- The Agent ID is read from:

```
config/config.yaml → azure.agent_id
```

The agent is responsible for:
- Selecting the best alternate flight
- Selecting the best seat
- Enforcing business rules (e.g. student vs premium passenger)
- Returning strict JSON output

---

## 7. Running the MCP Inspector (Optional)

The MCP Inspector is used **only for debugging** MCP tools.

### Command

```bash
npx @modelcontextprotocol/inspector
```

### Expected Output

```text
Starting MCP inspector...
Proxy server listening on 127.0.0.1:<PORT>
Session token: <TOKEN>
```

This step is **not required** for normal execution.

---

## 8. Running the MCP Server

### File

```
server.py
```

### Command

```bash
python server.py
```

### What This Does

- Starts the MCP server
- Registers recovery tools
- Exposes MCP endpoint

### MCP Endpoint

```
http://127.0.0.1:<port>/mcp
```

---

## 9. Running the Backend API (FastAPI)

### File

```
dashboard_api.py
```

### Command

```bash
uvicorn dashboard_api:app --host 127.0.0.1 --port <custom> --reload
```

### Backend Details

- Framework: FastAPI
- Port: `9000`

### Base URL

```
http://127.0.0.1:<custom>
```

### Primary Endpoint

```
POST /flight-recovery
```

Example request:

```json
{
  "pnr": "<PNR>",
  "last_name": "<LAST_NAME>"
}
```

---

## 10. Running the Frontend UI

### Commands

```bash
cd ui
npm install
npm run dev
```

### UI URL

```text
http://localhost:<UI_PORT>
```

(The exact port depends on frontend configuration.)

---

## 11. Execution Order (MANDATORY)

Start the system **in this exact order**:

1. **Authenticate with Azure**
   ```bash
   az login
   ```

2. **Start MCP Server**
   ```bash
   python server.py
   ```

3. **Start Backend API**
   ```bash
   uvicorn dashboard_api:app --host 127.0.0.1 --port <custom> --reload
   ```

4. **Start UI**
   ```bash
   npm run dev
   ```

---

## 12. Ports & URLs Summary

| Component | URL |
|--------|-----|
| MCP Server | http://127.0.0.1:<port>/mcp |
| Backend API | http://127.0.0.1:<port> |
| Frontend UI | http://localhost:<UI_PORT> |

---

## 13. Common Issues

### Azure Authentication Error
Run:
```bash
az login
```

---

### Missing Environment Variables
Ensure `.env` exists and contains required keys.

---

### MCP Not Reachable
- Verify MCP server is running
- Verify ports in `config.yaml`
- Ensure no port conflicts

---

## 14. Assumptions

- AI Agent already exists in Azure
- Required Azure permissions are configured
- External APIs are reachable
- Ports are free on the local machine

---

## 15. Final Notes

- No secrets are committed to the repository
- Configuration is fully externalized
- Azure authentication uses CLI only
- System is reproducible from scratch

---


