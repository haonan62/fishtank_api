# Read by gunicorn when it starts in this folder. Made for a very small server: one process holds the fish catalogue
# in little memory, and its threads keep one slow request from holding up the others
# WEB_CONCURRENCY sets more processes when the server has the memory, rate limits and data are shared through sqlite
import os

bind = os.environ.get('FISHTANK_BIND', '0.0.0.0:5000')
workers = int(os.environ.get('WEB_CONCURRENCY', '1'))
worker_class = 'gthread'
threads = 4
timeout = 30
# the worker's heartbeat file, on a slow or full disk a file there would make gunicorn kill healthy workers
worker_tmp_dir = '/dev/shm' if os.path.isdir('/dev/shm') else None
