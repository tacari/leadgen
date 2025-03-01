import logging
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score
import pandas as pd
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LeadModel:
    def __init__(self):
        self.pipeline = None
        self.model_file = 'lead_model.joblib'
        self.feature_cols = ['source', 'score', 'website_visits', 'days_since_last_visit', 'industry']
        self.categorical_cols = ['source', 'industry']
        self.numerical_cols = ['score', 'website_visits', 'days_since_last_visit']

        # Try to load existing model if available
        try:
            if os.path.exists(self.model_file):
                self.pipeline = joblib.load(self.model_file)
                logger.info(f"Loaded existing model from {self.model_file}")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.pipeline = None

    def train_from_database(self, db_conn):
        """Train the model using data from the database"""
        try:
            # Fetch data from the database
            query = """
                SELECT 
                    source, 
                    score, 
                    COALESCE(website_visits, 0) as website_visits, 
                    COALESCE(days_since_last_visit, 0) as days_since_last_visit, 
                    COALESCE(industry, 'unknown') as industry, 
                    CASE WHEN status = 'converted' THEN 1 ELSE 0 END as converted 
                FROM leads
                WHERE status IS NOT NULL
            """

            df = pd.read_sql(query, db_conn)

            # Check if we have enough data
            if len(df) < 20:  # Minimum number of samples
                logger.warning(f"Not enough data to train the model: {len(df)} samples")
                return False

            # Check if we have both converted and non-converted leads
            if len(df['converted'].unique()) < 2:
                logger.warning("Need both converted and non-converted leads to train")
                return False

            X = df[self.feature_cols]
            y = df['converted']

            # Define preprocessing for categorical features
            categorical_transformer = Pipeline(steps=[
                ('onehot', OneHotEncoder(handle_unknown='ignore'))
            ])

            # Define preprocessing for numerical features
            numerical_transformer = Pipeline(steps=[
                ('scaler', StandardScaler())
            ])

            # Combine preprocessing steps
            preprocessor = ColumnTransformer(
                transformers=[
                    ('cat', categorical_transformer, self.categorical_cols),
                    ('num', numerical_transformer, self.numerical_cols)
                ])

            # Create and train the pipeline
            self.pipeline = Pipeline(steps=[
                ('preprocessor', preprocessor),
                ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
            ])

            # Split the data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            # Train the model
            self.pipeline.fit(X_train, y_train)

            # Evaluate the model
            y_pred = self.pipeline.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)

            # Try to calculate AUC if possible
            try:
                y_pred_proba = self.pipeline.predict_proba(X_test)[:, 1]
                auc = roc_auc_score(y_test, y_pred_proba)
                logger.info(f"Model trained successfully. Accuracy: {accuracy:.2f}, AUC: {auc:.2f}")
            except:
                logger.info(f"Model trained successfully. Accuracy: {accuracy:.2f}")

            # Save the model
            joblib.dump(self.pipeline, self.model_file)
            return True

        except Exception as e:
            logger.error(f"Error training model: {e}")
            return False

    def predict(self, leads):
        """Predict probability of conversion for leads"""
        if self.pipeline is None:
            logger.warning("Model not trained yet")
            return None

        try:
            # Create DataFrame from leads
            data = []
            for lead in leads:
                row = {
                    'source': lead.get('source', 'unknown'),
                    'score': lead.get('score', 50),
                    'website_visits': lead.get('website_visits', 0),
                    'days_since_last_visit': lead.get('days_since_last_visit', 0),
                    'industry': lead.get('industry', 'unknown')
                }
                data.append(row)

            if not data:
                return []

            df = pd.DataFrame(data)

            # Make prediction
            probabilities = self.pipeline.predict_proba(df)[:, 1]

            # Convert to percentage (0-100)
            return [int(p * 100) for p in probabilities]

        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return None

    def update_lead_predictions(self, db_conn):
        """Update conversion_probability for all leads in the database"""
        if self.pipeline is None:
            logger.warning("Model not trained yet")
            return 0

        try:
            # Fetch leads without conversion probability
            query = """
                SELECT 
                    id, 
                    source, 
                    score, 
                    COALESCE(website_visits, 0) as website_visits, 
                    COALESCE(days_since_last_visit, 0) as days_since_last_visit, 
                    COALESCE(industry, 'unknown') as industry
                FROM leads
                WHERE conversion_probability IS NULL
                OR conversion_probability = 0
            """

            df = pd.read_sql(query, db_conn)

            if len(df) == 0:
                return 0

            # Backup IDs
            ids = df['id'].tolist()

            # Make predictions
            X = df[self.feature_cols]
            probabilities = self.pipeline.predict_proba(X)[:, 1]

            # Update database
            cur = db_conn.cursor()
            updated_count = 0

            for i, lead_id in enumerate(ids):
                prob = int(probabilities[i] * 100)  # Convert to percentage
                cur.execute(
                    "UPDATE leads SET conversion_probability = %s WHERE id = %s",
                    (prob, lead_id)
                )
                updated_count += 1

            db_conn.commit()
            cur.close()

            logger.info(f"Updated conversion probability for {updated_count} leads")
            return updated_count

        except Exception as e:
            logger.error(f"Error updating lead predictions: {e}")
            return 0



# Create a singleton instance
lead_model = LeadModel()