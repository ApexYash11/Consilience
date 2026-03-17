# Consilience Quickstart Guide

> Get up and running with Consilience in 10 minutes.

## Prerequisites

- Python 3.9+
- Git
- PostgreSQL/Neon database (or SQLite for development)
- OpenRouter API key (or use mock in development)

## 1. Clone & Setup (2 minutes)

```bash
# Clone the repository
git clone https://github.com/yourusername/consilience.git
cd consilience

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Configure Environment (2 minutes)

Create a `.env` file:

```env
# Development Configuration
DEBUG=true
ENVIRONMENT=development
API_PORT=8000

# Database (use SQLite for development)
DATABASE_URL=sqlite:///./consilience_dev.db

# LLM API (get from https://openrouter.ai)
OPENROUTER_API_KEY=sk_...your_key_here...
OPENROUTER_REFERER=https://localhost:8000

# Security (generate random string for development)
JWT_SECRET_KEY=dev-secret-change-in-production

# Frontend
FRONTEND_URL=http://localhost:3000
```

## 3. Run the API (1 minute)

```bash
python api/main.py
```

You should see:
```
INFO: Uvicorn running on http://0.0.0.0:8000
```

## 4. Explore the API

### Interactive Swagger Documentation
Open **[http://localhost:8000/docs](http://localhost:8000/docs)** in your browser — full interactive API documentation with "Try it out" buttons.

### Alternative: ReDoc
Open **[http://localhost:8000/redoc](http://localhost:8000/redoc)** for alternative documentation format.

### Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "Consilience",
  "version": "1.0.0",
  "database": "connected"
}
```

## 5. Create Your First Research Task (3 minutes)

### Get a Test JWT Token

In development with `DEBUG=true`, use this test token:

```bash
export TEST_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwicm9sZXMiOlsigGZyZWUiXSwiaXNzIjoiaHR0cHM6Ly9uZW9uYXV0aC5leGFtcGxlLmNvbSIsImF1ZCI6Im5lb25kYiIsImlhdCI6MTcxMDY4NzIwMCwiZXhwIjo3MTkwNjg3MjAwfQ.test"
```

### Submit a Research Task

```bash
curl -X POST http://localhost:8000/api/research/standard \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "What is machine learning?",
    "requirements": {}
  }'
```

Expected response:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "estimated_cost_usd": 0.05,
  "estimated_time_minutes": 5
}
```

Save the `task_id` for next steps.

### Check Task Status

```bash
curl -X GET http://localhost:8000/api/research/standard/550e8400-e29b-41d4-a716-446655440000/status \
  -H "Authorization: Bearer $TEST_TOKEN"
```

Response:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "current_step": "Verifying sources..."
}
```

Possible statuses: `pending`, `processing`, `completed`, `failed`

### Get Results

Once status is `completed`:

```bash
curl -X GET http://localhost:8000/api/research/standard/550e8400-e29b-41d4-a716-446655440000/result \
  -H "Authorization: Bearer $TEST_TOKEN"
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_auth_complete.py -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=html

# Run only auth tests
pytest tests/test_auth_complete.py -v
```

## Common Tasks

### View API Logs

```bash
# Logs are printed to stdout
# Watch real-time logs:
tail -f consilience.log
```

### Check Database

```python
# Connect to SQLite database directly
sqlite3 consilience_dev.db

# List tables
.tables

# Check users table
SELECT id, email, subscription_tier FROM users;
```

### Reset Database

```bash
# Remove SQLite database (will be recreated on next run)
rm consilience_dev.db

# Run API again to initialize
python api/main.py
```

### Debug Mode

Set `DEBUG=true` in `.env` to:
- Skip JWT signature verification
- Add detailed error messages
- Enable SQL query logging
- Show full tracebacks

⚠️ **Never use DEBUG=true in production!**

## Project Structure

```
api/
  ├── main.py              # FastAPI app + startup/shutdown
  ├── dependencies.py      # Auth, quotas, rate limits
  └── routes/
      ├── research.py      # Research endpoints
      ├── users.py         # User endpoints
      └── auth.py          # Auth endpoints

agents/                     # 7 specialized agents
orchestrator/              # LangGraph workflows
services/                  # Business logic
tests/                     # Test suite
```

## Troubleshooting

### "Database connection failed"
```bash
# Check DATABASE_URL is set and database runs
echo $DATABASE_URL
# For SQLite, ensure file is writable

# For PostgreSQL/Neon:
psql postgresql://user:pass@host:port/consilience -c "SELECT 1"
```

### "JWT validation failed"
```bash
# In development, ensure DEBUG=true
# In production, verify JWT_SECRET_KEY matches issuer
```

### "OpenRouter API rate limit"
- Check your OpenRouter API key is valid
- Check rate limits: https://openrouter.ai/account
- Use mock responses in development

### "Long research tasks timeout"
- Standard research: 3-5 minutes (increase if needed)
- Deep research: 10-20 minutes
- Monitor background task runner logs

## Next Steps

1. **Read the Full README** — Comprehensive documentation on architecture, deployment, cost model
2. **Explore API Endpoints** — Visit `/docs` for interactive testing
3. **Run Tests** — `pytest tests/ -v` to understand the system
4. **Study the Code** — Start with `orchestrator/standard_orchestrator.py`
5. **Deploy to Staging** — Follow deployment instructions in README

## Getting Help

- **Documentation**: [README.md](README.md) — Full comprehensive guide
- **Troubleshooting**: [README.md#troubleshooting](README.md#troubleshooting)
- **API Reference**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Status Report**: [STATUS_March_2026.md](STATUS_March_2026.md)

## Key Files to Understand

1. **api/main.py** — How the API starts and shuts down
2. **api/routes/research.py** — How research endpoints work
3. **orchestrator/standard_orchestrator.py** — 7-agent workflow
4. **services/cost_service.py** — Cost tracking and quotas
5. **tests/conftest.py** — How to write tests

---

**Happy researching! 🚀**
