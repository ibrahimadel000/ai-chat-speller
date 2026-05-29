Option Explicit

Dim fso, shell, projectDir, desktopDir, shortcut, shortcutPath, launcherPath

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectDir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
desktopDir = shell.SpecialFolders("Desktop")
shortcutPath = desktopDir & "\AI Agent Chat Spell Assistant.lnk"
launcherPath = projectDir & "\launchers\Start AI Agent Chat Spell Assistant.vbs"

If Not fso.FileExists(launcherPath) Then
    MsgBox "Could not find:" & vbCrLf & launcherPath, vbExclamation, "AI Agent Chat Spell Assistant"
    WScript.Quit 1
End If

Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = "wscript.exe"
shortcut.Arguments = """" & launcherPath & """"
shortcut.WorkingDirectory = projectDir
If fso.FileExists(projectDir & "\dist\AIAgentChatSpellAssistant.exe") Then
    shortcut.IconLocation = projectDir & "\dist\AIAgentChatSpellAssistant.exe,0"
ElseIf fso.FileExists(projectDir & "\assets\app_icon.ico") Then
    shortcut.IconLocation = projectDir & "\assets\app_icon.ico"
End If
shortcut.Description = "Start AI Agent Chat Spell Assistant"
shortcut.Save

MsgBox "Created desktop shortcut:" & vbCrLf & shortcutPath, vbInformation, "AI Agent Chat Spell Assistant"
