# /api/models.py (v4 - 獨立的 Cell Size 和 Line Width)

from pydantic import BaseModel, Field, confloat
from typing import List, Optional

# --- 1. 通用基礎模型 ---
class BaseGeneratorRequest(BaseModel):
    job_id: str
    boundary_width_mm: float = Field(..., gt=0, description="邊界寬度 (mm)")
    boundary_height_mm: float = Field(..., gt=0, description="邊界高度 (mm)")
    add_text_label: bool = Field(False, description="是否在圖樣中加入文字標籤")
     # ✅【修正 #1】使用 confloat(gt=0) 來驗證列表中的每一個浮點數
    cell_size_um_options: List[confloat(gt=0)] = Field(..., description="要測試的目標單元尺寸 (um) 選項列表")
#
#  --- 2. 各生成器的請求模型 ---

class JitterGridRequest(BaseGeneratorRequest):
    # 【核心修改】新增獨立的線寬/間隙批次參數
    line_width_um_options: List[confloat(gt=0)] = Field(..., description="要測試的線寬 (um) 選項列表")

    # 【移除】移除不直觀的比例參數
    # gap_to_cell_ratio: float 

    # 單次生成參數 (由 API 內部在迴圈中填寫)
    grid_cols: Optional[int] = Field(None, description="單次運行的網格欄數 (由 cell_size 計算)")
    cell_gap_mm: Optional[float] = Field(None, description="單次運行的單元間隙 (mm) (由 line_width 轉換)")
    
    # 固定參數
    jitter_strength: float = Field(0.5, ge=0, le=1, description="抖動強度 (0 到 1)")
    relaxation_steps: int = Field(1, ge=0, description="鬆弛迭代次數")

class SunflowerRequest(BaseGeneratorRequest):
    num_points: Optional[int] = Field(None, description="單次運行的點數 (由 cell_size 計算)")
    c_const: float = Field(4.0, description="Sunflower 演算法中的常數 c")

class PoissonRequest(BaseGeneratorRequest):
    radius_mm: Optional[float] = Field(None, description="單次運行的 Poisson 盤半徑 (mm) (由 cell_size 計算)")
    candidates: int = Field(30, description="每個新點的候選數量 (k)")

# --- 3. API 回應模型 ---

class BaseResponse(BaseModel):
    job_id: str
    publicUrls: List[str]
