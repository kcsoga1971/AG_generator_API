# /api/index.py (最終版本)

from fastapi import FastAPI
from fastapi.responses import Response
import io

# 從我們的模型檔案導入請求模型
from api.models import JitterGridRequest
# 從生成器檔案導入生成函式
from generators.jitter_grid_generator import generate_jitter_grid_dxf

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "OK", "message": "Honeycomb API is running."}

@app.post("/generate/jitter-grid")
def generate_jitter_grid_endpoint(params: JitterGridRequest):
    """
    接收參數並生成一個抖動網格的 DXF 檔案。
    """
    try:
        # 呼叫您的生成器函式
        dxf_output_string = generate_jitter_grid_dxf(params)
        
        # 將 DXF 字串轉換為 bytes
        dxf_bytes = io.BytesIO(dxf_output_string.encode('utf-8'))
        
        # 回傳 DXF 檔案
        return Response(
            content=dxf_bytes.getvalue(),
            media_type="application/vnd.dxf",
            headers={"Content-Disposition": "attachment; filename=jitter_grid.dxf"}
        )
    except Exception as e:
        # 在生產環境中提供更詳細的錯誤日誌會很有幫助
        print(f"Error during DXF generation: {e}")
        return Response(
            content=f"An error occurred: {e}",
            status_code=500
        )


