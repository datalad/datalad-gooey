Name "Datalad Gooey"

Outfile "datalad-gooey-installer-amd64.exe"

Section "git"
    SetOutPath "$TEMP"
    File /r "sources\git-64-bit.exe"
    ExecWait "$TEMP\git-64-bit.exe"
SectionEnd

Section "git-annex"
    SetOutPath "$TEMP"
    File /r "sources\git-annex-64-bit.exe"
    ExecWait "$TEMP\git-annex-64-bit.exe"
SectionEnd

Section "Python 3.9"
    StrCpy $INSTDIR "$LOCALAPPDATA\datalad.org\datalad-gooey"
    SetOutPath "$INSTDIR\python39"
    File /r "sources\python39\*.*"
SectionEnd

Section "Datalad-Gooey"
    StrCpy $INSTDIR "$LOCALAPPDATA\datalad.org\datalad-gooey"
    SetOutPath "$INSTDIR"
    File /r "sources\datalad.ico"
    CreateShortCut /NoWorkingDir "$DESKTOP\Datalad Gooey.lnk" "$INSTDIR\python39\python" "-m datalad_gooey" "$INSTDIR\datalad.ico"
SectionEnd
