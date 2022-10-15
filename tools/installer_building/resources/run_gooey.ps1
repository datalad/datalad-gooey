#! powershell

$ScriptPath = split-path -parent $MyInvocation.MyCommand.Definition
$env:PATH = "$env:PATH;$ScriptPath"

$env:PYSIDE_DESIGNER_PLUGINS = "."
$env:DISPLAY = "0:0"

Start-Process "$ScriptPath\..\python.exe" -ArgumentList "-m datalad_gooey" -NoNewWindow -Wait
