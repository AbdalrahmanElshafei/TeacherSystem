"""create sessions and attendance tables

Revision ID: 9c2f5a81e7d4
Revises: 4b8e1f92c3a7
Create Date: 2026-10-28 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9c2f5a81e7d4'
down_revision: Union[str, Sequence[str], None] = '4b8e1f92c3a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('session_date', sa.String(length=10), nullable=False),
        sa.Column('start_time', sa.String(length=8), nullable=False),
        sa.Column('end_time', sa.String(length=8), nullable=True),
        sa.Column('location', sa.String(length=150), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'scheduled'")),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sessions_id', 'sessions', ['id'], unique=False)
    op.create_index('ix_sessions_teacher_id', 'sessions', ['teacher_id'], unique=False)
    op.create_index('ix_sessions_group_id', 'sessions', ['group_id'], unique=False)
    op.create_index('ix_sessions_session_date', 'sessions', ['session_date'], unique=False)
    op.create_index('ix_sessions_status', 'sessions', ['status'], unique=False)
    op.create_index('ix_sessions_is_deleted', 'sessions', ['is_deleted'], unique=False)

    # 2. Create attendance table
    op.create_table(
        'attendance',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('student_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('recorded_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('recorded_by_user_type', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'student_id', name='uq_session_student_attendance')
    )
    op.create_index('ix_attendance_id', 'attendance', ['id'], unique=False)
    op.create_index('ix_attendance_teacher_id', 'attendance', ['teacher_id'], unique=False)
    op.create_index('ix_attendance_session_id', 'attendance', ['session_id'], unique=False)
    op.create_index('ix_attendance_student_id', 'attendance', ['student_id'], unique=False)
    op.create_index('ix_attendance_status', 'attendance', ['status'], unique=False)
    op.create_index('ix_attendance_is_deleted', 'attendance', ['is_deleted'], unique=False)
    op.create_index('ix_attendance_tenant', 'attendance', ['teacher_id', 'session_id', 'student_id'], unique=False)
    op.create_index('ix_attendance_session_status', 'attendance', ['session_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_table('attendance')
    op.drop_table('sessions')
