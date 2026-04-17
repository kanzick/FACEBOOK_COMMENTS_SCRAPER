@echo off
setlocal

set "SCRIPT=%~dp0comments.py"
set "PS1=%TEMP%\scraper_setup.ps1"

echo.
echo  Setting up run-comments command...
echo.

(
echo $profile_path = $PROFILE
echo $script_path = '%SCRIPT:\=\\%'
echo if (^!(Test-Path $profile_path^)^) { New-Item -Path $profile_path -Force ^| Out-Null }
echo $content = Get-Content $profile_path -Raw -ErrorAction SilentlyContinue
echo if ($content -notlike '*run-comments*'^) {
echo  Add-Content $profile_path "`nfunction run-comments { python '$script_path' }"
echo  Write-Host '  OK  Added run-comments to profile.' -ForegroundColor Green
echo } else {
echo  Write-Host '  OK  run-comments already in profile.' -ForegroundColor Cyan
echo }
echo $policy = Get-ExecutionPolicy -Scope CurrentUser
echo if ($policy -eq 'Restricted' -or $policy -eq 'Undefined'^) {
echo  Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
echo  Write-Host '  OK  ExecutionPolicy set to RemoteSigned.' -ForegroundColor Green
echo } else {
echo  Write-Host '  OK  ExecutionPolicy OK.' -ForegroundColor Cyan
echo }
) > "%PS1%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
del "%PS1%"

echo.
echo  Setup complete. Launching scraper...
timeout /t 2 /nobreak >nul

set "LAUNCH=%TEMP%\scraper_launch.ps1"
echo python '%SCRIPT:\=\\%' > "%LAUNCH%"

where wt >nul 2>&1
if %errorlevel% == 0 (
  wt new-tab -- powershell -NoExit -ExecutionPolicy Bypass -File "%LAUNCH%"
  ) else (
  start "Facebook Comment Scraper" powershell -NoExit -ExecutionPolicy Bypass -File "%LAUNCH%"
)

exit
