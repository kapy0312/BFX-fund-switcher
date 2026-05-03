@echo off
chcp 65001 >nul
echo 安裝套件...
pip install -r requirements.txt pyinstaller pywebview -q

echo 打包中...
pyinstaller --onefile --noconsole ^
  --add-data "templates;templates" ^
  --hidden-import cryptography ^
  --hidden-import flask ^
  --hidden-import webview ^
  --hidden-import clr_loader ^
  --hidden-import pythonnet ^
  --name BFX_Fund_Switcher ^
  launcher.py

echo.
echo 完成！exe 在 dist\BFX_Fund_Switcher.exe
pause