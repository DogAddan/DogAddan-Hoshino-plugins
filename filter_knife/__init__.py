import os, json, sqlite3, copy
import aiohttp

from .filter_knife import get_user_card_dict, uid2card, get_boss_hp
from .filter_knife import FilterKnife
import hoshino
from hoshino import Service
from hoshino.typing import CQEvent

TXT_LEN = 12

sv = Service("筛刀", bundle='pcr筛刀', help_='''
公会战筛刀插件
[开始筛刀]           清空以前的筛刀数据
[筛刀 伤害值 @群友]  把筛刀数据报给机器人，如果手里有多个账号可以用@代报，自己的筛刀不需要@
[筛刀信息]           显示现在的筛刀信息
[结算 编号]          提醒筛刀信息里某人结算出刀，编号是筛刀信息里的编号
[结束筛刀]           清空当前筛刀数据
'''.strip())

fk = FilterKnife()

def center(_txt):
    # 在字符串前后加空格格式化输出
    txt = str(_txt)
    return txt.center(TXT_LEN," ")

def get_filter_knife_info(gid):
    if not fk.is_filtering(gid):
        return "当前没有筛刀信息"

    all_damage = 0
    all_damage_list = []
    for uid in fk.filter_knife_data[gid]:
        all_damage_list.append(fk.filter_knife_data[gid][uid]["damage"])

    for damage in all_damage_list:
        all_damage += damage


    # 排序把列表反向
    all_damage_list.sort()
    all_damage_list.reverse()

    # 拷贝出一份数据来把uid按伤害值从大到小放到test_uid_list
    test_dict = copy.deepcopy(fk.filter_knife_data[gid])
    test_uid_list = []

    for damage in all_damage_list:
        for uid in test_dict.keys():
            if test_dict[uid]["damage"] == damage:
                test_uid_list.append(uid)
                test_dict.pop(uid)
                break

    fk.damage_ranking[gid] = copy.deepcopy(test_uid_list)
    a_damage = 0
    mes = "当前筛刀信息如下：\n"
    mes += f"BOSS生命值：{fk.boss_HP[gid]}   当前筛刀人数 {len(fk.filter_knife_data[gid])}   当前筛刀总伤害 {all_damage}\n"
    mes += f"编号 {center('用户名')}{center('伤害')}{center('击杀补偿时间')}\n"
    for i in range(len(test_uid_list)):
        mes += f"{i+1}.   {center(fk.filter_knife_data[gid][test_uid_list[i]]['name'])}{center(fk.filter_knife_data[gid][test_uid_list[i]]['damage'])}"
        damage = fk.filter_knife_data[gid][test_uid_list[i]]['damage']
        a_damage += damage
        mes += f"{center(fk.get_compensate_time(a_damage,damage,gid))}\n"

    return mes



@sv.on_prefix(["开始筛刀"])
async def _ (bot, ev: CQEvent):
    if not fk.is_get_db():
        await bot.send(ev, f'获取数据库路径失败，请检查配置')
        return
    gid = ev['group_id']
    if fk.is_filtering:
        await bot.send(ev, f'筛刀正在进行')
        return
    fk.start_filter_knife(gid)
    await bot.send(ev, "开始进行筛刀，请配合指挥上报")

@sv.on_prefix(["结束筛刀"])
async def _ (bot, ev: CQEvent):
    gid = ev['group_id']
    if not fk.is_filtering(gid):
        await bot.send(ev, f'筛刀未进行')
        return
    fk.end_filter_knife(gid)
    await bot.send(ev, "结束筛刀，当前数据清空")

@sv.on_prefix("筛刀")
async def _ (bot, ev):
    gid = ev['group_id']
    if not fk.is_filtering(gid):
        await bot.send(ev, f'筛刀未进行')
        return
    damage = ev.message.extract_plain_text().strip()
    if not damage.isdigit() :
        await bot.send(ev, "伤害值不能转换为数字",at_sender=True)
        return

    damage = int(damage)
    uid = ev['user_id']
    name = ev['sender']['card'] if ev['sender']['card'] != '' else ev['sender']['nickname']

    for m in ev['message']:
        if m['type'] == 'at' and m['data']['qq'] != 'all':
        # 检查消息有没有带@信息，有的话uid改为@的QQ号
            uid = m['data']['qq']
            user_card_dict = await get_user_card_dict(bot,ev.group_id)
            user_card = uid2card(int(uid),user_card_dict)
            name = f'{user_card}({name}代)'

    if uid in fk.filter_knife_data[gid]:
        await bot.send(ev, "你已经参加过本次筛刀了\n如果伤害填写错误请使用 [更新筛刀 伤害]", at_sender=True)
        return

    fk.add_filter_knife_data(gid,uid,name,damage)

    await bot.send(ev, "已记录筛刀信息", at_sender=True)
    await bot.send(ev, get_filter_knife_info(gid))

@sv.on_prefix("更新筛刀")
async def _ (bot, ev):
    gid = ev['group_id']
    if not fk.is_filtering(gid):
        await bot.send(ev, f'筛刀未进行')
        return
    damage = ev.message.extract_plain_text().strip()
    if not damage.isdigit() :
        await bot.send(ev, "伤害值不能转换为数字",at_sender=True)
        return

    damage = int(damage)
    uid = ev['user_id']

    for m in ev['message']:
        if m['type'] == 'at' and m['data']['qq'] != 'all':
        # 检查消息有没有带@信息，有的话uid改为@的QQ号
            uid = m['data']['qq']

    if not fk.is_uid_filtered(gid,uid):
        await bot.send(ev, "该成员未进行过筛刀", at_sender=True)
        return
    fk.update_filter_knife_data(gid,uid,damage)
    await bot.send(ev, "已更新筛刀伤害", at_sender=True)
    await bot.send(ev, get_filter_knife_info(gid))


@sv.on_prefix(["筛刀结算","结算筛刀","出来","结算"])
async def _ (bot, ev):
    gid = ev['group_id']
    if not fk.is_filtering(gid):
        await bot.send(ev, f'筛刀未进行')
        return
    gid = ev['group_id']
    number = ev.message.extract_plain_text().strip()
    if not number.isdigit():
        await bot.send(ev, "你需要输入一个正确编号", at_sender=True)

    number = int(number)
    uid = fk.damage_ranking[gid].pop(number-1)
    pop = fk.filter_knife_data[gid].pop(uid)

    await bot.send(ev, f"[CQ:at,qq={uid}] 请结算伤害为 {pop['damage']} 的出刀，游戏结算后尽快报刀")
    await bot.send(ev, get_filter_knife_info(gid))


@sv.on_prefix(["筛刀信息"])
async def _ (bot, ev):
    gid = ev['group_id']
    if not fk.is_filtering(gid):
        await bot.send(ev, f'筛刀未进行')
        return
    fk.boss_HP[gid] = int(get_boss_hp(gid))
    await bot.send(ev, get_filter_knife_info(gid))