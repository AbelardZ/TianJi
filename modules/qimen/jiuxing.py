# 九星分布计算模块（转盘奇门）
#
# 规则依据（转盘奇门通例）：
#   1. 值符星 = 时柱旬首（六甲）所落地盘宫在「元旦盘」上的九星，
#      而不是时干落宫的星，更不是固定的天蓬星。
#   2. 值符随时干：把值符星移到地盘时干所在宫，其余八星按
#      蓬、任、冲、辅、英、芮(禽)、柱、心的固定队形顺时针依次排布，
#      阴阳遁均顺时针，不随阴阳改变方向。
#   3. 旬首或时干落中宫，一律寄坤二宫；天禽星随天芮同宫（寄坤二）。
#
# 旧实现误把「时干宫最终得到的星」当作值符星，等价于把值符星恒定为
# 天蓬，导致天盘九星、天盘干与值符星显示整体错位，此处修正。

# 顺时针宫序（不含中宫），即洛书九宫的八卦方位序
GONG_ORDER = ['1', '8', '3', '4', '9', '2', '7', '6']
# 与宫序一一对应的元旦盘九星固定队形
STAR_ORDER = ['天蓬', '天任', '天冲', '天辅', '天英', '天芮', '天柱', '天心']
ORIGIN_STAR = dict(zip(GONG_ORDER, STAR_ORDER))


def _find_gong_by_stem(san_qi_liu_yi, stem):
    """在地盘三奇六仪中查找某个天干所在宫。"""
    if not stem:
        return ''
    for gong, value in san_qi_liu_yi.items():
        if value == stem:
            return gong
    return ''


def distribute_jiu_xing(san_qi_liu_yi, xun_shou, luo_gong_gan):
    """
    排布天盘九星，返回值符信息。

    参数:
    - san_qi_liu_yi: 地盘三奇六仪分布，形如 {'1':'戊', ...}
    - xun_shou: 旬首所遁六仪（戊/己/庚/辛/壬/癸）
    - luo_gong_gan: 当前值符所随的天干（时家为时干，甲已替换为旬首六仪）

    返回:
    {
      'jiu_xing': {'1':'天蓬',...,'5':'天禽',...},
      'zhi_fu_gong': 'x',   # 值符落宫（时干宫）
      'zhi_fu_xing': '天某' # 真正的旬首宫元旦盘星
    }
    """
    # 1. 由旬首宫定「值符星」——这是本模块的核心
    xun_gong = _find_gong_by_stem(san_qi_liu_yi, xun_shou) or '5'
    # 旬首落中宫时，元旦盘为天禽；天禽寄坤二与天芮同宫，故按天芮入队形
    xun_gong_for_star = '2' if xun_gong == '5' else xun_gong
    zhi_fu_xing = ORIGIN_STAR.get(xun_gong_for_star, '天蓬')

    # 2. 值符随时干落宫；时干不在盘中时退回旬首宫
    zhi_fu_gong = _find_gong_by_stem(san_qi_liu_yi, luo_gong_gan) or xun_gong
    if zhi_fu_gong == '5':
        zhi_fu_gong = '2'

    # 3. 九星整体顺时针旋转：值符星落在值符宫，其余按固定队形顺排
    jiu_xing = {g: '' for g in ('1', '2', '3', '4', '5', '6', '7', '8', '9')}
    # 中宫保留天禽（寄坤二），天芮宫的天盘干会并列带上中宫干
    jiu_xing['5'] = '天禽'

    star_idx = STAR_ORDER.index(zhi_fu_xing)
    if zhi_fu_gong in GONG_ORDER:
        gong_idx = GONG_ORDER.index(zhi_fu_gong)
    else:
        gong_idx = 0
        zhi_fu_gong = GONG_ORDER[0]

    for i in range(8):
        gong = GONG_ORDER[(gong_idx + i) % 8]
        jiu_xing[gong] = STAR_ORDER[(star_idx + i) % 8]

    return {
        'jiu_xing': jiu_xing,
        'zhi_fu_gong': zhi_fu_gong,
        'zhi_fu_xing': zhi_fu_xing,
    }
