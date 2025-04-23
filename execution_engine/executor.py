import docker
import os
import shutil
import uuid
import time
from execution_engine.metrices_logger import log_metrics  # <-- Metrics logger

client = docker.from_env()

def run_function_docker(user_code: str, timeout_seconds: int = 5) -> dict:
    build_id = str(uuid.uuid4())
    build_dir = f"./temp/{build_id}"
    os.makedirs(build_dir, exist_ok=True)

    handler_path = os.path.join(build_dir, "handler.py")
    with open(handler_path, "w") as f:
        f.write(user_code)

    dockerfile_src = "docker/python-runner/Dockerfile"
    dockerfile_dest = os.path.join(build_dir, "Dockerfile")
    shutil.copy(dockerfile_src, dockerfile_dest)

    image_tag = f"user-func-{build_id}"

    success = False
    start_time = time.time()

    try:
        print(f"🔧 Building Docker image: {image_tag}")
        client.images.build(path=build_dir, tag=image_tag)

        print(f"🚀 Running container...")
        container = client.containers.run(
            image=image_tag,
            detach=True,
            remove=True,
            mem_limit="128m",
            network_disabled=True
        )
        container.wait(timeout=timeout_seconds)
        logs = container.logs().decode("utf-8")
        success = True

    except docker.errors.BuildError as e:
        logs = f"❌ Docker build failed: {str(e)}"
    except docker.errors.APIError as e:
        logs = f"❌ Container error: {str(e)}"
    except Exception as e:
        logs = f"❌ Execution failed or timed out: {str(e)}"
    finally:
        duration = time.time() - start_time
        log_metrics(runtime="docker", success=success, duration=duration)
        shutil.rmtree(build_dir, ignore_errors=True)

    return {
        "status": "success" if success else "error",
        "output": logs,
        "runtime": "docker"
    }
