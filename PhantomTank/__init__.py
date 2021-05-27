import aiohttp, re, base64
from io import BytesIO
from PIL import Image

from hoshino import Service
from hoshino.typing import CQEvent, MessageSegment
from hoshino.util import DailyNumberLimiter
from aiocqhttp.event import Event
from typing import List

from .utils import make_tank, colorful_tank

lmt = DailyNumberLimiter(10)

sv = Service('PhantomTank', help_='[幻影|彩色幻影][图片][图片]')

def extract_url_from_event(event: Event) -> List[str]:
    urls = re.findall(r'http.*?term=\d', str(event.message))
    return urls

async def tank(bot, ev:CQEvent, type):
    url = extract_url_from_event(ev)
    if not url:
        await bot.finish(ev, '请附带图片!')
    if len(url) != 2:
        await bot.finish(ev, '图片数量不符!')
    print(url)
    await bot.send(ev, '请稍等片刻~')
    imgs = []
    try:
        for i in range(len(url)):
            async with  aiohttp.ClientSession() as session:
                async with session.get(url[i]) as resp:
                    cont = await resp.read()
                    imgs.append(Image.open(BytesIO(cont)))

        img_tank = await make_tank(imgs[0], imgs[1]) if type == 1 else await colorful_tank(imgs[0], imgs[1])
        img_msg = MessageSegment.image('base64://' + base64.b64encode(img_tank).decode())
        await bot.send(ev, img_msg)
    except:
        await bot.send(ev, '生成失败……')

@sv.on_prefix(('幻影'))
async def gen_5000_pic(bot, ev: CQEvent):
    await tank(bot, ev, 1)

@sv.on_prefix(('彩色幻影'))
async def gen_5000_pic(bot, ev: CQEvent):
    await tank(bot, ev, 2)