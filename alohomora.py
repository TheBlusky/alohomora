import base64
import re
import time
from asyncio import sleep
from datetime import timedelta
import aiohttp_jinja2
import jinja2
from aiohttp import web
import asyncio
import os
from aiohttp_session import get_session, setup, SimpleCookieStorage
from humanize import naturaldelta
import uuid

from allowed import Allowed
from logger import log

allowed = Allowed(
    "data/data.yml",
    "data/ip-list.yml",
)
token = os.environ.get("ALOHOMORA_TOKEN", str(uuid.uuid4()))
log(f"Starting server with token: {token}")


@aiohttp_jinja2.template("templates/login_form.jinja2")
async def login_form(request):
    return {}


async def login_check(request):
    data = await request.post()
    if "token" in data and data["token"] == token:
        session = await get_session(request)
        session["token"] = data["token"]
        return web.HTTPFound("/")
    else:
        return web.HTTPFound("/login-form")


async def check_auth(request):
    session = await get_session(request)
    if "token" in session and session["token"] == token:
        return True
    if auth := request.headers.get("Authorization", None):
        auth_decoded = base64.b64decode(auth.split(" ")[-1].encode()).decode()
        auth_token = auth_decoded.split(":")[-1]
        if auth_token == token:
            return True
    raise web.HTTPFound("/login-form")


@aiohttp_jinja2.template("templates/get_allowed.jinja2")
async def get_allowed(request):
    await check_auth(request)
    allowed_list = allowed.get_allowed()
    if "X-Forwarded-For" in request.headers:
        ip = request.headers["X-Forwarded-For"]
    else:
        ip = request.transport.get_extra_info("peername")[0]
    now = int(time.time())
    data = {
        "already_allowed": ip in allowed_list.keys(),
        "allowed_list": [
            {
                "ip": ip,
                "human_expiration": naturaldelta(
                    timedelta(seconds=allowed_elem["expiration"] - now)
                ),
                **allowed_elem,
            }
            for ip, allowed_elem in allowed_list.items()
        ],
        "ip": ip,
    }
    return data


async def add_allowed(request):
    await check_auth(request)
    data = await request.post()
    ip = data["ip"]
    description = data["desc"]
    expiration = (
        0 if data["expiration"] == "0" else int(data["expiration"]) + int(time.time())
    )
    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
        return web.HTTPFound("/")
    if not re.match(r"^[a-zA-Z0-9.,\- ]*$", description):
        return web.HTTPFound("/")
    allowed.add_allowed(ip, description, expiration)
    return web.HTTPFound("/")


async def auto_add_allowed(request):
    await check_auth(request)
    allowed_list = allowed.get_allowed()
    if "X-Forwarded-For" in request.headers:
        ip = request.headers["X-Forwarded-For"]
    else:
        ip = request.transport.get_extra_info("peername")[0]
    expiration = int(time.time()) + 3600
    if ip in allowed_list:
        allowed_expiration = allowed_list[ip]["expiration"]
        if allowed_expiration > 0 and allowed_expiration > expiration:
            return web.HTTPOk()
    allowed.add_allowed(ip, "Auto added element", expiration)
    return web.HTTPOk()


async def del_allowed(request):
    await check_auth(request)
    allowed_id = request.match_info["allowed_id"]
    allowed.del_allowed(allowed_id)
    return web.HTTPFound("/")


async def update_allowed():
    try:
        await sleep(5)
        while True:
            while await allowed.wait_for_expiration():
                pass
            allowed.get_allowed()
    except asyncio.CancelledError:
        pass


async def start_background_tasks(app):
    app["allowed_updated"] = asyncio.create_task(update_allowed())


async def cleanup_background_tasks(app):
    app["allowed_updated"].cancel()
    await app["allowed_updated"]


app = web.Application()
aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader("./"))
app.router.add_get("/", get_allowed)
app.router.add_post("/add", add_allowed)
app.router.add_post("/auto-add", auto_add_allowed)
app.router.add_get("/login-form", login_form)
app.router.add_post("/login-check", login_check)
app.router.add_get("/del/{allowed_id}", del_allowed)
app.router.add_static("/static", "static")
setup(app, SimpleCookieStorage())
app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)


def main():
    web.run_app(app)


if __name__ == "__main__":
    main()
