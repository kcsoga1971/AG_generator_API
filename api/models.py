# /api/models.py (改造後)

from pydantic import BaseModel, Field
from typing import List # <--- 1. 匯入 List

# --- 基礎請求模型 ---
class BasePatternRequest(BaseModel):
    job_id: str = Field(..., example="e25dc1a1-bb59-4d5b-b24c-f580ce916b80", description="由 n8n 工作流傳入的唯一任務 ID")
    boundary_width_mm: float = Field(..., example=100.0, description="圖樣的總寬度 (mm)")
    boundary_height_mm: float = Field(..., example=100.0, description="圖樣的總高度 (mm)")
    add_text_label: bool = Field(False, example=True, description="是否在圖樣中央加入文字標籤")
    text_content: str = Field("TEXT", example="Honeycomb", description="要加入的文字內容")
    text_height_mm: float = Field(10.0, example=10.0, description="文字的高度 (mm)")
    font_name: str = Field("Arial.ttf", description="（目前未啟用）用於文字的字體檔案名稱")
    output_unit: str = Field("mm", example="mm", description="輸出 DXF 檔案的單位 ('mm' 或 'um')")

# --- 特定生成器的模型 ---

class JitterGridRequest(BasePatternRequest):
    # 2. 修改參數為陣列形式
    grid_rows: int = Field(..., example=20, description="網格的行數")
    jitter_strength: float = Field(..., example=0.5, description="抖動強度 (0 到 1)")
    relaxation_steps: int = Field(..., example=2, description="Lloyd's 鬆弛演算法的迭代次數")
    
    # 將 grid_cols 和 cell_gap_mm 改為選項列表
    grid_cols_options: List[int] = Field(..., example=[20, 30], description="要遍歷的網格列數選項列表")
    cell_gap_mm_options: List[float] = Field(..., example=[0.1, 0.2], description="要遍歷的單元間隙選項列表 (mm)")

# --- 其他請求模型保持不變 ---
class SunflowerRequest(BasePatternRequest):
    num_points: int = Field(..., example=400, description="要生成的點的目標數量")
    sunflower_c: float = Field(..., example=3.6, description="向日葵螺旋的常數 c")
    jitter_strength: float = Field(..., example=0.1, description="點生成後的抖動強度 (0 到 1)")
    relaxation_steps: int = Field(..., example=1, description="Lloyd's 鬆弛演算法的迭代次數")
    cell_gap_mm: float = Field(0.1, example=0.1, description="每個 Voronoi 單元之間的間隙寬度 (mm)")


class PoissonRequest(BasePatternRequest):
    radius_mm: float = Field(..., example=5.0, description="泊松盤採樣中點之間的最小距離 (mm)")
    k_samples: int = Field(30, example=30, description="每個點周圍嘗試生成新點的次數")
    cell_gap_mm: float = Field(0.1, example=0.1, description="每個 Voronoi 單元之間的間隙寬度 (mm)")


# 3. 新增 API 回應模型
class JitterGridResponse(BaseModel):
    status: str = "success"
    job_id: str
    publicUrls: List[str]

