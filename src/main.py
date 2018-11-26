import asyncio
import concurrent.futures
import json
import logging

import aiohttp
import cachetools
import uvloop
from aiohttp import web
from nsfw import caffe_preprocess_and_compute, load_model

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
pool = concurrent.futures.ProcessPoolExecutor()
net, transformer = load_model()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(lineno)d %(message)s"
)


def compute(file: bytes, threshold: float) -> bool:
    score = caffe_preprocess_and_compute(
        file,
        caffe_transformer=transformer,
        caffe_net=net,
        output_layers=["prob"]
    )[1]
    return True if score > threshold else False


class Server(object):
    def __init__(self):
        with open("config.json") as fd:
            self._config = json.loads(fd.read())

        self._cache = None

        self._app = web.Application()
        self._app.on_startup.append(self.on_startup)
        self._app.add_routes([web.post("/", self.index)])

    @staticmethod
    def _log(message: object):
        logging.info("[SERVER] {0}".format(message))

    def run(self):
        self._log("STARTING")

        web.run_app(
            self._app,
            host=self._config["server"]["host"],
            port=self._config["server"]["port"],
        )

    async def on_startup(self, app):
        self._cache = cachetools.LRUCache(
            maxsize=self._config["cache"]["max_size"]
        )

    async def get_image(self, image: str, headers: dict, cookies: dict) -> bytes:
        async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(
                    ssl=False,
                    enable_cleanup_closed=True
                ),
                connector_owner=True,
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=10),
                raise_for_status=True
        ) as session:
            async with session.get(url=image, headers=headers) as response:
                return await response.read()

    async def is_censored(self, file: bytes) -> bool:
        return await asyncio.get_event_loop().run_in_executor(
            pool,
            compute,
            file,
            self._config["nsfw"]["threshold"]
        )

    async def index(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Bad JSON"}, status=400)

        image = body.get("image", None)
        if not image:
            return web.json_response({"error": "Missing Image"}, status=400)

        if image in self._cache:
            body["censor"] = self._cache[image]

        else:
            try:
                file = await self.get_image(image, body.get("headers", {}), body.get("cookies", {}))

            except Exception as e:
                self._log(e)
                return web.json_response({"error": "Image Download Failed"}, status=400)

            try:
                body["censor"] = self._cache[image] = await self.is_censored(file)

            except Exception as e:
                self._log(e)
                return web.json_response({"error": "Corrupt Image"}, status=400)

        return web.json_response(body)


if __name__ == "__main__":
    Server().run()
