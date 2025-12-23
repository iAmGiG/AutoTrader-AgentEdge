// GEX Visualizer - State Management
// Configuration, state object, and strike range calculations

// --- STRIKE RANGE CONFIGURATION ---
let strikeStart = 280;
let strikeEnd = 650;
let strikeStep = 10;
let strikes = [];
for (let s = strikeStart; s <= strikeEnd; s += strikeStep) strikes.push(s);

// --- APPLICATION STATE ---
const state = {
    price: 400,
    oi: 5,
    tilt: -0.15,
    simulating: false,
    simFrame: 0,
    persistenceDay: 1,
    currentIndex: -1,
    playbackSpeed: 2,
    isDragging: false,
    isResizing: false,
    yAxisScale: 1.0,
    xAxisScale: 1.0,
    invertScroll: false,
    yAxisDragging: false,
    xAxisDragging: false,
    priceDragging: false,
    dragStartY: 0,
    dragStartX: 0,
    dragStartScale: 1.0,
    dragStartPrice: 0
};

// --- SPY DEMO TIMELINE ---
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

// Store original demo timeline for switching back
const demoTimeline = [...timeline];

// --- STRIKE RANGE FUNCTIONS ---
function updateStrikeRange(minPrice, maxPrice) {
    const padding = (maxPrice - minPrice) * 0.2;
    const paddedMin = Math.max(0, minPrice - padding);
    const paddedMax = maxPrice + padding;

    let roundUnit;
    if (paddedMax < 50) roundUnit = 1;
    else if (paddedMax < 200) roundUnit = 5;
    else roundUnit = 10;

    strikeStart = Math.floor(paddedMin / roundUnit) * roundUnit;
    strikeEnd = Math.ceil(paddedMax / roundUnit) * roundUnit;

    if (strikeEnd - strikeStart < 10) {
        strikeEnd = strikeStart + Math.max(20, Math.ceil(paddedMax * 0.3));
    }

    const range = strikeEnd - strikeStart;
    if (range > 500) strikeStep = 20;
    else if (range > 200) strikeStep = 10;
    else if (range > 100) strikeStep = 5;
    else if (range > 50) strikeStep = 2;
    else strikeStep = 1;

    strikes.length = 0;
    for (let s = strikeStart; s <= strikeEnd; s += strikeStep) {
        strikes.push(s);
    }

    if (strikes.length < 10) {
        strikeStep = Math.max(1, Math.floor(range / 20));
        strikes.length = 0;
        for (let s = strikeStart; s <= strikeEnd; s += strikeStep) {
            strikes.push(s);
        }
    }

    console.log(`Strike range: $${strikeStart}-$${strikeEnd}, step: $${strikeStep}, count: ${strikes.length}`);
    updateYAxisBaseLabels();
}

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

// --- UTILITY FUNCTIONS ---
function getYear(dateStr) {
    return parseInt(dateStr.split('-')[0]);
}

function formatDate(dateStr) {
    const [year, month, day] = dateStr.split('-');
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[parseInt(month)-1]} ${parseInt(day)}, ${year}`;
}

// Export for other modules
window.GEX = window.GEX || {};
Object.assign(window.GEX, {
    state,
    timeline,
    demoTimeline,
    strikes,
    get strikeStart() { return strikeStart; },
    get strikeEnd() { return strikeEnd; },
    get strikeStep() { return strikeStep; },
    updateStrikeRange,
    updateYAxisBaseLabels,
    getYear,
    formatDate
});
