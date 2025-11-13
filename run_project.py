import uvicorn

from backend_pre_start import when_ready


if __name__ == "__main__":
    """Запуск проекта для разработки"""

    when_ready("start")
    uvicorn.run(app="main:app", reload=True)
