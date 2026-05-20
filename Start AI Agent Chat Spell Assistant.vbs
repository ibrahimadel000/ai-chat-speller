Option Explicit

Dim fso, shell, projectDir, pythonw, scriptPath

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = projectDir & "\.venv\Scripts\pythonw.exe"
scriptPath = projectDir & "\spell_overlay.py"

If Not fso.FileExists(pythonw) Then
    MsgBox "Python environment was not found:" & vbCrLf & pythonw & vbCrLf & vbCrLf & _
           "Open the project once in Codex/terminal and install requirements first.", _
           vbExclamation, "AI Agent Chat Spell Assistant"
    WScript.Quit 1
End If

If Not fso.FileExists(scriptPath) Then
    MsgBox "Could not find spell_overlay.py in:" & vbCrLf & projectDir, vbExclamation, "AI Agent Chat Spell Assistant"
    WScript.Quit 1
End If

shell.CurrentDirectory = projectDir
shell.Run """" & pythonw & """ """ & scriptPath & """", 0, False
