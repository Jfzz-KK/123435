# Creates the desktop shortcut for the DeepSeek Harness Web GUI.
#
#   pwsh -File tools\make_desktop_shortcut.ps1
#
# Produces ONE desktop shortcut:
#   "DeepSeek Harness (DSH) GUI.lnk" -- runs tools\dsh-gui-launch.vbs, which
#                                       starts the server if it is not already
#                                       running and then opens the browser.
#
# The shortcut deliberately targets wscript.exe rather than the URL.
#
# A .lnk whose target is http://127.0.0.1:3080 cannot start anything: Windows
# only hands the URL to the default browser, so clicking it fails whenever the
# server is not already running.  `dsh web` has no --detach option either, so
# something has to launch it -- that is what tools\dsh-gui-launch.vbs is for.
# See that file for the launch logic, and tools\dsh-web-background.vbs for the
# hidden server wrapper used by the logon scheduled task.
#
# Any stale .url of the same name is removed: on the desktop it looks identical
# (same name, same icon) but can never start the server, so it only causes
# "I clicked the icon and got a connection error" confusion.

param(
    [string]$Name      = "DeepSeek Harness (DSH) GUI",
    [string]$Launcher  = "",
    [string]$IconPath  = "",
    [string]$TargetDir = [Environment]::GetFolderPath('Desktop')
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# D:\deepseek-harness\tools\dsh-gui-launch.vbs, shared by every project here.
if (-not $Launcher) { $Launcher = Join-Path (Split-Path -Parent (Split-Path -Parent $root)) 'tools\dsh-gui-launch.vbs' }
if (-not $IconPath) { $IconPath = Join-Path $root 'assets\dsh-mascot.ico' }

if (-not (Test-Path $Launcher))  { throw "launcher not found: $Launcher" }
if (-not (Test-Path $IconPath))  { throw "icon not found: $IconPath" }
if (-not (Test-Path $TargetDir)) { throw "target directory not found: $TargetDir" }

$wscript = Join-Path $env:SystemRoot 'System32\wscript.exe'

# ---------------------------------------------------------- drop stale .url
# The old layout also wrote "$Name.url".  It cannot launch anything, so remove
# it rather than leave an indistinguishable twin next to the real shortcut.
$urlFile = Join-Path $TargetDir "$Name.url"
if (Test-Path $urlFile) {
    Remove-Item $urlFile -Force
    Write-Host "removed stale $urlFile"
}

# ---------------------------------------------------------------- .lnk file
$lnkFile = Join-Path $TargetDir "$Name.lnk"
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnkFile)
$sc.TargetPath       = $wscript
$sc.Arguments        = "`"$Launcher`""
$sc.WorkingDirectory = Split-Path -Parent $Launcher
$sc.Description      = 'DeepSeek Harness Web GUI - starts the server, then opens the browser'
$sc.IconLocation     = "$IconPath,0"
$sc.Save()
Write-Host "wrote $lnkFile"

# ------------------------------------------------------------------- report
$i = Get-Item $lnkFile
Write-Host ("  {0}  ({1} bytes)" -f $i.Name, $i.Length)

# Read it back so a silent write failure cannot slip through.
$check = $ws.CreateShortcut($lnkFile)
Write-Host "target : $($check.TargetPath)"
Write-Host "args   : $($check.Arguments)"
Write-Host "icon   : $($check.IconLocation)"
if ($check.TargetPath -notmatch 'wscript\.exe$') {
    Write-Warning "target is not wscript.exe - the shortcut will not launch the server"
}
