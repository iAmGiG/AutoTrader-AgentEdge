// GEX Visualizer - Data Loader Module
// Handles loading real GEX data from JSON files

const DataLoader = {
    index: null,
    currentData: null,
    dataMode: 'demo', // 'demo' or 'real'

    // Load the index of available symbols
    async loadIndex() {
        try {
            const response = await fetch('data/index.json');
            if (!response.ok) throw new Error('Index not found');
            this.index = await response.json();
            return this.index;
        } catch (error) {
            console.warn('Could not load data index:', error.message);
            return null;
        }
    },

    // Load data for a specific symbol
    async loadSymbol(symbol) {
        try {
            const response = await fetch(`data/${symbol.toLowerCase()}.json`);
            if (!response.ok) throw new Error(`Data not found for ${symbol}`);
            this.currentData = await response.json();
            return this.currentData;
        } catch (error) {
            console.error('Could not load symbol data:', error.message);
            return null;
        }
    },

    // Transform real data to visualizer timeline format
    transformToTimeline(data) {
        if (!data || !data.timeline) return [];

        return data.timeline.map(point => {
            // Calculate tilt from call/put OI concentration
            // Tilt negative = more puts = dealer short gamma
            // Tilt positive = more calls = dealer long gamma
            const tilt = point.regime === 'NEGATIVE_GAMMA'
                ? -0.15 - (point.put_oi - 0.5) * 0.5
                : 0.1 + (point.call_oi - 0.5) * 0.3;

            // Estimate OI multiplier from contracts count
            const oiMultiplier = Math.min(12, Math.max(3, point.contracts / 1000));

            return {
                date: point.date,
                price: point.price,
                oi: oiMultiplier,
                tilt: Math.max(-0.5, Math.min(0.5, tilt)),
                label: this.generateLabel(point),
                // Store original data for display
                _raw: {
                    gex: point.gex,
                    zero_gamma: point.zero_gamma,
                    regime: point.regime,
                    call_gex: point.call_gex,
                    put_gex: point.put_gex,
                    contracts: point.contracts,
                    quality: point.quality
                }
            };
        });
    },

    // Generate a descriptive label for the data point
    generateLabel(point) {
        const regime = point.regime === 'NEGATIVE_GAMMA' ? 'Short γ' : 'Long γ';
        const date = new Date(point.date);
        const month = date.toLocaleString('default', { month: 'short' });
        return `${month} ${date.getFullYear()} - ${regime}`;
    },

    // Get list of asset classes
    getAssetClasses() {
        if (!this.index) return [];
        return Object.keys(this.index.asset_classes).sort();
    },

    // Get symbols for an asset class
    getSymbolsForClass(assetClass) {
        if (!this.index || !this.index.asset_classes[assetClass]) return [];
        return this.index.asset_classes[assetClass].sort();
    },

    // Get all symbols
    getAllSymbols() {
        if (!this.index) return [];
        return this.index.symbols.map(s => s.symbol).sort();
    },

    // Get symbol info
    getSymbolInfo(symbol) {
        if (!this.index) return null;
        return this.index.symbols.find(s => s.symbol === symbol);
    }
};

// Export for use in main.js
window.DataLoader = DataLoader;
