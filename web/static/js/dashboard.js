document.addEventListener('DOMContentLoaded', function () {
    fetchData();
});

async function fetchData() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();
        renderChart(data.history, data.events);
    } catch (error) {
        console.error('Error fetching data:', error);
        document.querySelector('.loading').textContent = 'Error Loading Data';
    }
}

function renderChart(history, events) {
    const dates = history.map(d => d.Date);
    const close = history.map(d => d.Close);
    const sma = history.map(d => d.SMA_200);
    const rsi = history.map(d => d.RSI);
    const lrsVal = history.map(d => d.LRS_Sniper_Value);
    const bhVal = history.map(d => d.BH_TQQQ_Value);

    // --- Layout Configuration ---
    const layout = {
        grid: { rows: 3, columns: 1, pattern: 'independent', roworder: 'top to bottom' },
        autosize: true,
        height: window.innerHeight - 100,
        paper_bgcolor: '#1a1a1a',
        plot_bgcolor: '#1a1a1a',
        font: { color: '#e0e0e0' },
        showlegend: false,

        // Axis configuration
        xaxis: { rangeslider: { visible: false }, showgrid: true, gridcolor: '#333' },
        yaxis: { domain: [0.55, 1], showgrid: true, gridcolor: '#333', title: 'S&P 500' },

        xaxis2: { showgrid: true, gridcolor: '#333', matches: 'x', showticklabels: false },
        yaxis2: { domain: [0.30, 0.50], showgrid: true, gridcolor: '#333', title: 'RSI', range: [0, 100] },

        xaxis3: { showgrid: true, gridcolor: '#333', matches: 'x', title: 'Date' },
        yaxis3: { domain: [0, 0.25], type: 'log', showgrid: true, gridcolor: '#333', title: 'Equity ($)' },

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

    // RSI Zones
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

    // 3. Equity
    const traceLRS = {
        x: dates, y: lrsVal, type: 'scatter', mode: 'lines',
        name: 'Hybrid Sniper', line: { color: '#3388ff', width: 2 },
        xaxis: 'x3', yaxis: 'y3'
    };

    const traceBH = {
        x: dates, y: bhVal, type: 'scatter', mode: 'lines',
        name: 'Buy & Hold TQQQ', line: { color: '#555', width: 1 },
        xaxis: 'x3', yaxis: 'y3'
    };

    const data = [
        tracePrice, traceSMA,
        traceRSI, rsiLow, rsiHigh,
        traceLRS, traceBH
    ];

    Plotly.newPlot('chart-container', data, layout, { responsive: true });

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
