"""Pydantic request/response models for the Rental P&L API."""

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class TransactionOut(BaseModel):
    id: str
    date: date
    description: str
    amount: float
    source: str
    property: Optional[str]
    category: Optional[str]
    txn_type: str
    needs_review: bool
    raw_file: str


class TransactionUpdate(BaseModel):
    property: Optional[str] = None
    category: Optional[str] = None


class BulkUpdateItem(BaseModel):
    id: str
    property: Optional[str] = None
    category: Optional[str] = None


class BulkUpdateRequest(BaseModel):
    updates: List[BulkUpdateItem]


class UploadResponse(BaseModel):
    transactions: List[TransactionOut]
    total: int
    auto_categorized: int
    needs_review: int


class PipelineRunRequest(BaseModel):
    month: Optional[str] = None  # YYYY-MM filter; None = all in store


class PipelineRunResponse(BaseModel):
    status: str
    transactions_written: int
    details: Dict[str, int]
    message: str


class PipelineStatusResponse(BaseModel):
    running: bool
    last_run: Optional[Dict[str, Any]]


class VendorMappingOut(BaseModel):
    key: str
    property: str
    category: str


class VendorMappingCreate(BaseModel):
    key: str
    property: str
    category: str


class CategoriesResponse(BaseModel):
    categories: List[str]
    income_categories: List[str]


class PropertiesResponse(BaseModel):
    properties: List[str]


class OverviewResponse(BaseModel):
    total_income: float
    total_expenses: float
    net_cash_flow: float
