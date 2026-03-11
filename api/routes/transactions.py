"""Transaction routes: upload CSVs, list, update."""

import tempfile
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Query

from api import store
from api.dependencies import get_config
from api.schemas import (
    BulkUpdateRequest,
    TransactionOut,
    TransactionUpdate,
    UploadResponse,
)
from src.categorizer import categorize_transactions
from src.csv_parser import detect_and_parse

router = APIRouter()


def _txn_to_out(txn_id: str, txn) -> TransactionOut:
    return TransactionOut(
        id=txn_id,
        date=txn.date,
        description=txn.description,
        amount=txn.amount,
        source=txn.source,
        property=txn.property,
        category=txn.category,
        txn_type=txn.txn_type,
        needs_review=txn.needs_review,
        raw_file=txn.raw_file,
    )


@router.post("/transactions/upload", response_model=UploadResponse)
async def upload_csvs(files: List[UploadFile] = File(...)):
    """
    Upload one or more CSV files (WF or Chase format).
    Returns auto-categorized transactions. Uncertain ones are flagged needs_review=true.
    Clears any previously uploaded transactions from the store.
    """
    config = get_config()

    # Save uploads to temp files and parse
    all_txns = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for upload in files:
            tmp_path = Path(tmpdir) / upload.filename
            content = await upload.read()
            tmp_path.write_bytes(content)
            try:
                txns = detect_and_parse(tmp_path)
                all_txns.extend(txns)
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"Failed to parse {upload.filename}: {e}")

    if not all_txns:
        raise HTTPException(status_code=422, detail="No transactions found in uploaded files.")

    # Apply skip_descriptions filter
    skip_patterns = [s.lower() for s in config.get("skip_descriptions", [])]
    if skip_patterns:
        all_txns = [
            t for t in all_txns
            if not any(p in t.description.lower() for p in skip_patterns)
        ]

    # Auto-categorize (non-interactive — Claude suggests, flags unknowns as REVIEW)
    all_txns = categorize_transactions(all_txns, config, interactive=False)

    # Store with UUIDs (replace previous session)
    store.transactions.clear()
    for txn in all_txns:
        txn_id = str(uuid.uuid4())
        store.transactions[txn_id] = txn

    out = [_txn_to_out(tid, t) for tid, t in store.transactions.items()]
    return UploadResponse(
        transactions=out,
        total=len(out),
        auto_categorized=sum(1 for t in out if not t.needs_review),
        needs_review=sum(1 for t in out if t.needs_review),
    )


@router.get("/transactions", response_model=List[TransactionOut])
def list_transactions(month: Optional[str] = Query(None, description="Filter by YYYY-MM")):
    """List transactions currently in the store, optionally filtered by month."""
    result = []
    for txn_id, txn in store.transactions.items():
        if month:
            try:
                year, mon = int(month[:4]), int(month[5:7])
            except (ValueError, IndexError):
                raise HTTPException(status_code=400, detail="month must be YYYY-MM format")
            if txn.date.year != year or txn.date.month != mon:
                continue
        result.append(_txn_to_out(txn_id, txn))
    return sorted(result, key=lambda t: (t.needs_review is False, t.date))


@router.patch("/transactions/{txn_id}", response_model=TransactionOut)
def update_transaction(txn_id: str, body: TransactionUpdate):
    """Update the property and/or category of a single transaction."""
    txn = store.transactions.get(txn_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if body.property is not None:
        txn.property = body.property
    if body.category is not None:
        txn.category = body.category
        txn.needs_review = False  # manual edit resolves review flag

    return _txn_to_out(txn_id, txn)


@router.delete("/transactions/{txn_id}", status_code=204)
def delete_transaction(txn_id: str):
    """Remove a transaction from the store (e.g. personal transactions to exclude)."""
    if txn_id not in store.transactions:
        raise HTTPException(status_code=404, detail="Transaction not found")
    del store.transactions[txn_id]


@router.post("/transactions/bulk-update", response_model=List[TransactionOut])
def bulk_update_transactions(body: BulkUpdateRequest):
    """Update property/category for multiple transactions at once."""
    updated = []
    for item in body.updates:
        txn = store.transactions.get(item.id)
        if txn is None:
            raise HTTPException(status_code=404, detail=f"Transaction {item.id} not found")
        if item.property is not None:
            txn.property = item.property
        if item.category is not None:
            txn.category = item.category
            txn.needs_review = False
        updated.append(_txn_to_out(item.id, txn))
    return updated
