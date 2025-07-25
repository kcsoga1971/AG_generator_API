# /generators/jitter_grid_generator.py (最終修正版)

import io
import numpy as np
from scipy.spatial import Voronoi
import gdstk
import ezdxf

# 從我們的模型檔案中導入請求模型
from api.models import JitterGridRequest

class VoronoiPatternGenerator:
    """
    一個整合且高效能的 Voronoi 圖樣產生器。
    """
    def __init__(self, **kwargs):
        # 使用 .get() 方法安全地讀取參數，並提供預設值
        self.boundary_width_mm = kwargs.get('boundary_width_mm')
        self.boundary_height_mm = kwargs.get('boundary_height_mm')
        self.grid_rows = kwargs.get('grid_rows')
        self.grid_cols = kwargs.get('grid_cols')
        self.jitter_strength = kwargs.get('jitter_strength')
        self.relaxation_steps = kwargs.get('relaxation_steps')
        self.cell_gap_mm = kwargs.get('cell_gap_mm')
        self.add_text_label = kwargs.get('add_text_label', False)
        self.text_content = kwargs.get('text_content', "Test")
        self.text_height_mm = kwargs.get('text_height_mm', 5.0)
        self.font_name = kwargs.get('font_name', "Arial.ttf")
        self.output_unit = kwargs.get('output_unit', 'mm')
        
        self.unit = 1000 if self.output_unit == 'um' else 1
        self.cell_avg_width = self.boundary_width_mm / self.grid_cols

    def _generate_initial_points(self) -> np.ndarray:
        x = np.linspace(0, self.boundary_width_mm, self.grid_cols)
        y = np.linspace(0, self.boundary_height_mm, self.grid_rows)
        xv, yv = np.meshgrid(x, y)
        points = np.vstack([xv.ravel(), yv.ravel()]).T
        max_jitter = self.cell_avg_width * self.jitter_strength
        points += (np.random.rand(points.shape[0], 2) - 0.5) * max_jitter
        return points

    def _relax_points(self, points: np.ndarray) -> np.ndarray:
        for _ in range(self.relaxation_steps):
            box = [0, 0, self.boundary_width_mm, self.boundary_height_mm]
            vor = Voronoi(points, qhull_options="Qbb Qc Qz")
            new_points = []
            for idx, region_idx in enumerate(vor.point_region):
                if region_idx == -1 or not vor.regions[region_idx] or -1 in vor.regions[region_idx]:
                    new_points.append(points[idx])
                    continue
                region = vor.regions[region_idx]
                polygon = np.array([vor.vertices[i] for i in region])
                centroid = np.mean(polygon, axis=0)
                centroid[0] = np.clip(centroid[0], box[0], box[2])
                centroid[1] = np.clip(centroid[1], box[1], box[3])
                new_points.append(centroid)
            points = np.array(new_points)
        return points

    def run_generation_process(self) -> str:
        initial_points = self._generate_initial_points()
        final_points = self._relax_points(initial_points) if self.relaxation_steps > 0 else initial_points
            
        vor = Voronoi(final_points)
        voronoi_polygons_gds = [gdstk.Polygon(np.array([vor.vertices[i] for i in r]) * self.unit) for r in vor.regions if r and -1 not in r]

        boundary_gds = gdstk.rectangle((0, 0), (self.boundary_width_mm * self.unit, self.boundary_height_mm * self.unit))
        clipped_polygons = gdstk.boolean(voronoi_polygons_gds, boundary_gds, 'and')

        if self.cell_gap_mm > 0 and clipped_polygons:
            scaling_factor = max(0.1, 1.0 - (self.cell_gap_mm / self.cell_avg_width))
            final_voronoi_polygons = [poly.scale(scaling_factor) for poly in clipped_polygons]
        else:
            final_voronoi_polygons = clipped_polygons

        text_polygons = []
        if self.add_text_label and self.text_content:
            try:
                text_obj = gdstk.text(self.text_content, self.text_height_mm * self.unit, (self.boundary_width_mm / 2 * self.unit, self.boundary_height_mm / 2 * self.unit))
                text_polygons = gdstk.Cell("TEMP_TEXT").add(*text_obj).get_polygons()
            except Exception as e:
                print(f"Warning: Could not generate text polygons with gdstk. Error: {e}")

        final_polygons = gdstk.boolean(final_voronoi_polygons, text_polygons, 'not') if text_polygons else final_voronoi_polygons

        doc = ezdxf.new()
        msp = doc.modelspace()
        b_pts = [(0, 0), (self.boundary_width_mm, 0), (self.boundary_width_mm, self.boundary_height_mm), (0, self.boundary_height_mm)]
        msp.add_lwpolyline(b_pts, close=True, dxfattribs={"layer": "Boundary"})
        
        for poly in final_polygons:
            msp.add_lwpolyline(poly.points / self.unit, close=True, dxfattribs={"layer": "Pattern"})
        
        stream = io.StringIO()
        doc.write(stream)
        return stream.getvalue()

# --- API 入口函式 (已修正) ---
def generate_jitter_grid_dxf(params: JitterGridRequest) -> str:
    """
    API 的入口點，接收 Pydantic 模型並呼叫生成器。
    回傳 DXF 檔案內容的字串。
    """
    # 將 Pydantic 模型轉換為字典，傳遞給生成器類別
    generator = VoronoiPatternGenerator(**params.model_dump())
    dxf_content = generator.run_generation_process()
    return dxf_content
