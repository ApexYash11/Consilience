from fastapi import FastAPI
from database.connection import _engine
from database.connection import init_db
from fastapi.middleware.cors import CORSMiddleware
import asyncio

app = FastAPI(
    title="Consilience API",
    description="Multi-agent research orchestration platform",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# instantiate the database
@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup."""
    print("Consilience API initializing...")
    await asyncio.to_thread(init_db)
    print("Database initialized and connected.")

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Consilience API",
        "documentation": "/docs"
    }

@app.get("/startup")
def startup():
    init_db()
    return {"status": "database initialized"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

