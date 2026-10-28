@echo off
REM בניית agent-web.exe (ממשק Web: FastAPI + React) עם PyInstaller. להריץ ב-Windows מתוך שורש הפרויקט.
REM דורש Node.js לבניית הממשק.
pip install -r requirements.txt
pushd web
call npm install
call npm run build
popd
pyinstaller --onefile --console --name agent-web ^
  --add-data "agent\data;agent\data" ^
  --add-data "web\dist;agent\web_dist" ^
  --collect-submodules langgraph ^
  --collect-submodules langchain_openai ^
  --collect-submodules uvicorn ^
  --copy-metadata langgraph ^
  --copy-metadata langchain-core ^
  run_web.py
echo.
echo agent-web.exe created in dist\  -  place a .env file next to it before running.
