"""Initial schema for teachers assistants and sessions

Revision ID: 2cfd4c6d5251
Revises: 
Create Date: 2026-10-27 21:59:04.419461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2cfd4c6d5251'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Initial schema for teachers, assistants, and user_sessions."""
    # 1. Create teachers table
    op.create_table(
        'teachers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_teachers_id', 'teachers', ['id'], unique=False)
    op.create_index('ix_teachers_username', 'teachers', ['username'], unique=True)
    op.create_index('ix_teachers_is_deleted', 'teachers', ['is_deleted'], unique=False)

    # 2. Create assistants table
    op.create_table(
        'assistants',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('can_mark_attendance', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('can_view_attendance', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('can_manage_students', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('can_enter_grades', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('can_collect_cash', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('can_view_student_payment_history', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('can_view_financial_analytics', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('can_request_messages', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_assistants_id', 'assistants', ['id'], unique=False)
    op.create_index('ix_assistants_teacher_id', 'assistants', ['teacher_id'], unique=False)
    op.create_index('ix_assistants_username', 'assistants', ['username'], unique=True)
    op.create_index('ix_assistants_is_deleted', 'assistants', ['is_deleted'], unique=False)

    # 3. Create user_sessions table
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_token', sa.String(length=128), nullable=False),
        sa.Column('user_type', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('csrf_token', sa.String(length=64), nullable=False),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_sessions_id', 'user_sessions', ['id'], unique=False)
    op.create_index('ix_user_sessions_session_token', 'user_sessions', ['session_token'], unique=True)
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'], unique=False)
    op.create_index('ix_user_sessions_teacher_id', 'user_sessions', ['teacher_id'], unique=False)
    op.create_index('ix_user_sessions_expires_at', 'user_sessions', ['expires_at'], unique=False)
    op.create_index('ix_user_sessions_is_revoked', 'user_sessions', ['is_revoked'], unique=False)
    op.create_index('ix_user_sessions_is_deleted', 'user_sessions', ['is_deleted'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_user_sessions_is_deleted', table_name='user_sessions')
    op.drop_index('ix_user_sessions_is_revoked', table_name='user_sessions')
    op.drop_index('ix_user_sessions_expires_at', table_name='user_sessions')
    op.drop_index('ix_user_sessions_teacher_id', table_name='user_sessions')
    op.drop_index('ix_user_sessions_user_id', table_name='user_sessions')
    op.drop_index('ix_user_sessions_session_token', table_name='user_sessions')
    op.drop_index('ix_user_sessions_id', table_name='user_sessions')
    op.drop_table('user_sessions')

    op.drop_index('ix_assistants_is_deleted', table_name='assistants')
    op.drop_index('ix_assistants_username', table_name='assistants')
    op.drop_index('ix_assistants_teacher_id', table_name='assistants')
    op.drop_index('ix_assistants_id', table_name='assistants')
    op.drop_table('assistants')

    op.drop_index('ix_teachers_is_deleted', table_name='teachers')
    op.drop_index('ix_teachers_username', table_name='teachers')
    op.drop_index('ix_teachers_id', table_name='teachers')
    op.drop_table('teachers')
