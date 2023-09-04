RequestExecutionLevel user

Var GOOEYTEMP

Section "Initialize"
    StrCpy $GOOEYTEMP "$TEMP\datalad-gooey-installer-Wlkfd983e"
    RMDir /r "$GOOEYTEMP"
SectionEnd
