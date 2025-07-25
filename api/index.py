# api/index.py

# 強制重新部署的註解 - 2025-07-25 09:48
# (Adding a comment to force a re-deploy)
from fastapi import FastAPI, Response

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from starlette.responses import Response
from typing import Union, Literal, Dict, Any
from datetime import datetime
# --- 加入這行，匯入 traceback 模組 ---
import traceback

# 從我們的 generators 套件中，匯入各個生成器模組
from generators import jitter_grid_generator, sunflower_generator, poisson_generator

app = FastAPI(
    title="Honeycomb Pattern API",
    description="An API to generate various types of honeycomb/Voronoi patterns and return them as DXF files.",
    version="1.1.0",
)

# --- 為每個生成器定義專屬的參數模型 ---
# 這樣可以利用 Pydantic 的所有驗證功能

class JitterGridParams(BaseModel):
    boundary_width_mm: float = Field(100.0, gt=0, description="Boundary width in mm.")
    boundary_height_mm: float = Field(100.0, gt=0, description="Boundary height in mm.")
    grid_rows: int = Field(30, gt=0, description="Number of grid rows.")
    grid_cols: int = Field(30, gt=0, description="Number of grid columns.")
    jitter_strength: float = Field(0.45, ge=0, le=1, description="Jitter strength (0 to 1).")
    relaxation_steps: int = Field(2, ge=0, description="Number of Lloyd's relaxation steps.")
    cell_gap_mm: float = Field(0.1, ge=0, description="Gap between cells in mm.")
    add_text_label: bool = Field(False, description="Whether to add a text label.")
    text_content: str = Field("", description="The text content to add.")
    text_height_mm: float = Field(10.0, gt=0, description="Height of the text in mm.")
    font_name: str = Field("Arial.ttf", description="Font file name for the text (must be accessible).")
    output_unit: str = Field("mm", description="Output unit for internal calculations ('mm' or 'um').")

class SunflowerParams(BaseModel):
    boundary_width_mm: float = Field(100.0, gt=0, description="Boundary width in mm.")
    boundary_height_mm: float = Field(100.0, gt=0, description="Boundary height in mm.")
    num_points: int = Field(500, gt=0, description="Approximate number of points (cells).")
    sunflower_c: float = Field(3.6, gt=0, description="Scaling constant for the sunflower spiral.")
    jitter_strength: float = Field(0.1, ge=0, description="Jitter strength applied to points.")
    relaxation_steps: int = Field(0, ge=0, description="Number of Lloyd's relaxation steps.")
    cell_gap_mm: float = Field(0.1, ge=0, description="Gap between cells in mm.")
    add_text_label: bool = Field(False, description="Whether to add a text label.")
    text_content: str = Field("", description="The text content to add.")
    text_height_mm: float = Field(10.0, gt=0, description="Height of the text in mm.")
    font_name: str = Field("Arial.ttf", description="Font file name for the text.")
    output_unit: str = Field("mm", description="Output unit for internal calculations ('mm' or 'um').")


class PoissonParams(BaseModel):
    boundary_width_mm: float = Field(100.0, gt=0, description="Boundary width in mm.")
    boundary_height_mm: float = Field(100.0, gt=0, description="Boundary height in mm.")
    radius_mm: float = Field(5.0, gt=0, description="Minimum distance between points in mm.")
    k_samples: int = Field(30, gt=0, description="Number of samples to try before rejecting a point.")
    cell_gap_mm: float = Field(0.1, ge=0, description="Gap between cells in mm.")
    add_text_label: bool = Field(False, description="Whether to add a text label.")
    text_content: str = Field("", description="The text content to add.")
    text_height_mm: float = Field(10.0, gt=0, description="Height of the text in mm.")
    font_name: str = Field("Arial.ttf", description="Font file name for the text.")
    output_unit: str = Field("mm", description="Output unit for internal calculations ('mm' or 'um').")


# --- 使用 Union 來組合所有可能的參數模型 ---
# FastAPI 會根據 'generator_type' 的值來決定使用哪個模型
# 注意：這需要 request body 的結構是 { "generator_type": "...", "params": { ... } }
# 為了簡化，我們將 'generator_type' 移到 Body 中
class PatternRequest(BaseModel):
    generator_type: Literal['jitter_grid', 'sunflower', 'poisson']
    params: Union[JitterGridParams, SunflowerParams, PoissonParams]


# --- 使用字典來分派生成器，取代 if/elif/else ---
GENERATOR_MAP = {
    "jitter_grid": jitter_grid_generator.generate,
    "sunflower": sunflower_generator.generate,
    "poisson": poisson_generator.generate,
}

@app.get("/", tags=["Status"])
def home():
    """檢查 API 是否正在運行。"""
    return {"status": "ok", "message": "Honeycomb Pattern API is running."}

@app.post("/generate", tags=["Generation"])
def generate_pattern(request: PatternRequest):
    """
    根據指定的類型和參數生成蜂窩圖案。
    將 DXF 檔案內容作為串流回傳。
    """
    try:
        # 根據 generator_type 從字典中獲取對應的生成函式
        generator_func = GENERATOR_MAP.get(request.generator_type)
        
        if not generator_func:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid generator_type '{request.generator_type}'. Available types are: {list(GENERATOR_MAP.keys())}."
            )
            
        # 將 Pydantic 模型轉換為字典並傳遞給生成函式
        # .model_dump() 是 Pydantic v2 的方法，如果是 v1 則用 .dict()
        params_dict = request.params.model_dump()
        dxf_content = generator_func(**params_dict)
        
        # 準備檔名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{request.generator_type}_pattern_{timestamp}.dxf"
        
        # 將生成的 DXF 字串作為檔案回傳
        return Response(
            content=dxf_content,
            media_type="application/vnd.dxf",  # 更標準的 MIME type
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        # --- 這是關鍵的修改 ---
        # 在日誌中印出完整的錯誤堆疊追蹤
        print("--- An exception occurred, printing full traceback: ---")
        traceback.print_exc()
        print("----------------------------------------------------")
        
        # 保持原有的錯誤回傳給使用者
        raise HTTPException(status_code=500, detail=f"An error occurred during pattern generation: {str(e)}")

