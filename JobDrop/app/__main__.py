import uvicorn

from . import app

if __name__ == "__main__":
    # Port 8001 so it does not collide with the JobSpy jobs_api on 8000.
    uvicorn.run(app, host="0.0.0.0", port=8001)