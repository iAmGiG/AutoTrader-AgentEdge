// GEX Visualizer - Simulation & Playback
// Timeline navigation, playback controls, sparkline

const { state, timeline, demoTimeline, getYear, formatDate } = window.GEX;

// --- DOM ELEMENTS ---
const timelineTrack = document.getElementById('timeline-track');
const timelineProgress = document.getElementById('timeline-progress');
const timelineHandle = document.getElementById('timeline-handle');
const timelineMarkers = document.getElementById('timeline-markers');
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
const yearBadge = document.getElementById('year-badge');
const eventDate = document.getElementById('event-date');
const eventLabel = document.getElementById('event-label');
const eventIndex = document.getElementById('event-index');

// --- SIMULATION STATE ---
let simInterval = null;

// --- TIMELINE MARKERS ---
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

        sparklineHoverLine.setAttribute('x1', x);
        sparklineHoverLine.setAttribute('x2', x);
        sparklineHoverLine.style.opacity = '0.5';
        sparklineHoverDot.setAttribute('cx', x);
        sparklineHoverDot.setAttribute('cy', y);
        sparklineHoverDot.style.opacity = '1';

        tooltipDate.innerText = formatDate(point.date);
        tooltipPrice.innerText = `$${point.price}`;
        tooltipLabel.innerText = point.label;

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

// --- NAVIGATION ---
function goToIndex(idx) {
    if (idx < 0 || idx >= timeline.length) return;

    state.currentIndex = idx;
    const point = timeline[idx];

    state.price = point.price;
    state.oi = point.oi;
    state.tilt = point.tilt;

    window.GEX.syncControlsToState();
    updateTimeline();
    window.GEX.updateEventDisplay();
    if (window.GEX.updateRealDataMetrics) window.GEX.updateRealDataMetrics(point);
    window.GEX.render();
}

function jumpToYear(year) {
    const idx = timeline.findIndex(t => getYear(t.date) === year);
    if (idx >= 0) goToIndex(idx);
}

function updateTimeline() {
    const pct = state.currentIndex >= 0 ? (state.currentIndex / (timeline.length - 1)) * 100 : 0;
    timelineProgress.style.width = pct + '%';
    timelineHandle.style.left = pct + '%';

    if (state.currentIndex >= 0) {
        const point = timeline[state.currentIndex];
        yearBadge.innerText = getYear(point.date);
        yearBadge.classList.remove('inactive');
    } else {
        yearBadge.innerText = '----';
        yearBadge.classList.add('inactive');
    }

    const markers = timelineMarkers.querySelectorAll('.timeline-marker');
    const currentYear = state.currentIndex >= 0 ? getYear(timeline[state.currentIndex].date) : null;
    markers.forEach(m => {
        m.classList.toggle('active', parseInt(m.innerText) === currentYear);
    });
}

// --- STEP CONTROLS ---
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

// --- SPEED CONTROL ---
function setSpeed(speed) {
    state.playbackSpeed = speed;
    document.querySelectorAll('.speed-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById('speed-' + speed).classList.add('active');
}

// --- SIMULATION PLAYBACK ---
function toggleSimulation() {
    if (state.simulating) {
        state.simulating = false;
        clearInterval(simInterval);
        btnPlay.classList.remove('playing');
        btnPlay.innerHTML = '&#9654;';
        return;
    }

    state.simulating = true;
    btnPlay.classList.add('playing');
    btnPlay.innerHTML = '&#9724;';

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
                state.currentIndex = timeline.length - 1;
                state.simulating = false;
                clearInterval(simInterval);
                btnPlay.classList.remove('playing');
                btnPlay.innerHTML = '&#9654;';
                goToIndex(state.currentIndex);
                return;
            }
        }

        const curr = timeline[state.currentIndex];
        const next = timeline[Math.min(state.currentIndex + 1, timeline.length - 1)];
        const progress = subFrame / framesPerPoint;

        state.price = curr.price + (next.price - curr.price) * progress;
        state.oi = curr.oi + (next.oi - curr.oi) * progress;
        state.tilt = curr.tilt + (next.tilt - curr.tilt) * progress;

        if (Math.abs(state.tilt - lastTilt) > 0.08) {
            state.persistenceDay = 1;
            lastTilt = state.tilt;
        } else if (subFrame === 0) {
            state.persistenceDay = Math.min(8, state.persistenceDay + 1);
        }

        window.GEX.syncControlsToState();
        updateTimeline();
        window.GEX.updateEventDisplay();
        window.GEX.render();
    }, 80 / state.playbackSpeed);
}

// --- RESET ---
function resetToDefaults() {
    if (state.simulating) toggleSimulation();

    state.price = 400;
    state.oi = 5;
    state.tilt = -0.15;
    state.currentIndex = -1;
    state.persistenceDay = 1;
    state.yAxisScale = 1.0;
    state.xAxisScale = 1.0;

    window.GEX.syncControlsToState();
    updateTimeline();
    window.GEX.updateEventDisplay();
    window.GEX.render();
}

function resetView() {
    state.yAxisScale = 1.0;
    state.xAxisScale = 1.0;

    window.GEX.updateYAxisLabels();
    window.GEX.updateXAxisLabels();
    window.GEX.render();

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
        if (dashboard.requestFullscreen) {
            dashboard.requestFullscreen();
        } else if (dashboard.webkitRequestFullscreen) {
            dashboard.webkitRequestFullscreen();
        } else if (dashboard.msRequestFullscreen) {
            dashboard.msRequestFullscreen();
        }
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }
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

// Export
Object.assign(window.GEX, {
    createTimelineMarkers, createSparkline, updateSparkline, setupSparklineInteraction,
    goToIndex, jumpToYear, updateTimeline,
    stepForward, stepBack, stepToNext, stepBackward, jumpToStart, jumpToEnd,
    setSpeed, toggleSimulation, resetToDefaults, resetView, toggleFullscreen, toggleInvertScroll
});
