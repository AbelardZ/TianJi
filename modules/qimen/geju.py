# -*- coding: utf-8 -*-
"""奇门盘面标注：暗干、驿马、六仪击刑、入墓、门迫／门制、旬空。

规则依据（2026-11-04 核对）：
- 暗干：飞宫法，把本柱天干加到值使门落宫，按
  戊己庚辛壬癸丁丙乙阳顺阴逆飞布九宫；若值使门落宫地盘干与本柱干相同，
  则本柱干入中宫后再飞（易德轩「暗干、八门含干」、佟氏暗干条）。
- 驿马：按**时支**三合取马（奇门不看日支，与八字不同），
  申子辰马在寅、寅午戌马在申、巳酉丑马在亥、亥卯未马在巳，
  只落艮八／坤二／乾六／巽四四维宫（易德轩「盘面标注」条）。
- 六仪击刑：戊震三、己坤二、庚艮八、辛离九、壬巽四、癸巽四。
- 入墓：三奇入墓乙乾六／坤二、丙乾六、丁艮八；
  六仪（时干）入墓按十二长生墓库，戊丙→乾六、己丁庚→艮八、
  辛壬→巽四、癸→坤二（《奇门遁甲》吉凶格局条）。
- 门迫：门克宫为迫，宫克门为制；门生宫为和、宫生门为义（本模块只标迫/制）。
- 中宫无门无神，除暗干外不参与格局判断。
"""

from . import constants

# 暗干飞宫固定序列（六仪 + 逆序三奇）
AN_GAN_ORDER = ['戊', '己', '庚', '辛', '壬', '癸', '丁', '丙', '乙']

# 六仪击刑：天盘六仪加临地盘某宫
JI_XING_GONG = {
    '戊': '3', '己': '2', '庚': '8',
    '辛': '9', '壬': '4', '癸': '4',
}
JI_XING_WHY = {
    '戊': '甲子戊，子刑卯', '己': '甲戌己，戌刑未',
    '庚': '甲申庚，申刑寅', '辛': '甲午辛，午自刑',
    '壬': '甲辰壬，辰自刑', '癸': '甲寅癸，寅刑巳',
}

# 天盘干入墓宫（含三奇两说）
MU_GONG = {
    '乙': ('6', '2'),   # 阴木墓戌（乾六）；笼统木墓未（坤二）
    '丙': ('6',),       # 火墓戌
    '丁': ('8',),       # 阴火墓丑
    '戊': ('6',), '己': ('8',),
    '庚': ('8',), '辛': ('4',),
    '壬': ('4',), '癸': ('2',),
}
SAN_QI = ('乙', '丙', '丁')

# 九宫五行与八门五行（杜门属木，巽四本位）
GONG_WX = {
    '1': 'shui', '2': 'tu', '3': 'mu', '4': 'mu', '5': 'tu',
    '6': 'jin', '7': 'jin', '8': 'tu', '9': 'huo',
}
MEN_WX = {
    '休门': 'shui', '生门': 'tu', '伤门': 'mu', '杜门': 'mu',
    '景门': 'huo', '死门': 'tu', '惊门': 'jin', '开门': 'jin',
}
WX_CN = {'mu': '木', 'huo': '火', 'tu': '土', 'jin': '金', 'shui': '水'}
# 五行相克
KE = {'mu': 'tu', 'tu': 'shui', 'shui': 'huo', 'huo': 'jin', 'jin': 'mu'}

# 驿马：按本柱地支（时家取时支）三合局
_YI_MA_GROUPS = (
    (('申', '子', '辰'), '寅'),
    (('寅', '午', '戌'), '申'),
    (('巳', '酉', '丑'), '亥'),
    (('亥', '卯', '未'), '巳'),
)
YI_MA_ZHI = {zhi: ma for group, ma in _YI_MA_GROUPS for zhi in group}

GEJU_LEGEND = (
    ('暗', '暗干', '本柱天干加值使门，阳顺阴逆飞布九宫'),
    ('刑', '六仪击刑', '天盘六仪加临相刑之宫，极凶'),
    ('墓', '入墓', '天盘干落墓库之宫，吉凶无力'),
    ('迫', '门迫', '门克宫，吉门被迫吉不就'),
    ('制', '门制', '宫克门，事受制'),
    ('空', '旬空', '该宫地支旬空'),
    ('马', '驿马', '按时支三合取马，主变动'),
)


def distribute_an_gan(di_pan, zhi_shi_gong, luo_gong_gan, dun_type):
    """排布暗干（飞宫法），返回 ``{'宫号': '天干'}``。"""
    stem = luo_gong_gan if luo_gong_gan in AN_GAN_ORDER else '戊'

    # 值使门落宫地盘干与本柱干相同 → 本柱干入中宫后再飞
    homed = di_pan.get(zhi_shi_gong) == stem
    start_gong = '5' if homed else zhi_shi_gong

    stem_index = AN_GAN_ORDER.index(stem)
    yang = dun_type == 'yang'
    start_num = int(start_gong)
    an_gan = {}
    for i in range(9):
        gong = str((start_num - 1 + (i if yang else -i)) % 9 + 1)
        an_gan[gong] = AN_GAN_ORDER[(stem_index + i) % 9]

    rule = (f'本柱干 {stem} 加值使门 {zhi_shi_gong} 宫'
            + ('，与地盘干相同故入中宫后飞布' if homed else '')
            + f'，{"阳遁顺" if yang else "阴遁逆"}行九宫')
    return {'anGan': an_gan, 'rule': rule}


def yi_ma_of(anchor_zhi):
    """按本柱地支取驿马，返回地支与落宫。"""
    ma = YI_MA_ZHI.get(anchor_zhi)
    if not ma:
        return None
    return {
        'anchorZhi': anchor_zhi,
        'zhi': ma,
        'gong': constants.ZHI_GONG_MAP[ma],
        'rule': f'本柱地支 {anchor_zhi}，驿马在 {ma}，落 {constants.ZHI_GONG_MAP[ma]} 宫',
    }


def _split_stems(tian_gan):
    """天盘干可能是「乙庚」这类双干，逐个取出可参与格局的天干。"""
    if not tian_gan:
        return []
    return [c for c in tian_gan if c in MU_GONG or c in JI_XING_GONG]


def analyze_marks(gong, tian_gan, men, kong_gongs, yi_ma):
    """返回该宫的格局标注列表（含盘面单字、名称、解释、吉凶级别）。"""
    marks = []
    if gong == '5':
        return marks

    for stem in _split_stems(tian_gan):
        if JI_XING_GONG.get(stem) == gong:
            marks.append({
                'key': '刑', 'name': '六仪击刑', 'level': 'xiong',
                'desc': f'天盘 {stem} 加临 {gong} 宫（{JI_XING_WHY[stem]}），六仪击刑，极凶。',
            })
        if gong in MU_GONG.get(stem, ()):
            kind = '三奇入墓' if stem in SAN_QI else '天盘干入墓'
            marks.append({
                'key': '墓', 'name': kind, 'level': 'xiong',
                'desc': f'天盘 {stem} 落 {gong} 宫墓库，{kind}，吉者不吉、凶者不凶，无力之象。',
            })

    men_wx = MEN_WX.get(men)
    gong_wx = GONG_WX.get(gong)
    if men_wx and gong_wx:
        if KE.get(men_wx) == gong_wx:
            level = 'ji' if men in ('开门', '休门', '生门', '景门') else 'xiong'
            marks.append({
                'key': '迫', 'name': '门迫', 'level': 'xiong',
                'desc': (f'{men}属{WX_CN[men_wx]}克 {gong} 宫{WX_CN[gong_wx]}，门迫；'
                         f'{"吉门被迫吉不就" if level == "ji" else "凶门被迫祸重重"}。'),
            })
        elif KE.get(gong_wx) == men_wx:
            marks.append({
                'key': '制', 'name': '门制', 'level': 'ping',
                'desc': f'{gong} 宫{WX_CN[gong_wx]}克{men}属{WX_CN[men_wx]}，宫克门为制，事受牵制。',
            })

    if gong in (kong_gongs or []):
        marks.append({
            'key': '空', 'name': '旬空', 'level': 'ping',
            'desc': '此宫地支旬空，须待填实或冲实。',
        })

    if yi_ma and gong == yi_ma['gong']:
        marks.append({
            'key': '马', 'name': '驿马', 'level': 'ping',
            'desc': yi_ma['rule'] + '，主变动、出行、消息。',
        })

    return marks
