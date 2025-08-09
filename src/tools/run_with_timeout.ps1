param(
  [int]$TimeoutSec = 50,
  [Parameter(Mandatory=$true)]
  [string]$CmdLine
)

# 啟動子行程（包在 cmd.exe /c 方便執行整串命令）
$p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $CmdLine" -PassThru

# 逾時就殺掉整個樹
if (-not $p.WaitForExit($TimeoutSec * 1000)) {
  try { taskkill /PID $p.Id /T /F | Out-Null } catch {}
  Write-Output "⏱ Timeout after $TimeoutSec s"
  exit 124
}

exit $p.ExitCode
