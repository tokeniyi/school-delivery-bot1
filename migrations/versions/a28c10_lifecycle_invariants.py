"""Exclusive allocation and append-only match lifecycle events.

Revision ID: a28c10
Revises: 5196523efe8d
"""
from alembic import op
import sqlalchemy as sa

revision = 'a28c10'
down_revision = '5196523efe8d'
branch_labels = None
depends_on = None


def upgrade():
    # Block writers between the conflict check and unique-index creation.
    # Never select winners, delete approvals or silently repair existing data.
    op.execute('LOCK TABLE matches IN SHARE ROW EXCLUSIVE MODE')
    bind = op.get_bind()
    for column in ('student_request_id', 'parent_travel_id'):
        conflict = bind.execute(sa.text(
            f"SELECT {column} FROM matches WHERE status = 'approved' "
            f"GROUP BY {column} HAVING count(*) > 1 LIMIT 1"
        )).first()
        if conflict:
            raise RuntimeError(
                f'Lifecycle migration blocked: conflicting approved {column}; '
                'requires separately authorized reconciliation. No records changed.'
            )
    op.add_column('matches', sa.Column('review_revision', sa.Integer(), server_default='1', nullable=False))
    op.add_column('matches', sa.Column('closure_reason', sa.String(), nullable=True))
    for name, column in [('request', 'student_request_id'), ('travel', 'parent_travel_id')]:
        op.create_index(f'uq_matches_approved_{name}', 'matches', [column], unique=True,
                        postgresql_where=sa.text("status = 'approved'"))
    op.create_table(
        'match_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('match_id', sa.Integer(), sa.ForeignKey('matches.id'), nullable=False),
        sa.Column('from_status', sa.String(), nullable=True),
        sa.Column('to_status', sa.String(), nullable=False),
        sa.Column('actor_id', sa.BigInteger(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_match_events_match_id', 'match_events', ['match_id'])
    # Capture the known state only; legacy audits remain intact. Do not invent
    # actors or transitions absent from legacy data.
    op.execute("""INSERT INTO match_events
        (match_id, from_status, to_status, actor_id, reason, created_at)
        SELECT id, NULL, status, NULL, 'legacy_state_at_migration',
               COALESCE(reviewed_at, created_at) FROM matches""")


def downgrade():
    # Refuse a lossy downgrade once new lifecycle evidence exists. Restore from
    # an approved backup/process instead of erasing review history.
    bind = op.get_bind()
    op.execute('LOCK TABLE matches, match_events IN SHARE ROW EXCLUSIVE MODE')
    if bind.execute(sa.text(
        "SELECT 1 FROM match_events WHERE reason IS DISTINCT FROM "
        "'legacy_state_at_migration' LIMIT 1"
    )).first():
        raise RuntimeError('Downgrade blocked: would discard lifecycle history')
    op.drop_index('ix_match_events_match_id', table_name='match_events')
    op.drop_table('match_events')
    op.drop_index('uq_matches_approved_travel', table_name='matches')
    op.drop_index('uq_matches_approved_request', table_name='matches')
    op.drop_column('matches', 'closure_reason')
    op.drop_column('matches', 'review_revision')
