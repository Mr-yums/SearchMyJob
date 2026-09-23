import uvicorn

from searchmyjob.api.app import create_app
from searchmyjob.config import PORT

if __name__ == "__main__":
    uvicorn.run(create_app(), host="127.0.0.1", port=PORT, access_log=False)
