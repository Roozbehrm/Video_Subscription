# Video Subscription API

A simple Django REST API for a paid video streaming platform. Users can sign up, browse videos, subscribe to a plan, and watch videos based on their subscription tier. Comments, ratings, and view counts update live over WebSockets.

## What it does

- User registration & login (JWT auth)
- Browse videos and categories
- Subscription plans (free / paid tiers) with Zarinpal payment support
- Watch videos (only if your subscription tier allows it)
- Comment on and rate videos
- Live updates (views, comments, ratings) via WebSockets
- Background jobs for renewing/expiring subscriptions (Celery)

## Tech stack

- Django + Django REST Framework
- Django Channels + Daphne (for WebSockets)
- SQLite (local dev) / PostgreSQL (production)
- Redis + Celery (background tasks, optional locally)
- JWT auth (`djangorestframework-simplejwt`)
- `python-decouple` for environment variables

## Setup (local, no Docker)

1. Create a virtual environment and activate it:
```bash
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate  # Mac/Linux
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy the example env file and fill in your own values:
```bash
copy .env.example .env   # Windows
cp .env.example .env     # Mac/Linux
```
At minimum, set a real `DJANGO_SECRET_KEY`. You can leave `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` empty for local dev — the app will fall back to in-memory/no Redis needed.

4. Run migrations:
```bash
python manage.py migrate
```

5. Seed some demo subscription plans (optional, but handy for testing):
```bash
python manage.py seed_plans
```

6. Start the dev server:
```bash
python manage.py runserver
```

API docs (Swagger UI) will be available at `/api/schema/swagger-ui/`.

## Running tests

```bash
pytest
```

## Running with Docker

```bash
docker-compose up --build
```

This spins up the app, database, Redis, Celery worker, and Celery beat all together.

## Notes

- Videos aren't served through a public media URL — they're only accessible through the `/api/videos/{id}/stream/` endpoint, which checks your subscription before letting you download/stream anything.
- `min_tier` on a video controls which subscription plan is required to watch it (`0` = free for any logged-in user).

## WebSockets (live updates)

Each video has a live channel for views/ratings/comments. Connect to:

```
ws://127.0.0.1:8000/ws/videos/{video_id}/
```

For example, using `wscat` (`npm install -g wscat`):
```bash
wscat -c ws://127.0.0.1:8000/ws/videos/1/
```

Or in the browser console:
```js
const ws = new WebSocket("ws://127.0.0.1:8000/ws/videos/1/");
ws.onmessage = (msg) => console.log(JSON.parse(msg.data));
```

**What happens when you connect:**
- If the video doesn't exist or isn't published, the connection closes right away (code `4404`).
- Otherwise, you immediately get a snapshot of the current stats:
```json
{
  "event": "snapshot",
  "data": {
    "views_count": 12,
    "avg_rating": 4.5,
    "ratings_count": 8,
    "comments_count": 3
  }
}
```

**After that, you'll get pushed events whenever something happens to that video** (someone watches it, rates it, or comments), for example:
```json
{ "event": "view", "data": { "views_count": 13 } }
{ "event": "rating", "data": { "avg_rating": 4.6, "ratings_count": 9 } }
{ "event": "comment", "data": { "id": 5, "user": "someuser", "body": "great video!", "created_at": "..." } }
```

No authentication is required just to connect and listen — but actually triggering these events (rating, commenting, watching) still goes through the normal authenticated REST endpoints (`/api/videos/{id}/rate/`, `/comments/`, `/stream/`).
