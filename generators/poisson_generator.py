# generators/poisson_generator.py

import numpy as np
from scipy.spatial import Voronoi
import gdstk
import ezdxf
from ezdxf.addons import text2path
from ezdxf.math import BoundingBox
from ezdxf.enums import TextEntityAlignment

class PoissonDiscVoronoiGenerator:
    def __init__(
        self,
        boundary_width_mm: float, boundary_height_mm: float,
        radius_mm: float, k_samples: int,
        cell_gap_mm: float,
        add_text_label: bool, text_content: str, text_height_mm: float,
        font_name: str, output_unit: str
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
        self.mm_to_gds_unit = 1000 if self.output_unit == 'um' else 1

    def _generate_poisson_disc_points(self):
        cellsize = self.radius / np.sqrt(2)
        grid_width = int(np.ceil(self.width / cellsize))
        grid_height = int(np.ceil(self.height / cellsize))
        grid = np.empty((grid_width, grid_height), dtype=object)
        
        process_list = []
        points = []

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
                        ezdxf.math.Matrix44.translate(self.width / 2, self.height / 2, 0)
            path.transform(transform)
            path.render_splines_as_polylines(flattening_distance=0.01)
            for sub_path in path.sub_paths():
                msp.add_lwpolyline(sub_path.points(), close=sub_path.is_closed, dxfattribs={'layer': 'Text'})
        except Exception as e:
            print(f"Warning: Could not add text to DXF. Error: {e}")

    def run_generation_process(self):
        points = self._generate_poisson_disc_points()
        voronoi_polygons_np = self._create_voronoi_polygons(points)
        num_points = len(points)

        boundary_poly_gds = gdstk.rectangle((0, 0), (self.width * self.mm_to_gds_unit, self.height * self.mm_to_gds_unit))
        
        scaled_polygons_gds = []
        if self.cell_gap_mm > 0:
            avg_dist = np.sqrt((self.width * self.height) / num_points)
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
                    (self.width/2 * self.mm_to_gds_unit, self.height/2 * self.mm_to_gds_unit),
                    layer=2
                )
                text_cell.add(*text_obj)
                text_polygons_gds = text_cell.get_polygons()
                final_polygons = gdstk.boolean(clipped_polygons_gds, text_polygons_gds, 'not', layer=1)
            except Exception as e:
                print(f"Warning: Could not generate text for GDS subtraction. Error: {e}")

        dxf_doc = ezdxf.new()
        msp = dxf_doc.modelspace()
        
        b_pts = [(0,0), (self.width, 0), (self.width, self.height), (0, self.height)]
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
        'radius_mm': 5.0,
        'k_samples': 30,
        'cell_gap_mm': 0.1,
        'add_text_label': False,
        'text_content': '',
        'text_height_mm': 10.0,
        'font_name': 'Arial.ttf',
        'output_unit': 'mm',
    }
    config.update(kwargs)
    generator = PoissonDiscVoronoiGenerator(**config)
    dxf_content = generator.run_generation_process()
    return dxf_content
