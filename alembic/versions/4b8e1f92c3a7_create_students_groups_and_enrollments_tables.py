"""create students groups and enrollments tables

Revision ID: 4b8e1f92c3a7
Revises: 2cfd4c6d5251
Create Date: 2026-10-28 19:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4b8e1f92c3a7'
down_revision: Union[str, Sequence[str], None] = '2cfd4c6d5251'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create students table
    op.create_table(
        'students',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=False),
        sa.Column('grade_level', sa.String(length=20), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('parent_name', sa.String(length=120), nullable=True),
        sa.Column('parent_phone', sa.String(length=20), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_students_id', 'students', ['id'], unique=False)
    op.create_index('ix_students_teacher_id', 'students', ['teacher_id'], unique=False)
    op.create_index('ix_students_full_name', 'students', ['full_name'], unique=False)
    op.create_index('ix_students_grade_level', 'students', ['grade_level'], unique=False)
    op.create_index('ix_students_phone', 'students', ['phone'], unique=False)
    op.create_index('ix_students_parent_phone', 'students', ['parent_phone'], unique=False)
    op.create_index('ix_students_is_deleted', 'students', ['is_deleted'], unique=False)

    # 2. Create groups table
    op.create_table(
        'groups',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('grade_level', sa.String(length=20), nullable=False),
        sa.Column('subject', sa.String(length=100), nullable=True),
        sa.Column('schedule_details', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_groups_id', 'groups', ['id'], unique=False)
    op.create_index('ix_groups_teacher_id', 'groups', ['teacher_id'], unique=False)
    op.create_index('ix_groups_name', 'groups', ['name'], unique=False)
    op.create_index('ix_groups_grade_level', 'groups', ['grade_level'], unique=False)
    op.create_index('ix_groups_is_deleted', 'groups', ['is_deleted'], unique=False)

    # 3. Create group_students association table
    op.create_table(
        'group_students',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('student_id', sa.String(length=36), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_id', 'student_id', name='uq_group_student_membership')
    )
    op.create_index('ix_group_students_id', 'group_students', ['id'], unique=False)
    op.create_index('ix_group_students_teacher_id', 'group_students', ['teacher_id'], unique=False)
    op.create_index('ix_group_students_group_id', 'group_students', ['group_id'], unique=False)
    op.create_index('ix_group_students_student_id', 'group_students', ['student_id'], unique=False)
    op.create_index('ix_group_students_is_deleted', 'group_students', ['is_deleted'], unique=False)
    op.create_index('ix_group_students_tenant', 'group_students', ['teacher_id', 'group_id', 'student_id'], unique=False)


def downgrade() -> None:
    op.drop_table('group_students')
    op.drop_table('groups')
    op.drop_table('students')
