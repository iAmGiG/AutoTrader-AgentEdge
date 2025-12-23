// GEX Visualizer - UI Updates
// DOM updates, labels, status indicators, persistence meter

const { state, timeline, getYear, formatDate, strikeStart, strikeEnd } = window.GEX;

// --- DOM ELEMENTS ---
const elPrice = document.getElementById('inp-price');
const elOi = document.getElementById('inp-oi');
const elTilt = document.getElementById('inp-tilt');
const insightBox = document.getElementById('insight-box');
const yearBadge = document.getElementById('year-badge');
const volWarning = document.getElementById('vol-warning');
const persistenceMeter = document.getElementById('persistence-meter');
const eventDate = document.getElementById('event-date');
const eventLabel = document.getElementById('event-label');
const eventIndex = document.getElementById('event-index');

// --- CENTRALIZED STATE UPDATES ---
function setPrice(newPrice, enterManualMode = true) {
    const { strikeStart, strikeEnd } = window.GEX;
    state.price = Math.max(strikeStart, Math.min(strikeEnd, newPrice));
    elPrice.value = state.price;
    if (enterManualMode) state.currentIndex = -1;
    updateEventDisplay();
    window.GEX.render();
}

function setOi(newOi, enterManualMode = true) {
    state.oi = Math.max(3, Math.min(12, newOi));
    elOi.value = state.oi;
    if (enterManualMode) state.currentIndex = -1;
    updateEventDisplay();
    window.GEX.render();
}

function setTilt(newTilt, enterManualMode = true) {
    state.tilt = Math.max(-0.5, Math.min(0.5, newTilt));
    elTilt.value = state.tilt;
    if (enterManualMode) state.currentIndex = -1;
    updateEventDisplay();
    window.GEX.render();
}

function syncControlsToState() {
    elPrice.value = state.price;
    elOi.value = state.oi;
    elTilt.value = state.tilt;
}

// --- UI UPDATES ---
function updateEventDisplay() {
    if (state.currentIndex >= 0 && state.currentIndex < timeline.length) {
        const point = timeline[state.currentIndex];
        eventDate.innerText = formatDate(point.date);
        eventLabel.innerText = point.label;
        eventIndex.innerText = `Snapshot ${state.currentIndex + 1} of ${timeline.length}`;
        yearBadge.innerText = getYear(point.date);
        yearBadge.style.display = 'inline-block';
    } else {
        eventDate.innerText = 'Manual Mode';
        eventLabel.innerText = 'Use sliders to explore';
        eventIndex.innerText = '-';
        yearBadge.style.display = 'none';
    }
}

function updateYAxisLabels() {
    const scale = state.yAxisScale;
    const { strikeStart, strikeEnd } = window.GEX;
    const range = strikeEnd - strikeStart;
    const center = (strikeStart + strikeEnd) / 2;
    const scaledRange = range / scale;

    document.querySelectorAll('.y-axis .y-label').forEach((label) => {
        const basePrice = parseFloat(label.dataset.basePrice);
        const offset = basePrice - center;
        const scaledPrice = Math.round(center + offset / scale);
        label.innerText = '$' + scaledPrice;
    });

    const scaleText = scale === 1.0 ? '1.0x' : scale.toFixed(1) + 'x';
    document.querySelectorAll('.y-axis').forEach(axis => {
        axis.dataset.scale = scaleText;
    });
}

function updateXAxisLabels() {
    const scale = state.xAxisScale;
    const baseMax = 50;
    const scaledMax = Math.round(baseMax / scale);

    const normLabels = document.querySelectorAll('#x-axis-norm .x-label');
    if (normLabels.length >= 4) {
        normLabels[0].innerText = `-${scaledMax}`;
        normLabels[1].innerText = `-${Math.round(scaledMax/2)}`;
        normLabels[2].innerText = `+${Math.round(scaledMax/2)}`;
        normLabels[3].innerText = `+${scaledMax}`;
    }

    const absLabels = ['x-abs-min', 'x-abs-q1', 'x-abs-q3', 'x-abs-max'];
    const absValues = [-scaledMax, -Math.round(scaledMax/2), Math.round(scaledMax/2), scaledMax];
    absLabels.forEach((id, i) => {
        const el = document.getElementById(id);
        if (el) {
            const val = absValues[i];
            el.innerText = val < 0 ? `-$${Math.abs(val)}B` : `+$${val}B`;
        }
    });

    const xScaleText = scale === 1.0 ? '' : scale.toFixed(1) + 'x zoom';
    document.querySelectorAll('.x-axis').forEach(axis => {
        axis.dataset.scale = xScaleText;
    });
}

function updateVolWarning() {
    const isNegative = state.tilt < 0;
    const isPositive = state.tilt > 0;
    const tiltMagnitude = Math.abs(state.tilt);

    if (tiltMagnitude > 0.25) {
        volWarning.classList.add('visible');
        const volAmp = document.getElementById('vol-amp');
        const volProb = document.getElementById('vol-prob');

        if (isNegative) {
            volWarning.classList.add('negative');
            volWarning.classList.remove('positive');
            const amplification = (1 + tiltMagnitude * 8).toFixed(1);
            volAmp.innerText = `${amplification}x`;
            volProb.innerText = tiltMagnitude > 0.35 ? 'High Risk' : 'Elevated';
            document.querySelector('.vol-stat-label:first-of-type').innerText = 'Vol Amp:';
            document.querySelector('.vol-stat-label:last-of-type').innerText = 'Outlook:';
        } else {
            volWarning.classList.add('positive');
            volWarning.classList.remove('negative');
            const dampening = (1 / (1 + tiltMagnitude * 3)).toFixed(2);
            volAmp.innerText = `${dampening}x`;
            volProb.innerText = tiltMagnitude > 0.35 ? 'Very Stable' : 'Stable';
            document.querySelector('.vol-stat-label:first-of-type').innerText = 'Vol Damp:';
            document.querySelector('.vol-stat-label:last-of-type').innerText = 'Stability:';
        }
    } else {
        volWarning.classList.remove('visible', 'negative', 'positive');
    }
}

function updatePersistence() {
    const isNegative = state.tilt < -0.2;
    const isPositive = state.tilt > 0.2;

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

    const positiveColor = "#00e5ff";
    const negativeColor = "#ff3d57";
    const elevatedColor = "#ff9100";

    const tiltMag = Math.abs(state.tilt);
    if (tiltMag > 0.35) {
        statNorm.innerText = isNegative ? 'SHORT γ' : 'LONG γ';
        statNorm.style.color = isNegative ? negativeColor : positiveColor;
    } else if (tiltMag > 0.2) {
        statNorm.innerText = isNegative ? 'BEARISH' : 'BULLISH';
        statNorm.style.color = elevatedColor;
    } else {
        statNorm.innerText = 'NEUTRAL';
        statNorm.style.color = '#8b9bb4';
    }

    if (absTotal > 20) {
        statAbs.innerText = 'REGIME';
        statAbs.style.color = isNegative ? negativeColor : positiveColor;
    } else if (absTotal > 12) {
        statAbs.innerText = 'ELEVATED';
        statAbs.style.color = elevatedColor;
    } else {
        statAbs.innerText = 'NO REGIME';
        statAbs.style.color = '#8b9bb4';
    }
}

function updateInsight() {
    const isNegative = state.tilt < 0;
    const isPositive = state.tilt > 0;
    const tiltMag = Math.abs(state.tilt);
    let msg;

    if (isNegative && tiltMag > 0.3) {
        msg = `<strong>SHORT GAMMA:</strong> Dealers short options → hedge by selling into dips, buying into rallies → amplifies moves. Expect <span style="color:var(--accent-red)">higher volatility</span>.`;
    } else if (isNegative && tiltMag > 0.15) {
        msg = `<strong>Mild Short Gamma:</strong> Dealer hedging slightly amplifies price moves. Watch for increased intraday swings.`;
    } else if (isPositive && tiltMag > 0.3) {
        msg = `<strong>LONG GAMMA:</strong> Dealers long options → hedge by buying dips, selling rallies → dampens moves. Expect <span style="color:var(--accent-cyan)">lower volatility</span>.`;
    } else if (isPositive && tiltMag > 0.15) {
        msg = `<strong>Mild Long Gamma:</strong> Dealer hedging slightly dampens price moves. Market tends toward stability.`;
    } else {
        msg = `<strong>Neutral:</strong> Dealer positioning balanced. Market moves driven by fundamentals rather than options hedging flows.`;
    }
    insightBox.innerHTML = msg;
}

function updateRealDataMetrics(point) {
    const metricsPanel = document.getElementById('real-data-metrics');
    if (!metricsPanel) return;

    if (DataLoader.dataMode !== 'real' || !point._raw) {
        metricsPanel.style.display = 'none';
        return;
    }

    metricsPanel.style.display = 'block';
    const raw = point._raw;

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

    const contractsEl = document.getElementById('rdm-contracts');
    if (raw.contracts) {
        contractsEl.textContent = raw.contracts.toLocaleString();
    } else {
        contractsEl.textContent = '-';
    }

    const gammaEl = document.getElementById('rdm-gamma-balance');
    if (raw.call_gex !== null && raw.put_gex !== null) {
        const callGex = raw.call_gex || 0;
        const putGex = raw.put_gex || 0;
        const ratio = callGex !== 0 || putGex !== 0
            ? (callGex / (Math.abs(callGex) + Math.abs(putGex)) * 100).toFixed(0)
            : 50;
        const isPos = callGex > Math.abs(putGex);
        gammaEl.textContent = ratio + '% / ' + (100 - ratio) + '%';
        gammaEl.className = 'rdm-value ' + (isPos ? 'gamma-positive' : 'gamma-negative');
    } else {
        gammaEl.textContent = '-';
        gammaEl.className = 'rdm-value';
    }
}

function updateHeaderSymbol(symbol) {
    const priceLabel = document.querySelector('.metric-card .metric-label');
    if (priceLabel && priceLabel.textContent.includes('Price')) {
        priceLabel.textContent = `${symbol} Price`;
    }

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

    const priceSlider = document.getElementById('inp-price');
    if (priceSlider) {
        priceSlider.min = Math.floor(min * 0.8);
        priceSlider.max = Math.ceil(max * 1.1);
    }
}

// --- PERSISTENCE METER SETUP ---
function createPersistenceMeter() {
    for (let i = 0; i < 8; i++) {
        const bar = document.createElement('div');
        bar.className = 'persist-bar';
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

// Export
Object.assign(window.GEX, {
    elPrice, elOi, elTilt,
    setPrice, setOi, setTilt, syncControlsToState,
    updateEventDisplay, updateYAxisLabels, updateXAxisLabels,
    updateVolWarning, updatePersistence, updateStatus, updateInsight,
    updateRealDataMetrics, updateHeaderSymbol, updatePriceRange,
    createPersistenceMeter, createYAxisLabels
});
