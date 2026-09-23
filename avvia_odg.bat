@echo off
title OdG - non chiudere questa finestra finche' la usi
cd /d "%~dp0"
echo Avvio di OdG (versione di prova sul PC)...
echo.
echo Sul PC: http://localhost:5002
echo.
echo Per chiudere l'app, chiudi semplicemente questa finestra.
echo.
venv\Scripts\python.exe app.py
echo.
echo L'app si e' fermata. Se e' un errore, leggi il messaggio sopra.
pause
