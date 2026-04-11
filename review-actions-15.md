# Review Actions - PR #15

**Run Timestamp:** 2026-04-11T11:35:00Z

The following items from the pull request review have been identified as requiring further code changes. High-priority security and resource management issues have already been applied to the current branch.

## Remaining Items

### 1. Refactor Metadata Service to use Async Cache Directly
- **URL:** https://github.com/e4c5/kotte/pull/15#discussion_r3067547692
- **File:** `backend/app/services/metadata.py:34`
- **Why:** The current `LegacyPropertyCache` uses synchronous wrappers that attempt to run an event loop, which is brittle in an already-running async environment.
- **Plan:** 
  - Remove the `LegacyPropertyCache` class and `property_cache` instance.
  - Update all methods in `MetadataService` to use the `metadata_cache` instance directly with `await`.
  - Update any remaining synchronous callers (like tests) to use `asyncio.run` or appropriate async test fixtures.

### 2. Move Cache Maintenance to Background Task
- **URL:** https://github.com/e4c5/kotte/pull/15#discussion_r3067547795
- **File:** `backend/app/services/cache.py:54`
- **Why:** Performing cache cleanup synchronously within the `set()` method can cause latency spikes for the caller during high-frequency writes.
- **Plan:**
  - Modify `InMemoryCache` to use a non-blocking background task for periodic cleanup of expired items.
  - Ensure the background task is started on application lifespan initialization and properly cancelled on shutdown.

---
*Note: High-priority findings regarding Transaction Resource Management and Metrics Collector Thread Safety have been addressed in the latest commit.*
