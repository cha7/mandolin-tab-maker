# Mandolin Tab Maker installer for Windows 10 and 11. Press Windows+R, paste, press Enter:
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/cha7/mandolin-tab-maker/main/install.ps1 | iex"
#
# Downloads the app into %USERPROFILE%\MandolinTabMaker (MTAB_DIR to change it), installs
# uv (the Python package manager) into your user folder if it's missing, then the Python
# environment, puts a "Mandolin Tab Maker" shortcut on the Desktop, and starts the app.
# Running it again updates the app and keeps your tabs (out\) and caches (work\, .venv\).
# Needs no git, Node.js or Python of your own. ASCII only: it runs through irm | iex.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue" # Invoke-WebRequest is far faster without its progress bar

function Say($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Green }

try {
  $Repo = "cha7/mandolin-tab-maker"
  $Dir = if ($env:MTAB_DIR) { $env:MTAB_DIR } else { Join-Path $env:USERPROFILE "MandolinTabMaker" }

  Say "Downloading Mandolin Tab Maker into $Dir"
  $tmp = Join-Path ([IO.Path]::GetTempPath()) ("mtab-" + [guid]::NewGuid())
  New-Item -ItemType Directory -Force $tmp | Out-Null
  $zip = Join-Path $tmp "app.zip"
  Invoke-WebRequest "https://github.com/$Repo/archive/refs/heads/main.zip" -OutFile $zip -UseBasicParsing
  Expand-Archive $zip -DestinationPath $tmp
  New-Item -ItemType Directory -Force $Dir | Out-Null
  # Merges into the folder, so tabs and caches from before stay. Exit codes below 8 are success.
  robocopy (Join-Path $tmp "mandolin-tab-maker-main") $Dir /E /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "couldn't copy the app into $Dir" }
  Remove-Item $tmp -Recurse -Force

  $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
  if (-not (Test-Path $uv)) {
    $found = Get-Command uv -ErrorAction SilentlyContinue
    if ($found) { $uv = $found.Source }
  }
  if (-not (Test-Path $uv)) {
    Say "Installing uv (the Python package manager) into your user folder"
    $env:UV_NO_MODIFY_PATH = "1"
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (-not (Test-Path $uv)) { throw "couldn't install uv" }
  }

  Say "Installing the music tools (the first time downloads several GB; this can take 10 to 30 minutes)"
  Push-Location $Dir
  & $uv sync --no-dev
  $code = $LASTEXITCODE
  Pop-Location
  if ($code -ne 0) { throw "couldn't install the music tools. Run the same line again to retry." }

  # The launcher finds uv itself, so no user-folder path (which may not be ASCII) is written into it.
  $bat = Join-Path $Dir "Mandolin Tab Maker.bat"
  $lines = @(
    "@echo off",
    "rem Starts Mandolin Tab Maker (made by install.ps1). Close this window to stop it.",
    "cd /d ""%~dp0""",
    "set ""UV=%USERPROFILE%\.local\bin\uv.exe""",
    "if not exist ""%UV%"" set ""UV=uv""",
    """%UV%"" run --no-dev mtab app",
    "if errorlevel 1 pause"
  )
  Set-Content -Path $bat -Value $lines -Encoding ASCII

  $desktop = [Environment]::GetFolderPath("Desktop")
  $link = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop "Mandolin Tab Maker.lnk"))
  $link.TargetPath = $bat
  $link.WorkingDirectory = $Dir
  $link.IconLocation = (Join-Path $Dir "assets\mandolin.ico")
  $link.Description = "Mandolin Tab Maker"
  $link.Save()

  Say "Installed. Next time, double-click ""Mandolin Tab Maker"" on your Desktop."
  Say "Starting Mandolin Tab Maker"
  & $bat
} catch {
  Write-Host ""
  Write-Host "Sorry: $($_.Exception.Message)" -ForegroundColor Red
  Read-Host "Press Enter to close this window"
}
