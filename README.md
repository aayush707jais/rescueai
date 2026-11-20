# RESCUE-AI: Autonomous Emergency Response Coordination

An autonomous, non-LLM multi-agent system designed for intelligent emergency response coordination in road traffic accident scenarios.

---

## 🚑 System Architecture Overview

```text
       [ User Incident Report / Vision Detection ]
                           │
                           ▼
          [ Severity & Resource Demand Agent ]
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
   [ Resource Search Agent ]     [ Route Agent ]
   (Ambulance & Hospital pools)  (Dijkstra shortest path)
              │                         │
              └────────────┬────────────┘
                           ▼
              [ Coordinator Decision Agent ]
          (Trained Lightweight ML Random Forest)
                           │
                           ▼
                    [ Response Plan ]
                           │
                           ▼
             [ Event Replanning Controller ]
          (Dynamic response to breakdowns & blockages)
                           │
                           ▼
               [ Streamlit Command Center ]
```

---

## 🧠 Core Innovations

1. **Lightweight Trained ML Decision Model (Non-LLM)**:
   - Uses a **RandomForestClassifier** for priority classification (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) and a **RandomForestRegressor** for optimal ambulance dispatch count.
   - 15-dimensional state feature vector encoding casualty counts, severity, vehicle readiness, and hospital capacities/ETAs.
   - Deterministic rule-based fallback mode if model files are absent.
2. **Event-Driven Replanning Controller**:
   - `EVENT_DEPENDENCY_MAP` isolates and re-runs only affected agents upon environmental events (e.g. `AMBULANCE_UNAVAILABLE`, `ROAD_BLOCKED`, `HOSPITAL_FULL`, `CASUALTIES_INCREASED`).
   - Produces versioned, auditable `ResponsePlan` objects with diff tracking.
3. **Integrated Simulation Command Center**:
   - Folium-based map rendering nodes (A–F), ambulance positions, hospital status, and live route paths.
   - Interactive triggers for dynamic events and real-time replanning visualization.

---

## 📁 Repository Structure

```text
├── src/rescue_ai/
│   ├── coordinator_agent.py       # ML Coordinator Decision Agent (Random Forest / Fallback)
│   ├── replanning_controller.py   # Event-driven Replanning Controller & ResponsePlan
│   ├── resource_search_agent.py   # Ambulance & Hospital discovery and ranking
│   ├── route_agent.py             # Shortest path & travel time calculation (NetworkX)
│   ├── synthetic_map.py           # 6-node road network graph
│   └── api.py                     # FastAPI REST API endpoints
├── training/
│   ├── generate_dataset.py        # Generates 5,000 synthetic emergency scenarios
│   ├── train_coordinator.py       # Fits & exports Random Forest decision models
│   └── trained_model/             # Saved joblib models (priority_model.joblib, dispatch_model.joblib)
├── tests/
│   ├── test_agents.py             # Route & resource agent tests
│   ├── test_api.py                # FastAPI endpoint tests
│   └── test_coordinator.py       # Coordinator, replanner, and end-to-end pipeline tests
├── main_pipeline.py               # End-to-end execution pipeline & CLI demo
├── dashboard.py                   # Streamlit Command Center UI
└── README.md
```

---

## 🚀 Quickstart Guide

### 1. Environment Setup

Activate your virtual environment and install dependencies:
```bash
python -m pip install -r requirements.txt
# Or directly install core libraries:
python -m pip install scikit-learn joblib numpy networkx fastapi uvicorn streamlit folium streamlit-folium pytest httpx
```

### 2. Generate Dataset & Train Coordinator

To regenerate the 5,000-scenario dataset and retrain the ML coordinator:
```bash
# 1. Generate synthetic dataset (5000 scenarios)
python -m training.generate_dataset

# 2. Train and evaluate the models
python -m training.train_coordinator
```

### 3. Run End-to-End Pipeline Demo

Execute the complete multi-agent pipeline from incident processing to dynamic replanning:
```bash
python main_pipeline.py

# Or output full JSON response:
python main_pipeline.py --json
```

### 4. Run the Streamlit Dashboard

Launch the interactive emergency response command center:
```bash
streamlit run dashboard.py
```

### 5. Run the Test Suite

Run all unit and integration tests:
```bash
python -m pytest tests/ -v
```
