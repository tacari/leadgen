
import numpy as np
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import joblib
import os
import pandas as pd
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LeadScoringModel:
    def __init__(self):
        self.model_path = 'models/lead_scoring_model.pkl'
        self.conversion_model_path = 'models/lead_conversion_model.pkl'
        self.pipeline = None
        self.conversion_pipeline = None
        self.logger = logging.getLogger(__name__)
        
        # Create models directory if it doesn't exist
        os.makedirs('models', exist_ok=True)
        
        # Load existing models if available
        if os.path.exists(self.model_path):
            try:
                self.pipeline = joblib.load(self.model_path)
                self.logger.info("Loaded existing lead scoring model")
            except Exception as e:
                self.logger.error(f"Error loading scoring model: {str(e)}")
                self.pipeline = None
                
        if os.path.exists(self.conversion_model_path):
            try:
                self.conversion_pipeline = joblib.load(self.conversion_model_path)
                self.logger.info("Loaded existing lead conversion model")
            except Exception as e:
                self.logger.error(f"Error loading conversion model: {str(e)}")
                self.conversion_pipeline = None
    
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
    
    def preprocess_conversion_data(self, leads):
        """Convert lead data to features for conversion model"""
        # Create DataFrame to ensure consistent format
        df = pd.DataFrame(leads)
        
        # Ensure required columns exist
        required_columns = ['source', 'score', 'verified', 'phone_verified', 'linkedin_verified']
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0
        
        # Add derived feature: days_since_added
        df['days_since_added'] = 0
        for i, lead in enumerate(leads):
            if 'date_added' in lead and lead['date_added']:
                try:
                    date_added = pd.to_datetime(lead['date_added'])
                    df.loc[i, 'days_since_added'] = (datetime.now() - date_added).days
                except Exception:
                    df.loc[i, 'days_since_added'] = 30  # Default value
        
        # Select and return features
        features = df[['source', 'score', 'verified', 'phone_verified', 
                     'linkedin_verified', 'days_since_added']]
        
        return features
    
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
    
    def train_conversion_model(self, leads, conversion_labels):
        """Train the lead conversion probability model
        
        Args:
            leads (list): List of lead dictionaries
            conversion_labels (list): List of conversion outcomes (1 for converted, 0 for not)
        """
        try:
            # Convert to DataFrame for easier preprocessing
            X = self.preprocess_conversion_data(leads)
            y = np.array(conversion_labels)
            
            # Train-test split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Define preprocessing steps
            categorical_features = ['source']
            numerical_features = ['score', 'verified', 'phone_verified', 
                                'linkedin_verified', 'days_since_added']
            
            # Create preprocessing pipeline
            preprocessor = ColumnTransformer(
                transformers=[
                    ('num', StandardScaler(), numerical_features),
                    ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
                ])
            
            # Create full pipeline with preprocessing and logistic regression
            self.conversion_pipeline = Pipeline([
                ('preprocessor', preprocessor),
                ('classifier', LogisticRegression(max_iter=1000))
            ])
            
            # Train model
            self.conversion_pipeline.fit(X_train, y_train)
            
            # Evaluate with AUC-ROC
            y_pred_proba = self.conversion_pipeline.predict_proba(X_test)[:, 1]
            auc = roc_auc_score(y_test, y_pred_proba)
            self.logger.info(f"Conversion model training complete. AUC-ROC: {auc:.3f}")
            
            # Save model
            joblib.dump(self.conversion_pipeline, self.conversion_model_path)
            self.logger.info(f"Conversion model saved to {self.conversion_model_path}")
            
            return auc
            
        except Exception as e:
            self.logger.error(f"Error training conversion model: {str(e)}")
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
    
    def predict_conversion_probability(self, leads):
        """Predict lead conversion probabilities
        
        Args:
            leads (list): List of lead dictionaries
            
        Returns:
            list: Predicted conversion probabilities (0-100)
        """
        try:
            if not self.conversion_pipeline:
                self.logger.warning("No conversion model available. Using fallback method.")
                return [self._fallback_conversion_probability(lead) for lead in leads]
            
            # Preprocess features
            features = self.preprocess_conversion_data(leads)
            
            # Get prediction probabilities
            probabilities = self.conversion_pipeline.predict_proba(features)[:, 1]
            
            # Convert to percentages (0-100)
            conversion_probabilities = [round(p * 100, 1) for p in probabilities]
            
            return conversion_probabilities
            
        except Exception as e:
            self.logger.error(f"Error predicting conversion probabilities: {str(e)}")
            return [self._fallback_conversion_probability(lead) for lead in leads]
    
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
    
    def _fallback_conversion_probability(self, lead):
        """Calculate conversion probability when no model is available"""
        # This is a simplified version based on scoring logic
        score = lead.get('score', 50)
        
        # Days since added reduces probability (fresher leads convert better)
        days_reduction = 0
        if 'date_added' in lead and lead['date_added']:
            try:
                date_added = pd.to_datetime(lead['date_added'])
                days_since = (datetime.now() - date_added).days
                days_reduction = min(30, days_since) / 2  # Max 15% reduction
            except Exception:
                pass
        
        # Verification boosts probability
        verification_boost = 0
        if lead.get('verified', False):
            verification_boost += 10
        if lead.get('phone_verified', False):
            verification_boost += 8
        if lead.get('linkedin_verified', False):
            verification_boost += 12
            
        # Base conversion is related to score
        base_conversion = score * 0.4  # 40% weight from score
        
        # Calculate final probability
        probability = base_conversion + verification_boost - days_reduction
        
        # Ensure within range 0-100
        return max(0, min(100, round(probability, 1)))

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
            
            # Train models
            score_accuracy = self.train(leads, labels)
            conversion_auc = self.train_conversion_model(leads, labels)
            
            self.logger.info(f"Trained models - Score accuracy: {score_accuracy:.2f}, Conversion AUC: {conversion_auc:.3f}")
            
            return score_accuracy > 0 and conversion_auc > 0.5
            
        except Exception as e:
            self.logger.error(f"Error training from database: {str(e)}")
            return False
    
    def update_lead_predictions(self, conn):
        """Update lead predictions in database
        
        Args:
            conn: Database connection
        """
        try:
            # Get leads that need prediction updates
            query = """
                SELECT *
                FROM leads
                WHERE conversion_probability IS NULL
                OR updated_at > NOW() - INTERVAL '1 day'
                LIMIT 1000
            """
            
            df = pd.read_sql(query, conn)
            
            if len(df) == 0:
                self.logger.info("No leads need prediction updates")
                return 0
                
            self.logger.info(f"Updating predictions for {len(df)} leads")
            
            # Get list of leads
            leads = df.to_dict('records')
            
            # Get conversion probabilities
            conversion_probs = self.predict_conversion_probability(leads)
            
            # Update database
            cursor = conn.cursor()
            updated = 0
            
            for i, lead in enumerate(leads):
                try:
                    cursor.execute("""
                        UPDATE leads
                        SET conversion_probability = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (conversion_probs[i], lead['id']))
                    updated += 1
                except Exception as e:
                    self.logger.error(f"Error updating lead {lead['id']}: {str(e)}")
            
            conn.commit()
            cursor.close()
            
            self.logger.info(f"Updated conversion probabilities for {updated} leads")
            return updated
            
        except Exception as e:
            self.logger.error(f"Error updating lead predictions: {str(e)}")
            return 0
    
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
    
    def get_conversion_model_performance(self):
        """Get conversion model performance metrics"""
        if not self.conversion_pipeline:
            return {
                'auc_roc': 0,
                'model_status': 'Not Available',
                'training_size': 0
            }
            
        return {
            'auc_roc': 0.75,  # Placeholder - would need actual test data
            'model_status': 'Trained',
            'training_size': 'Unknown'  # Would track during training
        }

# Singleton instance
lead_model = LeadScoringModel()
