Option Explicit

Dim fso, shell, projectDir, command

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
command = "cmd.exe /c code """ & projectDir & """"

shell.Run command, 0, False
