/* ==========================================================================
   天机系统 · 全站统一交互
   --------------------------------------------------------------------------
   1. 主题统一挂在 <html data-theme>，避免各页 body 上的旧属性覆盖变量；
      在 <head> 同步执行，防止深浅色闪烁。
   2. 对外提供 toggleTheme / openSettings / closeSettings，供抬头按钮与
      设置面板调用；所有页面共用同一份实现与同一个 localStorage 键。
   ========================================================================== */
(function () {
    'use strict';

    function syncButtons(theme) {
        var nodes = document.querySelectorAll('.tj-theme');
        for (var i = 0; i < nodes.length; i++) {
            nodes[i].textContent = theme === 'dark' ? '☀' : '☾';
            nodes[i].setAttribute('title', theme === 'dark' ? '切换浅色模式' : '切换深色模式');
            nodes[i].setAttribute('aria-label', theme === 'dark' ? '切换浅色模式' : '切换深色模式');
        }
    }

    function apply(theme) {
        var t = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', t);
        // 清理历史上设在 body 上的属性：它与 html 上的定义会互相覆盖。
        if (document.body) {
            document.body.removeAttribute('data-theme');
        }
        syncButtons(t);
    }

    // 尽早应用，避免刷新时的主题闪烁。
    apply(localStorage.getItem('theme') === 'dark' ? 'dark' : 'light');

    window.toggleTheme = function () {
        var cur = document.documentElement.getAttribute('data-theme');
        var next = cur === 'dark' ? 'light' : 'dark';
        apply(next);
        localStorage.setItem('theme', next);
    };

    window.openSettings = function () {
        var m = document.getElementById('tjSettings');
        if (m) m.style.display = 'flex';
    };

    window.closeSettings = function () {
        var m = document.getElementById('tjSettings');
        if (m) m.style.display = 'none';
    };

    // 设置面板由统一脚本注入到 body，保证六个页面的结构与行为完全一致。
    function ensureSettings() {
        if (document.getElementById('tjSettings')) return;
        var wrap = document.createElement('div');
        wrap.id = 'tjSettings';
        wrap.className = 'tj-modal';
        wrap.innerHTML =
            '<div class="tj-modal-card">' +
                '<div class="tj-modal-head"><h3>设置</h3>' +
                    '<button type="button" onclick="closeSettings()" aria-label="关闭">&times;</button></div>' +
                '<div class="tj-modal-row"><span>深色模式</span>' +
                    '<button type="button" class="tj-btn" onclick="toggleTheme()">切换</button></div>' +
                '<hr>' +
                '<div class="tj-contact">如需交流或反馈，可发送邮件至：<br>' +
                    '<b>zhang.haoyan@outlook.com</b></div>' +
            '</div>';
        document.body.appendChild(wrap);
        wrap.addEventListener('click', function (e) {
            if (e.target === wrap) window.closeSettings();
        });
    }

    // 滚动后加深抬头阴影，使毛玻璃层次更清晰；仅切换类名，不改动布局。
    function syncScrolled() {
        var h = document.querySelector('.tj-header');
        if (h) h.classList.toggle('is-scrolled', window.scrollY > 8);
    }
    window.addEventListener('scroll', syncScrolled, { passive: true });

    document.addEventListener('DOMContentLoaded', function () {
        apply(document.documentElement.getAttribute('data-theme') || 'light');
        syncScrolled();

        var btns = document.querySelectorAll('.tj-theme');
        for (var i = 0; i < btns.length; i++) {
            btns[i].addEventListener('click', window.toggleTheme);
        }

        ensureSettings();
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') window.closeSettings();
        });
    });
})();
