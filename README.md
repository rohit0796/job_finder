# Job Finder Agent

`job-finder-agent` is a Python job-hunting agent that:

- fetches jobs from multiple sources
- filters and ranks them against your profile and resume
- tracks already-sent jobs in JSON instead of a database
- sends only new shortlisted roles to Telegram or email

The default local store is `seen_jobs.json`. For deployment, the recommended store is Vercel Blob.

## Local Usage

Set your environment variables:

```powershell
$env:GROQ_API_KEY="your_groq_key"
$env:SERPAPI_API_KEY="your_serpapi_key"
$env:TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run locally:

```powershell
python -m job_finder run --dry-run
python -m job_finder run
python -m job_finder list --limit 10
```

## Seen Job Storage

Local JSON store:

```toml
[app]
seen_store = "local_json"
seen_jobs_path = ".job_finder/seen_jobs.json"
```

Vercel Blob store:

```toml
[app]
seen_store = "vercel_blob"
seen_jobs_blob_path = "job-finder/seen_jobs.json"
```

## Vercel Deployment

This repo now includes:

- [api/cron_run.py](/d:/program/vs-programs/AI%20Agent/job_finder/api/cron_run.py)
- [vercel.json](/d:/program/vs-programs/AI%20Agent/job_finder/vercel.json)
- [job_finder.vercel.toml](/d:/program/vs-programs/AI%20Agent/job_finder/job_finder.vercel.toml)
- [requirements.txt](/d:/program/vs-programs/AI%20Agent/job_finder/requirements.txt)

The Vercel setup uses only `serpapi_google_jobs` by default. That is deliberate. It avoids brittle HTML scraping in a scheduled serverless environment.

### Cron Schedule

The configured schedule in [vercel.json](/d:/program/vs-programs/AI%20Agent/job_finder/vercel.json) is:

- `0 3 * * *`

That is once per day at `03:00 UTC`, which is `08:30 IST`.

### Required Vercel Environment Variables

Set these in your Vercel project:

- `CRON_SECRET`
- `SERPAPI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `GROQ_API_KEY`
- `BLOB_READ_WRITE_TOKEN`

Optional:

- `JOB_FINDER_CONFIG_PATH`
  Default behavior already prefers `job_finder.vercel.toml`, so you usually do not need this.

### Deploy Steps

1. Push this repo to GitHub.
2. Import the repo into Vercel.
3. In Vercel Project Settings, add the environment variables listed above.
4. Deploy to production.
5. Confirm the cron definition appears in Vercel.
6. Trigger the function manually once by opening:
   `/api/cron_run`
   Use an authenticated request if `CRON_SECRET` is set.

### Manual Test With Auth Header

If you want to test the route manually after deployment:

```bash
curl -H "Authorization: Bearer $CRON_SECRET" https://your-project.vercel.app/api/cron_run
```

## Notes

- `html_scrape` works only for pages whose job listings are present in the HTML response. If a site renders listings entirely in client-side JavaScript, this approach will not see them.
- `serpapi_google_jobs` uses SerpApi's Google Jobs endpoint and is the recommended source for Vercel deployment.
- Telegram messages are split into safe chunks so large result sets do not fail due to Telegram message length limits.
- If a notification channel succeeds, those jobs are marked as seen and will be skipped on the next run.
- The local config is [job_finder.toml](/d:/program/vs-programs/AI%20Agent/job_finder/job_finder.toml). The Vercel config is [job_finder.vercel.toml](/d:/program/vs-programs/AI%20Agent/job_finder/job_finder.vercel.toml).
