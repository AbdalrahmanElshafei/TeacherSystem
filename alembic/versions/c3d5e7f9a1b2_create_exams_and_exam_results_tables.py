"""create exams and exam results tables

Revision ID: c3d5e7f9a1b2
Revises: 9c2f5a81e7d4
Create Date: 2026-10-28 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d5e7f9a1b2'
down_revision: Union[str, Sequence[str], None] = '9c2f5a81e7d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add granular exam permissions to assistants
    with op.batch_alter_table('assistants') as batch_op:
        batch_op.add_column(sa.Column('can_view_grades', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('can_manage_exams', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    # 2. Create exams table
    op.create_table(
        'exams',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('exam_date', sa.String(length=10), nullable=False),
        sa.Column('max_score', sa.Float(), nullable=False),
        sa.Column('passing_score', sa.Float(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'scheduled'")),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_exams_id', 'exams', ['id'], unique=False)
    op.create_index('ix_exams_teacher_id', 'exams', ['teacher_id'], unique=False)
    op.create_index('ix_exams_group_id', 'exams', ['group_id'], unique=False)
    op.create_index('ix_exams_title', 'exams', ['title'], unique=False)
    op.create_index('ix_exams_exam_date', 'exams', ['exam_date'], unique=False)
    op.create_index('ix_exams_status', 'exams', ['status'], unique=False)
    op.create_index('ix_exams_is_deleted', 'exams', ['is_deleted'], unique=False)

    # 3. Create exam_results table
    op.create_table(
        'exam_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('exam_id', sa.String(length=36), nullable=False),
        sa.Column('student_id', sa.String(length=36), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'attended'")),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('recorded_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('recorded_by_user_type', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('exam_id', 'student_id', name='uq_exam_student_result')
    )
    op.create_index('ix_exam_results_id', 'exam_results', ['id'], unique=False)
    op.create_index('ix_exam_results_teacher_id', 'exam_results', ['teacher_id'], unique=False)
    op.create_index('ix_exam_results_exam_id', 'exam_results', ['exam_id'], unique=False)
    op.create_index('ix_exam_results_student_id', 'exam_results', ['student_id'], unique=False)
    op.create_index('ix_exam_results_status', 'exam_results', ['status'], unique=False)
    op.create_index('ix_exam_results_is_deleted', 'exam_results', ['is_deleted'], unique=False)
    op.create_index('ix_exam_result_tenant', 'exam_results', ['teacher_id', 'exam_id', 'student_id'], unique=False)
    op.create_index('ix_exam_result_status', 'exam_results', ['exam_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_table('exam_results')
    op.drop_table('exams')
    with op.batch_alter_table('assistants') as batch_op:
        batch_op.drop_column('can_manage_exams')
        batch_op.drop_column('can_view_grades')
