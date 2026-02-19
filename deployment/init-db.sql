-- Ensure Apache AGE extension is loaded (apache/age image has it pre-loaded)
CREATE EXTENSION IF NOT EXISTS age;

-- Create a sample graph for quick testing (optional)
-- Uncomment to auto-create a test graph on first run:
-- SELECT * FROM ag_catalog.create_graph('test_graph');
