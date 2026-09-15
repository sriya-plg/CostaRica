# Costa Rica — Microsoft Graph Email Unread Poller

Automated email ingestion pipeline for extracting Cardtronics invoice numbers and shipment numbers from incoming XML emails using Microsoft Graph API Unread Polling with `isRead` mark disposition (matching `plg-ml-domestic-order-entry-bot`).

## Architecture & How It Works

```
1. Polling (Producer)
   Timer Tick (every 15s) ──► Query Graph: isRead eq false & receivedDateTime >= (now - lookback_hours)
                                     │
2. In-Flight Tracking & Processing   ▼
   EmailTracker.start() ──► Download Attachments ──► Parse Invoice & Shipment XML ──► Backend API
                                     │
3. Disposition (Outcome)             ▼
   Success ───────────────► Graph API: PATCH isRead=true  &  EmailTracker.complete()
   Retryable Error ───────► Leave Unread in Outlook for retry on next tick
```

## Project Structure

```
app/
  core/                         # App-wide config and logging
    config.py
    logging.py
  persistence/                  # Local storage
    processed_emails.py         # SQLite dedup table (processed_emails.db)
  graph/                        # Microsoft Graph API
    client.py                   # MSAL auth + HTTP client with retries
    messages.py                 # list_unread_emails, mark_message_as_read
    attachments.py              # fetch attachments
  pipeline/                     # Email and XML processing pipeline
    message_processor.py        # Main processing flow
    subject_parser.py           # Extract shipment numbers from subjects
    xml_processor.py            # Parse XML attachments (Invoice & AHC XML)
  jobs/                         # Periodic polling jobs
    email_poller.py             # EmailTracker & unread email poller
  main.py                       # FastAPI application & APScheduler runner
scripts/
  poll_once.py                  # Standalone CLI to run a single poll iteration
data/                           # Runtime artifacts (gitignored)
  processed_emails.db
downloads/                      # Downloaded attachments & result.json
```

## Setup

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Configure `.env`:

   ```env
   TENANT_ID=your-azure-tenant-id
   CLIENT_ID=your-azure-client-id
   CLIENT_SECRET=your-azure-client-secret
   MAILBOX=your-monitored-mailbox@domain.com
   POLL_INTERVAL_SECONDS=15
   INITIAL_LOOKBACK_HOURS=48
   ```

3. Run the service:

   ```powershell
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. Or execute a single poll run manually:

   ```powershell
   uv run python scripts/poll_once.py
   ```


## Endpoints

- `GET /health` — Service health check.
- `GET /status` — Current polling status, mailbox, and delta state.
- `POST /poll` — Trigger an immediate poll iteration on-demand.

