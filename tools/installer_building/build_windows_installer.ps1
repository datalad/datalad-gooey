#! powershell

Param(
    [string]$Revision
)

Set-PSDebug -Trace 0

$start_dir = Get-Location
$build_dir = "${env:TEMP}\build-datalad-gooey-installer"
$sources_dir = "${build_dir}\sources"


# -------------------------------------------------------------
# Clean up old installation building files
if (Test-Path ${build_dir}) {
    Remove-Item -Recurse -Force ${build_dir}
}

New-Item -Path $build_dir -ItemType directory -Force
New-Item -Path ${sources_dir} -ItemType directory -Force

Push-Location $build_dir


# -------------------------------
# Set up the embedded interpreter

# Download embeddable python version 3.9.13
Invoke-WebRequest -UseBasicParsing https://www.python.org/ftp/python/3.9.13/python-3.9.13-embed-amd64.zip -OutFile empy-3.9.13-amd64.zip

# Extract the archive
Expand-Archive empy-3.9.13-amd64.zip ${sources_dir}\python39 -Force

# Adapt the path variable to allow for pip
'import site' | Out-File -FilePath ${sources_dir}\python39\python39._pth -Append -Encoding utf8

# Download get-pip and execute it to install pip in the embedded python environment
Invoke-WebRequest -UseBasicParsing https://bootstrap.pypa.io/get-pip.py -OutFile get-pip.py
Start-Process "${sources_dir}\python39\python.exe" -ArgumentList get-pip.py -Wait


#-----------------------------------------------------------------
# Create a distribution, create a local copy of required wheels

# Get the requested revision of datalad-gooey into the temp directory
git clone "https://github.com/datalad/datalad-gooey.git"
Set-Location datalad-gooey
git fetch origin "$Revision"
git reset --hard FETCH_HEAD

# Upgrade pip
python -m pip install pip --upgrade

# Install the builder and build a distribution
python -m pip install build
python -m pip install wheel
New-Item -Path ${sources_dir}\dist -ItemType directory -Force
python -m build -o ${sources_dir}\dist

# Create `wheelhouse` directory and fetch all dependencies into `wheelhouse`
New-Item -Path ${sources_dir}\wheelhouse -ItemType directory -Force
python -m pip wheel -w ${sources_dir}\wheelhouse .
# Fetch setup tools as well into `wheelhouse`
python -m pip wheel -w ${sources_dir}\wheelhouse setuptools


#--------------------------------------------------------------------------
# install datalad-gooey using the locally stored wheels and get its version
python -m pip install --no-index --find-links ${sources_dir}\wheelhouse (Get-Item ${sources_dir}\dist\datalad_gooey-*.whl)
$fetched_version = python -c "import datalad_gooey._version as v; print(v.get_versions()['version'])"


#------------------------------------------------------------------
# Move data to the location where the installer expects it.
Set-Location ..

# Copy the icon to "sources" where the NSI script expects it
Copy-Item $start_dir\resources\datalad.ico ${sources_dir}
Copy-Item $start_dir\resources\run_gooey.ps1 ${sources_dir}

# Fetch git for windows installer
Invoke-WebRequest -UseBasicParsing 'https://github.com/git-for-windows/git/releases/download/v2.37.3.windows.1/Git-2.37.3-64-bit.exe' -OutFile ${sources_dir}\git-64-bit.exe

# Fetch git annex for windows
Invoke-WebRequest -UseBasicParsing 'https://downloads.kitenet.net/git-annex/windows/current/git-annex-installer.exe' -OutFile ${sources_dir}\git-annex-64-bit.exe

# Copy the installer script to the temp directory so it can be run in this environment
# (there may be other ways to ensure correctness of relative paths)
Copy-Item $start_dir\windows-installer-amd64.nsi .

# Create the installer
makensis windows-installer-amd64.nsi

# Move the installer to a known location
Move-Item datalad-gooey-installer-amd64.exe $start_dir\datalad-gooey-installer-amd64.exe -Force

# Clean up a little
#Remove-Item $build_dir -Recurse -Force

Pop-Location

Write-Output "installed_version: $fetched_version"
