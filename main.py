import asyncio
import glob
import io
import logging
import os

import aiohttp
from aiohttp import web
from tiktokapipy.async_api import AsyncTikTokAPI
from tiktokapipy.models.video import Video

directory = "./videos"


async def save_file(api: AsyncTikTokAPI, url: str, filename: str):
    if not os.path.exists(directory):
        os.makedirs(directory)

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
            with open(os.path.join(directory, filename), "wb") as file:
                file.write(bytes_stream.getbuffer())


async def save_slideshow(video: Video, api: AsyncTikTokAPI):
    vf = (
        '"scale=iw*min(1080/iw\,1920/ih):ih*min(1080/iw\,1920/ih),'
        "pad=1080:1920:(1080-iw)/2:(1920-ih)/2,"
        'format=yuv420p"'
    )

    for index, image_data in enumerate(video.image_post.images):
        url = image_data.image_url.url_list[-1]
        await save_file(api, url, f"{video.id}_{index:02}.jpg")

    await save_file(api, video.music.play_url, f"{video.id}.mp3")

    command = [
        "ffmpeg",
        "-r 2/5",
        f"-i {directory}/{video.id}_%02d.jpg",
        f"-i {directory}/{video.id}.mp3",
        "-r 30",
        f"-vf {vf}",
        "-acodec copy",
        f"-t {len(video.image_post.images) * 2.5}",
        f"{directory}/{video.id}.mp4",
        "-y",
    ]
    ffmpeg_proc = await asyncio.create_subprocess_shell(
        " ".join(command),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await ffmpeg_proc.communicate()
    generated_files = glob.glob(os.path.join(directory, f"{video.id}*"))

    if not os.path.exists(os.path.join(directory, f"{video.id}.mp4")):
        logging.error(stderr.decode("utf-8"))
        for file in generated_files:
            os.remove(file)
        raise Exception("Something went wrong with piecing the slideshow together")


async def save_video(video: Video, api: AsyncTikTokAPI):
    await save_file(api, video.video.download_addr, f"{video.id}.mp4")


async def download_video(video):
    async with AsyncTikTokAPI() as api:
        if video.image_post:
            await save_slideshow(video, api)
        else:
            await save_video(video, api)


async def get_videos_by_hashtag(hashtag):
    async with AsyncTikTokAPI() as api:
        challenge = await api.challenge(hashtag, video_limit=3)
        async for video in challenge.videos:
            await download_video(video)


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

        await get_videos_by_hashtag(hashtag)

        return web.Response(status=200)

    app = web.Application()
    app.add_routes(routes)
    logging.basicConfig(level=logging.DEBUG)
    web.run_app(app, port=8000)
