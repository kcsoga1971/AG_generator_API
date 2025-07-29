# /api/index.py (v4 - 處理 Cell Size 和 Line Width 組合)

import itertools
import os
import math
from typing import List

from fastapi import FastAPI, Body, HTTPException
from supabase import create_client, Client

from .models import (
    JitterGridRequest, 
    SunflowerRequest, 
    PoissonRequest, 
    BaseResponse
)
from generators.jitter_grid_generator import generate_jitter_grid_dxf
from generators.sunflower_generator import generate_sunflower_dxf
from generators.poisson_generator import generate_poisson_dxf

# --- 初始化 ---
app = FastAPI(
    title="AG-Generator API",
    description="一個生成 Anti-glare (AG) 圖樣並直接上傳到雲端儲存的 API。",
    version="4.0.0", # 版本升級
)

try:
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("Supabase URL 或 Key 未設定在環境變數中")
    supabase: Client = create_client(url, key)
except Exception as e:
    print(f"錯誤：無法初始化 Supabase Client: {e}")
    supabase = None

BUCKET_NAME = "generatedfiles"

def um_to_mm(um):
    return um / 1000.0

# --- API 端點 ---

@app.get("/", tags=["General"])
def read_root():
    return {"message": "Welcome to the AG-Generator API v4. See /docs for endpoints."}

@app.post("/generate/jitter-grid", tags=["Generators"], response_model=BaseResponse)
async def generate_jitter_grid_endpoint(params: JitterGridRequest = Body(...)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client 未成功初始化")

    generated_urls = []
    
    # 【核心修改】使用 itertools.product 處理 cell_size 和 line_width 的所有組合
    param_combinations = itertools.product(
        params.cell_size_um_options, 
        params.line_width_um_options
    )

    for cell_size_um, line_width_um in param_combinations:
        try:
            # 1. 計算 grid_cols 和 grid_rows
            cell_size_mm = um_to_mm(cell_size_um)
            grid_cols = max(1, round(params.boundary_width_mm / cell_size_mm))
            grid_rows = max(1, round(params.boundary_height_mm / cell_size_mm)) # ✅【修正】新增這一行
            
            # 2. 計算 cell_gap_mm (直接從 line_width 轉換)
            cell_gap_mm = um_to_mm(line_width_um)

            # 檔名現在包含兩個關鍵參數
            file_path = f"{params.job_id}/jitter_cell-{cell_size_um}um_gap-{line_width_um}um.dxf"
            
            iteration_params_dict = params.model_dump()
            iteration_params_dict['grid_cols'] = grid_cols
            iteration_params_dict['grid_rows'] = grid_rows # ✅【修正】將 grid_rows 加入字典
            iteration_params_dict['cell_gap_mm'] = cell_gap_mm
            
            iteration_params = JitterGridRequest(**iteration_params_dict)
            dxf_content = generate_jitter_grid_dxf(iteration_params)
            
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path, file=dxf_content.encode('utf-8'),
                file_options={"content-type": "image/vnd.dxf", "upsert": "true"}
            )
            
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
            generated_urls.append(public_url)

        except Exception as e:
            print(f"Error processing combo (cell: {cell_size_um}, gap: {line_width_um}) for job {params.job_id}: {e}")

    if not generated_urls:
        raise HTTPException(status_code=500, detail="Jitter-Grid: 所有批次任務均生成失敗。")
        
    return BaseResponse(job_id=params.job_id, publicUrls=generated_urls)

# ... Sunflower 和 Poisson 的端點保持不變 ...
@app.post("/generate/sunflower", tags=["Generators"], response_model=BaseResponse)
async def generate_sunflower_endpoint(params: SunflowerRequest = Body(...)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client 未成功初始化")
    generated_urls = []
    for cell_size_um in params.cell_size_um_options:
        try:
            total_area_mm2 = params.boundary_width_mm * params.boundary_height_mm
            cell_area_mm2 = (um_to_mm(cell_size_um)) ** 2
            num_points = max(1, round(total_area_mm2 / cell_area_mm2))
            file_path = f"{params.job_id}/sunflower_cell-{cell_size_um}um.dxf"
            iteration_params_dict = params.model_dump()
            iteration_params_dict['num_points'] = num_points
            iteration_params = SunflowerRequest(**iteration_params_dict)
            dxf_content = generate_sunflower_dxf(iteration_params)
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path, file=dxf_content.encode('utf-8'),
                file_options={"content-type": "image/vnd.dxf", "upsert": "true"}
            )
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
            generated_urls.append(public_url)
        except Exception as e:
            print(f"Error processing cell_size {cell_size_um} for job {params.job_id}: {e}")
    if not generated_urls:
        raise HTTPException(status_code=500, detail="Sunflower: 所有批次任務均生成失敗。")
    return BaseResponse(job_id=params.job_id, publicUrls=generated_urls)

@app.post("/generate/poisson", tags=["Generators"], response_model=BaseResponse)
async def generate_poisson_endpoint(params: PoissonRequest = Body(...)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client 未成功初始化")
    generated_urls = []
    for cell_size_um in params.cell_size_um_options:
        try:
            radius_mm = um_to_mm(cell_size_um) / 2.0
            file_path = f"{params.job_id}/poisson_cell-{cell_size_um}um.dxf"
            iteration_params_dict = params.model_dump()
            iteration_params_dict['radius_mm'] = radius_mm
            iteration_params = PoissonRequest(**iteration_params_dict)
            dxf_content = generate_poisson_dxf(iteration_params)
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path, file=dxf_content.encode('utf-8'),
                file_options={"content-type": "image/vnd.dxf", "upsert": "true"}
            )
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
            generated_urls.append(public_url)
        except Exception as e:
            print(f"Error processing cell_size {cell_size_um} for job {params.job_id}: {e}")
    if not generated_urls:
        raise HTTPException(status_code=500, detail="Poisson: 所有批次任務均生成失敗。")
    return BaseResponse(job_id=params.job_id, publicUrls=generated_urls)

