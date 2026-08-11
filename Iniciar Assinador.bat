@echo off
title Tribunal 2.0
cd /d "%~dp0"
start http://localhost:8501
C:\Python314\python.exe -m streamlit run app.py --server.headless true
pause
