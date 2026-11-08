"""PayPal's own fees: kept per capture and per payout item, so the books show Maxx's real margin."""

import sqlalchemy as sa

from alembic import op

revision = "0012_paypal_fees"
down_revision = "0011_ai_budget"
branch_labels = None
depends_on = None

TABLES = ("payments", "payouts")


def upgrade():
    bind = op.get_bind()
    for table in TABLES:
        existing = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        if "paypal_fee" not in existing:
            op.add_column(table, sa.Column("paypal_fee", sa.Numeric(12, 2), nullable=True))


def downgrade():
    for table in TABLES:
        op.drop_column(table, "paypal_fee")
