# Getting Started with VariantIQ

This guide will walk you through setting up and using VariantIQ, from installation to making your first queries.

## Prerequisites

### Required
- Docker & Docker Compose (recommended) OR
- Python 3.11+ and PostgreSQL 15+ (manual setup)
- Git

### Optional (for full features)
- NCBI API Key ([get one here](https://www.ncbi.nlm.nih.gov/account/)) - **Highly Recommended**
- DrugBank API Key ([commercial license](https://go.drugbank.com/)) - Optional
- OpenAI or Anthropic API Key - Optional (for enhanced NLP)

## Quick Start (5 minutes)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/variantiq.git
cd variantiq
```

### 2. Configure Environment

```bash
# Copy environment template
cp backend/.env.example backend/.env

# Edit .env and add your API keys (optional but recommended)
nano backend/.env
```

**Minimum required changes in `.env`:**
```bash
SECRET_KEY=your_random_secret_key_here_min_32_chars
NCBI_EMAIL=your_email@example.com
NCBI_API_KEY=your_ncbi_key_here  # Optional but increases rate limits
```

### 3. One-Command Startup

```bash
make quickstart
```

This command will:
1. Build Docker images
2. Start PostgreSQL, Redis, and the API
3. Initialize the database
4. Load seed data (drugs + sample variants)

**Wait ~2-3 minutes for completion.**

### 4. Verify Installation

Open your browser to:
- **API Documentation**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/health
- **PgAdmin** (database UI): http://localhost:5050

### 5. Test the API

```bash
# Get variant statistics
curl http://localhost:8000/api/v1/variants/stats/summary

# List variants
curl http://localhost:8000/api/v1/variants/

# Search for EGFR variants
curl http://localhost:8000/api/v1/variants/?gene=EGFR

# Natural language query
curl -X POST http://localhost:8000/api/v1/query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "EGFR L858R druggability and clinical trials"}'
```

**🎉 You're up and running!**

---

## Detailed Setup

### Option A: Docker Setup (Recommended)

#### 1. Environment Configuration

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your configuration. **Important settings:**

```bash
# Security (REQUIRED)
SECRET_KEY=generate_with_python_secrets_token_urlsafe_32

# Database (auto-configured for Docker)
DATABASE_URL=postgresql+asyncpg://variantiq:variantiq_dev_password@postgres:5432/variantiq
REDIS_URL=redis://redis:6379/0

# NCBI API (RECOMMENDED - 10x faster rate limits)
NCBI_API_KEY=your_key_here
NCBI_EMAIL=your_email@example.com
```

To generate a secure `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### 2. Build and Start

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend
```

#### 3. Initialize Database

```bash
# Create tables
make db-init

# OR manually:
docker-compose exec backend python -c "import asyncio; from app.db.base import init_db; asyncio.run(init_db())"
```

#### 4. Load Data

```bash
# Load all data (incremental, respects rate limits)
make etl

# OR load specific datasets:
make etl-drugs          # ~1 minute
make etl-clinvar        # ~10 minutes for 100 variants
make etl-trials         # ~5 minutes for 50 trials
make etl-pubmed         # ~5 minutes for publications

# For testing (small dataset):
make etl-test           # ~2 minutes, limit=20 per pipeline
```

### Option B: Manual Setup (Without Docker)

#### 1. Install PostgreSQL 15+

```bash
# Ubuntu/Debian
sudo apt-get install postgresql-15

# macOS
brew install postgresql@15
```

#### 2. Install Redis

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis
```

#### 3. Create Database

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE variantiq;
CREATE USER variantiq WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE variantiq TO variantiq;
\q
```

#### 4. Install Python Dependencies

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### 5. Configure Environment

```bash
cp .env.example .env
nano .env
```

Update `DATABASE_URL` and `REDIS_URL` for local setup:
```bash
DATABASE_URL=postgresql+asyncpg://variantiq:your_password@localhost:5432/variantiq
REDIS_URL=redis://localhost:6379/0
```

#### 6. Initialize Database

```bash
python -c "import asyncio; from app.db.base import init_db; asyncio.run(init_db())"
```

#### 7. Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 8. Load Data

```bash
python scripts/run_etl.py --limit 50
```

---

## Loading Real Data

### Understanding the Data Pipelines

VariantIQ integrates data from multiple public sources:

| Pipeline | Source | Data Type | Est. Time (100 records) |
|----------|--------|-----------|-------------------------|
| `drugs` | Curated | Targeted therapies | ~10 seconds |
| `clinvar` | NCBI ClinVar | Genetic variants | ~5 minutes |
| `trials` | ClinicalTrials.gov | Clinical trials | ~3 minutes |
| `pubmed` | NCBI PubMed | Publications | ~4 minutes |

### Data Loading Strategies

#### 1. Quick Demo (Recommended for Testing)

```bash
# Load just drugs and a few variants
make etl-drugs
make etl-clinvar  # Defaults to limit=100
```

**Result:** ~50 drugs + ~100 variants in ~6 minutes

#### 2. Comprehensive Dataset (Production)

```bash
# Full refresh - loads all available data
make etl-full
```

**Result:**
- 15 curated drugs
- ~10,000 pathogenic variants
- ~1,000 clinical trials
- ~500 publications

**Time:** 2-4 hours (respects API rate limits)

#### 3. Incremental Updates (Daily Maintenance)

```bash
# Only fetch new/updated records since last run
make etl
```

**Time:** 5-15 minutes (depending on updates)

Set up a cron job:
```bash
0 2 * * * cd /path/to/variantiq && make etl >> logs/etl.log 2>&1
```

### Rate Limiting

**IMPORTANT:** All pipelines respect API rate limits:

- **Without NCBI API Key:** 3 requests/second
- **With NCBI API Key:** 10 requests/second (FREE, [get one here](https://www.ncbi.nlm.nih.gov/account/))

**We strongly recommend getting an NCBI API key** - it's free and makes data loading 3x faster.

---

## Using the API

### Interactive Documentation

Visit http://localhost:8000/docs for Swagger UI:
- Test all endpoints
- See request/response schemas
- View example queries

### Example Queries

#### 1. List Variants

```bash
# All variants (paginated)
curl http://localhost:8000/api/v1/variants/

# Filter by gene
curl http://localhost:8000/api/v1/variants/?gene=EGFR

# Search
curl http://localhost:8000/api/v1/variants/?search=L858R

# Pagination
curl http://localhost:8000/api/v1/variants/?skip=0&limit=20
```

#### 2. Get Variant Intelligence

```bash
# Get comprehensive analysis for variant ID 1
curl http://localhost:8000/api/v1/intelligence/1

# Customize what's included
curl "http://localhost:8000/api/v1/intelligence/1?include_trials=true&include_drugs=true&include_publications=false"
```

**Response includes:**
- Variant details
- Druggability score (if available)
- Related drugs
- Clinical trial statistics
- Market analysis (if available)
- Publications

#### 3. Natural Language Queries

```bash
curl -X POST http://localhost:8000/api/v1/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What drugs target BRAF V600E?",
    "options": {
      "include_trials": true,
      "include_drugs": true,
      "include_publications": true
    }
  }'
```

**Supported query types:**
- "EGFR L858R druggability"
- "Clinical trials for KRAS G12C"
- "What drugs target BRAF V600E?"
- "Market size for ALK fusion"
- "Show me BRCA1 variants"

#### 4. Gene-Level Summary

```bash
# Get summary for EGFR gene
curl http://localhost:8000/api/v1/intelligence/gene/EGFR/summary
```

#### 5. Database Statistics

```bash
# Get overall stats
curl http://localhost:8000/api/v1/variants/stats/summary

# List all genes
curl http://localhost:8000/api/v1/variants/genes/list
```

### Python Client Example

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Search for variants
response = requests.get(f"{BASE_URL}/variants/", params={"gene": "EGFR"})
variants = response.json()

# Get intelligence for first variant
if variants:
    variant_id = variants[0]["variant_id"]
    intelligence = requests.get(f"{BASE_URL}/intelligence/{variant_id}").json()

    print(f"Variant: {intelligence['variant']['variant_name']}")
    print(f"Gene: {intelligence['variant']['gene_symbol']}")

    if intelligence['druggability']:
        print(f"Druggability Score: {intelligence['druggability']['score']:.2f}")

    print(f"Related Drugs: {len(intelligence['drugs'])}")
    print(f"Clinical Trials: {intelligence['clinical_trials']['total']}")
```

---

## Development Workflow

### Useful Make Commands

```bash
make help              # Show all available commands
make up                # Start services
make down              # Stop services
make logs              # View logs
make shell             # Open backend shell
make db-shell          # Open PostgreSQL shell
make test              # Run tests
make lint              # Run linters
make format            # Format code
make clean             # Clean up generated files
```

### Database Management

```bash
# View database in PgAdmin
open http://localhost:5050
# Login: admin@variantiq.com / admin
# Add server: postgres / variantiq / variantiq_dev_password

# Reset database (WARNING: destroys data)
make db-reset

# Run migrations
make db-migrate
```

### Code Quality

```bash
# Format code
make format

# Run linters
make lint

# Run tests with coverage
make test

# View coverage report
open backend/htmlcov/index.html
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs

# Check specific service
docker-compose logs postgres
docker-compose logs backend

# Restart services
docker-compose restart

# Nuclear option - rebuild everything
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Database Connection Errors

```bash
# Ensure Postgres is running
docker-compose ps postgres

# Check if database exists
docker-compose exec postgres psql -U variantiq -c "\l"

# Reinitialize database
make db-init
```

### ETL Failures

```bash
# Check rate limiting - you may be hitting API limits
# Solution: Add NCBI_API_KEY to .env

# Check logs
docker-compose logs backend | grep ERROR

# Run with smaller limits for testing
docker-compose exec backend python scripts/run_etl.py --limit 10

# Run specific pipeline
docker-compose exec backend python scripts/run_etl.py --pipelines drugs
```

### Port Already in Use

```bash
# Find what's using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 instead
```

### Out of Memory

```bash
# Increase Docker memory limit (Docker Desktop settings)
# Recommended: 4GB+ for full data loading

# Or load data in smaller batches
make etl-drugs
make etl-clinvar  # Just this, skip others for now
```

---

## Next Steps

### 1. Explore the Data

- Browse variants in API docs: http://localhost:8000/docs
- Try natural language queries
- Examine variant intelligence reports

### 2. Load More Data

```bash
# Load comprehensive dataset
make etl-full
```

### 3. Customize

- Add your own genes of interest in `pubmed_pipeline.py`
- Modify search queries in `clinical_trials_pipeline.py`
- Adjust rate limits in `.env`

### 4. Build Features

- Implement ML druggability model
- Add financial modeling
- Create custom reports
- Build a frontend dashboard

### 5. Deploy to Production

See `DEPLOYMENT.md` for production deployment guide (coming soon).

---

## Support

- **Documentation**: See `docs/` directory
- **API Docs**: http://localhost:8000/docs
- **Architecture**: See `ARCHITECTURE.md`
- **Issues**: GitHub Issues
- **Email**: support@variantiq.com

---

**Happy coding!** 🧬💊📊
