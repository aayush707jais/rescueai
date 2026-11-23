# RESCUE-AI: Autonomous Multi-Agency Emergency Response Coordination

An autonomous, non-LLM multi-agent system designed for intelligent emergency response coordination in road traffic accident scenarios.

---

## 🚑 Multi-Agency Ecosystem & Roles

```text
       [ 📝 Citizen Incident Report (form.py) ]
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
    ┌──────────────────────┼──────────────────────┐
    ▼                      ▼                      ▼
[ 🎛️ Command Center ]  [ 🚑 Ambulance MDT ]   [ 🏥 Hospital ER ]
 (dashboard.py)       (ambulance_portal.py)  (hospital_portal.py)
    │                      │                      │
    └──────────────────────┼──────────────────────┘
                           ▼
               [ 🚓 Police & 🚒 Fire Squads ]
             (police_portal.py / fire_portal.py)
```

---

## 🌟 Interactive Portals

| Role / Agency | File | Description & Capabilities |
| :--- | :--- | :--- |
| **Master Integration Entrypoint** | `integration.py` | **THE SINGLE MAIN FILE**: Running this launches the entire ecosystem. Provides role switching and a 1-click button to spawn all 6 agency terminals in independent browser windows. Connects YOLO vision analysis with automated dispatch. |
| **Citizen Incident Form** | `form.py` | Public accident reporting with GPS coordinates, map selection, casualty inputs, and photo upload. |
| **Command Center Admin** | `dashboard.py` | Central dispatch operating picture. Displays all agency units, road blockages, response plans, and event triggers. |
| **Ambulance Mobile Terminal** | `ambulance_portal.py` | Turn-by-turn navigation map (Ambulance $\to$ Scene $\to$ Hospital), mission progression, and emergency **"Unable to Reach / Mechanical Breakdown"** trigger that auto-reassigns a replacement ambulance. |
| **Hospital Emergency Dept** | `hospital_portal.py` | Live inbound casualty triage, emergency bed capacity management, and **"Declare Full / Divert"** trigger. |
| **Police Dispatch Terminal** | `police_portal.py` | Perimeter security, accident dispatch alerts, and **Road Blockage / Clearing** controls that recalculate ambulance detours. |
| **Fire & Rescue Squad** | `fire_portal.py` | Technical rescue dispatch for heavy vehicular extrication, hydraulic cutting, and hazardous fuel spill containment. |

---

## 🧠 Core Innovations

1. **Lightweight Trained ML Decision Model (Non-LLM)**:
   - Uses a **RandomForestClassifier** for priority classification (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) and a **RandomForestRegressor** for optimal ambulance dispatch count.
   - 15-dimensional state feature vector encoding casualty counts, severity, vehicle readiness, and hospital capacities/ETAs.
   - Deterministic rule-based fallback mode if model files are absent.
2. **Event-Driven Replanning Controller**:
   - `EVENT_DEPENDENCY_MAP` isolates and re-runs only affected agents upon environmental events (`AMBULANCE_UNAVAILABLE`, `ROAD_BLOCKED`, `HOSPITAL_FULL`, `CASUALTIES_INCREASED`).
   - Produces versioned, auditable `ResponsePlan` objects with diff tracking.
3. **Synchronized Multi-Agency State Manager (`src/rescue_ai/state_manager.py`)**:
   - Thread-safe JSON persistence coordinating ambulances, hospitals, police, fire, road blockages, and notifications across concurrent sessions.

---

## 📁 Repository Structure

```text
├── src/rescue_ai/
│   ├── coordinator_agent.py       # ML Coordinator Decision Agent (Random Forest / Fallback)
│   ├── replanning_controller.py   # Event-driven Replanning Controller & ResponsePlan
│   ├── resource_search_agent.py   # Ambulance & Hospital discovery and ranking
│   ├── route_agent.py             # Dijkstra shortest path & dynamic blockage routing
│   ├── state_manager.py           # Shared real-time state synchronizer
│   ├── synthetic_map.py           # 6-node road network graph
│   └── api.py                     # FastAPI REST API endpoints
├── training/
│   ├── generate_dataset.py        # Generates 5,000 synthetic emergency scenarios
│   ├── train_coordinator.py       # Fits & exports Random Forest decision models
│   └── trained_model/             # Saved joblib models (priority_model.joblib, dispatch_model.joblib)
├── tests/
│   ├── test_agents.py             # Route & resource agent tests
│   ├── test_api.py                # FastAPI endpoint tests
│   ├── test_coordinator.py       # Coordinator, replanner, and pipeline tests
│   └── test_portals_and_state.py  # State manager & multi-agency sync tests
├── app.py                         # Master multi-agency unified portal launcher
├── dashboard.py                   # Command Center Admin dashboard
├── ambulance_portal.py            # Ambulance mobile data terminal
├── hospital_portal.py             # Hospital emergency department portal
├── police_portal.py               # Police traffic & perimeter portal
├── fire_portal.py                 # Fire & rescue extrication portal
├── form.py                        # Public accident reporting form
└── main_pipeline.py               # End-to-end execution pipeline & CLI demo
```

---

## 🚀 Quickstart Guide

### 1. Launch the Complete System (Single Main File)

Run `integration.py` to automatically launch the full integrated ecosystem:

```bash
streamlit run integration.py
# Or launch directly with python:
python integration.py
```

Inside `integration.py`:
- Use the sidebar to switch instantly between all operational roles (**Command Center**, **Ambulance MDT**, **Hospital ER**, **Police**, **Fire & Rescue**, and **Citizen AI Vision Form**).
- Or click **"🚀 Open All Portals in Separate Windows"** to automatically spawn all 6 agency terminals on individual ports (`8501`-`8506`) and open them in separate browser tabs!

You can also spawn all 6 independent browser windows directly from the command line:
```bash
python integration.py --launch-all
```

### 2. Running Portals as Independent Standalone Terminals

Each agency portal can also run as its own dedicated web interface on distinct monitors or browser tabs:

```bash
# Terminal 1: Command Center Admin
streamlit run dashboard.py --server.port 8501

# Terminal 2: Ambulance Mobile Terminal
streamlit run ambulance_portal.py --server.port 8502

# Terminal 3: Hospital Emergency Department
streamlit run hospital_portal.py --server.port 8503

# Terminal 4: Police Dispatch Terminal
streamlit run police_portal.py --server.port 8504

# Terminal 5: Fire & Rescue Squad
streamlit run fire_portal.py --server.port 8505

# Terminal 6: Citizen Incident Reporting Form
streamlit run form.py --server.port 8506
```

### 3. Run the Full Test Suite

Run all 21 unit and integration tests:
```bash
python -m pytest tests/ -v
```
