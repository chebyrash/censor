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


def is_censored(file: bytes, threshold: float) -> bool:
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

        self._client = None
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
        self._client = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                verify_ssl=False,
                enable_cleanup_closed=True
            ),
            connector_owner=False,
            timeout=aiohttp.ClientTimeout(total=10)
        )
        self._cache = cachetools.LRUCache(
            maxsize=self._config["cache"]["max_size"]
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
                async with self._client.get(url=image) as response:
                    file = await response.read()

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
