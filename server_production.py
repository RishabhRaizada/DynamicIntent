import json
import logging
import requests
from fastmcp import FastMCP

from tools.validator import validate_request
from tools.profile import find_users
from config.loader import load_config


# -------------------------------------------------
# Load config & secrets
# -------------------------------------------------
config, secrets = load_config()

INDIGO_FLIGHT_SEARCH_URL = config["indigo"]["flight_search_url"]
INDIGO_SEAT_MAP_URL = config["indigo"]["seat_map_url"]
REQUEST_TIMEOUT = config.get("indigo", {}).get("timeout", 30)

INDIGO_USER_KEY = secrets["INDIGO_USER_KEY"]
INDIGO_AUTH_TOKEN = secrets["INDIGO_AUTH_TOKEN"]


# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flight-disruption-mcp")


# -------------------------------------------------
# MCP Server
# -------------------------------------------------
mcp = FastMCP("flight_disruption_mcp")


# -------------------------------------------------
# Static Data
# -------------------------------------------------
with open("data/cancell_trigger.json", "r", encoding="utf-8") as f:
    CANCELLATIONS = json.load(f)


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def find_cancellation(pnr: str):
    for c in CANCELLATIONS:
        if c.get("pnr") == pnr:
            return c
    return None


# -------------------------------------------------
# Indigo APIs (SECURE)
# -------------------------------------------------
def call_indigo_flight_search(origin, destination, date):
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "user_key": INDIGO_USER_KEY,
        "authorization": INDIGO_AUTH_TOKEN,
        "source": "android",
        "version": "7.3.3",
        "user-agent": "IndiGoUAT/7.3.3.1"
    }

    body = {
        "codes": {"currency": "INR", "vaxDoseNo": ""},
        "criteria": [{
            "dates": {"beginDate": date},
            "flightFilters": {"type": "All"},
            "stations": {
                "originStationCodes": [origin],
                "destinationStationCodes": [destination]
            }
        }],
        "passengers": {
            "residentCountry": "IN",
            "types": [{"count": 1, "discountCode": "", "type": "ADT"}]
        },
        "infantCount": 0,
        "taxesAndFees": "TaxesAndFees",
        "totalPassengerCount": 1,
        "searchType": "OneWay",
        "isRedeemTransaction": False
    }

    response = requests.post(
        INDIGO_FLIGHT_SEARCH_URL,
        json=body,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )

    logger.info("✈️ Indigo Flight API status: %s", response.status_code)

    if response.status_code != 200:
        logger.error("❌ Indigo flight search failed")
        return {}

    return response.json()


def call_indigo_seat_map():
    headers = {
        "accept": "application/json",
        "user_key": INDIGO_USER_KEY,
        "authorization": INDIGO_AUTH_TOKEN,
        "source": "android",
        "version": "7.3.3",
        "user-agent": "IndiGoUAT/7.3.3.1"
    }

    try:
        response = requests.get(
            INDIGO_SEAT_MAP_URL,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        logger.info("🪑 Indigo Seat API status: %s", response.status_code)

        if response.status_code != 200 or not response.content:
            logger.warning("⚠️ Seat API returned empty / error response")
            return None

        return response.json()

    except Exception as e:
        logger.error("❌ Seat API call failed: %s", e)
        return None


# -------------------------------------------------
# Extractors (UNCHANGED LOGIC)
# -------------------------------------------------
def extract_available_flights(flights_json: dict):
    flights = {}
    trips = flights_json.get("data", {}).get("trips", [])

    for trip in trips:
        for journey in trip.get("journeysAvailable", []):
            segments = journey.get("segments", [])
            if not segments:
                continue

            segment = segments[0]
            identifier = segment.get("identifier", {})
            designator = segment.get("designator", {})

            carrier = identifier.get("carrierCode")
            flight_no = identifier.get("identifier")
            utc_departure = designator.get("utcDeparture")

            if not all([carrier, flight_no, utc_departure]):
                continue

            flight_uid = journey.get("journeyKey")
            if flight_uid in flights:
                continue

            flights[flight_uid] = {
                "flight_uid": flight_uid,
                "flight_number": f"{carrier}{flight_no}",
                "origin": designator.get("origin"),
                "destination": designator.get("destination"),
                "utcDeparture": utc_departure,
                "utcArrival": designator.get("utcArrival"),
                "stops": journey.get("stops"),
                "flightType": journey.get("flightType"),
                "isStretch": segment.get("isStretch", False),
                "fillingFast": journey.get("fillingFast", False)
            }

    return list(flights.values())


def extract_available_seats_from_seatmap(seatmap_json: dict):
    if not seatmap_json or "data" not in seatmap_json:
        return []

    seats = []
    data = seatmap_json["data"]

    for sm in data.get("seatMaps", []):
        seat_map = sm.get("seatMap", {})
        for deck in seat_map.get("decks", {}).values():
            for cabin in deck.get("compartments", {}).values():
                for seat in cabin.get("units", []):
                    if seat.get("assignable") and seat.get("availability", 0) > 0:
                        seats.append({
                            "seat_number": seat.get("designator"),
                            "travel_class": seat.get("travelClassCode", "Y"),
                            "availability": seat.get("availability"),
                            "seat_type": [p.get("code") for p in seat.get("properties", [])]
                        })
    return seats


# -------------------------------------------------
# MCP Tool
# -------------------------------------------------
@mcp.tool()
def recover_passenger(pnr: str, last_name: str):
    logger.info("🚑 recover_passenger called")

    if not pnr or not last_name:
        return {"content": [{"type": "json", "json": {
            "final": True, "status": "error", "reason": "PNR_AND_LAST_NAME_REQUIRED"
        }}]}

    cancellation = find_cancellation(pnr)
    if not cancellation:
        return {"content": [{"type": "json", "json": {
            "final": True, "status": "error", "reason": "PNR_NOT_FOUND"
        }}]}

    if cancellation.get("event_type") != "flight_cancelled":
        return {"content": [{"type": "json", "json": {
            "final": True, "status": "not_applicable", "reason": "NO_FLIGHT_DISRUPTION"
        }}]}

    user_info = cancellation.get("user_info", {})
    email = user_info.get("USR_EMAIL")
    phone = str(user_info.get("USR_MOBILE", ""))

    eligibility = validate_request(last_name, email or phone)
    if not eligibility or not eligibility.get("eligible"):
        return {"content": [{"type": "json", "json": {
            "final": True, "status": "ineligible"
        }}]}

    profile = find_users(last_name, email or phone)

    origin = cancellation["origin"]
    destination = cancellation["destination"]
    date = cancellation["scheduled_departure_time"][:10]

    flights = extract_available_flights(
        call_indigo_flight_search(origin, destination, date)
    )

    seats = extract_available_seats_from_seatmap(
        call_indigo_seat_map()
    )

    return {"content": [{"type": "json", "json": {
        "final": True,
        "status": "success",
        "pnr": pnr,
        "passenger": {
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "past_data": profile
        },
        "original_flight": cancellation,
        "recovery": {
            "available_flights": flights,
            "available_seats": seats
        }
    }}]}


# -------------------------------------------------
# Run MCP
# -------------------------------------------------
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=config["server"]["host"],
        port=config["server"]["mcp_port"],
        path=config["server"]["mcp_path"],
        stateless_http=True
    )