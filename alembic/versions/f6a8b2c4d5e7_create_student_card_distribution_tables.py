"""create student card distribution tables

Revision ID: f6a8b2c4d5e7
Revises: e5f7a9b1c3d4
Create Date: 2026-10-29 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f6a8b2c4d5e7'
down_revision: Union[str, Sequence[str], None] = 'e5f7a9b1c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create student_card_distributions table
    op.create_table(
        'student_card_distributions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('student_id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='not_sent'),
        sa.Column('card_generated_at', sa.DateTime(), nullable=True),
        sa.Column('share_opened_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_sent_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_by_id', sa.String(length=36), nullable=True),
        sa.Column('confirmed_by_name', sa.String(length=120), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('student_card_distributions', schema=None) as batch_op:
        batch_op.create_index('ix_student_card_distributions_id', ['id'], unique=False)
        batch_op.create_index('ix_student_card_distributions_teacher_id', ['teacher_id'], unique=False)
        batch_op.create_index('ix_student_card_distributions_student_id', ['student_id'], unique=False)
        batch_op.create_index('ix_student_card_distributions_group_id', ['group_id'], unique=False)
        batch_op.create_index('ix_student_card_distributions_status', ['status'], unique=False)
        batch_op.create_index('ix_student_card_distributions_is_deleted', ['is_deleted'], unique=False)
        batch_op.create_index('ix_student_card_dist_tenant', ['teacher_id', 'student_id'], unique=False)
        batch_op.create_index('ix_student_card_dist_group', ['teacher_id', 'group_id'], unique=False)
        batch_op.create_index('ix_student_card_dist_status', ['teacher_id', 'status'], unique=False)

    # 2. Create group_card_exports table
    op.create_table(
        'group_card_exports',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('exported_by_id', sa.String(length=36), nullable=False),
        sa.Column('exported_by_name', sa.String(length=120), nullable=True),
        sa.Column('student_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('export_type', sa.String(length=30), nullable=False, server_default='group_pdf'),
        sa.Column('exported_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('group_card_exports', schema=None) as batch_op:
        batch_op.create_index('ix_group_card_exports_id', ['id'], unique=False)
        batch_op.create_index('ix_group_card_exports_teacher_id', ['teacher_id'], unique=False)
        batch_op.create_index('ix_group_card_exports_group_id', ['group_id'], unique=False)
        batch_op.create_index('ix_group_card_exports_exported_at', ['exported_at'], unique=False)
        batch_op.create_index('ix_group_card_exports_is_deleted', ['is_deleted'], unique=False)
        batch_op.create_index('ix_group_card_exports_lookup', ['teacher_id', 'group_id', 'exported_at'], unique=False)


def downgrade() -> None:
    op.drop_table('group_card_exports')
    op.drop_table('student_card_distributions')
