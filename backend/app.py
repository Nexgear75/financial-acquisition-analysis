from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI()

origins = ["http://localhost:5173", "localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----- ENDPOINTS -----#
@app.get("/health")
async def get_health():
    return {"message": "Online"}


@app.get("/analyze/")
async def get_analyze(mother: str, child: str) -> str:  # str output is JSON
    content = ""
    # add content here
    content = json.dumps(content)
    return content
