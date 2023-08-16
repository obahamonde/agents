
from fastapi_llm import *


def create_app():
    app = AgentsAPI()
    app.include_router(Router())
    return app

app = create_app()
ssr = ServerSideRenderer()

@app.get("/")
async def root():
    return await ssr.render_template("index.html", name="World")