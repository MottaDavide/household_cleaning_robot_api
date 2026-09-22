"""Assembles the application from the three feature packages.

Each package brings its own router, and this is the only place that knows
about all of them at once.
"""

from fastapi import FastAPI
from src.app.system.routers import router as system_router
from src.app.map.routers import router as map_router
from src.app.robot.routers import router as robot_router


app = FastAPI(title="Household Cleaning Robot API")
app.include_router(system_router)
app.include_router(map_router)
app.include_router(robot_router)