@echo off
rem Reruns the 15 official events on a fresh server and compares with the submitted log.
cd /d %~dp0
set PY=..\.venv\Scripts\python
start "Enterprise server" %PY% _package\hack_the_highway_package\enterprise_server.py --data _package\hack_the_highway_package\data --out runs\official --overwrite
ping -n 6 127.0.0.1 >nul
%PY% run.py --execute http://127.0.0.1:8000 --out out\official\run
echo.
echo Same as submission\action_log.jsonl:
%PY% -c "print(open('runs/official/action_log.jsonl').read()==open('submission/action_log.jsonl').read())"
pause
