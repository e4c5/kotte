-- Sample graph "test_graph" for Kotte visualization testing
-- Run this in psql against your AGE database (e.g. postgresDB on localhost:5455).
--
-- Usage:
--   psql -h localhost -p 5455 -U postgresUser -d postgresDB -f docs/sample-graph-test_graph.sql
--
-- Or in an interactive psql session (same session for all statements):
--   \i docs/sample-graph-test_graph.sql

-- 1. Ensure AGE is available and search path is set
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- 2. Create the graph (idempotent: no-op if it already exists)
DO $$
BEGIN
  PERFORM * FROM ag_catalog.create_graph('test_graph');
EXCEPTION
  WHEN duplicate_schema OR duplicate_object THEN
    NULL;
END
$$;

-- 3. Create sample vertices (nodes)
SELECT * FROM cypher('test_graph', $$
  CREATE (a:Person {name: 'Alice', age: 30})
  RETURN a
$$) AS (result agtype);

SELECT * FROM cypher('test_graph', $$
  CREATE (b:Person {name: 'Bob', age: 25})
  RETURN b
$$) AS (result agtype);

SELECT * FROM cypher('test_graph', $$
  CREATE (c:Person {name: 'Carol', age: 28})
  RETURN c
$$) AS (result agtype);

SELECT * FROM cypher('test_graph', $$
  CREATE (d:Project {title: 'Kotte', status: 'active'})
  RETURN d
$$) AS (result agtype);

SELECT * FROM cypher('test_graph', $$
  CREATE (e:Project {title: 'AGE', status: 'active'})
  RETURN e
$$) AS (result agtype);

-- 4. Create edges (must match existing nodes)
SELECT * FROM cypher('test_graph', $$
  MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Bob'})
  CREATE (a)-[r:KNOWS {since: 2020}]->(b)
  RETURN r
$$) AS (result agtype);

SELECT * FROM cypher('test_graph', $$
  MATCH (b:Person {name: 'Bob'}), (c:Person {name: 'Carol'})
  CREATE (b)-[r:KNOWS {since: 2021}]->(c)
  RETURN r
$$) AS (result agtype);

SELECT * FROM cypher('test_graph', $$
  MATCH (a:Person {name: 'Alice'}), (c:Person {name: 'Carol'})
  CREATE (a)-[r:KNOWS]->(c)
  RETURN r
$$) AS (result agtype);

SELECT * FROM cypher('test_graph', $$
  MATCH (a:Person {name: 'Alice'}), (d:Project {title: 'Kotte'})
  CREATE (a)-[r:WORKS_ON {role: 'dev'}]->(d)
  RETURN r
$$) AS (result agtype);

SELECT * FROM cypher('test_graph', $$
  MATCH (b:Person {name: 'Bob'}), (d:Project {title: 'Kotte'})
  CREATE (b)-[r:WORKS_ON {role: 'dev'}]->(d)
  RETURN r
$$) AS (result agtype);

SELECT * FROM cypher('test_graph', $$
  MATCH (c:Person {name: 'Carol'}), (e:Project {title: 'AGE'})
  CREATE (c)-[r:WORKS_ON {role: 'contributor'}]->(e)
  RETURN r
$$) AS (result agtype);

-- 5. Verify: run in Kotte or psql
-- In Kotte: select graph "test_graph", then run:
--   MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 50
-- You should see nodes and edges in Graph View.
