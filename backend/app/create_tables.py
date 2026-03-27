from backend.app.database import Base, engine
from backend.app.models.job import Job

Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
