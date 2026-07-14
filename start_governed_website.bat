@echo off
title Hermes Agent Service
echo Starting Hermes Agent in the background...

:: Start the Python server in a minimized background window
start /min "" "%~dp0.venv\Scripts\python.exe" -m hermes_cli.web_server --host 127.0.0.1 --port 9119

:: Wait a brief moment for the server to bind to port 9119 using ping
ping -n 3 127.0.0.1 >nul

:: Open the default web browser to the dashboard website URL
start http://127.0.0.1:9119

echo Agent is running on http://127.0.0.1:9119
echo You can close this setup window.
