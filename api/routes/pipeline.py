"""Pipeline routes: trigger a run, check status."""

from typing import Optional

from fastapi import APIRouter, HTTPException

from api import store
from api.dependencies import get_config
from api.schemas import PipelineRunRequest, PipelineRunResponse, PipelineStatusResponse
from src.sheets_writer import append_transactions

router = APIRouter()


@router.post("/pipeline/run", response_model=PipelineRunResponse)
def run_pipeline(body: PipelineRunRequest = PipelineRunRequest()):
    """
    Write transactions from the in-memory store to Google Sheets.
    Optionally filter by month (YYYY-MM). Transactions must already be categorized.
    """
    if store.is_running:
        raise HTTPException(status_code=409, detail="A pipeline run is already in progress.")

    if not store.transactions:
        raise HTTPException(status_code=422, detail="No transactions in store. Upload CSVs first.")

    # Collect transactions, optionally filtered by month
    txns = list(store.transactions.values())
    if body.month:
        try:
            year, mon = int(body.month[:4]), int(body.month[5:7])
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="month must be YYYY-MM format")
        txns = [t for t in txns if t.date.year == year and t.date.month == mon]
        if not txns:
            raise HTTPException(
                status_code=422,
                detail=f"No transactions in store for month {body.month}."
            )

    # Require all transactions to have property + category assigned
    unresolved = [t for t in txns if not t.property or t.needs_review]
    if unresolved:
        descriptions = [t.description for t in unresolved[:5]]
        raise HTTPException(
            status_code=422,
            detail=f"{len(unresolved)} transaction(s) still need review: {descriptions}"
        )

    config = get_config()
    spreadsheet_id = config["spreadsheet_id"]
    service_account_path = config.get("service_account_path", "service_account.json")

    store.is_running = True
    try:
        written = append_transactions(txns, spreadsheet_id, service_account_path)
        total_written = sum(written.values())
        store.last_run = {
            "status": "success",
            "transactions_written": total_written,
            "details": written,
            "month": body.month,
        }
        return PipelineRunResponse(
            status="success",
            transactions_written=total_written,
            details=written,
            message=f"Wrote {total_written} transactions to Google Sheets.",
        )
    except Exception as e:
        store.last_run = {"status": "error", "message": str(e)}
        raise HTTPException(status_code=500, detail=f"Pipeline run failed: {e}")
    finally:
        store.is_running = False


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
def pipeline_status():
    """Check whether a run is in progress and what the last run result was."""
    return PipelineStatusResponse(
        running=store.is_running,
        last_run=store.last_run,
    )
