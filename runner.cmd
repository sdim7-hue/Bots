@echo off
cd /d C:\work\bots-cc
call claude -p "Read docs/observer-spec.md in full and implement it exactly: create the observer/ package per that spec. Commit locally with feat: messages; do not push." --permission-mode bypassPermissions > C:\work\bots-cc\cc-out.log 2>&1
echo done> C:\work\bots-cc\cc-done.flag