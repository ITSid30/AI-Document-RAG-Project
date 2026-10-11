from fastapi import FastAPI
from app.api.routes import router
from app.db.session import engine, Base
from app.models import document

app = FastAPI()
app.include_router(router)

Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"status": "alive"}