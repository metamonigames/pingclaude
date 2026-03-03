$current_path = Get-Location
wt -w 0 nt -d "$current_path" pwsh -NoExit -Command "claude --dangerously-skip-permissions"