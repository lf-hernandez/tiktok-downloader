import io
import logging
import os

import aiohttp
from aiohttp import web
from tiktokapipy.async_api import AsyncTikTokAPI
from tiktokapipy.models.video import Video

directory = "./videos"


async def get_tiktok_bytes_stream(api: AsyncTikTokAPI, url: str):
    async with aiohttp.ClientSession(
        cookies={
            cookie["name"]: cookie["value"]
            for cookie in await api.context.cookies()
            if cookie["name"] == "tt_chain_token"
        }
    ) as session:
        async with session.get(
            url, headers={"referer": "https://www.tiktok.com/"}
        ) as response:
            binary_response = await response.read()
            bytes_stream = io.BytesIO(binary_response)
            return bytes_stream


async def save_file(bytes_stream: io.BytesIO, filename: str):
    if not os.path.exists(directory):
        os.makedirs(directory)

    with open(os.path.join(directory, filename), "wb") as file:
        file.write(bytes_stream.getbuffer())


async def save_video(video: Video, api: AsyncTikTokAPI):
    video_bytes_stream = await get_tiktok_bytes_stream(
        api, url=video.video.download_addr
    )
    save_file(video_bytes_stream, filename=f"{video.id}.mp4")


async def download_video(video):
    async with AsyncTikTokAPI() as api:
        if video.image_post:
            return
        else:
            await save_video(video, api)


async def download_videos(videos):
    async for video in videos:
        await download_video(video)


async def get_videos_by_hashtag(hashtag):
    async with AsyncTikTokAPI() as api:
        challenge = await api.challenge(hashtag, video_limit=3)
        return challenge.videos


if __name__ == "__main__":
    routes = web.RouteTableDef()

    @routes.get("/")
    async def get_handler(request):
        return web.Response(status=200, text="Web server is up and running!")

    @routes.post("/download")
    async def post_handler(request):
        params = request.query
        hashtag = params.get("hashtag")
        if not hashtag:
            return web.HTTPError()

        videos = await get_videos_by_hashtag(hashtag)
        download_videos(videos)

        return web.Response(status=200)

    app = web.Application()
    app.add_routes(routes)
    logging.basicConfig(level=logging.DEBUG)
    web.run_app(app, port=8000)
