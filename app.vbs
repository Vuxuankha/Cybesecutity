Option Explicit
Dim sh, fso, base
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "wscript.exe //nologo """ & base & "\MO_APP_NETWORKAUTOMATION.vbs""", 0, False
