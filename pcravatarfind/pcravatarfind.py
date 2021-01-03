import random, os, sqlite3, asyncio, operator, re
from PIL import Image

import hoshino
from hoshino import Service, util, log
from hoshino.modules.priconne import chara
from hoshino.typing import MessageSegment, CQEvent

sv = Service('pcravatarfind', bundle='pcr娱乐', help_='''
找头像 | 找出一堆头像中的不同头像
找头像群排行 | 显示找头像小游戏猜对次数的群排行榜(只显示前十名)
'''.strip())

logger = log.new_logger('catguess')

SUB_PIC_SIZE = 128
ROW_NUM = 10
COL_NUM = 10
ONE_TURN_TIME = 40
DB_PATH = os.path.expanduser('~/.hoshino/cat_guess_winning_counter.db')

dir_path = os.path.join(os.path.expanduser(hoshino.config.RES_DIR), 'img', 'priconne', 'unit')
naoquan1_path = os.path.join(dir_path,'icon_unit_100161.png')
naoquan2_path = os.path.join(dir_path,'icon_unit_180131.png')
answer_path = os.path.join(dir_path,'maoquan.png')
maoquan1 = Image.open(naoquan1_path)
maoquan2 = Image.open(naoquan2_path)

def find_avatar(row=ROW_NUM,col=COL_NUM):
    w = col * SUB_PIC_SIZE
    h = row * SUB_PIC_SIZE
    base = Image.new('RGBA', (h, w), (255, 255, 255, 255))
    
    for i in range(row):
        for j in range(col):
            base.paste(maoquan1,(j*SUB_PIC_SIZE,i*SUB_PIC_SIZE))

    x = random.randint(0,9)
    y = random.randint(0,9)
    coordinate = (x+1,y+1)
    box = (x*SUB_PIC_SIZE,y*SUB_PIC_SIZE)
    base.paste(maoquan2,box)
    base.thumbnail((w//2,h//2))
    base.save(answer_path)
    return coordinate,base

class WinnerJudger:
    def __init__(self):
        self.on = False
        self.winner = ''
        self.coordinate = ()
    
    def record_winner(self, uid):
        self.winner = str(uid)
        
    def get_on_off_status(self):
        return self.on
    
    def set_coordinate(self, coordinate):
        self.coordinate = coordinate
    
    def turn_on(self):
        self.on = True
        
    def turn_off(self):
        self.on = False
        self.winner = ''
        self.coordinate = ()


winner_judger = WinnerJudger()


class WinningCounter:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self._create_table()


    def _connect(self):
        return sqlite3.connect(DB_PATH)


    def _create_table(self):
        try:
            self._connect().execute('''CREATE TABLE IF NOT EXISTS WINNINGCOUNTER
                          (UID INT PRIMARY KEY    NOT NULL,
                           COUNT           INT    NOT NULL);''')
        except:
            raise Exception('创建表发生错误')
    
    
    def _record_winning(self, uid):
        try:
            winning_number = self._get_winning_number(uid)
            conn = self._connect()
            conn.execute("INSERT OR REPLACE INTO WINNINGCOUNTER (UID,COUNT) \
                                VALUES (?,?)", (uid, winning_number+1))
            conn.commit()       
        except:
            raise Exception('更新表发生错误')


    def _get_winning_number(self, uid):
        try:
            r = self._connect().execute("SELECT COUNT FROM WINNINGCOUNTER WHERE UID=?",(uid,)).fetchone()        
            return 0 if r is None else r[0]
        except:
            raise Exception('查找表发生错误')


async def get_user_card_dict(bot, group_id):
    mlist = await bot.get_group_member_list(group_id=group_id)
    d = {}
    for m in mlist:
        d[m['user_id']] = m['card'] if m['card']!='' else m['nickname']
    return d


def uid2card(uid, user_card_dict):
    return str(uid) if uid not in user_card_dict.keys() else user_card_dict[uid]


@sv.on_fullmatch(('找头像排行榜', '找头像群排行'))
async def description_find_group_ranking(bot, ev: CQEvent):
    try:
        user_card_dict = await get_user_card_dict(bot, ev.group_id)
        card_winningcount_dict = {}
        winning_counter = WinningCounter()
        for uid in user_card_dict.keys():
            if uid != ev.self_id:
                card_winningcount_dict[user_card_dict[uid]] = winning_counter._get_winning_number(uid)
        group_ranking = sorted(card_winningcount_dict.items(), key = lambda x:x[1], reverse = True)
        msg = '找头像小游戏此群排行为:\n'
        for i in range(min(len(group_ranking), 10)):
            if group_ranking[i][1] != 0:
                msg += f'第{i+1}名: {group_ranking[i][0]}, 猜对次数: {group_ranking[i][1]}次\n'
        await bot.send(ev, msg.strip())
    except Exception as e:
        await bot.send(ev, '错误:\n' + str(e))
   
@sv.on_fullmatch('找头像')
async def avatar_find(bot, ev: CQEvent):
    try:
        if winner_judger.get_on_off_status():
            await bot.send(ev, "此轮游戏还没结束，请勿重复使用指令")
            return
        winner_judger.turn_on()
        coordinate,answer_pic = find_avatar()
        winner_judger.set_coordinate(coordinate)
        answer_pic = MessageSegment.image(util.pic2b64(answer_pic))
        await bot.send(ev, f'请找出不一样的头像坐标?({ONE_TURN_TIME}s后公布答案){answer_pic}')
        await asyncio.sleep(ONE_TURN_TIME)
        if winner_judger.winner != '':
            winner_judger.turn_off()
            return
        winner_judger.turn_off()
        await bot.send(ev, f'正确答案是: {coordinate}\n很遗憾，没有人答对~')
    except Exception as e:
        await bot.send(ev, '错误:\n' + str(e))
        
        
@sv.on_message()
async def on_input_coordinate(bot, ev: CQEvent):
    try:
        if winner_judger.get_on_off_status():
            s = ev.message.extract_plain_text()
            if not re.match(r'^\(\d\,\d\)$',s):
                return
            temp=s.replace('(','').replace(')','')
            answer=tuple([int(i) for i in temp.split(',')])
            coordinate = tuple(winner_judger.coordinate)
            logger.info(answer)
            logger.info(coordinate)
            logger.info(operator.eq(answer,winner_judger.coordinate))
            if operator.eq(answer,winner_judger.coordinate) and winner_judger.winner == '':
                winner_judger.record_winner(ev.user_id)
                winning_counter = WinningCounter()
                winning_counter._record_winning(ev.user_id)
                winning_count = winning_counter._get_winning_number(ev.user_id)
                user_card_dict = await get_user_card_dict(bot, ev.group_id)
                user_card = uid2card(ev.user_id, user_card_dict)
                msg_part = f'{user_card}猜对了，真厉害！TA已经猜对{winning_count}次了~\n(此轮游戏将在时间到后自动结束，请耐心等待)'
                msg =  f'正确坐标是: {winner_judger.coordinate}\n{msg_part}'
                await bot.send(ev, msg)
    except Exception as e:
        await bot.send(ev, '错误:\n' + str(e))