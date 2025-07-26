# /api/index.py (已修改為上傳 Supabase 版本)

# 在 index.py 頂部新增/確認這些 import
import itertools
from typing import List
from .models import JitterGridRequest, SunflowerRequest, PoissonRequest, JitterGridResponse # <--- 匯入 JitterGridResponse

import os
from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import JSONResponse
from supabase import create_client, Client

from .models import JitterGridRequest, SunflowerRequest, PoissonRequest
from generators.jitter_grid_generator import generate_jitter_grid_dxf
from generators.sunflower_generator import generate_sunflower_dxf
from generators.poisson_generator import generate_poisson_dxf

# --- 1. 初始化應用和 Supabase 客戶端 ---
app = FastAPI(
    title="Honeycomb API",
    description="一個生成 Voronoi 圖樣並直接上傳到雲端儲存的 API。",
    version="1.1.0", # 版本升級
)

# 從環境變數讀取 Supabase 憑證
try:
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("Supabase URL 或 Key 未設定在環境變數中")
    supabase: Client = create_client(url, key)
except Exception as e:
    # 如果在啟動時就無法初始化，讓應用程式知道有問題
    print(f"錯誤：無法初始化 Supabase Client: {e}")
    supabase = None

BUCKET_NAME = "generatedfiles" # 您在 Supabase 中的 Bucket 名稱

# --- 2. 重新定義 API 端點 ---

@app.get("/", tags=["General"])
def read_root():
    return {"message": "Welcome to the Honeycomb API. See /docs for endpoints."}

# --- 請用下面的程式碼替換掉你原本的 generate_jitter_grid_endpoint 函式 ---

@app.post("/generate/jitter-grid", tags=["Generators"], response_model=JitterGridResponse) # <--- 1. 更新 response_model
async def generate_jitter_grid_endpoint(params: JitterGridRequest = Body(...)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client 未成功初始化")

    # 2. 初始化一個列表，用來收集所有生成檔案的 URL
    generated_urls = []
    
    # 3. 使用 itertools.product 產生所有參數組合
    param_combinations = itertools.product(params.grid_cols_options, params.cell_gap_mm_options)

    try:
        # 4. 遍歷每一個參數組合
        for grid_col_option, cell_gap_option in param_combinations:
            
            # 5. 為每個組合建立一個獨一無二的檔案路徑 (在 job_id 資料夾下)
            #    這讓檔名具有描述性，例如: "e25dc1a1.../20cols_0.1gap.dxf"
            file_path = f"{params.job_id}/{grid_col_option}cols_{cell_gap_option}gap.dxf"

            # 6. 建立一個用於此次迭代的參數物件副本
            #    這是最關鍵的一步：我們複製原始請求，只更新當前迴圈需要變更的欄位
            iteration_params_dict = params.model_dump()
            iteration_params_dict['grid_cols'] = grid_col_option
            iteration_params_dict['cell_gap_mm'] = cell_gap_option
            
            # 將字典轉回 Pydantic 模型，以符合 generate_jitter_grid_dxf 的預期輸入
            iteration_params = JitterGridRequest(**iteration_params_dict)

            # 7. 呼叫生成器函式，傳入為本次迴圈特製的參數物件
            dxf_content = generate_jitter_grid_dxf(iteration_params)
            
            # 8. 將生成的 DXF 內容上傳到 Supabase Storage
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path,
                file=dxf_content.encode('utf-8'),
                file_options={"content-type": "image/vnd.dxf", "upsert": "true"}
            )
            
            # 9. 取得該檔案的公開 URL
            public_url_data = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
            
            # 10. 將 URL 加入到我們的列表中
            generated_urls.append(public_url_data)

        # 11. 迴圈結束後，回傳包含所有 URL 的成功回應
        return JitterGridResponse(
            job_id=params.job_id, 
            publicUrls=generated_urls
        )
        
    except Exception as e:
        # 如果過程中發生任何錯誤，回報錯誤
        raise HTTPException(status_code=500, detail=f"生成或上傳檔案時發生錯誤: {str(e)}")
# --- 為其他兩個端點套用相同的模式 ---

@app.post("/generate/sunflower", tags=["Generators"], response_model=dict)
async def generate_sunflower_endpoint(params: SunflowerRequest = Body(...)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client 未成功初始化")
        
    dxf_content = generate_sunflower_dxf(params)
    file_path = f"{params.job_id}.dxf"
    
    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=dxf_content.encode('utf-8'),
            file_options={"content-type": "image/vnd.dxf", "upsert": "true"}
        )
        public_url_data = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "job_id": params.job_id,
                "publicUrl": public_url_data
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上傳檔案至 Supabase 時發生錯誤: {str(e)}")


@app.post("/generate/poisson", tags=["Generators"], response_model=dict)
async def generate_poisson_endpoint(params: PoissonRequest = Body(...)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client 未成功初始化")
        
    dxf_content = generate_poisson_dxf(params)
    file_path = f"{params.job_id}.dxf"
    
    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=dxf_content.encode('utf-8'),
            file_options={"content-type": "image/vnd.dxf", "upsert": "true"}
        )
        public_url_data = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "job_id": params.job_id,
                "publicUrl": public_url_data
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上傳檔案至 Supabase 時發生錯誤: {str(e)}")

