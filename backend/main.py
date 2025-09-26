from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging
from database import Neo4jService
from models import PlantResponse, PlantUpdate
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
neo4j_service: Optional[Neo4jService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    logger.info("Starting up the application...")
    global neo4j_service
    neo4j_service = Neo4jService(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    
    try:
        neo4j_service.test_connection()
        logger.info("Successfully connected to Neo4j database")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j database: {e}")
        raise
    yield
    
    logger.info("Shutting down the application...")
    if neo4j_service:
        neo4j_service.close()

app = FastAPI(
    title="Weed Management Knowledge Graph API",
    description="API for interacting with plant/weed management knowledge graph",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:57375"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount static files for serving plant images
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {"message": "Weed Management Knowledge Graph API is running"}

@app.get("/plant/{scientific_name}", response_model=PlantResponse, tags=["Plants"])
async def get_plant(scientific_name: str) -> PlantResponse:
    """
    Retrieve all information for a specific plant including:
    - General properties
    - Traits
    - Soil claims
    - Weeding strategies (confirmed and predicted)
    """
    try:
        logger.info(f"Retrieving information for plant: {scientific_name}")
        
        if not neo4j_service:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        # Execute comprehensive query to get all plant information
        plant_data = neo4j_service.get_plant_complete_info(scientific_name)
        
        if not plant_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Plant '{scientific_name}' not found"
            )
        
        return PlantResponse(**plant_data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving plant {scientific_name}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error while retrieving plant information"
        )

@app.put("/plant/{scientific_name}", response_model=Dict[str, str], tags=["Plants"])
async def update_plant(scientific_name: str, plant_data: PlantUpdate) -> Dict[str, str]:
    """
    Update plant information using transactions.
    Updates properties and creates/updates relationships for:
    - Traits
    - Soil claims  
    - Weeding strategies
    """
    try:
        logger.info(f"Updating plant: {scientific_name}")
        
        if not neo4j_service:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        # Use transaction to update plant information
        success = neo4j_service.update_plant_complete_info(scientific_name, plant_data.dict())
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to update plant '{scientific_name}'"
            )
        
        return {"message": f"Plant '{scientific_name}' updated successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating plant {scientific_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while updating plant information"
        )

@app.get("/plants/search", response_model=List[str], tags=["Plants"])
async def search_plants(
    search_term: str = Query(..., description="Search term for plant names")
) -> List[str]:
    """
    Search for plants by name and return matching plant names.
    """
    try:
        logger.info(f"Searching for plants with term: {search_term}")
        
        if len(search_term.strip()) < 2:
            raise HTTPException(
                status_code=400,
                detail="Search term must be at least 2 characters long"
            )
        
        if not neo4j_service:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        # Get matching plant names
        scientificNames = neo4j_service.search_plants(search_term)
        
        return scientificNames
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching plants with term '{search_term}': {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while searching plants"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)