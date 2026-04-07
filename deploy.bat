@echo off
setlocal

set PROJECT=rental-pnl-automation
set REGION=us-central1
set SERVICE=rental-pnl

:: Use a timestamp tag to force a new revision on every deploy
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmm"') do set TAG=%%I
set IMAGE=%REGION%-docker.pkg.dev/%PROJECT%/%SERVICE%/%SERVICE%:%TAG%

echo.
echo Building image with tag %TAG%...
call gcloud builds submit --tag "%IMAGE%" --project=%PROJECT%

echo.
echo Deploying to Cloud Run...
call gcloud run deploy %SERVICE% --image="%IMAGE%" --region=%REGION% --project=%PROJECT%

echo.
echo Done. Service URL:
gcloud run services describe %SERVICE% --region=%REGION% --project=%PROJECT% --format="value(status.url)"
