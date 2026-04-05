"""
One-time script: write categories into the "Categories" tab of the P&L Google Sheet.
Categories are defined here directly (source of truth is the sheet, not config.yaml).

Tab format: Category | Type  (Type = "income" or "expense")

Run with:
    .venv\Scripts\python scripts\seed_categories_sheet.py
"""
import yaml
import gspread

CONFIG_PATH = "config.yaml"
TAB_NAME = "Categories"
HEADERS = ["Category", "Type"]

INCOME_CATEGORIES = [
    "Rental Income",
    "Late Fees",
    "Security Deposit",
    "Other Income",
]

EXPENSE_CATEGORIES = [
    "Mortgage/Loan Payment",
    "Property Tax",
    "Insurance",
    "HOA Fees",
    "Property Management",
    "Repairs & Maintenance",
    "Utilities (Owner Paid)",
    "Landscaping",
    "Household Goods",
    "Advertising/Vacancy",
    "Legal & Accounting",
    "Travel/Mileage",
    "Supplies",
    "Meals/Restaurants",
    "Meals/Not-Restaurants",
    "Subscriptions",
    "Other Expenses",
]


def main():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    spreadsheet_id = config["spreadsheet_id"]
    sa_path = config.get("service_account_path", "service_account.json")

    client = gspread.service_account(filename=sa_path)
    spreadsheet = client.open_by_key(spreadsheet_id)

    try:
        ws = spreadsheet.worksheet(TAB_NAME)
        print(f"Found existing tab '{TAB_NAME}' — clearing it.")
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=TAB_NAME, rows=100, cols=2)
        print(f"Created tab '{TAB_NAME}'.")

    rows = [HEADERS]
    for cat in INCOME_CATEGORIES:
        rows.append([cat, "income"])
    for cat in EXPENSE_CATEGORIES:
        rows.append([cat, "expense"])

    ws.update(rows, value_input_option="USER_ENTERED")
    print(f"Written {len(rows) - 1} categories to '{TAB_NAME}'.")


if __name__ == "__main__":
    main()
