# -*- coding: utf-8 -*-
# 小六壬 · 排盘逻辑（江氏 / 道传）
#
# 两派起课不同：
#   江氏：日时起课。大安起初一顺数至农历日 → 日宫；日宫起子时顺数至时辰 → 时宫（身宫）。
#         再以时辰地支为准「隔位」顺排地支，装六亲、六神、五星，并取自身六亲。
#   道传：月日时起课。大安起正月 → 月宫（天）；月宫起初一 → 日宫（地）；
#         日宫起子时 → 时宫（人）。只立三宫，断三宫生克与体用。
#
# 六宫永远按「大安→留连→速喜→赤口→小吉→空亡」顺时针循环。
#
# 起课方式两派各二：
#   时间起课 —— 江氏日时、道传月日时，如上。
#   数字起课 —— 江氏报一数代「日」，除六取余定日宫，余 0 作 6（空亡）；
#               道传报三数代月、日、时，连续起算定三宫。
#               两派的「时辰」仍是真实起课时刻：江氏据此定地支、六亲、
#               六神与五星所依的日宫之后诸宫，道传据以定体用之「用」。

import sxtwl
from datetime import timedelta

from .data import (
    PALACES, SHENS, STARS, ZHI, WX_ZHI,
    WX_PALACE_JIANG, WX_PALACE_DAO, SHEN_DAO,
    TIYONG,
)

SHENG = {'木': '火', '火': '土', '土': '金', '金': '水', '水': '木'}
KE = {'木': '土', '土': '水', '水': '火', '火': '金', '金': '木'}

SCHOOLS = {'jiang': '江氏', 'dao': '道传'}

# 起课方式。两派都支持「时间起课」；数字起课两派定法不同：
#   江氏 —— 只报一数，以数代「日」定日宫，再以真实时辰起时宫
#           （江春义《小六壬起课起卦装卦方法大全》：不论多少，除以六用余数
#           从大安起课，然后再起时辰）。
#   道传 —— 报三数，分代「月、日、时」定三才三宫；但体用的「用」仍取
#           起课的真实时辰（《道传小六壬排盘方法》明言「以时落宫为体，
#           起课时辰为用」，三数起课亦同）。
METHODS = {
    'jiang': {'time': '日时起课', 'number': '数字起课'},
    'dao': {'time': '月日时起课', 'number': '数字起课'},
}
# 数字起课所需报数个数
NUM_COUNT = {'jiang': 1, 'dao': 3}

SOIL = ('辰', '戌', '丑', '未')
FOUR_CARDINAL = ('子', '午', '卯', '酉')   # 子午卯酉
FOUR_GROWTH = ('寅', '申', '巳', '亥')     # 寅申巳亥

TIANGAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']


def liuqin_of(self_wx, other_wx):
    """以「我」的五行论他宫六亲。同我者兄弟、生我者父母、我生者子孙、我克者妻财、克我者官鬼。"""
    if self_wx == other_wx:
        return '兄弟'
    if SHENG[self_wx] == other_wx:
        return '子孙'
    if KE[self_wx] == other_wx:
        return '妻财'
    if KE[other_wx] == self_wx:
        return '官鬼'
    return '父母'


def shichen_index(dt):
    """时辰地支序号：子=0。23:00 起即为子时。"""
    return ((dt.hour + 1) // 2) % 12


def effective_dt(dt):
    """子时（23:00 后）属次日：换日再取农历。"""
    return dt + timedelta(days=1) if dt.hour >= 23 else dt


def lunar_of(dt):
    """取农历月、日与闰月标记。"""
    day_obj = sxtwl.fromSolar(dt.year, dt.month, dt.day)
    return (
        day_obj.getLunarMonth(),
        day_obj.getLunarDay(),
        bool(day_obj.isLunarLeap()),
        day_obj,
    )


def _ganzhi(day_obj):
    y = day_obj.getYearGZ(True)
    m = day_obj.getMonthGZ()
    d = day_obj.getDayGZ()
    return (
        TIANGAN[y.tg] + ZHI[y.dz],
        TIANGAN[m.tg] + ZHI[m.dz],
        TIANGAN[d.tg] + ZHI[d.dz],
    )


def build_jiang(lunar_day, h, day_pal=None):
    """江氏小六壬排盘。h 为时辰地支序号（子=0）。

    传入 day_pal 时以之代日宫（数字起课：报数除六取余，自大安起数定宫）。
    时宫仍自日宫起子时数至真实时辰，故地支、六亲、六神、五星皆不受影响。
    """
    # 1. 定日宫：大安起初一（数字起课则由报数定宫）
    if day_pal is None:
        day_pal = (lunar_day - 1) % 6
    # 2. 定时宫（身宫）：日宫起子时
    hour_pal = (day_pal + h) % 6
    body_zhi = ZHI[h]
    body_wx = WX_ZHI[body_zhi]

    # 3. 隔位排地支：以时宫地支为基准，每隔一位（+2）顺布一宫。
    #    六宫与十二支各差两位，故六宫恰得与时辰同奇偶的六个地支。
    zhis = []
    for g in range(6):
        off = (g - hour_pal) % 6
        zhis.append(ZHI[(h + 2 * off) % 12])

    # 4. 装六亲。隔位排后，除土外不会有同五行之支，故「兄弟」另有取法：
    #    子午卯酉为身取第三宫、寅申巳亥为身取第二宫、辰戌丑未为身则土土同类自明。
    #    （其理据是地支藏干与身支同类者，见江阳君教程第十一篇汇总表。）
    brother_pal = None
    if body_zhi not in SOIL:
        offset = 2 if body_zhi in FOUR_CARDINAL else 1
        brother_pal = (hour_pal + offset) % 6

    gong = []
    for g in range(6):
        zhi = zhis[g]
        wx = WX_ZHI[zhi]
        if g == hour_pal:
            liuqin = '自身'
        elif brother_pal is not None and g == brother_pal:
            liuqin = '兄弟'
        else:
            liuqin = liuqin_of(body_wx, wx)
        gong.append({
            'index': g,
            'name': PALACES[g],
            'zhi': zhi,
            'zhi_wx': wx,
            'palace_wx': WX_PALACE_JIANG[PALACES[g]],
            'liuqin': liuqin,
            # 5. 六神：青龙宫 = 时辰地支序号 % 6（即「子午大安、丑未留连……
            #    巳亥空亡起青龙」的归并），再依 青龙→朱雀→勾陈→白虎→玄武→腾蛇 顺排
            'shen': SHENS[(g - h % 6) % 6],
            # 6. 五星：自日宫顺起 木、火、土、金、水、天空
            'star': STARS[(g - day_pal) % 6],
            'is_day': g == day_pal,
            'is_hour': g == hour_pal,
        })

    # 7. 自身六亲：身支五行 与 身宫（时宫）宫位五行 论生克
    body_liuqin = liuqin_of(body_wx, WX_PALACE_JIANG[PALACES[hour_pal]])

    return {
        'school': 'jiang',
        'school_label': '江氏',
        'day_palace': PALACES[day_pal],
        'day_palace_wx': WX_PALACE_JIANG[PALACES[day_pal]],
        'hour_palace': PALACES[hour_pal],
        'hour_palace_wx': WX_PALACE_JIANG[PALACES[hour_pal]],
        'body_zhi': body_zhi,
        'body_wx': body_wx,
        'body_liuqin': body_liuqin,
        'gong': gong,
        'brother_palace': PALACES[brother_pal] if brother_pal is not None else None,
    }


def _chain_text(from_label, from_wx, to_label, to_wx):
    """三宫之间的关系，明确谁生谁、谁克谁，避免箭头歧义。"""
    if from_wx == to_wx:
        return f'{from_label}{from_wx}与{to_label}{to_wx}同气'
    if SHENG[from_wx] == to_wx:
        return f'{from_label}{from_wx}生{to_label}{to_wx}'
    if KE[from_wx] == to_wx:
        return f'{from_label}{from_wx}克{to_label}{to_wx}'
    if SHENG[to_wx] == from_wx:
        return f'{to_label}{to_wx}生{from_label}{from_wx}'
    return f'{to_label}{to_wx}克{from_label}{from_wx}'


def build_dao(lunar_month, lunar_day, h, pals=None):
    """道传小六壬排盘。三宫：月为天、日为地、时为人的三才。

    pals 为 (月宫, 日宫, 时宫) 序号，供数字起课（报三数）直接指定；
    缺省则依农历月、日、时顺数。体用的「用」始终取真实起课时辰。
    """
    month_pal, day_pal, hour_pal = pals if pals else (
        (lunar_month - 1) % 6,
        None,
        None,
    )
    if day_pal is None:
        day_pal = (month_pal + lunar_day - 1) % 6
    if hour_pal is None:
        hour_pal = (day_pal + h) % 6

    def cell(idx):
        name = PALACES[idx]
        return {
            'index': idx,
            'name': name,
            'wx': WX_PALACE_DAO[name],
            'shen': SHEN_DAO[name],
        }

    g3 = [
        dict(cell(month_pal), role='天', label='月宫', hint='起因、大环境'),
        dict(cell(day_pal), role='地', label='日宫', hint='过程、中间'),
        dict(cell(hour_pal), role='人', label='时宫', hint='结果、自身'),
    ]

    # 体用：落宫为体，时辰为用（《明卦篇》）
    ti_wx = WX_PALACE_DAO[PALACES[hour_pal]]
    yong_wx = WX_ZHI[ZHI[h]]
    if ti_wx == yong_wx:
        rel = '比和'
    elif KE[yong_wx] == ti_wx:
        rel = '用克体'
    elif SHENG[ti_wx] == yong_wx:
        rel = '体生用'
    elif SHENG[yong_wx] == ti_wx:
        rel = '用生体'
    else:
        rel = '体克用'
    level, note = TIYONG[rel]

    chain = [
        {
            'from': '月宫', 'to': '日宫',
            'text': _chain_text('月宫', g3[0]['wx'], '日宫', g3[1]['wx']),
        },
        {
            'from': '日宫', 'to': '时宫',
            'text': _chain_text('日宫', g3[1]['wx'], '时宫', g3[2]['wx']),
        },
    ]

    return {
        'school': 'dao',
        'school_label': '道传',
        'gong3': g3,
        'ti': {'name': PALACES[hour_pal], 'wx': ti_wx},
        'yong': {'zhi': ZHI[h], 'wx': yong_wx},
        'tiyong': {'rel': rel, 'level': level, 'note': note},
        'chain': chain,
    }


def _number_note_jiang(n, day_pal):
    """江氏数字起课：说明余数与落宫。余 0 作 6（空亡）。"""
    r = n % 6 or 6
    return f"报数 {n}，除 6 余 {r}，自大安起数至 {r} 落「{PALACES[day_pal]}」为日宫"


def calculate(school, dt, method='time', numbers=None):
    """按流派与起课方式起课。返回可直接渲染的字典。

    method='time'   时间起课（江氏日时 / 道传月日时）。
    method='number' 数字起课（江氏一数代日 / 道传三数代月日时）。
    """
    school = school if school in SCHOOLS else 'jiang'
    if method not in ('time', 'number'):
        method = 'time'
    numbers = [int(x) for x in (numbers or [])]

    if method == 'number':
        need = NUM_COUNT[school]
        if len(numbers) < need:
            raise ValueError(f"数字起课需报 {need} 个数")
        if any(n < 1 for n in numbers):
            raise ValueError("报数须为正整数")
        numbers = numbers[:need]
    else:
        numbers = []

    eff = effective_dt(dt)
    lunar_month, lunar_day, is_leap, day_obj = lunar_of(eff)
    year_gz, month_gz, day_gz = _ganzhi(day_obj)
    h = shichen_index(dt)

    result = {
        'school': school,
        'school_label': SCHOOLS[school],
        'method': method,
        'method_label': METHODS[school][method],
        'numbers': numbers,
        'datetime_str': dt.strftime('%Y-%m-%d %H:%M'),
        'lunar_str': f"{'闰' if is_leap else ''}{lunar_month}月{lunar_day}日",
        'lunar_month': lunar_month,
        'lunar_day': lunar_day,
        'is_leap': is_leap,
        'shichen': ZHI[h] + '时',
        'shichen_index': h,
        # 只是背景信息，两派起课本身不用年柱
        'year_gz': year_gz,
        'month_gz': month_gz,
        'day_gz': day_gz,
        'rolled': dt.hour >= 23,
    }

    if school == 'jiang':
        if method == 'number':
            day_pal = (numbers[0] - 1) % 6
            result['number_note'] = _number_note_jiang(numbers[0], day_pal)
            result['day_from_number'] = True
            result.update(build_jiang(lunar_day, h, day_pal=day_pal))
        else:
            result['number_note'] = ''
            result['day_from_number'] = False
            result.update(build_jiang(lunar_day, h))
    else:
        if method == 'number':
            n1, n2, n3 = numbers
            pals = (
                (n1 - 1) % 6,
                ((n1 - 1) + n2 - 1) % 6,
                (((n1 - 1) + n2 - 1) + n3 - 1) % 6,
            )
            result['number_note'] = (
                f"报数 {n1}、{n2}、{n3} 依次定月宫、日宫、时宫；"
                f"体用之「用」仍取起课时辰 {ZHI[h]}"
            )
            result.update(build_dao(lunar_month, lunar_day, h, pals=pals))
        else:
            result['number_note'] = ''
            result.update(build_dao(lunar_month, lunar_day, h))

    return result


def summary_of(result):
    """一行摘要，用于历史记录列表。"""
    prefix = '数字起课 · ' if result.get('method') == 'number' else ''
    if result['school'] == 'jiang':
        return (f"{prefix}日宫{result['day_palace']} · 时宫{result['hour_palace']}"
                f" · 身{result['body_zhi']}{result['body_wx']}")
    g3 = result['gong3']
    return f"{prefix}{g3[0]['name']}→{g3[1]['name']}→{g3[2]['name']} · {result['tiyong']['rel']}"
