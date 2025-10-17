from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250922_add_alias_to_purchase_intent'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('purchaseintent') as batch_op:
        batch_op.add_column(sa.Column('alias', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('purchaseintent') as batch_op:
        batch_op.drop_column('alias')

