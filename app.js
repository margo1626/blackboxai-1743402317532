// Connect to WebSocket
const socket = io();

// DOM Elements
const connectionStatus = document.getElementById('connection-status');
const botStatus = document.getElementById('bot-status');
const startBotBtn = document.getElementById('start-bot');
const stopBotBtn = document.getElementById('stop-bot');
const currentCapital = document.getElementById('current-capital');
const profitLoss = document.getElementById('profit-loss');
const positionsTable = document.getElementById('positions-table');

// Charts
let priceChart, rsiChart, macdChart;

// Initialize charts
function initCharts() {
    // Price Chart
    const priceCtx = document.getElementById('priceChart').getContext('2d');
    priceChart = new Chart(priceCtx, {
        type: 'candlestick',
        data: {
            datasets: [{
                label: 'ETH/USDC',
                data: [],
                color: {
                    up: '#10b981',
                    down: '#ef4444',
                    unchanged: '#9ca3af',
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute'
                    }
                },
                y: {
                    beginAtZero: false
                }
            }
        }
    });

    // RSI Chart
    const rsiCtx = document.getElementById('rsiChart').getContext('2d');
    rsiChart = new Chart(rsiCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'RSI (14)',
                data: [],
                borderColor: '#3b82f6',
                tension: 0.1,
                fill: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    ticks: {
                        stepSize: 20
                    }
                }
            },
            plugins: {
                annotation: {
                    annotations: {
                        overbought: {
                            type: 'line',
                            yMin: 70,
                            yMax: 70,
                            borderColor: '#ef4444',
                            borderWidth: 1,
                            label: {
                                content: 'Overbought',
                                enabled: true,
                                position: 'left'
                            }
                        },
                        oversold: {
                            type: 'line',
                            yMin: 30,
                            yMax: 30,
                            borderColor: '#10b981',
                            borderWidth: 1,
                            label: {
                                content: 'Oversold',
                                enabled: true,
                                position: 'left'
                            }
                        }
                    }
                }
            }
        }
    });

    // MACD Chart
    const macdCtx = document.getElementById('macdChart').getContext('2d');
    macdChart = new Chart(macdCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'MACD',
                    data: [],
                    borderColor: '#3b82f6',
                    tension: 0.1
                },
                {
                    label: 'Signal',
                    data: [],
                    borderColor: '#ef4444',
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

// Update charts with new data
function updateCharts(data) {
    // Format data for candlestick chart
    const candlestickData = data.map(item => ({
        x: new Date(item.time),
        o: item.open,
        h: item.high,
        l: item.low,
        c: item.close
    }));

    // Update price chart
    priceChart.data.datasets[0].data = candlestickData;
    priceChart.update();

    // Update RSI chart
    const rsiData = data.map(item => item.RSI);
    const labels = data.map(item => new Date(item.time));
    rsiChart.data.labels = labels;
    rsiChart.data.datasets[0].data = rsiData;
    rsiChart.update();

    // Update MACD chart
    const macdData = data.map(item => item.MACD);
    const signalData = data.map(item => item.MACD_Signal);
    macdChart.data.labels = labels;
    macdChart.data.datasets[0].data = macdData;
    macdChart.data.datasets[1].data = signalData;
    macdChart.update();
}

// Update account summary
function updateAccountSummary(data) {
    currentCapital.textContent = `$${data.current_capital.toFixed(2)}`;
    
    const profit = data.current_capital - data.initial_capital;
    const profitPct = (profit / data.initial_capital) * 100;
    const profitColor = profit >= 0 ? 'text-green-600' : 'text-red-600';
    
    profitLoss.innerHTML = `
        <span class="${profitColor}">$${profit.toFixed(2)} (${profitPct.toFixed(2)}%)</span>
    `;
}

// Update positions table
function updatePositionsTable(positions) {
    positionsTable.innerHTML = '';
    
    if (Object.keys(positions).length === 0) {
        positionsTable.innerHTML = `
            <tr>
                <td colspan="4" class="px-4 py-2 text-center text-gray-500">No open positions</td>
            </tr>
        `;
        return;
    }

    for (const [symbol, position] of Object.entries(positions)) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-4 py-2">${symbol}</td>
            <td class="px-4 py-2">${position.size.toFixed(4)}</td>
            <td class="px-4 py-2">$${position.entry_price.toFixed(2)}</td>
            <td class="px-4 py-2">$${position.current_price?.toFixed(2) || 'N/A'}</td>
        `;
        positionsTable.appendChild(row);
    }
}

// Socket event handlers
socket.on('connect', () => {
    console.log('Connected to server');
    connectionStatus.innerHTML = `
        <span class="h-3 w-3 rounded-full bg-green-500 mr-2"></span>
        <span>Connected</span>
    `;
    
    // Fetch initial data
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            updateAccountSummary(data);
            updatePositionsTable(data.positions);
            botStatus.textContent = data.bot_running ? 'Running' : 'Stopped';
            botStatus.className = data.bot_running ? 
                'px-3 py-1 rounded-full bg-green-100 text-green-800' : 
                'px-3 py-1 rounded-full bg-red-100 text-red-800';
                
            startBotBtn.disabled = data.bot_running;
            stopBotBtn.disabled = !data.bot_running;
        });
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    connectionStatus.innerHTML = `
        <span class="h-3 w-3 rounded-full bg-red-500 mr-2"></span>
        <span>Disconnected</span>
    `;
});

socket.on('status_update', (data) => {
    updateAccountSummary(data);
    updatePositionsTable(data.positions);
});

socket.on('chart_data', (data) => {
    updateCharts(data);
});

// Button event listeners
startBotBtn.addEventListener('click', () => {
    fetch('/api/start', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'Bot started') {
            botStatus.textContent = 'Running';
            botStatus.className = 'px-3 py-1 rounded-full bg-green-100 text-green-800';
            startBotBtn.disabled = true;
            stopBotBtn.disabled = false;
        }
    });
});

stopBotBtn.addEventListener('click', () => {
    fetch('/api/stop', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'Bot stopped') {
            botStatus.textContent = 'Stopped';
            botStatus.className = 'px-3 py-1 rounded-full bg-red-100 text-red-800';
            startBotBtn.disabled = false;
            stopBotBtn.disabled = true;
        }
    });
});

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
});
