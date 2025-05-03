from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import config # Import config for default values

class RecommendationRequest(BaseModel):
    user_id: str
    context_city: str
    context_day_period: str
    context_category: str
    top_n: int = config.DEFAULT_TOP_N
    w_knn: float = config.DEFAULT_W_KNN
    w_svd: float = config.DEFAULT_W_SVD
    w_context: float = config.DEFAULT_W_CONTEXT

class RecommendationResponse(BaseModel):
    recommendations: List[Dict[str, Any]]
    model_info: Dict[str, Any]

class UserProfile(BaseModel):
    user_id: str
    profile: Dict[str, Any]
    ratings: List[Dict[str, Any]]

class Contexts(BaseModel):
    cities: List[str]
    day_periods: List[str]
    categories: List[str]

class RetrainResponse(BaseModel):
    status: str
    message: str

class HealthResponse(BaseModel):
    status: str
    message: str

class QuickRecommendationItem(BaseModel):
    business_id: str
    name: Optional[str] = None
    address: Optional[str] = None
    categories: Optional[str] = None
    stars: Optional[float] = None # Overall stars from business table
    final_score: float
    score_knn: Optional[float] = None
    score_svd: Optional[float] = None
    score_context: Optional[float] = None

class QuickRecommendationResponse(BaseModel):
    recommendations: List[QuickRecommendationItem]