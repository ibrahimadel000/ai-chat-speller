Option Explicit

Dim fso, shell, projectDir, desktopDir, shortcut, shortcutPath, launcherPath

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
desktopDir = shell.SpecialFolders("Desktop")
shortcutPath = desktopDir & "\AI Chat Spell Assistant.lnk"
launcherPath = projectDir & "\Start AI Chat Spell Assistant.vbs"

If Not fso.FileExists(launcherPath) Then
    MsgBox "Could not find:" & vbCrLf & launcherPath, vbExclamation, "AI Chat Spell Assistant"
    WScript.Quit 1
End If

Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = "wscript.exe"
shortcut.Arguments = """" & launcherPath & """"
shortcut.WorkingDirectory = projectDir
shortcut.IconLocation = "shell32.dll,46"
shortcut.Description = "Start AI Chat Spell Assistant"
shortcut.Save

MsgBox "Created desktop shortcut:" & vbCrLf & shortcutPath, vbInformation, "AI Chat Spell Assistant"
