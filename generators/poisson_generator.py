# /generators/poisson_generator.py (修正版)

import io
import numpy as np
from scipy.spatial import Voronoi
import gdstk
import ezdxf

# 從我們的模型檔案中導入請求模型
from api.models import PoissonRequest

class PoissonVoronoiGenerator:
    """
    使用泊松盤採樣 (Poisson Disc Sampling) 生成的點來建立 Voronoi 圖樣。
    """
    def __init__(self, **kwargs):
        self.width = kwargs.get('boundary_width_mm')
        self.height = kwargs.get('boundary_height_mm')
        self.radius = kwargs.get('radius_mm')
        self.k = kwargs.get('k_samples')
        self.cell_gap_mm = kwargs.get('cell_gap_mm')
        self.add_text_label = kwargs.get('add_text_label', False)
        self.text_content = kwargs.get('text_content', "")
        self.text_height_mm = kwargs.get('text_height_mm', 5.0)
        self.font_name = kwargs.get('font_name', "Arial.ttf")
        self.output_unit = kwargs.get('output_unit', 'mm')
        
        self.unit = 1000 if self.output_unit == 'um' else 1

    def _generate_poisson_disc_points(self) -> np.ndarray:
        cellsize = self.radius / np.sqrt(2)
        grid_width = int(np.ceil(self.width / cellsize))
        grid_height = int(np.ceil(self.height / cellsize))
        grid = np.full((grid_width, grid_height), None, dtype=object)
        
        process_list, points = [], []
        first_point = np.random.uniform(0, [self.width, self.height])
        process_list.append(first_point)
        points.append(first_point)
        grid_x, grid_y = int(first_point[0] / cellsize), int(first_point[1] / cellsize)
        grid[grid_x, grid_y] = first_point

        while process_list:
            p = process_list.pop(np.random.randint(len(process_list)))
            for _ in range(self.k):
                theta = np.random.uniform(0, 2 * np.pi)
                r = np.random.uniform(self.radius, 2 * self.radius)
                new_point = p + r * np.array([np.cos(theta), np.sin(theta)])

                if 0 <= new_point[0] < self.width and 0 <= new_point[1] < self.height:
                    gx, gy = int(new_point[0] / cellsize), int(new_point[1] / cellsize)
                    is_valid = True
                    for i in range(max(0, gx - 2), min(grid_width, gx + 3)):
                        for j in range(max(0, gy - 2), min(grid_height, gy + 3)):
                            if grid[i, j] is not None and np.linalg.norm(grid[i, j] - new_point) < self.radius:
                                is_valid = False
                                break
                        if not is_valid: break
                    
                    if is_valid:
                        process_list.append(new_point)
                        points.append(new_point)
                        grid[gx, gy] = new_point
        return np.array(points)

    def run_generation_process(self) -> str:
        points = self._generate_poisson_disc_points()
        if len(points) == 0:
            doc = ezdxf.new()
            stream = io.StringIO()
            doc.write(stream)
            return stream.getvalue()
            
        avg_dist = np.sqrt((self.width * self.height) / len(points))
        vor = Voronoi(points)
        voronoi_polygons_gds = [gdstk.Polygon(np.array([vor.vertices[i] for i in r]) * self.unit) for r in vor.regions if r and -1 not in r]

        boundary_gds = gdstk.rectangle((0, 0), (self.width * self.unit, self.height * self.unit))
        clipped_polygons = gdstk.boolean(voronoi_polygons_gds, boundary_gds, 'and')

        if self.cell_gap_mm > 0 and clipped_polygons:
            scaling_factor = max(0.1, 1.0 - (self.cell_gap_mm / avg_dist))
            final_voronoi_polygons = [poly.scale(scaling_factor) for poly in clipped_polygons]
        else:
            final_voronoi_polygons = clipped_polygons

        text_polygons = []
        if self.add_text_label and self.text_content:
            try:
                text_obj = gdstk.text(self.text_content, self.text_height_mm * self.unit, (self.width / 2 * self.unit, self.height / 2 * self.unit))
                text_polygons = gdstk.Cell("TEMP_TEXT").add(*text_obj).get_polygons()
            except Exception as e:
                print(f"Warning: Could not generate text polygons with gdstk. Error: {e}")

        final_polygons = gdstk.boolean(final_voronoi_polygons, text_polygons, 'not') if text_polygons else final_voronoi_polygons

        doc = ezdxf.new()
        msp = doc.modelspace()
        b_pts = [(0,0), (self.width, 0), (self.width, self.height), (0, self.height)]
        msp.add_lwpolyline(b_pts, close=True, dxfattribs={"layer": "Boundary"})
        
        for poly in final_polygons:
            msp.add_lwpolyline(poly.points / self.unit, close=True, dxfattribs={"layer": "Pattern"})
            
        stream = io.StringIO()
        doc.write(stream)
        return stream.getvalue()

# --- API 入口函式 (已修正) ---
def generate_poisson_dxf(params: PoissonRequest) -> str:
    """
    API 的入口點，接收 Pydantic 模型並呼叫生成器。
    回傳 DXF 檔案內容的字串。
    """
    # 將 Pydantic 模型轉換為字典，傳遞給生成器類別
    generator = PoissonVoronoiGenerator(**params.model_dump())
    dxf_content = generator.run_generation_process()
    return dxf_content

