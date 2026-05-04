import os

API_URL = os.environ["API_URL"]
WORKER_SECRET = os.environ["WORKER_SECRET"]
WORKER_ID = os.environ.get("WORKER_ID", "worker-01")
DOCKER_HOST = os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")
