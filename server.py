from fastapi import FastAPI
from routes import macro

app = FastAPI()

# Include the routers from your other files
app.include_router(macro.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the API!"}