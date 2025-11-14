from google.oauth2.service_account import Credentials
import gspread

SERVICE_ACCOUNT_FILE = "keys.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

# Option 1 (Recommended): Use sheet ID
sheet = client.open_by_key("1GrNsCpFHJ2XtSHw_DgI-_PORGKhBi1tkTSQyALJnKoQ").sheet1

# Option 2 (if name is unique): use title
# sheet = client.open("sample sheet").sheet1

sheet.append_row(["1", "DTU", "CSE", "3rd Year"])
sheet.append_row(["1", "DTU", "CSE", "3rd Year"])

sheet.append_row(["1", "DTU", "CSE", "3rd Year"])
sheet.append_row(["1", "DTU", "CSE", "3rd Year"])
sheet.append_row(["1", "DTU", "CSE", "3rd Year"])
sheet.append_row(["1", "DTU", "CSE", "3rd Year"])
sheet.append_row(["1", "DTU", "CSE", "3rd Year"])
sheet.append_row(["1", "DTU", "CSE", "3rd Year"])

print("✅ Action completed successfully")