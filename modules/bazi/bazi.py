# -*- coding: utf-8 -*-
# 八字排盘系统 - 排盘逻辑模块

import io
import sxtwl
from datetime import datetime, timedelta

from .bazi_data import (
    TIANGAN,
    DIZHI,
    GAN_INDEX,
    ZHI_INDEX,
    YINYANG_GAN,
    GAN_WUXING,
    ZHI_WUXING,
    WUXING_ORDER,
    SHENG,
    KE,
    CANG_GAN,
    get_shishen,
    get_nayin,
    TAOHUA,
    YIMA,
    HUAGAI,
    JIANGXING,
    JIESHA,
    WANGSHEN,
    GUCHEN,
    GUASU,
    TIANYI,
    WENCHANG,
    LUSHEN,
    YANGREN,
    HONGLUAN,
    TIANXI,
    JINYU,
    YANG_GAN,
    WUHUDUN,
)


# 二十四节气（sxtwl 索引从冬至起）
JIEQI_NAMES = [
    "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
    "春分", "清明", "谷雨", "立夏", "小满", "芒种",
    "夏至", "小暑", "大暑", "立秋", "处暑", "白露",
    "秋分", "寒露", "霜降", "立冬", "小雪", "大雪",
]
# 起大运只数“节”（奇数位），不数“气”
JIE_INDICES = {i for i in range(24) if i % 2 == 1}
# 流月（寅月→丑月）各自起始的“节”在 JIEQI_NAMES 中的下标
JIE_FOR_MONTH = [(3 + 2 * i) % 24 for i in range(12)]

CHANGSHENG_STAGES = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
CHANGSHENG_START = {
    "甲": ("亥", 1), "乙": ("午", -1), "丙": ("寅", 1), "丁": ("酉", -1),
    "戊": ("寅", 1), "己": ("酉", -1), "庚": ("巳", 1), "辛": ("子", -1),
    "壬": ("申", 1), "癸": ("卯", -1),
}


def _lunar_month_cn(m):
    return ["正", "二", "三", "四", "五", "六",
            "七", "八", "九", "十", "冬", "腊"][m - 1] + "月"


def _lunar_day_cn(d):
    if d == 10:
        return "初十"
    if d == 20:
        return "二十"
    if d == 30:
        return "三十"
    tens = ["初", "十", "廿", "三"][d // 10]
    ones = ["一", "二", "三", "四", "五", "六", "七", "八", "九"][d % 10 - 1]
    return tens + ones


def _jiazi_num(gz):
    """返回干支在六十甲子中的序号（0 起）。"""
    g = GAN_INDEX[gz[0]]
    z = ZHI_INDEX[gz[1]]
    return g + 10 * (((g - z) // 2) % 6)


def _gz_at(n):
    n %= 60
    return TIANGAN[n % 10] + DIZHI[n % 12]


def _next_gz(gz):
    return _gz_at(_jiazi_num(gz) + 1)


def _prev_gz(gz):
    return _gz_at(_jiazi_num(gz) - 1)


def _xunkong(gz):
    """按六甲旬空计算某柱的空亡（返回两个地支）。"""
    n = _jiazi_num(gz)
    n0 = n - (n % 10)
    return DIZHI[(n0 + 10) % 12] + DIZHI[(n0 + 11) % 12]


def _changsheng(gan, zhi):
    """返回天干在地支的十二长生阶段。"""
    start_zhi, direction = CHANGSHENG_START[gan]
    distance = (ZHI_INDEX[zhi] - ZHI_INDEX[start_zhi]) % 12
    if direction < 0:
        distance = (-distance) % 12
    return CHANGSHENG_STAGES[distance]


def _year_gz(year):
    """取公历年份对应的年柱干支（以立春为界，2 月中旬必然已过立春）。"""
    day_obj = sxtwl.fromSolar(year, 2, 15)
    # 注意：此 sxtwl 版本中 getYearGZ(False) 才是以立春为界
    gz = day_obj.getYearGZ(False)
    return TIANGAN[gz.tg] + DIZHI[gz.dz]


def _jieqi_of_year(year):
    """返回该流年（立春→次年立春）十二个“节”的公历日期，键为节气下标。"""
    dates = {}
    for info in sxtwl.getJieQiByYear(year):
        if info.jqIndex in JIE_INDICES and info.jqIndex not in dates:
            day = sxtwl.JD2DD(info.jd)
            dates[info.jqIndex] = f"{day.Y:04d}-{day.M:02d}-{day.D:02d}"
    return dates


def _liuyue(year):
    """返回指定流年的十二个月干支，并标注该月起始的节气与公历日期。"""
    year_gan = _year_gz(year)[0]
    base = WUHUDUN[year_gan]
    jie_dates = _jieqi_of_year(year)
    months = []
    for index in range(12):
        gz = TIANGAN[(base + index) % 10] + DIZHI[(2 + index) % 12]
        jie_index = JIE_FOR_MONTH[index]
        jie_date = jie_dates.get(jie_index, "")
        months.append({
            "month": index + 1,
            "ganzhi": gz,
            "gan_wuxing": GAN_WUXING[gz[0]],
            "zhi_wuxing": ZHI_WUXING[gz[1]],
            "jieqi": JIEQI_NAMES[jie_index],
            "jieqi_date": jie_date,
            "jieqi_md": f"{int(jie_date[5:7])}/{int(jie_date[8:10])}" if jie_date else "",
        })
    return months


class bazi:
    """八字排盘主类。

    职责：
    - 接收公历时间与性别，计算年月日时四柱（可用干支覆盖）。
    - 计算十神、藏干、纳音、空亡、神煞、五行统计与旺衰。
    - 计算胎元、命宫、身宫，并按阳男阴女顺逆规则排大运。
    - 生成结构化的排盘数据与文本排盘。

    主要属性：
    - birth: 出生公历时间（datetime）。
    - pillars: 四柱列表（年/月/日/时），每柱含干支、十神、藏干、纳音、空亡、神煞。
    - dayun_list: 大运列表；liunian_list: 流年列表。
    """

    def __init__(self):
        self.subject = ""
        self.gender = "男"
        self.birth = None
        self.effective = None
        self.solar_minutes = 0
        self.hour_unknown = False
        self._birth_jd = None
        self.lunar_str = ""
        self.pillars_raw = []
        self.pillars = []
        self.day_master = ""
        self.day_wuxing = ""
        self.month_element = ""
        self.wuxing_counts = {}
        self.wuxing_hidden = {}
        self.wangshuai = {}
        self.strength_label = ""
        self.strength_support = 0
        self.strength_oppose = 0
        self.taiyuan = ""
        self.minggong = ""
        self.shengong = ""
        self.dayun_direction = ""
        self.dayun_start_age = ""
        self.dayun_start_date = ""
        self.jieqi_note = ""
        self.dayun_list = []
        self.liunian_list = []
        self.shensha_summary = []

    def date(self, year=None, month=None, day=None, hour=None, minute=None,
             gz_year=None, gz_month=None, gz_day=None, gz_hour=None,
             solar_minutes=0, hour_unknown=False):
        """计算四柱。

        - 未提供日期时取当前时间；提供干支则覆盖自动结果。
        - solar_minutes 为手动输入的真太阳时校正（分钟，可正可负），不做出生地自动校准。
        - hour_unknown 为 True 时忽略时柱（时柱未知）。
        """
        if year is None or month is None or day is None:
            now = datetime.now()
            year, month, day = now.year, now.month, now.day
            hour = now.hour if hour is None else hour
            minute = now.minute if minute is None else minute
        hour = hour or 0
        minute = minute or 0
        self.hour_unknown = bool(hour_unknown)
        self.solar_minutes = 0 if self.hour_unknown else int(solar_minutes or 0)
        try:
            self.birth = datetime(year, month, day, hour, minute)
        except ValueError:
            raise ValueError("无效的日期")
        self.effective = self.birth + timedelta(minutes=self.solar_minutes)
        eff = self.effective
        self._birth_jd = sxtwl.toJD(sxtwl.Time(eff.year, eff.month, eff.day, eff.hour, eff.minute, 0))

        day_obj = sxtwl.fromSolar(eff.year, eff.month, eff.day)

        def gz2(g):
            return TIANGAN[g.tg] + DIZHI[g.dz]

        pillars = [
            gz2(day_obj.getYearGZ(False)),
            gz2(day_obj.getMonthGZ()),
            gz2(day_obj.getDayGZ()),
            "" if self.hour_unknown else gz2(day_obj.getHourGZ(eff.hour)),
        ]
        # 节气当天但早于节气精确时刻时，日粒度干支会超前，需回退一柱
        if day_obj.hasJieQi() and not self.hour_unknown:
            jie_idx = day_obj.getJieQi()
            if jie_idx in JIE_INDICES and self._birth_jd < day_obj.getJieQiJD():
                pillars[1] = _prev_gz(pillars[1])
                if JIEQI_NAMES[jie_idx] == "立春":
                    pillars[0] = _prev_gz(pillars[0])
        if self.hour_unknown:
            pillars[3] = "未知"
        if gz_year:
            pillars[0] = gz_year
        if gz_month:
            pillars[1] = gz_month
        if gz_day:
            pillars[2] = gz_day
        if gz_hour and not self.hour_unknown:
            pillars[3] = gz_hour
        self.pillars_raw = pillars
        self.day_master = pillars[2][0]
        self.day_wuxing = GAN_WUXING[self.day_master]

        leap = bool(day_obj.isLunarLeap())
        self.lunar_str = (
            f"{day_obj.getLunarYear()}年"
            f"{'闰' if leap else ''}"
            f"{_lunar_month_cn(day_obj.getLunarMonth())}"
            f"{_lunar_day_cn(day_obj.getLunarDay())}"
        )

    def compute(self):
        """在 date() 之后执行，生成完整的排盘数据。"""
        day_master = self.day_master
        year_gan = self.pillars_raw[0][0]
        year_zhi = self.pillars_raw[0][1]
        day_zhi = self.pillars_raw[2][1]

        pillars = []
        for idx, gz in enumerate(self.pillars_raw):
            if gz == "未知":
                pillars.append({
                    "gan": "未知",
                    "zhi": "未知",
                    "ganzhi": "未知",
                    "gan_wuxing": "",
                    "zhi_wuxing": "",
                    "canggan_wuxing": [],
                    "gan_shishen": "-",
                    "canggan": [],
                    "canggan_shishen": [],
                    "dishi": "-",
                    "zizuo": "-",
                    "nayin": "-",
                    "xunkong": "-",
                    "shensha": [],
                })
                continue
            gan, zhi = gz[0], gz[1]
            canggan = [c for c in CANG_GAN[zhi] if c]
            pillars.append({
                "gan": gan,
                "zhi": zhi,
                "ganzhi": gz,
                "gan_wuxing": GAN_WUXING[gan],
                "canggan_wuxing": [GAN_WUXING[c] for c in (CANG_GAN[zhi] if zhi != "未知" else []) if c],
                "gan_shishen": "日主" if idx == 2 else get_shishen(day_master, gan),
                "zhi_wuxing": ZHI_WUXING[zhi],
                "canggan": canggan,
                "canggan_shishen": [get_shishen(day_master, c) for c in canggan],
                "dishi": _changsheng(day_master, zhi),
                "zizuo": _changsheng(gan, zhi),
                "nayin": get_nayin(gz),
                "xunkong": _xunkong(gz),
                "shensha": self._shensha_for(zhi, year_gan, year_zhi, day_zhi, day_master),
            })
        self.pillars = pillars
        self._shensha_summary()

        self._wuxing_stats()
        self._taiyuan_minggong_shengong()
        self._dayun()
        self._liunian()

    def _shensha_summary(self):
        """汇总各柱神煞：每个神煞分别落在哪一柱。"""
        column_names = ["年柱", "月柱", "日柱", "时柱"]
        mapping = {}
        for idx, p in enumerate(self.pillars):
            for name in p["shensha"]:
                mapping.setdefault(name, []).append(column_names[idx])
        self.shensha_summary = [
            {"name": name, "positions": positions}
            for name, positions in mapping.items()
        ]

    def _shensha_for(self, zhi, year_gan, year_zhi, day_zhi, day_master):
        """收集落在某地支上的神煞。地支类以年支/日支为锚，天干类以日干为锚。"""
        found = []
        branch_tables = [
            ("桃花", TAOHUA), ("驿马", YIMA), ("华盖", HUAGAI),
            ("将星", JIANGXING), ("劫煞", JIESHA), ("亡神", WANGSHEN),
            ("孤辰", GUCHEN), ("寡宿", GUASU),
            ("红鸾", HONGLUAN), ("天喜", TIANXI),
        ]
        for anchor in (year_zhi, day_zhi):
            for name, table in branch_tables:
                if table.get(anchor) == zhi and name not in found:
                    found.append(name)

        stem_tables = [
            ("文昌", WENCHANG), ("禄神", LUSHEN),
            ("羊刃", YANGREN), ("金舆", JINYU),
        ]
        for name, table in stem_tables:
            val = table.get(day_master)
            if val == zhi and name not in found:
                found.append(name)

        for anchor in (year_gan, day_master):
            val = TIANYI.get(anchor)
            if isinstance(val, tuple):
                hit = zhi in val
            else:
                hit = val == zhi
            if hit and "天乙贵人" not in found:
                found.append("天乙贵人")
        return found

    def _wuxing_stats(self):
        counts = {e: 0 for e in WUXING_ORDER}
        hidden = {e: 0 for e in WUXING_ORDER}
        for p in self.pillars:
            if p["gan"] == "未知":
                continue
            counts[GAN_WUXING[p["gan"]]] += 1
            counts[ZHI_WUXING[p["zhi"]]] += 1
            for c in p["canggan"]:
                hidden[GAN_WUXING[c]] += 1
        self.wuxing_counts = counts
        self.wuxing_hidden = hidden
        self.month_element = self.pillars[1]["zhi_wuxing"]

        wang = {}
        for e in WUXING_ORDER:
            if e == self.month_element:
                wang[e] = "旺"
            elif SHENG[self.month_element] == e:
                wang[e] = "相"
            elif SHENG[e] == self.month_element:
                wang[e] = "休"
            elif KE[e] == self.month_element:
                wang[e] = "囚"
            else:
                wang[e] = "死"
        self.wangshuai = wang

        # 简易日主强弱：印比（生我+同我）与财官食伤（我生/我克/克我）的计数对比
        yin_element = next(e for e in WUXING_ORDER if SHENG[e] == self.day_wuxing)
        support = counts[self.day_wuxing] + counts[yin_element]
        oppose = 8 - support
        if self.hour_unknown:
            oppose = 6 - support
        self.strength_support = support
        self.strength_oppose = oppose
        if support > oppose:
            self.strength_label = "偏强"
        elif support < oppose:
            self.strength_label = "偏弱"
        else:
            self.strength_label = "中和"

    def _taiyuan_minggong_shengong(self):
        month_gz = self.pillars_raw[1]
        # 胎元 = 月干前一位 + 月支前三位
        tg = TIANGAN[(GAN_INDEX[month_gz[0]] + 1) % 10]
        tz = DIZHI[(ZHI_INDEX[month_gz[1]] + 3) % 12]
        self.taiyuan = tg + tz

        if self.hour_unknown:
            self.minggong = "未知"
            self.shengong = "未知"
            return

        # 命宫：子位起正月逆数至生月，再从生月位起子时顺数至生时
        m_num = ZHI_INDEX[month_gz[1]] + 1
        h_num = ZHI_INDEX[self.pillars_raw[3][1]] + 1
        ming_zhi_idx = ((13 - m_num) + (h_num - 1)) % 12
        # 身宫：子位起正月顺数至生月，再从生月位起子时逆数至生时
        shen_zhi_idx = (m_num - (h_num - 1)) % 12

        year_gan = self.pillars_raw[0][0]
        base = WUHUDUN[year_gan]
        ming_gan_idx = (base + ((ming_zhi_idx - 2) % 12)) % 10
        shen_gan_idx = (base + ((shen_zhi_idx - 2) % 12)) % 10
        self.minggong = TIANGAN[ming_gan_idx] + DIZHI[ming_zhi_idx]
        self.shengong = TIANGAN[shen_gan_idx] + DIZHI[shen_zhi_idx]

    def _find_next_jie(self):
        """找出生后的下一个“节”，返回 (日期, 节名, JD)。"""
        dt = self.birth.date()
        day_obj = sxtwl.fromSolar(dt.year, dt.month, dt.day)
        if (day_obj.hasJieQi() and day_obj.getJieQi() in JIE_INDICES
                and day_obj.getJieQiJD() > self._birth_jd):
            idx = day_obj.getJieQi()
            return dt, JIEQI_NAMES[idx], day_obj.getJieQiJD()
        for i in range(1, 40):
            cur = dt + timedelta(days=i)
            obj = sxtwl.fromSolar(cur.year, cur.month, cur.day)
            if obj.hasJieQi() and obj.getJieQi() in JIE_INDICES:
                idx = obj.getJieQi()
                return cur, JIEQI_NAMES[idx], obj.getJieQiJD()
        raise ValueError("未找到下一个节气")

    def _find_prev_jie(self):
        """找出生前的上一个“节”，返回 (日期, 节名, JD)。"""
        dt = self.birth.date()
        day_obj = sxtwl.fromSolar(dt.year, dt.month, dt.day)
        if (day_obj.hasJieQi() and day_obj.getJieQi() in JIE_INDICES
                and day_obj.getJieQiJD() < self._birth_jd):
            idx = day_obj.getJieQi()
            return dt, JIEQI_NAMES[idx], day_obj.getJieQiJD()
        for i in range(1, 40):
            cur = dt - timedelta(days=i)
            obj = sxtwl.fromSolar(cur.year, cur.month, cur.day)
            if obj.hasJieQi() and obj.getJieQi() in JIE_INDICES:
                idx = obj.getJieQi()
                return cur, JIEQI_NAMES[idx], obj.getJieQiJD()
        raise ValueError("未找到上一个节气")

    def _dayun(self):
        yang_year = self.pillars_raw[0][0] in YANG_GAN
        forward = (yang_year and self.gender == "男") or (not yang_year and self.gender == "女")
        self.dayun_direction = "顺行" if forward else "逆行"

        if forward:
            jie_day, jie_name, jie_jd = self._find_next_jie()
            diff_days = jie_jd - self._birth_jd
        else:
            jie_day, jie_name, jie_jd = self._find_prev_jie()
            diff_days = self._birth_jd - jie_jd

        total_days = max(diff_days, 0.0)
        # 3 天折 1 年，1 天折 4 个月，1 时辰(2 小时)折 10 天
        years = int(total_days // 3)
        rem = total_days - years * 3
        months = int(rem * 4)
        days = int(round((rem * 4 - months) * 30))
        if days >= 30:
            months += days // 30
            days %= 30
        if months >= 12:
            years += months // 12
            months %= 12
        self.dayun_start_age = f"{years}岁{months}个月{days}天"
        self.dayun_start_date = (self.birth + timedelta(days=total_days / 3.0 * 365.25)).strftime("%Y-%m-%d")
        self.jieqi_note = f"{jie_name}（{jie_day.strftime('%Y-%m-%d')}）"

        year_gan = self.pillars_raw[0][0]
        year_zhi = self.pillars_raw[0][1]
        day_zhi = self.pillars_raw[2][1]
        gz = self.pillars_raw[1]
        dayun = []
        for i in range(10):
            gz = _next_gz(gz) if forward else _prev_gz(gz)
            start_age = years + i * 10
            zhi = gz[1]
            canggan = [c for c in CANG_GAN[zhi] if c]
            dayun.append({
                "ganzhi": gz,
                "gan_wuxing": GAN_WUXING[gz[0]],
                "zhi_wuxing": ZHI_WUXING[zhi],
                "shishen": get_shishen(self.day_master, gz[0]),
                "nayin": get_nayin(gz),
                "canggan": canggan,
                "canggan_wuxing": [GAN_WUXING[c] for c in canggan],
                "canggan_shishen": [get_shishen(self.day_master, c) for c in canggan],
                "dishi": _changsheng(self.day_master, zhi),
                "zizuo": _changsheng(gz[0], zhi),
                "xunkong": _xunkong(gz),
                "shensha": self._shensha_for(zhi, year_gan, year_zhi, day_zhi, self.day_master),
                "age_start": start_age,
                "age_end": start_age + 9,
                "year_start": int(self.dayun_start_date[:4]) + i * 10,
                "year_end": int(self.dayun_start_date[:4]) + i * 10 + 9,
            })
        self.dayun_list = dayun

    def _age_for_year(self, year):
        """按大运的起运年份换算流年对应的岁数。"""
        for item in self.dayun_list:
            if item["year_start"] <= year <= item["year_end"]:
                return item["age_start"] + (year - item["year_start"])
        if self.dayun_list:
            first = self.dayun_list[0]
            return first["age_start"] + (year - first["year_start"])
        return year - self.birth.year + 1

    def _liunian(self):
        year_gan = self.pillars_raw[0][0]
        year_zhi = self.pillars_raw[0][1]
        day_zhi = self.pillars_raw[2][1]
        if self.dayun_list:
            first_year = min(item["year_start"] for item in self.dayun_list)
            last_year = max(item["year_end"] for item in self.dayun_list)
        else:
            current_year = datetime.now().year
            first_year, last_year = current_year, current_year + 9
        self.liunian_list = []
        for y in range(first_year, last_year + 1):
            gz = _year_gz(y)
            zhi = gz[1]
            canggan = [c for c in CANG_GAN[zhi] if c]
            liuyue = _liuyue(y)
            for month in liuyue:
                month_zhi = month["ganzhi"][1]
                month_canggan = [c for c in CANG_GAN[month_zhi] if c]
                month.update({
                    "shishen": get_shishen(self.day_master, month["ganzhi"][0]),
                    "nayin": get_nayin(month["ganzhi"]),
                    "canggan": month_canggan,
                    "canggan_wuxing": [GAN_WUXING[c] for c in month_canggan],
                    "canggan_shishen": [get_shishen(self.day_master, c) for c in month_canggan],
                    "dishi": _changsheng(self.day_master, month_zhi),
                    "zizuo": _changsheng(month["ganzhi"][0], month_zhi),
                    "xunkong": _xunkong(month["ganzhi"]),
                    "shensha": self._shensha_for(month_zhi, year_gan, year_zhi, day_zhi, self.day_master),
                })
            self.liunian_list.append({
                "year": y,
                "age": self._age_for_year(y),
                "ganzhi": gz,
                "gan_wuxing": GAN_WUXING[gz[0]],
                "zhi_wuxing": ZHI_WUXING[zhi],
                "shishen": get_shishen(self.day_master, gz[0]),
                "nayin": get_nayin(gz),
                "canggan": canggan,
                "canggan_wuxing": [GAN_WUXING[c] for c in canggan],
                "canggan_shishen": [get_shishen(self.day_master, c) for c in canggan],
                "dishi": _changsheng(self.day_master, zhi),
                "zizuo": _changsheng(gz[0], zhi),
                "xunkong": _xunkong(gz),
                "shensha": self._shensha_for(zhi, year_gan, year_zhi, day_zhi, self.day_master),
                "liuyue": liuyue,
            })

    def get_data(self):
        """返回结构化的排盘数据，用于前端渲染。"""
        t = self.birth
        eff = self.effective
        time_part = "" if self.hour_unknown else f" {t.hour:02d}:{t.minute:02d}"
        return {
            "date_str": f"{t.year}年{t.month:02d}月{t.day:02d}日{time_part}",
            "date_ymd": t.strftime("%Y-%m-%d"),
            "hour": t.hour,
            "minute": t.minute,
            "effective_str": f"{eff.year}年{eff.month:02d}月{eff.day:02d}日 {eff.hour:02d}:{eff.minute:02d}",
            "solar_minutes": self.solar_minutes,
            "hour_unknown": self.hour_unknown,
            "lunar_str": self.lunar_str,
            "lunar_month_day": self.lunar_str.split("年", 1)[1] if "年" in self.lunar_str else self.lunar_str,
            "gender": self.gender,
            "subject": self.subject,
            "day_master": {
                "gan": self.day_master,
                "wuxing": self.day_wuxing,
                "yinyang": YINYANG_GAN[self.day_master],
                "strength": self.strength_label,
                "support": self.strength_support,
                "oppose": self.strength_oppose,
            },
            "month_element": self.month_element,
            "pillars": self.pillars,
            "wuxing": {
                "counts": self.wuxing_counts,
                "hidden_counts": self.wuxing_hidden,
                "wangshuai": self.wangshuai,
            },
            "taiyuan": self.taiyuan,
            "minggong": self.minggong,
            "shengong": self.shengong,
            "dayun": {
                "direction": self.dayun_direction,
                "start_age": self.dayun_start_age,
                "start_date": self.dayun_start_date,
                "jieqi_note": self.jieqi_note,
                "list": self.dayun_list,
            },
            "liunian": self.liunian_list,
            "shensha_summary": self.shensha_summary,
        }

    def get_bazi_string(self):
        """生成文本版排盘（用于复制/下载）。"""
        out = io.StringIO()
        t = self.birth
        out.write(f"**八字排盘 - {self.subject or '未命名'}**\n\n")
        time_part = "" if self.hour_unknown else f" {t.hour:02d}:{t.minute:02d}"
        out.write(f"公历：{t.year}年{t.month:02d}月{t.day:02d}日{time_part}（{self.gender}）\n")
        if self.solar_minutes:
            eff = self.effective
            out.write(f"真太阳时校正：{self.solar_minutes:+d} 分钟 → {eff.year}年{eff.month:02d}月{eff.day:02d}日 {eff.hour:02d}:{eff.minute:02d}\n")
        if self.hour_unknown:
            out.write("时柱：未知（未纳入五行统计与命宫/身宫）\n")
        out.write(f"农历：{self.lunar_str}\n")
        out.write(f"四柱：{' '.join(self.pillars_raw)}\n\n")

        labels = ["年柱", "月柱", "日柱", "时柱"]
        rows = [
            ("天干", [p["gan"] for p in self.pillars]),
            ("十神", [p["gan_shishen"] for p in self.pillars]),
            ("地支", [p["zhi"] for p in self.pillars]),
            ("藏干", [" ".join(p["canggan"]) if p["canggan"] else "-" for p in self.pillars]),
            ("藏干十神", [" ".join(p["canggan_shishen"]) if p["canggan_shishen"] else "-" for p in self.pillars]),
            ("纳音", [p["nayin"] for p in self.pillars]),
            ("空亡", [p["xunkong"] for p in self.pillars]),
            ("神煞", [" ".join(p["shensha"]) if p["shensha"] else "-" for p in self.pillars]),
        ]
        out.write(f"{'':<8}" + "".join(f"{x:>10}" for x in labels) + "\n")
        for label, cells in rows:
            out.write(f"{label:<8}" + "".join(f"{x:>10}" for x in cells) + "\n")

        out.write("\n日主：" + f"{self.day_master}{self.day_wuxing}（{YINYANG_GAN[self.day_master]}）" +
                  f"  生于{self.month_element}月  简易强弱：{self.strength_label}"
                  f"（印比{self.strength_support} / 克泄耗{self.strength_oppose}）\n")
        counts_str = " ".join(f"{e}{self.wuxing_counts[e]}" for e in WUXING_ORDER)
        hidden_str = " ".join(f"{e}{self.wuxing_hidden[e]}" for e in WUXING_ORDER)
        wang_str = " ".join(f"{e}{self.wangshuai[e]}" for e in WUXING_ORDER)
        out.write(f"五行（八字）：{counts_str}\n")
        out.write(f"五行（含藏干）：{hidden_str}\n")
        out.write(f"月令旺衰：{wang_str}\n")
        out.write(f"胎元：{self.taiyuan}  命宫：{self.minggong}  身宫：{self.shengong}\n")
        out.write(f"大运（{self.dayun_direction}）：{self.dayun_start_age}起运"
                  f"（{self.dayun_start_date}，近节：{self.jieqi_note}）\n")
        for d in self.dayun_list:
            out.write(f"  {d['age_start']:>2}~{d['age_end']}岁  {d['ganzhi']}  "
                      f"{d['shishen']}  {d['nayin']}  {d['year_start']}-{d['year_end']}\n")
        out.write("流年：\n")
        for l in self.liunian_list:
            out.write(f"  {l['year']}（{l['age']:>2}岁）  {l['ganzhi']}  {l['shishen']}  {l['nayin']}\n")
        return out.getvalue()


def create_bazi(subject, gender, year, month, day, hour, minute,
                gz_year=None, gz_month=None, gz_day=None, gz_hour=None,
                solar_minutes=0, hour_unknown=False):
    """创建并返回已初始化的 bazi 对象。"""
    app = bazi()
    app.subject = subject
    app.gender = gender or "男"
    app.date(year, month, day, hour, minute, gz_year, gz_month, gz_day, gz_hour,
             solar_minutes, hour_unknown)
    app.compute()
    return app


def perform_bazi(subject, gender, year, month, day, hour, minute,
                 gz_year=None, gz_month=None, gz_day=None, gz_hour=None,
                 solar_minutes=0, hour_unknown=False):
    """执行八字排盘，返回 (app, text)。"""
    app = create_bazi(subject, gender, year, month, day, hour, minute,
                      gz_year, gz_month, gz_day, gz_hour, solar_minutes, hour_unknown)
    return app, app.get_bazi_string()
