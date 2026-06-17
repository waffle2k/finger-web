import os

class Config:
    """Flask configuration class"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Database configuration (for future use)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Mail configuration (for future use)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # File upload configuration
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_FILE_SIZE', 16 * 1024 * 1024))  # 16MB default
    UPLOAD_FOLDER = '/tmp'
    ALLOWED_EXTENSIONS = {'txt'}
    
    # Remote server configuration for SCP
    REMOTE_HOST = os.environ.get('REMOTE_HOST') or 'example.com'
    REMOTE_USER = os.environ.get('REMOTE_USER') or 'user'
    REMOTE_PATH = os.environ.get('REMOTE_PATH') or '/home/user/uploads/'
    REMOTE_PORT = int(os.environ.get('REMOTE_PORT', 22))
    REMOTE_PRIVATE_KEY = os.environ.get('REMOTE_PRIVATE_KEY')  # Path to SSH private key file
    SCP_ENABLED = os.environ.get('SCP_ENABLED', 'false').lower() == 'true'
    
    # Rate limiting (Flask-Limiter), keyed per client IP.
    # The app only ever receives nginx cache *misses* (upstream caches 200s for
    # 30s), so these limits throttle exactly the uncached finger-daemon lookups
    # (e.g. username enumeration) without affecting the cached hot path.
    # Limit strings are ';'-separated, e.g. "30 per minute;600 per hour".
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'true').lower() == 'true'
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI') or 'memory://'
    # Global default applied to every route.
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT') or '120 per minute;2000 per hour'
    # Stricter limit for endpoints that shell out to the finger daemon.
    RATELIMIT_FINGER = os.environ.get('RATELIMIT_FINGER') or '30 per minute;600 per hour'
    # Limit for the authenticated upload endpoint (anti brute-force / spam).
    RATELIMIT_UPLOAD = os.environ.get('RATELIMIT_UPLOAD') or '10 per minute;60 per hour'
    # Number of trusted reverse-proxy hops in front of the app. nginx on the
    # same host appends one X-Forwarded-For entry, so the default is 1. Without
    # this the app only sees the Docker bridge gateway and every client would
    # share a single rate-limit bucket.
    PROXY_FORWARDED_COUNT = int(os.environ.get('PROXY_FORWARDED_COUNT', 1))

    # Basic authentication credentials - multiple users support
    # Environment variable format: "user1:pass1,user2:pass2"
    BASIC_AUTH_USERS_STR = os.environ.get('BASIC_AUTH_USERS', '')

    # Parse users string into dictionary
    BASIC_AUTH_USERS = {}
    for user_pass in BASIC_AUTH_USERS_STR.split(','):
        if ':' in user_pass:
            username, password = user_pass.strip().split(':', 1)
            BASIC_AUTH_USERS[username.strip()] = password.strip()
