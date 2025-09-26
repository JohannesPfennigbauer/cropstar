# Weed Management Knowledge Graph System

A comprehensive system for biological agriculture weed management using knowledge graphs, prediction models, and an intuitive web interface.

## 🌱 Project Overview

### **Motivation** 
Effective weed management is crucial in biological agriculture to maintain crop yields without chemical herbicides. Various suppression techniques—such as cover cropping and mechanical removal—are known to reduce weed pressure. However, understanding which techniques are effective for specific conditions requires structured knowledge representation.

### **Problem** 
Biological weed suppression depends on multiple factors from the environment and farm management. The challenge is to build a structured representation of these relationships and enable querying to suggest possible weed management techniques based on available knowledge.

### **Solution** 
This project constructs a Knowledge Graph (KG) that links weed species, crop types, soil conditions, and suppression techniques. The system uses Knowledge Graph Embeddings (KGE) for link prediction, allowing it to infer additional suppression strategies based on known patterns and provide data-driven recommendations.

### **Scope**
The project focuses on a manageable subset of weed species and suppression techniques, structuring existing agricultural knowledge and applying link prediction to suggest additional relationships. The system provides a functional foundation for querying and generating data-driven weed management recommendations.
In the future I plan to extend this KG to a fully functioning farm management system, covering the entire agricultural production process including task recommendations.


## 🏗️ System Architecture
The system consists of three main components:

### **Backend** (FastAPI + Neo4j)
- RESTful API for plant data management
- Neo4j graph database with relationship modeling
- Predictions using Graph Data Science library
- **📁 For detailed setup instructions, see: [`backend/README.md`](backend/README.md)**

### **Frontend** (Flutter Web App)
- Interactive plant detail screens with editing capabilities
- Real-time data synchronization with backend
- **📁 For detailed setup instructions, see: [`frontend/weedjournal/README.md`](frontend/weedjournal/README.md)**

### **Data & Knowledge**
- Structured plant/weed information from agricultural research and guidelines
  - Currently *not* provided within this repository. I am working on this.
- Jupyter notebooks for knowledge graph creation and evolution
- Relationship prediction using KGE and similarity algorithms


## 📝 Development Status
- ✅ Backend API with Neo4j integration
- ✅ Knowledge graph creation and evolution
- ✅ Link prediction with KGEs
- ✅ Flutter web interface with full CRUD operations
- ✅ Image integration and static file serving
- ☑️ Responsive UI with advanced layouts and graphics
- ☑️ KG Enhancement covering agricultural production process
- ☑️ Interface for entering observations and tasks.
- ☑️ GNN for recommendation of tasks and treatments


## 🤝 Contributing & Contact
If you're interested in contributing to this project or would like to collaborate on extending the knowledge graph system, please feel free to contact me! I welcome contributions, suggestions, and discussions about digital agriculture, knowledge graphs, or machine learning applications in farming.