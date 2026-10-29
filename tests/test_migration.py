import sqlite3
from pathlib import Path
from alembic.config import Config
from alembic import command
from sqlalchemy import inspect, create_engine
from app.database import Base
from app.config import DEFAULT_DB_PATH
import app.models

def test_alembic_fresh_migration_on_isolated_db(tmp_path):
    """
    Verify that Alembic's initial migration builds a fresh database from scratch,
    with exact tables, columns, indexes, and constraints matching Base.metadata,
    without touching the project's actual database.
    """
    # 1. Setup isolated temporary SQLite DB path
    temp_db_file = tmp_path / "fresh_migration_test.db"
    assert not temp_db_file.exists()
    temp_db_url = f"sqlite:///{temp_db_file.as_posix()}"

    # Explicit Safety Check: Ensure connection string is strictly the temporary DB
    assert "fresh_migration_test.db" in temp_db_url
    assert str(DEFAULT_DB_PATH) not in temp_db_url

    # Record actual database state before running test
    orig_db_stat = DEFAULT_DB_PATH.stat() if DEFAULT_DB_PATH.exists() else None

    # 2. Configure Alembic to point strictly to the temporary DB
    alembic_ini_path = Path("C:/TeacherSystem/alembic.ini")
    assert alembic_ini_path.exists()
    
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", temp_db_url)

    # 3. Execute upgrade head on the isolated DB
    command.upgrade(alembic_cfg, "head")

    assert temp_db_file.exists()
    assert temp_db_file.stat().st_size > 0

    # 4. Deep Inspection using SQLAlchemy Inspector on the isolated DB
    temp_engine = create_engine(temp_db_url)
    inspector = inspect(temp_engine)

    created_tables = set(inspector.get_table_names())
    expected_tables = {
        "teachers", "assistants", "user_sessions",
        "students", "groups", "group_students",
        "sessions", "attendance", "exams", "exam_results",
        "group_fee_configs", "student_dues", "cash_payments", "payment_allocations", "financial_audit_logs",
        "student_card_distributions", "group_card_exports",
        "alembic_version"
    }
    assert expected_tables.issubset(created_tables), f"Missing tables. Got: {created_tables}"

    # Verify each model table's columns and primary keys against Base.metadata
    for table_name in [
        "teachers", "assistants", "user_sessions", "students", "groups", "group_students",
        "sessions", "attendance", "exams", "exam_results",
        "group_fee_configs", "student_dues", "cash_payments", "payment_allocations", "financial_audit_logs",
        "student_card_distributions", "group_card_exports"
    ]:
        model_table = Base.metadata.tables[table_name]
        db_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
        
        # Check all expected columns exist with matching nullability
        for model_col in model_table.columns:
            assert model_col.name in db_columns, f"Column {model_col.name} missing in {table_name}"
            db_col = db_columns[model_col.name]
            assert db_col["nullable"] == model_col.nullable, (
                f"Nullable mismatch for {table_name}.{model_col.name}: "
                f"expected {model_col.nullable}, got {db_col['nullable']}"
            )

        # Check primary keys
        pk_constraint = inspector.get_pk_constraint(table_name)
        assert pk_constraint["constrained_columns"] == ["id"], (
            f"PK mismatch on {table_name}: {pk_constraint}"
        )

    # Check Foreign Keys on assistants
    assistant_fks = inspector.get_foreign_keys("assistants")
    assert len(assistant_fks) == 1
    fk = assistant_fks[0]
    assert fk["referred_table"] == "teachers"
    assert fk["referred_columns"] == ["id"]
    assert fk["constrained_columns"] == ["teacher_id"]

    # Check that user_sessions has NO foreign keys (matches model exactly)
    session_fks = inspector.get_foreign_keys("user_sessions")
    assert len(session_fks) == 0, f"Expected 0 FKs on user_sessions, found: {session_fks}"

    # Check Indexes using SQLite PRAGMA index_list directly
    conn = sqlite3.connect(str(temp_db_file))
    cursor = conn.cursor()

    # Teachers indexes
    cursor.execute("PRAGMA index_list(teachers)")
    teacher_indexes = {row[1]: bool(row[2]) for row in cursor.fetchall()}  # name: is_unique
    assert "ix_teachers_username" in teacher_indexes
    assert teacher_indexes["ix_teachers_username"] is True  # Unique index
    assert "ix_teachers_id" in teacher_indexes
    assert "ix_teachers_is_deleted" in teacher_indexes

    # Assistants indexes
    cursor.execute("PRAGMA index_list(assistants)")
    assistant_indexes = {row[1]: bool(row[2]) for row in cursor.fetchall()}
    assert "ix_assistants_username" in assistant_indexes
    assert assistant_indexes["ix_assistants_username"] is True
    assert "ix_assistants_teacher_id" in assistant_indexes
    assert "ix_assistants_id" in assistant_indexes
    assert "ix_assistants_is_deleted" in assistant_indexes

    # UserSessions indexes
    cursor.execute("PRAGMA index_list(user_sessions)")
    session_indexes = {row[1]: bool(row[2]) for row in cursor.fetchall()}
    assert "ix_user_sessions_session_token" in session_indexes
    assert session_indexes["ix_user_sessions_session_token"] is True
    assert "ix_user_sessions_user_id" in session_indexes
    assert "ix_user_sessions_teacher_id" in session_indexes
    assert "ix_user_sessions_expires_at" in session_indexes
    assert "ix_user_sessions_is_revoked" in session_indexes
    assert "ix_user_sessions_is_deleted" in session_indexes

    conn.close()
    temp_engine.dispose()

    # 5. Test downgrade base on the temporary database (drops tables)
    command.downgrade(alembic_cfg, "base")

    temp_engine_after_down = create_engine(temp_db_url)
    inspector_down = inspect(temp_engine_after_down)
    tables_after_down = set(inspector_down.get_table_names())
    assert "teachers" not in tables_after_down
    assert "assistants" not in tables_after_down
    assert "user_sessions" not in tables_after_down
    assert "students" not in tables_after_down
    assert "groups" not in tables_after_down
    assert "group_students" not in tables_after_down
    assert "sessions" not in tables_after_down
    assert "attendance" not in tables_after_down
    assert "exams" not in tables_after_down
    assert "exam_results" not in tables_after_down
    assert "group_fee_configs" not in tables_after_down
    assert "student_dues" not in tables_after_down
    assert "cash_payments" not in tables_after_down
    assert "payment_allocations" not in tables_after_down
    assert "financial_audit_logs" not in tables_after_down
    temp_engine_after_down.dispose()

    # 6. Safety Verification: Ensure project DB was never touched
    if orig_db_stat:
        current_stat = DEFAULT_DB_PATH.stat()
        assert current_stat.st_mtime == orig_db_stat.st_mtime, "CRITICAL: Project DB was touched!"
        assert current_stat.st_size == orig_db_stat.st_size, "CRITICAL: Project DB size changed!"


def test_sequential_migration_upgrade_and_downgrade_on_isolated_db(tmp_path):
    """
    Explicitly test sequential step-by-step upgrade and downgrade on an isolated file-based DB:
    1. Upgrade to current production revision '2cfd4c6d5251'.
    2. Upgrade to pending revision '4b8e1f92c3a7' (Students & Groups).
    3. Upgrade to pending revision '9c2f5a81e7d4' (Sessions & Attendance).
    4. Verify tables, foreign keys, indexes, and constraints.
    5. Step-by-step downgrade back to '4b8e1f92c3a7' then '2cfd4c6d5251'.
    6. Re-upgrade back to 'head'.
    7. Guarantee project DB is untouched.
    """
    temp_db_file = tmp_path / "sequential_migration_test.db"
    assert not temp_db_file.exists()
    temp_db_url = f"sqlite:///{temp_db_file.as_posix()}"

    orig_db_stat = DEFAULT_DB_PATH.stat() if DEFAULT_DB_PATH.exists() else None

    alembic_ini_path = Path("C:/TeacherSystem/alembic.ini")
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", temp_db_url)

    # Step 1: Upgrade to current production revision '2cfd4c6d5251'
    command.upgrade(alembic_cfg, "2cfd4c6d5251")
    eng1 = create_engine(temp_db_url)
    insp1 = inspect(eng1)
    tables1 = set(insp1.get_table_names())
    assert {"teachers", "assistants", "user_sessions", "alembic_version"}.issubset(tables1)
    assert "students" not in tables1
    assert "groups" not in tables1
    assert "sessions" not in tables1
    assert "attendance" not in tables1
    eng1.dispose()

    # Step 2: Upgrade to '4b8e1f92c3a7' (Students & Groups)
    command.upgrade(alembic_cfg, "4b8e1f92c3a7")
    eng2 = create_engine(temp_db_url)
    insp2 = inspect(eng2)
    tables2 = set(insp2.get_table_names())
    assert {"students", "groups", "group_students"}.issubset(tables2)
    assert "sessions" not in tables2
    assert "attendance" not in tables2
    # Verify FKs on group_students
    fks_gs = insp2.get_foreign_keys("group_students")
    fk_targets = {fk["referred_table"] for fk in fks_gs}
    assert {"teachers", "groups", "students"}.issubset(fk_targets)
    eng2.dispose()

    # Step 3: Upgrade to '9c2f5a81e7d4' (Sessions & Attendance)
    command.upgrade(alembic_cfg, "9c2f5a81e7d4")
    eng3 = create_engine(temp_db_url)
    insp3 = inspect(eng3)
    tables3 = set(insp3.get_table_names())
    assert {"sessions", "attendance"}.issubset(tables3)
    assert "exams" not in tables3
    assert "exam_results" not in tables3
    # Verify FKs on attendance
    fks_att = insp3.get_foreign_keys("attendance")
    att_fk_targets = {fk["referred_table"] for fk in fks_att}
    assert {"teachers", "sessions", "students"}.issubset(att_fk_targets)
    # Verify unique constraint on attendance (session_id, student_id)
    uqs_att = insp3.get_unique_constraints("attendance")
    uq_names = [uq["name"] for uq in uqs_att]
    assert "uq_session_student_attendance" in uq_names
    eng3.dispose()

    # Step 4: Upgrade to 'c3d5e7f9a1b2' (Exams & Grades)
    command.upgrade(alembic_cfg, "c3d5e7f9a1b2")
    eng4 = create_engine(temp_db_url)
    insp4 = inspect(eng4)
    tables4 = set(insp4.get_table_names())
    assert {"exams", "exam_results"}.issubset(tables4)
    # Verify FKs on exams
    fks_ex = insp4.get_foreign_keys("exams")
    ex_fk_targets = {fk["referred_table"] for fk in fks_ex}
    assert {"teachers", "groups"}.issubset(ex_fk_targets)
    # Verify FKs on exam_results
    fks_res = insp4.get_foreign_keys("exam_results")
    res_fk_targets = {fk["referred_table"] for fk in fks_res}
    assert {"teachers", "exams", "students"}.issubset(res_fk_targets)
    # Verify unique constraint on exam_results (exam_id, student_id)
    uqs_res = insp4.get_unique_constraints("exam_results")
    res_uq_names = [uq["name"] for uq in uqs_res]
    assert "uq_exam_student_result" in res_uq_names
    eng4.dispose()

    # Step 5: Upgrade to 'e5f7a9b1c3d4' (Finance & Payments)
    command.upgrade(alembic_cfg, "e5f7a9b1c3d4")
    eng5 = create_engine(temp_db_url)
    insp5 = inspect(eng5)
    tables5 = set(insp5.get_table_names())
    assert {"group_fee_configs", "student_dues", "cash_payments", "payment_allocations", "financial_audit_logs"}.issubset(tables5)
    # Verify FKs on student_dues
    fks_due = insp5.get_foreign_keys("student_dues")
    due_fk_targets = {fk["referred_table"] for fk in fks_due}
    assert {"teachers", "students", "groups"}.issubset(due_fk_targets)
    # Verify unique constraint on student_dues
    uqs_due = insp5.get_unique_constraints("student_dues")
    due_uq_names = [uq["name"] for uq in uqs_due]
    assert "uq_student_group_monthly_due" in due_uq_names
    assert "uq_student_session_charge" in due_uq_names
    # Verify indexes on cash_payments
    indexes_pay = {idx["name"] for idx in insp5.get_indexes("cash_payments")}
    assert "ix_cash_payments_receipt_number" in indexes_pay
    assert "ix_cash_payments_receipt" in indexes_pay
    eng5.dispose()

    # Step 6: Upgrade to 'f6a8b2c4d5e7' (Student Card Distribution)
    command.upgrade(alembic_cfg, "f6a8b2c4d5e7")
    eng6 = create_engine(temp_db_url)
    insp6 = inspect(eng6)
    tables6 = set(insp6.get_table_names())
    assert {"student_card_distributions", "group_card_exports"}.issubset(tables6)
    # Verify FKs on student_card_distributions
    fks_dist = insp6.get_foreign_keys("student_card_distributions")
    dist_fk_targets = {fk["referred_table"] for fk in fks_dist}
    assert {"teachers", "students", "groups"}.issubset(dist_fk_targets)
    eng6.dispose()

    # Step 7: Downgrade to 'e5f7a9b1c3d4'
    command.downgrade(alembic_cfg, "e5f7a9b1c3d4")
    eng7_down = create_engine(temp_db_url)
    insp7_down = inspect(eng7_down)
    tables7_down = set(insp7_down.get_table_names())
    assert "student_card_distributions" not in tables7_down
    assert "group_card_exports" not in tables7_down
    assert "group_fee_configs" in tables7_down
    assert "student_dues" in tables7_down
    eng7_down.dispose()

    # Step 8: Downgrade to 'c3d5e7f9a1b2'
    command.downgrade(alembic_cfg, "c3d5e7f9a1b2")
    eng6 = create_engine(temp_db_url)
    insp6 = inspect(eng6)
    tables6 = set(insp6.get_table_names())
    assert "group_fee_configs" not in tables6
    assert "student_dues" not in tables6
    assert "cash_payments" not in tables6
    assert "payment_allocations" not in tables6
    assert "financial_audit_logs" not in tables6
    assert "exams" in tables6
    assert "exam_results" in tables6
    eng6.dispose()

    # Step 9: Downgrade to '9c2f5a81e7d4'
    command.downgrade(alembic_cfg, "9c2f5a81e7d4")
    eng7 = create_engine(temp_db_url)
    insp7 = inspect(eng7)
    tables7 = set(insp7.get_table_names())
    assert "exams" not in tables7
    assert "exam_results" not in tables7
    assert "sessions" in tables7
    assert "attendance" in tables7
    eng7.dispose()

    # Step 8: Downgrade to '4b8e1f92c3a7'
    command.downgrade(alembic_cfg, "4b8e1f92c3a7")
    eng8 = create_engine(temp_db_url)
    insp8 = inspect(eng8)
    tables8 = set(insp8.get_table_names())
    assert "sessions" not in tables8
    assert "attendance" not in tables8
    assert "students" in tables8
    assert "groups" in tables8
    eng8.dispose()

    # Step 9: Downgrade to '2cfd4c6d5251'
    command.downgrade(alembic_cfg, "2cfd4c6d5251")
    eng9 = create_engine(temp_db_url)
    insp9 = inspect(eng9)
    tables9 = set(insp9.get_table_names())
    assert "students" not in tables9
    assert "groups" not in tables9
    assert "teachers" in tables9
    assert "assistants" in tables9
    eng9.dispose()

    # Step 10: Re-upgrade to 'head'
    command.upgrade(alembic_cfg, "head")
    eng10 = create_engine(temp_db_url)
    insp10 = inspect(eng10)
    tables10 = set(insp10.get_table_names())
    assert {
        "teachers", "assistants", "user_sessions", "students", "groups", "group_students",
        "sessions", "attendance", "exams", "exam_results",
        "group_fee_configs", "student_dues", "cash_payments", "payment_allocations", "financial_audit_logs"
    }.issubset(tables10)
    eng10.dispose()

    # Safety check
    if orig_db_stat:
        current_stat = DEFAULT_DB_PATH.stat()
        assert current_stat.st_mtime == orig_db_stat.st_mtime, "CRITICAL: Project DB was touched!"

