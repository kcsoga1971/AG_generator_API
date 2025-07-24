# generators/poisson_generator.py

import numpy as np
from scipy.spatial import Voronoi
import gdstk
import ezdxf

class PoissonVoronoiGenerator:
    """
    使用泊松盤採樣 (Poisson Disc Sampling) 生成的點來建立 Voronoi 圖樣。
    所有幾何運算都在 gdstk 中完成，最後匯出為 DXF。
    """
    def __init__(
        self,
        boundary_width_mm: float, boundary_height_mm: float,
        radius_mm: float, k_samples: int,
        cell_gap_mm: float,
        add_text_label: bool, text_content: str, text_height_mm: float,
        font_name: str, output_unit: str, **kwargs
    ):
        self.width = boundary_width_mm
        self.height = boundary_height_mm
        self.radius = radius_mm
        self.k = k_samples
        self.cell_gap_mm = cell_gap_mm
        self.add_text_label = add_text_label
        self.text_content = text_content
        self.text_height_mm = text_height_mm
        self.font_name = font_name
        self.output_unit = output_unit
        
        # gdstk 預設單位是微米(um)。如果我們以 mm 工作，需要轉換。
        self.unit = 1000 if self.output_unit == 'um' else 1

    def _generate_poisson_disc_points(self) -> np.ndarray:
        """
        使用 Bridson 演算法實現泊松盤採樣，生成在邊界內均勻分佈的點。
        """
        cellsize = self.radius / np.sqrt(2)
        grid_width = int(np.ceil(self.width / cellsize))
        grid_height = int(np.ceil(self.height / cellsize))
        grid = np.full((grid_width, grid_height), None, dtype=object)
        
        process_list = []
        points = []

        # 產生第一個點
        first_point = np.random.uniform(0, [self.width, self.height])
        process_list.append(first_point)
        points.append(first_point)
        grid_x, grid_y = int(first_point[0] / cellsize), int(first_point[1] / cellsize)
        grid[grid_x, grid_y] = first_point

        # 迭代生成新點
        while process_list:
            p = process_list.pop(np.random.randint(len(process_list)))
            for _ in range(self.k):
                theta = np.random.uniform(0, 2 * np.pi)
                r = np.random.uniform(self.radius, 2 * self.radius)
                new_point = p + r * np.array([np.cos(theta), np.sin(theta)])

                if 0 <= new_point[0] < self.width and 0 <= new_point[1] < self.height:
                    gx, gy = int(new_point[0] / cellsize), int(new_point[1] / cellsize)
                    
                    is_valid = True
                    # 檢查鄰近網格是否有衝突點
                    for i in range(max(0, gx - 2), min(grid_width, gx + 3)):
                        for j in range(max(0, gy - 2), min(grid_height, gy + 3)):
                            if grid[i, j] is not None:
                                if np.linalg.norm(grid[i, j] - new_point) < self.radius:
                                    is_valid = False
                                    break
                        if not is_valid:
                            break
                    
                    if is_valid:
                        process_list.append(new_point)
                        points.append(new_point)
                        grid[gx, gy] = new_point
        return np.array(points)

    def run_generation_process(self) -> str:
        """
        執行完整的生成流程，並回傳 DXF 格式的字串。
        """
        # 1. 產生泊松盤採樣點
        points = self._generate_poisson_disc_points()
        if len(points) == 0:
            # 如果沒有生成任何點，返回一個空的 DXF
            return ezdxf.new().tostring()
            
        # 計算平均間距，用於縮放
        avg_dist = np.sqrt((self.width * self.height) / len(points))

        # 2. 建立 Voronoi 圖並轉換為 gdstk 多邊形
        vor = Voronoi(points)
        voronoi_polygons_gds = []
        for region in vor.regions:
            if not region or -1 in region:
                continue
            polygon_points = np.array([vor.vertices[i] for i in region]) * self.unit
            voronoi_polygons_gds.append(gdstk.Polygon(polygon_points))

        # 3. 建立邊界並裁剪 Voronoi 多邊形
        boundary_gds = gdstk.rectangle(
            (0, 0),
            (self.width * self.unit, self.height * self.unit)
        )
        clipped_polygons = gdstk.boolean(voronoi_polygons_gds, boundary_gds, 'and')

        # 4. 縮放多邊形以產生間隙
        final_voronoi_polygons = []
        if self.cell_gap_mm > 0 and clipped_polygons:
            scaling_factor = 1.0 - (self.cell_gap_mm / avg_dist)
            scaling_factor = max(0.1, scaling_factor)
            
            for poly in clipped_polygons:
                final_voronoi_polygons.append(poly.scale(scaling_factor))
        else:
            final_voronoi_polygons = clipped_polygons

        # 5. 產生文字多邊形 (如果需要)
        text_polygons = []
        if self.add_text_label and self.text_content:
            try:
                text_obj = gdstk.text(
                    self.text_content, 
                    self.text_height_mm * self.unit, 
                    (self.width / 2 * self.unit, self.height / 2 * self.unit)
                )
                temp_cell = gdstk.Cell("TEMP_TEXT").add(*text_obj)
                text_polygons = temp_cell.get_polygons()
            except Exception as e:
                print(f"Warning: Could not generate text polygons with gdstk. Error: {e}")

        # 6. 從 Voronoi 圖案中減去 (挖空) 文字
        if text_polygons:
            final_polygons = gdstk.boolean(final_voronoi_polygons, text_polygons, 'not')
        else:
            final_polygons = final_voronoi_polygons

        # 7. 將最終的幾何圖形寫入 DXF 文件
        doc = ezdxf.new()
        msp = doc.modelspace()

        b_pts = [(0,0), (self.width, 0), (self.width, self.height), (0, self.height)]
        msp.add_lwpolyline(b_pts, close=True, dxfattribs={"layer": "Boundary"})
        
        for poly in final_polygons:
            points_in_mm = poly.points / self.unit
            msp.add_lwpolyline(points_in_mm, close=True, dxfattribs={"layer": "Pattern"})
            
        return doc.tostring()

# --- API 入口函式 ---
def generate(**kwargs) -> str:
    """
    API 的入口點，接收參數字典並呼叫生成器。
    """
    generator = PoissonVoronoiGenerator(**kwargs)
    dxf_content = generator.run_generation_process()
    return dxf_content

