Option Explicit

Dim fso, shell, projectDir

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.Run "explorer.exe """ & projectDir & """", 1, False
