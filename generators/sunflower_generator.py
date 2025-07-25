# generators/sunflower_generator.py

import io
import numpy as np
from scipy.spatial import Voronoi
import gdstk
import ezdxf

class SunflowerVoronoiGenerator:
    """
    使用向日葵螺旋（費馬螺線）分佈的點來生成 Voronoi 圖樣。
    所有幾何運算都在 gdstk 中完成，最後匯出為 DXF。
    """
    def __init__(
        self,
        boundary_width_mm: float, boundary_height_mm: float,
        num_points: int, sunflower_c: float, jitter_strength: float,
        relaxation_steps: int, cell_gap_mm: float,
        add_text_label: bool, text_content: str, text_height_mm: float,
        font_name: str, output_unit: str, **kwargs
    ):
        self.boundary_width_mm = boundary_width_mm
        self.boundary_height_mm = boundary_height_mm
        self.num_points = num_points
        self.sunflower_c = sunflower_c
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
        
        # 計算點的平均間距，用於縮放和抖動計算
        self.avg_dist = np.sqrt((self.boundary_width_mm * self.boundary_height_mm) / self.num_points)

    def _generate_sunflower_points(self) -> np.ndarray:
        """根據向日葵演算法生成點，並限制在邊界內。"""
        points = []
        phi = (1 + np.sqrt(5)) / 2  # 黃金比例
        center_x, center_y = self.boundary_width_mm / 2.0, self.boundary_height_mm / 2.0
        
        # 生成足夠的點以填滿矩形邊界
        # 我們需要找到能觸及角落的最大半徑
        max_radius = np.sqrt(center_x**2 + center_y**2)
        # 根據 r = c * sqrt(n) 反推需要的點數 n = (r/c)^2
        num_points_for_radius = int((max_radius / self.sunflower_c)**2) + 1
        
        for i in range(max(self.num_points, num_points_for_radius)):
            r = self.sunflower_c * np.sqrt(i)
            theta = 2 * np.pi * i / phi
            x = center_x + r * np.cos(theta)
            y = center_y + r * np.sin(theta)
            # 只保留在邊界內的點
            if 0 <= x <= self.boundary_width_mm and 0 <= y <= self.boundary_height_mm:
                points.append([x, y])
        
        # 如果生成的點多於需求，則從中隨機抽樣
        points = np.array(points)
        if len(points) > self.num_points:
            indices = np.random.choice(len(points), self.num_points, replace=False)
            points = points[indices]

        # 添加抖動
        if self.jitter_strength > 0:
            max_jitter = self.avg_dist * self.jitter_strength
            points += (np.random.rand(points.shape[0], 2) - 0.5) * max_jitter
            points = np.clip(points, [0, 0], [self.boundary_width_mm, self.boundary_height_mm])

        return points

    def _relax_points(self, points: np.ndarray) -> np.ndarray:
        """使用 Lloyd's 演算法對點進行鬆弛，使其分佈更均勻。 (與 jitter_grid 版本相同)"""
        for _ in range(self.relaxation_steps):
            box = [0, 0, self.boundary_width_mm, self.boundary_height_mm]
            vor = Voronoi(points, qhull_options="Qbb Qc Qz")
            
            new_points = []
            for idx, region_idx in enumerate(vor.point_region):
                if region_idx == -1 or not vor.regions[region_idx] or -1 in vor.regions[region_idx]:
                    new_points.append(points[idx])
                    continue

                polygon = np.array([vor.vertices[i] for i in vor.regions[region_idx]])
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
        # 1. 產生和鬆弛點
        initial_points = self._generate_sunflower_points()
        if self.relaxation_steps > 0:
            final_points = self._relax_points(initial_points)
        else:
            final_points = initial_points
            
        # 2. 建立 Voronoi 圖並轉換為 gdstk 多邊形
        vor = Voronoi(final_points)
        voronoi_polygons_gds = []
        for region in vor.regions:
            if not region or -1 in region:
                continue
            polygon_points = np.array([vor.vertices[i] for i in region]) * self.unit
            voronoi_polygons_gds.append(gdstk.Polygon(polygon_points))

        # 3. 建立邊界並裁剪 Voronoi 多邊形
        boundary_gds = gdstk.rectangle(
            (0, 0),
            (self.boundary_width_mm * self.unit, self.boundary_height_mm * self.unit)
        )
        clipped_polygons = gdstk.boolean(voronoi_polygons_gds, boundary_gds, 'and')

        # 4. 縮放多邊形以產生間隙
        final_voronoi_polygons = []
        if self.cell_gap_mm > 0 and clipped_polygons:
            scaling_factor = 1.0 - (self.cell_gap_mm / self.avg_dist)
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
                    (self.boundary_width_mm / 2 * self.unit, self.boundary_height_mm / 2 * self.unit)
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

        b_pts = [(0,0), (self.boundary_width_mm, 0), (self.boundary_width_mm, self.boundary_height_mm), (0, self.boundary_height_mm)]
        msp.add_lwpolyline(b_pts, close=True, dxfattribs={"layer": "Boundary"})
        
        for poly in final_polygons:
            points_in_mm = poly.points / self.unit
            msp.add_lwpolyline(points_in_mm, close=True, dxfattribs={"layer": "Pattern"})
            
        # 【最終修復】將 DXF 內容寫入記憶體中的文字串流
        stream = io.StringIO()
        doc.write(stream)
    
        # 從串流的開頭讀取所有內容並回傳
        return stream.getvalue()

# --- API 入口函式 ---
def generate(**kwargs) -> str:
    """
    API 的入口點，接收參數字典並呼叫生成器。
    """
    generator = SunflowerVoronoiGenerator(**kwargs)
    dxf_content = generator.run_generation_process()
    return dxf_content
