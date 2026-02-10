import json

CDP_FILE = "/Users/rishabhraizada/Desktop/AIonOS Uniform/Dashboard UI - MCP/data/cdp.json"


def normalize_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v == 1
    if isinstance(v, str):
            return v.strip().lower() in ["true", "1", "yes"]
    return False


def normalize_student(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v > 0
    if isinstance(v, str):
        return v.strip().isdigit() and int(v) > 0
    return False


def check_user_autorecovery_eligibility(last_name, email_or_phone):

    try:
        with open(CDP_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except FileNotFoundError:
        print(json.dumps({
            "status": "error",
            "message": "CDP data file 'cdp.json' not found in knowledge base"
        }, indent=2))
        return {"status": "error"}

    last_name = last_name.strip().lower()
    email_or_phone = email_or_phone.strip().lower()

    for user in users:
        user_info = user.get("user_info", {})

        ln = user_info.get("USR_LASTNAME", "").strip().lower()
        ph = str(user_info.get("USR_MOBILE", "")).strip().lower()
        em = user_info.get("USR_EMAIL", "").strip().lower()

        # last name must match
        if ln != last_name:
            continue

        # must match email OR phone
        if not (email_or_phone == ph or email_or_phone == em):
            continue

        guid = user_info.get("USR_GUID", "")
        bookings = user.get("booking_details", [])

        is_highspender = False
        is_student = False

        for b in bookings:
            h_high = normalize_bool(b.get("HIGHSPENDERHIGHFREQ", False))
            h_low = normalize_bool(b.get("HIGHSPENDERLOWFREQ", False))
            student = normalize_student(b.get("STUDENT", 0))

            if h_high or h_low:
                is_highspender = True
            if student:
                is_student = True

        eligible = is_highspender or is_student

        if eligible:
            print("User is eligible for Autorecovery")
            result = {
                "user_info": {
                    "USR_FIRSTNAME": user_info.get("USR_FIRSTNAME", ""),
                    "USR_LASTNAME": user_info.get("USR_LASTNAME", ""),
                    "USR_MOBILE": user_info.get("USR_MOBILE", ""),
                    "USR_EMAIL": user_info.get("USR_EMAIL", ""),
                    "USR_GUID": guid
                }
            }
            print(json.dumps(result, indent=2))
            return result

        print("User is not eligible for Autorecovery")
        return {"eligible": False}

    print("Invalid user info or user not found")
    return {"eligible": False, "reason": "invalid_user_info"}


def main():
    last_name = input("Last Name : ").strip()
    email_or_phone = input("Email / Phone Number : ").strip()

    if not last_name or not email_or_phone:
        print("Both fields are required")
        return

    check_user_autorecovery_eligibility(last_name, email_or_phone)


if __name__ == "__main__":
    main()

# MCP-compatible alias
def validate_request(last_name: str, email_or_phone: str):
    """
    MCP validation wrapper.
    Calls existing eligibility logic without changing it.
    """
    return check_user_autorecovery_eligibility(last_name, email_or_phone)
