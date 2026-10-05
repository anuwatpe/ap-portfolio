(() => {
    const container = document.querySelector('[data-visitor-counter]');
    if (!container) return;

    const config = window.ONTHAI_ANALYTICS?.umami || {};
    const isLocal = location.protocol === 'file:' || ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
    const isPreview = isLocal && new URLSearchParams(location.search).get('visitor-preview') === '1';
    const validWebsiteId = /^[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}$/i.test(config.websiteId || '');
    const refreshInterval = 60000;
    const labels = {
        th: {
            online: 'ออนไลน์', week: 'สัปดาห์นี้', month: 'เดือนนี้',
            region: 'สถิติผู้เข้าชมเว็บไซต์', link: 'ดูสถิติการเข้าชม',
            preview: 'ตัวอย่างหน้าตา · ไม่ใช่สถิติจริง',
            onlineHint: 'ผู้เข้าชมที่มีกิจกรรมใน 5 นาทีที่ผ่านมา',
            weekHint: 'ผู้เข้าชมตั้งแต่วันจันทร์ เวลา 00:00 น. ตามเวลาประเทศไทย',
            monthHint: 'ผู้เข้าชมตั้งแต่วันที่ 1 ของเดือน ตามเวลาประเทศไทย'
        },
        en: {
            online: 'Online', week: 'This week', month: 'This month',
            region: 'Website visitor statistics', link: 'View visit statistics',
            preview: 'Design preview · Not live statistics',
            onlineHint: 'Visitors active in the last 5 minutes',
            weekHint: 'Visitors since Monday, 00:00 Asia/Bangkok',
            monthHint: 'Visitors since the first day of the month, Asia/Bangkok'
        }
    };

    function hideCounter() {
        container.hidden = true;
        container.replaceChildren();
    }

    function startTracker() {
        if (isPreview || isLocal || !validWebsiteId || !config.domains?.includes(location.hostname)) return;
        try {
            const url = new URL(config.scriptUrl);
            if (url.protocol !== 'https:' || url.username || url.password) return;
            const script = document.createElement('script');
            script.src = url.href;
            script.defer = true;
            script.dataset.websiteId = config.websiteId;
            script.dataset.domains = config.domains.join(',');
            document.head.append(script);
        } catch {
            // Invalid or unfinished settings must not interrupt the static site.
        }
    }

    function shareSettings() {
        try {
            const url = new URL(config.shareUrl);
            const path = url.pathname.match(/^\/(?:analytics\/(us|eu)\/)?share\/([\w-]+)(?:\/.*)?$/);
            const region = path?.[1] || config.region;
            if (url.protocol !== 'https:' || url.hostname !== 'cloud.umami.is' || url.username || url.password || !path || !['us', 'eu'].includes(region)) return null;
            return {
                url: url.href,
                slug: path[2],
                api: `https://cloud.umami.is/analytics/${region}/api`
            };
        } catch {
            return null;
        }
    }

    function renderStats(counts, shareUrl) {
        const copy = labels[document.documentElement.lang] || labels.en;
        const locale = document.documentElement.lang === 'th' ? 'th-TH' : 'en-US';
        const panel = document.createElement('div');
        panel.className = 'visitor-stats';
        const metrics = document.createElement('dl');
        metrics.className = 'visitor-stats__metrics';

        for (const key of ['online', 'week', 'month']) {
            const item = document.createElement('div');
            item.className = 'visitor-stats__metric';
            item.title = copy[`${key}Hint`];
            const name = document.createElement('dt');
            name.className = 'visitor-stats__label';
            name.textContent = copy[key];
            const value = document.createElement('dd');
            value.className = 'visitor-stats__value';
            value.dataset.metric = key;
            value.textContent = new Intl.NumberFormat(locale, {
                notation: counts[key] >= 1000000 ? 'compact' : 'standard',
                maximumFractionDigits: 1
            }).format(counts[key]);
            value.title = new Intl.NumberFormat(locale).format(counts[key]);
            item.append(name, value);
            metrics.append(item);
        }

        const note = document.createElement(isPreview ? 'span' : 'a');
        note.className = 'visitor-stats__note';
        note.textContent = isPreview ? copy.preview : copy.link;
        if (!isPreview) {
            note.href = shareUrl;
            note.target = '_blank';
            note.rel = 'noopener noreferrer';
        }
        panel.append(metrics, note);
        container.setAttribute('aria-label', copy.region);
        container.dataset.counterMode = isPreview ? 'preview' : 'umami';
        container.replaceChildren(panel);
        container.hidden = false;
    }

    function showHitsCounter() {
        // Preserve the existing count until the owner's Umami account is connected.
        const counterKey = 'anuwatpe.github.io/ap-portfolio';
        const badgeUrl = new URL(`https://hits.sh/${counterKey}.svg`);
        badgeUrl.search = new URLSearchParams({ label: 'Visits', color: '7c3aed', labelColor: '334155', style: 'flat' }).toString();
        const link = document.createElement('a');
        link.href = `https://hits.sh/${counterKey}/`;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.className = 'inline-flex rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent';
        const image = document.createElement('img');
        image.height = 20;
        image.decoding = 'async';
        image.className = 'block h-5 w-auto max-w-full';
        function updateLabels() {
            const isThai = document.documentElement.lang === 'th';
            image.alt = isThai ? 'จำนวนการเข้าชมเว็บไซต์ ONTHAI Lab' : 'ONTHAI Lab website visits';
            link.title = isThai ? 'ดูสถิติการเข้าชมเว็บไซต์' : 'View website visit statistics';
            link.setAttribute('aria-label', link.title);
        }
        image.addEventListener('load', () => { container.hidden = image.naturalWidth === 0; }, { once: true });
        image.addEventListener('error', hideCounter, { once: true });
        updateLabels();
        window.addEventListener('languageChanged', updateLabels);
        link.append(image);
        container.append(link);
        container.dataset.counterMode = 'hits';
        image.src = badgeUrl.toString();
    }

    async function requestJson(url, headers = {}) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 8000);
        try {
            const response = await fetch(url, {
                headers, signal: controller.signal, credentials: 'omit', cache: 'no-store'
            });
            if (!response.ok) throw new Error('Statistics unavailable');
            return await response.json();
        } finally {
            clearTimeout(timer);
        }
    }

    function periodStarts(now) {
        // Calendar weeks start Monday; both periods use Thailand's UTC+7 timezone.
        const offset = 7 * 60 * 60 * 1000;
        const local = new Date(now + offset);
        const day = Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate()) - offset;
        return {
            week: day - ((local.getUTCDay() + 6) % 7) * 86400000,
            month: Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), 1) - offset
        };
    }

    startTracker();
    if (isPreview) {
        const counts = { online: 2, week: 128, month: 486 };
        renderStats(counts);
        window.addEventListener('languageChanged', () => renderStats(counts));
        return;
    }

    const share = shareSettings();
    if (!validWebsiteId || !share) {
        showHitsCounter();
        return;
    }

    let access = null;
    let counts = null;
    let busy = false;
    let lastAttempt = 0;

    async function refresh() {
        if (busy || document.hidden) return;
        busy = true;
        lastAttempt = Date.now();
        try {
            if (!access) {
                access = await requestJson(`${share.api}/share/${encodeURIComponent(share.slug)}`);
                if (!access.token || access.websiteId !== config.websiteId) throw new Error('Share does not match this website');
            }
            const headers = { 'x-umami-share-token': access.token, 'x-umami-share-context': '1' };
            const base = `${share.api}/websites/${encodeURIComponent(config.websiteId)}`;
            const now = Date.now();
            const starts = periodStarts(now);
            const [online, week, month] = await Promise.all([
                requestJson(`${base}/active`, headers),
                requestJson(`${base}/stats?${new URLSearchParams({ startAt: starts.week, endAt: now })}`, headers),
                requestJson(`${base}/stats?${new URLSearchParams({ startAt: starts.month, endAt: now })}`, headers)
            ]);
            const values = { online: online?.visitors, week: week?.visitors, month: month?.visitors };
            if (!Object.values(values).every(value => Number.isSafeInteger(value) && value >= 0)) throw new Error('Invalid visitor counts');
            counts = values;
            renderStats(counts, share.url);
        } catch {
            access = null;
            counts = null;
            hideCounter();
        } finally {
            busy = false;
        }
    }

    window.addEventListener('languageChanged', () => {
        if (counts) renderStats(counts, share.url);
    });
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && Date.now() - lastAttempt >= refreshInterval) refresh();
    });
    refresh();
    setInterval(refresh, refreshInterval);
})();
