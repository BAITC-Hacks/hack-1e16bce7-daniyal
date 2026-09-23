"""Import replay journal and transactional completion receipts."""
from alembic import op
import sqlalchemy as sa

revision = "0002_backend_workflows"
down_revision = "0001_dataset"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("dataset_import_batches",
        sa.Column("fingerprint", sa.String(64), primary_key=True),
        sa.Column("counts", sa.JSON(), nullable=False))
    op.add_column("activity_history", sa.Column("completed_on", sa.Date(), nullable=True))
    op.add_column("activity_history", sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("activity_history", sa.Column("session_date", sa.Date(), nullable=True))
    op.create_table("completion_receipts",
        sa.Column("employee_id", sa.String(), sa.ForeignKey("employees.employee_id"), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), primary_key=True),
        sa.Column("event_id", sa.String(), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("record_id", sa.String(), sa.ForeignKey("activity_history.record_id"), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False))


def downgrade():
    op.drop_table("completion_receipts")
    op.drop_column("activity_history", "session_date")
    op.drop_column("activity_history", "simulated")
    op.drop_column("activity_history", "completed_on")
    op.drop_table("dataset_import_batches")
