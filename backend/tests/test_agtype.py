"""Tests for AgType parser."""

import pytest
from app.services.agtype import AgTypeParser


class TestAgTypeParser:
    """Tests for AgType parser."""

    def test_parse_none(self):
        """Test parsing None value."""
        result = AgTypeParser.parse(None)
        assert result is None

    def test_parse_scalar_string(self):
        """Test parsing scalar string."""
        result = AgTypeParser.parse("test_string")
        assert result == "test_string"

    def test_parse_scalar_int(self):
        """Test parsing scalar integer."""
        result = AgTypeParser.parse(42)
        assert result == 42

    def test_parse_scalar_float(self):
        """Test parsing scalar float."""
        result = AgTypeParser.parse(3.14)
        assert result == 3.14

    def test_parse_scalar_bool(self):
        """Test parsing scalar boolean."""
        assert AgTypeParser.parse(True) is True
        assert AgTypeParser.parse(False) is False

    def test_parse_list(self):
        """Test parsing list."""
        result = AgTypeParser.parse([1, 2, 3])
        assert result == [1, 2, 3]

    def test_parse_nested_list(self):
        """Test parsing nested list."""
        result = AgTypeParser.parse([[1, 2], [3, 4]])
        assert result == [[1, 2], [3, 4]]

    def test_parse_dict(self):
        """Test parsing regular dictionary."""
        result = AgTypeParser.parse({"key": "value", "number": 42})
        assert result == {"key": "value", "number": 42}

    def test_parse_vertex(self):
        """Test parsing a vertex (node)."""
        vertex = {
            "id": 1,
            "label": "Person",
            "properties": {"name": "Alice", "age": 30},
        }
        result = AgTypeParser.parse(vertex)
        
        assert result["type"] == "node"
        assert result["id"] == "1"  # IDs are converted to strings
        assert result["label"] == "Person"
        assert result["properties"] == {"name": "Alice", "age": 30}

    def test_parse_vertex_with_list_label(self):
        """Test parsing vertex with label as list."""
        vertex = {
            "id": 1,
            "label": ["Person"],
            "properties": {},
        }
        result = AgTypeParser.parse(vertex)
        
        assert result["type"] == "node"
        assert result["label"] == "Person"

    def test_parse_vertex_with_empty_label_list(self):
        """Test parsing vertex with empty label list."""
        vertex = {
            "id": 1,
            "label": [],
            "properties": {},
        }
        result = AgTypeParser.parse(vertex)
        
        assert result["type"] == "node"
        assert result["label"] == ""

    def test_parse_edge(self):
        """Test parsing an edge."""
        edge = {
            "id": 1,
            "label": "KNOWS",
            "start_id": 10,
            "end_id": 20,
            "properties": {"since": 2020},
        }
        result = AgTypeParser.parse(edge)
        
        assert result["type"] == "edge"
        assert result["id"] == "1"
        assert result["label"] == "KNOWS"
        assert result["source"] == "10"
        assert result["target"] == "20"
        assert result["properties"] == {"since": 2020}

    def test_parse_edge_with_list_label(self):
        """Test parsing edge with label as list."""
        edge = {
            "id": 1,
            "label": ["KNOWS"],
            "start_id": 10,
            "end_id": 20,
            "properties": {},
        }
        result = AgTypeParser.parse(edge)
        
        assert result["type"] == "edge"
        assert result["label"] == "KNOWS"

    def test_parse_path(self):
        """Test parsing a path."""
        path_data = {
            "path": [
                {"id": 1, "label": "Person", "properties": {}},
                {"id": 1, "label": "KNOWS", "start_id": 1, "end_id": 2, "properties": {}},
                {"id": 2, "label": "Person", "properties": {}},
            ]
        }
        result = AgTypeParser.parse(path_data)
        
        # Path should be parsed as dict with type and elements
        assert isinstance(result, dict)
        assert result["type"] == "path"
        assert "elements" in result
        assert len(result["elements"]) == 3

    def test_parse_nested_structures(self):
        """Test parsing nested structures."""
        data = {
            "person": {
                "id": 1,
                "label": "Person",
                "properties": {"name": "Alice"},
            },
            "friends": [
                {"id": 2, "label": "Person", "properties": {}},
                {"id": 3, "label": "Person", "properties": {}},
            ],
        }
        result = AgTypeParser.parse(data)
        
        assert result["person"]["type"] == "node"
        assert len(result["friends"]) == 2
        assert result["friends"][0]["type"] == "node"

    def test_parse_json_string(self):
        """Test parsing JSON string."""
        json_str = '{"id": 1, "label": "Person", "properties": {}}'
        result = AgTypeParser.parse(json_str)
        
        assert result["type"] == "node"
        assert result["id"] == "1"

    def test_parse_invalid_json_string(self):
        """Test parsing invalid JSON string."""
        invalid_json = "not valid json"
        result = AgTypeParser.parse(invalid_json)
        
        # Should return the string as-is
        assert result == "not valid json"


class TestGraphElementExtraction:
    """Tests for graph element extraction."""

    def test_extract_nodes_only(self):
        """Test extracting nodes from results."""
        rows = [
            {"result": {"id": 1, "label": "Person", "properties": {}}},
            {"result": {"id": 2, "label": "Person", "properties": {}}},
        ]
        
        result = AgTypeParser.extract_graph_elements(rows)
        
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 0
        assert len(result["other"]) == 0

    def test_extract_edges_only(self):
        """Test extracting edges from results."""
        rows = [
            {
                "result": {
                    "id": 1,
                    "label": "KNOWS",
                    "start_id": 10,
                    "end_id": 20,
                    "properties": {},
                }
            }
        ]
        
        result = AgTypeParser.extract_graph_elements(rows)
        
        assert len(result["nodes"]) == 0
        assert len(result["edges"]) == 1
        assert len(result["other"]) == 0

    def test_extract_mixed_elements(self):
        """Test extracting mixed nodes and edges."""
        rows = [
            {"result": {"id": 1, "label": "Person", "properties": {}}},
            {
                "result": {
                    "id": 1,
                    "label": "KNOWS",
                    "start_id": 1,
                    "end_id": 2,
                    "properties": {},
                }
            },
            {"result": {"id": 2, "label": "Person", "properties": {}}},
        ]
        
        result = AgTypeParser.extract_graph_elements(rows)
        
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1
        assert len(result["other"]) == 0

    def test_extract_duplicate_nodes(self):
        """Test that duplicate nodes are not added."""
        rows = [
            {"result": {"id": 1, "label": "Person", "properties": {}}},
            {"result": {"id": 1, "label": "Person", "properties": {}}},  # Duplicate
        ]
        
        result = AgTypeParser.extract_graph_elements(rows)
        
        # Should only have one node
        assert len(result["nodes"]) == 1

    def test_extract_duplicate_edges(self):
        """Test that duplicate edges are not added."""
        rows = [
            {
                "result": {
                    "id": 1,
                    "label": "KNOWS",
                    "start_id": 10,
                    "end_id": 20,
                    "properties": {},
                }
            },
            {
                "result": {
                    "id": 1,
                    "label": "KNOWS",
                    "start_id": 10,
                    "end_id": 20,
                    "properties": {},
                }
            },  # Duplicate
        ]
        
        result = AgTypeParser.extract_graph_elements(rows)
        
        # Should only have one edge
        assert len(result["edges"]) == 1

    def test_extract_non_graph_elements(self):
        """Test extracting non-graph elements."""
        rows = [
            {"result": {"id": 1, "label": "Person", "properties": {}}},
            {"result": "scalar_value"},
            {"result": {"key": "value"}},  # Regular dict, not graph element
        ]
        
        result = AgTypeParser.extract_graph_elements(rows)
        
        assert len(result["nodes"]) == 1
        assert len(result["edges"]) == 0
        assert len(result["other"]) == 2  # Scalar and regular dict

    def test_extract_from_multiple_columns(self):
        """Test extracting from multiple columns."""
        rows = [
            {
                "node": {"id": 1, "label": "Person", "properties": {}},
                "edge": {
                    "id": 1,
                    "label": "KNOWS",
                    "start_id": 1,
                    "end_id": 2,
                    "properties": {},
                },
            }
        ]
        
        result = AgTypeParser.extract_graph_elements(rows)
        
        assert len(result["nodes"]) == 1
        assert len(result["edges"]) == 1

    def test_extract_empty_rows(self):
        """Test extracting from empty rows."""
        rows = []
        result = AgTypeParser.extract_graph_elements(rows)
        
        assert len(result["nodes"]) == 0
        assert len(result["edges"]) == 0
        assert len(result["other"]) == 0

    def test_extract_complex_nested(self):
        """Test extracting from complex nested structures."""
        rows = [
            {
                "result": [
                    {"id": 1, "label": "Person", "properties": {}},
                    {
                        "id": 1,
                        "label": "KNOWS",
                        "start_id": 1,
                        "end_id": 2,
                        "properties": {},
                    },
                ]
            }
        ]
        
        result = AgTypeParser.extract_graph_elements(rows)
        
        assert len(result["nodes"]) == 1
        assert len(result["edges"]) == 1

