# generators/sunflower_generator.py

import numpy as np
from scipy.spatial import Voronoi
import gdstk
import ezdxf
from ezdxf.addons import text2path
from ezdxf.math import BoundingBox
from ezdxf.enums import TextEntityAlignment

class VoronoiPatternGenerator:
    def __init__(
        self,
        boundary_width_mm: float, boundary_height_mm: float,
        num_points: int, sunflower_c: float, jitter_strength: float,
        relaxation_steps: int, cell_gap_mm: float,
        add_text_label: bool, text_content: str, text_height_mm: float,
        font_name: str, output_unit: str
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
        self.mm_to_gds_unit = 1000 if self.output_unit == 'um' else 1
        self.mm_to_dxf_unit = 1

    def _generate_sunflower_points(self):
        points = []
        phi = (1 + np.sqrt(5)) / 2
        center_x, center_y = self.boundary_width_mm / 2.0, self.boundary_height_mm / 2.0

        for i in range(self.num_points):
            r = self.sunflower_c * np.sqrt(i)
            theta = 2 * np.pi * i / phi
            x = center_x + r * np.cos(theta)
            y = center_y + r * np.sin(theta)
            if 0 <= x <= self.boundary_width_mm and 0 <= y <= self.boundary_height_mm:
                points.append([x, y])
        
        points = np.array(points)
        
        if self.jitter_strength > 0:
            avg_min_dist = min(self.boundary_width_mm, self.boundary_height_mm) / np.sqrt(self.num_points)
            max_jitter = avg_min_dist * self.jitter_strength
            points += (np.random.rand(points.shape[0], 2) - 0.5) * 2 * max_jitter
            points = np.clip(points, [0, 0], [self.boundary_width_mm, self.boundary_height_mm])

        return points

    def _relax_points(self, points):
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
        vor = Voronoi(points)
        polygons = []
        for region in vor.regions:
            if not region or -1 in region:
                continue
            polygon = [vor.vertices[i] for i in region]
            polygons.append(np.array(polygon))
        return polygons

    def _add_text_to_dxf(self, doc, msp):
        if not self.add_text_label or not self.text_content:
            return
        try:
            path = text2path.make_path_from_str(
                self.text_content, font=self.font_name, size=self.text_height_mm,
                align=TextEntityAlignment.MIDDLE_CENTER
            )
            bbox = BoundingBox(path.extents())
            transform = ezdxf.math.Matrix44.translate(-bbox.center.x, -bbox.center.y, 0) @ \
                        ezdxf.math.Matrix44.translate(self.boundary_width_mm / 2, self.boundary_height_mm / 2, 0)
            path.transform(transform)
            path.render_splines_as_polylines(flattening_distance=0.01)
            for sub_path in path.sub_paths():
                msp.add_lwpolyline(sub_path.points(), close=sub_path.is_closed, dxfattribs={'layer': 'Text'})
        except Exception as e:
            print(f"Warning: Could not add text to DXF. Error: {e}")

    def run_generation_process(self):
        points = self._generate_sunflower_points()
        if self.relaxation_steps > 0:
            points = self._relax_points(points)
        
        voronoi_polygons_np = self._create_voronoi_polygons(points)
        
        boundary_poly_gds = gdstk.rectangle((0, 0), (self.boundary_width_mm * self.mm_to_gds_unit, self.boundary_height_mm * self.mm_to_gds_unit))
        
        scaled_polygons_gds = []
        if self.cell_gap_mm > 0:
            avg_dist = np.sqrt((self.boundary_width_mm * self.boundary_height_mm) / self.num_points)
            scaling_factor = 1.0 - (self.cell_gap_mm / avg_dist)
            for p in voronoi_polygons_np:
                centroid = p.mean(axis=0)
                scaled_p = gdstk.Polygon((p - centroid) * scaling_factor + centroid)
                scaled_polygons_gds.append(scaled_p)
        else:
            scaled_polygons_gds = [gdstk.Polygon(p) for p in voronoi_polygons_np]

        clipped_polygons_gds = []
        for p in scaled_polygons_gds:
            clipped_list = gdstk.boolean(p, boundary_poly_gds, 'and')
            if clipped_list:
                clipped_polygons_gds.extend(clipped_list)
        
        final_polygons = clipped_polygons_gds
        if self.add_text_label and self.text_content:
            try:
                text_cell = gdstk.Cell("TEXT_TEMP")
                text_obj = gdstk.text(
                    self.text_content, self.text_height_mm * self.mm_to_gds_unit,
                    (self.boundary_width_mm/2 * self.mm_to_gds_unit, self.boundary_height_mm/2 * self.mm_to_gds_unit),
                    layer=2
                )
                text_cell.add(*text_obj)
                text_polygons_gds = text_cell.get_polygons()
                final_polygons = gdstk.boolean(clipped_polygons_gds, text_polygons_gds, 'not', layer=1)
            except Exception as e:
                print(f"Warning: Could not generate text for GDS subtraction. Error: {e}")

        dxf_doc = ezdxf.new()
        msp = dxf_doc.modelspace()
        
        b_pts = [(0,0), (self.boundary_width_mm, 0), (self.boundary_width_mm, self.boundary_height_mm), (0, self.boundary_height_mm)]
        msp.add_lwpolyline(b_pts, close=True, dxfattribs={"layer": "Boundary"})
        
        for poly in final_polygons:
            msp.add_lwpolyline(poly.points / self.mm_to_gds_unit, close=True, dxfattribs={"layer": "Voronoi_Final"})
            
        self._add_text_to_dxf(dxf_doc, msp)

        return dxf_doc.dumps()

# --- API 入口函式 ---
def generate(**kwargs) -> str:
    config = {
        'boundary_width_mm': 100.0,
        'boundary_height_mm': 100.0,
        'num_points': 500,
        'sunflower_c': 3.6,
        'jitter_strength': 0.1,
        'relaxation_steps': 0,
        'cell_gap_mm': 0.1,
        'add_text_label': False,
        'text_content': '',
        'text_height_mm': 10.0,
        'font_name': 'Arial.ttf',
        'output_unit': 'mm',
    }
    config.update(kwargs)
    generator = VoronoiPatternGenerator(**config)
    dxf_content = generator.run_generation_process()
    return dxf_content
