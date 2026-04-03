"""
Test script to run a real workflow on "climate change" topic.
This script runs the research workflow directly without API layer.
"""

import asyncio
import logging
import sys
import os
from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone

# Add backend to path
sys.path.insert(0, 'backend')

# Set environment variable to skip database connection if needed
os.environ.setdefault('SKIP_DATABASE_INIT', 'false')

from backend.models.research import ResearchState, ResearchDepth, TaskStatus
from backend.orchestrator.standard_orchestrator import run_research
from backend.database.connection import AsyncSessionLocal
from backend.services.research_service import ResearchService
from backend.utils.workflow_instrumentation import WorkflowInstrumentation

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def run_climate_change_workflow():
    """Run a real research workflow on climate change topic."""
    
    task_id = uuid4()
    user_id = uuid4()
    
    logger.info("=" * 80)
    logger.info("STARTING CLIMATE CHANGE RESEARCH WORKFLOW")
    logger.info("=" * 80)
    logger.info(f"Task ID: {task_id}")
    logger.info(f"User ID: {user_id}")
    logger.info("")
    
    start_time = None
    
    try:
        # Create database session
        async with AsyncSessionLocal() as db:
            # First, create or get a test user
            logger.info("Setting up test user...")
            test_user_id = uuid4()
            
            # Check if user exists, if not create it
            from sqlalchemy import select, text
            
            # Use raw SQL to check if user exists (avoids model conflicts)
            user_check = await db.execute(
                text("SELECT id FROM users WHERE id = :user_id"),
                {"user_id": str(test_user_id)}
            )
            existing_user = user_check.scalar_one_or_none()
            
            if not existing_user:
                # Create user using raw SQL insert
                # Use naive datetime (without timezone) to match database schema
                now = datetime.now()
                await db.execute(
                    text("""
                        INSERT INTO users (id, email, hashed_password, subscription_tier, subscription_status, is_active, created_at, updated_at)
                        VALUES (:id, :email, :password, :tier, :status, :active, :created_at, :updated_at)
                    """),
                    {
                        "id": str(test_user_id),
                        "email": f"test-climate-{test_user_id}@consilience.dev",
                        "password": "dummy_hash_for_testing",  # Just a placeholder
                        "tier": "FREE",
                        "status": "ACTIVE",
                        "active": True,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                await db.commit()
                logger.info(f"Created test user: {test_user_id}")
            else:
                logger.info(f"Using existing test user: {test_user_id}")
            
            user_id = test_user_id
            
            # Now create the research task
            logger.info("Creating task in database...")
            task = await ResearchService.save_research_task(
                session=db,
                user_id=user_id,
                topic="Climate Change: Impacts on Global Agriculture and Food Security",
                research_depth=ResearchDepth.STANDARD,
                title="Climate Change Research",
                description="Research on climate change impacts on global agriculture and food security",
                estimated_cost_usd=2.00,
            )
            logger.info(f"Task created in database with ID: {task.id}")
            logger.info("")
            
            # Convert task.id to UUID (ORM object may return Column type)
            task_id = UUID(str(task.id))
        
        # Log task creation
        WorkflowInstrumentation.log_task_created(
            task_id=task_id,
            user_id=user_id,
            topic="Climate Change: Impacts on Global Agriculture and Food Security",
            research_depth="standard",
            estimated_cost=2.00,
        )
        
        # Log task start
        WorkflowInstrumentation.log_task_started(
            task_id=task_id,
            worker_id="local-test-worker",
            deadline_seconds=900,  # 15 minutes
        )
        # Create research state
        state = ResearchState(
            task_id=str(task_id),
            topic="Climate Change: Impacts on Global Agriculture and Food Security",
            requirements={
                "focus_areas": [
                    "impacts on crop yields",
                    "regional variations",
                    "mitigation strategies",
                    "economic implications"
                ]
            },
            num_sources_target=15,
        )
        
        logger.info("Created research state:")
        logger.info(f"  Topic: {state.topic}")
        logger.info(f"  Depth: standard")
        logger.info(f"  Target sources: {state.num_sources_target}")
        logger.info("")
        logger.info("Starting workflow phases:")
        logger.info("-" * 80)
        
        # Set deadline to 15 minutes from now (use naive datetime to match utcnow())
        deadline_at = datetime.utcnow() + timedelta(seconds=900)
        
        # Run the orchestrator
        start_time = datetime.utcnow()
        final_state = await run_research(state, deadline_at=deadline_at)
        end_time = datetime.utcnow()
        
        execution_time = (end_time - start_time).total_seconds()
        
        logger.info("-" * 80)
        logger.info("")
        logger.info("WORKFLOW COMPLETED ✅")
        logger.info("=" * 80)
        logger.info(f"Execution time: {execution_time:.1f} seconds")
        logger.info(f"Total tokens used: {final_state.tokens_used}")
        logger.info(f"Total cost: ${final_state.cost:.2f}")
        logger.info(f"Sources found: {len(final_state.sources)}")
        logger.info("")
        
        if final_state.sources:
            logger.info("TOP SOURCES:")
            for i, source in enumerate(final_state.sources[:5], 1):
                # Handle both dict and Source object types
                title = source.get('title', 'Unknown title') if isinstance(source, dict) else getattr(source, 'title', 'Unknown title')
                url = source.get('url', 'No URL') if isinstance(source, dict) else getattr(source, 'url', 'No URL')
                logger.info(f"  {i}. {title}")
                logger.info(f"     URL: {url[:60]}...")
        
        logger.info("")
        logger.info("FINAL PAPER SUMMARY (first 500 chars):")
        logger.info("-" * 80)
        if final_state.final_paper:
            paper_preview = final_state.final_paper[:500]
            logger.info(paper_preview)
            if len(final_state.final_paper) > 500:
                logger.info("...")
        logger.info("")
        
        if final_state.contradictions:
            logger.info(f"Contradictions found: {len(final_state.contradictions)}")
            for i, contradiction in enumerate(final_state.contradictions[:3], 1):
                logger.info(f"  {i}. {contradiction}")
        else:
            logger.info("No contradictions found")
        
        logger.info("")
        logger.info("=" * 80)
        
        # Log task completion
        WorkflowInstrumentation.log_task_completed(
            task_id=task_id,
            tokens_used=final_state.tokens_used or 0,
            actual_cost=final_state.cost or 0.0,
            execution_time_seconds=execution_time,
        )
        
        return final_state
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"WORKFLOW FAILED ❌")
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}")
        logger.error("", exc_info=True)
        
        # Log task failure
        WorkflowInstrumentation.log_task_failed(
            task_id=task_id,
            error_code="EXECUTION_ERROR",
            error_message=str(e),
            execution_time_seconds=(datetime.now(timezone.utc) - start_time).total_seconds() if start_time else 0,
        )
        
        raise


async def main():
    """Main entry point."""
    logger.info("Climate Change Research Workflow Test")
    logger.info("Starting workflow execution...\n")
    
    try:
        result = await run_climate_change_workflow()
        logger.info("\n✅ Test completed successfully!")
        return 0
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
