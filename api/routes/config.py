"""Config routes: vendor mappings, categories, properties."""

import os

from fastapi import APIRouter, HTTPException

from api.dependencies import get_config, reload_config, _service_account_path
from fastapi import Query

from api.schemas import (
    CategoriesResponse,
    OverviewResponse,
    PropertiesResponse,
    SheetTransaction,
    VendorMappingCreate,
    VendorMappingOut,
)
from src.config_sheet import write_vendor_mapping, delete_vendor_mapping as sheet_delete_vendor_mapping
from src.sheets_writer import get_overview_cells, read_property_sheet_transactions

router = APIRouter()


@router.get("/config/vendor-mappings", response_model=list[VendorMappingOut])
def list_vendor_mappings():
    config = get_config()
    mappings = config.get("vendor_mappings") or {}
    return [
        VendorMappingOut(key=k, property=v["property"], category=v["category"])
        for k, v in mappings.items()
    ]


@router.post("/config/vendor-mappings", response_model=VendorMappingOut, status_code=201)
def add_vendor_mapping(body: VendorMappingCreate):
    config = get_config()
    properties = config.get("properties", [])
    all_categories = config.get("income_categories", []) + config.get("categories", [])

    if body.property not in properties:
        raise HTTPException(status_code=400, detail=f"Unknown property: {body.property!r}")
    if body.category not in all_categories:
        raise HTTPException(status_code=400, detail=f"Unknown category: {body.category!r}")

    spreadsheet_id = config["spreadsheet_id"]
    sa_path = _service_account_path(config)
    write_vendor_mapping(body.key, body.property, body.category, spreadsheet_id, sa_path)
    reload_config()
    return VendorMappingOut(key=body.key, property=body.property, category=body.category)


@router.delete("/config/vendor-mappings/{key:path}", status_code=204)
def delete_vendor_mapping(key: str):
    from urllib.parse import unquote
    config = get_config()
    mappings = config.get("vendor_mappings") or {}
    decoded_key = unquote(key)

    if decoded_key not in mappings:
        raise HTTPException(status_code=404, detail=f"Vendor mapping not found: {decoded_key!r}")

    spreadsheet_id = config["spreadsheet_id"]
    sa_path = _service_account_path(config)
    sheet_delete_vendor_mapping(decoded_key, spreadsheet_id, sa_path)
    reload_config()


@router.get("/config/categories", response_model=CategoriesResponse)
def list_categories():
    config = get_config()
    return CategoriesResponse(
        categories=config.get("categories", []),
        income_categories=config.get("income_categories", []),
    )


@router.get("/config/properties", response_model=PropertiesResponse)
def list_properties():
    config = get_config()
    return PropertiesResponse(properties=config.get("properties", []))


@router.get("/sheets/transactions", response_model=list[SheetTransaction])
def get_sheet_transactions(
    month: str = Query(..., description="YYYY-MM"),
    property: str = Query("all", description="Property name or 'all'"),
):
    """Read transactions directly from per-property Google Sheets for the given month."""
    config = get_config()
    svc = os.environ.get("SERVICE_ACCOUNT_PATH", "service_account.json")
    if not os.path.exists(svc):
        svc = "service_account.json"
    try:
        rows = read_property_sheet_transactions(config, month, property or "all", svc)
        return [SheetTransaction(**r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not read property sheets: {e}")


@router.get("/overview", response_model=OverviewResponse)
def get_overview():
    """Read E4:E6 from the Portfolio Summary tab (Total Income, Total Expenses, Net Cash Flow)."""
    config = get_config()
    spreadsheet_id = config.get("spreadsheet_id", "")
    svc = os.environ.get("SERVICE_ACCOUNT_PATH", "service_account.json")
    if not os.path.exists(svc):
        svc = "service_account.json"
    try:
        data = get_overview_cells(spreadsheet_id, svc)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not read overview from sheet: {e}")
    return OverviewResponse(**data)
