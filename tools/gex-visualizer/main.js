// GEX Visualizer - Main Orchestration
// Initialization and data mode management

// --- INITIALIZATION ---
function init() {
    const { createYAxisLabels, createPersistenceMeter } = window.GEX;
    const { createSvg, vizNorm, vizAbs } = window.GEX;
    const { createTimelineMarkers, createSparkline, setupSparklineInteraction } = window.GEX;
    const { setupScrubber, setupSliderHandlers } = window.GEX;
    const { render } = window.GEX;

    createYAxisLabels('y-axis-norm');
    createYAxisLabels('y-axis-abs');
    createSvg('svg-norm', vizNorm);
    createSvg('svg-abs', vizAbs);
    createPersistenceMeter();
    createTimelineMarkers();
    createSparkline();
    setupSparklineInteraction();
    setupScrubber();
    setupSliderHandlers();
    render();
}

// --- DATA MODE FUNCTIONS ---
async function setDataMode(mode) {
    const { timeline, demoTimeline, updateStrikeRange, rebuildCharts,
            updateHeaderSymbol, updatePriceRange, resetToDefaults,
            createSparkline, createTimelineMarkers } = window.GEX;

    document.getElementById('mode-demo').classList.toggle('active', mode === 'demo');
    document.getElementById('mode-real').classList.toggle('active', mode === 'real');

    const selectors = document.getElementById('symbol-selectors');
    selectors.style.display = mode === 'real' ? 'block' : 'none';

    if (mode === 'demo') {
        DataLoader.dataMode = 'demo';
        timeline.length = 0;
        timeline.push(...demoTimeline);

        updateStrikeRange(222, 605);
        rebuildCharts();

        updateHeaderSymbol('SPY');
        updatePriceRange(222, 605);
        resetToDefaults();
        createSparkline();

        const markersContainer = document.getElementById('timeline-markers');
        markersContainer.innerHTML = '';
        createTimelineMarkers();
    } else {
        DataLoader.dataMode = 'real';

        if (!DataLoader.index) {
            await DataLoader.loadIndex();
            if (!DataLoader.index) {
                alert('Could not load data. Make sure to run export_data.py first.');
                setDataMode('demo');
                return;
            }
        }

        populateAssetClasses();

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

    document.getElementById('data-info').innerHTML = '';
}

async function onSymbolChange() {
    const { state, timeline, updateStrikeRange, rebuildCharts,
            updateHeaderSymbol, updatePriceRange, toggleSimulation,
            createSparkline, createTimelineMarkers, goToIndex } = window.GEX;

    const symbol = document.getElementById('symbol-select').value;
    if (!symbol) return;

    document.getElementById('data-info').innerHTML = 'Loading...';

    const data = await DataLoader.loadSymbol(symbol);
    if (!data) {
        document.getElementById('data-info').innerHTML = '<span style="color:var(--accent-red)">Failed to load data</span>';
        return;
    }

    const newTimeline = DataLoader.transformToTimeline(data);

    timeline.length = 0;
    timeline.push(...newTimeline);

    const info = DataLoader.getSymbolInfo(symbol);
    document.getElementById('data-info').innerHTML =
        `<strong>${data.count}</strong> days (${info.date_range.start} to ${info.date_range.end})`;

    updateHeaderSymbol(symbol);

    const prices = newTimeline.map(p => p.price).filter(p => p);
    if (prices.length > 0) {
        const minPrice = Math.min(...prices);
        const maxPrice = Math.max(...prices);
        updatePriceRange(minPrice, maxPrice);
        updateStrikeRange(minPrice, maxPrice);
        rebuildCharts();
    }

    if (state.simulating) toggleSimulation();
    state.currentIndex = -1;

    const markersContainer = document.getElementById('timeline-markers');
    markersContainer.innerHTML = '';
    createTimelineMarkers();

    createSparkline();

    if (timeline.length > 0) {
        goToIndex(0);
    }
}

// --- APP INITIALIZATION ---
async function initApp() {
    init();

    DataLoader.loadIndex().then(() => {
        if (DataLoader.index) {
            console.log(`GEX Data: ${DataLoader.index.symbols.length} symbols available`);
        }
    });
}

initApp();
