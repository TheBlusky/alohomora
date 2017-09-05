import re
import time
import aiohttp_jinja2
import jinja2
from aiohttp import web
import asyncio
import os
from aiohttp_session import get_session, setup, SimpleCookieStorage
from allowed import Allowed

allowed = Allowed("data/db.sqlite")
token = os.environ["ALOHOMORA_TOKEN"] if "ALOHOMORA_TOKEN" in os.environ else "XXX"


async def download_conf(request):
    await check_auth(request)
    response = aiohttp_jinja2.render_template('data/allow.conf', request, {})
    response.headers['Content-Type'] = 'text/plain'
    if 'dl' in request.rel_url.query:
        response.headers['Content-Type'] = 'application/force-download'
    return response


@aiohttp_jinja2.template('templates/login_form.jinja2')
async def login_form(request):
    return {}


async def login_check(request):
    data = await request.post()
    if 'token' in data and data['token'] == token:
        session = await get_session(request)
        session['token'] = data['token']
        return web.HTTPFound('/')
    else:
        return web.HTTPFound('/login-form')

async def check_auth(request):
    session = await get_session(request)
    if 'token' not in session or session['token'] != token:
        raise web.HTTPFound('/login-form')


@aiohttp_jinja2.template('templates/get_allowed.jinja2')
async def get_allowed(request):
    await check_auth(request)
    allowed_list = allowed.get_allowed()
    if "X-Forwarded-For" in request.headers:
        ip = request.headers["X-Forwarded-For"]
    else:
        ip = request.transport.get_extra_info('peername')[0]
    data = {
        "allowed_list": allowed_list,
        "cur_time": int(time.time()),
        "ip": ip
    }
    return data

async def add_allowed(request):
    await check_auth(request)
    data = await request.post()
    ip = data['ip']
    description = data['desc']
    expiration = 0 if data['expiration'] == "0" else int(data['expiration']) + int(time.time())
    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
        return web.HTTPFound('/')
    if not re.match(r"^[a-zA-Z0-9.,\- ]*$", description):
        return web.HTTPFound('/')
    allowed.add_allowed(ip, description, expiration)
    return web.HTTPFound('/')

async def del_allowed(request):
    await check_auth(request)
    allowed_id = int(request.match_info['allowed_id'])
    allowed.del_allowed(allowed_id)
    return web.HTTPFound('/')

async def update_allowed(app):
    try:
        while True:
            allowed.get_allowed()
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        pass

async def start_background_tasks(app):
    app['allowed_updated'] = app.loop.create_task(update_allowed(app))


async def cleanup_background_tasks(app):
    app['allowed_updated'].cancel()
    await app['allowed_updated']


app = web.Application()
aiohttp_jinja2.setup(app,loader=jinja2.FileSystemLoader('./'))
app.router.add_get('/', get_allowed)
app.router.add_post('/add', add_allowed)
app.router.add_get('/login-form', login_form)
app.router.add_get('/allow.conf', download_conf)
app.router.add_post('/login-check', login_check)
app.router.add_get('/del/{allowed_id}', del_allowed)
app.router.add_static('/static', "static")
setup(app, SimpleCookieStorage())
app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)


def main():
    web.run_app(app)

if __name__ == '__main__':
    main()
