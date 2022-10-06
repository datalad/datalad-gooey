#! powershell

Param(
    [string]$Revision
)

$start_dir = Get-Location

Push-Location $env:TEMP

# Download embeddable python version 3.9.13
Invoke-WebRequest -UseBasicParsing https://www.python.org/ftp/python/3.9.13/python-3.9.13-embed-amd64.zip -OutFile empy-3.9.13-amd64.zip
New-Item -Path sources -ItemType directory -Force

# Extract the archive
Expand-Archive empy-3.9.13-amd64.zip sources\python39 -Force

# Adapt the path variable to allow for pip
'import site' | Out-File -FilePath sources\python39\python39._pth -Append -Encoding utf8

# Download pip and execute it
Invoke-WebRequest -UseBasicParsing https://bootstrap.pypa.io/get-pip.py -OutFile get-pip.py
.\sources\python39\python.exe get-pip.py

# Use pip to install the latest version of datalad-gooey
.\sources\python39\python.exe -m pip install "git+https://github.com/datalad/datalad-gooey.git@$Revision"
$installed_version = .\sources\python39\python.exe -c "import datalad_gooey._version as v; print(v.get_versions()['version'])"

# Copy the icon, git installer, and git-annex installer to "sources" where the script
# expects them
Copy-Item $start_dir\resources\datalad.ico .\sources
Copy-Item $start_dir\resources\dl.py .\sources\python39\dl.py

# Fetch git for windows installer
Invoke-WebRequest -UseBasicParsing 'https://github.com/git-for-windows/git/releases/download/v2.37.3.windows.1/Git-2.37.3-64-bit.exe' -OutFile .\sources\git-64-bit.exe

# Fetch git annex for windows
Invoke-WebRequest -UseBasicParsing 'https://downloads.kitenet.net/git-annex/windows/current/git-annex-installer.exe' -OutFile .\sources\git-annex-64-bit.exe

# Copy the installer script to the temp directory so it can be run in this environment
# (there may be other ways to ensure correctness of relative paths)
Copy-Item $start_dir\windows-installer-amd64.nsi .

# Create the installer
makensis windows-installer-amd64.nsi

# Move the installer to a known location
Move-Item datalad-gooey-installer-amd64.exe $start_dir\datalad-gooey-installer-amd64.exe -Force

# Clean up a little
Remove-Item sources -Recurse -Force

Pop-Location

Write-Output "installed_version: $installed_version"
