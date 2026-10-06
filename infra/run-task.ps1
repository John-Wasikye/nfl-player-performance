<#
.SYNOPSIS
Runs the pipeline task on Fargate once, waits for it, and prints how it ended.

.DESCRIPTION
The same image and settings as the daily schedule, with the command swapped. Needs an AWS login first:
  aws sso login --profile nfl_player_stats

.EXAMPLE
.\run-task.ps1 daily               # what the schedule runs
.\run-task.ps1 run                 # ingest, build, publish, without the projection step
.\run-task.ps1 backtest            # score the rankings against the following week
.\run-task.ps1 predict             # project the coming week, no lock
.\run-task.ps1 predict --lock      # lock the week. Only before its first kickoff.
#>
param(
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
    [string[]]$Command
)

$ErrorActionPreference = "Stop"
if (-not $env:AWS_PROFILE) { $env:AWS_PROFILE = "nfl_player_stats" }
$cluster = "nfl-player-performance"
$logGroup = "/ecs/nfl-pipeline"

function Invoke-Aws {
    $output = & aws @args
    if ($LASTEXITCODE -ne 0) { throw "aws $($args -join ' ') failed" }
    $output
}

$vpc = Invoke-Aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text
$subnets = (Invoke-Aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" --query "Subnets[].SubnetId" --output text) -split "\s+" | Select-Object -First 2
$group = Invoke-Aws ec2 describe-security-groups --filters "Name=group-name,Values=nfl-pipeline-task" --query "SecurityGroups[0].GroupId" --output text

# JSON goes through files because PowerShell 5.1 mangles quotes passed to native programs.
$overrides = @{ containerOverrides = @(@{ name = "pipeline"; command = @($Command) }) } | ConvertTo-Json -Depth 5 -Compress
$network = @{ awsvpcConfiguration = @{ subnets = @($subnets); securityGroups = @($group); assignPublicIp = "ENABLED" } } | ConvertTo-Json -Depth 5 -Compress
$overridesFile = New-TemporaryFile
$networkFile = New-TemporaryFile
[System.IO.File]::WriteAllText($overridesFile, $overrides)
[System.IO.File]::WriteAllText($networkFile, $network)

try {
    $taskArn = Invoke-Aws ecs run-task --cluster $cluster --task-definition nfl-pipeline --launch-type FARGATE `
        --overrides "file://$overridesFile" --network-configuration "file://$networkFile" `
        --query "tasks[0].taskArn" --output text
} finally {
    Remove-Item $overridesFile, $networkFile -ErrorAction SilentlyContinue
}
$taskId = $taskArn.Split("/")[-1]
Write-Host "Started task $taskId running: nfl-pipeline $($Command -join ' ')"

& aws ecs wait tasks-stopped --cluster $cluster --tasks $taskId
$exit = Invoke-Aws ecs describe-tasks --cluster $cluster --tasks $taskId --query "tasks[0].containers[0].exitCode" --output text
$reason = Invoke-Aws ecs describe-tasks --cluster $cluster --tasks $taskId --query "tasks[0].stoppedReason" --output text

Write-Host ""
Write-Host "Exit code: $exit ($reason)"
Write-Host "Last log lines (full log: log group $logGroup, stream pipeline/pipeline/$taskId):"
$events = Invoke-Aws logs get-log-events --log-group-name $logGroup --log-stream-name "pipeline/pipeline/$taskId" `
    --query "events[].message" --output text
($events -split "`t" | Select-Object -Last 8) | ForEach-Object { Write-Host "  $_" }
if ($exit -ne "0") { exit 1 }
