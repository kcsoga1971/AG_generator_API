# generators/jitter_grid_generator.py

import numpy as np
from scipy.spatial import Voronoi
import gdstk
import ezdxf
from ezdxf.addons import text2path
from ezdxf.math import BoundingBox
from ezdxf.enums import TextEntityAlignment

# (這裡貼上您原始檔案中的 VoronoiPatternGenerator 類別，無需任何修改)
class VoronoiPatternGenerator:
    """
    一個整合且高效能的 Voronoi 圖樣產生器 (Jitter Grid + Relaxation)。
    """
    def __init__(
        self,
        boundary_width_mm: float, boundary_height_mm: float,
        grid_rows: int, grid_cols: int, jitter_strength: float,
        relaxation_steps: int, cell_gap_mm: float,
        add_text_label: bool, text_content: str, text_height_mm: float,
        font_name: str, output_unit: str
    ):
        # ... (您原始檔案中的完整 __init__ 內容) ...
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
        self.mm_to_gds_unit = 1000 if self.output_unit == 'um' else 1
        self.mm_to_dxf_unit = 1 # DXF is unitless, but we work in mm

    def _generate_initial_points(self):
        # ... (您原始檔案中的完整 _generate_initial_points 內容) ...
        x = np.linspace(0, self.boundary_width_mm, self.grid_cols)
        y = np.linspace(0, self.boundary_height_mm, self.grid_rows)
        xv, yv = np.meshgrid(x, y)
        points = np.vstack([xv.ravel(), yv.ravel()]).T
        cell_width = self.boundary_width_mm / (self.grid_cols - 1) if self.grid_cols > 1 else self.boundary_width_mm
        cell_height = self.boundary_height_mm / (self.grid_rows - 1) if self.grid_rows > 1 else self.boundary_height_mm
        max_jitter = min(cell_width, cell_height) * self.jitter_strength
        points += (np.random.rand(points.shape[0], 2) - 0.5) * 2 * max_jitter
        return points

    def _relax_points(self, points):
        # ... (您原始檔案中的完整 _relax_points 內容) ...
        for _ in range(self.relaxation_steps):
            vor = Voronoi(points)
            new_points = []
            for idx, region_idx in enumerate(vor.point_region):
                if region_idx != -1 and all(i != -1 for i in vor.regions[region_idx]):
                    polygon = [vor.vertices[i] for i in vor.regions[region_idx]]
                    centroid = np.mean(polygon, axis=0)
                    new_points.append(centroid)
                else:
                    new_points.append(vor.points[idx])
            points = np.array(new_points)
        return points

    def _create_voronoi_polygons(self, points):
        # ... (您原始檔案中的完整 _create_voronoi_polygons 內容) ...
        vor = Voronoi(points)
        polygons = []
        for region in vor.regions:
            if not region or -1 in region:
                continue
            polygon = [vor.vertices[i] for i in region]
            polygons.append(np.array(polygon))
        return polygons

    def _scale_and_clip_polygons(self, polygons):
        # ... (您原始檔案中的完整 _scale_and_clip_polygons 內容) ...
        boundary_poly = gdstk.rectangle(
            (0, 0),
            (self.boundary_width_mm * self.mm_to_gds_unit, self.boundary_height_mm * self.mm_to_gds_unit)
        )
        scaling_factor = 1.0 - (self.cell_gap_mm * np.sqrt(2) / (self.boundary_width_mm / self.grid_cols))
        scaled_clipped_polygons = []
        for poly_np in polygons:
            centroid = poly_np.mean(axis=0)
            poly_gdstk = gdstk.Polygon((poly_np - centroid) * scaling_factor + centroid)
            clipped_list = gdstk.boolean(poly_gdstk, boundary_poly, 'and')
            if clipped_list:
                scaled_clipped_polygons.extend(clipped_list)
        return scaled_clipped_polygons

    def _add_text_to_dxf(self, doc, msp):
        # ... (您原始檔案中的完整 _add_text_to_dxf 內容) ...
        if not self.add_text_label or not self.text_content:
            return
        try:
            path = text2path.make_path_from_str(
                self.text_content,
                font=self.font_name,
                size=self.text_height_mm,
                align=TextEntityAlignment.MIDDLE_CENTER
            )
            bbox = BoundingBox(path.extents())
            transform_matrix = ezdxf.math.Matrix44.translate(
                -bbox.center.x, -bbox.center.y, 0
            ) @ ezdxf.math.Matrix44.translate(
                self.boundary_width_mm / 2, self.boundary_height_mm / 2, 0
            )
            path.transform(transform_matrix)
            path.render_splines_as_polylines(flattening_distance=0.01)
            path.render_points_as_lines(radius=0.005)
            for sub_path in path.sub_paths():
                msp.add_lwpolyline(sub_path.points(), close=sub_path.is_closed)
        except Exception as e:
            print(f"Warning: Could not add text to DXF. Error: {e}")

    def _save_dxf(self, polygons, text_polygons):
        # ... (您原始檔案中的完整 _save_dxf 內容) ...
        doc = ezdxf.new()
        msp = doc.modelspace()
        boundary_pts = [
            (0, 0), (self.boundary_width_mm, 0),
            (self.boundary_width_mm, self.boundary_height_mm),
            (0, self.boundary_height_mm)
        ]
        msp.add_lwpolyline(boundary_pts, close=True, dxfattribs={'layer': 'Boundary'})
        for poly in polygons:
            msp.add_lwpolyline(poly.points, close=True, dxfattribs={'layer': 'Voronoi'})
        if text_polygons:
            for poly in text_polygons:
                msp.add_lwpolyline(poly.points, close=True, dxfattribs={'layer': 'Text'})
        return doc.tostring()

    def run_generation_process(self):
        # ... (您原始檔案中的完整 run_generation_process 內容，但修改了回傳值) ...
        points = self._generate_initial_points()
        if self.relaxation_steps > 0:
            points = self._relax_points(points)
        
        voronoi_polygons = self._create_voronoi_polygons(points)
        
        boundary_poly_gds = gdstk.rectangle(
            (0, 0), 
            (self.boundary_width_mm * self.mm_to_gds_unit, self.boundary_height_mm * self.mm_to_gds_unit)
        )
        
        scaled_polygons = []
        if self.cell_gap_mm > 0:
            scaling_factor = 1.0 - (self.cell_gap_mm / (self.boundary_width_mm / self.grid_cols))
            for p in voronoi_polygons:
                centroid = p.mean(axis=0)
                scaled_p = gdstk.Polygon((p - centroid) * scaling_factor + centroid)
                scaled_polygons.append(scaled_p)
        else:
            scaled_polygons = [gdstk.Polygon(p) for p in voronoi_polygons]

        clipped_polygons = []
        for p in scaled_polygons:
            clipped_list = gdstk.boolean(p, boundary_poly_gds, 'and')
            if clipped_list:
                clipped_polygons.extend(clipped_list)
        
        text_polygons_gds = []
        if self.add_text_label and self.text_content:
            try:
                text_cell = gdstk.Cell("TEXT_TEMP")
                text_obj = gdstk.text(
                    self.text_content, 
                    self.text_height_mm * self.mm_to_gds_unit, 
                    (self.boundary_width_mm/2 * self.mm_to_gds_unit, self.boundary_height_mm/2 * self.mm_to_gds_unit), 
                    layer=2
                )
                text_cell.add(*text_obj)
                text_polygons_gds = text_cell.get_polygons()
            except Exception as e:
                print(f"Warning: Could not generate text for GDS. Error: {e}")

        final_polygons = gdstk.boolean(clipped_polygons, text_polygons_gds, 'not', layer=1)
        
        # For DXF, we need to convert back to a simple list of numpy arrays for ezdxf
        dxf_doc = ezdxf.new()
        msp = dxf_doc.modelspace()
        
        # Add boundary
        b_pts = [(0,0), (self.boundary_width_mm, 0), (self.boundary_width_mm, self.boundary_height_mm), (0, self.boundary_height_mm)]
        msp.add_lwpolyline(b_pts, close=True, dxfattribs={"layer": "Boundary"})
        
        # Add final polygons
        for poly in final_polygons:
            msp.add_lwpolyline(poly.points / self.mm_to_gds_unit, close=True, dxfattribs={"layer": "Voronoi_Final"})
            
        # Add text via ezdxf's robust method
        self._add_text_to_dxf(dxf_doc, msp)

        return dxf_doc.tostring()


# --- API 入口函式 ---
def generate(**kwargs) -> str:
    """
    API 的入口點，接收參數並呼叫生成器。
    回傳 DXF 檔案內容的字串。
    """
    # 為可選參數提供預設值
    config = {
        'boundary_width_mm': 100.0,
        'boundary_height_mm': 100.0,
        'grid_rows': 30,
        'grid_cols': 30,
        'jitter_strength': 0.45,
        'relaxation_steps': 2,
        'cell_gap_mm': 0.1,
        'add_text_label': False,
        'text_content': '',
        'text_height_mm': 10.0,
        'font_name': 'Arial.ttf',
        'output_unit': 'mm',
    }
    # 使用傳入的參數更新預設設定
    config.update(kwargs)

    generator = VoronoiPatternGenerator(**config)
    dxf_content = generator.run_generation_process()
    return dxf_content

