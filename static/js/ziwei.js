/* ==========================================================================
   紫微斗数排盘 —— 前端逻辑（基于 iztro v2.6）
   关键：iztro 的 astrolabe.palaces 是按「地支顺序」排列的数组，
        不是按宫位顺序。因此必须依据 palace.earthlyBranch 把每个宫
        放到固定方位的网格上，否则盘面方位全错。
   ========================================================================== */
(function () {
    'use strict';

    /* ---------- 常量 ---------- */
    // 地支 → 网格区域（见 ziwei.css 的 grid-template-areas）
    var BRANCH_AREA = {
        '子': 'zi', '丑': 'chou', '寅': 'yin', '卯': 'mao',
        '辰': 'chen', '巳': 'si', '午': 'wu', '未': 'wei',
        '申': 'shen', '酉': 'you', '戌': 'xu', '亥': 'hai'
    };

    // 星曜类型 → 样式类
    var TYPE_CLASS = {
        major: 'major', soft: 'soft', tough: 'tough',
        flower: 'flower', helper: 'helper', lucun: 'lucun',
        tianma: 'tianma', adjective: 'adj'
    };

    // 天干 / 地支 五行（用于四柱着色，与八字页 c-* 类一致）
    var GAN_WX = {
        '甲': '木', '乙': '木', '丙': '火', '丁': '火', '戊': '土',
        '己': '土', '庚': '金', '辛': '金', '壬': '水', '癸': '水'
    };
    var ZHI_WX = {
        '子': '水', '丑': '土', '寅': '木', '卯': '木', '辰': '土', '巳': '火',
        '午': '火', '未': '土', '申': '金', '酉': '金', '戌': '土', '亥': '水'
    };

    var SCOPE_LABEL = {
        decadal: '大限', yearly: '流年', monthly: '流月',
        daily: '流日', hourly: '流时', age: '小限'
    };

    // 庙旺利陷分级 → 样式类（亮度按强弱上色）
    var BR_LEVEL = {
        '庙': 'miao', '旺': 'wang', '得': 'de', '利': 'li',
        '平': 'ping', '陷': 'xian', '不': 'xian'   // 「不」= 不得地，归为最弱（红）
    };

    // iztro 仅对 14 主星 + 昌曲火铃羊陀 返回 brightness；以下高频 graded 星
    // iztro 不输出，这里补一张标准庙旺利陷查表（按地支）。
    // 仅收录传统确有庙旺利陷评级的星；杂曜（天官天福等）不强行标注以免误导。
    var BRIGHTNESS_TABLE = {
        '左辅': { '辰':'庙','戌':'庙','丑':'庙','未':'庙','寅':'旺','申':'旺','午':'平','卯':'平','子':'陷','亥':'陷' },
        '右弼': { '辰':'庙','戌':'庙','丑':'庙','未':'庙','寅':'旺','申':'旺','午':'平','卯':'平','子':'陷','亥':'陷' },
        '天魁': { '寅':'庙','申':'庙','辰':'旺','戌':'旺','午':'平','未':'平','卯':'平','酉':'平','子':'陷','亥':'陷' },
        '天钺': { '卯':'庙','酉':'庙','巳':'旺','亥':'旺','寅':'平','申':'平','午':'平','未':'平','子':'陷' },
        '天空': { '辰':'庙','戌':'庙','丑':'旺','未':'旺','寅':'平','申':'平','子':'陷','亥':'陷' },
        '地空': { '辰':'庙','戌':'庙','丑':'旺','未':'旺','寅':'平','申':'平','子':'陷','亥':'陷' },
        '地劫': { '辰':'庙','戌':'庙','丑':'旺','未':'旺','寅':'平','申':'平','子':'陷','亥':'陷' }
    };

    /* ---------- 运行时状态 ---------- */
    var astrolabe = null;
    var horoscope = null;
    var currentScope = 'decadal';
    var currentDate = null;      // 运限基准日期
    var selectedIndex = null;    // 当前选中宫位（palaces 下标）
    var showAdj = true;          // 是否显示杂曜
    var shen12 = 'changsheng12'; // 底部十二神类型（对应 palace 属性名）
    var timeIndex = 0;           // 出生时辰下标

    /* ---------- 工具 ---------- */
    function $(id) { return document.getElementById(id); }

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    /** 公历小时 → iztro 时辰下标（0=子时…12=晚子时） */
    function hourToTimeIndex(h) {
        if (h === 23) return 12;
        if (h === 0) return 0;
        return Math.floor((h + 1) / 2);
    }

    function fmtDate(d) {
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var day = String(d.getDate()).padStart(2, '0');
        return d.getFullYear() + '-' + m + '-' + day;
    }

    /** 四化角标；scope=true 表示运限四化（描边样式） */
    function mutagenBadge(type, isScope) {
        var map = { '禄': 'lu', '权': 'quan', '科': 'ke', '忌': 'ji' };
        var key = map[type];
        if (!key) return '';
        return '<span class="zw-mu zw-mu-' + key + (isScope ? ' zw-mu-scope' : '') + '">' +
            esc(type) + '</span>';
    }

    /**
     * 单颗星 HTML。
     * @param {object} s 星曜
     * @param {object} muMap 运限四化 { 星名: '禄'|'权'|'科'|'忌' }
     * @param {boolean} isScopeStar 是否运限星（流年/大限叠加）
     * @param {string} branch 所在宫地支，用于查表补全 iztro 未给亮度的高频星
     */
    function starHtml(s, muMap, isScopeStar, branch) {
        var cls = 'zw-star zw-s-' + (TYPE_CLASS[s.type] || 'adj');
        if (isScopeStar) cls += ' zw-s-scope';
        var h = '<span class="' + cls + '">' + esc(s.name);
        // 亮度：优先用 iztro 自带，否则用查表（仅对确有评级的星）
        var br = s.brightness;
        if (!br && branch && BRIGHTNESS_TABLE[s.name]) br = BRIGHTNESS_TABLE[s.name][branch];
        if (br) {
            var lv = BR_LEVEL[br] || '';
            h += '<span class="zw-s-br' + (lv ? ' lv-' + lv : '') + '">' + esc(br) + '</span>';
        }
        if (s.mutagen) h += mutagenBadge(s.mutagen, false);
        if (muMap && muMap[s.name]) h += mutagenBadge(muMap[s.name], true);
        return h + '</span>';
    }

    /* ======================================================================
       排盘
       ====================================================================== */
    function render() {
        var rec = window.MINGLI_RECORD;
        if (!window.iztro || !rec || !rec.time) return;

        var t = String(rec.time);              // "YYYY-MM-DD HH:MM"
        var dateStr = t.slice(0, 10);
        var hour = parseInt(t.slice(11, 13), 10) || 0;
        timeIndex = hourToTimeIndex(hour);
        var gender = rec.gender || '男';

        try {
            if (iztro.astro && iztro.astro.config) {
                iztro.astro.config({
                    algorithm: 'default', yearDivide: 'normal', dayDivide: 'forward',
                    ageDivide: 'normal', horoscopeDivide: 'normal'
                });
            }
            astrolabe = iztro.astro.bySolar(dateStr, timeIndex, gender, true, 'zh-CN');
        } catch (e) {
            showError('排盘失败：' + e.message);
            return;
        }

        var empty = $('zwEmpty');
        if (empty) empty.style.display = 'none';
        ['zwToolbar', 'zwChartWrap', 'zwScopeDetail'].forEach(function (id) {
            var el = $(id);
            if (el) el.style.display = '';
        });

        currentDate = new Date();
        selectedIndex = null;
        computeHoroscope();   // 内部会调用 drawChart()
    }

    function showError(msg) {
        var empty = $('zwEmpty');
        if (!empty) return;
        empty.style.display = '';
        empty.innerHTML = '<div class="icon">紫</div><p>' + esc(msg) + '</p>';
        ['zwToolbar', 'zwChartWrap', 'zwScopeDetail', 'zwDetail'].forEach(function (id) {
            var el = $(id);
            if (el) el.style.display = 'none';
        });
    }

    /* ---------- 中宫 ---------- */
    function drawCenter() {
        var rec = window.MINGLI_RECORD || {};
        var pillars = String(astrolabe.chineseDate || '').trim().split(/\s+/);
        var labels = ['年柱', '月柱', '日柱', '时柱'];

        var pHtml = '';
        for (var i = 0; i < 4; i++) {
            var p = pillars[i] || '—';
            var gan = p.charAt(0) || '';
            var zhi = p.charAt(1) || '';
            var gc = GAN_WX[gan] ? ' c-' + GAN_WX[gan] : '';
            var zc = ZHI_WX[zhi] ? ' c-' + ZHI_WX[zhi] : '';
            pHtml +=
                '<div class="zw-c-pillar">' +
                '<span class="zw-c-gan' + gc + '">' + esc(gan) + '</span>' +
                '<span class="zw-c-zhi' + zc + '">' + esc(zhi) + '</span>' +
                '<span class="zw-c-label">' + labels[i] + '</span>' +
                '</div>';
        }

        var gCls = (rec.gender === '女') ? 'female' : 'male';
        var gIcon = (rec.gender === '女') ? '♀' : '♂';

        $('zwCenter').innerHTML =
            '<div class="zw-c-head">' +
                '<span class="zw-c-name">' + esc(rec.name || '未命名') + '</span>' +
                '<span class="zw-c-badge ' + gCls + '">' + gIcon + ' ' + esc(rec.gender || '男') + '</span>' +
                '<span class="zw-c-badge">' + esc(astrolabe.fiveElementsClass || '') + '</span>' +
            '</div>' +
            '<div class="zw-c-pillars">' + pHtml + '</div>' +
            '<dl class="zw-c-grid">' +
                '<dt>命主</dt><dd>' + esc(astrolabe.soul || '—') + '</dd>' +
                '<dt>身主</dt><dd>' + esc(astrolabe.body || '—') + '</dd>' +
                '<dt>生肖</dt><dd>' + esc(astrolabe.zodiac || '—') + '</dd>' +
                '<dt>星座</dt><dd>' + esc(astrolabe.sign || '—') + '</dd>' +
            '</dl>' +
            '<div class="zw-c-meta">' +
                '阳历 ' + esc(String(rec.time || '').slice(0, 10)) + '　' +
                esc(astrolabe.time || '') +
                (astrolabe.timeRange ? ' ' + esc(astrolabe.timeRange) : '') +
                '<br>农历 ' + esc(astrolabe.lunarDate || '') +
            '</div>';
    }

    /* ---------- 十二宫 ---------- */
    function drawChart() {
        drawCenter();

        var scope = horoscope ? horoscope[currentScope] : null;
        // 运限四化：mutagen = [禄, 权, 科, 忌]（星名）
        var muMap = {};
        if (scope && scope.mutagen) {
            var keys = ['禄', '权', '科', '忌'];
            for (var k = 0; k < 4; k++) {
                if (scope.mutagen[k]) muMap[scope.mutagen[k]] = keys[k];
            }
        }
        var scopeStars = (scope && scope.stars) ? scope.stars : null;

        var html = '';
        for (var i = 0; i < astrolabe.palaces.length; i++) {
            var p = astrolabe.palaces[i];
            var area = BRANCH_AREA[p.earthlyBranch];
            if (!area) continue;

            var cls = ['zw-palace', 'zw-b-' + area];
            if (p.name === '命宫') cls.push('is-soul');
            if (p.isBodyPalace) cls.push('is-body');
            if (p.isOriginalPalace) cls.push('is-original');
            if (scope && scope.index === i) cls.push('is-scope');
            if (selectedIndex !== null && isLinked(selectedIndex, i)) cls.push('is-linked');

            /* 头：大限 · 宫名 · 干支 */
            var head =
                '<div class="zw-p-head">' +
                    '<span class="zw-p-decadal">' +
                        esc(p.decadal.range[0]) + '-' + esc(p.decadal.range[1]) +
                    '</span>' +
                    '<span class="zw-p-name">' + esc(p.name) + '</span>' +
                    '<span class="zw-p-gz">' +
                        esc(p.heavenlyStem) + esc(p.earthlyBranch) +
                    '</span>' +
                '</div>';

            /* 主星：逐行，大字 */
            var major = '';
            for (var a = 0; a < p.majorStars.length; a++) {
                major += '<div class="zw-major-row">' +
                    starHtml(p.majorStars[a], muMap, false, p.earthlyBranch) + '</div>';
            }

            /* 辅曜 / 煞曜 / 桃花：并排一行 */
            var minor = '';
            for (var b = 0; b < p.minorStars.length; b++) {
                minor += starHtml(p.minorStars[b], muMap, false, p.earthlyBranch);
            }
            /* 运限星叠加 */
            if (scopeStars && scopeStars[i]) {
                for (var c = 0; c < scopeStars[i].length; c++) {
                    minor += starHtml(scopeStars[i][c], null, true, p.earthlyBranch);
                }
            }
            if (minor) minor = '<div class="zw-minor-row">' + minor + '</div>';

            /* 杂曜 */
            var adj = '';
            if (showAdj && p.adjectiveStars && p.adjectiveStars.length) {
                var adjHtml = '';
                for (var d = 0; d < p.adjectiveStars.length; d++) {
                    adjHtml += starHtml(p.adjectiveStars[d], null, false, p.earthlyBranch);
                }
                adj = '<div class="zw-adj-row">' + adjHtml + '</div>';
            }

            /* 空宫提示 */
            if (!p.majorStars.length) {
                major = '<div class="zw-major-row"><span class="zw-p-empty">空宫</span></div>' + major;
            }

            /* 脚：十二神 + 岁数 */
            var shen = p[shen12] || '';
            var foot =
                '<div class="zw-p-foot">' +
                    '<span class="zw-p-shen">' + esc(shen) + '</span>' +
                    '<span class="zw-p-ages">' + esc(p.ages.slice(0, 4).join(' ')) + '</span>' +
                '</div>';

            html += '<div class="' + cls.join(' ') + '" data-idx="' + i + '">' +
                head +
                '<div class="zw-p-stars">' + major + minor + adj + '</div>' +
                foot +
            '</div>';
        }

        var chart = $('zwChart');
        if (!chart) return;
        // 只替换宫位节点，保留中宫（#zwCenter）
        var old = chart.querySelectorAll('.zw-palace');
        for (var n = 0; n < old.length; n++) old[n].remove();
        chart.insertAdjacentHTML('beforeend', html);
    }

    /** 三合（财帛/官禄）或对宫 —— 用于联动高亮 */
    function isLinked(from, to) {
        if (from === to) return false;
        try {
            var sur = astrolabe.surroundedPalaces(astrolabe.palaces[from].name);
            var names = [];
            if (sur.opposite) names.push(sur.opposite.name);
            if (sur.wealth) names.push(sur.wealth.name);
            if (sur.career) names.push(sur.career.name);
            return names.indexOf(astrolabe.palaces[to].name) >= 0;
        } catch (e) { return false; }
    }

    /* ======================================================================
       运限
       ====================================================================== */
    function computeHoroscope() {
        try {
            horoscope = astrolabe.horoscope(fmtDate(currentDate), timeIndex);
        } catch (e) {
            horoscope = null;
            $('zwScopeDetail').innerHTML =
                '<span class="zw-d-hint">运限计算失败：' + esc(e.message) + '</span>';
            drawChart();   // 运限失败也要画出本命盘
            return;
        }
        renderScopeBar();
    }

    function renderScopeBar() {
        if (!horoscope) return;
        var s = horoscope[currentScope];
        if (!s) return;

        var sub = '';
        if (currentScope === 'yearly') sub = currentDate.getFullYear() + '年';
        else if (currentScope === 'monthly') sub = (currentDate.getMonth() + 1) + '月';
        else if (currentScope === 'daily') sub = fmtDate(currentDate);
        else if (currentScope === 'hourly') sub = fmtDate(currentDate) + ' ' + currentDate.getHours() + '时';
        else if (currentScope === 'decadal') {
            // 大限显示对应年龄区间，比重复干支更有信息量
            var dp = astrolabe.palaces[s.index];
            if (dp && dp.decadal) {
                sub = dp.decadal.range[0] + '-' + dp.decadal.range[1] + '岁';
            }
        }

        var ageTxt = '';
        if (horoscope.age && horoscope.age.nominalAge != null) {
            ageTxt = ' · ' + horoscope.age.nominalAge + '岁';
        }

        $('zwScopeLabel').innerHTML =
            '<b>' + esc(SCOPE_LABEL[currentScope]) + '</b> ' +
            esc(s.heavenlyStem + s.earthlyBranch) + ' · ' + esc(sub) + ageTxt;

        /* 详情：四化 + 落宫 + 运限星 */
        var mu = ['禄', '权', '科', '忌'];
        var muHtml = '';
        if (s.mutagen) {
            for (var i = 0; i < 4; i++) {
                if (s.mutagen[i]) {
                    muHtml += '<span>' + esc(mu[i]) + ' ' + esc(s.mutagen[i]) +
                        mutagenBadge(mu[i], true) + '</span>';
                }
            }
        }
        var palaceName = (s.palaceNames && s.palaceNames[s.index]) ? s.palaceNames[s.index] : '—';
        var scopeStarNames = [];
        if (s.stars) {
            s.stars.forEach(function (arr) {
                arr.forEach(function (st) { scopeStarNames.push(st.name); });
            });
        }

        $('zwScopeDetail').innerHTML =
            '<div class="zw-sd-title">' +
                esc(SCOPE_LABEL[currentScope]) + '　' +
                esc(s.heavenlyStem + s.earthlyBranch) +
                '<span class="zw-sd-sub">入「' + esc(palaceName) + '」</span>' +
            '</div>' +
            '<div class="zw-sd-row">' +
                '<span>四化：<span class="zw-sd-mu">' + (muHtml || '—') + '</span></span>' +
                '<span>运限星：<b>' + (scopeStarNames.length ? esc(scopeStarNames.join('、')) : '—') + '</b></span>' +
            '</div>';

        drawChart();
    }

    function setScope(scope) {
        currentScope = scope;
        var btns = document.querySelectorAll('#zwScopeSelect button');
        for (var i = 0; i < btns.length; i++) {
            btns[i].classList.toggle('active', btns[i].dataset.scope === scope);
        }
        renderScopeBar();
    }

    function stepScope(dir) {
        if (!currentDate) return;
        if (currentScope === 'decadal') currentDate.setFullYear(currentDate.getFullYear() + dir * 10);
        else if (currentScope === 'yearly') currentDate.setFullYear(currentDate.getFullYear() + dir);
        else if (currentScope === 'monthly') currentDate.setMonth(currentDate.getMonth() + dir);
        else if (currentScope === 'daily') currentDate.setDate(currentDate.getDate() + dir);
        else if (currentScope === 'hourly') currentDate.setHours(currentDate.getHours() + dir * 2);
        computeHoroscope();
    }

    function resetScope() {
        currentDate = new Date();
        computeHoroscope();
    }

    /* ======================================================================
       宫位详情
       ====================================================================== */
    function selectPalace(idx) {
        selectedIndex = (selectedIndex === idx) ? null : idx;
        drawChart();

        var box = $('zwDetail');
        if (selectedIndex === null) { box.style.display = 'none'; return; }

        var p = astrolabe.palaces[idx];
        var scope = horoscope ? horoscope[currentScope] : null;
        var muMap = {};
        if (scope && scope.mutagen) {
            var keys = ['禄', '权', '科', '忌'];
            for (var k = 0; k < 4; k++) {
                if (scope.mutagen[k]) muMap[scope.mutagen[k]] = keys[k];
            }
        }

        var tags = '';
        if (p.name === '命宫') tags += '<span class="zw-d-tag soul">命宫</span>';
        if (p.isBodyPalace) tags += '<span class="zw-d-tag body">身宫</span>';
        if (p.isOriginalPalace) tags += '<span class="zw-d-tag">来因宫</span>';

        function starsRow(list, extraClass) {
            if (!list || !list.length) return '<span class="zw-d-hint">无</span>';
            var h = '';
            for (var i = 0; i < list.length; i++) h += starHtml(list[i], muMap, false, p.earthlyBranch);
            return '<span class="zw-d-stars ' + (extraClass || '') + '">' + h + '</span>';
        }

        /* 三方四正 */
        var relate = '';
        try {
            var sur = astrolabe.surroundedPalaces(p.name);
            var parts = [];
            if (sur.wealth) parts.push('财帛 ' + sur.wealth.name);
            if (sur.career) parts.push('官禄 ' + sur.career.name);
            if (sur.opposite) parts.push('对宫 ' + sur.opposite.name);
            relate = parts.join('　') || '—';
        } catch (e) { relate = '—'; }

        box.innerHTML =
            '<div class="zw-d-head">' +
                '<span class="zw-d-title">' + esc(p.name) + '</span>' +
                '<span class="zw-d-gz">' + esc(p.heavenlyStem + p.earthlyBranch) + '</span>' +
                '<span class="zw-d-tag">大限 ' + esc(p.decadal.range[0]) + '-' + esc(p.decadal.range[1]) + '</span>' +
                tags +
            '</div>' +
            '<div class="zw-d-block"><span class="zw-d-label">主星</span>' +
                starsRow(p.majorStars) + '</div>' +
            '<div class="zw-d-block"><span class="zw-d-label">辅煞</span>' +
                starsRow(p.minorStars) + '</div>' +
            '<div class="zw-d-block"><span class="zw-d-label">杂曜</span>' +
                starsRow(p.adjectiveStars, 'adj') + '</div>' +
            '<div class="zw-d-block"><span class="zw-d-label">十二神</span>' +
                '长生 ' + esc(p.changsheng12 || '—') + '　博士 ' + esc(p.boshi12 || '—') +
                '　将前 ' + esc(p.jiangqian12 || '—') + '　岁前 ' + esc(p.suiqian12 || '—') +
            '</div>' +
            '<div class="zw-d-block"><span class="zw-d-label">三方四正</span>' +
                '<span class="zw-d-hint">' + esc(relate) + '</span></div>' +
            '<div class="zw-d-block"><span class="zw-d-label">岁数</span>' +
                '<span class="zw-d-hint">' + esc(p.ages.join(' ')) + '</span></div>';

        box.style.display = 'block';
    }

    /* ======================================================================
       绑定
       ====================================================================== */
    function bind() {
        var seg = $('zwScopeSelect');
        if (seg) {
            seg.addEventListener('click', function (e) {
                var btn = e.target.closest('button');
                if (btn && btn.dataset.scope) setScope(btn.dataset.scope);
            });
        }

        var chart = $('zwChart');
        if (chart) {
            chart.addEventListener('click', function (e) {
                var cell = e.target.closest('.zw-palace');
                if (cell && cell.dataset.idx !== undefined) {
                    selectPalace(parseInt(cell.dataset.idx, 10));
                }
            });
        }

        var adjBox = $('zwShowAdj');
        if (adjBox) {
            adjBox.addEventListener('change', function () {
                showAdj = adjBox.checked;
                drawChart();
            });
        }

        var shenSel = $('zwShen12');
        if (shenSel) {
            shenSel.addEventListener('change', function () {
                shen12 = shenSel.value;
                drawChart();
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        bind();
        render();
    });

    /* 供模板内联 onclick 调用 */
    window.zwStep = stepScope;
    window.zwReset = resetScope;
    window.zwSetScope = setScope;
})();
