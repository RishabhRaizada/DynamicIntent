import json
import copy
from typing import Dict, Any, List, Optional


class UserServiceWrapper:
    
    def __init__(self, cdp_file: str = "cdp.json", seat_data_file: str = None):
        self.cdp_file = cdp_file
        self.seat_data_file = seat_data_file
        self.users_data = None
        self.seat_data = None
        self._load_cdp_data()
    
    def _load_cdp_data(self):
        try:
            with open(self.cdp_file, "r", encoding="utf-8") as f:
                self.users_data = json.load(f)
        except FileNotFoundError:
            print(f"Warning: CDP file '{self.cdp_file}' not found")
            self.users_data = []
    
    def _load_seat_data(self):
        if self.seat_data is None and self.seat_data_file:
            try:
                with open(self.seat_data_file, "r", encoding="utf-8") as f:
                    self.seat_data = json.load(f)
            except FileNotFoundError:
                print(f"Warning: Seat data file '{self.seat_data_file}' not found")
                self.seat_data = {}
    
    @staticmethod
    def _normalize_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return v == 1
        if isinstance(v, str):
            return v.strip().lower() in ["true", "1", "yes"]
        return False
    
    @staticmethod
    def _normalize_student(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return v > 0
        if isinstance(v, str):
            return v.strip().isdigit() and int(v) > 0
        return False
    
    def check_autorecovery_eligibility(self, last_name: str, email_or_phone: str) -> Dict[str, Any]:
        if not self.users_data:
            return {
                "status": "error",
                "message": "CDP data not loaded"
            }
        
        last_name = last_name.strip().lower()
        email_or_phone = email_or_phone.strip().lower()
        
        for user in self.users_data:
            user_info = user.get("user_info", {})
            
            ln = user_info.get("USR_LASTNAME", "").strip().lower()
            ph = str(user_info.get("USR_MOBILE", "")).strip().lower()
            em = user_info.get("USR_EMAIL", "").strip().lower()
            
            if ln != last_name:
                continue
            
            if not (email_or_phone == ph or email_or_phone == em):
                continue
            
            guid = user_info.get("USR_GUID", "")
            bookings = user.get("booking_details", [])
            
            is_highspender = False
            is_student = False
            
            for b in bookings:
                h_high = self._normalize_bool(b.get("HIGHSPENDERHIGHFREQ", False))
                h_low = self._normalize_bool(b.get("HIGHSPENDERLOWFREQ", False))
                student = self._normalize_student(b.get("STUDENT", 0))
                
                if h_high or h_low:
                    is_highspender = True
                if student:
                    is_student = True
            
            eligible = is_highspender or is_student
            
            if eligible:
                return {
                    "status": "eligible",
                    "eligible": True,
                    "user_info": {
                        "USR_FIRSTNAME": user_info.get("USR_FIRSTNAME", ""),
                        "USR_LASTNAME": user_info.get("USR_LASTNAME", ""),
                        "USR_MOBILE": user_info.get("USR_MOBILE", ""),
                        "USR_EMAIL": user_info.get("USR_EMAIL", ""),
                        "USR_GUID": guid
                    },
                    "criteria": {
                        "is_highspender": is_highspender,
                        "is_student": is_student
                    }
                }
            
            return {
                "status": "not_eligible",
                "eligible": False,
                "message": "User is not eligible for Autorecovery"
            }
        
        return {
            "status": "not_found",
            "eligible": False,
            "message": "Invalid user info or user not found"
        }
    
    def find_user_profile(self, last_name: str, email_or_phone: str) -> Dict[str, Any]:
        if not self.users_data:
            return {
                "status": "error",
                "message": "CDP data not loaded"
            }
        
        last_name = last_name.strip().lower()
        email_or_phone = email_or_phone.strip().lower()
        
        matches = []
        
        for user in self.users_data:
            user_info = user.get("user_info", {})
            
            ln = user_info.get("USR_LASTNAME", "").strip().lower()
            ph = str(user_info.get("USR_MOBILE", "")).strip().lower()
            em = user_info.get("USR_EMAIL", "").strip().lower()
            
            if ln != last_name:
                continue
            
            if not (email_or_phone == ph or email_or_phone == em):
                continue
            
            matches.append({
                "user_info": user_info,
                "booking_details": user.get("booking_details", [])
            })
        
        if not matches:
            return {
                "status": "not_found",
                "message": "Invalid user info or user not found"
            }
        
        return {
            "status": "success",
            "data": matches
        }
    
    def filter_available_seats(self, seat_data: Optional[Dict[str, Any]] = None, 
                              output_file: Optional[str] = None) -> Dict[str, Any]:
        if seat_data is None:
            self._load_seat_data()
            seat_data = self.seat_data
        
        if not seat_data:
            return {
                "status": "error",
                "message": "No seat data available"
            }
        
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
        
        if output_file:
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)
                print(f"Filtered seat data saved to: {output_file}")
            except Exception as e:
                print(f"Error saving to file: {e}")
        
        return result
    
    def get_user_complete_info(self, last_name: str, email_or_phone: str) -> Dict[str, Any]:
        eligibility_result = self.check_autorecovery_eligibility(last_name, email_or_phone)
        profile_result = self.find_user_profile(last_name, email_or_phone)
        
        return {
            "eligibility": eligibility_result,
            "profile": profile_result,
            "timestamp": self._get_timestamp()
        }
    
    @staticmethod
    def _get_timestamp():
        from datetime import datetime
        return datetime.now().isoformat()
    
    def batch_check_eligibility(self, users: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        results = []
        for user in users:
            last_name = user.get("last_name", "")
            email_or_phone = user.get("email_or_phone", "")
            
            result = self.check_autorecovery_eligibility(last_name, email_or_phone)
            results.append({
                "input": user,
                "result": result
            })
        
        return results


def create_wrapper(cdp_file: str = "cdp.json", seat_data_file: str = None) -> UserServiceWrapper:
    return UserServiceWrapper(cdp_file, seat_data_file)


def main():
    print("=" * 60)
    print("USER SERVICE WRAPPER - UNIFIED INTERFACE")
    print("=" * 60)
    print()
    print("Available Operations:")
    print("1. Check Autorecovery Eligibility")
    print("2. Find User Profile")
    print("3. Filter Available Seats")
    print("4. Get Complete User Info")
    print("5. Exit")
    print()
    
    wrapper = UserServiceWrapper(cdp_file="cdp.json")
    
    while True:
        choice = input("\nSelect operation (1-5): ").strip()
        
        if choice == "1":
            last_name = input("Last Name: ").strip()
            email_or_phone = input("Email / Phone Number: ").strip()
            
            if last_name and email_or_phone:
                result = wrapper.check_autorecovery_eligibility(last_name, email_or_phone)
                print("\n" + "=" * 60)
                print("ELIGIBILITY RESULT:")
                print("=" * 60)
                print(json.dumps(result, indent=2))
        
        elif choice == "2":
            last_name = input("Last Name: ").strip()
            email_or_phone = input("Email / Phone Number: ").strip()
            
            if last_name and email_or_phone:
                result = wrapper.find_user_profile(last_name, email_or_phone)
                print("\n" + "=" * 60)
                print("PROFILE RESULT:")
                print("=" * 60)
                print(json.dumps(result, indent=2))
        
        elif choice == "3":
            seat_file = input("Seat data file path (or press Enter to skip): ").strip()
            output_file = input("Output file path (default: available_seats.json): ").strip()
            
            if not output_file:
                output_file = "available_seats.json"
            
            if seat_file:
                wrapper.seat_data_file = seat_file
            
            result = wrapper.filter_available_seats(output_file=output_file)
            
            if result.get("status") != "error":
                print("\n✅ Seats filtered successfully!")
            else:
                print(f"\n❌ Error: {result.get('message')}")
        
        elif choice == "4":
            last_name = input("Last Name: ").strip()
            email_or_phone = input("Email / Phone Number: ").strip()
            
            if last_name and email_or_phone:
                result = wrapper.get_user_complete_info(last_name, email_or_phone)
                print("\n" + "=" * 60)
                print("COMPLETE USER INFO:")
                print("=" * 60)
                print(json.dumps(result, indent=2))
        
        elif choice == "5":
            print("\nExiting... Goodbye!")
            break
        
        else:
            print("\n❌ Invalid choice. Please select 1-5.")


if __name__ == "__main__":
    main()
