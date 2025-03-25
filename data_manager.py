import pandas as pd
from database import DatabaseManager

class DataManager:
    def __init__(self):
        self.db = DatabaseManager()

    def get_manufacturers(self):
        products = self.db.get_all_products()
        return sorted(set(p['manufacturer'] for p in products))

    def get_product_types(self, manufacturer):
        products = self.db.get_all_products()
        return sorted(set(p['product_type'] for p in products if p['manufacturer'] == manufacturer))

    def get_product_descriptions(self, manufacturer, product_type):
        products = self.db.get_all_products()
        descriptions = [
            f"{p['description']} ({p['product_code']})"  # Include product code in description
            for p in products 
            if p['manufacturer'] == manufacturer and p['product_type'] == product_type
        ]
        return sorted(descriptions)

    def get_product_details_by_description(self, manufacturer, product_type, description):
        products = self.db.get_all_products()
        for product in products:
            if (product['manufacturer'] == manufacturer and 
                product['product_type'] == product_type and 
                f"{product['description']} ({product['product_code']})" == description):
                return product
        return None

    def import_catalog(self, file):   
                try:
                    # Read Excel file
                    if file.name.endswith('.xlsx'):
                        df = pd.read_excel(file)
                    else:
                        df = pd.read_csv(file)

                    # Validate column names
                    expected_columns = ['manufacturer', 'product_type', 'description', 'product_code', 'unit_cost']
                    if not all(col in df.columns for col in expected_columns):
                        return False, "File must contain columns: manufacturer, product_type, description, product_code, unit_cost"

                    # Clean and validate data
                    df = df[expected_columns + ['supplier', 'discount'] if 'supplier' in df.columns else expected_columns]

                    # Convert unit_cost to float and product_code to string
                    try:
                        df['unit_cost'] = df['unit_cost'].astype(float)
                        df['product_code'] = df['product_code'].astype(str)

                        # Handle missing or blank discount values
                        if 'discount' in df.columns:
                            df['discount'] = df['discount'].fillna(0).astype(float)  # Replace NaN with 0
                        else:
                            df['discount'] = 0.0  # Add discount column with default value 0
                    except Exception as e:
                        return False, f"Error processing data: {str(e)}"

                    # Import to database
                    return self.db.import_catalog(df)

                except Exception as e:
                    return False, f"Error importing file: {str(e)}"