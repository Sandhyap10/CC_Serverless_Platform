from sqlalchemy import Column, String, Integer, create_engine
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class FunctionModel(Base):
    __tablename__ = 'functions'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    route = Column(String, nullable=False)
    language = Column(String, nullable=False)
    timeout = Column(Integer, nullable=False)

