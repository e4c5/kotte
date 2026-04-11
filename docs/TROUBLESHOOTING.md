# Troubleshooting Guide

This guide covers common issues encountered when setting up, developing, or using Kotte.

## Backend Issues

### ModuleNotFoundError: No module named 'itsdangerous' (or other packages)
**Issue:** Tests or server fail to start with dependency errors.
**Solution:** Ensure all dependencies are installed. Kotte has both production and development requirements.
```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
```

### Apache AGE extension not found
**Issue:** `APIException: Apache AGE extension not found in database`
**Solution:** 
1. Ensure the PostgreSQL instance has the AGE extension installed.
2. Run `CREATE EXTENSION IF NOT EXISTS age CASCADE;` in your database.
3. If using Docker, ensure you're using an image that includes AGE (like `apache/age`).

### Connection pool initialization timeout
**Issue:** Backend fails to connect to the database within 10 seconds.
**Solution:**
1. Check if the database host and port are correct in your `.env` file.
2. Ensure the database is running and reachable from the backend.
3. Increase `DB_CONNECT_TIMEOUT` in your configuration if the database is slow to respond.

---

## Frontend Issues

### Multiple elements found with the same role
**Issue:** Vitest failures when querying for buttons or labels.
**Solution:** This often happens when automatic cleanup is disabled or when multiple tabs are rendered in the same test.
1. Ensure `globals: true` is set in `vite.config.ts`.
2. Use more specific queries (e.g., regex with anchors: `getByRole('button', { name: /^filter$/i })`).

### D3 TypeError: simulation.nodes is not a function
**Issue:** Frontend tests failing after adding D3 cleanup logic.
**Solution:** The D3 mock in your test needs to support the chained methods used in the component. Ensure the mock `forceSimulation` returns an object with `nodes()`, `force()`, etc., that return `this` or the appropriate mock.

### CSS styles not applying (Tailwind)
**Issue:** UI looks unstyled or broken.
**Solution:** Kotte uses Tailwind CSS 4. Ensure your build process is running and the PostCSS configuration is correct.
```bash
cd frontend
npm install
npm run dev
```

---

## Common Workflows

### Re-running tests
Always run both backend and frontend tests before committing changes:
```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test -- --run
```

### Debugging with Logs
Enable structured logging or adjust the log level in your `.env`:
```env
LOG_LEVEL=DEBUG
STRUCTURED_LOGGING=false
```
When `STRUCTURED_LOGGING` is `false`, logs are easier to read in the console during development.
