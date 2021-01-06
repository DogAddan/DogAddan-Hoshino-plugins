import random, os, sqlite3, asyncio, operator, re
from PIL import Image

import hoshino
from hoshino import Service, util, log, R
from hoshino.modules.priconne import chara
from hoshino.typing import MessageSegment, CQEvent

from . import GameMaster

sv = Service('pcravatarfind', bundle='pcr娱乐', help_='''
找头像 | 找出一堆头像中的不同头像
找头像群排行 | 显示找头像小游戏猜对次数的群排行榜(只显示前十名)
'''.strip())

SUB_PIC_SIZE = 128
ROW_NUM = 10
COL_NUM = 10
ONE_TURN_TIME = 40
DB_PATH = os.path.expanduser('~/.hoshino/cat_guess_winning_counter.db')

avatar1 = R.img(f'priconne/unit/icon_unit_100161.png').open()
avatar2 = R.img(f'priconne/unit/icon_unit_180131.png').open()

gm = GameMaster(DB_PATH)

def get_merge_avatar(row=ROW_NUM,col=COL_NUM):
    w = col * SUB_PIC_SIZE
    h = row * SUB_PIC_SIZE
    base = Image.new('RGBA', (h, w), (255, 255, 255, 255))
    
    for i in range(row):
        for j in range(col):
            base.paste(avatar1,(j*SUB_PIC_SIZE,i*SUB_PIC_SIZE))

    x = random.randint(0,9)
    y = random.randint(0,9)
    coordinate = (x+1,y+1)
    base.paste(avatar2,(x*SUB_PIC_SIZE,y*SUB_PIC_SIZE))
    base.thumbnail((w//2,h//2))
    return coordinate,base

@sv.on_fullmatch(("找头像排行", "找头像排名","找头像排行榜", "找头像群排行"))
async def description_find_group_ranking(bot, ev: CQEvent):
    ranking = gm.db.get_ranking(ev.group_id)
    msg = ["【猜头像小游戏排行榜】"]
    for i, item in enumerate(ranking):
        uid, count = item
        m = await bot.get_group_member_info(
            self_id=ev.self_id, group_id=ev.group_id, user_id=uid
        )
        name = m["card"] or m["nickname"] or str(uid)
        msg.append(f"第{i + 1}名：{name} 猜对{count}次")
    await bot.send(ev, "\n".join(msg))
   
@sv.on_fullmatch('找头像')
async def avatar_find(bot, ev: CQEvent):
    if gm.is_playing(ev.group_id):
        await bot.finish(ev, "游戏仍在进行中…")
    with gm.start_game(ev.group_id) as game:
        game.answer,answer_pic = get_merge_avatar()
        answer_pic = MessageSegment.image(util.pic2b64(answer_pic))
        await bot.send(ev, f'请找出不一样的头像坐标?({ONE_TURN_TIME}s后公布答案){answer_pic}')
        await asyncio.sleep(ONE_TURN_TIME)
        if game.winner:
            return
    await bot.send(ev, f'正确答案是: {game.answer}\n很遗憾，没有人答对~')
        
        
@sv.on_message()
async def on_input_coordinate(bot, ev: CQEvent):
    game = gm.get_game(ev.group_id)
    if not game or game.winner:
        return
    #匹配输入，正确内容转换为元组
    s = ev.message.extract_plain_text()
    if not re.match(r'^(?:\(|（)\d+(?:\,|，)\d+(?:\)|）)$',s):
        return
    temp=s.replace('(','').replace(')','').replace('（','').replace('）','').replace('，',',')
    answer=tuple([int(i) for i in temp.split(',')])

    if operator.eq(answer,game.answer):
        game.winner = ev.user_id
        n = game.record()
        msg_part = f'{MessageSegment.at(ev.user_id)}猜对了，真厉害！TA已经猜对{n}次了~\n(此轮游戏将在时间到后自动结束，请耐心等待)'
        msg =  f'正确坐标是: {game.answer}\n{msg_part}'
        await bot.send(ev, msg)