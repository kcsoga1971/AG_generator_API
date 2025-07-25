# /api/models.py (新檔案)

from pydantic import BaseModel
from typing import Literal

# 將資料模型（請求的結構）放在一個獨立的檔案中
# 這樣可以被 API 端點和生成器函式安全地導入，而不會產生循環
class JitterGridRequest(BaseModel):
    boundary_width_mm: float
    boundary_height_mm: float
    grid_rows: int
    grid_cols: int
    jitter_strength: float
    relaxation_steps: int
    cell_gap_mm: float
    add_text_label: bool = False
    text_content: str = "Test"
    text_height_mm: float = 5.0
    font_name: str = "Arial.ttf"
    output_unit: Literal['mm', 'um'] = 'mm'
