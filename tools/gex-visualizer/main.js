// GEX Regime Trace Comparator - Main JavaScript
// Extracted from index.html for modularization

// --- CONFIGURATION ---
// Strike range - will be recalculated based on symbol price range
let strikeStart = 280;
let strikeEnd = 650;
let strikeStep = 10;
let strikes = [];
for(let s = strikeStart; s <= strikeEnd; s += strikeStep) strikes.push(s);

// Recalculate strikes based on price range
function updateStrikeRange(minPrice, maxPrice) {
    // Add 20% padding on each side
    const padding = (maxPrice - minPrice) * 0.2;
    strikeStart = Math.floor((minPrice - padding) / 10) * 10;
    strikeEnd = Math.ceil((maxPrice + padding) / 10) * 10;

    // Adjust step size based on price range
    const range = strikeEnd - strikeStart;
    if (range > 500) strikeStep = 20;
    else if (range > 200) strikeStep = 10;
    else if (range > 100) strikeStep = 5;
    else strikeStep = 2;

    // Rebuild strikes array
    strikes.length = 0;
    for(let s = strikeStart; s <= strikeEnd; s += strikeStep) {
        strikes.push(s);
    }

    // Update Y-axis base labels
    updateYAxisBaseLabels();
}

// Update Y-axis label base prices for new range
function updateYAxisBaseLabels() {
    const range = strikeEnd - strikeStart;
    const step = range / 4;
    const labels = [
        Math.round(strikeEnd),
        Math.round(strikeEnd - step),
        Math.round(strikeEnd - step * 2),
        Math.round(strikeEnd - step * 3),
        Math.round(strikeStart)
    ];

    document.querySelectorAll('.y-axis .y-label').forEach((label, idx) => {
        if (labels[idx] !== undefined) {
            label.dataset.basePrice = labels[idx];
            label.innerText = '$' + labels[idx];
        }
    });
}

// SPY Historical Timeline - Monthly EOD Regime Snapshots (2020-2025)
// Values represent end-of-day regime characteristics for each period
const timeline = [
    // 2020 - COVID Era
    { date: "2020-03-23", price: 222, oi: 3.5, tilt: -0.42, label: "COVID Bottom" },
    { date: "2020-06-08", price: 323, oi: 4.0, tilt: -0.15, label: "V-Shape Recovery" },
    { date: "2020-09-02", price: 357, oi: 4.3, tilt: -0.22, label: "Tech Bubble Peak" },
    { date: "2020-12-31", price: 373, oi: 4.5, tilt: -0.12, label: "Year End Rally" },
    // 2021 - Bull Run
    { date: "2021-02-12", price: 392, oi: 5.0, tilt: -0.08, label: "Meme Stock Era" },
    { date: "2021-05-07", price: 422, oi: 5.3, tilt: -0.14, label: "Inflation Fears Begin" },
    { date: "2021-09-02", price: 453, oi: 5.8, tilt: -0.18, label: "0DTE Growth Starts" },
    { date: "2021-12-31", price: 476, oi: 6.0, tilt: -0.15, label: "ATH Year End" },
    // 2022 - Bear Market
    { date: "2022-01-24", price: 436, oi: 6.2, tilt: -0.32, label: "Fed Pivot Fears" },
    { date: "2022-06-16", price: 366, oi: 6.5, tilt: -0.45, label: "Bear Market Low" },
    { date: "2022-08-16", price: 429, oi: 6.8, tilt: -0.25, label: "Bear Rally" },
    { date: "2022-10-12", price: 358, oi: 7.0, tilt: -0.38, label: "Retest Lows" },
    { date: "2022-12-30", price: 384, oi: 7.2, tilt: -0.28, label: "Choppy Year End" },
    // 2023 - Recovery
    { date: "2023-02-02", price: 418, oi: 7.5, tilt: -0.20, label: "AI Rally Begins" },
    { date: "2023-07-31", price: 457, oi: 8.0, tilt: -0.22, label: "Summer Melt-Up" },
    { date: "2023-10-27", price: 411, oi: 8.2, tilt: -0.35, label: "Rate Spike Selloff" },
    { date: "2023-12-28", price: 479, oi: 8.5, tilt: -0.18, label: "Santa Rally" },
    // 2024 - New Highs
    { date: "2024-03-28", price: 523, oi: 9.0, tilt: -0.20, label: "Q1 Breakout" },
    { date: "2024-07-16", price: 565, oi: 9.5, tilt: -0.25, label: "Summer ATH" },
    { date: "2024-11-11", price: 600, oi: 10.0, tilt: -0.30, label: "Election Rally" },
    // 2025 - Current
    { date: "2025-12-20", price: 605, oi: 11.0, tilt: -0.32, label: "Current (Today)" },
];

// --- STATE ---
let state = {
    price: 400,
    oi: 5,
    tilt: -0.15,
    simulating: false,
    simFrame: 0,
    persistenceDay: 1,
    currentIndex: -1,        // Current timeline position (-1 = not on timeline)
    playbackSpeed: 2,        // 1x, 2x, 4x
    isDragging: false,
    isResizing: false,
    yAxisScale: 1.0,         // Y-axis zoom scale (0.5 to 2.0)
    xAxisScale: 1.0,         // X-axis zoom scale (0.5 to 3.0) for gamma magnitude
    invertScroll: false,     // Invert scroll direction for price adjustment (default: off = visual mapping)
    yAxisDragging: false,    // Y-axis drag state
    xAxisDragging: false,    // X-axis drag state
    priceDragging: false,    // Chart panel drag for spot price
    dragStartY: 0,           // Starting Y position for drag
    dragStartX: 0,           // Starting X position for drag
    dragStartScale: 1.0,     // Starting scale value for drag
    dragStartPrice: 0        // Starting price for chart panel drag
};

// --- DOM ELEMENTS ---
const elPrice = document.getElementById('inp-price');
const elOi = document.getElementById('inp-oi');
const elTilt = document.getElementById('inp-tilt');

// --- CENTRALIZED STATE UPDATES ---
// These functions ensure all state changes are synchronized across UI and state

function setPrice(newPrice, enterManualMode = true) {
    // Clamp to valid range
    state.price = Math.max(280, Math.min(620, newPrice));
    // Sync slider
    elPrice.value = state.price;
    // Enter manual mode if not from timeline navigation
    if (enterManualMode) {
        state.currentIndex = -1;
    }
    updateEventDisplay();
    render();
}

function setOi(newOi, enterManualMode = true) {
    state.oi = Math.max(3, Math.min(12, newOi));
    elOi.value = state.oi;
    if (enterManualMode) {
        state.currentIndex = -1;
    }
    updateEventDisplay();
    render();
}

function setTilt(newTilt, enterManualMode = true) {
    state.tilt = Math.max(-0.5, Math.min(0.5, newTilt));
    elTilt.value = state.tilt;
    if (enterManualMode) {
        state.currentIndex = -1;
    }
    updateEventDisplay();
    render();
}
const vizNorm = document.getElementById('viz-norm');
const vizAbs = document.getElementById('viz-abs');
const insightBox = document.getElementById('insight-box');
const yearBadge = document.getElementById('year-badge');
const volWarning = document.getElementById('vol-warning');
const persistenceMeter = document.getElementById('persistence-meter');
const timelineTrack = document.getElementById('timeline-track');
const timelineProgress = document.getElementById('timeline-progress');
const timelineHandle = document.getElementById('timeline-handle');
const timelineMarkers = document.getElementById('timeline-markers');
const eventDate = document.getElementById('event-date');
const eventLabel = document.getElementById('event-label');
const eventIndex = document.getElementById('event-index');
const btnPlay = document.getElementById('btn-play');
const sparklinePath = document.getElementById('sparkline-path');
const sparklineArea = document.getElementById('sparkline-area');
const sparklineMarker = document.getElementById('sparkline-marker');
const sparklineCurrentLine = document.getElementById('sparkline-current-line');
const currentPriceLabel = document.getElementById('current-price-label');
const sparklineContainer = document.getElementById('price-sparkline');
const sparklineHoverLine = document.getElementById('sparkline-hover-line');
const sparklineHoverDot = document.getElementById('sparkline-hover-dot');
const sparklineTooltip = document.getElementById('sparkline-tooltip');
const tooltipDate = document.getElementById('tooltip-date');
const tooltipPrice = document.getElementById('tooltip-price');
const tooltipLabel = document.getElementById('tooltip-label');

// --- INITIALIZATION ---
function init() {
    createYAxisLabels('y-axis-norm');
    createYAxisLabels('y-axis-abs');
    createSvg('svg-norm', vizNorm);
    createSvg('svg-abs', vizAbs);
    createPersistenceMeter();
    createTimelineMarkers();
    createSparkline();
    setupSparklineInteraction();
    setupScrubber();
    render();

    elPrice.addEventListener('input', (e) => setPrice(parseFloat(e.target.value)));
    elOi.addEventListener('input', (e) => setOi(parseFloat(e.target.value)));
    elTilt.addEventListener('input', (e) => setTilt(parseFloat(e.target.value)));
}

// --- TIMELINE MARKERS ---
function getYear(dateStr) {
    return parseInt(dateStr.split('-')[0]);
}

function formatDate(dateStr) {
    const [year, month, day] = dateStr.split('-');
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[parseInt(month)-1]} ${parseInt(day)}, ${year}`;
}

function createTimelineMarkers() {
    const years = [...new Set(timeline.map(t => getYear(t.date)))];
    years.forEach(year => {
        const marker = document.createElement('span');
        marker.className = 'timeline-marker';
        marker.innerText = year;
        marker.onclick = () => jumpToYear(year);
        timelineMarkers.appendChild(marker);
    });
}

// --- SPARKLINE CHART ---
function createSparkline() {
    const prices = timeline.map(t => t.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const width = 200;
    const height = 60;
    const padding = 4;

    // Generate path data
    let pathD = '';
    let areaD = '';

    timeline.forEach((point, i) => {
        const x = (i / (timeline.length - 1)) * width;
        const y = height - padding - ((point.price - minPrice) / (maxPrice - minPrice)) * (height - padding * 2);

        if (i === 0) {
            pathD = `M ${x} ${y}`;
            areaD = `M ${x} ${height} L ${x} ${y}`;
        } else {
            pathD += ` L ${x} ${y}`;
            areaD += ` L ${x} ${y}`;
        }
    });

    // Close area path
    areaD += ` L ${width} ${height} Z`;

    sparklinePath.setAttribute('d', pathD);
    sparklineArea.setAttribute('d', areaD);

    // Hide marker initially
    sparklineMarker.setAttribute('cx', -10);
    sparklineMarker.setAttribute('cy', -10);
    sparklineCurrentLine.setAttribute('x1', -10);
    sparklineCurrentLine.setAttribute('x2', -10);
}

function updateSparkline() {
    const prices = timeline.map(t => t.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const width = 200;
    const height = 60;
    const padding = 4;

    if (state.currentIndex >= 0 && state.currentIndex < timeline.length) {
        // On historical timeline - show marker at correct position
        const x = (state.currentIndex / (timeline.length - 1)) * width;
        const price = timeline[state.currentIndex].price;
        const y = height - padding - ((price - minPrice) / (maxPrice - minPrice)) * (height - padding * 2);

        sparklineMarker.setAttribute('cx', x);
        sparklineMarker.setAttribute('cy', y);
        sparklineCurrentLine.setAttribute('x1', x);
        sparklineCurrentLine.setAttribute('x2', x);
        sparklineCurrentLine.setAttribute('y1', 0);
        sparklineCurrentLine.setAttribute('y2', height);

        currentPriceLabel.innerText = `$${price}`;
        currentPriceLabel.style.color = 'var(--warning-yellow)';
    } else {
        // Manual mode - hide marker (not on historical timeline)
        sparklineMarker.setAttribute('cx', -10);
        sparklineMarker.setAttribute('cy', -10);
        sparklineCurrentLine.setAttribute('x1', -10);
        sparklineCurrentLine.setAttribute('x2', -10);

        currentPriceLabel.innerText = `Manual: $${Math.round(state.price)}`;
        currentPriceLabel.style.color = 'var(--text-dim)';
    }
}

// --- SPARKLINE INTERACTION ---
function setupSparklineInteraction() {
    const prices = timeline.map(t => t.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);

    function getIndexFromX(clientX) {
        const rect = sparklineContainer.getBoundingClientRect();
        const pct = (clientX - rect.left) / rect.width;
        return Math.round(Math.max(0, Math.min(timeline.length - 1, pct * (timeline.length - 1))));
    }

    function getYForIndex(idx) {
        const height = 60;
        const padding = 4;
        const price = timeline[idx].price;
        return height - padding - ((price - minPrice) / (maxPrice - minPrice)) * (height - padding * 2);
    }

    sparklineContainer.addEventListener('mousemove', (e) => {
        const idx = getIndexFromX(e.clientX);
        const point = timeline[idx];
        const rect = sparklineContainer.getBoundingClientRect();
        const x = (idx / (timeline.length - 1)) * 200;
        const y = getYForIndex(idx);

        // Update hover elements
        sparklineHoverLine.setAttribute('x1', x);
        sparklineHoverLine.setAttribute('x2', x);
        sparklineHoverLine.style.opacity = '0.5';
        sparklineHoverDot.setAttribute('cx', x);
        sparklineHoverDot.setAttribute('cy', y);
        sparklineHoverDot.style.opacity = '1';

        // Update tooltip
        tooltipDate.innerText = formatDate(point.date);
        tooltipPrice.innerText = `$${point.price}`;
        tooltipLabel.innerText = point.label;

        // Position tooltip
        const tooltipX = Math.min(rect.width - 120, Math.max(0, (e.clientX - rect.left) - 60));
        sparklineTooltip.style.left = tooltipX + 'px';
        sparklineTooltip.style.top = '-50px';
        sparklineTooltip.classList.add('visible');
    });

    sparklineContainer.addEventListener('mouseleave', () => {
        sparklineHoverLine.style.opacity = '0';
        sparklineHoverDot.style.opacity = '0';
        sparklineTooltip.classList.remove('visible');
    });

    sparklineContainer.addEventListener('click', (e) => {
        const idx = getIndexFromX(e.clientX);
        if (state.simulating) toggleSimulation();
        goToIndex(idx);
    });
}

function jumpToYear(year) {
    const idx = timeline.findIndex(t => getYear(t.date) === year);
    if (idx >= 0) goToIndex(idx);
}

// --- SCRUBBER & RESIZE SETUP ---
const sidebarResize = document.getElementById('sidebar-resize');
const dashboard = document.getElementById('dashboard');

function setupScrubber() {
    // Click on track
    timelineTrack.addEventListener('click', (e) => {
        if (state.isDragging) return;
        const rect = timelineTrack.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        const idx = Math.round(pct * (timeline.length - 1));
        goToIndex(Math.max(0, Math.min(timeline.length - 1, idx)));
    });

    // Drag timeline handle
    timelineHandle.addEventListener('mousedown', (e) => {
        state.isDragging = true;
        e.preventDefault();
    });

    // Sidebar resize handle
    sidebarResize.addEventListener('mousedown', (e) => {
        state.isResizing = true;
        sidebarResize.classList.add('dragging');
        e.preventDefault();
    });

    // Global mousemove for both drags
    document.addEventListener('mousemove', (e) => {
        // Timeline scrubbing
        if (state.isDragging) {
            const rect = timelineTrack.getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            const idx = Math.round(pct * (timeline.length - 1));
            goToIndex(idx);
        }
        // Sidebar resizing
        if (state.isResizing) {
            const newWidth = Math.max(220, Math.min(400, e.clientX));
            dashboard.style.setProperty('--sidebar-width', newWidth + 'px');
        }
    });

    // Global mouseup
    document.addEventListener('mouseup', () => {
        state.isDragging = false;
        state.isResizing = false;
        sidebarResize.classList.remove('dragging');
    });

    // Keyboard controls
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT') return;
        switch(e.key) {
            case ' ': e.preventDefault(); toggleSimulation(); break;
            case 'ArrowRight': e.preventDefault(); stepForward(); break;
            case 'ArrowLeft': e.preventDefault(); stepBack(); break;
            case 'ArrowUp': e.preventDefault(); stepToNext(); break;
            case 'ArrowDown': e.preventDefault(); stepBackward(); break;
            case 'Home': e.preventDefault(); jumpToStart(); break;
            case 'End': e.preventDefault(); jumpToEnd(); break;
            case 'r': case 'R': e.preventDefault(); resetView(); break;
            case 'f': case 'F': e.preventDefault(); toggleFullscreen(); break;
        }
    });

    // Mouse wheel on chart panels to adjust spot price visually
    const chartPanels = document.querySelectorAll('.chart-panel');
    chartPanels.forEach(panel => {
        panel.addEventListener('wheel', (e) => {
            // Check if hovering over Y-axis or X-axis (let them handle their own scroll)
            if (e.target.closest('.y-axis') || e.target.closest('.x-axis')) return;

            e.preventDefault();
            if (state.simulating) return;

            // Scroll adjusts spot price
            const step = e.shiftKey ? 10 : 2; // Shift for larger steps
            let delta = e.deltaY > 0 ? -step : step;

            // Default (invertScroll OFF): scroll UP = price UP (visual/intuitive mapping)
            // invertScroll ON: scroll DOWN = price UP (natural scroll like mobile)
            if (state.invertScroll) delta = -delta;

            setPrice(state.price + delta);
        }, { passive: false });

        // Click-drag on chart panel to adjust spot price
        const startPriceDrag = (e) => {
            // Don't start if clicking on axis controls
            if (e.target.closest('.y-axis') || e.target.closest('.x-axis')) return;
            if (state.simulating) return;

            state.priceDragging = true;
            state.dragStartY = e.clientY || (e.touches && e.touches[0].clientY);
            state.dragStartPrice = state.price;
            panel.style.cursor = 'grabbing';
            e.preventDefault();
        };
        panel.addEventListener('mousedown', startPriceDrag);
        panel.addEventListener('touchstart', startPriceDrag, { passive: false });
    });

    // Y-axis scroll-to-scale (TradingView style)
    const yAxes = document.querySelectorAll('.y-axis');
    yAxes.forEach(yAxis => {
        yAxis.addEventListener('wheel', (e) => {
            e.preventDefault();
            e.stopPropagation();

            // Scroll up = zoom in (smaller scale factor shows more detail)
            // Scroll down = zoom out (larger scale factor compresses view)
            const scaleDelta = e.deltaY > 0 ? 0.1 : -0.1;
            state.yAxisScale = Math.max(0.2, Math.min(3.0, state.yAxisScale + scaleDelta));

            updateYAxisLabels();
            render();
        }, { passive: false });

        // Double-click to reset scale
        yAxis.addEventListener('dblclick', () => {
            state.yAxisScale = 1.0;
            updateYAxisLabels();
            render();
        });

        // Click-drag to scale (TradingView style, touchpad/mobile friendly)
        const startYDrag = (e) => {
            state.yAxisDragging = true;
            state.dragStartY = e.clientY || (e.touches && e.touches[0].clientY);
            state.dragStartScale = state.yAxisScale;
            yAxis.style.cursor = 'grabbing';
            e.preventDefault();
        };
        yAxis.addEventListener('mousedown', startYDrag);
        yAxis.addEventListener('touchstart', startYDrag, { passive: false });
    });

    // X-axis scroll-to-scale for magnitude
    const xAxes = document.querySelectorAll('.x-axis');
    xAxes.forEach(xAxis => {
        xAxis.addEventListener('wheel', (e) => {
            e.preventDefault();
            e.stopPropagation();

            // Scroll adjusts X-axis scale (magnitude zoom)
            const scaleDelta = e.deltaY > 0 ? 0.1 : -0.1;
            state.xAxisScale = Math.max(0.3, Math.min(3.0, state.xAxisScale + scaleDelta));

            updateXAxisLabels();
            render();
        }, { passive: false });

        // Double-click to reset X scale
        xAxis.addEventListener('dblclick', () => {
            state.xAxisScale = 1.0;
            updateXAxisLabels();
            render();
        });

        // Click-drag to scale (TradingView style, touchpad/mobile friendly)
        const startXDrag = (e) => {
            state.xAxisDragging = true;
            state.dragStartX = e.clientX || (e.touches && e.touches[0].clientX);
            state.dragStartScale = state.xAxisScale;
            xAxis.style.cursor = 'grabbing';
            e.preventDefault();
        };
        xAxis.addEventListener('mousedown', startXDrag);
        xAxis.addEventListener('touchstart', startXDrag, { passive: false });
    });

    // Global handlers for axis and price dragging
    const handleAxisDrag = (e) => {
        if (state.yAxisDragging) {
            const clientY = e.clientY || (e.touches && e.touches[0].clientY);
            const deltaY = state.dragStartY - clientY;
            // Drag up = zoom in, drag down = zoom out
            const scaleDelta = deltaY * 0.005;
            state.yAxisScale = Math.max(0.2, Math.min(3.0, state.dragStartScale + scaleDelta));
            updateYAxisLabels();
            render();
        }
        if (state.xAxisDragging) {
            const clientX = e.clientX || (e.touches && e.touches[0].clientX);
            const deltaX = clientX - state.dragStartX;
            // Drag right = zoom in, drag left = zoom out
            const scaleDelta = deltaX * 0.005;
            state.xAxisScale = Math.max(0.3, Math.min(3.0, state.dragStartScale + scaleDelta));
            updateXAxisLabels();
            render();
        }
        if (state.priceDragging) {
            const clientY = e.clientY || (e.touches && e.touches[0].clientY);
            const deltaY = state.dragStartY - clientY;
            // Sensitivity: ~1 price unit per 2 pixels
            let priceDelta = deltaY * 0.5;
            // Default (invertScroll OFF): drag UP = price UP (visual/intuitive mapping)
            // invertScroll ON: drag DOWN = price UP (natural scroll like mobile)
            if (state.invertScroll) priceDelta = -priceDelta;
            setPrice(state.dragStartPrice + priceDelta);
        }
    };

    const endAxisDrag = () => {
        if (state.yAxisDragging) {
            state.yAxisDragging = false;
            document.querySelectorAll('.y-axis').forEach(el => el.style.cursor = 'ns-resize');
        }
        if (state.xAxisDragging) {
            state.xAxisDragging = false;
            document.querySelectorAll('.x-axis').forEach(el => el.style.cursor = 'ew-resize');
        }
        if (state.priceDragging) {
            state.priceDragging = false;
            document.querySelectorAll('.chart-panel').forEach(el => el.style.cursor = 'grab');
        }
    };

    document.addEventListener('mousemove', handleAxisDrag);
    document.addEventListener('touchmove', handleAxisDrag, { passive: false });
    document.addEventListener('mouseup', endAxisDrag);
    document.addEventListener('touchend', endAxisDrag);

    // Position sidebar popup on hover (fixed positioning)
    const sidebarShortcuts = document.querySelector('.sidebar .shortcuts-help');
    if (sidebarShortcuts) {
        const popup = sidebarShortcuts.querySelector('.shortcuts-popup');
        const btn = sidebarShortcuts.querySelector('.shortcuts-btn');
        sidebarShortcuts.addEventListener('mouseenter', () => {
            const rect = btn.getBoundingClientRect();
            popup.style.left = (rect.left + rect.width / 2 - 90) + 'px';
            popup.style.top = (rect.top - popup.offsetHeight - 10) + 'px';
        });
    }
}

function createPersistenceMeter() {
    for (let i = 0; i < 8; i++) {
        const bar = document.createElement('div');
        bar.className = 'persistence-bar';
        bar.id = `persist-bar-${i}`;
        persistenceMeter.appendChild(bar);
    }
}

function createYAxisLabels(containerId) {
    const container = document.getElementById(containerId);
    const labels = [650, 560, 470, 380, 290];
    labels.forEach((price) => {
        const label = document.createElement('div');
        label.className = 'y-label';
        label.dataset.basePrice = price;
        label.innerText = '$' + price;
        container.appendChild(label);
    });
}

function updateYAxisLabels() {
    const scale = state.yAxisScale;
    const center = state.price;

    // Update label values
    document.querySelectorAll('.y-axis .y-label').forEach(label => {
        const basePrice = parseInt(label.dataset.basePrice);
        // Scale prices around current spot price
        const scaled = Math.round(center + (basePrice - center) * scale);
        label.innerText = '$' + scaled;
    });

    // Update scale indicator on Y-axis
    const scaleText = scale === 1.0 ? '1.0x' : scale.toFixed(1) + 'x';
    document.querySelectorAll('.y-axis').forEach(axis => {
        axis.dataset.scale = scaleText;
    });
}

function updateXAxisLabels() {
    const scale = state.xAxisScale;
    const baseMax = 50;
    const scaledMax = Math.round(baseMax / scale);

    // Update normalized chart labels
    const normLabels = document.querySelectorAll('#x-axis-norm .x-label');
    if (normLabels.length >= 4) {
        normLabels[0].innerText = `-${scaledMax}`;
        normLabels[1].innerText = `-${Math.round(scaledMax/2)}`;
        normLabels[2].innerText = `+${Math.round(scaledMax/2)}`;
        normLabels[3].innerText = `+${scaledMax}`;
    }

    // Update absolute chart labels (in billions)
    const absLabels = ['x-abs-min', 'x-abs-q1', 'x-abs-q3', 'x-abs-max'];
    const absValues = [-scaledMax, -Math.round(scaledMax/2), Math.round(scaledMax/2), scaledMax];
    absLabels.forEach((id, i) => {
        const el = document.getElementById(id);
        if (el) {
            const val = absValues[i];
            el.innerText = val < 0 ? `-$${Math.abs(val)}B` : `+$${val}B`;
        }
    });

    // Update scale indicator on X-axis
    const xScaleText = scale === 1.0 ? '' : scale.toFixed(1) + 'x zoom';
    document.querySelectorAll('.x-axis').forEach(axis => {
        axis.dataset.scale = xScaleText;
    });
}

function createSvg(id, container) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("id", id);

    // Center vertical line (0 axis)
    const centerLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    centerLine.setAttribute("class", "center-line");
    centerLine.setAttribute("x1", "50%");
    centerLine.setAttribute("x2", "50%");
    centerLine.setAttribute("y1", "0");
    centerLine.setAttribute("y2", "100%");
    svg.appendChild(centerLine);

    // Create bars for each strike
    strikes.forEach((_, i) => {
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("class", "bar");
        rect.setAttribute("x", "50%");
        rect.setAttribute("y", `${(i / strikes.length) * 100}%`);
        rect.setAttribute("height", `${85 / strikes.length}%`);
        rect.setAttribute("rx", "2");
        rect.setAttribute("id", `${id}-bar-${i}`);
        svg.appendChild(rect);
    });

    // Zero gamma line (horizontal)
    const zeroLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    zeroLine.setAttribute("class", "zero-gamma-line");
    zeroLine.setAttribute("x1", "0");
    zeroLine.setAttribute("x2", "100%");
    zeroLine.setAttribute("id", `${id}-zero`);
    svg.appendChild(zeroLine);

    // Zero gamma label
    const zeroLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    zeroLabel.setAttribute("class", "zero-marker");
    zeroLabel.setAttribute("x", "85%");
    zeroLabel.setAttribute("id", `${id}-zero-label`);
    zeroLabel.textContent = "0&#947;";
    svg.appendChild(zeroLabel);

    // Price line (horizontal)
    const priceLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    priceLine.setAttribute("class", "price-line");
    priceLine.setAttribute("x1", "0");
    priceLine.setAttribute("x2", "100%");
    priceLine.setAttribute("id", `${id}-price`);
    svg.appendChild(priceLine);

    // Price label
    const priceLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    priceLabel.setAttribute("class", "price-marker");
    priceLabel.setAttribute("x", "5");
    priceLabel.setAttribute("id", `${id}-price-label`);
    priceLabel.textContent = "SPOT";
    svg.appendChild(priceLabel);

    container.appendChild(svg);
}

// --- RENDER LOGIC ---
function render() {
    // Update Labels
    document.getElementById('lbl-price').innerText = '$' + Math.round(state.price);
    document.getElementById('lbl-oi').innerText = state.oi.toFixed(1) + "M";
    document.getElementById('lbl-tilt').innerText = state.tilt.toFixed(2);
    document.getElementById('header-price').innerText = Math.round(state.price);

    // Calculate S^2 factor
    const s2Scale = (state.price * state.price) / (300 * 300);
    document.getElementById('header-s2').innerText = s2Scale.toFixed(1) + "x";

    // Calculate zero gamma level (simplified: slightly above spot in negative gamma)
    const zeroGamma = Math.round(state.price * (1 + Math.abs(state.tilt) * 0.05));
    document.getElementById('zero-gamma-price').innerText = '$' + zeroGamma;

    // Calculate center index for current price
    const centerIndex = Math.floor((state.price - strikeStart) / strikeStep);
    const zeroIndex = Math.floor((zeroGamma - strikeStart) / strikeStep);
    const sigma = 12;

    let totalAbsGex = 0;
    let maxNormVal = 0;

    // Calculate center Y position (where current price is)
    // Invert Y so higher prices are at TOP (lower Y%), matching Y-axis labels
    const centerYPercent = 100 - (centerIndex / strikes.length) * 100;

    // Calculate GEX for each strike
    strikes.forEach((_, i) => {
        const dist = Math.abs(i - centerIndex);

        // Gamma peaks at ATM (Gaussian distribution)
        let gammaRaw = Math.exp(-(dist * dist) / (2 * (sigma / 2) * (sigma / 2)));

        // Apply dealer tilt
        let netGamma = gammaRaw * state.tilt;

        // FORMULA 1: NORMALIZED (Practitioner)
        let valNorm = netGamma * 50;

        // FORMULA 2: ABSOLUTE (Paper 2) with S^2 scaling
        const baselineS2 = 300 * 300;
        const currentS2 = state.price * state.price;
        const priceFactor = currentS2 / baselineS2;
        const baselineOI = 5;
        const oiFactor = state.oi / baselineOI;

        let valAbs = valNorm * priceFactor * oiFactor;

        totalAbsGex += Math.abs(valAbs) * 0.1;

        // Calculate scaled Y position for this bar
        // Invert Y so higher strikes are at TOP (lower Y%), matching Y-axis labels
        const baseY = 100 - (i / strikes.length) * 100;
        const scaledY = centerYPercent + (baseY - centerYPercent) * state.yAxisScale;

        updateBar('svg-norm', i, valNorm, scaledY);
        updateBar('svg-abs', i, valAbs, scaledY);

        if (Math.abs(valNorm) > maxNormVal) maxNormVal = Math.abs(valNorm);
    });

    // Update header GEX
    document.getElementById('header-gex').innerText = '$' + totalAbsGex.toFixed(0) + 'B';

    // Update price lines with scaling
    const priceY = Math.max(0, Math.min(100, centerYPercent));
    // Invert Y for zero gamma line to match chart orientation
    const zeroYBase = 100 - (zeroIndex / strikes.length) * 100;
    const zeroY = Math.max(0, Math.min(100, centerYPercent + (zeroYBase - centerYPercent) * state.yAxisScale));
    updatePriceLine('svg-norm', priceY, zeroY);
    updatePriceLine('svg-abs', priceY, zeroY);

    // Update data overlays
    document.getElementById('val-norm-max').innerText = maxNormVal.toFixed(2);
    document.getElementById('val-scale-factor').innerText = s2Scale.toFixed(1) + "x";
    document.getElementById('val-abs-total').innerText = "$" + totalAbsGex.toFixed(1) + "B";

    // Update volatility warning
    updateVolWarning();

    // Update persistence meter
    updatePersistence();

    // Update status indicators
    updateStatus(totalAbsGex, maxNormVal);

    // Update price sparkline
    updateSparkline();

    // Update Y-axis labels (for zoom state)
    updateYAxisLabels();

    // Update X-axis labels (for magnitude zoom)
    updateXAxisLabels();
}

function updateBar(svgId, index, val, scaledY) {
    const bar = document.getElementById(`${svgId}-bar-${index}`);
    if (!bar) return;

    // Apply X-axis scale to width (scale > 1 = zoom in = bars appear wider)
    const scaledVal = val * state.xAxisScale;
    const width = Math.min(Math.abs(scaledVal), 48);
    bar.setAttribute("width", `${width}%`);

    // Update Y position with scaling
    const barHeight = (85 / strikes.length) * state.yAxisScale;
    bar.setAttribute("y", `${scaledY}%`);
    bar.setAttribute("height", `${Math.max(0.5, barHeight)}%`);

    if (val < 0) {
        bar.setAttribute("fill", "#ff3d57");
        bar.setAttribute("x", `${50 - width}%`);
    } else {
        bar.setAttribute("fill", "#00e5ff");
        bar.setAttribute("x", "50%");
    }

    // Saturation warning for absolute chart (check original value, not scaled)
    if (svgId === 'svg-abs' && Math.abs(val) > 45 / state.xAxisScale) {
        bar.setAttribute("fill", "#ffffff");
    }

    // Hide bars that are off-screen (Y)
    if (scaledY < -10 || scaledY > 110) {
        bar.setAttribute("opacity", "0");
    } else {
        bar.setAttribute("opacity", "0.85");
    }
}

function updatePriceLine(svgId, priceY, zeroY) {
    const priceLine = document.getElementById(`${svgId}-price`);
    const priceLabel = document.getElementById(`${svgId}-price-label`);
    const zeroLine = document.getElementById(`${svgId}-zero`);
    const zeroLabel = document.getElementById(`${svgId}-zero-label`);

    if (priceLine) {
        priceLine.setAttribute("y1", `${priceY}%`);
        priceLine.setAttribute("y2", `${priceY}%`);
    }
    if (priceLabel) {
        priceLabel.setAttribute("y", `${priceY - 1}%`);
    }
    if (zeroLine) {
        zeroLine.setAttribute("y1", `${zeroY}%`);
        zeroLine.setAttribute("y2", `${zeroY}%`);
    }
    if (zeroLabel) {
        zeroLabel.setAttribute("y", `${zeroY - 1}%`);
        zeroLabel.textContent = "0γ";
    }
}

function updateVolWarning() {
    const isNegativeGamma = state.tilt < -0.25;
    const isPositiveGamma = state.tilt > 0.25;
    const volStatus = document.getElementById('vol-status');
    const volAmp = document.getElementById('vol-amp');
    const volProb = document.getElementById('vol-prob');

    // Remove all state classes first
    volWarning.classList.remove('active', 'inactive', 'positive', 'negative');

    if (isNegativeGamma) {
        volWarning.classList.add('active', 'negative');
        volStatus.innerText = 'NEGATIVE GAMMA REGIME';
        // Scale amplification based on how negative
        const amp = (3.81 * (Math.abs(state.tilt) / 0.35)).toFixed(1);
        const prob = (10.1 * (Math.abs(state.tilt) / 0.35)).toFixed(1);
        volAmp.innerText = amp + 'x';
        volProb.innerText = prob + 'x';
        // Update labels for negative gamma context
        volAmp.parentElement.querySelector('.vol-stat-label').innerText = 'Vol Amp:';
        volProb.parentElement.querySelector('.vol-stat-label').innerText = 'Extreme Prob:';
    } else if (isPositiveGamma) {
        volWarning.classList.add('active', 'positive');
        volStatus.innerText = 'POSITIVE GAMMA REGIME';
        // Positive gamma = dampening effect
        const damp = (1 / (1 + state.tilt * 2)).toFixed(2);
        const stability = Math.min(99, Math.round(50 + state.tilt * 100));
        volAmp.innerText = damp + 'x';
        volProb.innerText = stability + '%';
        // Update labels for positive gamma context
        volAmp.parentElement.querySelector('.vol-stat-label').innerText = 'Vol Damp:';
        volProb.parentElement.querySelector('.vol-stat-label').innerText = 'Stability:';
    } else {
        volWarning.classList.add('inactive');
        volStatus.innerText = 'GAMMA STATUS: NEUTRAL';
        volAmp.innerText = '1.0x';
        volProb.innerText = '-';
        volAmp.parentElement.querySelector('.vol-stat-label').innerText = 'Vol Effect:';
        volProb.parentElement.querySelector('.vol-stat-label').innerText = 'Outlook:';
    }
}

function updatePersistence() {
    const isNegative = state.tilt < -0.2;
    const isPositive = state.tilt > 0.2;
    const avgDays = isNegative ? 5 : (isPositive ? 10 : 8);
    document.getElementById('persist-days').innerText = '~' + avgDays + ' days';
    document.getElementById('persist-current').innerText = 'Day ' + state.persistenceDay;

    for (let i = 0; i < 8; i++) {
        const bar = document.getElementById(`persist-bar-${i}`);
        bar.classList.remove('active', 'negative', 'positive');
        if (i < state.persistenceDay) {
            bar.classList.add('active');
            if (isNegative) bar.classList.add('negative');
            else if (isPositive) bar.classList.add('positive');
        }
    }
}

function updateStatus(absTotal, _normMax) {
    const statNorm = document.getElementById('status-norm');
    const statAbs = document.getElementById('status-abs');
    const isNegative = state.tilt < 0;

    // Colors based on gamma direction
    const positiveColor = "#00e5ff";  // Cyan - stabilizing
    const negativeColor = "#ff3d57";  // Red - amplifying
    const elevatedColor = "#ff9100";  // Orange - watching
    const neutralColor = "#8b9bb4";   // Dim - neutral

    // Practitioner status - direction matters
    if (Math.abs(state.tilt) > 0.35) {
        statNorm.innerText = isNegative ? "STRONG SHORT γ" : "STRONG LONG γ";
        statNorm.style.color = isNegative ? negativeColor : positiveColor;
        statNorm.style.textShadow = isNegative
            ? "0 0 8px rgba(255, 61, 87, 0.4)"
            : "0 0 8px rgba(0, 229, 255, 0.4)";
    } else if (Math.abs(state.tilt) > 0.2) {
        statNorm.innerText = isNegative ? "SHORT γ BIAS" : "LONG γ BIAS";
        statNorm.style.color = isNegative ? elevatedColor : positiveColor;
        statNorm.style.textShadow = "none";
    } else {
        statNorm.innerText = "NEUTRAL";
        statNorm.style.color = neutralColor;
        statNorm.style.textShadow = "none";
    }

    // Absolute status - also respects direction
    if (absTotal > 20) {
        statAbs.innerText = isNegative ? "REGIME: SHORT γ" : "REGIME: LONG γ";
        statAbs.style.color = isNegative ? negativeColor : positiveColor;
        statAbs.style.textShadow = isNegative
            ? "0 0 10px rgba(255, 61, 87, 0.6)"
            : "0 0 10px rgba(0, 229, 255, 0.6)";
    } else if (absTotal > 12) {
        statAbs.innerText = "ELEVATED";
        statAbs.style.color = elevatedColor;
        statAbs.style.textShadow = "none";
    } else {
        statAbs.innerText = "NO REGIME";
        statAbs.style.color = neutralColor;
        statAbs.style.textShadow = "none";
    }

    updateInsight(absTotal);
}

function updateInsight(absTotal) {
    let msg = "";
    const s2 = (state.price * state.price / 90000).toFixed(1);

    if (state.price > 550 && state.oi > 8) {
        msg = `<strong>&#9888; INFLATION ARTIFACT:</strong> Right panel shows "$${absTotal.toFixed(0)}B regime" at SPY $${Math.round(state.price)} (S&#178;=${s2}x). Left panel correctly shows this is dealer positioning, not a true regime. <em>This is why Paper 2 methodology over-detects in 2024-2025.</em>`;
    } else if (state.tilt < -0.3) {
        msg = `<strong style="color:#ff3d57">&#9888; SHORT GAMMA REGIME:</strong> Research shows 3.81x volatility amplification. UVXY typically leads SPY by 1 day. Dealers amplify moves. Expect regime to persist ~5 days average.`;
    } else if (state.tilt > 0.3) {
        msg = `<strong style="color:#2ed573">&#10003; LONG GAMMA REGIME:</strong> Dealers are long gamma - they dampen volatility by buying dips and selling rallies. Market stabilization effect. Expect regime to persist ~10 days average.`;
    } else if (state.price < 350) {
        msg = `<strong>2020 BASELINE:</strong> At $${Math.round(state.price)}, both methods align. Move price to 2024-2025 levels ($550+) to see S&#178; divergence. GEX research validated with 50.88M options records.`;
    } else {
        msg = `Run simulation to watch S&#178; factor cause methodology divergence as SPY doubles from 2020 ($300) to 2025 ($600). Normalized ratio stays stable while absolute GEX inflates.`;
    }

    insightBox.innerHTML = msg;
}

// --- MEDIA CONTROLS ---
function goToIndex(idx) {
    if (idx < 0 || idx >= timeline.length) return;

    state.currentIndex = idx;
    const point = timeline[idx];

    // Update state values
    state.price = point.price;
    state.oi = point.oi;
    state.tilt = point.tilt;

    // Sync all UI controls
    syncControlsToState();

    updateTimeline();
    updateEventDisplay();
    updateRealDataMetrics(point);
    render();
}

// Update real data metrics panel (only shown in real data mode)
function updateRealDataMetrics(point) {
    const metricsPanel = document.getElementById('real-data-metrics');
    if (!metricsPanel) return;

    // Only show in real data mode with _raw data
    if (DataLoader.dataMode !== 'real' || !point._raw) {
        metricsPanel.style.display = 'none';
        return;
    }

    metricsPanel.style.display = 'block';
    const raw = point._raw;

    // Quality score (0-1 scale)
    const qualityEl = document.getElementById('rdm-quality');
    if (raw.quality !== null && raw.quality !== undefined) {
        const pct = Math.round(raw.quality * 100);
        qualityEl.textContent = pct + '%';
        qualityEl.className = 'rdm-value ' +
            (pct >= 80 ? 'quality-good' : pct >= 50 ? 'quality-fair' : 'quality-poor');
    } else {
        qualityEl.textContent = '-';
        qualityEl.className = 'rdm-value';
    }

    // Contract count
    const contractsEl = document.getElementById('rdm-contracts');
    if (raw.contracts) {
        contractsEl.textContent = raw.contracts.toLocaleString();
    } else {
        contractsEl.textContent = '-';
    }

    // Call/Put gamma balance
    const gammaEl = document.getElementById('rdm-gamma-balance');
    if (raw.call_gex !== null && raw.put_gex !== null) {
        const callGex = raw.call_gex || 0;
        const putGex = raw.put_gex || 0;
        const ratio = callGex !== 0 || putGex !== 0
            ? (callGex / (Math.abs(callGex) + Math.abs(putGex)) * 100).toFixed(0)
            : 50;
        const isPositive = callGex > Math.abs(putGex);
        gammaEl.textContent = ratio + '% / ' + (100 - ratio) + '%';
        gammaEl.className = 'rdm-value ' + (isPositive ? 'gamma-positive' : 'gamma-negative');
    } else {
        gammaEl.textContent = '-';
        gammaEl.className = 'rdm-value';
    }
}

// Sync all slider controls to current state values
function syncControlsToState() {
    elPrice.value = state.price;
    elOi.value = state.oi;
    elTilt.value = state.tilt;
}

function updateTimeline() {
    const pct = state.currentIndex >= 0 ? (state.currentIndex / (timeline.length - 1)) * 100 : 0;
    timelineProgress.style.width = pct + '%';
    timelineHandle.style.left = pct + '%';

    // Update year badge
    if (state.currentIndex >= 0) {
        const point = timeline[state.currentIndex];
        yearBadge.innerText = getYear(point.date);
        yearBadge.classList.remove('inactive');
    } else {
        yearBadge.innerText = '----';
        yearBadge.classList.add('inactive');
    }

    // Update year markers
    const markers = timelineMarkers.querySelectorAll('.timeline-marker');
    const currentYear = state.currentIndex >= 0 ? getYear(timeline[state.currentIndex].date) : null;
    markers.forEach(m => {
        m.classList.toggle('active', parseInt(m.innerText) === currentYear);
    });
}

function updateEventDisplay() {
    if (state.currentIndex >= 0 && state.currentIndex < timeline.length) {
        const point = timeline[state.currentIndex];
        eventDate.innerText = formatDate(point.date);
        eventLabel.innerText = point.label;
        eventIndex.innerText = `Snapshot ${state.currentIndex + 1} of ${timeline.length} | SPY $${point.price}`;
    } else {
        eventDate.innerText = 'Manual Mode';
        eventLabel.innerText = 'Adjust parameters with sliders';
        eventIndex.innerText = '--';
    }
}

// Step controls
function stepForward() {
    if (state.simulating) return;
    if (state.currentIndex < 0) state.currentIndex = -1;
    if (state.currentIndex < timeline.length - 1) {
        goToIndex(state.currentIndex + 1);
    }
}

function stepBack() {
    if (state.simulating) return;
    if (state.currentIndex > 0) {
        goToIndex(state.currentIndex - 1);
    } else if (state.currentIndex < 0) {
        goToIndex(0);
    }
}

function stepToNext() {
    if (state.simulating) return;
    // Jump to next major event (different year)
    if (state.currentIndex < 0) {
        goToIndex(0);
        return;
    }
    const currentYear = getYear(timeline[state.currentIndex].date);
    for (let i = state.currentIndex + 1; i < timeline.length; i++) {
        if (getYear(timeline[i].date) !== currentYear) {
            goToIndex(i);
            return;
        }
    }
    goToIndex(timeline.length - 1);
}

function stepBackward() {
    if (state.simulating) return;
    // Jump to previous major event (different year)
    if (state.currentIndex <= 0) {
        goToIndex(0);
        return;
    }
    const currentYear = getYear(timeline[state.currentIndex].date);
    for (let i = state.currentIndex - 1; i >= 0; i--) {
        if (getYear(timeline[i].date) !== currentYear) {
            goToIndex(i);
            return;
        }
    }
    goToIndex(0);
}

function jumpToStart() {
    if (state.simulating) toggleSimulation();
    goToIndex(0);
}

function jumpToEnd() {
    if (state.simulating) toggleSimulation();
    goToIndex(timeline.length - 1);
}

// Speed control
function setSpeed(speed) {
    state.playbackSpeed = speed;
    document.querySelectorAll('.speed-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById('speed-' + speed).classList.add('active');
}

// --- SIMULATION ---
let simInterval = null;

function toggleSimulation() {
    if (state.simulating) {
        // Pause
        state.simulating = false;
        clearInterval(simInterval);
        btnPlay.classList.remove('playing');
        btnPlay.innerHTML = '&#9654;';
        return;
    }

    // Start playing
    state.simulating = true;
    btnPlay.classList.add('playing');
    btnPlay.innerHTML = '&#9724;'; // Pause icon

    if (state.currentIndex < 0) state.currentIndex = 0;
    if (state.currentIndex >= timeline.length - 1) state.currentIndex = 0;

    state.persistenceDay = 1;
    let lastTilt = timeline[state.currentIndex].tilt;
    let subFrame = 0;
    const framesPerPoint = 20;

    simInterval = setInterval(() => {
        if (!state.simulating) {
            clearInterval(simInterval);
            return;
        }

        subFrame++;

        if (subFrame >= framesPerPoint) {
            subFrame = 0;
            state.currentIndex++;

            if (state.currentIndex >= timeline.length) {
                // End of timeline
                state.currentIndex = timeline.length - 1;
                state.simulating = false;
                clearInterval(simInterval);
                btnPlay.classList.remove('playing');
                btnPlay.innerHTML = '&#9654;';
                goToIndex(state.currentIndex);
                return;
            }
        }

        // Interpolate between points
        const curr = timeline[state.currentIndex];
        const next = timeline[Math.min(state.currentIndex + 1, timeline.length - 1)];
        const progress = subFrame / framesPerPoint;

        state.price = curr.price + (next.price - curr.price) * progress;
        state.oi = curr.oi + (next.oi - curr.oi) * progress;
        state.tilt = curr.tilt + (next.tilt - curr.tilt) * progress;

        // Track regime persistence
        if (Math.abs(state.tilt - lastTilt) > 0.08) {
            state.persistenceDay = 1;
            lastTilt = state.tilt;
        } else if (subFrame === 0) {
            state.persistenceDay = Math.min(8, state.persistenceDay + 1);
        }

        syncControlsToState();
        updateTimeline();
        updateEventDisplay();
        render();
    }, 80 / state.playbackSpeed);
}

function resetToDefaults() {
    if (state.simulating) toggleSimulation();

    state.price = 400;
    state.oi = 5;
    state.tilt = -0.15;
    state.currentIndex = -1;
    state.persistenceDay = 1;
    state.yAxisScale = 1.0;
    state.xAxisScale = 1.0;

    syncControlsToState();
    updateTimeline();
    updateEventDisplay();
    render();
}

function toggleInvertScroll() {
    state.invertScroll = !state.invertScroll;
    const toggle = document.getElementById('invert-toggle');
    if (state.invertScroll) {
        toggle.classList.add('active');
    } else {
        toggle.classList.remove('active');
    }
}

function resetView() {
    // Reset zoom scales to default
    state.yAxisScale = 1.0;
    state.xAxisScale = 1.0;

    // Update displays
    updateYAxisLabels();
    updateXAxisLabels();
    render();

    // Visual feedback - briefly highlight the reset button
    const btn = document.getElementById('btn-reset-view');
    if (btn) {
        btn.style.color = 'var(--accent-cyan)';
        btn.style.borderColor = 'var(--accent-cyan)';
        btn.style.transform = 'scale(1.1)';
        setTimeout(() => {
            btn.style.color = '';
            btn.style.borderColor = '';
            btn.style.transform = '';
        }, 200);
    }
}

function toggleFullscreen() {
    const dashboard = document.getElementById('dashboard');
    if (!document.fullscreenElement) {
        // Enter fullscreen
        if (dashboard.requestFullscreen) {
            dashboard.requestFullscreen();
        } else if (dashboard.webkitRequestFullscreen) {
            dashboard.webkitRequestFullscreen();
        } else if (dashboard.msRequestFullscreen) {
            dashboard.msRequestFullscreen();
        }
    } else {
        // Exit fullscreen
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }
}

// --- DATA MODE FUNCTIONS ---

// Store original demo timeline for switching back
const demoTimeline = [...timeline];

async function setDataMode(mode) {
    // Update button states
    document.getElementById('mode-demo').classList.toggle('active', mode === 'demo');
    document.getElementById('mode-real').classList.toggle('active', mode === 'real');

    // Show/hide symbol selectors
    const selectors = document.getElementById('symbol-selectors');
    selectors.style.display = mode === 'real' ? 'block' : 'none';

    if (mode === 'demo') {
        // Restore demo timeline
        DataLoader.dataMode = 'demo';
        timeline.length = 0;
        timeline.push(...demoTimeline);

        // Reset strike range to SPY defaults
        updateStrikeRange(222, 605);
        rebuildCharts();

        // Reset to demo state
        updateHeaderSymbol('SPY');
        updatePriceRange(222, 605);
        resetToDefaults();
        createSparkline();

        // Clear and rebuild timeline markers
        const markersContainer = document.getElementById('timeline-markers');
        markersContainer.innerHTML = '';
        createTimelineMarkers();
    } else {
        // Switch to real data mode
        DataLoader.dataMode = 'real';

        // Load index if not already loaded
        if (!DataLoader.index) {
            await DataLoader.loadIndex();
            if (!DataLoader.index) {
                alert('Could not load data. Make sure to run export_data.py first.');
                setDataMode('demo');
                return;
            }
        }

        // Populate asset class dropdown
        populateAssetClasses();

        // Auto-select equity and SPY if available
        const assetSelect = document.getElementById('asset-class-select');
        if (DataLoader.index.asset_classes['equity']) {
            assetSelect.value = 'equity';
            onAssetClassChange();
            const symbolSelect = document.getElementById('symbol-select');
            if (DataLoader.index.asset_classes['equity'].includes('SPY')) {
                symbolSelect.value = 'SPY';
                await onSymbolChange();
            }
        }
    }
}

function populateAssetClasses() {
    const select = document.getElementById('asset-class-select');
    select.innerHTML = '';

    const classes = DataLoader.getAssetClasses();
    classes.forEach(cls => {
        const option = document.createElement('option');
        option.value = cls;
        option.textContent = cls.charAt(0).toUpperCase() + cls.slice(1);
        select.appendChild(option);
    });
}

function onAssetClassChange() {
    const assetClass = document.getElementById('asset-class-select').value;
    const symbolSelect = document.getElementById('symbol-select');

    symbolSelect.innerHTML = '<option value="">Select symbol...</option>';

    const symbols = DataLoader.getSymbolsForClass(assetClass);
    symbols.forEach(sym => {
        const option = document.createElement('option');
        option.value = sym;
        option.textContent = sym;
        symbolSelect.appendChild(option);
    });

    // Clear data info
    document.getElementById('data-info').innerHTML = '';
}

async function onSymbolChange() {
    const symbol = document.getElementById('symbol-select').value;
    if (!symbol) return;

    // Show loading state
    document.getElementById('data-info').innerHTML = 'Loading...';

    // Load symbol data
    const data = await DataLoader.loadSymbol(symbol);
    if (!data) {
        document.getElementById('data-info').innerHTML = '<span style="color:var(--accent-red)">Failed to load data</span>';
        return;
    }

    // Transform to timeline format
    const newTimeline = DataLoader.transformToTimeline(data);

    // Update global timeline
    timeline.length = 0;
    timeline.push(...newTimeline);

    // Update UI
    const info = DataLoader.getSymbolInfo(symbol);
    document.getElementById('data-info').innerHTML =
        `<strong>${data.count}</strong> days (${info.date_range.start} to ${info.date_range.end})`;

    // Update header to show current symbol
    updateHeaderSymbol(symbol);

    // Update price range in sparkline header and chart scaling
    const prices = newTimeline.map(p => p.price).filter(p => p);
    if (prices.length > 0) {
        const minPrice = Math.min(...prices);
        const maxPrice = Math.max(...prices);
        updatePriceRange(minPrice, maxPrice);

        // Update strike range for new symbol's price range
        updateStrikeRange(minPrice, maxPrice);

        // Rebuild SVG charts with new strike range
        rebuildCharts();
    }

    // Rebuild visualizer with new data
    if (state.simulating) toggleSimulation();
    state.currentIndex = -1;

    // Clear and rebuild timeline markers
    const markersContainer = document.getElementById('timeline-markers');
    markersContainer.innerHTML = '';
    createTimelineMarkers();

    // Rebuild sparkline
    createSparkline();

    // Reset to first point
    if (timeline.length > 0) {
        goToIndex(0);
    }
}

// Rebuild chart SVGs with current strike range
function rebuildCharts() {
    // Clear existing SVGs
    const vizNorm = document.getElementById('viz-norm');
    const vizAbs = document.getElementById('viz-abs');

    vizNorm.innerHTML = '';
    vizAbs.innerHTML = '';

    // Recreate SVGs with new strike count
    createSvg('svg-norm', vizNorm);
    createSvg('svg-abs', vizAbs);
}

function updateHeaderSymbol(symbol) {
    const priceLabel = document.querySelector('.metric-card .metric-label');
    if (priceLabel && priceLabel.textContent.includes('Price')) {
        priceLabel.textContent = `${symbol} Price`;
    }

    // Update sparkline title
    const sparkTitle = document.querySelector('.price-chart-title');
    if (sparkTitle) {
        const years = timeline.length > 0
            ? `${getYear(timeline[0].date)}-${getYear(timeline[timeline.length - 1].date)}`
            : '----';
        sparkTitle.textContent = `${symbol} ${years}`;
    }
}

function updatePriceRange(min, max) {
    const rangeEl = document.getElementById('price-range');
    if (rangeEl) {
        rangeEl.textContent = `$${Math.round(min)} - $${Math.round(max)}`;
    }

    // Update price slider range
    const priceSlider = document.getElementById('inp-price');
    if (priceSlider) {
        priceSlider.min = Math.floor(min * 0.8);
        priceSlider.max = Math.ceil(max * 1.1);
    }
}

// Initialize on load
async function initApp() {
    init();

    // Pre-load data index (non-blocking)
    DataLoader.loadIndex().then(() => {
        if (DataLoader.index) {
            console.log(`GEX Data: ${DataLoader.index.symbols.length} symbols available`);
        }
    });
}

initApp();
