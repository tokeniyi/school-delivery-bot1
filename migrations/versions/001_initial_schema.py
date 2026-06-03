"""initial_schema

Revision ID: 001
Revises: 
Create Date: 2026-06-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===== users =====
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=False, server_default='Student'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'], unique=True)

    # ===== student_requests =====
    op.create_table(
        'student_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('item_description', sa.String(), nullable=False),
        sa.Column('pickup_location', sa.String(), nullable=False),
        sa.Column('destination_school', sa.String(), nullable=False),
        sa.Column('delivery_date', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_student_requests_status', 'student_requests', ['status'])
    op.create_index('ix_student_requests_delivery_date', 'student_requests', ['delivery_date'])
    op.create_index('ix_student_requests_destination_school', 'student_requests', ['destination_school'])
    op.create_index('ix_student_requests_pickup_location', 'student_requests', ['pickup_location'])

    # ===== parent_travels =====
    op.create_table(
        'parent_travels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('origin_location', sa.String(), nullable=False),
        sa.Column('destination_school', sa.String(), nullable=False),
        sa.Column('travel_date', sa.String(), nullable=False),
        sa.Column('can_carry_packages', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='available'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_parent_travels_status', 'parent_travels', ['status'])
    op.create_index('ix_parent_travels_travel_date', 'parent_travels', ['travel_date'])
    op.create_index('ix_parent_travels_destination_school', 'parent_travels', ['destination_school'])
    op.create_index('ix_parent_travels_origin_location', 'parent_travels', ['origin_location'])

    # ===== matches =====
    op.create_table(
        'matches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_request_id', sa.Integer(), nullable=False),
        sa.Column('parent_travel_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending_review'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['student_request_id'], ['student_requests.id']),
        sa.ForeignKeyConstraint(['parent_travel_id'], ['parent_travels.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_matches_status', 'matches', ['status'])
    op.create_index('ix_matches_student_request_id', 'matches', ['student_request_id'])
    op.create_index('ix_matches_parent_travel_id', 'matches', ['parent_travel_id'])
    op.create_index('ix_matches_created_at', 'matches', ['created_at'])

    # ===== audit_logs =====
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.BigInteger(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_logs_admin_id', 'audit_logs', ['admin_id'])
    op.create_index('ix_audit_logs_entity_type_entity_id', 'audit_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('matches')
    op.drop_table('parent_travels')
    op.drop_table('student_requests')
    op.drop_table('users')
