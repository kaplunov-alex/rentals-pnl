"""
One-time script: write vendor_mappings from config.yaml into the
"Vendor Mappings" tab of the P&L Google Sheet.

Run with:
    .venv/Scripts/python scripts/seed_vendor_mappings_sheet.py
"""
import yaml
import gspread

CONFIG_PATH = "config.yaml"
TAB_NAME = "Vendor Mappings"
HEADERS = ["Key", "Property", "Category"]


def main():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    spreadsheet_id = config["spreadsheet_id"]
    sa_path = config.get("service_account_path", "service_account.json")
    mappings: dict = config.get("vendor_mappings", {})

    client = gspread.service_account(filename=sa_path)
    spreadsheet = client.open_by_key(spreadsheet_id)

    try:
        ws = spreadsheet.worksheet(TAB_NAME)
        print(f"Found existing tab '{TAB_NAME}' — clearing it.")
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=TAB_NAME, rows=500, cols=3)
        print(f"Created tab '{TAB_NAME}'.")

    rows = [HEADERS] + [
        [key, v.get("property", ""), v.get("category", "")]
        for key, v in sorted(mappings.items())
    ]

    ws.update(rows, value_input_option="USER_ENTERED")
    print(f"Written {len(rows) - 1} vendor mappings to '{TAB_NAME}'.")


if __name__ == "__main__":
    main()
