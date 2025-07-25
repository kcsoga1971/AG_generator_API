# generators/jitter_grid_generator.py

import io
import numpy as np
from scipy.spatial import Voronoi
import gdstk
import ezdxf

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
            # 添加邊界外的"鬼"點來改善邊緣單元格的形狀
            box = [0, 0, self.boundary_width_mm, self.boundary_height_mm]
            vor = Voronoi(points, qhull_options="Qbb Qc Qz") # 選項有助於穩定性
            
            new_points = []
            for idx, region_idx in enumerate(vor.point_region):
                if region_idx == -1:
                    new_points.append(points[idx]) # 保留無效區域的點
                    continue
                
                region = vor.regions[region_idx]
                if not region or -1 in region:
                    new_points.append(points[idx]) # 保留開放區域的點
                    continue

                # 計算區域的質心
                polygon = np.array([vor.vertices[i] for i in region])
                centroid = np.mean(polygon, axis=0)
                
                # 確保質心在邊界內
                centroid[0] = np.clip(centroid[0], box[0], box[2])
                centroid[1] = np.clip(centroid[1], box[1], box[3])
                new_points.append(centroid)

            points = np.array(new_points)
        return points

    def run_generation_process(self) -> str:
        """
        執行完整的生成流程，並回傳 DXF 格式的字串。
        流程: 產生點 -> 鬆弛點 -> 產生 Voronoi 多邊形 -> 縮放/裁剪 -> 減去文字 -> 匯出 DXF
        """
        # 1. 產生和鬆弛點
        initial_points = self._generate_initial_points()
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
            # 計算縮放因子
            scaling_factor = 1.0 - (self.cell_gap_mm / self.cell_avg_width)
            scaling_factor = max(0.1, scaling_factor) # 避免縮放到零或負數
            
            for poly in clipped_polygons:
                # gdstk 的 scale 方法以質心為中心進行縮放
                final_voronoi_polygons.append(poly.scale(scaling_factor))
        else:
            final_voronoi_polygons = clipped_polygons

        # 5. 產生文字多邊形 (如果需要)
        text_polygons = []
        if self.add_text_label and self.text_content:
            try:
                # gdstk.text 需要字體檔案路徑，這裡假設它在一個 'fonts' 資料夾中
                # 在生產環境中，您需要確保這個路徑是正確的
                # from pathlib import Path
                # font_path = Path("fonts") / self.font_name
                
                text_obj = gdstk.text(
                    self.text_content, 
                    self.text_height_mm * self.unit, 
                    (self.boundary_width_mm / 2 * self.unit, self.boundary_height_mm / 2 * self.unit),
                    # font=str(font_path) # 如果字體不在系統路徑中
                )
                # 將文字轉換為多邊形
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

        # 添加邊界框
        b_pts = [
            (0, 0), (self.boundary_width_mm, 0),
            (self.boundary_width_mm, self.boundary_height_mm), (0, self.boundary_height_mm)
        ]
        msp.add_lwpolyline(b_pts, close=True, dxfattribs={"layer": "Boundary"})
        
        # 添加最終的圖案多邊形
        for poly in final_polygons:
            # 從 gdstk 單位轉換回 DXF 單位 (mm)
            points_in_mm = poly.points / self.unit
            msp.add_lwpolyline(points_in_mm, close=True, dxfattribs={"layer": "Pattern"})
        
        # ... (省略前面添加多邊形的程式碼)

        # 【最終修復】將 DXF 內容寫入記憶體中的文字串流。
        # 我們不再需要任何 DEBUG 或 DIAGNOSTICS 輸出，將它們全部移除。
        stream = io.StringIO()
        doc.write(stream)
    
        # 從串流的開頭讀取所有內容並回傳
        return stream.getvalue()


# --- API 入口函式 ---
def generate(**kwargs) -> str:
    """
    API 的入口點，接收參數字典並呼叫生成器。
    回傳 DXF 檔案內容的字串。
    """
    # Pydantic 模型已經在 API 層處理了預設值和驗證，這裡直接實例化即可
    generator = VoronoiPatternGenerator(**kwargs)
    dxf_content = generator.run_generation_process()
    return dxf_content


