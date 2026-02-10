import json
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
from config.loader import load_config


config, _ = load_config()

try:
    PROJECT_ENDPOINT = config["azure"]["project_endpoint"]
    AGENT_ID = config["azure"]["agent_id"]
except KeyError as e:
    raise RuntimeError(f"Missing config key: {e}")

MCP_URL = (
    f"http://{config['server']['host']}:"
    f"{config['server']['mcp_port']}"
    f"{config['server']['mcp_path']}"
)


app = FastAPI(title="Flight Recovery API")



class RecoveryRequest(BaseModel):
    pnr: str
    last_name: str




def execute_mcp_tool(tool_name: str, arguments: dict) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        },
        "id": 1
    }

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"
    }

    response = requests.post(MCP_URL, json=payload, headers=headers, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(response.text)

    for line in response.text.splitlines():
        if not line.startswith("data:"):
            continue

        raw = line.replace("data:", "", 1).strip()
        mcp_payload = json.loads(raw)
        result = mcp_payload.get("result", {})

        structured = result.get("structuredContent", {})
        content = structured.get("content", [])

        if content and content[0].get("type") == "json":
            return content[0]["json"]

        for item in result.get("content", []):
            if item.get("type") == "text":
                try:
                    embedded = json.loads(item["text"])
                    for c in embedded.get("content", []):
                        if c.get("type") == "json":
                            return c["json"]
                except Exception:
                    pass

    raise RuntimeError("No MCP JSON response found")



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.post("/flight-recovery")
def flight_recovery(request: RecoveryRequest):
    try:

        mcp_data = execute_mcp_tool(
            "recover_passenger",
            {"pnr": request.pnr, "last_name": request.last_name}
        )


        if mcp_data.get("status") != "success":
            return {
                "status": mcp_data.get("status"),
                "reason": mcp_data.get("reason"),
                "message": "Passenger not eligible for auto-recovery. Agent NOT invoked."
            }

        recovery = mcp_data.get("recovery", {})


        if not recovery.get("available_flights") or not recovery.get("available_seats"):
            return {
                "status": "error",
                "message": "Flights or seats missing — agent invocation blocked."
            }


        booking = (
            mcp_data.get("passenger", {})
            .get("Past Data", [{}])[0]
            .get("booking_details", [{}])[0]
        )

        if booking.get("STUDENT", 0) > 0:
            recovery["available_seats"] = [
                s for s in recovery["available_seats"]
                if s.get("travel_class") == "Y"
            ]


        client = AIProjectClient(
            endpoint=PROJECT_ENDPOINT,
            credential=DefaultAzureCredential()
        )

        with client:
            thread = client.agents.threads.create()

            client.agents.messages.create(
                thread_id=thread.id,
                role="user",
                content = f"""
You are a STRICT Flight & Seat Recovery Decision Engine.
Passenger Profile:
--------------------------------
INPUT DATA (ACTUAL MCP RESPONSE - THIS IS YOUR UNIVERSE)
--------------------------------

Passenger Profile:
{json.dumps(mcp_data.get('passenger', {}), indent=2)}

Original Flight:
{json.dumps(mcp_data.get('original_flight', {}), indent=2)}

Available Flights (YOU MUST SELECT FROM THIS LIST):
{json.dumps(recovery.get('available_flights', []), indent=2)}

Available Seats (YOU MUST SELECT FROM THIS LIST):
{json.dumps(recovery.get('available_seats', []), indent=2)}
You are a STRICT Flight & Seat Optimization Engine.

ABSOLUTE RULES (FAIL IF VIOLATED):
1. You MUST ONLY use flights and seats provided in the input JSON.
2. You MUST NOT invent flight_uid, flight_number, seat_number, or prices.
3. If any identifier is not found in the input → FAIL.
--------------------------------
ORIGINAL BOOKING CONSTRAINTS (MANDATORY)
--------------------------------

The original_flight represents the passenger's contractual booking intent.

MANDATORY RULES:

1. Route Preservation:
- selected_flight.origin MUST equal original_flight.origin
- selected_flight.destination MUST equal original_flight.destination
- If no such flight exists → FAIL

2. Time Proximity:
- Prefer flights whose utcDeparture is closest to original_flight.utc_scheduled_departure
- Prefer earlier arrival over later arrival when possible

3. Cabin Preservation:
- If original_flight.cabin_class == "Business":
  - Must preserve Business cabin in recovery
  - Only downgrade if no business seats exist
- If original_flight.cabin_class == "Economy":
  - Economy acceptable, upgrade optional for highspender

These rules apply BEFORE CDP logic.
CDP rules apply only after these booking constraints are satisfied.

--------------------------------
PRIORITY 0 (ORIGINAL BOOKING OVERRIDE)
--------------------------------

If original_flight.cabin_class == "Business":
- ALWAYS select a flight that has min_business_fare available
- ALWAYS select a seat with travel_class == "C"
- This rule OVERRIDES STUDENT logic
- Only downgrade to Economy if NO business seats exist


If student > 0 AND original_flight.cabin_class == "Economy":
- MUST NOT select travel_class == "C"
- MUST select economy class only
- FAIL if only business seats are selected

If original_flight.cabin_class == "Economy":
- Proceed with CDP rules as defined



--------------------------------
CDP PRIORITY ORDER (MANDATORY)
--------------------------------

Evaluate booking_details[0] first.

PRIORITY 1 (OVERRIDES EVERYTHING):
- If STUDENT > 0:
  - ALWAYS choose the CHEAPEST min_economy_fare flight
  - NEVER choose business class
  - Seat priority: cheapest economy seat, ignore comfort
  - Comfort signals (LEGROOM, XL, AISLE) are SECONDARY

- If HIGHSPENDERHIGHFREQ == true OR HIGHSPENDERLOWFREQ == true:
  - Price is IRRELEVANT
  - Prefer comfort, stretch, business class
  - Prefer earlier arrival and non-stop

--------------------------------
PRIORITY 2 (ONLY IF NOT STUDENT / HIGHSPENDER)
--------------------------------

Journey Intent:
- BUSINESS > LEISURE → time + comfort
- LEISURE >= BUSINESS → cost + flexibility

--------------------------------
FLIGHT SCORING (STRICT)
--------------------------------

For EACH available flight:

Start score = 0

Base:
+40 if NonStop
+25 if utcArrival earlier than original flight
+20 if utcDeparture closest to original flight
-15 if fillingFast == true

STUDENT OVERRIDE:
- score = -min_economy_fare
- IGNORE all comfort bonuses

HIGHSPENDER OVERRIDE:
+40 if isStretch == true
+30 if min_business_fare exists

--------------------------------
SEAT SCORING (STRICT)
--------------------------------

For EACH seat on SELECTED flight:

Start score = 0

STUDENT OVERRIDE:
- Prefer travel_class == "Y"
- Ignore LEGROOM, XL, WINDOW, AISLE
- Pick seat with highest availability or lowest cost proxy

HIGHSPENDER OVERRIDE:
+40 if travel_class == "C"
+25 if LEGROOM
+20 if XL
+15 if AISLE or WINDOW
==============================
OUTPUT MANDATORY (STRICT JSON ONLY)
==============================
You MUST return EXACTLY this JSON structure.
{{
    
  "selected_flight": {{ ... }},
  "selected_seat": {{ ... }},
  "reasoning": {{
    "flight_reason": "Explicitly reference STUDENT or HIGHSPENDER rule",
    "seat_reason": "Explicitly reference STUDENT or HIGHSPENDER rule"
  }}
}}

FAIL IF:
- Cheapest flight is NOT selected for STUDENT
- Business class is selected for STUDENT
- Any invented ID appears
"""
)

            run = client.agents.runs.create(
                thread_id=thread.id,
                agent_id=AGENT_ID
            )

            while True:
                run = client.agents.runs.get(thread.id, run.id)
                if run.status == "completed":
                    break

            messages = client.agents.messages.list(
                thread_id=thread.id,
                order=ListSortOrder.ASCENDING
            )

            for msg in reversed(list(messages)):
                if msg.role == "assistant":
                    agent_output = json.loads(msg.text_messages[0].text.value)
                    return {
                        "status": "success",
                        **agent_output
                    }


        raise RuntimeError("Agent produced no output")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
