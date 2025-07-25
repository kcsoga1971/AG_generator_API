# /api/index.py (最終正確版)

from fastapi import FastAPI, Body
from fastapi.responses import StreamingResponse
import io

from .models import JitterGridRequest, SunflowerRequest, PoissonRequest
from generators.jitter_grid_generator import generate_jitter_grid_dxf
from generators.sunflower_generator import generate_sunflower_dxf
from generators.poisson_generator import generate_poisson_dxf

app = FastAPI(
    title="Honeycomb API",
    description="An API for generating various honeycomb-like (Voronoi) patterns as DXF files.",
    version="1.0.0",
)

@app.get("/", tags=["General"])
def read_root():
    return {"message": "Welcome to the Honeycomb API. See /docs for endpoints."}

@app.post("/generate/jitter-grid", tags=["Generators"])
async def generate_jitter_grid_endpoint(params: JitterGridRequest = Body(...)):
    dxf_content = generate_jitter_grid_dxf(params)
    return StreamingResponse(
        io.BytesIO(dxf_content.encode()),
        media_type="application/vnd.dxf",
        headers={"Content-Disposition": "attachment; filename=jitter_grid.dxf"}
    )

@app.post("/generate/sunflower", tags=["Generators"])
async def generate_sunflower_endpoint(params: SunflowerRequest = Body(...)):
    dxf_content = generate_sunflower_dxf(params)
    return StreamingResponse(
        io.BytesIO(dxf_content.encode()),
        media_type="application/vnd.dxf",
        headers={"Content-Disposition": "attachment; filename=sunflower.dxf"}
    )

@app.post("/generate/poisson", tags=["Generators"])
async def generate_poisson_endpoint(params: PoissonRequest = Body(...)):
    dxf_content = generate_poisson_dxf(params)
    return StreamingResponse(
        io.BytesIO(dxf_content.encode()),
        media_type="application/vnd.dxf",
        headers={"Content-Disposition": "attachment; filename=poisson.dxf"}
    )
