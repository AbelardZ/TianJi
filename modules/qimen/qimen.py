# 奇门遁甲核心计算库
# 实现完整的奇门遁甲排盘系统

from collections import Counter

from lunar_python import Lunar, Solar
from datetime import datetime, timedelta

from . import jiuxing as jiu_xing_module
from . import bamen as ba_men_module
from . import bashen as ba_shen_module
from . import dipan as di_pan_module
from . import constants
from . import timeutil
from . import geju

# 天干地支对应
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 三奇六仪(天盘)
SAN_QI = ["戊", "己", "庚"]
LIU_YI = ["辛", "壬", "癸", "丁", "丙", "乙"]

# 九宫位置信息
JIU_GONG = {
    '1': {'name': '坎', 'direction': '正北', 'element': 'shui', 'color': '#03A9F4', 'yinyang': '阴', 'dizhi': '子'},
    '2': {'name': '坤', 'direction': '西南', 'element': 'tu', 'color': '#795548', 'yinyang': '阴', 'dizhi': '未申'},
    '3': {'name': '震', 'direction': '正东', 'element': 'mu', 'color': '#4CAF50', 'yinyang': '阳', 'dizhi': '卯'},
    '4': {'name': '巽', 'direction': '东南', 'element': 'mu', 'color': '#4CAF50', 'yinyang': '阳', 'dizhi': '辰巳'},
    '5': {'name': '中', 'direction': '中宫', 'element': 'tu', 'color': '#795548', 'yinyang': '阴阳', 'dizhi': ''},
    '6': {'name': '乾', 'direction': '西北', 'element': 'jin', 'color': '#FF9800', 'yinyang': '阳', 'dizhi': '戌亥'},
    '7': {'name': '兑', 'direction': '正西', 'element': 'jin', 'color': '#FF9800', 'yinyang': '阴', 'dizhi': '酉'},
    '8': {'name': '艮', 'direction': '东北', 'element': 'tu', 'color': '#795548', 'yinyang': '阳', 'dizhi': '丑寅'},
    '9': {'name': '离', 'direction': '正南', 'element': 'huo', 'color': '#F44336', 'yinyang': '阳', 'dizhi': '午'}
}

# 九星信息
# 别名按北斗九星通例：蓬贪狼、芮巨门、冲禄存、辅文曲、禽廉贞、
# 心武曲、柱破军、任左辅、英右弼。旧表把芮/禽/心/任/英五项的别名错配。
JIU_XING = {
    '天蓬': {'alias': '贪狼', 'element': 'shui', 'color': '#03A9F4', 'feature': '主智慧、口才、机变'},
    '天芮': {'alias': '巨门', 'element': 'tu', 'color': '#795548', 'feature': '主稳重、忠厚、坚韧'},
    '天冲': {'alias': '禄存', 'element': 'mu', 'color': '#4CAF50', 'feature': '主冲击、变化、快速'},
    '天辅': {'alias': '文曲', 'element': 'mu', 'color': '#4CAF50', 'feature': '主扶助、支持、辅佐'},
    '天禽': {'alias': '廉贞', 'element': 'tu', 'color': '#795548', 'feature': '为中宫之神，主枢纽、核心'},
    '天心': {'alias': '武曲', 'element': 'jin', 'color': '#FF9800', 'feature': '主决断、判断、果决'},
    '天柱': {'alias': '破军', 'element': 'jin', 'color': '#FF9800', 'feature': '主坚固、支撑、顶天立地'},
    '天任': {'alias': '左辅', 'element': 'tu', 'color': '#795548', 'feature': '主责任、重担、实际'},
    '天英': {'alias': '右弼', 'element': 'huo', 'color': '#F44336', 'feature': '主才华、聪明、显贵'}
}

# 八门信息
BA_MEN = {
    '休门': {'feature': '为吉门，主休养、安宁、平和。适合休息与调养。', 'type': 'ji', 'element': 'shui', 'color': '#03A9F4'},
    '生门': {'feature': '为吉门，主生发、成长、喜庆。适合开始新事物。', 'type': 'ji', 'element': 'mu', 'color': '#4CAF50'},
    '伤门': {'feature': '为凶门，主伤害、损失、疾病。需避免冲突与伤害。', 'type': 'xiong', 'element': 'mu', 'color': '#4CAF50'},
    '杜门': {'feature': '为凶门，主阻塞、停滞、困难。事情易受阻碍。', 'type': 'xiong', 'element': 'mu', 'color': '#795548'},
    '景门': {'feature': '为吉门，主光明、展示、明亮。适合公开场合与展示。', 'type': 'ji', 'element': 'huo', 'color': '#F44336'},
    '死门': {'feature': '为凶门，主衰败、结束、死亡。不宜开始重要事情。', 'type': 'xiong', 'element': 'tu', 'color': '#795548'},
    '惊门': {'feature': '为凶门，主惊吓、变故、突发状况。需注意意外变化。', 'type': 'xiong', 'element': 'jin', 'color': '#FF9800'},
    '开门': {'feature': '为吉门，主通达、顺畅、开始。万事顺利，有好的开端。', 'type': 'ji', 'element': 'jin', 'color': '#FF9800'}
}

# 八神信息
BA_SHEN = {
    '值符': {'feature': '为贵神，主吉庆、贵人、福星。', 'type': 'ji'},
    '腾蛇': {'feature': '为凶神，主口舌是非、波动起伏。', 'type': 'xiong'},
    '太阴': {'feature': '为吉神，主柔和、隐藏、内敛。', 'type': 'ji'},
    '六合': {'feature': '为吉神，主和谐、团结、合作。', 'type': 'ji'},
    '白虎': {'feature': '为凶神，主凶猛、伤害、灾祸。', 'type': 'xiong'},
    '玄武': {'feature': '为凶神，主隐秘、盗窃、欺诈。', 'type': 'xiong'},
    '九地': {'feature': '为吉神，主地利、丰收、稳固。', 'type': 'ji'},
    '九天': {'feature': '为吉神，主高升、贵人、成功。', 'type': 'ji'}
}

# 日家奇门三元定位：以「最接近二至的甲子日」为起点，六十日一元。
# 依据《奇门遁甲统宗》「又法日奇门起例」与《遁甲演义》：
#   冬至后阳遁，第一／二／三甲子各用阳一／七／四局；
#   夏至后阴遁，第一／二／三甲子各用阴九／三／六局。
# 冬至到夏至约 183 日，略多于三元 180 日；默认「置闰续元」把多出的几日
# 仍归第三元直到下一二至，不再周而复始跳回上元（可选切回旧行为）。
def _ri_jia_yuan(date, options=None):
    options = options or {}
    day0 = datetime(date.year, date.month, date.day)
    candidates = []
    for offset in (-1, 0, 1):
        probe = Lunar.fromDate(datetime(date.year + offset, 6, 15, 12))
        for name, solar in probe.getJieQiTable().items():
            if name in ('冬至', '夏至') and hasattr(solar, 'getYear'):
                candidates.append(
                    (datetime(solar.getYear(), solar.getMonth(), solar.getDay()), name)
                )
    past = sorted({c for c in candidates if c[0] <= day0})

    if past:
        solstice_day, solstice_name = past[-1]
        sol_idx = constants.LIU_SHI_HUA_JIA_ZI.index(
            Lunar.fromDate(solstice_day + timedelta(hours=12)).getDayInGanZhi()
        )
        prev_jiazi = solstice_day - timedelta(days=sol_idx)
        next_jiazi = prev_jiazi + timedelta(days=60)
        if abs((next_jiazi - solstice_day).days) < abs((prev_jiazi - solstice_day).days):
            base = next_jiazi
        else:
            base = prev_jiazi
    else:
        # 兜底：节气表异常时，退回当日所在旬的甲子日
        solstice_name = '冬至' if date.month in (12, 1, 2, 3, 4, 5) else '夏至'
        sol_idx = constants.LIU_SHI_HUA_JIA_ZI.index(
            Lunar.fromDate(date).getDayInGanZhi()
        )
        base = day0 - timedelta(days=sol_idx)

    days = (day0 - base).days
    ri_run = options.get('ri_run', '延续')
    if ri_run not in constants.RI_RUN_MODES:
        ri_run = '延续'

    run_note = ''
    if days >= 180 and ri_run == '延续':
        yuan_idx = 2
        run_note = (f'逾三元 {days - 180} 日，行置闰：第三元延续至下一二至，'
                    f'不回上元')
    else:
        yuan_idx = (days // 60) % 3
        if days >= 180:
            run_note = f'逾三元，按周而复始回到第 {yuan_idx + 1} 元'

    if solstice_name == '冬至':
        dun_type = 'yang'
        ju_num = constants.RI_JIA_YANG_JU[yuan_idx]
    else:
        dun_type = 'yin'
        ju_num = constants.RI_JIA_YIN_JU[yuan_idx]

    return {
        'solstice': solstice_name,
        'base': base,
        'days': days,
        'yuan_index': yuan_idx,
        'dun_type': dun_type,
        'ju_num': ju_num,
        'ri_run': ri_run,
        'run_note': run_note,
    }


def _shang_yuan_segment(date):
    """返回当日所在「三元段」的起点：不晚于当日的最近上元符头。

    上元符头 = 甲／己日且地支为子午卯酉，每 15 天一次。
    置闰法以完整三元（15 天）为一个节气段，段内节气不中途换表。
    """
    for delta in range(0, 16):
        day = date - timedelta(days=delta)
        lunar = Lunar.fromDate(datetime(day.year, day.month, day.day, 12))
        if (lunar.getDayGan() in ('甲', '己')
                and lunar.getDayZhi() in constants.SHANG_YUAN_ZHI):
            return datetime(day.year, day.month, day.day, 12)
    return date


def _chao_jie_info(jie_qi_name, jie_qi_time):
    """判定当前节气的正授／超神／接气，以及是否需要置闰（闰奇）。

    上元符头 = 甲／己日且地支为子午卯酉。符头先于节气为超神，
    节气先于符头为接气，同日为正授；「超不过九，接不过五」，
    超神过九且节气为芒种／大雪时重复该节气三元（闰奇）。
    """
    base = {
        'status': '未知', 'days': 0, 'run_qi': False,
        'note': '节气交接时刻不可用，未判超神接气',
    }
    if jie_qi_time is None:
        return base

    jq_day = jie_qi_time.date()
    shang_yuan = []
    for delta in range(-15, 16):
        day = jq_day + timedelta(days=delta)
        lunar = Lunar.fromDate(datetime(day.year, day.month, day.day, 12))
        if (lunar.getDayGan() in ('甲', '己')
                and lunar.getDayZhi() in constants.SHANG_YUAN_ZHI):
            shang_yuan.append((abs(delta), delta, day))
    if not shang_yuan:
        return base

    _, _, fu_day = min(shang_yuan)
    diff = (jq_day - fu_day).days
    if diff > 0:
        status, days = '超神', diff
    elif diff < 0:
        status, days = '接气', -diff
    else:
        status, days = '正授', 0

    run_qi = (status == '超神' and days > constants.CHAO_JIE_MAX
              and jie_qi_name in constants.ZHI_RUN_JIE_QI)
    note = f'{jie_qi_name}{status}{days}日（上元符头 {fu_day.isoformat()}）'
    if run_qi:
        note += '，超神过九，行闰奇：重复该节气三元'

    return {
        'status': status,
        'days': days,
        'run_qi': run_qi,
        'shangYuan': fu_day,
        'note': note,
    }


def calculate_ju_shu(date, method='时家', options=None,
                     jie_qi_name=None, jie_qi_time=None):
    """计算局数。

    - ``jie_qi_name`` / ``jie_qi_time`` 由时间层按精确交接时刻给出；
      未传时退回 ``getPrevJieQi(True)``（按日粒度）。
    - ``options['ding_ju']``：拆补（默认）／置闰。
    - ``options['ri_run']``：日家逾三元时的处理。
    - ``options['year_rule']``：年柱分界（立春／正月）。
    """
    options = options or {}
    lunar = Lunar.fromDate(date)

    if jie_qi_name is None:
        jq = lunar.getPrevJieQi(True)
        jie_qi_name = jq.getName() if hasattr(jq, 'getName') else str(jq)
    if jie_qi_time is None:
        _, jie_qi_time = timeutil.current_jie_qi(date)

    chao = _chao_jie_info(jie_qi_name, jie_qi_time)

    day_gan = lunar.getDayGan()
    day_zhi = lunar.getDayZhi()
    gan_index = TIAN_GAN.index(day_gan) if day_gan in TIAN_GAN else 0
    zhi_index = DI_ZHI.index(day_zhi) if day_zhi in DI_ZHI else 0
    offset = gan_index % 5
    fu_tou_zhi_index = (zhi_index - offset) % 12
    fu_tou_date = date - timedelta(days=offset)
    fu_tou_zhi = DI_ZHI[fu_tou_zhi_index]

    year_rule = options.get('year_rule', '立春')
    if year_rule not in constants.YEAR_RULES:
        year_rule = '立春'
    year_gz = (lunar.getYearInGanZhiByLiChun()
               if year_rule == '立春' else lunar.getYearInGanZhi())

    yuan_names = ('上元', '中元', '下元')
    chao_out = {
        'status': chao['status'],
        'days': chao['days'],
        'runQi': chao['run_qi'],
        'note': chao['note'],
        'jieQiAt': jie_qi_time.strftime('%Y-%m-%d %H:%M') if jie_qi_time else '',
    }

    # ------------------------------------------------------------------
    # 年／月／日家：一局用满一元，不逐柱递减局数
    # ------------------------------------------------------------------
    if method in ('年家', '月家', '日家'):
        if method == '年家':
            # 年家太岁与年柱统一按选定的分界（默认立春），
            # 立春～春节窗口内农历年尚未进位，需手工 +1 年。
            year = lunar.getYear()
            if year_gz != lunar.getYearInGanZhi():
                year += 1
            yuan_idx = ((year - constants.NIAN_JIA_JIAZI_BASE) // 60) % 3
            ju_num = constants.NIAN_JIA_YUAN_JU[yuan_idx]
            dun_type = 'yin'
            yuan_start = year - (year - constants.NIAN_JIA_JIAZI_BASE) % 60
            note = (f'六十年一元，{yuan_start} 年起，'
                    f'一局用满六十年；'
                    f'年柱按{year_rule}分界（{year_gz}）')

        elif method == '月家':
            year_gan, year_zhi = year_gz[0], year_gz[1]
            gan_back = TIAN_GAN.index(year_gan) % 5
            fu_gan = TIAN_GAN[(TIAN_GAN.index(year_gan) - gan_back) % 10]
            fu_zhi = DI_ZHI[(DI_ZHI.index(year_zhi) - gan_back) % 12]
            if fu_zhi in constants.MENG_ZHI:
                yuan_idx = 0
            elif fu_zhi in constants.ZHONG_ZHI:
                yuan_idx = 1
            else:
                yuan_idx = 2
            ju_num = constants.YUE_JIA_YUAN_JU[yuan_idx]
            dun_type = 'yin'
            yuan_kind = ('四孟', '四仲', '四季')[yuan_idx]
            note = (f'六十月一元，甲己符头 '
                    f'{fu_gan}{fu_zhi} 年（{yuan_kind}），'
                    f'一局用满五年；定元年柱按{year_rule}分界')

        else:  # 日家
            ri = _ri_jia_yuan(date, options)
            yuan_idx = ri['yuan_index']
            ju_num = ri['ju_num']
            dun_type = ri['dun_type']
            note = (f'六十日一元，基准甲子 '
                    f'{ri["base"].strftime("%Y-%m-%d")}（{ri["solstice"]}），'
                    f'已行 {ri["days"]} 日')
            if ri['run_note']:
                note += f'；{ri["run_note"]}'

        dun_name = '阳遁' if dun_type == 'yang' else '阴遁'
        return {
            'jieQiName': jie_qi_name,
            'type': dun_type,
            'number': str(ju_num),
            'yuan': yuan_names[yuan_idx],
            'fullName': f'{dun_name}{ju_num}局 ({yuan_names[yuan_idx]})',
            'formatCode': f'{dun_type}-{ju_num}',
            'note': note,
            'chaoJie': chao_out,
        }

    # ------------------------------------------------------------------
    # 时家：拆补法（节气为主）与置闰法（符头主主）
    # ------------------------------------------------------------------
    yuan_mod = fu_tou_zhi_index % 3
    if yuan_mod == 0:
        yuan_index, yuan_name = 0, '上元'
    elif yuan_mod == 2:
        yuan_index, yuan_name = 1, '中元'
    else:
        yuan_index, yuan_name = 2, '下元'

    ding_ju = options.get('ding_ju', '拆补')
    if ding_ju not in constants.DING_JU_METHODS:
        ding_ju = '拆补'

    table_jq = jie_qi_name
    run_qi = False
    note_parts = [f'{ding_ju}法', chao['note']]
    if ding_ju == '置闰':
        # 以完整三元（15 天）为一段，段界是不晚于当日的最近上元符头；
        # 用该段起点所属节气查局数表，段内节气交接不中途换表。
        # 超神（符头先到）与接气（符头未到）自然沿用旧节气之局。
        segment = _shang_yuan_segment(date)
        table_jq, _ = timeutil.current_jie_qi(segment)
        if chao['run_qi']:
            table_jq = jie_qi_name
            run_qi = True
            note_parts.append('闰奇：重复本节气三元，使符头与节气重新对齐')
        elif table_jq != jie_qi_name:
            note_parts.append(
                f'三元段起 {segment.strftime("%m-%d")} 属{table_jq}，沿用其局')
    note_parts.append(f'符头 {fu_tou_zhi} 日定{yuan_name}')

    info = constants.JIE_QI_JU_MAP.get(table_jq)
    if info:
        dun_type = info['type']
        ju_num = info['yuan'][yuan_index]
        dun_name = '阳遁' if dun_type == 'yang' else '阴遁'
        chao_out['runQi'] = run_qi
        return {
            'jieQiName': jie_qi_name,
            'tableJieQi': table_jq,
            'type': dun_type,
            'number': str(ju_num),
            'yuan': yuan_name,
            'fullName': f'{dun_name}{ju_num}局 ({yuan_name})',
            'formatCode': f'{dun_type}-{ju_num}',
            'note': '；'.join(note_parts),
            'chaoJie': chao_out,
        }

    return {
        'jieQiName': jie_qi_name,
        'tableJieQi': table_jq,
        'type': 'yang',
        'number': '1',
        'yuan': '上元',
        'fullName': f'阳遁1局 (默认, 未知节气{jie_qi_name})',
        'formatCode': 'yang-1',
        'note': '；'.join(note_parts),
        'chaoJie': chao_out,
    }


def distribute_san_qi_liu_yi(ju_shu):
    """
    排布三奇六仪 (地盘)
    :param ju_shu: 局数信息
    :return: 三奇六仪分布
    """
    # 顺序：戊 己 庚 辛 壬 癸 丁 丙 乙
    gan_list = ['戊', '己', '庚', '辛', '壬', '癸', '丁', '丙', '乙']
    
    dun_type = ju_shu['type'] # 'yang' or 'yin'
    start_gong = int(ju_shu['number'])
    
    result = {}
    
    current_gong = start_gong
    
    for gan in gan_list:
        result[str(current_gong)] = gan
        
        if dun_type == 'yang':
            current_gong += 1
            if current_gong > 9:
                current_gong = 1
        else:
            current_gong -= 1
            if current_gong < 1:
                current_gong = 9
                
    return result

def get_xun_shou(lunar, method, year_gz=None):
    """
    获取旬首
    :param lunar: Lunar对象
    :param method: 排盘方法
    :param year_gz: 年柱（按选定分界），年家用；为空时退回农历年
    :return: 旬首天干
    """
    # 根据排盘方法选择不同的干支
    if method == '年家':
        gan_zhi = year_gz or lunar.getYearInGanZhi()
    elif method == '月家':
        gan_zhi = lunar.getMonthInGanZhi()
    elif method == '日家':
        gan_zhi = lunar.getDayInGanZhi()
    else:
        # 时家
        gan_zhi = lunar.getTimeInGanZhi()
        
    # 统一计算旬首
    # 60甲子表
    jia_zi_list = [
        "甲子", "乙丑", "丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉",
        "甲戌", "乙亥", "丙子", "丁丑", "戊寅", "己卯", "庚辰", "辛巳", "壬午", "癸未",
        "甲申", "乙酉", "丙戌", "丁亥", "戊子", "己丑", "庚寅", "辛卯", "壬辰", "癸巳",
        "甲午", "乙未", "丙申", "丁酉", "戊戌", "己亥", "庚子", "辛丑", "壬寅", "癸卯",
        "甲辰", "乙巳", "丙午", "丁未", "戊申", "己酉", "庚戌", "辛亥", "壬子", "癸丑",
        "甲寅", "乙卯", "丙辰", "丁巳", "戊午", "己未", "庚申", "辛酉", "壬戌", "癸亥"
    ]
    
    try:
        idx = jia_zi_list.index(gan_zhi)
        # 旬首索引 = (idx // 10) * 10
        xun_shou_idx = (idx // 10) * 10
        xun_shou_gan_zhi = jia_zi_list[xun_shou_idx]
        
        # 映射到六仪
        return constants.XUN_SHOU_MAP.get(xun_shou_gan_zhi, '')
    except ValueError:
        return ''

def get_luo_gong_gan_zhi(lunar, method, year_gz=None):
    """
    获取落宫干 (当前分析的天干)
    :param lunar: 农历对象
    :param method: 方法
    :param year_gz: 年柱（按选定分界），年家用；为空时退回农历年
    :return: 落宫天干
    """
    if method == '年家':
        return (year_gz or lunar.getYearInGanZhi())[0]
    elif method == '月家':
        return lunar.getMonthGan()
    elif method == '日家':
        return lunar.getDayGan()
    else:
        # 时家
        return lunar.getTimeGan()

def _xun_kong(gan_zhi):
    """按六十甲子旬首统一计算旬空，四家一致。

    例：甲子旬（idx=0）空戌亥；甲戌旬（idx=10）空申酉。
    不依赖 ``lunar-python`` 各柱 XunKong 接口，避免年柱按立春分界后
    仍取农历年旬空的错配。
    """
    try:
        idx = constants.LIU_SHI_HUA_JIA_ZI.index(gan_zhi)
    except ValueError:
        return ''
    zhi_idx = idx % 12
    return DI_ZHI[(zhi_idx + 10) % 12] + DI_ZHI[(zhi_idx + 11) % 12]


def get_kong_wang(lunar, method, gan_zhi=None):
    """
    获取空亡（旬空）地支。
    :param gan_zhi: 本柱干支；给出时按统一旬空算法计算
    """
    if gan_zhi:
        return _xun_kong(gan_zhi)
    if method == '年家':
        return _xun_kong(lunar.getYearInGanZhi())
    elif method == '月家':
        return _xun_kong(lunar.getMonthInGanZhi())
    elif method == '日家':
        return _xun_kong(lunar.getDayInGanZhi())
    else:
        return _xun_kong(lunar.getTimeInGanZhi())

def get_kong_wang_gong(kong_wang_zhi):
    """
    获取空亡宫位
    :param kong_wang_zhi: 空亡地支
    :return: 空亡宫位
    """
    # 地支对应宫位
    gongs = set()
    for char in kong_wang_zhi:
        if char in constants.ZHI_GONG_MAP:
            gongs.add(constants.ZHI_GONG_MAP[char])
            
    return list(gongs)

def analyze_gong(gong, jiu_xing, ba_men, ba_shen,
                 tian_gan='', an_gan='', marks=None, yi_ma=None):
    """
    分析宫位吉凶，并附上暗干、驿马与格局标注。
    """
    marks = marks or []
    xing = jiu_xing.get(gong, '')
    men = ba_men.get(gong, '')
    shen = ba_shen.get(gong, '')

    # 简化的吉凶判断逻辑
    ji_xiong = 'ping'
    ji_xiong_text = '平'

    if men in ['开门', '休门', '生门', '景门']:
        ji_xiong = 'ji'
        ji_xiong_text = '吉'
    elif men in ['死门', '惊门', '伤门', '杜门']:
        ji_xiong = 'xiong'
        ji_xiong_text = '凶'

    xing_info = JIU_XING.get(xing, {})
    xing_alias = xing_info.get('alias', '')
    geju_text = '；'.join(m['desc'] for m in marks)

    # ba_men / ba_shen 是「宫位 -> 名称」映射；门的说明应查 BA_MEN 元数据表，
    # 旧代码用宫号映射去查门名，导致说明恒为空串。
    # 中宫无门无神，另给断语，避免出现「天禽与同宫，临之。」这类空挂文案。
    if not men and not shen:
        explain = f'中宫无门无神，{xing}寄坤二宫，为全局枢纽。'
    else:
        explain = (f'{xing}与{men}同宫，{shen}临之。'
                   f'{BA_MEN.get(men, {}).get("feature", "")}')
    if geju_text:
        explain += f' 格局：{geju_text}'

    return {
        'direction': JIU_GONG[gong]['direction'],
        'gongName': JIU_GONG[gong]['name'],
        'jiXiong': ji_xiong,
        'jiXiongText': ji_xiong_text,
        'xing': xing,
        'xingAlias': xing_alias,
        'men': men,
        'shen': shen,
        'tianGan': tian_gan,
        'anGan': an_gan,
        'marks': marks,
        'markKeys': [m['key'] for m in marks],
        'geJuText': geju_text,
        'yiMa': bool(yi_ma and yi_ma['gong'] == gong),
        'explain': explain,
    }

def overall_analysis(jiu_gong_analysis, zhi_fu_gong, zhi_shi_gong, purpose):
    """
    综合分析
    :param jiu_gong_analysis: 九宫分析
    :param zhi_fu_gong: 值符宫
    :param zhi_shi_gong: 值使宫
    :param purpose: 目的
    :return: 分析结果
    """
    # 简化的综合分析
    suggestions = []
    
    # 根据目的给出建议
    if purpose == '事业':
        suggestions.append('事业方面，关注开门落宫。')
    elif purpose == '财运':
        suggestions.append('财运方面，关注生门落宫。')
    else:
        suggestions.append('综合运势平稳。')
        
    suggestions.append(f'值符在{zhi_fu_gong}宫，值使在{zhi_shi_gong}宫，为关键信息。')
    
    # 寻找吉宫
    best_gong = '1'
    for gong, analysis in jiu_gong_analysis.items():
        if analysis['jiXiong'] == 'ji':
            best_gong = gong
            suggestions.append(f'{analysis["direction"]}({analysis["gongName"]}宫)为吉方，利于行事。')
            break
            
    return {
        'overallJiXiong': 'ping',
        'overallJiXiongText': '平',
        'suggestions': suggestions,
        'bestGong': best_gong
    }

def calculate(date, options=None):
    """
    奇门遁甲计算主函数。

    选项（全部可选，缺省即保持原有行为）：
    - ``longitude`` / ``eot``：真太阳时校正（东经度、是否叠加均时差）
    - ``late_zi``：23 点晚子时日柱进位（默认启用，修复四柱错配）
    - ``year_rule``：年柱分界，「立春」（默认）或「正月」
    - ``ding_ju``：时家定局法「拆补」（默认）或「置闰」
    - ``ri_run``：日家逾三元时「延续」（默认置闰续元）或「周而复始」
    """
    if options is None:
        options = {}

    default_options = {
        'type': '四柱',
        'method': '时家',
        'purpose': '综合',
        'location': '默认位置',
        'longitude': None,
        'eot': True,
        'late_zi': True,
        'year_rule': '立春',
        'ding_ju': '拆补',
        'ri_run': '延续',
    }
    opts = {**default_options, **options}
    method = opts['method']
    if method not in ('时家', '日家', '月家', '年家'):
        method = '时家'
    if opts['year_rule'] not in constants.YEAR_RULES:
        opts['year_rule'] = '立春'
    if opts['ding_ju'] not in constants.DING_JU_METHODS:
        opts['ding_ju'] = '拆补'
    if opts['ri_run'] not in constants.RI_RUN_MODES:
        opts['ri_run'] = '延续'

    try:
        # 1. 时间层：真太阳时 → 晚子时进位 → 精确节气交接
        tc = timeutil.resolve_time(date, opts)
        pan_date = tc['pan']
        lunar = Lunar.fromDate(pan_date)
        jq_name, jq_time = timeutil.current_jie_qi(tc['solar'])

        # 2. 四柱年柱按选定分界，年家太岁同步
        year_gz = (lunar.getYearInGanZhiByLiChun()
                   if opts['year_rule'] == '立春'
                   else lunar.getYearInGanZhi())
        si_zhu = {
            'year': year_gz,
            'month': lunar.getMonthInGanZhi(),
            'day': lunar.getDayInGanZhi(),
            'time': lunar.getTimeInGanZhi(),
        }

        # 3. 定局
        ju_shu = calculate_ju_shu(pan_date, method, opts, jq_name, jq_time)

        # 4. 旬首、本柱、落宫干、旬空
        xun_shou_stem = get_xun_shou(lunar, method, year_gz)
        xun_shou = {
            '戊': '戊 (甲子元帅)', '己': '己 (甲戌元帅)',
            '庚': '庚 (甲申元帅)', '辛': '辛 (甲午元帅)',
            '壬': '壬 (甲辰元帅)', '癸': '癸 (甲寅元帅)',
        }.get(xun_shou_stem, xun_shou_stem)

        if method == '年家':
            current_gan_zhi = year_gz
        elif method == '月家':
            current_gan_zhi = lunar.getMonthInGanZhi()
        elif method == '日家':
            current_gan_zhi = lunar.getDayInGanZhi()
        else:
            current_gan_zhi = lunar.getTimeInGanZhi()

        jia_zi = constants.LIU_SHI_HUA_JIA_ZI
        try:
            curr_idx = jia_zi.index(current_gan_zhi)
        except ValueError:
            curr_idx = 0
        xun_idx = (curr_idx // 10) * 10
        offset = curr_idx - xun_idx

        luo_gong_gan = get_luo_gong_gan_zhi(lunar, method, year_gz)
        if luo_gong_gan == '甲':
            luo_gong_gan = xun_shou_stem

        kong_wang_zhi = get_kong_wang(lunar, method, current_gan_zhi)
        kong_wang_gong = get_kong_wang_gong(kong_wang_zhi)

        # 5. 四盘
        san_qi_liu_yi = distribute_san_qi_liu_yi(ju_shu)
        jiu_xing_result = jiu_xing_module.distribute_jiu_xing(
            san_qi_liu_yi, xun_shou_stem, luo_gong_gan)

        star_origin = {
            '天蓬': '1', '天芮': '2', '天冲': '3', '天辅': '4',
            '天禽': '5', '天心': '6', '天柱': '7', '天任': '8', '天英': '9',
        }
        tian_pan_gan = {}
        for gong, star in jiu_xing_result['jiu_xing'].items():
            if gong == '5':
                continue
            origin_gong = star_origin.get(star)
            if not origin_gong:
                continue
            stem = san_qi_liu_yi.get(origin_gong, '')
            if star == '天芮':
                stem_5 = san_qi_liu_yi.get('5', '')
                if stem_5:
                    stem = f'{stem}{stem_5}'
            tian_pan_gan[gong] = stem

        zhi_gong = None
        if method == '年家':
            zhi_gong = constants.ZHI_GONG_MAP.get(year_gz[1])
        elif method == '月家':
            zhi_gong = constants.ZHI_GONG_MAP.get(lunar.getMonthZhi())
        elif method == '日家':
            zhi_gong = constants.ZHI_GONG_MAP.get(lunar.getDayZhi())
        ba_men_result = ba_men_module.distribute_ba_men(
            san_qi_liu_yi, xun_shou_stem, offset, ju_shu['type'], zhi_gong)
        ba_shen = ba_shen_module.distribute_ba_shen(
            jiu_xing_result['zhi_fu_gong'], ju_shu['type'])

        # 6. 暗干、驿马与格局标注
        an_gan = geju.distribute_an_gan(
            san_qi_liu_yi, ba_men_result['zhi_shi_gong'],
            luo_gong_gan, ju_shu['type'])
        anchor_zhi = {
            '年家': year_gz[1],
            '月家': lunar.getMonthZhi(),
            '日家': lunar.getDayZhi(),
        }.get(method, lunar.getTimeZhi())
        yi_ma = geju.yi_ma_of(anchor_zhi)

        jiu_gong_analysis = {}
        for i in range(1, 10):
            gong = str(i)
            marks = geju.analyze_marks(
                gong,
                tian_pan_gan.get(gong, ''),
                ba_men_result['ba_men'].get(gong, ''),
                kong_wang_gong,
                yi_ma,
            )
            jiu_gong_analysis[gong] = analyze_gong(
                gong, jiu_xing_result['jiu_xing'],
                ba_men_result['ba_men'], ba_shen,
                tian_pan_gan.get(gong, ''),
                an_gan['anGan'].get(gong, ''),
                marks, yi_ma,
            )

        analysis = overall_analysis(
            jiu_gong_analysis, jiu_xing_result['zhi_fu_gong'],
            ba_men_result['zhi_shi_gong'], opts['purpose'])

        mark_count = Counter(
            m['key'] for a in jiu_gong_analysis.values() for m in a['marks'])
        mark_summary = ' · '.join(
            f'{k}{mark_count[k]}'
            for k in ('刑', '墓', '迫', '制', '空', '马') if mark_count[k]
        ) or '本盘无格局标注'

        # 7. 中宫值符星表述（教材异名）
        xun_gong = next(
            (g for g, v in san_qi_liu_yi.items() if v == xun_shou_stem), '')
        zhi_fu_note = (
            '旬首落中宫，天禽寄坤二与天芮同宫；本盘值符星记作天芮，'
            '部分教材记作天禽，属同一落宫的不同表述'
        ) if xun_gong == '5' else ''

        time_info = {
            'raw': date.strftime('%Y-%m-%d %H:%M'),
            'solar': tc['solar'].strftime('%Y-%m-%d %H:%M'),
            'pan': pan_date.strftime('%Y-%m-%d %H:%M'),
            'longitude': tc['longitude'],
            'eot': tc['use_eot'],
            'offsetMinutes': round(tc['offset_minutes'], 2),
            'eotMinutes': round(tc['eot_minutes'], 2),
            'lateZi': tc['late_zi'],
            'lateZiHit': tc['late_zi_hit'],
            'jieQi': jq_name,
            'jieQiAt': jq_time.strftime('%Y-%m-%d %H:%M') if jq_time else '',
            'notes': tc['notes'],
            'summary': tc['summary'],
        }

        return {
            'basicInfo': {
                'date': f'{date.strftime("%Y年%m月%d日 %H:%M")}',
                'lunarDate': (f'{lunar.getYearShengXiao()}年 '
                              f'{lunar.getMonthInChinese()}月 '
                              f'{lunar.getDayInChinese()}'),
                'type': opts['type'],
                'method': method,
                'purpose': opts['purpose'],
                'location': opts['location'],
                'panDate': pan_date.strftime('%Y-%m-%d %H:%M'),
                'timeNote': tc['summary'],
            },
            'siZhu': si_zhu,
            'juShu': ju_shu,
            'xunShou': xun_shou,
            'luoGongGan': luo_gong_gan,
            'sanQiLiuYi': san_qi_liu_yi,
            'jiuXing': jiu_xing_result['jiu_xing'],
            'baMen': ba_men_result['ba_men'],
            'baShen': ba_shen,
            'diPan': san_qi_liu_yi,
            'tianPan': tian_pan_gan,
            'zhiFuGong': jiu_xing_result['zhi_fu_gong'],
            'zhiFuXing': jiu_xing_result['zhi_fu_xing'],
            'zhiFuXingNote': zhi_fu_note,
            'zhiShiGong': ba_men_result['zhi_shi_gong'],
            'zhiShiMen': ba_men_result['zhi_shi_men'],
            'kongWangZhi': kong_wang_zhi,
            'kongWangGong': kong_wang_gong,
            'anGan': an_gan['anGan'],
            'anGanRule': an_gan['rule'],
            'yiMa': yi_ma,
            'geJuLegend': [
                {'key': k, 'name': n, 'desc': d}
                for k, n, d in geju.GEJU_LEGEND
            ],
            'markSummary': mark_summary,
            'timeInfo': time_info,
            'options': {
                'longitude': tc['longitude'],
                'eot': bool(tc['use_eot']),
                'late_zi': bool(tc['late_zi']),
                'year_rule': opts['year_rule'],
                'ding_ju': opts['ding_ju'],
                'ri_run': opts['ri_run'],
            },
            'jiuGongAnalysis': jiu_gong_analysis,
            'analysis': analysis,
        }
    except Exception as e:
        print(f'奇门遁甲计算出错: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        try:
            error_msg = str(e)
        except Exception as str_error:
            print(f'str() function error: {str_error}')
            error_msg = repr(e)
        return {
            'error': True,
            'message': error_msg,
            'basicInfo': {
                'date': date.isoformat(),
                'type': opts['type'],
                'method': opts['method'],
                'purpose': opts['purpose'],
                'location': opts['location'],
            },
        }
