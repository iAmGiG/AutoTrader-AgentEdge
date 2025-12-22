// GEX Visualizer - Event Handlers
// Keyboard, mouse, scrubber, axis interactions

const { state } = window.GEX;

// --- DOM ELEMENTS ---
const sidebarResize = document.getElementById('sidebar-resize');
const dashboard = document.getElementById('dashboard');
const timelineTrack = document.getElementById('timeline-track');
const timelineHandle = document.getElementById('timeline-handle');

// --- SCRUBBER SETUP ---
function setupScrubber() {
    const { timeline, goToIndex, toggleSimulation, setPrice,
            updateYAxisLabels, updateXAxisLabels, render,
            stepForward, stepBack, stepToNext, stepBackward,
            jumpToStart, jumpToEnd, resetView, toggleFullscreen } = window.GEX;

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

    // Mouse wheel on chart panels to adjust spot price
    const chartPanels = document.querySelectorAll('.chart-panel');
    chartPanels.forEach(panel => {
        panel.addEventListener('wheel', (e) => {
            if (e.target.closest('.y-axis') || e.target.closest('.x-axis')) return;

            e.preventDefault();
            if (state.simulating) return;

            const step = e.shiftKey ? 10 : 2;
            let delta = e.deltaY > 0 ? -step : step;

            if (state.invertScroll) delta = -delta;

            setPrice(state.price + delta);
        }, { passive: false });

        // Click-drag on chart panel to adjust spot price
        const startPriceDrag = (e) => {
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

    // Y-axis scroll-to-scale
    const yAxes = document.querySelectorAll('.y-axis');
    yAxes.forEach(yAxis => {
        yAxis.addEventListener('wheel', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const scaleDelta = e.deltaY > 0 ? 0.1 : -0.1;
            state.yAxisScale = Math.max(0.2, Math.min(3.0, state.yAxisScale + scaleDelta));

            updateYAxisLabels();
            render();
        }, { passive: false });

        yAxis.addEventListener('dblclick', () => {
            state.yAxisScale = 1.0;
            updateYAxisLabels();
            render();
        });

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

    // X-axis scroll-to-scale
    const xAxes = document.querySelectorAll('.x-axis');
    xAxes.forEach(xAxis => {
        xAxis.addEventListener('wheel', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const scaleDelta = e.deltaY > 0 ? 0.1 : -0.1;
            state.xAxisScale = Math.max(0.3, Math.min(3.0, state.xAxisScale + scaleDelta));

            updateXAxisLabels();
            render();
        }, { passive: false });

        xAxis.addEventListener('dblclick', () => {
            state.xAxisScale = 1.0;
            updateXAxisLabels();
            render();
        });

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
            const scaleDelta = deltaY * 0.005;
            state.yAxisScale = Math.max(0.2, Math.min(3.0, state.dragStartScale + scaleDelta));
            updateYAxisLabels();
            render();
        }
        if (state.xAxisDragging) {
            const clientX = e.clientX || (e.touches && e.touches[0].clientX);
            const deltaX = clientX - state.dragStartX;
            const scaleDelta = deltaX * 0.005;
            state.xAxisScale = Math.max(0.3, Math.min(3.0, state.dragStartScale + scaleDelta));
            updateXAxisLabels();
            render();
        }
        if (state.priceDragging) {
            const clientY = e.clientY || (e.touches && e.touches[0].clientY);
            const deltaY = state.dragStartY - clientY;
            let priceDelta = deltaY * 0.5;
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

    // Position sidebar popup on hover
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

// --- SLIDER INPUT HANDLERS ---
function setupSliderHandlers() {
    const { elPrice, elOi, elTilt, setPrice, setOi, setTilt } = window.GEX;

    elPrice.addEventListener('input', (e) => setPrice(parseFloat(e.target.value)));
    elOi.addEventListener('input', (e) => setOi(parseFloat(e.target.value)));
    elTilt.addEventListener('input', (e) => setTilt(parseFloat(e.target.value)));
}

// Export
Object.assign(window.GEX, {
    setupScrubber, setupSliderHandlers
});
