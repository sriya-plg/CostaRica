# Costa Rica — Graph email subscription webhook (step 1)

Detect new email arrival via a Microsoft Graph subscription webhook. Attachment download, XML parsing, and backend integration are stubbed for a later stage.

## Project structure

```
app/
  core/                         # App-wide config and logging
    config.py
    logging.py
  persistence/                  # Local storage
    processed_emails.py         # SQLite dedup table
    subscription_store.py       # JSON subscription state
  graph/                        # Microsoft Graph API
    client.py                   # msal auth + HTTP with retries
    subscriptions.py            # create / renew subscription calls
  webhook/                      # Step 1: inbound Graph notifications
    router.py                   # GET/POST /webhook
    notifications.py            # validate, dedup, dispatch
  pipeline/                     # Step 2+: email processing (stubbed)
    message_processor.py
  jobs/                         # Scheduled background work
    subscription_lifecycle.py   # ensure valid + periodic renewal
  main.py                       # FastAPI app bootstrap
scripts/
  create_subscription.py        # one-off subscription setup CLI
data/                           # runtime artifacts (gitignored)
  processed_emails.db
  subscription.json
```

## Prerequisites

- Python 3.13+
- An Azure AD app registration with **Application** permission `Mail.Read` (admin consent granted)
- [ngrok](https://ngrok.com/) (or another HTTPS tunnel) for local webhook delivery

## Setup

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in values:

   - `MAILBOX` — the mailbox user ID or UPN to watch
   - `CLIENT_STATE` — a secret string Graph echoes back; must match what the webhook validates
   - `NOTIFICATION_URL` — public HTTPS URL ending in `/webhook` (set after ngrok is running)

3. Start ngrok and note the HTTPS URL:

   ```powershell
   ngrok http 8000
   ```

   Set `NOTIFICATION_URL` in `.env` to `https://<ngrok-host>/webhook`.

4. Create the Graph subscription (also done automatically on server startup if missing/expired):

   ```powershell
   python scripts/create_subscription.py
   ```

5. Start the FastAPI server:

   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   On startup the app ensures a valid subscription exists and schedules renewal every 4 hours when expiry is within one day.

## Test

1. Send an email to the monitored mailbox.
2. Graph POSTs to `/webhook`; the server responds `202` immediately and processes in the background.
3. Confirm a row in SQLite:

   ```powershell
   sqlite3 data/processed_emails.db "SELECT * FROM processed_emails;"
   ```

   You should see `message_id`, `status='received'`, and `received_at`.

## Webhook behavior

- **GET** `/webhook?validationToken=...` — returns the token as `text/plain` (Graph subscription validation).
- **POST** `/webhook` — validates `clientState`, deduplicates on `message_id`, inserts `processed_emails`, then calls the stub in `app/pipeline/message_processor.py`.

Subscription state is stored in `data/subscription.json`; processed messages in `data/processed_emails.db`.
