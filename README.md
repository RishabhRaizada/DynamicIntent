# Flight Disruption Auto-Recovery System

## Overview
Automated passenger recovery system for flight cancellations using:
- MCP (FastMCP)
- Real-time flight & seat APIs
- CDP eligibility rules
- Azure AI Agent decisioning

## Components
- MCP Server (recover_passenger tool)
- FastAPI Dashboard API
- Indigo Flight & Seat APIs
- Azure AI Agent

## Prerequisites
- Python 3.10+
- Azure CLI logged in
- Internet access (Indigo APIs)

## Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
