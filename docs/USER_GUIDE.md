# Kotte User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Connecting to a Database](#connecting-to-a-database)
4. [Working with Graphs](#working-with-graphs)
5. [Running Cypher Queries](#running-cypher-queries)
6. [Visualizing Results](#visualizing-results)
7. [Managing Saved Connections](#managing-saved-connections)
8. [Query History](#query-history)
9. [Exporting Data](#exporting-data)
10. [Troubleshooting](#troubleshooting)

---

## Introduction

Kotte is a graph visualizer for Apache AGE, designed to help you explore and query graph databases with ease. It provides an intuitive interface for running Cypher queries and visualizing the results as interactive graphs or tables.

### Key Features

- **Interactive Graph Visualization**: Explore your graph data with D3.js-powered force-directed layouts
- **Cypher Query Editor**: Write and execute Cypher queries with syntax highlighting and history
- **Multiple View Modes**: Switch between graph visualization and table view
- **Saved Connections**: Store frequently-used database connections securely
- **Metadata Explorer**: Browse graphs, node labels, and edge types
- **Export Capabilities**: Export results as CSV or JSON
- **Secure Session Management**: Your credentials are encrypted and handled securely

---

## Getting Started

### Prerequisites

Before using Kotte, ensure you have:

- PostgreSQL 14 or higher installed and running
- Apache AGE extension installed and enabled
- Network access to your PostgreSQL database
- A web browser (Chrome, Firefox, Safari, or Edge)

### First Launch

1. **Start Kotte**: Navigate to `http://localhost:5173` (or your configured URL)
2. **Connect to Database**: You'll see the connection page on first launch
3. **Enter Credentials**: Provide your database connection details
4. **Start Exploring**: Once connected, you can browse graphs and run queries

---

## Connecting to a Database

### Connection Form

To connect to a PostgreSQL database with Apache AGE:

1. **Host**: Enter the database hostname (e.g., `localhost` or `db.example.com`)
2. **Port**: Enter the port number (default: `5432`)
3. **Database**: Enter the database name (e.g., `postgres`)
4. **User**: Enter your database username
5. **Password**: Enter your database password

### Connection Options

#### One-Time Connection
- Enter credentials and click "Connect"
- Credentials are used only for this session
- Not saved for future use

#### Saved Connection
- Check "Save this connection" before connecting
- Give your connection a name (e.g., "Production DB")
- Connection details are encrypted and saved
- Reuse the connection in future sessions

### Verifying Connection

After connecting, Kotte will:
- Verify that the AGE extension is available
- Load the list of available graphs
- Display the metadata sidebar
- Show a success notification

If connection fails, check:
- Database is running and accessible
- Credentials are correct
- PostgreSQL allows connections from your IP
- AGE extension is installed (`CREATE EXTENSION IF NOT EXISTS age;`)

---

## Working with Graphs

### Selecting a Graph

1. **Metadata Sidebar**: View all available graphs in the left sidebar
2. **Click a Graph**: Select a graph to set it as the active context
3. **Graph Information**: See node labels, edge types, and counts

### Creating a New Graph

Kotte doesn't create graphs directly. Use your PostgreSQL client to create graphs:

```sql
-- Create a new graph
SELECT * FROM ag_catalog.create_graph('my_graph');

-- Add some data
SELECT * FROM cypher('my_graph', $$
    CREATE (n:Person {name: 'Alice', age: 30})
    RETURN n
$$) AS (v agtype);
```

### Exploring Graph Metadata

The metadata sidebar shows:

- **Node Labels**: All vertex types in the graph (e.g., `Person`, `Product`)
- **Edge Types**: All relationship types (e.g., `KNOWS`, `PURCHASED`)
- **Counts**: Approximate counts for each label/type
- **Properties**: Sample properties discovered for each type

Click on a label or edge type to see a sample query.

---

## Running Cypher Queries

### Query Editor

The query editor provides:

- **Syntax Highlighting**: Cypher keywords and syntax are highlighted
- **Multi-line Input**: Write complex queries across multiple lines
- **Parameter Support**: Use parameters for dynamic queries
- **Keyboard Shortcuts**: Quick access to common actions

### Writing Queries

#### Basic Query

```cypher
MATCH (n:Person)
RETURN n
LIMIT 10
```

#### Query with Relationships

```cypher
MATCH (p:Person)-[r:KNOWS]->(f:Person)
WHERE p.age > 25
RETURN p, r, f
```

#### Parameterized Query

Use the Parameters field (JSON format) below the query editor:

```json
{
  "minAge": 25,
  "limit": 10
}
```

Query:
```cypher
MATCH (n:Person)
WHERE n.age > $minAge
RETURN n
LIMIT $limit
```

### Executing Queries

1. **Write Query**: Enter your Cypher query in the editor
2. **Add Parameters** (optional): Enter parameters in JSON format
3. **Execute**: Click "Run Query" or press `Ctrl+Enter` (Windows/Linux) or `Cmd+Enter` (Mac)
4. **View Results**: Results appear in the graph or table view

### Query Controls

- **Run Query**: Execute the current query
- **Cancel Query**: Stop a running query (for long-running queries)
- **Clear**: Clear the query editor
- **Format**: Auto-format your query (if available)

### Query Results

Results can contain:

- **Nodes**: Graph vertices with properties
- **Edges**: Relationships between nodes
- **Paths**: Sequences of nodes and relationships
- **Scalar Values**: Numbers, strings, booleans
- **Mixed Results**: Combinations of the above

---

## Visualizing Results

### Graph View

The graph view displays query results as an interactive network:

#### Navigation
- **Pan**: Click and drag the background
- **Zoom**: Use mouse wheel or pinch gesture
- **Select Node**: Click a node to see its properties
- **Pin Node**: Double-click to fix a node in place
- **Unpin Node**: Double-click a pinned node to release it

#### Layout Options

- **Force-Directed**: Default physics-based layout
- **Hierarchical**: Top-down tree layout
- **Radial**: Circular layout radiating from center
- **Grid**: Organized grid layout
- **Random**: Random placement

Change layout using the controls in the top toolbar.

#### Styling

Nodes are automatically colored by label. Edge thickness and color indicate relationship types.

**Node Appearance:**
- Color determined by label type
- Size based on node degree (number of connections)
- Label shows primary property (usually `name` or `id`)

**Edge Appearance:**
- Color indicates relationship type
- Arrows show direction
- Label shows relationship type

#### Graph Limits

For performance, graph visualization has limits:
- Maximum 5,000 nodes
- Maximum 10,000 edges

If your query exceeds these limits:
- A warning is displayed
- Automatically switches to table view
- Suggestion to refine query with `WHERE` or `LIMIT` clauses

### Table View

The table view shows raw query results in tabular format:

#### Features
- **Sortable Columns**: Click column headers to sort
- **Pagination**: Navigate through large result sets
- **Column Resizing**: Drag column borders to resize
- **Cell Inspection**: Click cells to see full content

#### Data Types

Table view displays:
- **Nodes**: As expandable objects showing all properties
- **Edges**: With source, target, and properties
- **Scalars**: Direct values (numbers, strings, etc.)
- **Arrays**: As formatted lists
- **Objects**: As nested structures

### Switching Views

Toggle between Graph and Table view:
1. Use the view toggle button in the toolbar
2. Or press `G` for graph view, `T` for table view

The active view is saved for your session.

---

## Managing Saved Connections

### Viewing Saved Connections

1. **Connection Page**: Access saved connections from the main connection page
2. **Saved List**: View all your saved connections
3. **Connection Details**: See host, port, database, and user (password is hidden)

### Using a Saved Connection

1. **Select Connection**: Click on a saved connection from the list
2. **Connect**: Click "Connect" to establish the connection
3. **Auto-fill**: Credentials are automatically filled

### Editing Saved Connections

1. **Select Connection**: Click the edit icon next to a saved connection
2. **Update Details**: Modify any connection parameters
3. **Save Changes**: Click "Save" to update

Note: You can update the connection name, host, port, database, and user. To change the password, delete and re-save the connection.

### Deleting Saved Connections

1. **Select Connection**: Click the delete icon next to a saved connection
2. **Confirm**: Confirm the deletion
3. **Removed**: Connection is permanently deleted from encrypted storage

### Security

All saved connections are:
- **Encrypted at Rest**: Using AES-256-GCM encryption
- **User-Specific**: Each user's connections are isolated
- **Secure Storage**: Credentials never sent to client unencrypted
- **Session-Based**: Connection credentials cleared after disconnect

---

## Query History

### Accessing History

Query history tracks all queries you've executed in the current session.

**Navigate History:**
- Press `Ctrl+Up` (Windows/Linux) or `Cmd+Up` (Mac) for previous query
- Press `Ctrl+Down` (Windows/Linux) or `Cmd+Down` (Mac) for next query

### History Features

- **Session-Based**: History persists for your current session
- **Unlimited Size**: No limit on number of queries stored
- **Chronological Order**: Most recent queries first
- **Editable**: Retrieved queries can be edited before re-running

### Clearing History

History is automatically cleared when you disconnect from the database.

---

## Exporting Data

### Export Formats

Kotte supports exporting query results in multiple formats:

#### CSV Export

1. **Switch to Table View**: CSV export works from table view
2. **Export Button**: Click "Export CSV" in the toolbar
3. **Download**: Browser downloads the CSV file

Use cases:
- Import into spreadsheet applications
- Data analysis in Excel or Google Sheets
- Backup of query results

#### JSON Export

1. **Table View**: Ensure you're in table view
2. **Export JSON**: Click "Export JSON" in the toolbar
3. **Download**: Browser downloads the JSON file

Use cases:
- Integration with other applications
- Programmatic data processing
- Backup with full type information

### Export Limitations

- Exports current query results only
- Large result sets may take time to export
- Browser download limits may apply to very large exports

---

## Troubleshooting

### Connection Issues

**Problem**: "Connection failed" error

**Solutions**:
- Verify PostgreSQL is running: `systemctl status postgresql`
- Check network connectivity: `ping <database-host>`
- Verify credentials are correct
- Check PostgreSQL `pg_hba.conf` allows connections from your IP
- Ensure database exists: `psql -l`

**Problem**: "AGE extension not found"

**Solutions**:
- Install AGE extension in PostgreSQL
- Run `CREATE EXTENSION IF NOT EXISTS age;` in your database
- Verify AGE is in PostgreSQL extensions: `SELECT * FROM pg_available_extensions WHERE name = 'age';`

### Query Errors

**Problem**: "Syntax error in Cypher query"

**Solutions**:
- Review Cypher syntax documentation
- Check for typos in keywords (`MATCH`, `WHERE`, `RETURN`)
- Ensure property names match graph schema
- Verify parameter names match between query and parameters JSON

**Problem**: "Query timeout"

**Solutions**:
- Simplify query to reduce execution time
- Add `LIMIT` clause to restrict results
- Add `WHERE` clause to filter data
- Consider adding indexes to your graph (see Contributing Guide)
- Contact administrator to increase query timeout

**Problem**: "Graph too large to visualize"

**Solutions**:
- Use `LIMIT` to restrict node count
- Add `WHERE` filters to focus on subset
- Use table view for large result sets
- Consider breaking query into smaller parts

### Visualization Issues

**Problem**: "Graph view is empty but table has data"

**Solutions**:
- Check if query returns nodes/edges (not just scalars)
- Verify result contains graph elements
- Switch to table view to inspect results
- Try a different query that returns graph structure

**Problem**: "Nodes overlap or layout is messy"

**Solutions**:
- Try different layout algorithms (hierarchical, radial, grid)
- Pin important nodes to organize manually
- Reduce number of nodes with `LIMIT`
- Use `WHERE` clause to focus on relevant subgraph

**Problem**: "Graph is very slow to render"

**Solutions**:
- Reduce query results with `LIMIT`
- Add filters to focus on specific area of graph
- Use table view for initial exploration
- Consider breaking into multiple smaller queries

### Session Issues

**Problem**: "Session expired"

**Solutions**:
- Re-connect to database from connection page
- Sessions expire after 30 minutes of inactivity
- Sessions expire after 1 hour maximum
- Check if backend server is still running

**Problem**: "Lost connection to server"

**Solutions**:
- Verify backend is running on port 8000
- Check network connectivity
- Refresh browser page
- Restart backend server if needed

### Data Issues

**Problem**: "Properties not showing in metadata"

**Solutions**:
- Metadata uses sampling, rare properties may not appear
- Run direct query to inspect: `MATCH (n:Label) RETURN properties(n) LIMIT 10`
- Properties may be sparse across nodes
- Try refreshing metadata (reconnect)

**Problem**: "Counts seem incorrect"

**Solutions**:
- Counts are approximate estimates from PostgreSQL
- Run `ANALYZE` on your database for better estimates
- Use query to get exact count: `MATCH (n:Label) RETURN count(n)`

---

## Tips and Best Practices

### Query Performance

1. **Use LIMIT**: Always use `LIMIT` for exploratory queries
2. **Filter Early**: Add `WHERE` clauses to reduce data scanned
3. **Index Properties**: Work with DBA to add indexes on frequently queried properties
4. **Avoid SELECT ***: Return only needed properties
5. **Test Small First**: Test queries on small datasets before scaling up

### Visualization

1. **Start Small**: Begin with `LIMIT 100` and increase as needed
2. **Use Filters**: Focus on specific subgraphs for clarity
3. **Pin Key Nodes**: Pin important nodes to stabilize layout
4. **Color Coding**: Use node labels as visual cues
5. **Layout Experimentation**: Try different layouts for different graph types

### Security

1. **Strong Passwords**: Use strong database passwords
2. **Saved Connections**: Use saved connections for convenience and security
3. **Regular Logout**: Disconnect when done
4. **Network Security**: Use secure network connections
5. **Credential Sharing**: Never share saved connection credentials

### Workflow

1. **Explore Metadata**: Start by browsing graph schema
2. **Sample Queries**: Use small queries to understand data
3. **Iterate**: Refine queries based on results
4. **Save Work**: Export important results
5. **Document**: Keep notes on useful queries

---

## Keyboard Shortcuts

| Action | Windows/Linux | Mac |
|--------|---------------|-----|
| Execute Query | `Ctrl+Enter` | `Cmd+Enter` |
| Previous Query | `Ctrl+Up` | `Cmd+Up` |
| Next Query | `Ctrl+Down` | `Cmd+Down` |
| Graph View | `G` | `G` |
| Table View | `T` | `T` |
| Focus Query Editor | `Ctrl+K` | `Cmd+K` |

---

## Accessibility

Kotte aims to be accessible to all users. Here are the current accessibility features and limitations:

### Keyboard Navigation

- **Tab Navigation**: Use `Tab` and `Shift+Tab` to navigate through interactive elements
- **Keyboard Shortcuts**: All major actions have keyboard shortcuts (see above)
- **Focus Indicators**: Visual indicators show which element has focus
- **Skip to Content**: Use keyboard shortcuts to jump to main content areas

### Screen Reader Support

**Current Limitations**:
- Graph visualizations are primarily visual and have limited screen reader support
- Use **Table View** for better screen reader accessibility
- Node and edge properties are available as text in table view
- Query results include descriptive labels and ARIA attributes where possible

**Recommendations for Screen Reader Users**:
1. Use Table View instead of Graph View for exploring results
2. Query editor has proper labels and can be used with screen readers
3. Export data as CSV for analysis in accessible tools like spreadsheets
4. Metadata sidebar provides text-based navigation of graph structure

### Visual Accessibility

- **High Contrast**: Interface uses sufficient color contrast ratios
- **Text Sizing**: Text can be resized using browser zoom (Ctrl/Cmd + +/-)
- **Color Coding**: Node colors in graph view use distinct hues
- **Focus Indicators**: Clear visual focus indicators for keyboard navigation

### Known Limitations

- Interactive graph visualization requires mouse for optimal use
- Some complex graph layouts may be difficult to navigate with keyboard alone
- Real-time force-directed animations may cause motion sensitivity issues

**Accessibility Feedback**: If you encounter accessibility barriers, please report them via GitHub Issues.

---

## Support and Resources

### Documentation

- [Quick Start Guide](QUICKSTART.md) - Installation and setup
- [Architecture Documentation](ARCHITECTURE.md) - Technical architecture
- [Contributing Guide](CONTRIBUTING.md) - For developers

### Apache AGE Resources

- [AGE Documentation](https://age.apache.org/)
- [Cypher Query Language](https://age.apache.org/age-manual/master/intro/cypher.html)
- [AGE Functions Reference](https://age.apache.org/age-manual/master/functions/)

### Kotte Resources

- API Documentation: `http://localhost:8000/api/docs` (when backend is running)
- GitHub Repository: [e4c5/kotte](https://github.com/e4c5/kotte)

---

## Appendix: Example Queries

### Basic Queries

**Get all nodes of a type:**
```cypher
MATCH (n:Person)
RETURN n
LIMIT 10
```

**Get nodes with specific property:**
```cypher
MATCH (n:Person)
WHERE n.age > 30
RETURN n.name, n.age
ORDER BY n.age DESC
```

**Count nodes:**
```cypher
MATCH (n:Person)
RETURN count(n) AS total
```

### Relationship Queries

**Find direct relationships:**
```cypher
MATCH (p:Person)-[r:KNOWS]->(f:Person)
RETURN p, r, f
LIMIT 20
```

**Find paths:**
```cypher
MATCH path = (a:Person {name: 'Alice'})-[:KNOWS*1..3]->(b:Person)
RETURN path
```

**Find mutual connections:**
```cypher
MATCH (a:Person)-[:KNOWS]->(b:Person)-[:KNOWS]->(a)
RETURN a, b
```

### Analytical Queries

**Degree centrality (most connected nodes):**
```cypher
MATCH (n:Person)-[r:KNOWS]-()
RETURN n.name, count(r) AS connections
ORDER BY connections DESC
LIMIT 10
```

**Find isolated nodes:**
```cypher
MATCH (n:Person)
WHERE NOT (n)-[:KNOWS]-()
RETURN n
```

**Community detection (connected components):**
```cypher
MATCH (n:Person)-[:KNOWS*]-(m:Person)
WHERE id(n) < id(m)
RETURN collect(DISTINCT n.name) AS community
```

### Data Creation

**Create nodes:**
```cypher
CREATE (n:Person {name: 'Bob', age: 35, city: 'New York'})
RETURN n
```

**Create relationships:**
```cypher
MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Bob'})
CREATE (a)-[r:KNOWS {since: 2020}]->(b)
RETURN a, r, b
```

**Batch create:**
```cypher
UNWIND [
  {name: 'Charlie', age: 28},
  {name: 'Diana', age: 32}
] AS person
CREATE (p:Person)
SET p = person
RETURN p
```

---

**Last Updated:** February 2026
