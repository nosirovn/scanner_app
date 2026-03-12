// Scanner Dashboard JavaScript

let wsScanner = null;
let wsReconnectDelay = 1000;
let currentTab = 'gainers';
let allStocks = [];
let scannerFilters = null;
let currentSession = 'market';
let lastNonClosedSession = 'market';
let scanStatus = null;
let sortState = { key: null, direction: 'asc' };
let countdownInterval = null;
let scannerInterval = null;
const GLOBAL_MAX_PRICE = 500;
let isStocksLoading = false;
let pendingStocksReload = false;
let lastWsReload = 0;
let columnFilters = {
    ticker: '',
    company_name: '',
    price_min: null,
    change_min: null,
    rvol_min: null,
    volume_min_m: null,
    float_max_m: null,
    ema_alignment: '',
    news_mode: ''
};

const EMA_LABEL_TO_VALUE = {
    '↓': -1,
    '↑': 1,
    '↑↑': 2,
    '↑↑↑': 3
};

const SETTINGS_PRESETS = {
    gap_go: {
        price_min: 1,
        price_max: 20,
        gap_min: 4,
        change_min: 4,
        volume_min: 50_000,
        relative_volume_min: 3,
        float_max_m: 100,
        news_mode: 'with_news',
        movers_scan_limit: 500,
        momentum_change_min: 12,
        momentum_rvol_min: 5,
        momentum_float_min: 10_000_000
    },
    momentum: {
        price_min: 2,
        price_max: 20,
        change_min: 6,
        volume_min: 300_000,
        relative_volume_min: 2,
        float_max_m: 50,
        news_mode: 'all',
        movers_scan_limit: 500,
        momentum_change_min: 10,
        momentum_rvol_min: 4,
        momentum_float_min: 50_000_000
    },
    high_of_day_break: {
        price_min: 1,
        price_max: 20,
        change_min: 5,
        volume_min: 200_000,
        relative_volume_min: 2,
        float_max_m: 200,
        news_mode: 'all',
        movers_scan_limit: 500,
        momentum_change_min: 7,
        momentum_rvol_min: 3,
        momentum_float_min: 50_000_000
    },
    low_float_runner: {
        price_min: 0,
        price_max: 10,
        gap_min: 5,
        change_min: 10,
        volume_min: 200_000,
        relative_volume_min: 4,
        float_max_m: 20,
        news_mode: 'with_news',
        movers_scan_limit: 1000,
        momentum_change_min: 12,
        momentum_rvol_min: 6,
        momentum_float_min: 8_000_000
    },
    vwap_reclaim: {
        price_min: 5,
        price_max: 20,
        gap_min: 0,
        change_min: 3,
        volume_min: 200_000,
        relative_volume_min: 2,
        float_max_m: 500,
        news_mode: 'all',
        movers_scan_limit: 1000,
        momentum_change_min: 6,
        momentum_rvol_min: 3,
        momentum_float_min: 100_000_000
    },
    large_cap_breakout: {
        price_min: 10,
        price_max: 100,
        gap_min: 2,
        change_min: 3,
        volume_min: 500_000,
        relative_volume_min: 1.5,
        float_max_m: 5000,
        news_mode: 'all',
        movers_scan_limit: 500,
        momentum_change_min: 5,
        momentum_rvol_min: 2,
        momentum_float_min: 500_000_000
    }
};

const PRESET_PLAYBOOK = {
    gap_go: {
        title: 'Gap & Go Scanner',
        filters: [
            'Price: $1 - $20',
            'Gap %: > 4%',
            'Premarket Volume: > 50K',
            'Relative Volume: > 2',
            'Float: < 100M',
            'Exchange: NASDAQ / NYSE / AMEX',
            'News Catalyst: optional but preferred'
        ],
        logic: 'Detects premarket demand imbalance where gapping stocks with unusual volume may break premarket highs and trend into the open.',
        purpose: 'Used to isolate early-morning momentum leaders that can produce fast continuation moves in the first 5-60 minutes.',
        behavior: [
            'Mark premarket high and key support before open.',
            'Enter on clean breakout or first pullback to VWAP/support.',
            'Scale out into extension and avoid chasing late candles.'
        ],
        useCase: 'Best for premarket preparation and opening-range breakout execution.'
    },
    momentum: {
        title: 'Momentum Scanner',
        filters: [
            'Price: $0 - $20',
            'Change %: > 7%',
            'Volume: > 300K',
            'Relative Volume: > 3',
            'Float: < 50M',
            'Price above VWAP: preferred'
        ],
        logic: 'Tracks intraday acceleration where price and volume expand together, confirming active demand and continuation probability.',
        purpose: 'Finds stocks gaining strength during session rotation when new leaders emerge beyond the opening bell.',
        behavior: [
            'Watch for volume surge and clean micro pullback entries.',
            'Prioritize symbols holding above VWAP and intraday support.',
            'Re-enter only on constructive consolidation breaks.'
        ],
        useCase: 'Primary all-day scanner for intraday continuation momentum setups.'
    },
    high_of_day_break: {
        title: 'High of Day Break Scanner',
        filters: [
            'Price: $0 - $20',
            'Near High of Day: within ~1%',
            'Change %: > 5%',
            'Relative Volume: > 2',
            'Volume Spike: enabled'
        ],
        logic: 'Highlights symbols pressing day-high resistance where breakout triggers can cascade as momentum traders and algos join.',
        purpose: 'Captures one of the most common momentum entries: clean high-of-day break with confirming volume.',
        behavior: [
            'Wait for tight consolidation just below HOD.',
            'Enter on breakout only if tape and volume confirm.',
            'Cut quickly on failed reclaim below breakout level.'
        ],
        useCase: 'Fast tactical scanner for breakout bursts that can expand in minutes.'
    },
    low_float_runner: {
        title: 'Low Float Runner Scanner',
        filters: [
            'Price: $1 - $10',
            'Float: < 20M',
            'Volume: > 200K',
            'Change %: > 10%',
            'Gap %: > 5%',
            'News Catalyst: preferred'
        ],
        logic: 'Targets low-float names where limited supply can create explosive upside when demand suddenly increases.',
        purpose: 'Designed to catch volatile small-cap runners early, before the strongest expansion phase.',
        behavior: [
            'Trade smaller size due to volatility and halt risk.',
            'Use strict stop placement and partial profit-taking.',
            'Avoid entries after parabolic exhaustion candles.'
        ],
        useCase: 'Specialized scanner for aggressive momentum traders seeking outsized percentage moves.'
    },
    vwap_reclaim: {
        title: 'VWAP Reclaim Scanner',
        filters: [
            'Price: $0 - $20',
            'Change %: > 3%',
            'Relative Volume: > 2',
            'Volume Spike: enabled',
            'Price crossing above VWAP'
        ],
        logic: 'Finds stocks reclaiming VWAP after weakness, signaling buyers regaining control and potential trend continuation.',
        purpose: 'Surfaces high-probability reversal or continuation setups after intraday pullbacks and consolidations.',
        behavior: [
            'Wait for reclaim + hold above VWAP.',
            'Use higher lows as confirmation before adding.',
            'Exit quickly if reclaim fails and VWAP is lost.'
        ],
        useCase: 'Ideal for midday reversals and second-leg continuation entries.'
    },
    large_cap_breakout: {
        title: 'Large Cap Breakout Scanner',
        filters: [
            'Price: $10 - $100',
            'Change %: > 3%',
            'Gap %: > 2%',
            'Volume: > 500K',
            'Relative Volume: > 1.5',
            'Float: < 5B'
        ],
        logic: 'Targets higher-priced liquid names breaking out of consolidation with above-average volume, ideal for larger position sizing.',
        purpose: 'Finds institutional-quality breakouts in mid/large-cap stocks with tighter spreads and more predictable moves.',
        behavior: [
            'Focus on clean breakouts above prior resistance.',
            'Use wider stops due to higher price and ATR.',
            'Scale into strength with partial entries.'
        ],
        useCase: 'Best for traders who prefer liquid names with smoother price action and lower halt risk.'
    }
};

const PRESET_RADAR_TITLES = {
    custom: '⚡ SCANNER RADAR',
    gap_go: '⚡ GAP & GO RADAR',
    momentum: '⚡ MOMENTUM RADAR',
    high_of_day_break: '⚡ HIGH OF DAY BREAK RADAR',
    low_float_runner: '⚡ LOW FLOAT RUNNER RADAR',
    vwap_reclaim: '⚡ VWAP RECLAIM RADAR',
    large_cap_breakout: '⚡ LARGE CAP BREAKOUT RADAR'
};

const CUSTOM_PRESET_STORAGE_KEY = 'scanner_custom_preset_v1';
const NAMED_PRESETS_STORAGE_KEY = 'scanner_named_presets_v1';
const AUTO_REFRESH_STORAGE_KEY = 'scanner_auto_refresh_sec_v1';

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
    initializeScannerOptions();
    initializeSettingsPanelEnhancements();
    loadScannerSettings();
    initializeWebSocket();
    updateSessionInfo();
    refreshScanStatus();
    loadStocks();
    startCountdown();
    startScannerUpdates();
});

// ============ WebSocket Connection ============

function initializeWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsScanner = new WebSocket(`${protocol}//${window.location.host}/ws/scanner`);

    wsScanner.onopen = () => {
        console.log('WebSocket connected');
    };

    wsScanner.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleScannerUpdate(data);
    };

    wsScanner.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    wsScanner.onclose = () => {
        console.log('WebSocket disconnected. Reconnecting...');
        wsReconnectDelay = Math.min((wsReconnectDelay || 1000) * 2, 30000);
        setTimeout(() => { initializeWebSocket(); }, wsReconnectDelay);
    };

    wsScanner.onopen = () => {
        wsReconnectDelay = 1000;
    };
}

// ============ Session Management ============

async function updateSessionInfo() {
    try {
        const response = await fetch('/api/session/current');
        const data = await response.json();
        currentSession = data.current_session;
        if (currentSession !== 'closed') {
            lastNonClosedSession = currentSession;
        }

        document.getElementById('sessionName').textContent = data.current_session.toUpperCase();
        updateSessionIndicator(data.current_session);
        const sessionSelect = document.getElementById('filterSessionType');
        if (sessionSelect && data.current_session !== 'closed') {
            sessionSelect.value = data.current_session;
        }

    } catch (error) {
        console.error('Error fetching session info:', error);
    }
}

function updateSessionIndicator(session) {
    const dot = document.getElementById('sessionDot');
    dot.className = 'session-dot ' + session;

    document.getElementById('sessionName').textContent =
        session.toUpperCase().replace('_', ' ');
}

function startCountdown() {
    countdownInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/session/current');
            const data = await response.json();

            const seconds = Math.max(0, Math.floor(data.seconds_until_next));
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;

            document.getElementById('countdown').textContent =
                `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
            const countdownEl = document.getElementById('filterMarketCountdown');
            if (countdownEl) countdownEl.value = document.getElementById('countdown').textContent;
        } catch (error) {
            console.error('Countdown error:', error);
        }
    }, 1000);
}

// ============ Data Loading ============

async function loadStocks() {
    if (isStocksLoading) {
        pendingStocksReload = true;
        return;
    }

    isStocksLoading = true;
    try {
        let sessionParam = currentSession;
        if (currentSession === 'closed') {
            const effective = String(scanStatus?.effective_session || '').toLowerCase();
            sessionParam = (effective && effective !== 'closed') ? effective : (lastNonClosedSession || 'market');
        }
        const response = await fetch(`/api/stocks/top?session=${encodeURIComponent(sessionParam)}&limit=20`);
        if (!response.ok) throw new Error('Failed to load stocks');
        const stocks = await response.json();

        // Keep the last visible dataset during closed sessions when no fresh rows are returned.
        if (!(currentSession === 'closed' && stocks.length === 0 && allStocks.length > 0)) {
            allStocks = stocks;
        }
        renderStocks(allStocks);
        loadMomentumRadar();
    } catch (error) {
        console.error('Error loading stocks:', error);
        const tableEl = document.getElementById('stocksTable');
        if (tableEl) {
            tableEl.innerHTML =
                '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Unable to load stocks right now</div>';
        }
    } finally {
        isStocksLoading = false;
        if (pendingStocksReload) {
            pendingStocksReload = false;
            loadStocks();
        }
    }
}

async function loadMomentumRadar() {
    try {
        const response = await fetch('/api/stocks/momentum?limit=10');
        if (!response.ok) throw new Error('Failed to load momentum stocks');
        const stocks = await response.json();

        if (!stocks.length) {
            document.getElementById('momentumList').innerHTML = renderMomentumStatus();
            return;
        }

        const html = stocks.map(stock => `
            <div class="momentum-item">
                <div class="momentum-ticker">🔥 <a href="https://finance.yahoo.com/chart/${encodeURIComponent(stock.ticker)}#eyJpbnRlcnZhbCI6NjAsInBlcmlvZGljaXR5IjoxLCJ0aW1lVW5pdCI6Im1pbnV0ZSJ9" target="_blank" rel="noopener noreferrer" class="ticker-link">${stock.ticker}</a> ${fmtUSD(stock.price)}</div>
                <div class="momentum-stats">
                    <span class="momentum-line">Change +${fmtNum(stock.percent_change, 1)}%</span>
                    <span class="momentum-line">VOL: ${fmtNum(Number(stock.volume || 0) / 1_000_000, 1)} M</span>
                    <span class="momentum-line">RVOL: x${fmtNum(stock.rvol, 1)}</span>
                    <span class="momentum-line">Float: ${fmtNum(stock.float / 1_000_000, 1)}M</span>
                    <span class="momentum-line momentum-news-wrap">
                        <span class="momentum-news-preview">News: "${escapeHtml(summarizeNews(stock.news_summary || stock.news_headline || ''))}"</span>
                        <span class="momentum-news-full">News: "${escapeHtml(buildFiveSentenceSummary(stock.news_summary || stock.news_headline || ''))}"</span>
                    </span>
                    <span class="alert-level-line">EN: ${fmtUSD(stock.entry)}</span>
                    <span class="alert-level-line">TP: ${fmtUSD(stock.tp)}</span>
                    <span class="alert-level-line">SL: ${fmtUSD(stock.sl)}</span>
                </div>
            </div>
        `).join('');

        document.getElementById('momentumList').innerHTML = html;
    } catch (error) {
        console.error('Error loading momentum radar:', error);
        document.getElementById('momentumList').innerHTML = renderMomentumStatus(error.message || 'Unable to fetch momentum stocks');
    }
}

async function refreshScanStatus() {
    try {
        const response = await fetch('/api/scanner/run-status');
        if (!response.ok) return;
        const data = await response.json();
        scanStatus = data.scan || null;
        updateStatusBar(data);
    } catch (error) {
        console.error('Error loading scanner run status:', error);
        updateStatusBar(null);
    }
}

function updateStatusBar(data) {
    const appDot = document.getElementById('appStatusDot');
    const appLabel = document.getElementById('appStatusLabel');
    const ibkrDot = document.getElementById('ibkrStatusDot');
    const ibkrLabel = document.getElementById('ibkrStatusLabel');
    const metaLabel = document.getElementById('lastScanLabel');
    if (!appDot) return;

    const scan = data?.scan || {};
    const ds = data?.data_source || {};

    // App status
    if (!data) {
        appDot.className = 'status-dot red';
        appLabel.textContent = 'Offline';
    } else if (scan.last_error) {
        appDot.className = 'status-dot red';
        appLabel.textContent = 'Error';
    } else if (scan.in_progress) {
        appDot.className = 'status-dot yellow';
        appLabel.textContent = 'Scanning';
    } else if (scan.effective_session === 'closed') {
        appDot.className = 'status-dot blue';
        appLabel.textContent = 'Market Closed';
    } else if (scan.completed_at) {
        appDot.className = 'status-dot green';
        appLabel.textContent = 'Idle';
    } else {
        appDot.className = 'status-dot blue';
        appLabel.textContent = 'Waiting';
    }

    // IBKR status
    if (ds.ibkr_connected) {
        ibkrDot.className = 'status-dot green';
        ibkrLabel.textContent = 'IBKR Live';
    } else {
        ibkrDot.className = 'status-dot gray';
        ibkrLabel.textContent = 'IBKR Off';
    }

    // Last scan meta
    if (scan.completed_at) {
        const ago = _timeAgo(scan.completed_at);
        const count = scan.result_count ?? 0;
        metaLabel.textContent = `${count} found \u00b7 ${ago}`;
    } else if (scan.in_progress) {
        metaLabel.textContent = 'Scan running...';
    } else {
        metaLabel.textContent = '--';
    }
}

function _timeAgo(iso) {
    try {
        const t = new Date(iso);
        const diff = Math.round((Date.now() - t.getTime()) / 1000);
        if (diff < 5) return 'just now';
        if (diff < 60) return diff + 's ago';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        return Math.floor(diff / 3600) + 'h ago';
    } catch { return ''; }
}

function renderMomentumStatus(fetchError = null) {
    const status = scanStatus || {};
    const trigger = status.trigger || 'interval';
    const triggerLabel = {
        interval: 'Scheduled scan',
        settings_update: 'Settings restart scan',
        websocket: 'Live update scan'
    }[trigger] || 'Scanner task';

    let title = 'Searching momentum stocks...';
    let detail = 'Fetching market data and calculating momentum.';
    let stateClass = 'is-idle';

    if (fetchError) {
        title = 'Scanner connection issue';
        detail = fetchError;
        stateClass = 'is-error';
    } else if (status.last_error) {
        title = 'Scanner error';
        detail = status.last_error;
        stateClass = 'is-error';
    } else if (status.in_progress) {
        title = 'Screening in progress...';
        detail = `${triggerLabel}: fetching quotes, volume and EMA signals.`;
        stateClass = 'is-running';
    } else if (status.completed_at && Number(status.result_count || 0) === 0) {
        title = 'Search complete: no momentum stocks';
        detail = 'Scanner finished, but nothing matched current filters.';
        stateClass = 'is-empty';
    } else if (status.completed_at) {
        title = 'Waiting for next scan...';
        detail = `${triggerLabel} completed. Monitoring for the next update.`;
        stateClass = 'is-idle';
    }

    const sessionLine = status.effective_session
        ? `Session: ${String(status.effective_session).toUpperCase()}`
        : 'Session: -';
    const updatedLine = status.completed_at
        ? `Last update: ${new Date(status.completed_at).toLocaleTimeString()}`
        : 'Last update: pending';

    return `
        <div class="momentum-item momentum-status ${stateClass}">
            <div class="momentum-status-title"><span class="status-dot"></span>${title}</div>
            <div class="momentum-status-detail">${detail}</div>
            <div class="momentum-status-meta">${sessionLine} | ${updatedLine}</div>
        </div>
    `;
}

// ============ Scanner Settings ============

function initializeScannerOptions() {
    // Volume min uses a standard number+slider dual input now
}

function initializeSettingsPanelEnhancements() {
    const savedRefresh = getInputNumber('filterAutoRefresh', Number(localStorage.getItem(AUTO_REFRESH_STORAGE_KEY) || 12));
    const refreshEl = document.getElementById('filterAutoRefresh');
    if (refreshEl) refreshEl.value = Math.max(3, Math.min(120, savedRefresh));

    const sessionEl = document.getElementById('filterSessionType');
    if (sessionEl) sessionEl.value = currentSession || 'market';

    initializeDualInputControls();
    renderPresetPlaybook(document.getElementById('filterPreset')?.value || 'custom');
    updateMomentumRadarTitleByPreset(document.getElementById('filterPreset')?.value || 'custom');
    updateAllSectionCriteria();
    updateMasterToggleLabel();
    // Watch for input changes to update criteria
    document.querySelectorAll('.settings-scroll input, .settings-scroll select').forEach(el => {
        el.addEventListener('change', () => updateAllSectionCriteria());
        el.addEventListener('input', () => updateAllSectionCriteria());
    });
}

function initializeDualInputControls() {
    bindDualInputControl('filterPriceMin', 'filterPriceMinSlider');
    bindDualInputControl('filterPriceMax', 'filterPriceMaxSlider');
    bindDualInputControl('filterChangeMin', 'filterChangeMinSlider');
    bindDualInputControl('filterRvolMin', 'filterRvolMinSlider');
    bindDualInputControl('filterFloatMin', 'filterFloatMinSlider');
    bindDualInputControl('filterFloatMax', 'filterFloatMaxSlider');
    bindDualInputControl('filterMomentumChangeMin', 'filterMomentumChangeMinSlider');
    bindDualInputControl('filterMomentumRvolMin', 'filterMomentumRvolMinSlider');
    bindDualInputControl('filterMomentumFloatMin', 'filterMomentumFloatMinSlider');
    bindDualInputControl('filterMomentumSpike', 'filterMomentumSpikeSlider');
    bindDualInputControl('filterAutoRefresh', 'filterAutoRefreshSlider');
    bindDualInputControl('filterGapMin', 'filterGapMinSlider');
    bindDualInputControl('filterAvgDailyVolume', 'filterAvgDailyVolumeSlider');
    bindDualInputControl('filterSharesOutstanding', 'filterSharesOutstandingSlider');
    bindDualInputControl('filterSpreadMax', 'filterSpreadMaxSlider');
    bindDualInputControl('filterVolumeMin', 'filterVolumeMinSlider');
}

function bindDualInputControl(numberId, sliderId) {
    const numberEl = document.getElementById(numberId);
    const sliderEl = document.getElementById(sliderId);
    if (!numberEl || !sliderEl) return;

    ensureSliderMarks(numberId, sliderEl);

    const clampToSliderBounds = (val) => {
        const min = Number(sliderEl.min);
        const max = Number(sliderEl.max);
        if (!Number.isFinite(val)) return Number(sliderEl.value);
        return Math.max(min, Math.min(max, val));
    };

    const syncFromNumber = () => {
        const parsed = Number(numberEl.value);
        if (!Number.isFinite(parsed)) return;
        sliderEl.value = String(clampToSliderBounds(parsed));
    };

    const syncFromSlider = () => {
        numberEl.value = sliderEl.value;
    };

    numberEl.addEventListener('input', syncFromNumber);
    sliderEl.addEventListener('input', syncFromSlider);

    syncFromNumber();
}

function ensureSliderMarks(numberId, sliderEl) {
    if (!sliderEl.parentElement) return;
    let marks = sliderEl.parentElement.querySelector('.slider-marks');
    if (!marks) {
        marks = document.createElement('div');
        marks.className = 'slider-marks';
        marks.innerHTML = '<span class="slider-mark-left"></span><span class="slider-mark-right"></span>';
        sliderEl.insertAdjacentElement('afterend', marks);
    }

    const leftEl = marks.querySelector('.slider-mark-left');
    const rightEl = marks.querySelector('.slider-mark-right');
    if (!leftEl || !rightEl) return;

    const min = Number(sliderEl.min);
    const max = Number(sliderEl.max);
    leftEl.textContent = formatSliderMark(numberId, min);
    rightEl.textContent = formatSliderMark(numberId, max);
}

function formatSliderMark(numberId, value) {
    const id = numberId.toLowerCase();
    if (id.includes('price')) return `$${fmtNum(value, 0)}`;
    if (id.includes('rvol')) return `${fmtNum(value, 0)}x`;
    if (id.includes('float')) return `${fmtNum(value, 0)}M`;
    if (id.includes('spread')) return `${fmtNum(value, 0)}%`;
    if (id.includes('change') || id.includes('gap')) return `${fmtNum(value, 0)}%`;
    if (id.includes('spike')) return `${fmtNum(value, 0)}x`;
    if (id.includes('volume') || id.includes('avgdaily')) {
        return value >= 1_000_000 ? `${fmtNum(value / 1_000_000, 1)}M` : value >= 1_000 ? `${fmtNum(value / 1_000, 0)}K` : String(value);
    }
    return String(value);
}

async function loadScannerSettings() {
    try {
        const response = await fetch('/api/scanner/settings');
        if (!response.ok) throw new Error('Failed to load scanner settings');
        scannerFilters = await response.json();
        setFilterInputs(scannerFilters);
    } catch (error) {
        console.error('Error loading scanner settings:', error);
    }
}

function setFilterInputs(filters) {
    if (!filters) return;

    const setValue = (id, value) => {
        const el = document.getElementById(id);
        if (el) {
            el.value = value;
            const slider = document.getElementById(`${id}Slider`);
            if (slider) slider.value = String(value);
        }
    };

    setValue('filterPriceMin', Number(filters.price_min ?? 0));
    setValue('filterPriceMax', Number(filters.price_max ?? 20));
    setValue('filterGapMin', 0);
    setValue('filterFloatMax', Math.round((Number(filters.float_max ?? 20_000_000)) / 1_000_000));
    setValue('filterFloatMin', 0);
    setValue('filterSharesOutstanding', 0);
    setValue('filterRvolMin', Math.round(Number(filters.relative_volume_min ?? 1)));
    setValue('filterAvgDailyVolume', 0);
    // Volume min — standard number input
    setValue('filterVolumeMin', Math.max(10_000, Math.min(2_000_000, Number(filters.volume_min ?? 10_000))));
    setValue('filterChangeMin', Number(filters.change_min ?? 1));
    const emaMinArrows = Number(filters.ema_min_arrows ?? 0);
    setValue('filterEmaMinArrows', [0, 1, 2, 3].includes(emaMinArrows) ? emaMinArrows : 0);
    // Universe size — activate the right button
    const universeVal = String(filters.movers_scan_limit ?? 100);
    const hiddenUniverse = document.getElementById('filterMoversScanLimit');
    if (hiddenUniverse) hiddenUniverse.value = universeVal;
    document.querySelectorAll('#universeStack .stack-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.value === universeVal);
    });
    setValue('filterMomentumChangeMin', filters.momentum_change_min ?? 12);
    setValue('filterMomentumRvolMin', filters.momentum_rvol_min ?? 5);
    setValue('filterMomentumFloatMin', ((filters.momentum_float_min ?? filters.momentum_float_max ?? 10_000_000) / 1_000_000).toFixed(0));
    setValue('filterMomentumSpike', 1.5);
    const sessionFallback = currentSession === 'closed' ? (lastNonClosedSession || 'market') : currentSession;
    setValue('filterSessionType', filters.session_type || sessionFallback);

    const refreshSaved = Number(localStorage.getItem(AUTO_REFRESH_STORAGE_KEY) || 12);
    setValue('filterAutoRefresh', Math.max(3, Math.min(120, refreshSaved)));

    const setChecked = (id, checked) => {
        const el = document.getElementById(id);
        if (el) el.checked = checked;
    };
    setChecked('filterEma9', false);
    setChecked('filterEma20', emaMinArrows > 0);
    setChecked('filterVwap', false);
    setChecked('filterBreakPmHigh', false);
    setChecked('filterBreakDayHigh', false);
    setChecked('filterConsolidation', false);
    setChecked('filterWithNews', (filters.news_mode ?? 'all') === 'with_news');
    setChecked('filterExchangeNasdaq', true);
    setChecked('filterExchangeNyse', true);
    setChecked('filterExchangeAmex', true);
    setChecked('filterExcludeHalted', true);
    setChecked('filterShortableOnly', false);
    setValue('filterSpreadMax', 5);

    const presetEl = document.getElementById('filterPreset');
    if (presetEl) {
        presetEl.value = detectPresetFromFilters(filters);
        presetEl.dataset.previousPreset = presetEl.value;
    }
    renderPresetPlaybook(presetEl?.value || 'custom');
    updateMomentumRadarTitleByPreset(presetEl?.value || 'custom');
    updateAllSectionCriteria();
}

function detectPresetFromFilters(filters) {
    const toCompare = {
        movers_scan_limit: Number(filters.movers_scan_limit ?? 120),
        momentum_change_min: Number(filters.momentum_change_min ?? 12),
        momentum_rvol_min: Number(filters.momentum_rvol_min ?? 5),
        momentum_float_min: Number(filters.momentum_float_min ?? filters.momentum_float_max ?? 10_000_000)
    };

    const isMatch = (preset) => Object.keys(preset).every(key => toCompare[key] === preset[key]);

    if (isMatch(SETTINGS_PRESETS.gap_go)) return 'gap_go';
    if (isMatch(SETTINGS_PRESETS.momentum)) return 'momentum';
    if (isMatch(SETTINGS_PRESETS.high_of_day_break)) return 'high_of_day_break';
    if (isMatch(SETTINGS_PRESETS.low_float_runner)) return 'low_float_runner';
    if (isMatch(SETTINGS_PRESETS.vwap_reclaim)) return 'vwap_reclaim';
    if (isMatch(SETTINGS_PRESETS.large_cap_breakout)) return 'large_cap_breakout';
    return 'custom';
}

function applySettingsPreset(presetName) {
    const presetEl = document.getElementById('filterPreset');
    const previousPreset = presetEl?.dataset.previousPreset || 'custom';

    // Preserve manually entered values before switching away from custom.
    if (previousPreset === 'custom' && presetName !== 'custom') {
        saveCustomPresetToStorage();
    }

    if (!presetName) return;
    if (presetName === 'custom') {
        restoreCustomPresetFromStorage();
        if (presetEl) presetEl.dataset.previousPreset = 'custom';
        renderPresetPlaybook('custom');
        updateMomentumRadarTitleByPreset('custom');
        updateAllSectionCriteria();
        return;
    }

    const preset = SETTINGS_PRESETS[presetName];
    if (!preset) return;

    const setValue = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    };

    setValue('filterPriceMin', preset.price_min ?? 0);
    setValue('filterPriceMax', preset.price_max ?? 20);
    setValue('filterGapMin', preset.gap_min ?? 0);
    setValue('filterChangeMin', preset.change_min ?? 3);
    setValue('filterRvolMin', preset.relative_volume_min ?? 1);
    setValue('filterFloatMax', preset.float_max_m ?? 50);
    // Volume min — standard number input
    setValue('filterVolumeMin', Math.max(10_000, Math.min(2_000_000, preset.volume_min ?? 500_000)));
    // News — checkbox
    const newsCheckbox = document.getElementById('filterWithNews');
    if (newsCheckbox) newsCheckbox.checked = (preset.news_mode === 'with_news');
    // Universe size — activate button
    const uVal = String(preset.movers_scan_limit);
    const uHidden = document.getElementById('filterMoversScanLimit');
    if (uHidden) uHidden.value = uVal;
    document.querySelectorAll('#universeStack .stack-btn').forEach(b => b.classList.toggle('active', b.dataset.value === uVal));
    setValue('filterMomentumChangeMin', preset.momentum_change_min);
    setValue('filterMomentumRvolMin', preset.momentum_rvol_min);
    setValue('filterMomentumFloatMin', Math.round(preset.momentum_float_min / 1_000_000));

    if (presetEl) presetEl.dataset.previousPreset = presetName;
    renderPresetPlaybook(presetName);
    updateMomentumRadarTitleByPreset(presetName);
    // Auto-expand the playbook panel when a preset is selected
    const playbookSec = document.getElementById('playbookSection');
    if (playbookSec && !playbookSec.classList.contains('active')) {
        playbookSec.classList.add('active');
        updateMasterToggleLabel();
    }
    updateAllSectionCriteria();
}

function renderPresetPlaybook(presetName) {
    const titleEl = document.querySelector('.preset-insight-title');
    const filtersEl = document.getElementById('presetFiltersList');
    const logicEl = document.getElementById('presetLogicText');
    const purposeEl = document.getElementById('presetPurposeText');
    const behaviorEl = document.getElementById('presetBehaviorList');
    const useCaseEl = document.getElementById('presetUseCaseText');

    if (!titleEl || !filtersEl || !logicEl || !purposeEl || !behaviorEl || !useCaseEl) return;

    if (!presetName || presetName === 'custom' || !PRESET_PLAYBOOK[presetName]) {
        titleEl.textContent = 'Custom Scanner Preset';
        filtersEl.innerHTML = '<li>Custom values from current panel</li>';
        logicEl.textContent = 'Uses your active settings to scan for momentum setups based on your selected thresholds.';
        purposeEl.textContent = 'Flexible mode for discretionary traders who tailor rules to current market conditions.';
        behaviorEl.innerHTML = '<li>Adjust thresholds by session volatility.</li><li>Save named variants for recurring market regimes.</li>';
        useCaseEl.textContent = 'Best when market character shifts and fixed templates are too rigid.';
        return;
    }

    const p = PRESET_PLAYBOOK[presetName];
    titleEl.textContent = p.title;
    filtersEl.innerHTML = p.filters.map(item => `<li>${item}</li>`).join('');
    logicEl.textContent = p.logic;
    purposeEl.textContent = p.purpose;
    behaviorEl.innerHTML = p.behavior.map(item => `<li>${item}</li>`).join('');
    useCaseEl.textContent = p.useCase;
}

function updateMomentumRadarTitleByPreset(presetName) {
    const el = document.getElementById('momentumRadarTitle');
    if (!el) return;
    el.textContent = PRESET_RADAR_TITLES[presetName] || PRESET_RADAR_TITLES.custom;
}

function saveCustomPresetToStorage() {
    const payload = {
        price_min: getInputNumber('filterPriceMin', 0),
        price_max: getInputNumber('filterPriceMax', 20),
        float_max_m: getInputNumber('filterFloatMax', 20),
        relative_volume_min: getInputNumber('filterRvolMin', 1),
        volume_min: getInputNumber('filterVolumeMin', 10000),
        change_min: getInputNumber('filterChangeMin', 1),
        ema_min_arrows: getInputNumber('filterEmaMinArrows', 0),
        news_mode: document.getElementById('filterWithNews')?.checked ? 'with_news' : 'all',
        movers_scan_limit: getInputNumber('filterMoversScanLimit', 100),
        momentum_change_min: getInputNumber('filterMomentumChangeMin', 12),
        momentum_rvol_min: getInputNumber('filterMomentumRvolMin', 5),
        momentum_float_min_m: getInputNumber('filterMomentumFloatMin', 10),
        gap_min: getInputNumber('filterGapMin', 0),
        float_min_m: getInputNumber('filterFloatMin', 0),
        avg_daily_volume: getInputNumber('filterAvgDailyVolume', 0),
        spread_max: getInputNumber('filterSpreadMax', 5),
        auto_refresh: getInputNumber('filterAutoRefresh', 12),
        session_type: (document.getElementById('filterSessionType')?.value || 'market'),
        momentum_spike: getInputNumber('filterMomentumSpike', 1.5),
        ema9: Boolean(document.getElementById('filterEma9')?.checked),
        ema20: Boolean(document.getElementById('filterEma20')?.checked),
        vwap: Boolean(document.getElementById('filterVwap')?.checked),
        break_pm_high: Boolean(document.getElementById('filterBreakPmHigh')?.checked),
        break_day_high: Boolean(document.getElementById('filterBreakDayHigh')?.checked),
        consolidation: Boolean(document.getElementById('filterConsolidation')?.checked),
        with_news: Boolean(document.getElementById('filterWithNews')?.checked),
        exchange_nasdaq: Boolean(document.getElementById('filterExchangeNasdaq')?.checked),
        exchange_nyse: Boolean(document.getElementById('filterExchangeNyse')?.checked),
        exchange_amex: Boolean(document.getElementById('filterExchangeAmex')?.checked),
        exclude_halted: Boolean(document.getElementById('filterExcludeHalted')?.checked),
        shortable_only: Boolean(document.getElementById('filterShortableOnly')?.checked)
    };
    localStorage.setItem(CUSTOM_PRESET_STORAGE_KEY, JSON.stringify(payload));
}

function restoreCustomPresetFromStorage() {
    const raw = localStorage.getItem(CUSTOM_PRESET_STORAGE_KEY);
    if (!raw) return;

    let saved;
    try {
        saved = JSON.parse(raw);
    } catch {
        return;
    }

    const setValue = (id, value) => {
        const el = document.getElementById(id);
        if (el && value !== undefined && value !== null) {
            el.value = value;
            const slider = document.getElementById(`${id}Slider`);
            if (slider) slider.value = String(value);
        }
    };

    setValue('filterPriceMin', saved.price_min);
    setValue('filterPriceMax', saved.price_max);
    setValue('filterFloatMax', saved.float_max_m);
    setValue('filterRvolMin', saved.relative_volume_min);
    // Volume min — standard number input
    setValue('filterVolumeMin', saved.volume_min);
    setValue('filterChangeMin', saved.change_min);
    setValue('filterEmaMinArrows', saved.ema_min_arrows);
    // News — checkbox
    setChecked('filterWithNews', saved.with_news ?? (saved.news_mode === 'with_news'));
    // Universe size — activate button
    const sUVal = String(saved.movers_scan_limit);
    const sUHidden = document.getElementById('filterMoversScanLimit');
    if (sUHidden) sUHidden.value = sUVal;
    document.querySelectorAll('#universeStack .stack-btn').forEach(b => b.classList.toggle('active', b.dataset.value === sUVal));
    setValue('filterMomentumChangeMin', saved.momentum_change_min);
    setValue('filterMomentumRvolMin', saved.momentum_rvol_min);
    setValue('filterMomentumFloatMin', saved.momentum_float_min_m);
    setValue('filterGapMin', saved.gap_min);
    setValue('filterFloatMin', saved.float_min_m);
    setValue('filterAvgDailyVolume', saved.avg_daily_volume);
    setValue('filterSpreadMax', saved.spread_max);
    setValue('filterAutoRefresh', saved.auto_refresh);
    setValue('filterSessionType', saved.session_type);
    setValue('filterMomentumSpike', saved.momentum_spike);

    const setChecked = (id, checked) => {
        const el = document.getElementById(id);
        if (el && typeof checked === 'boolean') el.checked = checked;
    };
    setChecked('filterEma9', saved.ema9);
    setChecked('filterEma20', saved.ema20);
    setChecked('filterVwap', saved.vwap);
    setChecked('filterBreakPmHigh', saved.break_pm_high);
    setChecked('filterBreakDayHigh', saved.break_day_high);
    setChecked('filterConsolidation', saved.consolidation);
    setChecked('filterWithNews', saved.with_news ?? (saved.news_mode === 'with_news'));
    setChecked('filterExchangeNasdaq', saved.exchange_nasdaq);
    setChecked('filterExchangeNyse', saved.exchange_nyse);
    setChecked('filterExchangeAmex', saved.exchange_amex);
    setChecked('filterExcludeHalted', saved.exclude_halted);
    setChecked('filterShortableOnly', saved.shortable_only);
}

function getInputNumber(id, fallback = 0) {
    const el = document.getElementById(id);
    if (!el) return fallback;
    const value = parseFloat(el.value);
    return Number.isFinite(value) ? value : fallback;
}

function normalizeRvolMin(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 1;
    return Math.max(0.1, Math.min(500, numeric));
}

function collectFilterInputValues() {
    const priceMin = getInputNumber('filterPriceMin', scannerFilters?.price_min ?? 0);
    const priceMax = getInputNumber('filterPriceMax', scannerFilters?.price_max ?? 20);
    const safeMin = Math.max(0, priceMin);
    const safeMax = Math.max(safeMin + 0.01, priceMax);

    return {
        price_min: safeMin,
        price_max: safeMax,
        float_max: getInputNumber('filterFloatMax', (scannerFilters?.float_max ?? 20_000_000) / 1_000_000) * 1_000_000,
        relative_volume_min: normalizeRvolMin(getInputNumber('filterRvolMin', scannerFilters?.relative_volume_min ?? 1)),
        volume_min: getInputNumber('filterVolumeMin', scannerFilters?.volume_min ?? 10000),
        change_min: getInputNumber('filterChangeMin', scannerFilters?.change_min ?? 1),
        ema_min_arrows: Math.max(0, Math.min(3, getInputNumber('filterEmaMinArrows', scannerFilters?.ema_min_arrows ?? 0))),
        news_mode: document.getElementById('filterWithNews')?.checked ? 'with_news' : 'all',
        movers_scan_limit: getInputNumber('filterMoversScanLimit', scannerFilters?.movers_scan_limit ?? 100),
        momentum_change_min: getInputNumber('filterMomentumChangeMin', scannerFilters?.momentum_change_min ?? 12),
        momentum_rvol_min: getInputNumber('filterMomentumRvolMin', scannerFilters?.momentum_rvol_min ?? 5),
        momentum_float_min: getInputNumber('filterMomentumFloatMin', (scannerFilters?.momentum_float_min ?? scannerFilters?.momentum_float_max ?? 10_000_000) / 1_000_000) * 1_000_000
    };
}

function summarizeNews(headline) {
    const text = String(headline || '').trim();
    if (!text) return '';
    return text.length > 160 ? `${text.slice(0, 157)}...` : text;
}

function buildFiveSentenceSummary(rawText) {
    const text = String(rawText || '').replace(/\s+/g, ' ').trim();
    if (!text) return '';
    const sentences = text.match(/[^.!?]+[.!?]?/g) || [text];
    return sentences.slice(0, 5).join(' ').trim();
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function applyScannerSettings() {
    const btn = document.getElementById('applyFiltersBtn');
    const payload = collectFilterInputValues();
    const selectedPreset = document.getElementById('filterPreset')?.value || 'custom';

    try {
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Applying...';
        }

        const response = await fetch('/api/scanner/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to apply scanner settings');
        }

        const data = await response.json();
        scannerFilters = data.filters;
        scanStatus = data.scan_status || null;

        if (selectedPreset === 'custom') {
            saveCustomPresetToStorage();
        }
        localStorage.setItem(AUTO_REFRESH_STORAGE_KEY, String(getInputNumber('filterAutoRefresh', 12)));
        restartScannerUpdates();

        if (btn) {
            btn.textContent = 'Restarting...';
        }

        showNotification('Scanner restarting with new settings...', 'momentum');

        await waitForScanCompletion(scanStatus?.settings_version);
        await loadStocks();
        await updateSessionInfo();

        if (btn) {
            btn.textContent = 'Applied';
        }

        setTimeout(() => {
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Apply & Restart';
            }
        }, 2000);
    } catch (error) {
        console.error('Error applying scanner settings:', error);
        showNotification(error.message || 'Failed to apply scanner settings', 'error');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Apply & Restart';
        }
    }
}

async function waitForScanCompletion(targetSettingsVersion) {
    if (!targetSettingsVersion) return;

    const maxAttempts = 20;
    for (let i = 0; i < maxAttempts; i++) {
        try {
            const response = await fetch('/api/scanner/run-status');
            if (!response.ok) break;

            const data = await response.json();
            scanStatus = data.scan || null;

            if (
                scanStatus &&
                !scanStatus.in_progress &&
                scanStatus.completed_at &&
                scanStatus.settings_version >= targetSettingsVersion
            ) {
                if (scanStatus.last_error) {
                    throw new Error(scanStatus.last_error);
                }
                return;
            }
        } catch (error) {
            console.error('Error waiting for scan completion:', error);
            throw error;
        }

        await new Promise(resolve => setTimeout(resolve, 1000));
    }
}

// ============ Stock Rendering ============

function renderStocks(stocks) {
    const tableEl = document.getElementById('stocksTable');
    if (!tableEl) return;

    const filteredStocks = filterStocks(stocks);
    const sortedStocks = sortStocks(filteredStocks);
    const html = sortedStocks.map(stock => renderStockRow(stock)).join('');

    tableEl.innerHTML = html ||
        '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">No stocks match current filters</div>';
    updateSortIndicators();
}

function renderStockRow(stock) {
    const floatStr = stock.float >= 1_000_000 ?
        `${fmtNum(stock.float/1_000_000, 1)}M` :
        `${fmtNum(stock.float/1000, 0)}K`;
    const volumeStr = `${fmtNum(stock.volume / 1_000_000, 1)}M`;
    const companyName = stock.company_name || '-';

    return `
        <div class="table-row">
            <div class="ticker-cell">
                <a href="https://www.google.com/finance/quote/${stock.ticker}"
                   target="_blank" class="ticker-link">${stock.ticker}</a>
                <div class="ticker-levels">E ${fmtNum(stock.entry, 2)} | TP ${fmtNum(stock.tp, 2)} | SL ${fmtNum(stock.sl, 2)}</div>
            </div>
            <div class="company-name-cell">${companyName}</div>
            <div>${fmtUSD(stock.price)}</div>
            <div class="${stock.percent_change >= 0 ? 'price-positive' : 'price-negative'}">
                +${fmtNum(stock.percent_change, 1)}%
            </div>
            <div>x${fmtNum(stock.rvol, 1)}</div>
            <div>${volumeStr}</div>
            <div>${floatStr}</div>
            <div>${stock.ema_alignment}</div>
            <div>${renderNewsCell(stock)}</div>
        </div>
    `;
}

function renderNewsCell(stock) {
    const hasNews = Boolean(stock.news_summary || stock.news_headline || stock.catalyst);
    if (stock.news_headline) {
        const preview = summarizeNews(stock.news_headline);
        const details = buildFiveSentenceSummary(stock.news_summary || stock.news_headline);
        const detailedText = escapeHtml(details || preview);
        const linkedDetails = stock.news_url
            ? `<a class="news-popover-link" href="${escapeHtml(stock.news_url)}" target="_blank" rel="noopener noreferrer">${detailedText}</a>`
            : detailedText;
        return `
            <div class="news-cell">
                <span class="news-pill news-preview">📰 ${escapeHtml(preview)}</span>
                <div class="news-popover">${linkedDetails}</div>
            </div>
        `;
    }
    if (stock.catalyst) {
        return `<span class="news-pill">📰 ${String(stock.catalyst).replace(/_/g, ' ')}</span>`;
    }
    if (hasNews) return '<span class="news-pill">📰 News</span>';
    return '-';
}

function getAlertColor(alertLevel) {
    const colors = {
        'momentum': '#ffd93d'
    };
    return colors[alertLevel] || 'transparent';
}

// ============ Filtering ============

function filterStocks(stocks) {
    return stocks.filter(stock => {
        if (currentTab === 'low-float' && stock.float > 5_000_000) return false;
        if (currentTab === 'unusual-volume' && stock.rvol < 8) return false;
        if (currentTab === 'momentum' && !stock.momentum_score) return false;
        if (currentTab === 'alerts' && !stock.alert_level) return false;

        const ticker = (stock.ticker || '').toLowerCase();
        const companyName = (stock.company_name || '').toLowerCase();
        const ema = (stock.ema_alignment || '').toLowerCase();
        const hasNews = Boolean(stock.news_summary || stock.news_headline || stock.catalyst);

        if (columnFilters.ticker && !ticker.includes(columnFilters.ticker)) return false;
        if (columnFilters.company_name && !companyName.includes(columnFilters.company_name)) return false;
        if (columnFilters.price_min !== null && stock.price < columnFilters.price_min) return false;
        if (columnFilters.change_min !== null && stock.percent_change < columnFilters.change_min) return false;
        if (columnFilters.rvol_min !== null && stock.rvol < columnFilters.rvol_min) return false;
        if (columnFilters.volume_min_m !== null && (stock.volume / 1_000_000) < columnFilters.volume_min_m) return false;
        if (columnFilters.float_max_m !== null && (stock.float / 1_000_000) > columnFilters.float_max_m) return false;
        if (columnFilters.ema_alignment && !ema.includes(columnFilters.ema_alignment)) return false;
        if (columnFilters.news_mode === 'with_news' && !hasNews) return false;
        if (columnFilters.news_mode === 'no_news' && hasNews) return false;

        return true;
    });
}

function applyColumnFilters() {
    const getNum = (id) => {
        const el = document.getElementById(id);
        if (!el || el.value === '') return null;
        const v = parseFloat(el.value);
        return Number.isFinite(v) ? v : null;
    };

    columnFilters = {
        ticker: (document.getElementById('colFilterTicker')?.value || '').trim().toLowerCase(),
        company_name: (document.getElementById('colFilterName')?.value || '').trim().toLowerCase(),
        price_min: getNum('colFilterPriceMin'),
        change_min: getNum('colFilterChangeMin'),
        rvol_min: getNum('colFilterRvolMin'),
        volume_min_m: getNum('colFilterVolumeMin'),
        float_max_m: getNum('colFilterFloatMax'),
        ema_alignment: (document.getElementById('colFilterEma')?.value || '').trim().toLowerCase(),
        news_mode: (document.getElementById('colFilterNews')?.value || '').trim().toLowerCase()
    };

    renderStocks(allStocks);
}

function resetColumnFilters() {
    [
        'colFilterTicker', 'colFilterName', 'colFilterPriceMin', 'colFilterChangeMin',
        'colFilterRvolMin', 'colFilterVolumeMin', 'colFilterFloatMax', 'colFilterEma',
        'colFilterNews'
    ].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    columnFilters = {
        ticker: '',
        company_name: '',
        price_min: null,
        change_min: null,
        rvol_min: null,
        volume_min_m: null,
        float_max_m: null,
        ema_alignment: '',
        news_mode: ''
    };

    renderStocks(allStocks);
}

function sortStocks(stocks) {
    if (!sortState.key) return stocks;

    const sorted = [...stocks].sort((a, b) => {
        const multiplier = sortState.direction === 'asc' ? 1 : -1;
        return compareValues(a, b, sortState.key) * multiplier;
    });

    return sorted;
}

function compareValues(a, b, key) {
    const num = (val) => (typeof val === 'number' && !isNaN(val)) ? val : 0;

    switch (key) {
        case 'ticker':
            return (a.ticker || '').localeCompare(b.ticker || '');
        case 'company_name':
            return (a.company_name || '').localeCompare(b.company_name || '');
        case 'price':
            return num(a.price) - num(b.price);
        case 'percent_change':
            return num(a.percent_change) - num(b.percent_change);
        case 'rvol':
            return num(a.rvol) - num(b.rvol);
        case 'volume':
            return num(a.volume) - num(b.volume);
        case 'float':
            return num(a.float) - num(b.float);
        case 'ema_alignment':
            return (a.ema_alignment || '').localeCompare(b.ema_alignment || '');
        case 'alert_level':
            return (a.alert_level || '').localeCompare(b.alert_level || '');
        case 'news': {
            return (a.news_summary || a.news_headline || a.catalyst || '').localeCompare(
                b.news_summary || b.news_headline || b.catalyst || ''
            );
        }
        default:
            return 0;
    }
}

function setSort(key) {
    if (sortState.key === key) {
        sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc';
    } else {
        sortState = { key, direction: 'asc' };
    }

    renderStocks(allStocks);
    updateSortIndicators();
}

function updateSortIndicators() {
    document.querySelectorAll('.table-header .sortable').forEach(el => {
        const indicator = el.querySelector('.sort-indicator');
        const key = el.dataset.sort;

        if (!indicator) return;

        if (sortState.key === key) {
            indicator.textContent = sortState.direction === 'asc' ? '↑' : '↓';
        } else {
            indicator.textContent = '↕';
        }
    });
}

function toggleFilters() {
    const panel = document.getElementById('filtersPanel');
    panel.classList.toggle('collapsed');
}

function toggleSettingsSection(button) {
    const section = button.closest('.settings-section');
    if (!section) return;
    section.classList.toggle('active');
    updateMasterToggleLabel();
}

function toggleAllSections() {
    const sections = document.querySelectorAll('.settings-section[data-section]');
    const anyOpen = Array.from(sections).some(s => s.classList.contains('active'));
    sections.forEach(s => {
        if (anyOpen) s.classList.remove('active');
        else s.classList.add('active');
    });
    updateMasterToggleLabel();
}

function updateMasterToggleLabel() {
    const btn = document.getElementById('masterToggleBtn');
    if (!btn) return;
    const sections = document.querySelectorAll('.settings-section[data-section]');
    const anyOpen = Array.from(sections).some(s => s.classList.contains('active'));
    btn.textContent = anyOpen ? '▼ Collapse All' : '▶ Expand All';
}

function selectUniverseSize(btnEl) {
    document.querySelectorAll('#universeStack .stack-btn').forEach(b => b.classList.remove('active'));
    btnEl.classList.add('active');
    const hidden = document.getElementById('filterMoversScanLimit');
    if (hidden) hidden.value = btnEl.dataset.value;
    updateAllSectionCriteria();
}

// Section criteria display
function updateAllSectionCriteria() {
    document.querySelectorAll('.settings-section[data-section]').forEach(sec => {
        let existing = sec.querySelector('.section-criteria');
        if (!existing) {
            existing = document.createElement('div');
            existing.className = 'section-criteria';
            const toggle = sec.querySelector('.section-toggle');
            if (toggle) toggle.insertAdjacentElement('afterend', existing);
        }
        const parts = collectSectionCriteria(sec);
        existing.textContent = parts.length ? parts.join(' · ') : '';
    });
}

function collectSectionCriteria(sec) {
    const parts = [];
    // Number/range inputs
    sec.querySelectorAll('.section-body input[type="number"], .section-body input[type="text"][readonly]').forEach(inp => {
        if (inp.id && inp.id.endsWith('Slider')) return;
        const label = inp.closest('.filter-group')?.querySelector('label')?.textContent?.trim();
        if (!label) return;
        const val = inp.type === 'text' ? inp.value : inp.value;
        if (val && val !== '0' && val !== '00:00:00' && val !== '') {
            parts.push(`${label}: ${val}`);
        }
    });
    // Select inputs
    sec.querySelectorAll('.section-body select').forEach(sel => {
        const label = sel.closest('.filter-group')?.querySelector('label')?.textContent?.trim();
        if (!label) return;
        const opt = sel.options[sel.selectedIndex];
        if (opt && opt.value !== 'all' && opt.value !== '0') {
            parts.push(`${label}: ${opt.text}`);
        }
    });
    // Checkboxes
    sec.querySelectorAll('.section-body input[type="checkbox"]:checked').forEach(cb => {
        const lbl = cb.closest('label')?.textContent?.trim();
        if (lbl) parts.push(lbl);
    });
    // Button stack
    const activeStack = sec.querySelector('.stack-btn.active');
    if (activeStack) {
        const label = activeStack.closest('.filter-group')?.querySelector('label')?.textContent?.trim();
        if (label) parts.push(`${label}: ${activeStack.textContent}`);
    }
    return parts;
}

function resetSettingsDefaults() {
    setFilterInputs({
        price_min: 0,
        price_max: GLOBAL_MAX_PRICE,
        float_max: 20_000_000,
        relative_volume_min: 1,
        volume_min: 10_000,
        change_min: 3,
        ema_min_arrows: 0,
        news_mode: 'all',
        movers_scan_limit: 100,
        momentum_change_min: 12,
        momentum_rvol_min: 5,
        momentum_float_min: 10_000_000
    });
    showNotification('Settings reset to defaults', 'info');
}

function saveNamedPreset() {
    const name = window.prompt('Preset name');
    if (!name) return;
    const store = JSON.parse(localStorage.getItem(NAMED_PRESETS_STORAGE_KEY) || '{}');
    const payload = JSON.parse(localStorage.getItem(CUSTOM_PRESET_STORAGE_KEY) || '{}');
    if (!Object.keys(payload).length) {
        saveCustomPresetToStorage();
        store[name] = JSON.parse(localStorage.getItem(CUSTOM_PRESET_STORAGE_KEY) || '{}');
    } else {
        saveCustomPresetToStorage();
        store[name] = JSON.parse(localStorage.getItem(CUSTOM_PRESET_STORAGE_KEY) || '{}');
    }
    localStorage.setItem(NAMED_PRESETS_STORAGE_KEY, JSON.stringify(store));
    showNotification(`Preset saved: ${name}`, 'success');
}

function loadNamedPreset() {
    const store = JSON.parse(localStorage.getItem(NAMED_PRESETS_STORAGE_KEY) || '{}');
    const names = Object.keys(store);
    if (!names.length) {
        showNotification('No saved presets found', 'info');
        return;
    }
    const name = window.prompt(`Preset to load:\n${names.join('\n')}`);
    if (!name || !store[name]) return;
    const values = store[name];
    localStorage.setItem(CUSTOM_PRESET_STORAGE_KEY, JSON.stringify(values));
    restoreCustomPresetFromStorage();
    updateMomentumRadarTitleByPreset(document.getElementById('filterPreset')?.value || 'custom');
    showNotification(`Preset loaded: ${name}`, 'success');
}

function exportCurrentPreset() {
    saveCustomPresetToStorage();
    const payload = {
        preset: document.getElementById('filterPreset')?.value || 'custom',
        values: JSON.parse(localStorage.getItem(CUSTOM_PRESET_STORAGE_KEY) || '{}'),
        exported_at: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `scanner_preset_${payload.preset}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showNotification('Preset exported', 'success');
}

function importPresetFromJson() {
    const raw = window.prompt('Paste exported preset JSON here');
    if (!raw) return;
    try {
        const parsed = JSON.parse(raw);
        const values = parsed.values || parsed;
        localStorage.setItem(CUSTOM_PRESET_STORAGE_KEY, JSON.stringify(values));
        restoreCustomPresetFromStorage();

        const presetEl = document.getElementById('filterPreset');
        if (presetEl) {
            presetEl.value = parsed.preset && (parsed.preset in SETTINGS_PRESETS) ? parsed.preset : 'custom';
            presetEl.dataset.previousPreset = presetEl.value;
            renderPresetPlaybook(presetEl.value);
            updateMomentumRadarTitleByPreset(presetEl.value);
        }
        showNotification('Preset imported', 'success');
    } catch {
        showNotification('Invalid preset JSON', 'error');
    }
}

function manageNamedPresets() {
    const store = JSON.parse(localStorage.getItem(NAMED_PRESETS_STORAGE_KEY) || '{}');
    const names = Object.keys(store);
    if (!names.length) {
        showNotification('No saved presets to manage', 'info');
        return;
    }

    // Remove existing modal if any
    document.getElementById('presetManagerModal')?.remove();

    const overlay = document.createElement('div');
    overlay.id = 'presetManagerModal';
    overlay.className = 'preset-manager-overlay';

    const panel = document.createElement('div');
    panel.className = 'preset-manager-panel';

    const header = document.createElement('div');
    header.className = 'preset-manager-header';
    header.innerHTML = '<span>Manage Saved Presets</span>';
    const closeBtn = document.createElement('button');
    closeBtn.className = 'preset-manager-close';
    closeBtn.textContent = '\u2715';
    closeBtn.onclick = () => overlay.remove();
    header.appendChild(closeBtn);
    panel.appendChild(header);

    const list = document.createElement('div');
    list.className = 'preset-manager-list';

    function renderList() {
        const currentStore = JSON.parse(localStorage.getItem(NAMED_PRESETS_STORAGE_KEY) || '{}');
        const currentNames = Object.keys(currentStore);
        list.innerHTML = '';
        if (!currentNames.length) {
            list.innerHTML = '<div style="color:#71717a;text-align:center;padding:1rem;">No saved presets</div>';
            return;
        }
        currentNames.forEach(name => {
            const row = document.createElement('div');
            row.className = 'preset-manager-row';

            const label = document.createElement('span');
            label.className = 'preset-manager-name';
            label.textContent = name;

            const actions = document.createElement('div');
            actions.className = 'preset-manager-actions';

            const renameBtn = document.createElement('button');
            renameBtn.className = 'preset-manager-btn rename';
            renameBtn.textContent = 'Rename';
            renameBtn.onclick = () => {
                const newName = window.prompt('New name for preset:', name);
                if (!newName || newName === name) return;
                const s = JSON.parse(localStorage.getItem(NAMED_PRESETS_STORAGE_KEY) || '{}');
                if (s[newName]) {
                    if (!confirm(`Preset "${newName}" already exists. Overwrite?`)) return;
                }
                s[newName] = s[name];
                delete s[name];
                localStorage.setItem(NAMED_PRESETS_STORAGE_KEY, JSON.stringify(s));
                showNotification(`Renamed: ${name} → ${newName}`, 'success');
                renderList();
            };

            const updateBtn = document.createElement('button');
            updateBtn.className = 'preset-manager-btn update';
            updateBtn.textContent = 'Update';
            updateBtn.onclick = () => {
                if (!confirm(`Overwrite "${name}" with current settings?`)) return;
                saveCustomPresetToStorage();
                const s = JSON.parse(localStorage.getItem(NAMED_PRESETS_STORAGE_KEY) || '{}');
                s[name] = JSON.parse(localStorage.getItem(CUSTOM_PRESET_STORAGE_KEY) || '{}');
                localStorage.setItem(NAMED_PRESETS_STORAGE_KEY, JSON.stringify(s));
                showNotification(`Updated: ${name}`, 'success');
            };

            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'preset-manager-btn delete';
            deleteBtn.textContent = 'Delete';
            deleteBtn.onclick = () => {
                if (!confirm(`Delete preset "${name}"?`)) return;
                const s = JSON.parse(localStorage.getItem(NAMED_PRESETS_STORAGE_KEY) || '{}');
                delete s[name];
                localStorage.setItem(NAMED_PRESETS_STORAGE_KEY, JSON.stringify(s));
                showNotification(`Deleted: ${name}`, 'success');
                renderList();
            };

            actions.appendChild(renameBtn);
            actions.appendChild(updateBtn);
            actions.appendChild(deleteBtn);
            row.appendChild(label);
            row.appendChild(actions);
            list.appendChild(row);
        });
    }

    renderList();
    panel.appendChild(list);

    const footer = document.createElement('div');
    footer.className = 'preset-manager-footer';
    const doneBtn = document.createElement('button');
    doneBtn.className = 'mini-btn';
    doneBtn.textContent = 'Done';
    doneBtn.onclick = () => overlay.remove();
    footer.appendChild(doneBtn);
    panel.appendChild(footer);

    overlay.appendChild(panel);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
}

// ============ Tab Switching ============

function switchTab(tab) {
    currentTab = tab;

    // Update tab buttons
    document.querySelectorAll('.tab').forEach(btn => {
        btn.classList.remove('active');
    });
    const clicked = document.querySelector(`.tab[onclick="switchTab('${tab}')"]`);
    if (clicked) clicked.classList.add('active');

    // Re-render stocks
    renderStocks(allStocks);
}

// ============ Actions ============

async function addToWatchlist(ticker) {
    try {
        const response = await fetch(`/api/watchlist/add/${ticker}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.status === 'added') {
            showNotification(`${ticker} added to watchlist`, 'success');
        } else if (data.status === 'already_exists') {
            showNotification(`${ticker} already in watchlist`, 'info');
        }
    } catch (error) {
        console.error('Error adding to watchlist:', error);
    }
}

// ============ Scanner Updates ============

function handleScannerUpdate(data) {
    if (data.type === 'scanner_update') {
        const now = Date.now();
        if (now - lastWsReload < 4000) return;
        lastWsReload = now;
        loadStocks();
    }
}

function startScannerUpdates() {
    const refreshMs = Math.max(3000, getInputNumber('filterAutoRefresh', 12) * 1000);
    scannerInterval = setInterval(async () => {
        await refreshScanStatus();
        await loadStocks();
    }, refreshMs);
}

function restartScannerUpdates() {
    if (scannerInterval) clearInterval(scannerInterval);
    startScannerUpdates();
}

// ============ Notifications ============

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert-notification ${type}`;
    notification.innerHTML = `<strong>${message}</strong>`;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// ============ Utilities ============

function fmtNum(num, decimals = 2) {
    return Number(num).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtUSD(num) {
    return '$' + fmtNum(num, 2);
}

function formatNumber(num) {
    if (num >= 1_000_000) return fmtNum(num / 1_000_000, 1) + 'M';
    if (num >= 1_000) return fmtNum(num / 1_000, 1) + 'K';
    return fmtNum(num, 2);
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (wsScanner) wsScanner.close();
    if (countdownInterval) clearInterval(countdownInterval);
    if (scannerInterval) clearInterval(scannerInterval);
});
