import asyncio
import json
import logging
from io import BytesIO

import PIL.Image as Image
import aiohttp
import uvloop
from aiohttp import web
from nsfw import classify

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(lineno)d %(message)s")


class Server(object):
    def __init__(self):
        with open("config.json") as fd:
            self._config: dict = json.loads(fd.read())

        self._client: aiohttp.ClientSession = None
        self._cache: dict = {}

        self._app: web.Application = web.Application()
        self._app.on_startup.append(self.on_startup)
        self._app.add_routes([web.post("/", self.index)])

    @staticmethod
    def _log(message: str):
        logging.info("[SERVER] {0}".format(message))

    def run(self):
        self._log("STARTING")

        web.run_app(
            self._app,
            host=self._config["server"]["host"],
            port=self._config["server"]["port"],
        )

    async def on_startup(self, app):
        self._client = aiohttp.ClientSession()

    async def index(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.Response(text=json.dumps({"error": "Bad JSON"}), status=400)

        image = body.get("image", None)
        if not image:
            return web.Response(text=json.dumps({"error": "Missing Image"}), status=400)

        if image in self._cache:
            body["censor"] = self._cache[image]
        else:
            try:
                async with self._client.get(url=image) as response:
                    file = BytesIO(await response.read())
                score = classify(Image.open(file))[1]
                body["censor"] = self._cache[image] = True if score > self._config["nsfw"]["threshold"] else False
            except Exception:
                return web.Response(text=json.dumps({"error": "Corrupt Image"}), status=400)

        return web.Response(text=json.dumps(body))


if __name__ == "__main__":
    Server().run()
