from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from execution_engine.executor import run_function_docker  # and optionally run_function_gvisor

app = FastAPI()

class FunctionRequest(BaseModel):
    code: str

@app.post("/run-function")
def run_function(req: FunctionRequest, runtime: str = "docker"):
    try:
        if runtime == "gvisor":
            # Not yet implemented (optional)
            # output = run_function_gvisor(req.code)
            raise HTTPException(status_code=501, detail="gVisor not supported on this platform")
        else:
            output = run_function_docker(req.code)

        return output

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
