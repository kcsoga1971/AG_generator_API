# /api/index.py (用於除錯的臨時版本)
# 這個檔案的唯一目的，是測試 'jitter_grid_generator' 能否在 Render 環境中被成功導入。

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import io
import sys
import os
import traceback # 導入 traceback 以獲取更詳細的錯誤堆疊

# --- 開始診斷代碼 ---
print("--- [DIAGNOSTIC] STARTING API SERVER (Minimal Debug Version) ---")
print(f"--- [DIAGNOSTIC] Python Version: {sys.version}")
print(f"--- [DIAGNOSTIC] Current Working Directory: {os.getcwd()}")
print("--- [DIAGNOSTIC] Attempting to import from generators.jitter_grid_generator...")

IMPORT_ERROR_MESSAGE = ""
IMPORT_SUCCESS = False

try:
    # 我們只測試這一個導入，這是目前問題的核心
    from generators.jitter_grid_generator import generate_jitter_grid_dxf, JitterGridRequest
    print("--- [DIAGNOSTIC] SUCCESS: Imported from generators.jitter_grid_generator.")
    IMPORT_SUCCESS = True
except Exception as e:
    # 如果導入失敗，捕獲詳細的錯誤訊息和堆疊追蹤
    IMPORT_SUCCESS = False
    error_stack = traceback.format_exc() # 獲取完整的錯誤堆疊
    IMPORT_ERROR_MESSAGE = f"Error Type: {type(e).__name__}\nError Details: {e}\nFull Traceback:\n{error_stack}"
    
    print("--- [DIAGNOSTIC] ##################################################")
    print(f"--- [DIAGNOSTIC] CRITICAL ERROR: FAILED to import from generators!")
    print(f"--- [DIAGNOSTIC] {IMPORT_ERROR_MESSAGE}")
    print("--- [DIAGNOSTIC] ##################################################")
# --- 結束診斷代碼 ---


app = FastAPI()

# 根路由，用於檢查服務是否啟動
@app.get("/")
def read_root():
    if IMPORT_SUCCESS:
        status = "OK"
        message = "API is running and generator was imported successfully."
    else:
        status = "ERROR"
        message = "API is running, but failed to import the generator module. Check logs."
    return {"status": status, "message": message}

# 一個特殊的路由，用於直接在網頁上看到導入錯誤訊息
@app.get("/debug-import-error")
def get_import_error():
    if IMPORT_SUCCESS:
        return {"message": "No import error was detected."}
    else:
        # 返回捕獲到的詳細錯誤訊息
        return JSONResponse(
            status_code=500,
            content={
                "error": "Module Import Failed",
                "details": IMPORT_ERROR_MESSAGE
            }
        )

# 我們暫時移除所有其他的路由，如 /generate/jitter-grid，以避免混淆
