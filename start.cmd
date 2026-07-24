@echo off
title PC-DECK 7710
cd /d "%~dp0"
start "" "http://127.0.0.1:7710"
C:\Python310\python.exe legacy\server.py
