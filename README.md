# Consilience: Multi-Agent AI Research Platform

> A production-grade system for generating high-quality research papers through coordinated multi-agent collaboration, rigorous verification, and deterministic orchestration.

## What is Consilience?

Consilience solves the **reliability problem in AI-generated research**. Traditional AI systems produce unreliable outputs because they operate as "black boxes" with no oversight, verification, or quality control.

**Consilience takes a different approach:**

Instead of trusting a single LLM, we orchestrate **7 specialized agents** working in parallel through a **deterministic workflow** with explicit quality gates:

1. **Planner** - Decomposes research topics into verifiable claims
2. **5× Parallel Researchers** - Execute targeted searches (web, academic, PDF extraction)
3. **Verifier** - Cross-checks sources and validates citations
4. **Detector** - Identifies hallucinations and unsupported claims
5. **Synthesizer** - Synthesizes research into a cohesive paper
6. **Reviewer** - Critiques methodology and identifies gaps
7. **Formatter** - Produces publication-ready output

Each agent is **transparent, auditable, and replaceable**—you can see exactly what each agent did, why, and when.

## Key Features

### 🔄 Deterministic Orchestration
- **LangGraph-based workflow** with 11 nodes managing agent transitions
- **Conditional routing** based on quality metrics (source verification, synthesis confidence)
- **Explicit decision points** where agents verify each other's work
- **No black boxes** — every decision is logged and auditable

### 🔍 Quality Assurance Built-In
- **Multi-round verification** ensures sources are legitimate
- **Hallucination detection** catches unsupported claims automatically
- **Citation validation** prevents broken or fabricated references
- **Confidence scoring** on all claims and sources

### 💰 Cost Tracking & Quotas
- **Per-token cost tracking** from OpenRouter LLM API
- **Monthly quotas** prevent runaway costs
- **Fair usage policies** with free and paid tiers
- **Detailed usage analytics** per user/team

### 🔐 Enterprise Security
- **JWT-based authentication** via Neon DB
- **Role-based access control** (free/paid/admin tiers)
- **Subscription management** with Dodo Payments integration
- **Immutable audit logs** for compliance

### 📊 Async Task Processing
- **Background research execution** via FastAPI background tasks
- **Real-time status polling** with /status endpoints
- **Large-scale paper storage** with structured metadata
- **Research context persistence** for reproducibility

##  Architecture Overview
- **Backend**: FastAPI with async/await, SQLAlchemy 2.0 ORM
- **Database**: Neon PostgreSQL with async connection pooling
- **Orchestration**: LangGraph for deterministic multi-agent workflows
- **LLM Client**: OpenRouter with token counting fallback
- **Task Queue**: FastAPI background tasks (asyncio)
- **API Docs**: Auto-generated Swagger UI at `/docs`

##  Getting Started
1. **Clone the repository**
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Configure Environment**: Add `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to `.env`.
4. **Run the API**: `python api/main.py`

## API Quickstart

The API is available at `http://localhost:8000` with interactive documentation at `/docs`.

### 1. Create a Standard Research Task

```bash
curl -X POST http://localhost:8000/api/research/standard \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Climate change impacts on agriculture",
    "requirements": {}
  }'
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "estimated_cost_usd": 0.05,
  "estimated_time_minutes": 5
}
```

### 2. Check Research Status

```bash
curl -X GET http://localhost:8000/api/research/standard/550e8400-e29b-41d4-a716-446655440000/status \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "current_step": "Verifying sources...",
  "created_at": "2026-03-17T10:30:00Z"
}
```

### 3. Retrieve Research Results

```bash
curl -X GET http://localhost:8000/api/research/standard/550e8400-e29b-41d4-a716-446655440000/result \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "final_paper": "## Climate Change Impacts on Agriculture...",
  "sources": [
    {
      "url": "https://...",
      "title": "...",
      "quality_score": 0.95
    }
  ],
  "metadata": {
    "total_tokens": 32000,
    "cost_usd": 0.45,
    "duration_seconds": 287
  }
}
```

### 4. Check Your Usage and Quota

```bash
curl -X GET http://localhost:8000/api/users/usage \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "period": "2026-03",
  "standard_research": {
    "used": 2,
    "quota": 5,
    "remaining": 3
  },
  "deep_research": {
    "used": 1,
    "quota": 5,
    "remaining": 4,
    "available": true
  },
  "tokens_this_month": 32000,
  "cost_this_month_usd": 12.50,
  "subscription_tier": "free"
}
```

### 5. Create a Deep Research Task (Paid Feature)

```bash
curl -X POST http://localhost:8000/api/research/deep \
  -H "Authorization: Bearer YOUR_PAID_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Quantum computing applications in drug discovery",
    "requirements": {}
  }'
```

**Note:** Deep research requires a paid subscription and takes 10-30 minutes.

## Configuration & Deployment

### Environment Variables

Create a `.env` file with:

```env
# API Configuration
DEBUG=false                          # Disable in production
ENVIRONMENT=production               # development | staging | production
APP_NAME=Consilience
APP_VERSION=1.0.0
API_PORT=8000

# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/consilience

# LLM / Cost Tracking
OPENROUTER_API_KEY=your_key_here
OPENROUTER_REFERER=https://yourapp.com

# Security
JWT_SECRET_KEY=your-secret-key-change-in-production
FRONTEND_URL=https://yourapp.com

# Optional: LangSmith Monitoring
LANGSMITH_API_KEY=optional
LANGSMITH_PROJECT=optional
```

### Installation & Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/consilience.git
cd consilience

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations (if using Alembic)
alembic upgrade head

# Start the API server
python api/main.py

# The API will be available at http://localhost:8000
# Swagger docs: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_auth_complete.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run async tests only
pytest tests/ -k "async" -v
```

## Project Structure

```
consilience/
├── api/                      # FastAPI application
│   ├── main.py              # App initialization, startup/shutdown events
│   ├── dependencies.py       # Dependency injection (auth, quotas, rate limits)
│   └── routes/              # Endpoint implementations
│       ├── research.py       # POST/GET research endpoints
│       ├── users.py          # User profile and usage endpoints
│       └── auth.py           # Authentication endpoints
│
├── agents/                   # Multi-agent orchestration
│   ├── standard/            # 7 standard research agents
│   └── deep/                # Deep research sub-agents
│
├── orchestrator/            # LangGraph workflow definitions
│   ├── standard_orchestrator.py  # 11-node standard workflow
│   ├── deep_orchestrator.py      # Deep research orchestrator
│   └── langraph_workflow.py       # LangGraph configuration
│
├── models/                  # Data models
│   ├── research.py          # Research task models
│   ├── user.py              # User models
│   ├── payment.py           # Subscription models
│   └── audit.py             # Audit log models
│
├── services/                # Business logic
│   ├── cost_service.py      # Cost tracking and quota enforcement
│   ├── research_service.py  # Research task management
│   ├── cleanup_service.py   # TTL cleanup for old files
│   └── payment_service.py   # Dodo Payments integration
│
├── database/                # Database
│   ├── connection.py        # Async DB & connection pooling
│   ├── schema.py            # SQLAlchemy table definitions
│   └── migrations/          # Alembic migrations
│
├── core/                    # Core utilities
│   ├── config.py            # Settings and configuration
│   ├── security.py          # JWT verification
│   └── exceptions.py        # Custom exceptions
│
├── tools/                   # Agent tools (APIs, search, extraction)
│   ├── web_search.py        # Google Custom Search
│   ├── academic_search.py   # Semantic Scholar API
│   └── pdf_extraction.py    # Document parsing
│
├── tests/                   # Test suite
│   ├── conftest.py          # Pytest fixtures (auth, DB, client)
│   ├── test_auth_complete.py
│   ├── test_standard_research.py
│   ├── test_deep_research.py
│   └── test_quota_enforcement.py
│
├── requirements.txt         # Python dependencies
├── pytest.ini               # Pytest configuration
└── README.md               # This file
```

## API Endpoints Reference

### Research Tasks

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/research/standard` | Required | Create standard research task |
| GET | `/api/research/standard/{task_id}/status` | Required | Get task status |
| GET | `/api/research/standard/{task_id}/result` | Required | Get completed results |
| POST | `/api/research/deep` | Paid Required | Create deep research task (more rounds) |
| GET | `/api/research/deep/{task_id}/status` | Required | Get deep task status |
| GET | `/api/research/deep/{task_id}/result` | Required | Get deep task results |

### User Management

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/users/usage` | Required | Get usage stats and quotas |
| GET | `/api/users/profile` | Required | Get user profile |
| POST | `/api/users/update-subscription` | Required | Change subscription tier |

### Health & Maintenance

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | Optional | API health check |
| GET | `/docs` | None | Interactive Swagger UI |
| GET | `/redoc` | None | ReDoc API documentation |

## Cost Model

### Standard Research
- **Free Tier**: 5 tasks/month, ~$0.10 per task
- **Paid Tier**: 20 tasks/month, ~$0.10 per task

### Deep Research (Paid Only)
- **Paid Tier**: 10 tasks/month, ~$0.50 per task (3 research rounds)

**Costs are tracked per LLM token from OpenRouter and are transparent to users.**

## Security & Compliance

### Authentication
- JWT-based with Neon DB integration
- HS256 signature verification
- Token refresh capability
- Role-based access control (free/paid/admin)

### Data Protection
- All transit encrypted via HTTPS
- Database password stored in secrets manager
- No API keys logged or stored
- Immutable audit trail

### Rate Limiting
- 10 requests per 60 seconds per user
- HTTP 429 (Too Many Requests) when exceeded
- Automatic quota enforcement

## Troubleshooting

### Common Issues

**"Database connection failed"**
- Check `DATABASE_URL` in `.env`
- Verify PostgreSQL/Neon is running
- Check credentials

**"JWT signature verification failed"**
- Set `DEBUG=true` for development
- Use test JWT tokens from conftest.py
- Check token expiration (`exp` claim)

**"Research task hangs indefinitely"**
- Check background task runner (asyncio)
- Monitor LLM API rate limits
- Check logs for agent errors

**"Tests fail with 'no such table' error"**
- Run `pytest` with async DB reset
- Check conftest.py fixtures are loaded
- Ensure `BASE.metadata.create_all()` executes

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes and add tests
4. Run `pytest tests/ -v` to verify
5. Submit a pull request

**Code Quality Standards:**
- All tests must pass (`pytest tests/ -v`)
- Coverage >= 80% for new code
- Type hints required for all functions
- Docstrings for all public methods
- Follow PEP 8 style guide

## Performance & Scalability

### Current Benchmarks
- **Standard Research Task**: 3-5 minutes (7 agents, 5 parallel researchers)
- **Deep Research Task**: 10-20 minutes (18 sub-agents, 3 rounds)
- **Concurrent Users**: Tested with 50+ simultaneous tasks
- **Database**: ~10,000 research records, <100ms query time

### Optimization Recommendations
- Enable Redis caching for search results
- Use connection pooling (already enabled with asyncpg)
- Implement async request batching for LLM calls
- Consider distributed task queue (Celery) for scale > 1000 users

## Documentation

- [Architecture Guide](DEEP_RESEARCH_GUIDE.md) - Deep research design and agent interaction
- [Status Report](STATUS_March_2026.md) - Phase completion and test results
- [Setup Instructions](setup.md) - Detailed installation guide
- [LangSmith Plan](LANGSMITH_OBSERVABILITY_IMPLEMENTATION_PLAN.md) - Observability roadmap

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Email: support@consilience.ai
- Discord: https://discord.gg/consilience

---

**Built with ❤️ for reliable, transparent AI research**

*Last Updated: March 17, 2026*
*Version: 1.0 (Production Ready)*
