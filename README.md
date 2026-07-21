# Pittsburgh Weather + AQI Calendar Feed

A self-updating `.ics` calendar feed with a daily event showing the forecast
(high/low, conditions, precipitation chance, wind) and the US Air Quality
Index, built on the free [Open-Meteo](https://open-meteo.com) API (no API key
needed).

## How it works

- `generate_weather_ics.py` fetches a 7-day forecast + AQI and writes `docs/weather.ics`.
- A GitHub Actions workflow (`.github/workflows/update-feed.yml`) re-runs this
  script every day at 11:00 UTC and commits the refreshed file.
- GitHub Pages serves `docs/weather.ics` at a stable URL that any calendar app
  can subscribe to. Because the file is regenerated daily, subscribers'
  calendars stay current without you doing anything.

## One-time setup (~5 minutes)

1. **Create a new GitHub repo** (public or private both work) and push these
   files to it:
   ```
   git init
   git add .
   git commit -m "Initial weather ICS feed"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```

2. **Enable GitHub Pages**:
   - Go to your repo → **Settings → Pages**
   - Under "Build and deployment", set **Source** to "Deploy from a branch"
   - Set **Branch** to `main` and folder to `/docs`
   - Save. GitHub will give you a URL like:
     `https://<your-username>.github.io/<repo-name>/weather.ics`

3. **Enable the workflow**: it will run automatically on the cron schedule.
   You can also trigger it manually anytime from the repo's **Actions** tab →
   "Update weather & AQI ICS feed" → **Run workflow** — do this once now so
   `docs/weather.ics` gets committed via the bot (rather than relying only on
   the copy you pushed manually).

## Subscribing

Once Pages is live, subscribe using the `webcal://` version of the URL so
your calendar app treats it as a live feed rather than a one-time import:

```
webcal://<your-username>.github.io/<repo-name>/weather.ics
```

- **Apple Calendar (Mac)**: File → New Calendar Subscription → paste the URL
- **iPhone/iPad**: Settings → Calendar → Accounts → Add Account → Other →
  Add Subscribed Calendar → paste the URL
- **Google Calendar**: Other calendars (+) → From URL → paste the
  `https://` version (Google doesn't use `webcal://`)
- **Outlook**: Add calendar → Subscribe from web → paste the URL

Set the refresh interval to daily if your client asks (Google Calendar
refreshes on its own schedule, roughly every 12–24 hours, and this can't be
sped up).

## Changing the location

Edit the `--lat`, `--lon`, and `--name` values in
`.github/workflows/update-feed.yml` (find coordinates for any city at
[latlong.net](https://www.latlong.net/)). Commit the change and the next run
will pick it up.

## Notes

- AQI forecasts from Open-Meteo only extend 7 days out; the weather forecast
  itself can go further if you raise `--days` (up to 16), but AQI won't be
  shown for days beyond day 7.
- AQI shown is the **daily maximum** US AQI (the standard way of reporting a
  single-number "AQI for the day"), aggregated from hourly data.
- Data source: Open-Meteo Weather Forecast API and Air Quality API, both free
  and requiring no signup.
