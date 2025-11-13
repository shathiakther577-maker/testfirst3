from settings import Config
import backend_pre_start

timeout = 9999
workers = 4
when_ready = backend_pre_start.when_ready
worker_class = "uvicorn.workers.UvicornWorker"
bind = "localhost:9999" if Config.DEVELOPMENT_MODE else "localhost:8000"
