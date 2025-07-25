# /api/index.py (最終除錯版本)

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import io
import sys
import os
import traceback

# --- 開始診斷代碼 ---
print("--- [DIAGNOSTIC] STARTING API SERVER (Final Debug Version) ---")
print(f"--- [DIAGNOSTIC] Python Version: {sys.version}")
print(f"--- [DIAGNOSTIC] Current Working Directory: {os.getcwd()}")
print("--- [DIAGNOSTIC] Attempting to import the 'generators.jitter_grid_generator' module...")

IMPORT_ERROR_MESSAGE = ""
IMPORT_SUCCESS = False

try:
    # 關鍵改動：我們不再導入特定函式，而是導入整個模組。
    # 這會強制 Python 執行 jitter_grid_generator.py 並報告其內部的任何錯誤。
    import generators.jitter_grid_generator
    
    print("--- [DIAGNOSTIC] SUCCESS: The module 'generators.jitter_grid_generator' was imported.")
    IMPORT_SUCCESS = True
except Exception as e:
    IMPORT_SUCCESS = False
    error_stack = traceback.format_exc()
    IMPORT_ERROR_MESSAGE = f"Error Type: {type(e).__name__}\nError Details: {e}\nFull Traceback:\n{error_stack}"
    
    print("--- [DIAGNOSTIC] ##################################################")
    print(f"--- [DIAGNOSTIC] CRITICAL ERROR: FAILED to import the module!")
    print(f"--- [DIAGNOSTIC] THIS IS THE ROOT CAUSE:")
    print(f"--- [DIAGNOSTIC] {IMPORT_ERROR_MESSAGE}")
    print("--- [DIAGNOSTIC] ##################################################")
# --- 結束診斷代碼 ---


app = FastAPI()

@app.get("/")
def read_root():
    if IMPORT_SUCCESS:
        status = "OK"
        message = "API is running. The generator module was imported successfully."
    else:
        status = "ERROR"
        message = "API is running, but the generator module failed to load. Check logs for the root cause."
    return {"status": status, "message": message}

@app.get("/debug-import-error")
def get_import_error():
    if IMPORT_SUCCESS:
        return {"message": "No import error was detected."}
    else:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Module Load Failed",
                "details": IMPORT_ERROR_MESSAGE
            }
        )

