# -*- coding: utf-8 -*-
"""大六壬 · 排盘逻辑。

流程：定月将 → 月将加时布天地盘 → 取四课 → 九宗门发三传 →
      排十二天将 → 旬遁干、六亲、旬空、驿马、日禄。

支持两种起课：

- ``time``：正时起课。公历时刻 → 真太阳时校正（可选）→ 23 点晚子时换日
  → 日干支、占时地支、按节气精确时刻取月将。
- ``manual``：手动指定日干支、占时、月将，用于复盘只给「某日某将某时」
  的古籍课例；真实时刻只作记录，不参与起课。

流派选项（见 data.py 与 README）：月将换将法（中气／节气）、天乙贵人
（通行口诀／袁树珊《探原》）、涉害法（计害／孟仲季简法）。
"""

import math
from datetime import datetime, timedelta

from lunar_python import Lunar

from .data import (
    ZHI, GAN, ZHI_IDX, GAN_WX, ZHI_WX, JIAZI, JI_GONG, GONG_JI_GAN,
    SHENG, KE, ZHI_YANG, GAN_YANG, YUEJIANG_RULES, JIANG_NAME,
    TIANJIANG, JI_JIANG, TIANJIANG_DESC, NOBLE_RULES, DAY_ZHI, SHUN_GONG,
    MENG, ZHONG, CHONG, XING, SELF_XING, SANHE_NEXT, YIMA, GAN_HE, DAY_LU,
    METHODS, SHEHAI_RULES, ZONGMEN_INFO, KETI_INFO,
    ke, wx_of, liuqin, gong_wx_list, meng_rank,
)

METHODS = METHODS
SHEHAI_RULES = SHEHAI_RULES
YUEJIANG_RULE_NAMES = tuple(YUEJIANG_RULES)
NOBLE_RULE_NAMES = tuple(NOBLE_RULES)
TIANJIANG = TIANJIANG
GAN = GAN
ZHI = ZHI

OPTION_DEFAULTS = {
    'method': 'time',
    'yuejiang_rule': '中气',
    'noble_rule': '通行',
    'shehai_rule': '计害',
    'longitude': None,       # None / '' 表示不校正真太阳时
    'eot': True,             # 叠加均时差（仅在给定经度时生效）
    'late_zi': True,         # 23:00 起日柱进位次日
    'manual': {
        'day_gan': '甲', 'day_zhi': '子', 'shichen': '子', 'yuejiang': '亥',
    },
}


# ---------------------------------------------------------------------------
# 时间层
# ---------------------------------------------------------------------------

def _as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ('0', 'false', 'off', 'no', '否', '')


def normalize_options(options):
    """规范化前端／落库参数，兼容缺省、空串与旧记录。"""
    o = dict(OPTION_DEFAULTS)
    o.update({k: v for k, v in (options or {}).items() if k in OPTION_DEFAULTS})

    o['method'] = o['method'] if o['method'] in METHODS else 'time'
    o['yuejiang_rule'] = (o['yuejiang_rule'] if o['yuejiang_rule'] in YUEJIANG_RULES
                          else '中气')
    o['noble_rule'] = o['noble_rule'] if o['noble_rule'] in NOBLE_RULES else '通行'
    o['shehai_rule'] = o['shehai_rule'] if o['shehai_rule'] in SHEHAI_RULES else '计害'
    o['eot'] = _as_bool(o['eot'], True)
    o['late_zi'] = _as_bool(o['late_zi'], True)

    raw = o['longitude']
    try:
        lon = None if raw is None or str(raw).strip() == '' else float(raw)
    except (TypeError, ValueError):
        lon = None
    o['longitude'] = lon if lon is not None and -180 <= lon <= 180 else None

    m = o['manual'] if isinstance(o['manual'], dict) else {}
    o['manual'] = normalize_manual(m)
    return o


def normalize_manual(m):
    m = m or {}
    gan = m.get('day_gan', '甲')
    zhi = m.get('day_zhi', '子')
    shichen = m.get('shichen', '子')
    yuejiang = m.get('yuejiang', '亥')
    return {
        'day_gan': gan if gan in GAN else '甲',
        'day_zhi': zhi if zhi in ZHI else '子',
        'shichen': shichen if shichen in ZHI else '子',
        'yuejiang': yuejiang if yuejiang in ZHI else '亥',
    }


def equation_of_time_minutes(date):
    """NOAA 均时差近似式（分钟），年内误差约 ±0.3 分。"""
    doy = date.timetuple().tm_yday
    b = 2.0 * math.pi * (doy - 81) / 364.0
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def _resolve_time(date, opts):
    """返回排盘历法基准、校后时刻与取法说明。"""
    lon = opts['longitude']
    lon_min = (lon - 120.0) * 4.0 if lon is not None else 0.0
    eot_min = equation_of_time_minutes(date) if (lon is not None and opts['eot']) else 0.0
    solar = date + timedelta(minutes=lon_min + eot_min)

    late_hit = opts['late_zi'] and solar.hour >= 23
    if late_hit:
        # 晚子时：日柱整体进位次日 00:00，时辰仍为子时
        pan = datetime.combine(solar.date() + timedelta(days=1), datetime.min.time())
        pan = pan.replace(minute=solar.minute, second=solar.second)
    else:
        pan = solar

    notes = []
    if lon is not None:
        notes.append(
            f'真太阳时：东经 {lon:g}° 时差 {lon_min:+.1f} 分'
            + (f'、均时差 {eot_min:+.1f} 分' if opts['eot'] else '（未叠加均时差）')
            + f'，校后 {solar.strftime("%Y-%m-%d %H:%M")}')
    else:
        notes.append('未做真太阳时校正，按北京时间（东经 120°）钟表时间起课')
    if late_hit:
        notes.append('晚子时换日：日柱进位次日，时辰仍为子时')
    elif not opts['late_zi']:
        notes.append('未启用 23 点换日，日柱按 00:00 分界')
    return {'solar': solar, 'pan': pan, 'late_hit': late_hit, 'notes': notes}


def shichen_index(dt):
    """时辰地支序号（子＝0，23:00 起即为子时）。"""
    return ((dt.hour + 1) // 2) % 12


def _jieqi_points(date):
    """跨前后三年收集节气交接精确时刻；表中上一年「大雪」键为 DA_XUE。"""
    points = []
    for year in (date.year - 1, date.year, date.year + 1):
        table = Lunar.fromDate(datetime(year, 6, 15, 12)).getJieQiTable()
        for key, solar in table.items():
            name = '大雪' if key == 'DA_XUE' else key
            if solar is None or not hasattr(solar, 'toYmdHms'):
                continue
            try:
                when = datetime.strptime(solar.toYmdHms(), '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                continue
            points.append((when, name))
    return sorted(set(points))


def current_yuejiang(date, rule='中气'):
    """按换将节气精确时刻取月将，返回 (月将支, 节气名, 交接时刻)。"""
    table = YUEJIANG_RULES.get(rule, YUEJIANG_RULES['中气'])
    past = [(w, n) for w, n in _jieqi_points(date) if n in table and w <= date]
    if not past:
        return '亥', '雨水', None
    when, name = past[-1]
    return table[name], name, when


def _lunar_info(dt):
    lunar = Lunar.fromDate(dt)
    month = lunar.getMonth()
    return {
        'lunar_str': ('闰' if month < 0 else '') + f'{abs(month)}月{lunar.getDay()}日',
        'year_gz': lunar.getYearInGanZhi(),
        'month_gz': lunar.getMonthInGanZhi(),
        'day_gz': lunar.getDayInGanZhi(),
        'time_gz': lunar.getTimeInGanZhi(),
    }


# ---------------------------------------------------------------------------
# 四课与九宗门
# ---------------------------------------------------------------------------

def _rel(up, down, down_is_gan):
    """四课上下生克：下克上为「贼」，上克下为「克」。"""
    uw = ZHI_WX[up]
    dw = GAN_WX[down] if down_is_gan else ZHI_WX[down]
    if KE[dw] == uw:
        return '贼'
    if KE[uw] == dw:
        return '克'
    return '无'


def _uniq(cands):
    """按上神去重（同一天盘支在多课出现只算一个候选）。"""
    seen = {}
    for c in cands:
        seen.setdefault(c['shang'], c)
    return list(seen.values())


def _bi_pick(cands, day_gan):
    """比用：取与日干同阴阳者；俱不比时退回全部候选。"""
    yang = day_gan in GAN_YANG
    bi = [c for c in cands if (c['shang'] in ZHI_YANG) == yang]
    return (bi, bool(bi)) if bi else (cands, False)


def _harm_depth(zhi, gong_of, kind):
    """涉害计害：从所临地盘宫的下一宫顺行至本家宫止。

    下贼上计「地盘克天盘神」重数，上克下计「天盘神克地盘」重数；
    每宫计入本气与十干寄宫之干，不采用八字藏干，也不计入起临宫。
    """
    target = ZHI_WX[zhi]
    cur = (ZHI_IDX[gong_of[zhi]] + 1) % 12
    home = ZHI_IDX[zhi]
    count = 0
    for _ in range(12):
        for w in gong_wx_list(ZHI[cur]):
            if kind == '贼':
                if KE[w] == target:
                    count += 1
            elif KE[target] == w:
                count += 1
        if cur == home:
            break
        cur = (cur + 1) % 12
    return count


def _rank_text(rank):
    return {3: '孟', 2: '仲', 1: '季'}[rank]


def _shehai(cands, kind, opts, day_gan, gong_of):
    """涉害取用，返回 (所选课, 依据文字, 格名)。"""
    rows = []
    for c in cands:
        z = c['shang']
        g = gong_of[z]
        depth = (_harm_depth(z, gong_of, kind)
                 if opts['shehai_rule'] == '计害' else None)
        rows.append({'c': c, 'z': z, 'gong': g,
                     'depth': depth, 'rank': meng_rank(g)})

    if opts['shehai_rule'] == '计害':
        parts = '、'.join(f'{r["z"]} 临{r["gong"]} 计 {r["depth"]} 重' for r in rows)
        note = f'涉归本家计害：{parts}；取深者'
        best = max(r['depth'] for r in rows)
        tied = [r for r in rows if r['depth'] == best]
        if len(tied) == 1:
            keti = '涉害课'
        else:
            note += f'；{best} 重并列，再论孟仲季'
            top = max(r['rank'] for r in tied)
            tied = [r for r in tied if r['rank'] == top]
            keti = ('见机格' if top == 3 else
                    '察微格' if top == 2 else '缀瑕格')
    else:
        parts = '、'.join(f'{r["z"]} 临{r["gong"]}（{_rank_text(r["rank"])}）'
                         for r in rows)
        note = f'孟仲季简法：{parts}；先孟次仲，季不用'
        top = max(r['rank'] for r in rows)
        tied = [r for r in rows if r['rank'] == top]
        keti = ('见机格' if top == 3 else
                '察微格' if top == 2 else '缀瑕格')
        if top == 1:
            # 「季当休」：候选俱临季，不用季上神，改走复等的刚日／柔日规则
            tied = rows
            note += '；候选俱临季，季不用，改依刚日取干上、柔日取支上'

    if len(tied) > 1:
        prefer = 1 if day_gan in GAN_YANG else 3
        chosen = next((r for r in tied if r['c']['no'] == prefer), None)
        if chosen is None:
            chosen = min(tied, key=lambda r: r['c']['no'])
        else:
            keti = '缀瑕格（复等）'
        note += ('；深浅与孟仲俱等（复等），'
                 f'{"刚日取干上神" if prefer == 1 else "柔日取支上神"}')
        return chosen['c'], note, keti
    return tied[0]['c'], note, keti


def _from_cands(cands, kind, opts, day_gan, gong_of, all_kes=None):
    """贼克 / 比用 / 涉害：由相克候选定初传。

    课体细分须看**全体四课**是否同时有上克下与下贼上，不能只看候选，
    否则「重审课」（既有上克下又有下贼上而取贼）永远不会出现。
    """
    all_kes = all_kes if all_kes is not None else cands
    has_zei = any(k['rel'] == '贼' for k in all_kes)
    has_ke = any(k['rel'] == '克' for k in all_kes)
    picked = _uniq(cands)

    if len(picked) == 1:
        if has_zei and has_ke:
            keti = '重审课'
        elif has_zei:
            keti = '始入课'
        else:
            keti = '元首课'
        return (picked[0]['shang'], '贼克', keti,
                f'四课中{"下贼上" if has_zei else "上克下"}取用'
                + ('（另有上克下，取贼为重审）' if has_zei and has_ke else '仅一处')
                + f'，取第 {picked[0]["no"]} 课上神 {picked[0]["shang"]} 发用')

    after_bi, has_bi = _bi_pick(picked, day_gan)
    after_bi = _uniq(after_bi)
    if len(after_bi) == 1:
        return (after_bi[0]['shang'], '比用', '知一课',
                f'相克者 {len(picked)} 处，按比用取与日干'
                f'{"同阳" if day_gan in GAN_YANG else "同阴"}之 '
                f'{after_bi[0]["shang"]}（第 {after_bi[0]["no"]} 课）发用')

    note = (f'相克者 {len(picked)} 处，'
            + ('俱比' if has_bi else '俱不比')
            + f'，比用不能定，转入涉害（{opts["shehai_rule"]}）')
    chosen, she_note, keti = _shehai(after_bi, kind, opts, day_gan, gong_of)
    return chosen['shang'], '涉害', keti, note + '；' + she_note


def _yaoke(kes, day_gan, opts, gong_of):
    """遥克：先蒿矢（神克日），后弹射（日克神）。"""
    day_w = GAN_WX[day_gan]
    ups = _uniq([{'no': k['no'], 'shang': k['shang'], 'rel': k['rel']}
                 for k in kes])
    for label, test in (
        ('蒿矢课', lambda z: KE[ZHI_WX[z]] == day_w),
        ('弹射课', lambda z: KE[day_w] == ZHI_WX[z]),
    ):
        hits = [c for c in ups if test(c['shang'])]
        if not hits:
            continue
        after_bi, _ = _bi_pick(hits, day_gan)
        after_bi = _uniq(after_bi)
        if len(after_bi) == 1:
            chosen, extra = after_bi[0], '按比用取与日干比者'
        else:
            chosen_c, extra, _ = _shehai(after_bi, '贼', opts, day_gan, gong_of)
            chosen, extra = chosen_c, '俱比俱不比，' + extra
        return (chosen['shang'], '遥克', label,
                f'四课无上下克，{"上神遥克日干" if label == "蒿矢课" else "日干遥克上神"}，'
                f'{extra}，取 {chosen["shang"]} 发用')
    return None


def _xing_chain(first, k1, k3, yang):
    """伏吟中末传：递刑；初自刑则取另一课上神为中，中再自刑则末取冲。"""
    if first in SELF_XING:
        mid = k3 if yang else k1
        flag = f'初传 {first} 自刑，中传改取{"支上神" if yang else "干上神"} {mid}'
    else:
        mid = XING[first]
        flag = f'中传取 {first} 所刑之 {mid}'
    if mid in SELF_XING:
        last = CHONG[mid]
        flag += f'；中传 {mid} 亦自刑，末传取冲 {last}'
    else:
        last = XING[mid]
        flag += f'；末传取 {mid} 所刑之 {last}'
    return mid, last, flag


def _three_chuan(kes, shang, gong_of, day_gan, day_zhi, offset, opts):
    """九宗门取三传。返回 (三传支列表, 宗门, 课体, 依据)。"""
    k1, k3, k4 = kes[0]['shang'], kes[2]['shang'], kes[3]['shang']
    yang = day_gan in GAN_YANG
    zei = [k for k in kes if k['rel'] == '贼']
    ke_ = [k for k in kes if k['rel'] == '克']
    cands = zei or ke_
    kind = '贼' if zei else '克'
    distinct = len({(k['shang'], k['xia']) for k in kes})
    bazhuan = JI_GONG[day_gan] == day_zhi    # 八专日：日干寄宫与日支同位
    fuyin, fanyin = offset == 0, offset == 6

    def chain(first):
        mid, last = shang[first], shang[shang[first]]
        return [first, mid, last], f'中传取地盘 {first} 上神 {mid}，末传取 {mid} 上神 {last}'

    # 伏吟 / 返吟：优先于其余宗门，有克仍按贼克诸法取初，中末另按刑或冲
    if fuyin or fanyin:
        if cands:
            first, zongmen, keti, note = _from_cands(
                cands, kind, opts, day_gan, gong_of, kes)
            note = f'{"伏吟" if fuyin else "返吟"}盘有克：' + note
        else:
            first = k1 if (fuyin and yang) else k3
            zongmen = '伏吟' if fuyin else '返吟'
            note = (f'{"伏吟" if fuyin else "返吟"}盘无克，'
                    f'{"刚日取干上神" if (fuyin and yang) else "取支上神"} {first} 发用')
        if fuyin:
            mid, last, flag = _xing_chain(first, k1, k3, yang)
            chuan = [first, mid, last]
            keti = ('伏吟课·杜传格' if first in SELF_XING else
                    '伏吟课·不虞格' if cands else
                    '伏吟课·自任格' if yang else '伏吟课·自信格')
            zongmen = '伏吟'
            return chuan, zongmen, keti, note + '；' + flag
        if cands:
            mid, last = CHONG[first], CHONG[CHONG[first]]
            keti = '返吟课·无依格'
            flag = f'中传取初传之冲 {mid}，末传再取冲 {last}'
        else:
            ma = YIMA[day_zhi]
            first, mid, last = ma, k3, k1
            keti = '返吟课·无亲格（井栏）'
            note = (f'返吟无克（井栏格）：丑未日取驿马 {ma} 发用')
            flag = f'中传取支上神 {k3}，末传取干上神 {k1}'
        return [first, mid, last], '返吟', keti, note + '；' + flag

    if cands:
        first, zongmen, keti, note = _from_cands(
            cands, kind, opts, day_gan, gong_of, kes)
        chuan, flag = chain(first)
        return chuan, zongmen, keti, note + '；' + flag

    if bazhuan:
        if yang:
            first = ZHI[(ZHI_IDX[k1] + 2) % 12]
            note = f'八专日（{day_gan}{day_zhi} 干支同位），阳日自干上神 {k1} 顺数三位（含起点）得 {first}'
        else:
            first = ZHI[(ZHI_IDX[k4] - 2) % 12]
            note = f'八专日（{day_gan}{day_zhi} 干支同位），阴日自第四课上神 {k4} 逆数三位（含起点）得 {first}'
        return ([first, k1, k1], '八专', '八专课',
                note + f'；中末传俱归干上神 {k1}（不论遥克）')

    yao = _yaoke(kes, day_gan, opts, gong_of)
    if yao:
        first, zongmen, keti, note = yao
        chuan, flag = chain(first)
        return chuan, zongmen, keti, note + '；' + flag

    if distinct == 3:
        if yang:
            he = GAN_HE[day_gan]
            gong = JI_GONG[he]
            first = shang[gong]
            note = (f'四课不全（三课）且无克无遥：刚日 {day_gan} 合 {he}，'
                    f'{he} 寄 {gong}，取 {gong} 宫上神 {first} 发用')
        else:
            first = SANHE_NEXT[day_zhi]
            note = (f'四课不全（三课）且无克无遥：柔日取支前三合，'
                    f'{day_zhi} 前一支为 {first}，发用')
        return ([first, k1, k1], '别责', '别责课',
                note + f'；中末传俱用干上神 {k1}')

    if yang:
        first, mid, last = shang['酉'], k3, k1
        keti = '昴星课·虎视格'
        note = (f'四课全备而无克无遥：刚日仰视，取地盘酉宫上神 {first} 发用；'
                f'中传支上神 {k3}，末传干上神 {k1}')
    else:
        first, mid, last = gong_of['酉'], k1, k3
        keti = '昴星课·冬蛇掩目格'
        note = (f'四课全备而无克无遥：柔日俯视，取天盘酉下神 {first} 发用；'
                f'中传干上神 {k1}，末传支上神 {k3}')
    return [first, mid, last], '昴星', keti, note


# ---------------------------------------------------------------------------
# 天将、遁干与盘面组装
# ---------------------------------------------------------------------------

def _noble_map(day_gan, shichen, noble_rule, gong_of):
    day_pair = NOBLE_RULES[noble_rule][day_gan]
    is_day = shichen in DAY_ZHI
    noble_zhi = day_pair[0 if is_day else 1]
    noble_gong = gong_of[noble_zhi]
    shun = noble_gong in SHUN_GONG
    step = 1 if shun else -1
    mapping = {}
    for i, name in enumerate(TIANJIANG):
        mapping[ZHI[(ZHI_IDX[noble_zhi] + step * i) % 12]] = name
    return {
        'zhi': noble_zhi,
        'gong': noble_gong,
        'day_night': '昼贵' if is_day else '夜贵',
        'shun': shun,
        'mapping': mapping,
        'note': (f'{day_gan}日{shichen}时属{"昼" if is_day else "夜"}，'
                 f'用{"昼" if is_day else "夜"}贵{noble_zhi}；贵人临地盘{noble_gong}'
                 f'宫，故十二天将{"顺" if shun else "逆"}布'),
    }


def _dun_gan(day_gz):
    """旬遁：自旬首地支起甲顺配十干，余二支为旬空。"""
    idx = JIAZI.index(day_gz)
    xun = idx // 10 * 10
    first = ZHI_IDX[JIAZI[xun][1]]
    mapping = {ZHI[(first + i) % 12]: GAN[i] for i in range(10)}
    kong = [ZHI[(first + 10) % 12], ZHI[(first + 11) % 12]]
    return mapping, kong, JIAZI[xun]


def _relation(a, b):
    wa, wb = ZHI_WX[a], ZHI_WX[b]
    if wa == wb:
        return '比和'
    if SHENG[wa] == wb:
        return '生'
    if KE[wa] == wb:
        return '克'
    if SHENG[wb] == wa:
        return '受生'
    return '受克'


def _decorate(zhi, day_gan, dun, kong, ma, lu, tianjiang):
    jiang = tianjiang.get(zhi, '')
    return {
        'zhi': zhi,
        'wx': ZHI_WX[zhi],
        'shen': JIANG_NAME[zhi],
        'jiang': jiang,
        'jiang_ji': jiang in JI_JIANG,
        'jiang_desc': TIANJIANG_DESC.get(jiang, ''),
        'dun': dun.get(zhi, ''),
        'dun_full': (dun.get(zhi, '') + zhi) if dun.get(zhi) else zhi,
        'liuqin': liuqin(zhi, day_gan),
        'kong': zhi in kong,
        'ma': zhi == ma,
        'lu': zhi == lu,
    }


def build_pan(day_gz, shichen, yuejiang, meta=None, options=None):
    """由「日干支 + 占时地支 + 月将」构造完整课式（手动复盘亦走此入口）。"""
    opts = normalize_options(options)
    if day_gz not in JIAZI:
        raise ValueError(f'无效的日干支：{day_gz}')
    if shichen not in ZHI or yuejiang not in ZHI:
        raise ValueError('占时或月将须为十二地支之一')
    day_gan, day_zhi = day_gz[0], day_gz[1]

    offset = (ZHI_IDX[yuejiang] - ZHI_IDX[shichen]) % 12
    shang = {g: ZHI[(ZHI_IDX[g] + offset) % 12] for g in ZHI}
    gong_of = {v: k for k, v in shang.items()}

    k1s = shang[JI_GONG[day_gan]]
    k3s = shang[day_zhi]
    kes = [
        {'no': 1, 'label': '干上（干阳）', 'xia': day_gan,
         'xia_is_gan': True, 'shang': k1s},
        {'no': 2, 'label': '干阴', 'xia': k1s,
         'xia_is_gan': False, 'shang': shang[k1s]},
        {'no': 3, 'label': '支上（支阳）', 'xia': day_zhi,
         'xia_is_gan': False, 'shang': k3s},
        {'no': 4, 'label': '支阴', 'xia': k3s,
         'xia_is_gan': False, 'shang': shang[k3s]},
    ]
    for k in kes:
        k['rel'] = _rel(k['shang'], k['xia'], k['xia_is_gan'])
        k['rel_label'] = {'贼': '下贼上', '克': '上克下', '无': '无克'}[k['rel']]

    chuan, zongmen, keti, note = _three_chuan(
        kes, shang, gong_of, day_gan, day_zhi, offset, opts)

    noble = _noble_map(day_gan, shichen, opts['noble_rule'], gong_of)
    dun, kong, xunshou = _dun_gan(day_gz)
    ma, lu = YIMA[day_zhi], DAY_LU[day_gan]
    tianjiang = noble['mapping']

    cells = []
    for gong in ZHI:
        c = _decorate(shang[gong], day_gan, dun, kong, ma, lu, tianjiang)
        c['gong'] = gong
        c['gong_wx'] = ZHI_WX[gong]
        c['is_yuejiang'] = shang[gong] == yuejiang
        cells.append(c)

    for k in kes:
        k['info'] = _decorate(k['shang'], day_gan, dun, kong, ma, lu, tianjiang)
        k['xia_wx'] = wx_of(k['xia'])

    chuans = []
    for i, zhi in enumerate(chuan):
        c = _decorate(zhi, day_gan, dun, kong, ma, lu, tianjiang)
        c['pos'] = ('初传', '中传', '末传')[i]
        c['gong'] = gong_of[zhi]
        chuans.append(c)

    base_keti = next((n for n in KETI_INFO if keti.startswith(n.split('·')[0])), None)
    rel12 = _relation(chuan[0], chuan[1])
    rel23 = _relation(chuan[1], chuan[2])
    rel_chuan_day = _relation(chuan[2], JI_GONG[day_gan])
    advice = [
        f'课体「{keti}」：{KETI_INFO.get(base_keti or "", "见取用依据")}',
        f'三传 {chuan[0]}→{chuan[1]}→{chuan[2]}：初{rel12}中、中{rel23}末；'
        f'末传与日干寄宫 {JI_GONG[day_gan]} 为{rel_chuan_day}。',
        f'初传 {chuans[0]["dun_full"]} 为日干之{chuans[0]["liuqin"]}，'
        f'乘{chuans[0]["jiang"]}（{"吉将" if chuans[0]["jiang_ji"] else "凶将"}：'
        f'{chuans[0]["jiang_desc"]}）。',
        f'旬首 {xunshou}，旬空 {"、".join(kong)}；驿马 {ma}、日禄 {lu}。',
        '提示：以上为课式结构与象类，不构成吉凶断语；断课须合参四课、旺衰、'
        '年命与所问之事。',
    ]

    meta = dict(meta or {})
    return {
        'method': opts['method'],
        'method_label': METHODS[opts['method']],
        'options': {k: opts[k] for k in
                    ('yuejiang_rule', 'noble_rule', 'shehai_rule',
                     'longitude', 'eot', 'late_zi')},
        'manual': opts['manual'],
        'datetime_str': meta.get('datetime_str', ''),
        'day_gz': day_gz,
        'day_gan': day_gan,
        'day_zhi': day_zhi,
        'shichen': shichen,
        'yuejiang': yuejiang,
        'yuejiang_name': JIANG_NAME[yuejiang],
        'offset': offset,
        'pan_type': ('伏吟' if offset == 0 else
                     '返吟' if offset == 6 else '常盘'),
        'ji_gong': JI_GONG[day_gan],
        'tianpan': shang,
        'gong_of': gong_of,
        'cells': cells,
        'cells_by_gong': {c['gong']: c for c in cells},
        'kes': kes,
        'keti_count': len({(k['shang'], k['xia']) for k in kes}),
        'bazhuan': JI_GONG[day_gan] == day_zhi,
        'chuan': [c['zhi'] for c in chuans],
        'chuans': chuans,
        'zongmen': zongmen,
        'zongmen_info': ZONGMEN_INFO.get(zongmen, ''),
        'keti': keti,
        'qu_yong_note': note,
        'advice': advice,
        'noble': noble,
        'tianjiang': tianjiang,
        'dun': dun,
        'kong': kong,
        'xunshou': xunshou,
        'yima': ma,
        'day_lu': lu,
        'time_info': meta,
    }


def calculate(dt, method='time', manual=None, options=None):
    """起课主入口。``options`` 可含 method / manual / 各流派与时法参数。"""
    opts = normalize_options({**(options or {}), 'method': method})
    if manual is not None:
        opts['manual'] = normalize_manual(manual)

    if opts['method'] == 'manual':
        m = opts['manual']
        day_gz = m['day_gan'] + m['day_zhi']
        meta = {
            'datetime_str': dt.strftime('%Y-%m-%d %H:%M'),
            'lunar_str': '',
            'notes': ['日干支、月将与占时由用户指定；真实时刻仅作记录，不参与起课'],
            'jieqi_name': '', 'jieqi_at': '', 'four_pillars': {},
            'method_note': '手动指定（复盘古籍课例）',
        }
        return build_pan(day_gz, m['shichen'], m['yuejiang'], meta, opts)

    resolved = _resolve_time(dt, opts)
    pan_dt = resolved['pan']
    shichen = ZHI[shichen_index(resolved['solar'])]
    li = _lunar_info(pan_dt)
    yj, jq_name, jq_when = current_yuejiang(resolved['solar'], opts['yuejiang_rule'])
    meta = {
        'datetime_str': dt.strftime('%Y-%m-%d %H:%M'),
        'lunar_str': li['lunar_str'],
        'four_pillars': {
            'year': li['year_gz'], 'month': li['month_gz'],
            'day': li['day_gz'], 'time': li['time_gz'],
        },
        'jieqi_name': jq_name,
        'jieqi_at': jq_when.strftime('%Y-%m-%d %H:%M:%S') if jq_when else '',
        'yuejiang_from': f'自{jq_name}起用 {yj}（{JIANG_NAME[yj]}）将',
        'late_zi': resolved['late_hit'],
        'notes': resolved['notes'],
        'method_note': f'正时起课 · {opts["yuejiang_rule"]}换将',
    }
    return build_pan(li['day_gz'], shichen, yj, meta, opts)


def summary_of(pan):
    """一行摘要，用于历史记录列表。"""
    return (f"{pan['day_gz']}日 · {pan['shichen']}时 · {pan['yuejiang']}将 "
            f"· {pan['keti']}（{pan['zongmen']}） "
            f"· 三传 {'→'.join(pan['chuan'])}")
