(() => {
    const container = document.querySelector('[data-visitor-counter]');
    if (!container) return;

    // Keep one fixed key for every page, including a future custom domain.
    const counterKey = 'anuwatpe.github.io/ap-portfolio';
    const badgeUrl = new URL(`https://hits.sh/${counterKey}.svg`);
    badgeUrl.search = new URLSearchParams({
        label: 'Visits',
        color: '7c3aed',
        labelColor: '334155',
        style: 'flat'
    }).toString();

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

    image.addEventListener('load', () => {
        container.hidden = image.naturalWidth === 0;
    }, { once: true });
    image.addEventListener('error', () => {
        container.hidden = true;
        container.replaceChildren();
    }, { once: true });

    updateLabels();
    window.addEventListener('languageChanged', updateLabels);
    link.append(image);
    container.append(link);
    image.src = badgeUrl.toString();
})();
