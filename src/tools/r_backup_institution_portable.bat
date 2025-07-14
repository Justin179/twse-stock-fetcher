@echo off
cd /d %~dp0

REM Activate virtual environment
call ..\venv\Scripts\activate.bat

REM Run backup script (portable)
python backup_institution_db_stable.py