import os, sqlite3

def get_db_path():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"
                                        "yobot/yobot/src/client/yobot_data/yobotdata.db"))
    if not (os.path.isfile(db_path) or os.access(db_path, os.R_OK)):
        return None
    return db_path

#=============本段配置插件版不填,便携版或源码版必填===============
DB_PATH = get_db_path()
if not DB_PATH:
    DB_PATH = ''
    # 例：C:/Hoshino/hoshino/modules/yobot/yobot/src/client/yobot_data/yobotdata.db
    # 注意斜杠方向！！！

#==============================================

def get_game_server(gid:str) -> str:
    '''获取game_server''' 
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f'select game_server from clan_group where group_id={gid}')
    game_server = cur.fetchall()[0][0]
    cur.close()
    conn.close()
    return game_server

def get_boss_hp(gid:str) -> str:
    '''获取boss_health'''
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f'select boss_health from clan_group where group_id={gid}')
    boss_health = cur.fetchall()[0][0]
    cur.close()
    conn.close()
    return boss_health

async def get_user_card_dict(bot, group_id):
    '''获取群名片列表'''
    mlist = await bot.get_group_member_list(group_id=group_id)
    d = {}
    for m in mlist:
        d[m['user_id']] = m['card'] if m['card']!='' else m['nickname']
    return d

def uid2card(uid, user_card_dict):
    '''uid转换名片'''
    return str(uid) if uid not in user_card_dict.keys() else user_card_dict[uid]

class FilterKnife:

    def __init__(self):
        self.filter_knife_data = {}
        self.boss_HP = {}
        self.game_server = {}
        self.damage_ranking = {}
        self._is_get_db = True if get_db_path() else False

    def is_get_db(self):
        return self._is_get_db
    
    def is_filtering(self, gid):
        return gid in self.filter_knife_data

    def is_uid_filtered(self, gid, uid):
        return uid in self.filter_knife_data[gid]

    def get_compensate_time(self,all_damage:int,last_damage:int,gid):
        if self.boss_HP[gid] > all_damage:
            return 0
        compensate_time = (1 - (self.boss_HP[gid]-(all_damage-last_damage)) / last_damage) * 90 + self.game_server[gid]
        return compensate_time

    def start_filter_knife(self,gid):
        self.filter_knife_data[gid] = {}
        if not (gid in self.game_server):
            self.game_server[gid] = 10 if 'cn' == get_game_server(gid) else 20
        self.boss_HP[gid] = get_boss_hp(gid)
        
    def end_filter_knife(self, gid):
        self.filter_knife_data.pop(gid)

    def add_filter_knife_data(self, gid, uid, name, damage):
        self.filter_knife_data[gid][uid] = {}
        self.filter_knife_data[gid][uid]["name"] = name
        self.filter_knife_data[gid][uid]["damage"]  = damage

    def update_filter_knife_data(self, gid, uid, damage):
        self.filter_knife_data[gid][uid]["damage"]  = damage