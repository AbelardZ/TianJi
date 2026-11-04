# 八门分布计算模块

def distribute_ba_men(san_qi_liu_yi, xun_shou, hour_offset, dun_type, zhi_gong=None):
    """
    排布八门
    :param san_qi_liu_yi: 三奇六仪分布 (地盘)
    :param xun_shou: 旬首
    :param hour_offset: 时辰偏移量 (当前时辰 - 旬首时辰)
    :param dun_type: 阴阳遁 ('yin' or 'yang')
    :param zhi_gong: 年／月／日家的地支落宫；为 None 时按时家旬内序号飞宫
    :return: 八门分布和值使信息
    """
    # 1. 确定值使门（原宫位）
    # 查找旬首所在宫 (地盘)
    zhi_shi_gong_origin = ''
    for gong, value in san_qi_liu_yi.items():
        if value == xun_shou:
            zhi_shi_gong_origin = gong
            break
            
    if not zhi_shi_gong_origin:
        zhi_shi_gong_origin = '5'
        
    # 如果在中宫，值使门为死门(2)
    if zhi_shi_gong_origin == '5':
        zhi_shi_gong_origin = '2'

    # 基本八门分布 (地盘八门)
    basic_gong_to_men = {
        '1': '休门',
        '8': '生门',
        '3': '伤门',
        '4': '杜门',
        '9': '景门',
        '2': '死门',
        '7': '惊门',
        '6': '开门'
    }
    
    zhi_shi_men = basic_gong_to_men.get(zhi_shi_gong_origin, '死门')
    
    # 2. 确定值使门落宫
    # 时家：值使随时支，按旬内序号从旬首宫起在九宫（含中宫）阳顺阴逆飞宫。
    # 年／月／日家：值使随该柱地支，直接加临地支对应的九宫地盘宫
    #   （子坎一、丑寅艮八、卯震三、辰巳巽四、午离九、未申坤二、酉兑七、戌亥乾六）。
    if zhi_gong:
        target_gong = zhi_gong
    else:
        start_pos = int(zhi_shi_gong_origin)
        if dun_type == 'yang':
            # 阳遁顺行
            current_pos = (start_pos + hour_offset - 1) % 9 + 1
        else:
            # 阴遁逆行
            current_pos = start_pos - hour_offset
            while current_pos < 1:
                current_pos += 9
        target_gong = str(current_pos)

    # 落入中宫(5)寄坤宫(2)
    if target_gong == '5':
        target_gong = '2'

    # 3. 排布八门
    # 八门顺序（顺时针）
    men_order = ['休门', '生门', '伤门', '杜门', '景门', '死门', '惊门', '开门']
    # 宫位顺序（顺时针，不含中宫）
    gong_order = ['1', '8', '3', '4', '9', '2', '7', '6']
    
    ba_men = {}
    ba_men['5'] = '' # 中宫无门
    
    try:
        men_index = men_order.index(zhi_shi_men)
    except ValueError:
        men_index = 0
        
    try:
        gong_index = gong_order.index(target_gong)
    except ValueError:
        gong_index = 0
        
    # 顺排
    for i in range(8):
        current_gong = gong_order[(gong_index + i) % 8]
        current_men = men_order[(men_index + i) % 8]
        ba_men[current_gong] = current_men

    return {
        'zhi_shi_gong': target_gong,
        'zhi_shi_men': zhi_shi_men,
        'ba_men': ba_men
    }