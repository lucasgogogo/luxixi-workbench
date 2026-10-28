param(
  [ValidateSet('start','status','stop')][string]$Action='start',
  [string]$DataDir,
  [int]$Port
)
$ErrorActionPreference='Stop'
$taskPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $taskPython)){throw '缺少本产品独立Python环境；请从Skill运行scripts/workbench.py setup。'}
$taskArgs=@('-X','utf8','-B','-m','luxixi_workbench',$Action)
if($PSBoundParameters.ContainsKey('Port')){$taskArgs+=@('--port',[string]$Port)}
if($DataDir){$taskArgs+=@('--data-dir',$DataDir)}
Push-Location -LiteralPath $PSScriptRoot
try { & $taskPython @taskArgs; $taskExit=$LASTEXITCODE } finally { Pop-Location }
exit $taskExit
