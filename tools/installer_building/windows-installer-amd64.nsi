Name "Datalad Gooey"

Outfile "datalad-gooey-installer-amd64.exe"

RequestExecutionLevel admin

!include installer-init.nsi

Section "git"
    SetOutPath "$GOOEYTEMP\"
    File /r "sources\git-64-bit.exe"
    ExecWait "$GOOEYTEMP\git-64-bit.exe"
SectionEnd

Section "git-annex"
    SetOutPath "$GOOEYTEMP\"
    File /r "sources\git-annex-64-bit.exe"
    ExecWait "$GOOEYTEMP\git-annex-64-bit.exe"
SectionEnd

!include installer-gooey.nsi
