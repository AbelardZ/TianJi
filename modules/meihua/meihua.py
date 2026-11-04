# -*- coding: utf-8 -*-
"""梅花易数 · 排盘逻辑

三种起课（起卦）方式：

1. **时间起卦**（《梅花易数》年月日时起卦法）：年支数 + 农历月 + 农历日
   除 8 取余为上卦；再加时辰数除 8 取余为下卦；四数之和除 6 取余为动爻。
   余 0 分别作 8（坤）与 6（上爻）。年支数子 1…亥 12，时辰数子 1…亥 12。
2. **数字起卦**：报两个数，各除 8 取余定上下卦，两数之和除 6 取余定动爻
   （《梅花易数》「两数之和除以六，余数为动爻」一系；另有「加时辰数」与
   「报三数分别定上/下/动」两说，本模块不混用，见 README）。
3. **手动指定**：直接选上下卦与动爻，用于复盘经典卦例，真实时刻只作记录。

排盘：本卦 → 动爻阴阳翻转得变卦；取本卦二三四爻为下互、三四五爻为上互得互卦。
体用：动爻在下卦则下卦为用、上卦为体；动爻在上卦则上卦为用、下卦为体。
以体卦五行为我，看用卦生克，得「用生体 / 比和 / 体克用 / 体生用 / 用克体」五断。

历法：农历月日与干支由 lunar-python 提供；23:00 起属次日子时，年月日一律
按次日农历取（时辰仍为子时），与小六壬、奇门的处理一致。年支分界默认
正月初一，可切为立春分界。
"""

from datetime import timedelta

from lunar_python import Lunar

from .data import (
    ZHI, ZHI_NUM, XIANTIAN_NUM, NUM_OF, TRIGRAMS,
    TRIGRAM_LINES, TRIGRAM_SYMBOL, TRIGRAM_NATURE, TRIGRAM_WX, TRIGRAM_DESC,
    GUA64, GUA_MEANING, SHENG, KE, TIYONG, MONTH_WANG, WANG_NOTE,
    METHODS, YEAR_RULES,
)

METHODS = METHODS
YEAR_RULES = YEAR_RULES
TRIGRAMS = TRIGRAMS

LINE_OF_BITS = {tuple(bits): name for name, bits in TRIGRAM_LINES.items()}


def shichen_index(dt):
    """时辰地支序号：子 = 0。23:00 起即为子时。"""
    return ((dt.hour + 1) // 2) % 12


def effective_dt(dt):
    """子时（23:00 后）属次日：换日再取农历年月日。"""
    return dt + timedelta(days=1) if dt.hour >= 23 else dt


def _lunar_info(dt):
    l = Lunar.fromDate(dt)
    month = l.getMonth()          # 负数表示闰月
    return {
        'lunar_month': abs(month),
        'lunar_day': l.getDay(),
        'is_leap': month < 0,
        'lunar_str': ('闰' if month < 0 else '') + f'{abs(month)}月{l.getDay()}日',
        'year_gz': l.getYearInGanZhi(),                    # 正月初一分界
        'year_gz_lichun': l.getYearInGanZhiByLiChun(),    # 立春分界
        'month_gz': l.getMonthInGanZhi(),
        'day_gz': l.getDayInGanZhi(),
        'time_gz': l.getTimeInGanZhi(),
        'month_zhi': l.getMonthZhi(),                     # 节气月支，用于旺衰
    }


def _trigram_of(bits):
    return LINE_OF_BITS[tuple(bits)]


def _gua(lines):
    """由六爻（自下而上，1 阳 0 阴）构造一张重卦。"""
    lower = _trigram_of(lines[:3])
    upper = _trigram_of(lines[3:])
    name = GUA64[upper][lower]
    return {
        'name': name,
        'meaning': GUA_MEANING[name],
        'upper': upper,
        'lower': lower,
        'upper_wx': TRIGRAM_WX[upper],
        'lower_wx': TRIGRAM_WX[lower],
        'upper_symbol': TRIGRAM_SYMBOL[upper],
        'lower_symbol': TRIGRAM_SYMBOL[lower],
        'upper_nature': TRIGRAM_NATURE[upper],
        'lower_nature': TRIGRAM_NATURE[lower],
        'lines': list(lines),
    }


def relation(ti_wx, yong_wx):
    """以体卦五行为我，判定用卦与我的五类生克关系。"""
    if ti_wx == yong_wx:
        return '比和'
    if SHENG[yong_wx] == ti_wx:
        return '用生体'
    if SHENG[ti_wx] == yong_wx:
        return '体生用'
    if KE[yong_wx] == ti_wx:
        return '用克体'
    return '体克用'


def wangshuai(wx, season_wx):
    """旺相休囚死：当令者旺、令生者相、生令者休、克令者囚、令克者死。"""
    if wx == season_wx:
        return '旺'
    if SHENG[season_wx] == wx:
        return '相'
    if SHENG[wx] == season_wx:
        return '休'
    if KE[wx] == season_wx:
        return '囚'
    return '死'


def _mod_text(total, base, zero_as):
    """「23÷8 余 7」这类可复核的算式文本；整除时写明余 0 的取法。"""
    r = total % base
    if r == 0:
        return f'{total}÷{base} 整除，余 0 作 {zero_as}'
    return f'{total}÷{base} 余 {r}'


def calculate(dt, method='time', numbers=None, manual=None, year_rule='正月'):
    """起卦并返回可直接渲染的盘面字典。"""
    method = method if method in METHODS else 'time'
    year_rule = year_rule if year_rule in YEAR_RULES else '正月'
    numbers = [int(n) for n in (numbers or [])]
    manual = dict(manual or {})

    eff = effective_dt(dt)
    li = _lunar_info(eff)
    h = shichen_index(dt)
    shichen = ZHI[h]
    shichen_num = h + 1

    year_gz = li['year_gz'] if year_rule == '正月' else li['year_gz_lichun']
    year_zhi = year_gz[-1]
    year_num = ZHI_NUM[year_zhi]

    if method == 'time':
        s3 = year_num + li['lunar_month'] + li['lunar_day']
        s4 = s3 + shichen_num
        upper_num = s3 % 8 or 8
        lower_num = s4 % 8 or 8
        dong = s4 % 6 or 6
        calc_note = (
            f'年支 {year_zhi}={year_num}（{year_rule}分界）、农历 {li["lunar_month"]} 月 '
            f'{li["lunar_day"]} 日、{shichen}时={shichen_num}。'
            f'上卦：{year_num}+{li["lunar_month"]}+{li["lunar_day"]}={s3}，'
            f'{_mod_text(s3, 8, 8)} → {XIANTIAN_NUM[upper_num]}；'
            f'下卦：{s3}+{shichen_num}={s4}，{_mod_text(s4, 8, 8)} → {XIANTIAN_NUM[lower_num]}；'
            f'动爻：{_mod_text(s4, 6, 6)} → 第 {dong} 爻。'
        )
    elif method == 'number':
        if len(numbers) < 2:
            raise ValueError('数字起卦需报两个数（上卦数、下卦数）')
        n1, n2 = numbers[:2]
        if n1 < 1 or n2 < 1:
            raise ValueError('报数须为正整数')
        upper_num = n1 % 8 or 8
        lower_num = n2 % 8 or 8
        dong = (n1 + n2) % 6 or 6
        calc_note = (
            f'报数 {n1}、{n2}：{_mod_text(n1, 8, 8)} → 上卦 {XIANTIAN_NUM[upper_num]}；'
            f'{_mod_text(n2, 8, 8)} → 下卦 {XIANTIAN_NUM[lower_num]}；'
            f'{n1}+{n2}={n1 + n2}，{_mod_text(n1 + n2, 6, 6)} → 第 {dong} 爻动。'
            '真实时刻只用于记录农历与月令，不参与取数。'
        )
    else:
        upper = manual.get('upper', '乾')
        lower = manual.get('lower', '坤')
        dong = int(manual.get('dong', 1))
        if upper not in NUM_OF or lower not in NUM_OF:
            raise ValueError('上下卦须为八卦之一')
        if dong < 1 or dong > 6:
            raise ValueError('动爻须在 1 至 6 之间')
        upper_num, lower_num = NUM_OF[upper], NUM_OF[lower]
        calc_note = (
            f'手动指定：上卦 {upper}、下卦 {lower}、第 {dong} 爻动。'
            '真实时刻只用于记录农历与月令，不参与取数。'
        )

    upper, lower = XIANTIAN_NUM[upper_num], XIANTIAN_NUM[lower_num]
    lines = TRIGRAM_LINES[lower] + TRIGRAM_LINES[upper]
    ben = _gua(lines)

    hu = _gua(lines[1:4] + lines[2:5])          # 二三四为下互、三四五为上互
    bian_lines = list(lines)
    bian_lines[dong - 1] ^= 1
    bian = _gua(bian_lines)

    # 动爻所在之卦为用，另一卦为体
    if dong <= 3:
        ti = {'name': upper, 'wx': TRIGRAM_WX[upper], 'pos': '上卦'}
        yong = {'name': lower, 'wx': TRIGRAM_WX[lower], 'pos': '下卦'}
        bian_yong_name = bian['lower']
    else:
        ti = {'name': lower, 'wx': TRIGRAM_WX[lower], 'pos': '下卦'}
        yong = {'name': upper, 'wx': TRIGRAM_WX[upper], 'pos': '上卦'}
        bian_yong_name = bian['upper']

    rel = relation(ti['wx'], yong['wx'])
    level, note = TIYONG[rel]

    # 变卦参考：体卦不动，用卦位置换成变卦的新卦，再看一层生克
    bian_rel = relation(ti['wx'], TRIGRAM_WX[bian_yong_name])
    bian_level, bian_note = TIYONG[bian_rel]

    season_wx = MONTH_WANG.get(li['month_zhi'], '土')
    state = wangshuai(ti['wx'], season_wx)

    return {
        'method': method,
        'method_label': METHODS[method],
        'year_rule': year_rule,
        'numbers': numbers[:2] if method == 'number' else [],
        'manual': manual if method == 'manual' else {},
        'datetime_str': dt.strftime('%Y-%m-%d %H:%M'),
        'lunar_str': li['lunar_str'],
        'lunar_month': li['lunar_month'],
        'lunar_day': li['lunar_day'],
        'is_leap': li['is_leap'],
        'year_gz': year_gz,
        'month_gz': li['month_gz'],
        'day_gz': li['day_gz'],
        'time_gz': li['time_gz'],
        'year_zhi': year_zhi,
        'year_num': year_num,
        'shichen': shichen + '时',
        'shichen_num': shichen_num,
        'rolled': dt.hour >= 23,
        'upper_num': upper_num,
        'lower_num': lower_num,
        'dong': dong,
        'dong_label': f'第 {dong} 爻动（{"下" if dong <= 3 else "上"}卦）',
        'calc_note': calc_note,
        'ben': ben,
        'hu': hu,
        'bian': bian,
        'ti': ti,
        'yong': yong,
        'tiyong': {'rel': rel, 'level': level, 'note': note},
        'bian_tiyong': {
            'rel': bian_rel, 'level': bian_level, 'note': bian_note,
            'yong_name': bian_yong_name,
            'yong_wx': TRIGRAM_WX[bian_yong_name],
        },
        'wang': {
            'month_zhi': li['month_zhi'],
            'season_wx': season_wx,
            'state': state,
            'note': WANG_NOTE[state],
        },
        'trigram_info': {
            pos: {
                'name': name,
                'wx': TRIGRAM_WX[name],
                'symbol': TRIGRAM_SYMBOL[name],
                'nature': TRIGRAM_NATURE[name],
                'desc': TRIGRAM_DESC[name],
            }
            for pos, name in (('upper', upper), ('lower', lower))
        },
    }


def summary_of(pan):
    """一行摘要，用于历史记录列表。"""
    return (f"{pan['method_label']} · {pan['ben']['name']} · {pan['dong_label']} "
            f"· 体{pan['ti']['name']}{pan['ti']['wx']}/用{pan['yong']['name']}{pan['yong']['wx']} "
            f"· {pan['tiyong']['rel']}（{pan['tiyong']['level']}）")
