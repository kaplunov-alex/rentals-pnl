@echo off
setlocal

set PROJECT=rental-pnl-automation
set REGION=us-central1
set SERVICE=rental-pnl
set IMAGE=%REGION%-docker.pkg.dev/%PROJECT%/%SERVICE%/%SERVICE%:latest

echo.
echo Building image...
gcloud builds submit --tag "%IMAGE%" --project=%PROJECT%
if %ERRORLEVEL% neq 0 (
    echo Build failed. Aborting deploy.
    exit /b 1
)

echo.
echo Deploying to Cloud Run...
gcloud run deploy %SERVICE% --image="%IMAGE%" --region=%REGION% --project=%PROJECT%
if %ERRORLEVEL% neq 0 (
    echo Deploy failed.
    exit /b 1
)

echo.
echo Done. Service URL:
gcloud run services describe %SERVICE% --region=%REGION% --project=%PROJECT% --format="value(status.url)"
