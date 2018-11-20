import asyncio
import concurrent.futures
import json
import logging
from io import BytesIO

import PIL.Image as Image
import aiohttp
import cachetools
import uvloop
from aiohttp import web
from nsfw import classify

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(lineno)d %(message)s")

pool = concurrent.futures.ProcessPoolExecutor()


def is_censored(file: BytesIO, threshold: float) -> bool:
    return True if classify(Image.open(file))[1] > threshold else False


class Server(object):
    def __init__(self):
        with open("config.json") as fd:
            self._config = json.loads(fd.read())

        self._cache = cachetools.ttl.TTLCache(
            maxsize=self._config["cache"]["max_size"],
            ttl=self._config["cache"]["TTL"]
        )

        self._app = web.Application()
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
                async with aiohttp.ClientSession() as session:
                    async with session.get(url=image) as response:
                        file = BytesIO(await response.read())

            except:
                return web.Response(text=json.dumps({"error": "Image Download Failed"}), status=400)

            try:
                censor = await asyncio.get_event_loop().run_in_executor(
                    pool,
                    is_censored,
                    file,
                    self._config["nsfw"]["threshold"]
                )
                body["censor"] = self._cache[image] = censor

            except:
                return web.Response(text=json.dumps({"error": "Corrupt Image"}), status=400)

        return web.Response(text=json.dumps(body))


if __name__ == "__main__":
    Server().run()
