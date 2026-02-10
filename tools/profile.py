import json

CDP_FILE = "/Users/rishabhraizada/Desktop/AIonOS Uniform/Dashboard UI - MCP/data/cdp.json"


def find_users(last_name, email_or_phone):

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

    matches = []

    for user in users:
        user_info = user.get("user_info", {})

        ln = user_info.get("USR_LASTNAME", "").strip().lower()
        ph = str(user_info.get("USR_MOBILE", "")).strip().lower()
        em = user_info.get("USR_EMAIL", "").strip().lower()

        # last name must match
        if ln != last_name:
            continue

        # must match phone OR email
        if not (email_or_phone == ph or email_or_phone == em):
            continue

        matches.append({
            "user_info": user_info,
            "booking_details": user.get("booking_details", [])
        })

    if not matches:
        print("Invalid user info or user not found")
        return {"status": "not_found"}

    print(json.dumps(matches, indent=2))
    return matches


def main():
    last_name = input("Last Name : ").strip()
    email_or_phone = input("Email / Phone Number : ").strip()

    if not last_name or not email_or_phone:
        print("Both fields are required")
        return

    find_users(last_name, email_or_phone)


if __name__ == "__main__":
    main()
