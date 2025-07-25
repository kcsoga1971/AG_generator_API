# /api/models.py (完整更新版)

from pydantic import BaseModel, Field

# --- 基礎請求模型 ---
# 包含所有生成器共用的參數
class BasePatternRequest(BaseModel):
    boundary_width_mm: float = Field(..., example=100.0, description="圖樣的總寬度 (mm)")
    boundary_height_mm: float = Field(..., example=100.0, description="圖樣的總高度 (mm)")
    cell_gap_mm: float = Field(0.1, example=0.1, description="每個 Voronoi 單元之間的間隙寬度 (mm)")
    add_text_label: bool = Field(False, example=True, description="是否在圖樣中央加入文字標籤")
    text_content: str = Field("TEXT", example="Honeycomb", description="要加入的文字內容")
    text_height_mm: float = Field(10.0, example=10.0, description="文字的高度 (mm)")
    font_name: str = Field("Arial.ttf", description="（目前未啟用）用於文字的字體檔案名稱")
    output_unit: str = Field("mm", example="mm", description="輸出 DXF 檔案的單位 ('mm' 或 'um')")

# --- 特定生成器的模型 ---

class JitterGridRequest(BasePatternRequest):
    grid_rows: int = Field(..., example=20, description="網格的行數")
    grid_cols: int = Field(..., example=20, description="網格的列數")
    jitter_strength: float = Field(..., example=0.5, description="抖動強度 (0 到 1 之間，0=無抖動, 1=最大抖動)")
    relaxation_steps: int = Field(..., example=2, description="Lloyd's 鬆弛演算法的迭代次數")

class SunflowerRequest(BasePatternRequest):
    num_points: int = Field(..., example=400, description="要生成的點的目標數量")
    sunflower_c: float = Field(..., example=3.6, description="向日葵螺旋的常數 c (影響點的密度)")
    jitter_strength: float = Field(..., example=0.1, description="點生成後的抖動強度 (0 到 1)")
    relaxation_steps: int = Field(..., example=1, description="Lloyd's 鬆弛演算法的迭代次數")

class PoissonRequest(BasePatternRequest):
    radius_mm: float = Field(..., example=5.0, description="泊松盤採樣中點之間的最小距離 (mm)")
    k_samples: int = Field(30, example=30, description="每個點周圍嘗試生成新點的次數 (影響採樣密度)")

