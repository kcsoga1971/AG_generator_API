# api/index.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import Response
from typing import Dict, Any

# 從我們的 generators 套件中，匯入各個生成器模組
from generators import jitter_grid_generator, sunflower_generator, poisson_generator

app = FastAPI(
    title="Honeycomb Pattern API",
    description="An API to generate various types of honeycomb/Voronoi patterns and return them as DXF files.",
    version="1.0.0",
)

# 定義請求的資料結構
# 使用一個靈活的字典來接收不同生成器的參數
class PatternRequest(BaseModel):
    generator_type: str = Field(..., example="jitter_grid", description="Type of generator to use. Options: 'jitter_grid', 'sunflower', 'poisson'")
    params: Dict[str, Any] = Field(..., example={"boundary_width_mm": 100, "grid_rows": 20, "cell_gap_mm": 0.2})

@app.get("/", tags=["Status"])
def home():
    """Check if the API is running."""
    return {"status": "ok", "message": "Honeycomb Pattern API is running."}

@app.post("/generate", tags=["Generation"])
def generate_pattern(request: PatternRequest):
    """
    Generate a honeycomb pattern based on the specified type and parameters.
    Returns the DXF file content as a string.
    """
    try:
        dxf_content = None
        
        # 根據 generator_type 選擇要執行的函式
        if request.generator_type == "jitter_grid":
            dxf_content = jitter_grid_generator.generate(**request.params)
        elif request.generator_type == "sunflower":
            dxf_content = sunflower_generator.generate(**request.params)
        elif request.generator_type == "poisson":
            dxf_content = poisson_generator.generate(**request.params)
        else:
            # 如果傳入一個未知的類型，回傳 400 錯誤
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid generator_type '{request.generator_type}'. Available types are: 'jitter_grid', 'sunflower', 'poisson'."
            )
        
        # 準備檔名
        filename = f"{request.generator_type}_pattern_{int(request.params.get('boundary_width_mm', 100))}.dxf"
        
        # 將生成的 DXF 字串作為檔案回傳
        # media_type 'application/dxf' 讓瀏覽器或客戶端知道這是一個 DXF 檔案
        return Response(
            content=dxf_content,
            media_type="application/dxf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        # 捕捉生成過程中可能發生的任何錯誤
        raise HTTPException(status_code=500, detail=f"An error occurred during pattern generation: {str(e)}")

