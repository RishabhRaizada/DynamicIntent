import copy
from typing import Dict, Any
import json


def filter_available_seats_keep_structure(seat_data: Dict[str, Any]) -> Dict[str, Any]:

    result = copy.deepcopy(seat_data)

    seat_maps = result.get("data", {}).get("seatMaps", [])

    for seat_map_entry in seat_maps:
        seat_map = seat_map_entry.get("seatMap", {})
        decks = seat_map.get("decks", {})

        for deck in decks.values():
            compartments = deck.get("compartments", {})

            for cabin in compartments.values():
                units = cabin.get("units", [])

                cabin["units"] = [
                    seat for seat in units
                    if seat.get("assignable") is True
                    and seat.get("availability", 0) > 0
                ]

    return result

with open("/Users/rishabhraizada/Desktop/AIonOS Uniform/Dashboard UI - MCP/data/available_seats.json", "r", encoding="utf-8") as f:
    seat_data = json.load(f)

filtered_data = filter_available_seats_keep_structure(seat_data)

with open("available_seats.json", "w", encoding="utf-8") as f:
    json.dump(filtered_data, f, indent=2)

print("Saved: available_seats.json")