from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
import app.models  # Ensures all models are registered with Base.metadata
from app.routers import auth, users, students, groups, sessions, exams, finance, backup, distribution
from app.config import logger

# Initialize database schema
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TeacherSystem API",
    description="Professional Commercial Management System for Egyptian High-School Teachers",
    version="1.0.0"
)

# Static Files & Frontend Configuration
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serves the primary Arabic RTL frontend application entry point."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Frontend application assets not found."}
    )

# CORS configuration for Local Area Network & Localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
    ],
    allow_origin_regex=r"^http:\/\/(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler to prevent leakage of internal stack traces or secrets
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error processing {request.method} {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact system administrator."}
    )

# Include Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(students.router)
app.include_router(groups.router)
app.include_router(sessions.router)
app.include_router(exams.router)
app.include_router(finance.router)
app.include_router(backup.router)
app.include_router(distribution.router)

@app.get("/api/health", tags=["Health"])
def health_check():
    """Health check endpoint to verify system status and local server availability."""
    return {
        "status": "healthy",
        "system": "TeacherSystem",
        "version": "1.0.0"
    }
