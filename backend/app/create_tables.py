from backend.app.database import Base, engine
from backend.app.models.user import User
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.app.models.application import Application

Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
