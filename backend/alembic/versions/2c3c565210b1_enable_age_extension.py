"""enable age extension

Ensures the Apache AGE extension is present in the target database. This
is the entry point of Kotte's migration chain because every downstream
feature (cypher queries, label indices, graph visualisation) assumes the
`age` extension is installed and `ag_catalog` is on the search path.

`CREATE EXTENSION IF NOT EXISTS` makes this safe to re-run. It's also a
no-op on databases that already have AGE installed, which is the common
case — operators who point Kotte at an existing AGE-backed database will
see `upgrade()` finish instantly without touching anything.

Downgrade is deliberately a no-op: dropping the AGE extension would
cascade-delete every graph in the database, which is a data-loss
operation that should never happen via a routine `alembic downgrade`.
Operators who really want to uninstall AGE can do it manually.

Revision ID: 2c3c565210b1
Revises:
Create Date: 2026-04-20 22:37:06.058193

"""

from typing import Sequence, Union

from alembic import op

revision: str = "2c3c565210b1"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Install Apache AGE if not already present."""
    op.execute("CREATE EXTENSION IF NOT EXISTS age")


def downgrade() -> None:
    """Intentionally a no-op — see the module docstring."""
    pass
