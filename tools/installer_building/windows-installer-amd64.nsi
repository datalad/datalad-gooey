Name "Datalad Gooey"

Outfile "datalad-gooey-installer-amd64.exe"

Var GOOEYTEMP


Section "Initialize"
    StrCpy $GOOEYTEMP "$TEMP\datalad-gooey-installer-Wlkfd983e"
    RMDir /r "$GOOEYTEMP"
SectionEnd

Section "git"
    SetOutPath "$GOOEYTEMP\"
    File /r "sources\git-64-bit.exe"
    ExecWait "$GOOEYTEMP\git-64-bit.exe"
SectionEnd

Section "git-annex"
    SetOutPath "$GOOEYTEMP"
    File /r "sources\git-annex-64-bit.exe"
    ExecWait "$GOOEYTEMP\git-annex-64-bit.exe"
SectionEnd

Section "Python 3.9"
    StrCpy $INSTDIR "$LOCALAPPDATA\datalad.org\datalad-gooey"
    SetOutPath "$INSTDIR\python39"
    File /r "sources\python39\*.*"
SectionEnd

Section "Datalad-Gooey"
    StrCpy $INSTDIR "$LOCALAPPDATA\datalad.org\datalad-gooey"
    SetOutPath "$GOOEYTEMP"
    # TODO: delete wheelhouse and dist
    File /r "sources\wheelhouse"
    File /r "sources\dist"
    ExecWait "powershell $INSTDIR\python39\python -m pip install --no-index --find-links $GOOEYTEMP\wheelhouse (Get-Item $GOOEYTEMP\dist\datalad_gooey*-py3-none-any.whl)"
    SetOutPath "$INSTDIR"
    File /r "sources\datalad.ico"
    SetOutPath "$INSTDIR\python39\Scripts"
    File /r "sources\run_gooey.ps1"
    CreateShortCut /NoWorkingDir "$DESKTOP\Datalad Gooey.lnk" "$INSTDIR\python39\Scripts\run_gooey.ps1" "" "$INSTDIR\datalad.ico"
SectionEnd
