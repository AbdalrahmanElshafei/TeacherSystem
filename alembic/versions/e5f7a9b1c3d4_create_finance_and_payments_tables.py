"""create finance and payments tables

Revision ID: e5f7a9b1c3d4
Revises: c3d5e7f9a1b2
Create Date: 2026-10-28 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f7a9b1c3d4'
down_revision: Union[str, Sequence[str], None] = 'c3d5e7f9a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add can_manage_fees permission to assistants table
    with op.batch_alter_table('assistants') as batch_op:
        batch_op.add_column(sa.Column('can_manage_fees', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    # 2. Create group_fee_configs table
    op.create_table(
        'group_fee_configs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('fee_model', sa.String(length=20), nullable=False, server_default='monthly'),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('effective_from', sa.String(length=10), nullable=False),
        sa.Column('effective_to', sa.String(length=10), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('group_fee_configs') as batch_op:
        batch_op.create_index('ix_group_fee_configs_teacher_id', ['teacher_id'], unique=False)
        batch_op.create_index('ix_group_fee_configs_group_id', ['group_id'], unique=False)
        batch_op.create_index('ix_group_fee_configs_fee_model', ['fee_model'], unique=False)
        batch_op.create_index('ix_group_fee_configs_is_active', ['is_active'], unique=False)
        batch_op.create_index('ix_group_fee_configs_tenant', ['teacher_id', 'group_id', 'is_active'], unique=False)

    # 3. Create student_dues table
    op.create_table(
        'student_dues',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('student_id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('fee_config_id', sa.String(length=36), nullable=True),
        sa.Column('charge_type', sa.String(length=20), nullable=False),
        sa.Column('billing_month', sa.String(length=7), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('paid_amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='unpaid'),
        sa.Column('due_date', sa.String(length=10), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('void_reason', sa.Text(), nullable=True),
        sa.Column('voided_at', sa.DateTime(), nullable=True),
        sa.Column('voided_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['fee_config_id'], ['group_fee_configs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'group_id', 'billing_month', name='uq_student_group_monthly_due'),
        sa.UniqueConstraint('student_id', 'session_id', name='uq_student_session_charge')
    )
    with op.batch_alter_table('student_dues') as batch_op:
        batch_op.create_index('ix_student_dues_teacher_id', ['teacher_id'], unique=False)
        batch_op.create_index('ix_student_dues_student_id', ['student_id'], unique=False)
        batch_op.create_index('ix_student_dues_group_id', ['group_id'], unique=False)
        batch_op.create_index('ix_student_dues_fee_config_id', ['fee_config_id'], unique=False)
        batch_op.create_index('ix_student_dues_charge_type', ['charge_type'], unique=False)
        batch_op.create_index('ix_student_dues_billing_month', ['billing_month'], unique=False)
        batch_op.create_index('ix_student_dues_session_id', ['session_id'], unique=False)
        batch_op.create_index('ix_student_dues_status', ['status'], unique=False)
        batch_op.create_index('ix_student_dues_tenant_student', ['teacher_id', 'student_id', 'status'], unique=False)
        batch_op.create_index('ix_student_dues_tenant_group_month', ['teacher_id', 'group_id', 'billing_month'], unique=False)
        batch_op.create_index('ix_student_dues_tenant_status', ['teacher_id', 'status'], unique=False)

    # 4. Create cash_payments table
    op.create_table(
        'cash_payments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('student_id', sa.String(length=36), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('allocated_amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('payment_date', sa.String(length=10), nullable=False),
        sa.Column('payment_method', sa.String(length=20), nullable=False, server_default='cash'),
        sa.Column('receipt_number', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('recorded_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('recorded_by_user_type', sa.String(length=20), nullable=True),
        sa.Column('is_reversed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('reversal_reason', sa.Text(), nullable=True),
        sa.Column('reversed_at', sa.DateTime(), nullable=True),
        sa.Column('reversed_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('cash_payments') as batch_op:
        batch_op.create_index('ix_cash_payments_teacher_id', ['teacher_id'], unique=False)
        batch_op.create_index('ix_cash_payments_student_id', ['student_id'], unique=False)
        batch_op.create_index('ix_cash_payments_payment_date', ['payment_date'], unique=False)
        batch_op.create_index('ix_cash_payments_receipt_number', ['receipt_number'], unique=False)
        batch_op.create_index('ix_cash_payments_is_reversed', ['is_reversed'], unique=False)
        batch_op.create_index('ix_cash_payments_tenant_date', ['teacher_id', 'payment_date'], unique=False)
        batch_op.create_index('ix_cash_payments_tenant_student', ['teacher_id', 'student_id', 'payment_date'], unique=False)
        batch_op.create_index('ix_cash_payments_receipt', ['teacher_id', 'receipt_number'], unique=False)

    # 5. Create payment_allocations table
    op.create_table(
        'payment_allocations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('payment_id', sa.String(length=36), nullable=False),
        sa.Column('due_id', sa.String(length=36), nullable=False),
        sa.Column('allocated_amount', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['due_id'], ['student_dues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payment_id'], ['cash_payments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('payment_allocations') as batch_op:
        batch_op.create_index('ix_payment_allocations_teacher_id', ['teacher_id'], unique=False)
        batch_op.create_index('ix_payment_allocations_payment_id', ['payment_id'], unique=False)
        batch_op.create_index('ix_payment_allocations_due_id', ['due_id'], unique=False)
        batch_op.create_index('ix_allocations_tenant_due', ['teacher_id', 'due_id'], unique=False)
        batch_op.create_index('ix_allocations_tenant_payment', ['teacher_id', 'payment_id'], unique=False)

    # 6. Create financial_audit_logs table
    op.create_table(
        'financial_audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('actor_user_id', sa.String(length=36), nullable=True),
        sa.Column('actor_user_type', sa.String(length=20), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('financial_audit_logs') as batch_op:
        batch_op.create_index('ix_financial_audit_logs_teacher_id', ['teacher_id'], unique=False)
        batch_op.create_index('ix_financial_audit_logs_action', ['action'], unique=False)
        batch_op.create_index('ix_financial_audit_tenant_action', ['teacher_id', 'action', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('financial_audit_logs')
    op.drop_table('payment_allocations')
    op.drop_table('cash_payments')
    op.drop_table('student_dues')
    op.drop_table('group_fee_configs')
    with op.batch_alter_table('assistants') as batch_op:
        batch_op.drop_column('can_manage_fees')
