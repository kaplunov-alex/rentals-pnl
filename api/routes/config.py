"""Config routes: vendor mappings, categories, properties."""

import os

from fastapi import APIRouter, HTTPException

from api.dependencies import get_config, reload_config
from api.schemas import (
    CategoriesResponse,
    OverviewResponse,
    PropertiesResponse,
    VendorMappingCreate,
    VendorMappingOut,
)
from src.config_updater import save_vendor_mapping
from src.sheets_writer import get_overview_cells

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

    save_vendor_mapping(body.key, body.property, body.category)
    reload_config()
    return VendorMappingOut(key=body.key, property=body.property, category=body.category)


@router.delete("/config/vendor-mappings/{key:path}", status_code=204)
def delete_vendor_mapping(key: str):
    import yaml
    config = get_config()
    mappings = config.get("vendor_mappings") or {}

    # URL-decode the key (slashes and special chars may be encoded)
    from urllib.parse import unquote
    decoded_key = unquote(key)

    if decoded_key not in mappings:
        raise HTTPException(status_code=404, detail=f"Vendor mapping not found: {decoded_key!r}")

    del mappings[decoded_key]

    with open("config.yaml", "r") as f:
        raw = yaml.safe_load(f)
    raw["vendor_mappings"] = mappings
    with open("config.yaml", "w") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)

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
