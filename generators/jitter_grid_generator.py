# /generators/jitter_grid_generator.py (最終修復版)

import io
import numpy as np
from scipy.spatial import Voronoi
import gdstk
import ezdxf

# 新增這一行：從我們的新模型檔案中導入請求模型
from api.models import JitterGridRequest

# 注意：我們將不再需要 ezdxf 的 text2path, BoundingBox 等，因為所有幾何運算都在 gdstk 中完成。

class VoronoiPatternGenerator:
    """
    一個整合且高效能的 Voronoi 圖樣產生器。
    所有幾何運算（包括文字）都在 gdstk 中完成，最後匯出為 DXF。
    """
    def __init__(
        self,
        boundary_width_mm: float, boundary_height_mm: float,
        grid_rows: int, grid_cols: int, jitter_strength: float,
        relaxation_steps: int, cell_gap_mm: float,
        add_text_label: bool, text_content: str, text_height_mm: float,
        font_name: str, output_unit: str, **kwargs # 接收多餘的參數以保持彈性
    ):
        self.boundary_width_mm = boundary_width_mm
        self.boundary_height_mm = boundary_height_mm
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.jitter_strength = jitter_strength
        self.relaxation_steps = relaxation_steps
        self.cell_gap_mm = cell_gap_mm
        self.add_text_label = add_text_label
        self.text_content = text_content
        self.text_height_mm = text_height_mm
        self.font_name = font_name
        self.output_unit = output_unit
        
        # gdstk 預設單位是微米(um)。如果我們以 mm 工作，需要轉換。
        self.unit = 1000 if self.output_unit == 'um' else 1
        
        # 計算單元格尺寸以供後續使用
        self.cell_avg_width = self.boundary_width_mm / self.grid_cols

    def _generate_initial_points(self) -> np.ndarray:
        """產生帶有抖動的初始網格點。"""
        x = np.linspace(0, self.boundary_width_mm, self.grid_cols)
        y = np.linspace(0, self.boundary_height_mm, self.grid_rows)
        xv, yv = np.meshgrid(x, y)
        points = np.vstack([xv.ravel(), yv.ravel()]).T
        
        # 抖動強度基於平均單元格寬度
        max_jitter = self.cell_avg_width * self.jitter_strength
        points += (np.random.rand(points.shape[0], 2) - 0.5) * max_jitter
        return points

    def _relax_points(self, points: np.ndarray) -> np.ndarray:
        """使用 Lloyd's 演算法對點進行鬆弛，使其分佈更均勻。"""
        for _ in range(self.relaxation_steps):
            box = [0, 0, self.boundary_width_mm, self.boundary_height_mm]
            vor = Voronoi(points, qhull_options="Qbb Qc Qz") # 選項有助於穩定性
            
            new_points = []
            for idx, region_idx in enumerate(vor.point_region):
                if region_idx == -1:
                    new_points.append(points[idx])
                    continue
                
                region = vor.regions[region_idx]
                if not region or -1 in region:
                    new_points.append(points[idx])
                    continue

                polygon = np.array([vor.vertices[i] for i in region])
                centroid = np.mean(polygon, axis=0)
                
                centroid[0] = np.clip(centroid[0], box[0], box[2])
                centroid[1] = np.clip(centroid[1], box[1], box[3])
                new_points.append(centroid)

            points = np.array(new_points)
        return points

    def run_generation_process(self) -> str:
        """
        執行完整的生成流程，並回傳 DXF 格式的字串。
        """
        initial_points = self._generate_initial_points()
        if self.relaxation_steps > 0:
            final_points = self._relax_points(initial_points)
        else:
            final_points = initial_points
            
        vor = Voronoi(final_points)
        voronoi_polygons_gds = []
        for region in vor.regions:
            if not region or -1 in region:
                continue
            polygon_points = np.array([vor.vertices[i] for i in region]) * self.unit
            voronoi_polygons_gds.append(gdstk.Polygon(polygon_points))

        boundary_gds = gdstk.rectangle(
            (0, 0),
            (self.boundary_width_mm * self.unit, self.boundary_height_mm * self.unit)
        )
        clipped_polygons = gdstk.boolean(voronoi_polygons_gds, boundary_gds, 'and')

        final_voronoi_polygons = []
        if self.cell_gap_mm > 0 and clipped_polygons:
            scaling_factor = 1.0 - (self.cell_gap_mm / self.cell_avg_width)
            scaling_factor = max(0.1, scaling_factor)
            
            for poly in clipped_polygons:
                final_voronoi_polygons.append(poly.scale(scaling_factor))
        else:
            final_voronoi_polygons = clipped_polygons

        text_polygons = []
        if self.add_text_label and self.text_content:
            try:
                text_obj = gdstk.text(
                    self.text_content, 
                    self.text_height_mm * self.unit, 
                    (self.boundary_width_mm / 2 * self.unit, self.boundary_height_mm / 2 * self.unit)
                )
                temp_cell = gdstk.Cell("TEMP_TEXT").add(*text_obj)
                text_polygons = temp_cell.get_polygons()
            except Exception as e:
                print(f"Warning: Could not generate text polygons with gdstk. Error: {e}")

        if text_polygons:
            final_polygons = gdstk.boolean(final_voronoi_polygons, text_polygons, 'not')
        else:
            final_polygons = final_voronoi_polygons

        doc = ezdxf.new()
        msp = doc.modelspace()

        b_pts = [
            (0, 0), (self.boundary_width_mm, 0),
            (self.boundary_width_mm, self.boundary_height_mm), (0, self.boundary_height_mm)
        ]
        msp.add_lwpolyline(b_pts, close=True, dxfattribs={"layer": "Boundary"})
        
        for poly in final_polygons:
            points_in_mm = poly.points / self.unit
            msp.add_lwpolyline(points_in_mm, close=True, dxfattribs={"layer": "Pattern"})
        
        stream = io.StringIO()
        doc.write(stream)
    
        return stream.getvalue()


# --- API 入口函式 (修改後) ---
def generate_jitter_grid_dxf(params: JitterGridRequest) -> str:
    """
    API 的入口點，接收 Pydantic 模型並呼叫生成器。
    回傳 DXF 檔案內容的字串。
    """
    # 將 Pydantic 模型轉換為字典，傳遞給生成器類別
    generator = VoronoiPatternGenerator(**params.model_dump())
    dxf_content = generator.run_generation_process()
    return dxf_content

