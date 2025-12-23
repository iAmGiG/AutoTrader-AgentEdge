// GEX Visualizer - Chart Rendering
// SVG creation, bar rendering, price lines

const { state, strikes, strikeStart, strikeEnd, strikeStep } = window.GEX;

// --- DOM ELEMENTS ---
const vizNorm = document.getElementById('viz-norm');
const vizAbs = document.getElementById('viz-abs');

// --- SVG CREATION ---
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
    const currentStrikes = window.GEX.strikes;
    currentStrikes.forEach((_, i) => {
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("class", "bar");
        rect.setAttribute("x", "50%");
        rect.setAttribute("y", `${(i / currentStrikes.length) * 100}%`);
        rect.setAttribute("height", `${85 / currentStrikes.length}%`);
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
    zeroLabel.textContent = "0γ";
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

// --- BAR UPDATES ---
function updateBar(svgId, index, val, scaledY) {
    const bar = document.getElementById(`${svgId}-bar-${index}`);
    if (!bar) return;

    const currentStrikes = window.GEX.strikes;

    // Apply X-axis scale to width (scale > 1 = zoom in = bars appear wider)
    const scaledVal = val * state.xAxisScale;
    const width = Math.min(Math.abs(scaledVal), 48);
    bar.setAttribute("width", `${width}%`);

    // Update Y position with scaling
    const barHeight = (85 / currentStrikes.length) * state.yAxisScale;
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

// --- PRICE LINE UPDATES ---
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

// --- REBUILD CHARTS ---
function rebuildCharts() {
    vizNorm.innerHTML = '';
    vizAbs.innerHTML = '';

    createSvg('svg-norm', vizNorm);
    createSvg('svg-abs', vizAbs);
}

// --- MAIN RENDER ---
function render() {
    const { strikeStart, strikeEnd, strikeStep, strikes: currentStrikes } = window.GEX;
    const { updateYAxisLabels, updateXAxisLabels, updateVolWarning, updatePersistence,
            updateStatus, updateInsight } = window.GEX;

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
    const centerYPercent = 100 - (centerIndex / currentStrikes.length) * 100;

    // Calculate GEX for each strike
    currentStrikes.forEach((_, i) => {
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
        const baseY = 100 - (i / currentStrikes.length) * 100;
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
    const zeroYBase = 100 - (zeroIndex / currentStrikes.length) * 100;
    const zeroY = Math.max(0, Math.min(100, centerYPercent + (zeroYBase - centerYPercent) * state.yAxisScale));
    updatePriceLine('svg-norm', priceY, zeroY);
    updatePriceLine('svg-abs', priceY, zeroY);

    // Update data overlays
    document.getElementById('val-norm-max').innerText = maxNormVal.toFixed(2);
    document.getElementById('val-scale-factor').innerText = s2Scale.toFixed(1) + "x";
    document.getElementById('val-abs-total').innerText = "$" + totalAbsGex.toFixed(1) + "B";

    // Call UI update functions
    if (updateVolWarning) updateVolWarning();
    if (updatePersistence) updatePersistence();
    if (updateStatus) updateStatus(totalAbsGex, maxNormVal);
    if (updateYAxisLabels) updateYAxisLabels();
    if (updateXAxisLabels) updateXAxisLabels();

    // Update sparkline if available
    if (window.GEX.updateSparkline) window.GEX.updateSparkline();
}

// Export
Object.assign(window.GEX, {
    vizNorm, vizAbs,
    createSvg, updateBar, updatePriceLine, rebuildCharts, render
});
