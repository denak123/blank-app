import os
from sqlalchemy import create_engine, Column, String, Float, Integer, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

# Load database URL from environment variables (NEVER hardcode credentials)
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Enforce SSL for Supabase
if "pooler.supabase.com" in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

# Initialize engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    manufacturer = Column(String, nullable=False)
    product_type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    product_code = Column(String, nullable=False, unique=True)  # Added unique constraint
    unit_cost = Column(Float, nullable=False)
    supplier = Column(String, nullable=True)
    discount = Column(Float, nullable=True, default=0.0)

    def to_dict(self):
        return {
            'id': self.id,
            'manufacturer': self.manufacturer,
            'product_type': self.product_type,
            'description': self.description,
            'product_code': self.product_code,
            'unit_cost': float(self.unit_cost),
            'supplier': self.supplier,
            'discount': float(self.discount) if self.discount is not None else 0.0
        }

def init_db():
    Base.metadata.create_all(engine)  # Create tables if they don't exist

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class DatabaseManager:
    def __init__(self):
        self.session = SessionLocal()
    
    def get_all_products(self):
        products = self.session.scalars(select(Product)).all()
        return [product.to_dict() for product in products]
    
    def add_product(self, product_data):
        try:
            product = Product(**product_data)
            self.session.add(product)
            self.session.commit()
            return True, "Product added successfully"
        except Exception as e:
            self.session.rollback()
            return False, f"Error adding product: {str(e)}"
        finally:
            self.session.close()
    
    # ... (similar fixes for update_product, delete_product, etc.)