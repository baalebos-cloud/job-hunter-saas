"""Initialize isolated test settings before any module imports Settings."""
import os

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['SECRET_KEY'] = 'test-key-only-not-for-production'
