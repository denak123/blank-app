import os
import pandas as pd
from sqlalchemy import create_engine, Column, String, Float, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# =================================================================
# TEMPORARY WORKAROUND - DELETE BEFORE COMMITTING TO GIT!
# Replace with your actual Supabase credentials
SUPABASE_URL = "postgresql://postgres.nbyxzrsvfqoumgrcysvn:Acc010171!@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"
DATABASE_URL = f"{SUPABASE_URL}?sslmode=require"  # Enforce SSL
# =================================================================

# Initialize database
engine = create_engine(DATABASE_URL)
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
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def get_db():
    Session = sessionmaker(bind=engine)
    return Session()

class DatabaseManager:
    def __init__(self):
        self.session = init_db()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
    
    def get_all_products(self):
        return [product.to_dict() for product in self.session.query(Product).all()]
    
    def add_product(self, product_data):
        try:
            product = Product(**product_data)
            self.session.add(product)
            self.session.commit()
            return True, "Product added successfully"
        except Exception as e:
            self.session.rollback()
            return False, f"Error adding product: {str(e)}"
    
    def update_product(self, product_code, product_data):
        try:
            product = self.session.query(Product).filter_by(product_code=product_code).first()
            if product:
                for key, value in product_data.items():
                    setattr(product, key, value)
                self.session.commit()
                return True, "Product updated successfully"
            return False, "Product not found"
        except Exception as e:
            self.session.rollback()
            return False, f"Error updating product: {str(e)}"
    
    def delete_product(self, product_code):
        try:
            product = self.session.query(Product).filter_by(product_code=product_code).first()
            if product:
                self.session.delete(product)
                self.session.commit()
                return True, "Product deleted successfully"
            return False, "Product not found"
        except Exception as e:
            self.session.rollback()
            return False, f"Error deleting product: {str(e)}"
    
    def import_catalog(self, df):
        try:
            products_data = df.to_dict('records')
            batch_size = 500
            for i in range(0, len(products_data), batch_size):
                batch = products_data[i:i + batch_size]
                for product_data in batch:
                    product_data['unit_cost'] = float(product_data['unit_cost'])
                    if 'discount' in product_data:
                        product_data['discount'] = float(product_data['discount'])
                    existing = self.session.query(Product).filter_by(
                        product_code=product_data['product_code']
                    ).first()
                    
                    if existing:
                        for key, value in product_data.items():
                            setattr(existing, key, value)
                    else:
                        new_product = Product(**product_data)
                        self.session.add(new_product)
                self.session.commit()
            return True, f"Successfully imported {len(products_data)} products"
        except Exception as e:
            self.session.rollback()
            return False, f"Error importing catalog: {str(e)}"

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Temporary database setup complete. REMOVE HARDCODED CREDENTIALS BEFORE COMMITTING!")