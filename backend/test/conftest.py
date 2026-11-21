"""Initialize isolated test settings before any module imports Settings."""
import os

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['SECRET_KEY'] = 'test-key-only-not-for-production'
os.environ['ENVIRONMENT'] = 'test'
os.environ.setdefault('ADMIN_2FA_REQUIRED', 'false')   # enforced in test_admin_console.py
