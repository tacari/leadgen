
import numpy as np
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
import joblib
import os
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LeadScoringModel:
    def __init__(self):
        self.model_path = 'models/lead_scoring_model.pkl'
        self.pipeline = None
        self.logger = logging.getLogger(__name__)
        
        # Create models directory if it doesn't exist
        os.makedirs('models', exist_ok=True)
        
        # Load existing model if available
        if os.path.exists(self.model_path):
            try:
                self.pipeline = joblib.load(self.model_path)
                self.logger.info("Loaded existing lead scoring model")
            except Exception as e:
                self.logger.error(f"Error loading model: {str(e)}")
                self.pipeline = None
    
    def preprocess_lead_data(self, leads):
        """Convert lead data to features for model training/prediction"""
        features = []
        
        for lead in leads:
            # Extract numeric and categorical features
            feature_vector = [
                1 if lead.get('verified', False) else 0,
                1 if lead.get('phone_verified', False) else 0,
                1 if lead.get('linkedin_verified', False) else 0,
                self._get_source_score(lead.get('source', '')),
                1 if lead.get('website') else 0,
                1 if '@' in lead.get('email', '') and not any(
                    provider in lead.get('email', '').lower() 
                    for provider in ['gmail', 'yahoo', 'hotmail', 'outlook']) else 0,
                len(lead.get('description', '')) / 1000 if lead.get('description') else 0,
                lead.get('rating', 0) / 5 if lead.get('rating') else 0,
                1 if lead.get('competitor_source') else 0
            ]
            features.append(feature_vector)
            
        return np.array(features)
    
    def _get_source_score(self, source):
        """Convert source to numeric score"""
        source_scores = {
            'linkedin': 0.9,
            'google maps': 0.8,
            'yellow pages': 0.6,
            'facebook': 0.7,
            'instagram': 0.65,
            'twitter': 0.5,
            'competitor': 0.85
        }
        
        source = source.lower()
        for key, score in source_scores.items():
            if key in source:
                return score
        return 0.4  # Default score for unknown sources
    
    def train(self, leads, labels):
        """Train the lead scoring model
        
        Args:
            leads (list): List of lead dictionaries
            labels (list): List of scores or conversion outcomes (1 for converted, 0 for not)
        """
        try:
            # Extract features
            features = self.preprocess_lead_data(leads)
            
            # Train-test split
            X_train, X_test, y_train, y_test = train_test_split(
                features, labels, test_size=0.2, random_state=42
            )
            
            # Create pipeline with preprocessing and model
            self.pipeline = Pipeline([
                ('scaler', StandardScaler()),
                ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
            ])
            
            # Train model
            self.pipeline.fit(X_train, y_train)
            
            # Evaluate
            accuracy = self.pipeline.score(X_test, y_test)
            self.logger.info(f"Model training complete. Test accuracy: {accuracy:.2f}")
            
            # Save model
            joblib.dump(self.pipeline, self.model_path)
            self.logger.info(f"Model saved to {self.model_path}")
            
            return accuracy
            
        except Exception as e:
            self.logger.error(f"Error training model: {str(e)}")
            return 0
    
    def predict(self, leads):
        """Predict lead scores using ML model
        
        Args:
            leads (list): List of lead dictionaries
            
        Returns:
            list: Predicted scores between 0-100
        """
        try:
            if not self.pipeline:
                self.logger.warning("No model available. Using fallback scoring method.")
                return [self._fallback_score(lead) for lead in leads]
            
            # Extract features
            features = self.preprocess_lead_data(leads)
            
            # Get prediction probabilities (confidence that lead will convert)
            probabilities = self.pipeline.predict_proba(features)[:, 1]
            
            # Convert to 0-100 scale
            scores = [int(p * 100) for p in probabilities]
            
            return scores
            
        except Exception as e:
            self.logger.error(f"Error predicting scores: {str(e)}")
            return [self._fallback_score(lead) for lead in leads]
    
    def _fallback_score(self, lead):
        """Calculate lead score using rule-based method when ML model fails"""
        score = 50  # Base score
        
        # Source quality
        source = lead.get('source', '').lower()
        source_scores = {
            'linkedin': 20,
            'google maps': 15,
            'yellow pages': 10,
            'facebook': 8, 
            'instagram': 7,
            'competitor': 15
        }
        
        for src, points in source_scores.items():
            if src in source:
                score += points
                break
        
        # Verification flags
        if lead.get('verified', False):
            score += 10
        if lead.get('phone_verified', False):
            score += 10
        if lead.get('linkedin_verified', False):
            score += 10
        
        # Other factors
        if lead.get('website'):
            score += 5
        if lead.get('competitor_source'):
            score += 10
        
        return min(100, score)

    def train_from_database(self, conn):
        """Train model using leads from database
        
        Args:
            conn: Database connection
        """
        try:
            # Get leads that have status information
            query = """
                SELECT l.*, CASE WHEN l.status IN ('Converted', 'Closed Won') THEN 1 ELSE 0 END as converted
                FROM leads l
                WHERE l.status IS NOT NULL
            """
            
            df = pd.read_sql(query, conn)
            
            if len(df) < 50:
                self.logger.warning(f"Only {len(df)} labeled leads available. Need at least 50 for training.")
                return False
            
            # Convert to list of dicts for preprocessing
            leads = df.to_dict('records')
            labels = df['converted'].values
            
            # Train model
            accuracy = self.train(leads, labels)
            return accuracy > 0
            
        except Exception as e:
            self.logger.error(f"Error training from database: {str(e)}")
            return False
    
    def get_feature_importance(self):
        """Get feature importance from model"""
        if not self.pipeline or not hasattr(self.pipeline['classifier'], 'feature_importances_'):
            return {}
        
        feature_names = [
            'Email Verified', 'Phone Verified', 'LinkedIn Verified', 
            'Source Quality', 'Has Website', 'Company Email',
            'Description Length', 'Rating', 'From Competitor'
        ]
        
        importances = self.pipeline['classifier'].feature_importances_
        return dict(zip(feature_names, importances))

# Singleton instance
lead_model = LeadScoringModel()
