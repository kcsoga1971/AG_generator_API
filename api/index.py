# /api/index.py (已修改為上傳 Supabase 版本)

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

@app.post("/generate/jitter-grid", tags=["Generators"], response_model=dict)
async def generate_jitter_grid_endpoint(params: JitterGridRequest = Body(...)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client 未成功初始化")

    # 步驟 1: 生成 DXF 檔案內容 (這部分不變)
    dxf_content = generate_jitter_grid_dxf(params)
    
    # 步驟 2: 使用 job_id 作為檔案路徑/名稱
    file_path = f"{params.job_id}.dxf"
    
    try:
        # 步驟 3: 將檔案內容上傳到 Supabase Storage
        # 我們需要將字串編碼為 bytes
        supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=dxf_content.encode('utf-8'),
            file_options={"content-type": "image/vnd.dxf", "upsert": "true"}
        )
        
        # 步驟 4: 取得該檔案的公開 URL
        public_url_data = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
        
        # 步驟 5: 回傳包含 URL 的 JSON 給 n8n
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "job_id": params.job_id,
                "publicUrl": public_url_data
            }
        )
    except Exception as e:
        # 如果上傳過程出錯，回傳詳細的錯誤訊息
        raise HTTPException(status_code=500, detail=f"上傳檔案至 Supabase 時發生錯誤: {str(e)}")


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

