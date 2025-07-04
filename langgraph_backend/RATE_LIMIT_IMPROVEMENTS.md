# Rate Limit and Performance Improvements

This document describes the improvements made to handle rate limiting and performance issues in the LangGraph backend.

## Changes Made

### 1. Semaphore for Parallel Task Control
- Added dynamic semaphore creation based on `num_parallel_tasks` configuration
- Limits concurrent web research operations to prevent overwhelming the API
- Default: 4 parallel tasks (configurable)

### 2. Exponential Backoff Retry Mechanism
- Created `retry_with_exponential_backoff` decorator
- Handles 429 (rate limit) errors automatically
- Configuration:
  - Max retries: 5
  - Base multiplier: 1 second
  - Max wait time: 120 seconds
  - Includes random jitter to prevent thundering herd

### 3. Async/Blocking I/O Fix
- Wrapped `ChatVertexAI` initialization in `asyncio.to_thread()`
- Prevents `BlockingError` from Google Auth file reads in async context
- Ensures ASGI server performance isn't degraded

## Usage

### Configuring Parallel Tasks
```python
# In your client code
config = {
    "configurable": {
        "num_parallel_tasks": 4  # Adjust based on your needs
    }
}
```

### Rate Limit Handling
The system will automatically retry requests that hit rate limits. You'll see warnings in the logs:
```
Rate limit hit (429). Retrying generate_query in 2.34 seconds. Attempt 1/5
```

### Running with High Volume
When running with high parameters (e.g., 30 queries, 50 loops), consider:
1. Reducing `num_parallel_tasks` to 2-3
2. Monitoring rate limit warnings in logs
3. Adjusting retry parameters if needed

## Benefits
1. **Prevents 429 errors** - Automatic retry with backoff
2. **Better resource utilization** - Controlled parallelism
3. **Improved reliability** - Handles transient failures
4. **No blocking I/O errors** - Async-safe Google Auth initialization
5. **Production ready** - Suitable for high-volume research tasks 