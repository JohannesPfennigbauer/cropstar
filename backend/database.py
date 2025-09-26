from neo4j import GraphDatabase, Driver
from typing import Dict, Any, List, Optional
import logging
from config import NEO4J_DATABASE

logger = logging.getLogger(__name__)

class Neo4jService:
    """Service class for Neo4j database operations"""
    
    def __init__(self, uri: str, username: str, password: str):
        """Initialize Neo4j driver"""
        self.driver: Driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = NEO4J_DATABASE
    
    def close(self):
        """Close the driver connection"""
        if self.driver:
            self.driver.close()
    
    def test_connection(self) -> bool:
        """Test the database connection"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                return record is not None and record["test"] == 1
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise
    
    def get_plant_complete_info(self, scientific_name: str) -> Optional[Dict[str, Any]]:
        """
        Get complete information for a plant including properties, traits, 
        soil claims, and weeding strategies
        """
        query = """
        MATCH (p:Plant {scientificName: $scientific_name})
        OPTIONAL MATCH (p)-[:hasTrait]->(ptv:PlantTraitValue)-[:isInstanceOf]->(pt:PlantTrait)
        OPTIONAL MATCH (p)-[:prefers]->(sc:SoilCondition)-[:isInstanceOf]->(sp:SoilProperty)
        OPTIONAL MATCH (ws:WeedingStrategy)-[ie:isEffectiveAgainst|predictedEffectiveAgainst]->(p)
        
        RETURN 
        p AS plant,
        collect(DISTINCT {plant_trait_name: pt.name, plant_trait_value: toString(ptv.valueName)}) AS traits,
        collect(DISTINCT {soil_condition: sc.name, soil_property: sp.name}) AS soil_claims,
        collect(DISTINCT {strategy_name: ws.name, german_name: ws.germanName, type: ws.type, 
                confidence: COALESCE(ie.confidence, 0.0), relationship_type: type(ie)}) AS weeding_strategies
        """
     
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, scientific_name=scientific_name)
                record = result.single()
                
                if not record or not record["plant"]:
                    return None
                
                plant = record["plant"]
                traits = [t for t in record["traits"] if t.get("plant_trait_name") is not None]
                soil_claims = [s for s in record["soil_claims"] if s.get("soil_condition") is not None]
                weeding_strategies = [s for s in record["weeding_strategies"] if s.get("strategy_name") is not None]
                
                return {
                    "scientific_name": scientific_name,
                    "properties": {
                        "common_name": plant.get("commonName"),
                        "german_name": plant.get("germanName"),
                        "family": plant.get("family"),
                        "genus": plant.get("genus")
                    },
                    "traits": traits,
                    "soil_claims": soil_claims,
                    "weeding_strategies": weeding_strategies
                }
        
        except Exception as e:
            logger.error(f"Error retrieving plant {scientific_name}: {e}")
            raise
    
    def update_plant_complete_info(self, scientific_name: str, plant_data: Dict[str, Any]) -> bool:
        """
        Update complete plant information using transactions
        """
        def update_transaction(tx, scientific_name: str, data: Dict[str, Any]):
            # Update plant properties
            if "properties" in data and data["properties"]:
                property_updates = data.get('properties', {})
                filtered_updates = {k: v for k, v in property_updates.items() if v is not None}
                if filtered_updates:
                    tx.run("MATCH (p:Plant {scientificName: $name}) SET p += $updates", 
                           name=scientific_name, updates=filtered_updates)
            
            # Update traits
            if "traits" in data:
                tx.run("""
                    MATCH (p:Plant {scientificName: $name})-[r:hasTrait]->(:PlantTraitValue)
                    DELETE r
                """, name=scientific_name)
                
                traits_updates = data.get('traits', [])
                for trait in traits_updates:
                    if trait.get('plant_trait_name') and trait.get('plant_trait_value'):
                        plant_trait_value = str(trait['plant_trait_value'])
                        tx.run("""
                            MATCH (p:Plant {scientificName: $name})
                            MERGE (tv:PlantTraitValue {valueName: $plant_trait_value})
                            MERGE (t:PlantTrait {name: $plant_trait_name})
                            MERGE (p)-[:hasTrait]->(tv)
                            MERGE (tv)-[:isInstanceOf]->(t)
                        """, name=scientific_name, plant_trait_value=plant_trait_value, plant_trait_name=trait['plant_trait_name'])
            
            # Update soil claims
            if "soil_claims" in data:
                tx.run("""
                    MATCH (p:Plant {scientificName: $name})-[r:prefers]->(:SoilCondition)
                    DELETE r
                """, name=scientific_name)
                
                soil_claims_updates = data.get('soil_claims', [])
                for soil_claim in soil_claims_updates:
                    if soil_claim.get('soil_condition') and soil_claim.get('soil_property'):
                        tx.run("""
                            MATCH (p:Plant {scientificName: $name})
                            MERGE (sc:SoilCondition {name: $soil_condition})
                            MERGE (sp:SoilProperty {name: $soil_property})
                            MERGE (p)-[:prefers]->(sc)
                            MERGE (sc)-[:isInstanceOf]->(sp)
                        """, name=scientific_name, soil_condition=soil_claim['soil_condition'], soil_property=soil_claim['soil_property'])
            
            # Update weeding strategies
            if "weeding_strategies" in data:
                tx.run("""
                    MATCH (:WeedingStrategy)-[r:isEffectiveAgainst|predictedEffectiveAgainst]->(p:Plant {scientificName: $name})
                    DELETE r
                """, name=scientific_name)
                
                strategies_updates = data.get('weeding_strategies', [])
                for strategy in strategies_updates:
                    if strategy.get('strategy_name'):
                        relationship_type = "predictedEffectiveAgainst" if strategy.get('confidence', 0) < 1.0 else "isEffectiveAgainst"
                        
                        tx.run(f"""
                            MATCH (p:Plant {{scientificName: $name}})
                            MERGE (ws:WeedingStrategy {{name: $strategy_name}})
                            MERGE (ws)-[r:{relationship_type}]->(p)
                            SET ws.germanName = $german_name, 
                                ws.type = $type,
                                r.confidence = $confidence
                        """, name=scientific_name, 
                             strategy_name=strategy['strategy_name'], 
                             german_name=strategy.get('german_name'), 
                             type=strategy.get('type'),
                             confidence=strategy.get('confidence'))
        
        try:
            with self.driver.session(database=self.database) as session:
                session.execute_write(update_transaction, scientific_name, plant_data)
                return True
        
        except Exception as e:
            logger.error(f"Error updating plant {scientific_name}: {e}")
            return False
    
    def search_plants(self, search_term: str) -> List[str]:
        """
        Search for plant names that match the search term
        """
        query = """
        MATCH (p:Plant)
        WHERE toLower(p.scientificName) CONTAINS toLower($search_term)
           OR toLower(p.commonName) CONTAINS toLower($search_term)
           OR toLower(p.germanName) CONTAINS toLower($search_term)
        RETURN DISTINCT p.scientificName as scientific_name
        ORDER BY p.scientificName
        LIMIT 50
        """
        # if working wiht lists: OR ANY(common_name IN p.common_names WHERE common_name CONTAINS $search_term)
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, search_term=search_term)
                return [record["scientific_name"] for record in result if record["scientific_name"]]
        
        except Exception as e:
            logger.error(f"Error searching plants with term '{search_term}': {e}")
            raise