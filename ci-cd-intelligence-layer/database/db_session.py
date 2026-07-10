import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .schema import Base, UserAccount
from coded_tools.migration_intelligence._paths import database_path

# Define local sqlite database path (dynamic — DATABASE_URL overrides)
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{database_path()}"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = scoped_session(session_factory)

def init_db():
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Pre-populate default users for the demo/stakeholders if empty
    session = SessionLocal()
    try:
        user_count = session.query(UserAccount).count()
        if user_count == 0:
            # Add stakeholder
            stakeholder = UserAccount(
                user_id="stakeholder-123",
                name="Sanjana Mohanty",
                role="stakeholder",
                email="sanjanamohanty@cognizant.com"
            )
            # Add approver
            approver = UserAccount(
                user_id="approver-456",
                name="IT Infrastructure Director",
                role="approver",
                email="infra-director@cognizant.com"
            )
            session.add_all([stakeholder, approver])
            session.commit()
            print("Default UserAccounts pre-populated.")
    except Exception as e:
        session.rollback()
        print(f"Error initializing default data: {e}")
    finally:
        session.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
