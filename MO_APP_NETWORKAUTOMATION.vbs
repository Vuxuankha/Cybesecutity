Option Explicit
Dim sh, fso, base, core, cmd, rc, answer, installCmd, installRc, msg, logPath
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
core = base & "\_internal\launcher\START_DESKTOP_CORE.bat"
logPath = base & "\runtime_data\logs\desktop_bootstrap.log"

If Not fso.FileExists(core) Then
  MsgBox "Thieu tep khoi dong noi bo:" & vbCrLf & core & vbCrLf & vbCrLf & _
         "Hay giai nen lai toan bo goi ZIP vao mot thu muc moi.", _
         vbCritical, "NetworkAutomation Desktop 7.0.3"
  WScript.Quit 17
End If

cmd = "cmd.exe /d /c """ & core & """"
rc = sh.Run(cmd, 0, True)

If rc = 11 Then
  answer = MsgBox( _
    "May tinh chua co Python tuong thich (3.11, 3.12 hoac 3.13)." & vbCrLf & vbCrLf & _
    "Ban co muon tu dong cai Python 3.12 bang Windows Package Manager (winget) khong?" & vbCrLf & _
    "Neu chon Yes, ung dung se cai Python cho tai khoan Windows hien tai va thu khoi dong lai.", _
    vbYesNo + vbQuestion, "NetworkAutomation Desktop 7.0.3")

  If answer = vbYes Then
    installCmd = "cmd.exe /d /c winget install --id Python.Python.3.12 -e --scope user --silent --accept-package-agreements --accept-source-agreements --disable-interactivity"
    installRc = sh.Run(installCmd, 0, True)
    If installRc = 0 Then
      rc = sh.Run(cmd, 0, True)
      If rc = 0 Then WScript.Quit 0
      MsgBox "Python da duoc cai, nhung NetworkAutomation van chua khoi dong duoc." & vbCrLf & _
             "Ma loi moi: " & rc & vbCrLf & _
             "Xem log: " & logPath, _
             vbCritical, "NetworkAutomation Desktop 7.0.3"
      WScript.Quit rc
    Else
      MsgBox "Khong the tu dong cai Python (winget ma loi " & installRc & ")." & vbCrLf & _
             "Hay cai Python 3.12 x64, sau do mo lai MO_APP_NETWORKAUTOMATION.vbs.", _
             vbCritical, "NetworkAutomation Desktop 7.0.3"
      WScript.Quit 11
    End If
  Else
    MsgBox "Hay cai Python 3.11, 3.12 hoac 3.13 (khuyen nghi 3.12 x64)," & vbCrLf & _
           "sau do mo lai MO_APP_NETWORKAUTOMATION.vbs.", _
           vbInformation, "NetworkAutomation Desktop 7.0.3"
    WScript.Quit 11
  End If
End If

If rc <> 0 Then
  Select Case rc
    Case 1
      msg = "Ung dung da khoi dong backend nhung giao dien Desktop gap loi. Xem log de biet chi tiet."
    Case 3
      msg = "May tinh thieu Microsoft Edge WebView2 Runtime. Hay cai WebView2 Runtime roi mo lai ung dung."
    Case 12
      msg = "Khong tao duoc moi truong Python moi."
    Case 13
      msg = "Khong cap nhat duoc pip trong moi truong Python."
    Case 14
      msg = "Khong cai duoc thu vien phu thuoc. Kiem tra Internet/Proxy/Antivirus."
    Case 15
      msg = "Khong tao duoc thu muc moi truong trong LOCALAPPDATA/TEMP. Kiem tra quyen ghi cua tai khoan Windows."
    Case 16
      msg = "Khong truy cap duoc thu muc ung dung. Hay giai nen ZIP vao thu muc thuong nhu Documents hoac C:\NetworkAutomation."
    Case 17
      msg = "Goi ung dung bi thieu tep khoi dong noi bo. Hay giai nen lai ZIP."
    Case Else
      msg = "Khong the khoi dong NetworkAutomation Desktop."
  End Select
  MsgBox msg & vbCrLf & "Ma loi: " & rc & vbCrLf & _
         "Xem log: " & logPath, _
         vbCritical, "NetworkAutomation Desktop 7.0.3"
End If
