' 더블클릭하면 콘솔(cmd) 창이 전혀 뜨지 않고 Wafer ID 검색 프로그램만 실행됩니다.
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = scriptDir
shell.Run """" & scriptDir & "\run_wafer_search.bat""", 0, False
