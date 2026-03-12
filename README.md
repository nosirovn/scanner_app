# Small-Cap Momentum Stock Scanner

A production-ready, real-time stock momentum scanner for identifying high-probability Gap & Go trading opportunities. Built with FastAPI, WebSockets, and Finnhub API.

## Features

✨ **Real-Time Scanning**
- Continuous monitoring of top 50 gainers
- 5-second scan intervals
- Real-time data from Finnhub API

📊 **Advanced Analytics**
- Momentum scoring and ranking
- EMA alignment detection (EMA 20/50/200)
- Relative volume (RVOL) calculation
- Automatic trading level generation (Entry, TP, SL)

🎯 **Smart Alerts**
- Three alert levels: Watch, Momentum, Hot
- Telegram bot notifications with clickable links
- In-app sound alerts
- Alert history tracking

⭐ **Obvious Stock Detection**
- Identifies single most obvious trade of the day
- Multi-factor scoring (price, volume, float, catalysts, EMAs)
- Highest probability setup highlighted

⚡ **Momentum Radar**
- Top 3-5 strongest momentum stocks
- Updates every 5 seconds
- Real-time momentum tracking

🎨 **Interactive Dashboard**
- Clean, responsive web UI
- Session-based filtering (Premarket, Market, After Hours)
- Dynamic countdown to next session
- Adjustable filters
- Watchlist management

## Project Structure

```
scanner_app/
├── app.py                      # Main FastAPI application
├── config.py                   # Configuration & settings
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── .env                       # (Create from .env.example)
│
├── data/
│   └── market_data.py         # Finnhub API client
│
├── scanner/
│   ├── scanner_engine.py      # Main scanning logic
│   ├── momentum_radar.py       # Momentum tracking
│   ├── obvious_stock.py        # Obvious stock detection
│   └── level_calculator.py     # Trading level calculations
│
├── alerts/
│   ├── telegram_alert.py       # Telegram notifications
│   └── sound_alert.py          # Audio alerts
│
├── database/
│   ├── db.py                  # Database setup
│   └── models.py              # SQLAlchemy models
│
├── dashboard/
│   ├── routes.py              # API endpoints & WebSocket
│   ├── templates/
│   │   └── index.html         # Main dashboard UI
│   └── static/
│       ├── style.css          # Styling
│       └── app.js             # Frontend logic
│
├── utils/
│   └── logger.py              # Logging configuration
│
└── logs/                       # Application logs (auto-created)
```

## Installation

### 1. Clone & Setup

```bash
cd scanner_app
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` and add:
- **FINNHUB_API_KEY**: Get from [https://finnhub.io](https://finnhub.io) (free tier available)
- **TELEGRAM_BOT_TOKEN**: Create bot via [@BotFather](https://t.me/botfather) on Telegram
- **TELEGRAM_CHAT_ID**: Your Telegram user ID (send `/start` to your bot to get it)

### 4. Run Application

```bash
python app.py
```

Access dashboard at: **http://localhost:8000**

## Configuration

### Scanner Filters (Default)

Edit `config.py` to customize:

```python
SCANNER_FILTERS = {
    "price_min": 1,              # Minimum price
    "price_max": 20,             # Maximum price
    "float_max": 10_000_000,     # Maximum float (shares)
    "relative_volume_min": 5,    # Minimum RVOL
    "volume_min": 50_000,        # Minimum volume
    "change_min": 10             # Minimum % change
}
```

### Alert Thresholds

Three alert levels are configured:

**Watch Alert** (least aggressive)
- Change ≥ 8%, RVOL ≥ 3

**Momentum Alert**
- Change ≥ 12%, RVOL ≥ 5, Float < 10M

**Hot Alert** (most aggressive)
- Change ≥ 20%, RVOL ≥ 7, Volume ≥ 100K, Float < 10M, Catalyst present

### Market Sessions (ET - Eastern Time)

```
Premarket:    04:00 - 09:30
Market:       09:30 - 16:00
After Hours:  16:00 - 20:00
```

## API Endpoints

### REST API

```
GET  /health                    # Health check
GET  /api/session/current       # Current market session
GET  /api/scanner/status        # Scanner statistics
GET  /api/stocks/top            # Top stocks (paginated)
GET  /api/stocks/momentum       # Momentum leaders
GET  /api/stocks/obvious        # Obvious stock of day
GET  /api/alerts/recent         # Recent alerts
GET  /api/watchlist             # Get watchlist
POST /api/watchlist/add/{ticker} # Add to watchlist
POST /api/settings/{key}        # Update settings
```

### WebSocket

```
WS /ws/scanner                  # Real-time scanner updates
WS /ws/alerts                   # Real-time alert stream
```

## Dashboard Features

### Header
- Real-time session indicator with countdown to next session
- Color-coded session badges (Premarket 🟣, Market 🟢, After Hours 🔵)
- Adjustable filters panel

### Obvious Stock
- Single most obvious trade of the day
- Key metrics: Price, Change %, RVOL, Float
- Multi-factor ranking algorithm

### Momentum Radar
- Top 5 strongest momentum stocks
- Updated every 5 seconds
- Quick visual scan of market momentum

### Tabs
- **Gainers**: Top performers
- **Low Float**: Small float stocks
- **Unusual Volume**: High relative volume
- **Momentum**: Highest momentum scores
- **Alerts**: Triggered alerts only

### Scanner Table
Displays qualified stocks with:
- Ticker, Price, Change %, RVOL, Volume, Float
- EMA Alignment (↑↑↑ / ↑↑ / ↑ / ↓)
- Alert Level (Hot 🔥 / Momentum ⚡ / Watch 👁️)
- Trading Levels (Entry, TP, SL)
- Catalyst icons (News 📰, Earnings 💰, etc.)

### Watchlist
- Add/remove stocks to personal watchlist
- Persistent storage

## Trading Levels

Automatic calculation based on price and EMA alignment:

- **Entry (E)**: 2% above current price
- **Take Profit (TP)**: 12% above current price (adjusted for EMA alignment)
- **Stop Loss (SL)**: 3% below current price (tighter if below EMA50)
- **Risk/Reward**: Automatically calculated ratio

Color-coded display:
- Entry → Black
- TP → Blue
- SL → Yellow

## Catalyst Detection

The scanner automatically detects catalysts:
- 📰 News
- 💰 Earnings
- 📝 SEC Filing
- 📈 Unusual Volume
- 🤝 Partnership

Hover over catalyst icons for 2-sentence summary.

## Telegram Alerts

Format example:
```
🔥 HOT MOMENTUM ALERT

[ABCD](https://www.google.com/finance/quote/ABCD)

Price: 4.12
E 4.20 | TP 4.60 | SL 3.98

+28%
RVOL 9.4
Volume 410K
Float 6M

EMAs ↑↑↑
Catalyst 📰
```

## Database

### SQLite (Default)
Automatically created at `scanner.db`

### PostgreSQL (Production)
Set in `.env`:
```
DATABASE_URL=postgresql://user:password@localhost/scanner_db
```

### Tables
- **stocks**: Individual stock scans
- **alerts**: Alert history
- **scan_sessions**: Session statistics
- **watchlist**: User watchlist
- **trades**: Trade records
- **settings**: Application settings

## Performance Targets

- Scan interval: 5 seconds
- Stocks scanned: 30-150 per session
- Alert latency: <500ms
- Dashboard refresh: Real-time WebSocket updates

## Logging

Logs are written to `logs/scanner.log` with:
- Timestamp
- Log level
- Component
- Message

Configure level in `.env`:
```
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Troubleshooting

### No stocks appearing
- Check Finnhub API key is valid
- Verify scanner is running during market hours
- Check logs in `logs/scanner.log`

### Telegram alerts not sending
- Verify bot token is correct
- Confirm chat ID is valid
- Check bot has permission to send messages

### Database errors
- Delete `scanner.db` and restart (will recreate)
- Or check database connection string

### WebSocket connection failed
- Ensure ws:// or wss:// protocol is used
- Check firewall allows port 8000

## Production Deployment

### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:8000
```

### Using Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

Build and run:
```bash
docker build -t scanner .
docker run -p 8000:8000 --env-file .env scanner
```

### Environment Variables

Always use `.env` file or environment variables for:
- API Keys
- Database credentials
- Bot tokens
- Never commit `.env` to git

## Future Enhancements

- [ ] Machine learning momentum prediction
- [ ] Multi-timeframe analysis
- [ ] Advanced drawing tools on charts
- [ ] Email alerts
- [ ] Discord integration
- [ ] Performance analytics dashboard
- [ ] Automated trading execution
- [ ] Strategy backtesting
- [ ] Mobile app

## Support

For issues or questions:
1. Check logs in `logs/scanner.log`
2. Review configuration in `.env`
3. Verify API credentials are valid
4. Ensure market hours are active

## License

This project is provided as-is for educational and personal use.

## Disclaimer

This scanner is for educational purposes only. Trading stocks involves risk. Always perform your own research and consult with a financial advisor before making investment decisions. Past performance does not guarantee future results.

---

**Happy scanning! 🚀📈**
