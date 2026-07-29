from fastapi import FastAPI
from .fullbody_RnM import router as exercise_author_router

app = FastAPI()

app.include_router(exercise_author_router)