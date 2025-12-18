@echo off
start cmd /k "python main.py -debug || (echo. & echo Script failed with error code %errorlevel%) & echo. & echo Press any key to exit... & pause >nul"