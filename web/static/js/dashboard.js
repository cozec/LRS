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
    } catch (error) {
        console.error('Error details:', error);
        document.querySelector('.loading').innerHTML = `<span style="color: #ff3333; font-family: monospace;">${error.message}</span>`;
    }
}

function renderChart(history, events) {
    const dates = history.map(d => d.Date);
    const close = history.map(d => d.Close);
    const sma = history.map(d => d.SMA_200);
    const rsi = history.map(d => d.RSI);
    // Equity data no longer needed for display

    // 3. TQQQ
    const tqqq = history.map(d => d.TQQQ_Close);
    const traceTQQQ = {
        x: dates, y: tqqq, type: 'scatter', mode: 'lines',
        name: 'TQQQ', line: { color: '#00bcd4', width: 1.2 },
        xaxis: 'x3', yaxis: 'y3'
    };

    // --- Layout Configuration ---
    const layout = {
        grid: { rows: 3, columns: 1, pattern: 'independent', roworder: 'top to bottom' },
        autosize: true,
        height: window.innerHeight - 50,
        paper_bgcolor: '#1a1a1a',
        plot_bgcolor: '#1a1a1a',
        font: { color: '#e0e0e0' },
        showlegend: false,

        // Axis configuration (Price)
        xaxis: { rangeslider: { visible: false }, showgrid: true, gridcolor: '#333' },
        yaxis: { domain: [0.60, 1], showgrid: true, gridcolor: '#333', title: 'S&P 500' },

        // Axis 2 (RSI)
        xaxis2: { showgrid: true, gridcolor: '#333', matches: 'x', showticklabels: false },
        yaxis2: { domain: [0.35, 0.55], showgrid: true, gridcolor: '#333', title: 'RSI', range: [0, 100] },

        // Axis 3 (TQQQ)
        xaxis3: {
            showgrid: true, gridcolor: '#333', matches: 'x', title: 'Date',
            rangeselector: {
                buttons: [
                    { count: 6, label: '6M', step: 'month', stepmode: 'backward' },
                    { count: 1, label: '1Y', step: 'year', stepmode: 'backward' },
                    { count: 5, label: '5Y', step: 'year', stepmode: 'backward' },
                    { step: 'all', label: 'All' }
                ],
                font: { color: '#e0e0e0', size: 11 },
                bgcolor: '#333',
                activecolor: '#555',
                y: 1.2 // Move buttons above bottom chart or keep top? 
                // Let's keep buttons on top chart but range linked? 
                // Actually Plotly buttons usually go on the specific axis. 
                // Let's put buttons on top axis (x1) for visibility.
            }
        },
        yaxis3: { domain: [0, 0.30], type: 'log', showgrid: true, gridcolor: '#333', title: 'TQQQ ($)' },

        // Annotations (Flags)
        annotations: events.flatMap(e => {
            const flags = [createFlag(e)]; // Always Price Flag

            // Add RSI Flag for Sniper Signals
            if (e.type.includes('SNIPER')) {
                flags.push(createRSIFlag(e));
            }
            return flags;
        })
    };

    // ... rest of layout ...

    // Move rangeselector back to x1 for top visibility
    layout.xaxis.rangeselector = {
        buttons: [
            { count: 6, label: '6M', step: 'month', stepmode: 'backward' },
            { count: 1, label: '1Y', step: 'year', stepmode: 'backward' },
            { count: 5, label: '5Y', step: 'year', stepmode: 'backward' },
            { step: 'all', label: 'All' }
        ],
        font: { color: '#e0e0e0', size: 11 },
        bgcolor: '#333',
        activecolor: '#555',
        x: 0, y: 1.05
    };
    delete layout.xaxis3.rangeselector;

    // --- Traces ---

    // 1. Price
    const tracePrice = {
        x: dates, y: close, type: 'scatter', mode: 'lines',
        name: 'SPX', line: { color: '#e0e0e0', width: 1 },
        xaxis: 'x', yaxis: 'y'
    };

    const traceMA10 = {
        x: dates, y: history.map(d => d.MA_10), type: 'scatter', mode: 'lines',
        name: 'MA 10', line: { color: '#2979ff', width: 1 },
        xaxis: 'x', yaxis: 'y'
    };

    const traceSMA = {
        x: dates, y: sma, type: 'scatter', mode: 'lines',
        name: 'SMA 200', line: { color: '#ffa500', width: 1, dash: 'dash' },
        xaxis: 'x', yaxis: 'y'
    };

    // Buffer Magic (Hysteresis Zone)
    const traceSMALower = {
        x: dates, y: history.map(d => d.SMA_200_Lower), type: 'scatter', mode: 'lines',
        name: '-2% Buffer', line: { color: '#ffa500', width: 0, dash: 'dot' },
        showlegend: false, hoverinfo: 'none', xaxis: 'x', yaxis: 'y'
    };

    const traceSMAUpper = {
        x: dates, y: history.map(d => d.SMA_200_Upper), type: 'scatter', mode: 'lines',
        name: 'Buffer Zone', line: { color: '#ffa500', width: 0, dash: 'dot' },
        fill: 'tonexty', fillcolor: 'rgba(255, 165, 0, 0.1)', // Faint Orange Fill
        hoverinfo: 'none', xaxis: 'x', yaxis: 'y'
    };

    // Draw the actual lines on top if needed, or just keep the fill? 
    // Let's draw dashed lines for the boundaries + fill.
    // Redefining to ensure lines show.

    const traceSMALowerLine = {
        x: dates, y: history.map(d => d.SMA_200_Lower), type: 'scatter', mode: 'lines',
        name: '-2% Buffer', line: { color: '#ffa500', width: 0.8, dash: 'dot' }, opacity: 0.6,
        hoverinfo: 'none', xaxis: 'x', yaxis: 'y'
    };
    const traceSMAUpperLine = {
        x: dates, y: history.map(d => d.SMA_200_Upper), type: 'scatter', mode: 'lines',
        name: '+2% Buffer', line: { color: '#ffa500', width: 0.8, dash: 'dot' }, opacity: 0.6,
        hoverinfo: 'none', xaxis: 'x', yaxis: 'y'
    };

    // 2. RSI
    const traceRSI = {
        x: dates, y: rsi, type: 'scatter', mode: 'lines',
        name: 'RSI(14)', line: { color: '#ba68c8', width: 1 },
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

    // --- Default Range: 1 Year ---
    const lastDate = new Date(dates[dates.length - 1]);
    const oneYearAgo = new Date(lastDate);
    oneYearAgo.setFullYear(lastDate.getFullYear() - 1);
    const rangeStart = oneYearAgo.toISOString().split('T')[0];
    const rangeEnd = dates[dates.length - 1];

    layout.xaxis.range = [rangeStart, rangeEnd];

    const startIdx = dates.findIndex(d => d >= rangeStart);
    if (startIdx !== -1) {
        const visibleClose = close.slice(startIdx);
        const minPrice = Math.min(...visibleClose);
        const maxPrice = Math.max(...visibleClose);
        const padding = (maxPrice - minPrice) * 0.05;
        layout.yaxis.range = [minPrice - padding, maxPrice + padding];

        // TQQQ (Log) - Set range for log axis
        const visibleTQQQ = tqqq.slice(startIdx);
        const minTQQQ = Math.min(...visibleTQQQ);
        const maxTQQQ = Math.max(...visibleTQQQ);
        // For log axis, range is log10(value)
        layout.yaxis3.range = [Math.log10(minTQQQ * 0.9), Math.log10(maxTQQQ * 1.1)];
    }

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
                    // Price
                    const visibleClose = close.slice(startIdx, endIdx);
                    const minPrice = Math.min(...visibleClose);
                    const maxPrice = Math.max(...visibleClose);
                    const padding = (maxPrice - minPrice) * 0.05;

                    // TQQQ
                    const visibleTQQQ = tqqq.slice(startIdx, endIdx);
                    const minTQQQ = Math.min(...visibleTQQQ);
                    const maxTQQQ = Math.max(...visibleTQQQ);

                    Plotly.relayout(gd, {
                        'yaxis.range': [minPrice - padding, maxPrice + padding],
                        'yaxis3.range': [Math.log10(minTQQQ * 0.9), Math.log10(maxTQQQ * 1.1)]
                    });
                }
            }
        });
    });

    // Remove loading spinner
    document.querySelector('.loading').remove();
}

function createFlag(event) {
    let color = '#888';
    let text = event.type;
    let ay = -40; // Default (Above)

    if (event.type.includes('TREND')) {
        color = '#00ff00';
        ay = 60; // Below, pointing Up
    } else if (event.type.includes('SNIPER')) {
        color = '#00ff88';
        ay = 40; // Below, pointing Up
    } else if (event.type.includes('EXIT')) {
        color = '#ff3333';
        ay = -40; // Only Exits stay above (pointing Down)
    }

    return {
        x: event.date,
        y: event.price,
        xref: 'x',
        yref: 'y',
        text: text,
        showarrow: true,
        arrowhead: 2,
        ax: 0,
        ay: ay,
        arrowcolor: color,
        font: { color: color, size: 10 },
        bgcolor: '#1a1a1a',
        bordercolor: color,
        borderwidth: 1,
        borderpad: 2,
        opacity: 0.8
    };
}

function createRSIFlag(event) {
    // Similar to Sniper Flag but for RSI panel (y2)
    return {
        x: event.date,
        y: event.rsi, // Use RSI value
        xref: 'x', // Shared X axis
        yref: 'y2', // RSI Axis
        text: 'SNIPE',
        showarrow: true,
        arrowhead: 2,
        ax: 0,
        ay: -30, // Point down to the line? Or up?
        // RSI is usually at bottom. Let's point down to the signal point.
        // Actually, for purchase signal (Entry), usually below pointing up is good.
        // But RSI space is cramped. Let's put it above pointing down.
        arrowcolor: '#00ff88',
        font: { color: '#00ff88', size: 9 },
        bgcolor: '#1a1a1a',
        bordercolor: '#00ff88',
        borderwidth: 1,
        borderpad: 2,
        opacity: 0.8
    };
}
