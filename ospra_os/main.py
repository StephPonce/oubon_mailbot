from fastapi import FastAPI

from ospra_os.gmail.routes import router as gmail_router

app = FastAPI(title="OspraOS API", version="0.1")
app.include_router(gmail_router)


@app.get("/debug/routes")
def debug_routes():
    return sorted([r.path for r in app.routes])
