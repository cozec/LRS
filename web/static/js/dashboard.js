document.addEventListener('DOMContentLoaded', function () {
    fetchData();
});

async function fetchData() {
    try {
        // Check Plotly
        if (typeof Plotly === 'undefined') {
            throw new Error("Plotly.js library failed to load (CDN issue). Check internet connection.");
        }

        const response = await fetch('/api/data');
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`API Error ${response.status}: ${errText.substring(0, 100)}`);
        }

        const data = await response.json();
        if (data.error) {
            throw new Error("Server Error: " + data.error);
        }

        renderChart(data.history, data.events);

        const overlay = document.querySelector('.loading-overlay');
        if (overlay) overlay.classList.add('hidden');

    } catch (error) {
        console.error('Error details:', error);
        const overlay = document.querySelector('.loading-overlay');
        if (overlay) {
            overlay.classList.remove('hidden');
            overlay.innerHTML = `<span style="color: #ff3333; font-family: monospace;">${error.message}</span>`;
        }
    }
}

function renderChart(history, events) {
    const dates = history.map(d => d.Date);
    const open = history.map(d => d.Open);
    const high = history.map(d => d.High);
    const low = history.map(d => d.Low);
    const close = history.map(d => d.Close);
    const sma = history.map(d => d.SMA_200);
    const rsi = history.map(d => d.RSI);
    // Equity data no longer needed for display

    // 3. TQQQ
    const tqqq = history.map(d => d.TQQQ_Close);
    const traceTQQQ = {
        x: dates, y: tqqq, type: 'scatter', mode: 'lines',
        name: 'TQQQ', line: { color: '#3399ff', width: 1 }, /* Thinner, refreshed blue */
        xaxis: 'x3', yaxis: 'y3'
    };

    // --- Layout Configuration ---
    const layout = {
        grid: { rows: 3, columns: 1, pattern: 'independent', roworder: 'top to bottom' },
        autosize: true,
        height: document.getElementById('chart-container').clientHeight,
        margin: { t: 5, b: 40, l: 50, r: 80 },
        paper_bgcolor: '#1a1a1a',
        plot_bgcolor: '#1a1a1a',
        font: { color: '#e0e0e0' },
        showlegend: false,

        // Calculate all missing dates (gaps) to hide them
        // This handles weekends AND holidays (like Dec 25) automatically
        // by finding any calendar day not present in the dataset.
        xaxis: {
            rangeslider: { visible: false },
            showgrid: true,
            gridcolor: '#333',
            rangebreaks: [
                { values: getMissingDates(dates) }
            ],
            rangeselector: {
                buttons: [
                    { count: 3, label: '3M', step: 'month', stepmode: 'backward' },
                    { count: 6, label: '6M', step: 'month', stepmode: 'backward' },
                    { count: 1, label: '1Y', step: 'year', stepmode: 'backward' },
                    { count: 5, label: '5Y', step: 'year', stepmode: 'backward' },
                    { step: 'all', label: 'All' }
                ],
                font: { color: '#e0e0e0', size: 11 },
                bgcolor: '#333',
                activecolor: '#555',
                y: 0.40,
                yanchor: 'bottom'
            }
        },
        yaxis: { domain: [0.40, 1], showgrid: true, gridcolor: '#333', title: 'S&P 500' },

        // Axis 2 (RSI) - Smaller
        xaxis2: { showgrid: true, gridcolor: '#333', matches: 'x', showticklabels: false },
        yaxis2: { domain: [0.21, 0.39], showgrid: true, gridcolor: '#333', title: 'RSI', range: [0, 100] },

        // Axis 3 (TQQQ) - Smaller
        // Axis 3 (TQQQ) - Smaller
        xaxis3: {
            showgrid: true, gridcolor: '#333', matches: 'x', title: 'Date'
        },
        yaxis3: { domain: [0, 0.20], type: 'log', showgrid: true, gridcolor: '#333', title: 'TQQQ ($)' },

        // Annotations (Flags)
        annotations: events.flatMap(e => {
            const flags = [createFlag(e)]; // Always Price Flag

            // Add RSI Flag for Sniper Signals OR Exit Signals
            // Note: Trend signals don't necessarily have a specific RSI trigger point visualized here,
            // but we can add them if desired. User specifically asked for "Exit Signal".
            if (e.type.includes('SNIPER') || e.type.includes('EXIT')) {
                flags.push(createRSIFlag(e));
            }
            return flags;
        })
    };

    // ... rest of layout ...

    // --- Traces ---

    // 1. Price (Candlestick)
    const tracePrice = {
        x: dates,
        open: open, high: high, low: low, close: close,
        type: 'candlestick',
        name: 'SPX',
        increasing: { line: { color: '#26a69a' }, fillcolor: '#26a69a' }, /* Teal Green */
        decreasing: { line: { color: '#ef5350' }, fillcolor: '#ef5350' }, /* Red */
        xaxis: 'x', yaxis: 'y'
    };

    const traceMA10 = {
        x: dates, y: history.map(d => d.MA_10), type: 'scatter', mode: 'lines',
        name: 'MA 10', line: { color: '#007bff', width: 1.5 }, /* Blue */
        xaxis: 'x', yaxis: 'y'
    };

    const traceSMA = {
        x: dates, y: sma, type: 'scatter', mode: 'lines',
        name: 'SMA 200', line: { color: '#4fc3f7', width: 1.5 }, /* Light Blue/Cyan */
        xaxis: 'x', yaxis: 'y'
    };

    // Buffer Magic (Hysteresis Zone)
    const traceSMALower = {
        x: dates, y: history.map(d => d.SMA_200_Lower), type: 'scatter', mode: 'lines',
        name: '-2% Buffer', line: { color: '#ffcc00', width: 0, dash: 'dot' },
        showlegend: false, hoverinfo: 'none', xaxis: 'x', yaxis: 'y'
    };

    const traceSMAUpper = {
        x: dates, y: history.map(d => d.SMA_200_Upper), type: 'scatter', mode: 'lines',
        name: 'Buffer Zone', line: { color: '#ffcc00', width: 0, dash: 'dot' },
        fill: 'tonexty', fillcolor: 'rgba(255, 204, 0, 0.15)', // Brighter Gold Fill
        hoverinfo: 'none', xaxis: 'x', yaxis: 'y'
    };

    // Draw the actual lines on top if needed, or just keep the fill? 
    // Let's draw dashed lines for the boundaries + fill.
    // Redefining to ensure lines show.

    const traceSMALowerLine = {
        x: dates, y: history.map(d => d.SMA_200_Lower), type: 'scatter', mode: 'lines',
        name: '-2% Buffer', line: { color: '#ffcc00', width: 0.8, dash: 'dot' }, opacity: 0.7,
        hoverinfo: 'none', xaxis: 'x', yaxis: 'y'
    };
    const traceSMAUpperLine = {
        x: dates, y: history.map(d => d.SMA_200_Upper), type: 'scatter', mode: 'lines',
        name: '+2% Buffer', line: { color: '#ffcc00', width: 0.8, dash: 'dot' }, opacity: 0.7,
        hoverinfo: 'none', xaxis: 'x', yaxis: 'y'
    };

    // 2. RSI
    const traceRSI = {
        x: dates, y: rsi, type: 'scatter', mode: 'lines',
        name: 'RSI(14)', line: { color: '#cc66ff', width: 1 }, /* Lighter purple */
        xaxis: 'x2', yaxis: 'y2'
    };

    // RSI Zones (Thresholds: 30 and 50)
    const rsiLow = {
        x: dates, y: Array(dates.length).fill(30), type: 'scatter', mode: 'lines',
        line: { color: '#00ff88', width: 0.5, dash: 'dot' }, hoverinfo: 'none',
        xaxis: 'x2', yaxis: 'y2'
    };
    const rsiHigh = {
        x: dates, y: Array(dates.length).fill(50), type: 'scatter', mode: 'lines',
        line: { color: '#888', width: 0.5, dash: 'dot' }, hoverinfo: 'none',
        xaxis: 'x2', yaxis: 'y2'
    };

    const data = [
        tracePrice, traceMA10, traceSMA,
        traceSMALower, traceSMAUpper, // Fill
        traceSMALowerLine, traceSMAUpperLine, // Lines on top
        traceRSI, rsiLow, rsiHigh,
        traceTQQQ
    ];

    // Auto-Calculate Initial Y-Axis for 1 Year (Price)
    // Also TQQQ if we want, but Price is main

    // --- Default Range: 6 Months ---
    const lastDate = new Date(dates[dates.length - 1]);
    const sixMonthsAgo = new Date(lastDate);
    sixMonthsAgo.setMonth(lastDate.getMonth() - 6);
    const rangeStart = sixMonthsAgo.toISOString().split('T')[0];

    // Add padding on the right side (5 days) for better visibility of today's values
    const rangeEndDate = new Date(lastDate);
    rangeEndDate.setDate(rangeEndDate.getDate() + 5);
    const rangeEnd = rangeEndDate.toISOString().split('T')[0];

    layout.xaxis.range = [rangeStart, rangeEnd];

    const startIdx = dates.findIndex(d => d >= rangeStart);
    if (startIdx !== -1) {
        const visibleClose = close.slice(startIdx);
        const visibleSMA = sma.slice(startIdx).filter(v => v != null);
        const allPriceData = [...visibleClose, ...visibleSMA];
        const minPrice = Math.min(...allPriceData);
        const maxPrice = Math.max(...allPriceData);
        const padding = (maxPrice - minPrice) * 0.05;
        layout.yaxis.range = [minPrice - padding, maxPrice + padding];

        // TQQQ (Log) - Set range for log axis
        const visibleTQQQ = tqqq.slice(startIdx);
        const minTQQQ = Math.min(...visibleTQQQ);
        const maxTQQQ = Math.max(...visibleTQQQ);
        // For log axis, range is log10(value)
        layout.yaxis3.range = [Math.log10(minTQQQ * 0.9), Math.log10(maxTQQQ * 1.1)];

        // RSI (Linear) - Auto Scale
        const visibleRSI = rsi.slice(startIdx);
        const minRSI = Math.min(...visibleRSI);
        const maxRSI = Math.max(...visibleRSI);
        layout.yaxis2.range = [Math.max(0, minRSI - 5), Math.min(100, maxRSI + 5)];
    }

    // Get latest values for right-side annotations
    const latestClose = close[close.length - 1];
    const latestMA10 = history[history.length - 1].MA_10;
    const latestMA200 = sma[sma.length - 1];

    // Add right-side price annotations (no horizontal lines)
    layout.annotations = layout.annotations || [];
    layout.annotations.push(
        // Current Price label (green background, white text)
        {
            x: 1.01, y: latestClose,
            xref: 'paper', yref: 'y',
            text: `<b>${latestClose.toFixed(2)}</b>`,
            showarrow: false,
            font: { color: '#fff', size: 12 },
            bgcolor: '#26a69a',
            borderpad: 4,
            xanchor: 'left'
        },
        // MA10 label (blue background, white text)
        {
            x: 1.01, y: latestMA10,
            xref: 'paper', yref: 'y',
            text: `<b>${latestMA10.toFixed(2)}</b>`,
            showarrow: false,
            font: { color: '#fff', size: 11 },
            bgcolor: '#007bff',
            borderpad: 3,
            xanchor: 'left'
        },
        // MA200 label (blue background, black text)
        {
            x: 1.01, y: latestMA200,
            xref: 'paper', yref: 'y',
            text: `<b>${latestMA200.toFixed(2)}</b>`,
            showarrow: false,
            font: { color: '#000', size: 11 },
            bgcolor: '#4fc3f7',
            borderpad: 3,
            xanchor: 'left'
        }
    );

    Plotly.newPlot('chart-container', data, layout, { responsive: true, scrollZoom: true }).then(gd => {
        gd.on('plotly_relayout', event => {
            // Link range updates? They are linked by matches: 'x'
            // Auto-scale Logic
            if (event['xaxis.range[0]'] || event['xaxis.range']) {
                const xStart = event['xaxis.range[0]'] || event['xaxis.range'][0];
                const xEnd = event['xaxis.range[1]'] || event['xaxis.range'][1];

                const startIdx = dates.findIndex(d => d >= xStart);
                let endIdx = dates.findIndex(d => d >= xEnd);
                if (endIdx === -1) endIdx = dates.length - 1;

                if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
                    // Price (include MA200 for proper scaling)
                    const visibleClose = close.slice(startIdx, endIdx);
                    const visibleSMA = sma.slice(startIdx, endIdx).filter(v => v != null);
                    const allPriceData = [...visibleClose, ...visibleSMA];
                    const minPrice = Math.min(...allPriceData);
                    const maxPrice = Math.max(...allPriceData);
                    const padding = (maxPrice - minPrice) * 0.05;

                    // TQQQ
                    const visibleTQQQ = tqqq.slice(startIdx, endIdx);
                    const minTQQQ = Math.min(...visibleTQQQ);
                    const maxTQQQ = Math.max(...visibleTQQQ);

                    // RSI
                    const visibleRSI = rsi.slice(startIdx, endIdx);
                    const minRSI = Math.min(...visibleRSI);
                    const maxRSI = Math.max(...visibleRSI);

                    Plotly.relayout(gd, {
                        'yaxis.range': [minPrice - padding, maxPrice + padding],
                        'yaxis3.range': [Math.log10(minTQQQ * 0.9), Math.log10(maxTQQQ * 1.1)],
                        'yaxis2.range': [Math.max(0, minRSI - 5), Math.min(100, maxRSI + 5)]
                    });
                }
            }
        });
    });
}

function createFlag(event) {
    let color = '#888';
    let text = event.type;
    let ay = -40;
    let ax = 25;

    if (event.type.includes('EXIT')) {
        color = '#ff5252';
        ay = -60;
        ax = 30;
    } else if (event.type.includes('TREND')) {
        color = '#00ff00';
        ay = 60;
        ax = -30;
    } else if (event.type.includes('SNIPER')) {
        color = '#00ff88';
        ay = 50;
        ax = -25;
    }

    return {
        x: event.date,
        y: event.price,
        xref: 'x',
        yref: 'y',
        text: `<b>${text}</b>`,
        showarrow: true,
        arrowhead: 2,
        arrowsize: 1.2,
        standoff: 8,
        ax: ax,
        ay: ay,
        arrowcolor: color,
        font: { color: event.type.includes('EXIT') ? '#fff' : color, size: 10 },
        bgcolor: event.type.includes('EXIT') ? '#ff5252' : '#1a1a1a',
        bordercolor: color,
        borderwidth: 1,
        borderpad: 3,
        opacity: 0.9
    };
}

function createRSIFlag(event) {
    let color = '#888';
    let text = 'RSI';
    let ay = -30; // Default Above
    let ax = 15;  // Default horizontal offset

    if (event.type.includes('EXIT')) {
        color = '#ff5252';
        text = event.type;
        ay = -60; // Further Above
        ax = 25;  // Offset right
    } else if (event.type.includes('SNIPER')) {
        color = '#00ff88';
        text = 'SNIPE';
        ay = 60; // Further Below
        ax = -20; // Offset left
    }

    return {
        x: event.date,
        y: event.rsi, // Use RSI value
        xref: 'x', // Shared X axis
        yref: 'y2', // RSI Axis
        text: `<b>${text}</b>`,
        showarrow: true,
        arrowhead: 2,
        ax: ax,
        ay: ay,
        arrowcolor: color,
        font: { color: event.type.includes('EXIT') ? '#fff' : color, size: 9 },
        bgcolor: event.type.includes('EXIT') ? '#ff5252' : '#1a1a1a',
        bordercolor: color,
        borderwidth: 1,
        borderpad: 3,
        opacity: 0.9
    };
}

// Helper to find all calendar dates missing from the dataset
function getMissingDates(availableDates) {
    if (!availableDates || availableDates.length === 0) return [];

    const missing = [];
    // Parse start and end from string to avoid timezone issues (assume YYYY-MM-DD)
    const startParts = availableDates[0].split('-');
    const endParts = availableDates[availableDates.length - 1].split('-');

    // Create UTC dates to strictly follow calendar days
    const current = new Date(Date.UTC(startParts[0], startParts[1] - 1, startParts[2]));
    const last = new Date(Date.UTC(endParts[0], endParts[1] - 1, endParts[2]));

    const dateSet = new Set(availableDates);

    // Iterate day by day
    while (current < last) {
        // Add 1 day
        current.setUTCDate(current.getUTCDate() + 1);
        if (current >= last) break;

        // Format back to YYYY-MM-DD
        const iso = current.toISOString().split('T')[0];

        if (!dateSet.has(iso)) {
            missing.push(iso);
        }
    }
    return missing;
}
