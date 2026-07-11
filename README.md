# Cartographer

**Author:** Sanjana Mohanty
**Co-Author:** Teja Sree Kuppi Reddy

Cartographer is an AI agent network, built on **Neuro-SAN**, that automates the analysis, drafting, and recommendation stage of a cloud migration — turning a migration prompt and a `project.json` manifest into a self-validated Terraform blueprint, an architecture diagram, a consolidated findings report, and a human approval workflow.

See [`summary.md`](summary.md) for the full problem statement and solution overview, and [`architecture.md`](architecture.md) for the system architecture and diagrams.

---

## 1. Prerequisites

Before setting up the project locally, make sure you have the following installed:

- **Python 3.11+**
- **pip** (or a virtual environment tool such as `venv` or `conda`)
- **Node.js 18+** and **npm** (for the dashboard SPA)
- **Docker** and **Docker Compose** (for the hackathon/local topology)
- **Terraform CLI** (used by the Lead Architect Agent for `terraform validate` / `fmt --check`)
- Access to an **NVIDIA NIM** endpoint and API key
- SMTP credentials for outbound email (or a test SMTP server such as [Mailtrap](https://mailtrap.io) / [MailHog](https://github.com/mailhog/MailHog) for local development)

## 2. Clone the Repository

```bash
git clone <your-fork-or-repo-url>
cd cartographer
```

## 3. Create and Configure the `.env` File

Create a file named `.env` in the project root and populate it with the following variables:

```bash
# --- LLM Configuration ---
NVIDIA_API_KEY=your_nvidia_nim_api_key_here
NVIDIA_NIM_MODEL=mistralai/mistral-small-4-119b-2603   # optional override, this is the default

# --- Neuro-SAN ---
NEURO_SAN_URL=http://localhost:8080                     # base URL of the running Neuro-SAN server
LLM_PROVIDER_PRIMARY=nvidia_nim

# --- Database ---
DATABASE_URL=sqlite:///./cartographer.db                # SQLite for dev/hackathon
# DATABASE_URL=postgresql://user:password@localhost:5432/cartographer  # use this in production

# --- SMTP / Notifications ---
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_CREDENTIALS=your_smtp_username:your_smtp_password

# --- Approval Gate ---
APPROVAL_WINDOW_HOURS=48
MAX_REDRAFT_ATTEMPTS=4

# --- Cloud & Diagram Settings ---
SUPPORTED_CLOUD_PROVIDERS=aws,azure,gcp
DIAGRAM_OUTPUT_FORMAT=svg                                # svg (default) or png
DIAGRAM_RENDER_ENGINE=mermaid_cli                         # mermaid_cli or graphviz

# --- Cost Reference ---
COST_RATE_CARD_PATH=./config/cost_rate_card.json

# --- File Storage ---
REQUEST_RESPONSE_ROOT=./request_response/
```

> **Note:** Never commit your `.env` file to version control. Make sure it is listed in `.gitignore`.

## 4. Install Backend Dependencies

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

> `requirements.txt` is currently a placeholder in this repository — populate it with the backend's actual dependencies (e.g., `neuro-san`, `sqlalchemy`, `reportlab`, `checkov`, `python-dotenv`, etc.) before installing.

## 5. Install Dashboard Dependencies

```bash
cd dashboard-web
npm install
cd ..
```

## 6. Set Up the Database

For local/hackathon use (SQLite), the database file is created automatically on first run. For production (PostgreSQL), make sure the database referenced in `DATABASE_URL` exists:

```bash
# Example: create a local PostgreSQL database
createdb cartographer
```

Then run any migration/setup scripts provided by the backend (e.g.):

```bash
python -m database.db_session
```

## 7. Run with Docker Compose (Recommended for Local/Hackathon Setup)

The simplest way to bring up the full stack (Neuro-SAN, orchestrator, database, dashboard) is via the provided Docker Compose file:

```bash
docker compose -f deploy/docker-compose.yaml up --build
```

This will start:
- the Neuro-SAN agent network container
- the orchestrator/gateway container
- the database container
- the dashboard container

Once running, the dashboard should be accessible at `http://localhost:3000` (or the port configured in `deploy/docker-compose.yaml`), and the API at the URL configured in `NEURO_SAN_URL`.

## 8. Run Manually (Without Docker)

If you prefer to run each component individually:

**Start the Neuro-SAN agent server:**
```bash
python -m neuro_san.session.run_server
```

**Start the Gateway/API:**
```bash
python -m gateway.api.main
```

**Start the Dashboard:**
```bash
cd dashboard-web
npm run dev
```

## 9. Verify the Setup

1. Confirm the API is reachable at the configured `NEURO_SAN_URL`.
2. Open the dashboard in your browser and confirm the request list page loads.
3. Submit a sample migration request (a mock `project.json`) and confirm the agent network runs end-to-end, producing a blueprint, architecture diagram, and report.
4. Confirm an approval-request email is sent to the configured SMTP recipient.

## 10. Project Structure

Refer to [`architecture.md`](architecture.md) for detailed architecture diagrams and [`summary.md`](summary.md) for the full solution design, agent responsibilities, and technology stack.
