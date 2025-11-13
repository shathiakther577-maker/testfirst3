import os
import uuid

from jinja2 import Template
from pyppeteer import launch


class Painter:

    @classmethod
    async def draw_image(
        cls,
        *,
        width: int,  # Ширина изображения
        height: int,  # Высота изображения
        template_path: str,  # Путь до html шаблона
        jinja_args: dict | None = None  # параметры для jinja
    ) -> str:
        """Конвертирует шаблон html в img и возвращает путь до изображения"""

        html_path = cls._render_page(template_path, jinja_args or {})
        image_path = await cls._screenshot_image(width, height, html_path)
        os.remove(html_path)

        return image_path


    @classmethod
    def _render_page(cls, template_path: str, jinja_args: dict) -> str:
        """Подставляет значения в html шаблон и возвращает путь до шаблона"""

        template = Template(open(template_path).read())
        html_str = template.render(**jinja_args)

        directory, _ = os.path.split(template_path)
        filename = f"{uuid.uuid4()}.html"
        html_path = os.path.join(directory, filename)

        with open(html_path, "w") as file:
            file.write(html_str)

        return html_path


    @classmethod
    async def _screenshot_image(cls, width: int, height: int, html_path: str) -> str:
        """Делает скриншот html страницы и возвращает путь до изображения"""

        img_path = f"{html_path.removesuffix('.html')}.png"
        browser = await launch(
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False,
            options={
                "args": ["--no-sandbox"],
                "defaultViewport": {"width": width, "height": height, "isLandscape": True}
            }
        )
        page = await browser.newPage()

        await page.goto(f"file://{html_path}", {"waitUntil": "networkidle0"})
        await page.screenshot({"path": img_path})
        await browser.close()

        return img_path
