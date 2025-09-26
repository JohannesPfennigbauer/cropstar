from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Trait(BaseModel):
    """Model for plant traits"""
    plant_trait_name: str
    plant_trait_value: Optional[str] = None

class SoilClaim(BaseModel):
    """Model for soil requirements/claims"""
    soil_property: str
    soil_condition: Optional[str] = None

class WeedingStrategy(BaseModel):
    """Model for weeding strategies"""
    type: str  # e.g., "mechanical", "chemical", "biological"
    strategy_name: str
    german_name: Optional[str] = None
    confidence: Optional[float] = 0
    relationshipType: Optional[str] = None

class PlantProperties(BaseModel):
    """Model for general plant properties"""
    common_name: Optional[str] = None
    german_name: Optional[str] = None
    family: Optional[str] = None
    genus: Optional[str] = None
    # crop: bool = False # True if the plant can be cultivated a crop, False otherwise

class PlantResponse(BaseModel):
    """Complete plant information response model"""
    scientific_name: str
    properties: PlantProperties
    traits: List[Trait] = Field(default_factory=list)
    soil_claims: List[SoilClaim] = Field(default_factory=list)
    weeding_strategies: List[WeedingStrategy] = Field(default_factory=list)

class PlantUpdate(BaseModel):
    """Model for updating plant information"""
    properties: Optional[PlantProperties] = None
    traits: Optional[List[Trait]] = None
    soil_claims: Optional[List[SoilClaim]] = None
    weeding_strategies: Optional[List[WeedingStrategy]] = None

class SearchResult(BaseModel):
    """Model for search results"""
    scientific_names: List[str]
    total_count: int

class ErrorResponse(BaseModel):
    """Model for error responses"""
    detail: str
    error_code: Optional[str] = None