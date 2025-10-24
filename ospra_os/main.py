from fastapi import FastAPI

from ospra_os.gmail.routes import router as gmail_router

app = FastAPI(title="Ospra OS", version="0.1")
app.include_router(gmail_router)
