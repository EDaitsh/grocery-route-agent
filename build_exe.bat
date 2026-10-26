@echo off
REM בניית agent.exe עם PyInstaller (להריץ ב-Windows מתוך שורש הפרויקט)
pip install -r requirements.txt
pyinstaller --onefile --console --name agent ^
  --add-data "agent\data;agent\data" ^
  --collect-submodules langgraph ^
  --collect-submodules langchain_openai ^
  --copy-metadata langgraph ^
  --copy-metadata langchain-core ^
  run_agent.py
echo.
echo agent.exe created in dist\  -  place a .env file next to it before running.
