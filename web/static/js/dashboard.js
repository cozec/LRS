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

    // --- Layout Configuration ---
    const layout = {
        grid: { rows: 2, columns: 1, pattern: 'independent', roworder: 'top to bottom' },
        autosize: true,
        height: window.innerHeight - 100,
        paper_bgcolor: '#1a1a1a',
        plot_bgcolor: '#1a1a1a',
        font: { color: '#e0e0e0' },
        showlegend: false,

        // Axis configuration
        xaxis: {
            rangeslider: { visible: false },
            showgrid: true,
            gridcolor: '#333',
            rangeselector: {
                buttons: [
                    { count: 6, label: '6M', step: 'month', stepmode: 'backward' },
                    { count: 1, label: '1Y', step: 'year', stepmode: 'backward' },
                    { count: 5, label: '5Y', step: 'year', stepmode: 'backward' },
                    { step: 'all', label: 'All' }
                ],
                font: { color: '#e0e0e0', size: 11 },
                bgcolor: '#333',
                activecolor: '#555'
            }
        },
        yaxis: { domain: [0.40, 1], showgrid: true, gridcolor: '#333', title: 'S&P 500' },

        xaxis2: { showgrid: true, gridcolor: '#333', matches: 'x', title: 'Date' },
        yaxis2: { domain: [0, 0.30], showgrid: true, gridcolor: '#333', title: 'RSI', range: [0, 100] },

        // Annotations (Flags)
        annotations: events.map(e => createFlag(e))
    };

    // --- Traces ---

    // 1. Price
    const tracePrice = {
        x: dates, y: close, type: 'scatter', mode: 'lines',
        name: 'SPX', line: { color: '#e0e0e0', width: 1 },
        xaxis: 'x', yaxis: 'y'
    };

    const traceSMA = {
        x: dates, y: sma, type: 'scatter', mode: 'lines',
        name: 'SMA 200', line: { color: '#ffa500', width: 1, dash: 'dash' },
        xaxis: 'x', yaxis: 'y'
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
        tracePrice, traceSMA,
        traceRSI, rsiLow, rsiHigh
    ];

    Plotly.newPlot('chart-container', data, layout, { responsive: true, scrollZoom: true }).then(gd => {
        gd.on('plotly_relayout', event => {
            // Auto-scale Y-axis based on visible X-range
            if (event['xaxis.range[0]'] || event['xaxis.range']) {
                const xStart = event['xaxis.range[0]'] || event['xaxis.range'][0];
                const xEnd = event['xaxis.range[1]'] || event['xaxis.range'][1];

                // Find indices
                const startIdx = dates.findIndex(d => d >= xStart);
                let endIdx = dates.findIndex(d => d >= xEnd);
                if (endIdx === -1) endIdx = dates.length - 1;

                if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
                    const visibleClose = close.slice(startIdx, endIdx);
                    const minPrice = Math.min(...visibleClose);
                    const maxPrice = Math.max(...visibleClose);

                    // Pad by 5%
                    const padding = (maxPrice - minPrice) * 0.05;

                    Plotly.relayout(gd, {
                        'yaxis.range': [minPrice - padding, maxPrice + padding]
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
    let ay = -40; // Arrow length

    if (event.type.includes('ENTRY')) {
        color = '#00ff88'; // Green
        ay = -40;
    } else if (event.type.includes('EXIT')) {
        color = '#ff3333'; // Red
        ay = -40;
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
