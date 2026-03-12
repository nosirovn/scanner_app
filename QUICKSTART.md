# Quick Start Guide - Small-Cap Momentum Scanner

## 5-Minute Setup

### Step 1: Get API Keys (2 min)

**Finnhub API Key:**
1. Go to [https://finnhub.io](https://finnhub.io)
2. Sign up (free tier available)
3. Get API key from dashboard

**Telegram Bot:**
1. Open Telegram
2. Search for [@BotFather](https://t.me/botfather)
3. Send `/newbot` and follow instructions
4. Copy the **bot token**

**Telegram Chat ID:**
1. Search for [@userinfobot](https://t.me/userinfobot)
2. Send `/start` and copy your **user ID**

### Step 2: Install & Configure (2 min)

```bash
# Navigate to scanner directory
cd scanner_app

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy example env
cp .env.example .env

# Edit .env and add your API keys
# FINNHUB_API_KEY=your_key
# TELEGRAM_BOT_TOKEN=your_token
# TELEGRAM_CHAT_ID=your_id
```

### Step 3: Run (1 min)

```bash
python app.py
```

**Open in browser:** http://localhost:8000

## Dashboard Usage

### 🎯 What to Look For

1. **Obvious Stock** (red banner at top)
   - This is the single best setup right now
   - Check the trading levels: Entry (E), Take Profit (TP), Stop Loss (SL)

2. **Momentum Radar** (yellow section)
   - Top 5 strongest momentum stocks
   - Updates every 5 seconds
   - 🔥 = Very strong, ⚡ = Strong

3. **Scanner Table** (main data)
   - All qualified stocks
   - Green % = winners
   - RVOL = relative volume (higher is better)
   - Use filters to narrow down

### 🎨 Alert Colors Explained

- 🔥 **HOT** (Red) = Most aggressive, best probability
- ⚡ **MOMENTUM** (Yellow) = Strong momentum signal
- 👁️ **WATCH** (Cyan) = Early signal, watch closely

### 📊 Columns Explained

| Column | Meaning |
|--------|---------|
| Ticker | Stock symbol (clickable → Google Finance) |
| Price | Current price |
| Change % | Percent gain/loss |
| RVOL | Relative volume (5+ is good) |
| Volume | Total shares traded |
| Float | Shares outstanding |
| EMA | Trend alignment (↑↑↑ = most bullish) |
| Alert | Alert level if triggered |
| ⭐ | Add to watchlist |

### 📈 EMA Alignment

- ↑↑↑ = **Bullish** (Price above all EMAs) ✅ Best
- ↑↑ = **Bullish** (above 2 EMAs)
- ↑ = **Weak** (above 1 EMA)
- ↓ = **Bearish** (below EMAs)

### 🎚️ Using Filters

Click "⚙ Filters" to customize:
- **Price Min/Max**: Filter by price range
- **Float Max**: Only small float (<5M for micro-caps)
- **Min RVOL**: Higher = more volume surge (5-10 is sweet spot)
- **Min Change %**: Filter by % gain (10%+ recommended)

### 💫 Session Info

Header shows:
- **🟣 PREMARKET** (4:00 - 9:30 AM)
- **🟢 MARKET** (9:30 AM - 4:00 PM) ← Most active
- **🔵 AFTER HOURS** (4:00 - 8:00 PM)

## Telegram Alerts

Once configured:
- **Hot alerts** will come to Telegram instantly
- Click ticker name to open Google Finance
- Shows Entry, TP, SL right in message
- Includes all key metrics

## Trading Strategy Tips

### Perfect Setup Contains:

✅ +15% or more change
✅ RVOL 5+
✅ EMA alignment ↑↑ or better
✅ Small float (<10M)
✅ Catalyst present (News, Earnings, etc.)

### Risk Management:

- **Entry**: Price level shown
- **TP (Take Profit)**: Exit profitable side
- **SL (Stop Loss)**: Exit losing side
- **Risk/Reward**: Ratio calculated automatically

### Gap & Go Strategy:

1. Look for Obvious Stock (red box)
2. Check if it has catalyst (📰, 💰, 🤝)
3. Verify EMA alignment (↑↑↑ is best)
4. Watch RVOL trend (should stay high or increase)
5. Enter at support level shown
6. Exit at TP or SL

## Monitoring Best Practices

1. **During Premarket** (4:00 - 9:30 AM)
   - Scan for runners
   - Note high RVOL stocks
   - Plan entries for market open

2. **Market Open** (9:30 - 10:00 AM)
   - Most volatility and volume
   - Best for Gap & Go trades
   - Monitor Telegram alerts closely

3. **Mid-Day** (10:00 AM - 2:00 PM)
   - Secondary moves
   - Lower volume typically
   - Good for confirmation trades

4. **End of Day** (2:00 - 4:00 PM)
   - Late runners
   - Watch for consolidation
   - Plan next day's setups

## Common Issues & Solutions

### Problem: No stocks showing up
**Solution:**
- Check if market is open (outside 9:30 AM - 4:00 PM ET)
- Verify Finnhub API key in `.env`
- Check logs: `tail -f logs/scanner.log`

### Problem: Telegram alerts not working
**Solution:**
- Verify bot token is correct
- Send `/start` to bot in Telegram
- Check chat ID matches your user ID
- Ensure bot has permissions

### Problem: Dashboard loads slow
**Solution:**
- Reduce filter window to smaller time period
- Restart application: `Ctrl+C` then `python app.py`
- Check internet connection

### Problem: Alerts too frequent/spam
**Solution:**
- Increase minimum thresholds in filters:
  - Raise "Min Change %" to 15%
  - Raise "Min RVOL" to 8

## Advanced Usage

### Adding More Stocks to Watchlist

Click the ⭐ star on any stock to add to watchlist.
Access at: http://localhost:8000/api/watchlist

### Custom Filters

Edit `config.py` to change defaults:
```python
SCANNER_FILTERS = {
    "price_min": 1,
    "price_max": 20,
    "float_max": 10_000_000,
    "relative_volume_min": 5,
    "volume_min": 50_000,
    "change_min": 10
}
```

### Change Alert Thresholds

Edit alert levels in `config.py`:
```python
ALERT_LEVELS = {
    "watch": {"change_min": 8, "rvol_min": 3},
    "momentum": {"change_min": 12, "rvol_min": 5, "float_max": 10_000_000},
    "hot": {"change_min": 20, "rvol_min": 7, ...}
}
```

## Database

Scanner saves all data to SQLite database (`scanner.db`):
- Stock scans
- Alert history
- Trade logs
- Watchlist

To reset database:
```bash
rm scanner.db
# Restart app - database will be recreated
python app.py
```

## Performance Tips

1. **Reduce CPU Usage**
   - Use filters to narrow down stocks
   - Increase scan interval (edit `SCAN_INTERVAL` in config)

2. **Faster Alerts**
   - Use hot alert threshold only
   - Disable watch alerts in settings

3. **Lower Latency**
   - Use wired internet connection
   - Close other applications
   - Ensure Finnhub API is responding

## Keyboard Shortcuts (Coming Soon)

Coming in next version:
- `Q` = Quick add to watchlist
- `A` = Toggle alerts on/off
- `/` = Search stocks

## Support Resources

- **Finnhub Docs**: https://finnhub.io/docs/api
- **FastAPI Docs**: http://localhost:8000/docs (when running)
- **Telegram Bot Docs**: https://core.telegram.org/bots

## Next Steps

1. ✅ Get API keys set up
2. ✅ Run the scanner
3. ✅ Monitor for 1-2 hours during market
4. ✅ Get familiar with the interface
5. 🎯 Start trading!

---

**Need help? Check `README.md` for detailed documentation.**

**Happy trading! 🚀📈**
