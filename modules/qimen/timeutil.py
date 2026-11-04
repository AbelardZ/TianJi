# -*- coding: utf-8 -*-
"""奇门时间层：真太阳时、晚子时换日、节气交接精确时刻。

``lunar-python`` 的日柱按 00:00 换日、时柱却按 23:00 换日：
23:00-24:00 之间 ``getDayInGanZhi()`` 仍属当日，``getTimeInGanZhi()``
已属次日子时，四柱自相矛盾。本模块把该时段整体进位到次日 00:00，
使四柱、旬首、空亡、定局全部取同一历法基准。

节气交接时刻取自 ``getJieQiTable()`` 返回的 Solar（含时分秒），
取代原先只按「当日/前一日」粒度的 ``getPrevJieQi(True)``。
"""

import math
from datetime import datetime, timedelta

from lunar_python import Lunar

from . import constants

JIE_QI_NAMES = tuple(constants.JIE_QI_JU_MAP.keys())

# lunar-python 的节气表从上一年「大雪」起算，该一项用英文键
_JIE_QI_KEY_ALIAS = {'DA_XUE': '大雪'}


def equation_of_time_minutes(date):
    """均时差（真太阳时 - 平太阳时），单位分钟。

    采用 NOAA / Spencer 近似式，年内误差约 ±0.3 分钟，
    对奇门定局（以日、时辰为单位）无影响。
    """
    day_of_year = date.timetuple().tm_yday
    b = 2.0 * math.pi * (day_of_year - 81) / 364.0
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def _as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ('0', 'false', 'off', 'no', '否', '')


def resolve_time(date, options=None):
    """把用户输入的钟表时间解析成排盘时间，并返回完整取法说明。

    选项：
    - ``longitude``：当地东经度（度，东经为正）；为空表示不校正真太阳时
    - ``eot``：是否叠加均时差，默认 True（仅在给定经度时生效）
    - ``late_zi``：是否启用 23 点换日，默认 True
    """
    options = options or {}

    raw_longitude = options.get('longitude')
    longitude = None
    if raw_longitude is not None and str(raw_longitude).strip() != '':
        try:
            longitude = float(raw_longitude)
        except (TypeError, ValueError):
            longitude = None
    if longitude is not None and not (-180.0 <= longitude <= 180.0):
        longitude = None

    use_eot = _as_bool(options.get('eot'), True)
    late_zi = _as_bool(options.get('late_zi'), True)

    longitude_minutes = 0.0
    eot_minutes = 0.0
    if longitude is not None:
        longitude_minutes = (longitude - 120.0) * 4.0
        if use_eot:
            eot_minutes = equation_of_time_minutes(date)
    offset_minutes = longitude_minutes + eot_minutes
    solar = date + timedelta(minutes=offset_minutes)

    late_zi_hit = False
    if late_zi and solar.hour >= 23:
        # 晚子时：整体进位到次日 00:00（保留分秒，时辰仍为子时）
        pan = datetime.combine(solar.date() + timedelta(days=1),
                               datetime.min.time())
        pan = pan.replace(minute=solar.minute, second=solar.second)
        late_zi_hit = True
    else:
        pan = solar

    notes = []
    if longitude is not None:
        parts = [f'东经 {longitude:g}° 时差 {longitude_minutes:+.1f} 分']
        if use_eot:
            parts.append(f'均时差 {eot_minutes:+.1f} 分')
        notes.append('真太阳时校正：' + '，'.join(parts) +
                     f'，合计 {offset_minutes:+.1f} 分；'
                     f'校后 {solar.strftime("%Y-%m-%d %H:%M")}')
    else:
        notes.append('未做真太阳时校正，按北京时间（东经 120°）钟表时间起局')
    if late_zi_hit:
        notes.append('晚子时换日：23:00 后日柱进位次日，'
                     f'排盘基准 {pan.strftime("%Y-%m-%d %H:%M")}，时辰仍为子时')
    elif late_zi:
        notes.append('23 点换日已启用，本次不在晚子时时段')
    else:
        notes.append('未启用 23 点换日，日柱按 00:00 分界')

    return {
        'raw': date,
        'solar': solar,
        'pan': pan,
        'longitude': longitude,
        'use_eot': use_eot,
        'longitude_minutes': longitude_minutes,
        'eot_minutes': eot_minutes,
        'offset_minutes': offset_minutes,
        'late_zi': late_zi,
        'late_zi_hit': late_zi_hit,
        'notes': notes,
        'summary': '；'.join(notes),
    }


def current_jie_qi(date):
    """返回 (节气名, 交接时刻 datetime)。

    按精确交接时刻判断，而不是按日粒度；交接当日交接时刻之前仍属上一节气。
    """
    lunar = Lunar.fromDate(date)
    table = lunar.getJieQiTable()
    candidates = []
    for key, solar in table.items():
        name = _JIE_QI_KEY_ALIAS.get(key, key)
        if name not in JIE_QI_NAMES or solar is None:
            continue
        if not hasattr(solar, 'toYmdHms'):
            continue
        try:
            when = datetime.strptime(solar.toYmdHms(), '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            continue
        candidates.append((when, name))

    past = [item for item in sorted(set(candidates)) if item[0] <= date]
    if past:
        return past[-1][1], past[-1][0]

    # 兜底：节气表异常时退回按日粒度
    jie_qi = lunar.getPrevJieQi(True)
    name = jie_qi.getName() if hasattr(jie_qi, 'getName') else str(jie_qi)
    return name, None
