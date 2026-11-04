# 八神分布计算模块

def distribute_ba_shen(zhi_fu_gong, dun_type):
    """
    排布八神
    :param zhi_fu_gong: 值符宫 (天盘)
    :param dun_type: 阴阳遁 ('yin' or 'yang')
    :return: 八神分布
    """
    # 八神顺序
    shen_order = ['值符', '腾蛇', '太阴', '六合', '白虎', '玄武', '九地', '九天']

    # 宫位顺序（顺时针，不含中宫）
    clockwise_gong_order = ['1', '8', '3', '4', '9', '2', '7', '6']
    # 宫位顺序（逆时针，不含中宫）
    anticlockwise_gong_order = ['1', '6', '7', '2', '9', '4', '3', '8']

    # 八神分布结果
    ba_shen = {
        '1': '',
        '2': '',
        '3': '',
        '4': '',
        '5': '',  # 中宫没有神
        '6': '',
        '7': '',
        '8': '',
        '9': ''
    }
    
    # 如果值符宫在中宫(5)，通常寄坤宫(2)
    if zhi_fu_gong == '5':
        zhi_fu_gong = '2'

    # 值符在值符宫
    ba_shen[zhi_fu_gong] = '值符'

    # 值符宫在宫序中的位置
    try:
        zhi_fu_gong_index = clockwise_gong_order.index(zhi_fu_gong)
    except ValueError:
        zhi_fu_gong_index = 0

    # 排列其他神
    for i in range(1, 8):
        if dun_type == 'yang':
            # 阳遁：宫顺时针排，神顺排
            current_gong = clockwise_gong_order[(zhi_fu_gong_index + i) % 8]
            current_shen = shen_order[i]
        else:
            # 阴遁：宫逆时针排，神顺排
            # 需要找到值符宫在逆时针宫序中的位置
            try:
                anti_index = anticlockwise_gong_order.index(zhi_fu_gong)
            except ValueError:
                anti_index = 0
            current_gong = anticlockwise_gong_order[(anti_index + i) % 8]
            current_shen = shen_order[i]
            
        ba_shen[current_gong] = current_shen

    return ba_shen