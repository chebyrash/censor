import asyncio
import concurrent.futures
import json
import logging
import subprocess

import aiohttp
import cachetools
import magic
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
    return True if score >= threshold else False


def get_frames(file: bytes) -> list:
    process = subprocess.Popen(
        ["ffmpeg",
         "-loglevel", "panic",
         "-i", "pipe:",
         "-vf", "fps=1/4",
         "-f", "image2pipe",
         "-vcodec", "mjpeg",
         "pipe:"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    frames = process.communicate(input=file)[0].split(b"\xff\xd9")

    return [x + b"\xff\xd9" for x in frames[:len(frames) - 1]]


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

    @staticmethod
    async def get_file(url: str, headers: dict, cookies: dict) -> bytes:
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
            async with session.get(url=url, headers=headers) as response:
                return await response.read()

    @staticmethod
    def get_file_type(file: bytes) -> str:
        return magic.from_buffer(buffer=file, mime=True).split("/")[1]

    @staticmethod
    def verify_file_type_support(file_type: str) -> str:
        return {
            "webm": "video",
            "mp4": "video",
            "png": "image",
            "jpeg": "image"
        }.get(file_type, None)

    @staticmethod
    async def get_video_frames(file: bytes) -> list:
        return await asyncio.get_event_loop().run_in_executor(
            pool,
            get_frames,
            file
        )

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

        url = body.get("url", None)
        # Backwards compatibility support, REMOVE when client migrates
        image = body.get("image", None)
        url = url if url else image

        if not url:
            return web.json_response({"error": "Missing URL"}, status=400)

        if url in self._cache:
            body["censor"] = self._cache[url]
            return web.json_response(body)

        try:
            file = await self.get_file(
                url=url,
                headers=body.get("headers", {}),
                cookies=body.get("cookies", {})
            )
        except Exception as e:
            self._log(e)
            return web.json_response({"error": "Image Download Failed"}, status=400)

        file_type = self.get_file_type(file)
        file_type = self.verify_file_type_support(file_type)
        if not file_type:
            return web.json_response({"error": "File Format Not Supported"}, status=400)

        if file_type == "image":
            try:
                body["censor"] = self._cache[url] = await self.is_censored(file)
            except Exception as e:
                self._log(e)
                return web.json_response({"error": "Corrupt Image"}, status=400)

        elif file_type == "video":
            frames = await self.get_video_frames(file)

            censor = True
            for frame in frames:
                try:
                    censor = await self.is_censored(frame)
                except Exception as e:
                    self._log(e)
                    return web.json_response({"error": "Corrupt Video"}, status=400)

                if censor:
                    break

            body["censor"] = self._cache[url] = censor

        return web.json_response(body)


if __name__ == "__main__":
    Server().run()
