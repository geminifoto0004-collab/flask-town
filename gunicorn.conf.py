"""Gunicorn runtime for the dedicated CUSTOMS AGENT TOWN Render service.

The Render start command remains simply:
    gunicorn town_app:app

Gunicorn automatically loads gunicorn.conf.py from the working directory.
DeepSeek itself is still bounded to 12 seconds for manual/admin commands; this
higher worker timeout is only a safety ceiling for TiDB persistence and other
server work around the model call.
"""

# Free Render has limited CPU/RAM. Keep one process so in-memory caches and
# background town threads stay single-owner, but allow a few request threads so
# /world, /health and dialogue polling are not blocked behind one AI command.
workers = 1
worker_class = "gthread"
threads = 4

# Gunicorn's default 30-second worker timeout was too close to the combined
# DeepSeek + TiDB request budget and surfaced as Render HTTP 502 even when the
# application was still working. This is a worker safety ceiling, not the AI
# timeout; the manual DeepSeek read limit remains 12 seconds in the app.
timeout = 90
graceful_timeout = 30
keepalive = 5

# Keep Render logs visible and unbuffered enough for timeout diagnosis.
accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True
