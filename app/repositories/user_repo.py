import uuid
import threading
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, update, func, insert, literal
from app.models.user import Teacher, Assistant, UserSession
from app.core.security import hash_password, calculate_session_expiry, hash_token

_setup_lock = threading.Lock()

class UserRepository:
    """
    Repository handling User and Session operations.
    Enforces strict teacher-level multi-tenancy at the query level for all operations.
    """

    # --- Teacher Operations ---
    @staticmethod
    def count_teachers(db: Session) -> int:
        """Count existing active teachers (used to determine First-Run Setup status)."""
        return db.query(func.count(Teacher.id)).filter(Teacher.is_deleted == False).scalar() or 0

    @staticmethod
    def create_initial_teacher_atomic(
        db: Session,
        username: str,
        full_name: str,
        phone: str,
        password: str
    ) -> Optional[Teacher]:
        """
        Atomically create the initial primary teacher account.
        Guarantees that even under concurrent setup requests, no more than one initial
        Teacher account can ever be created in the database.
        
        Uses dual-layer synchronization:
        1. Process-level threading lock to serialize incoming setup calls in Python.
        2. Database-level atomic conditional insert (INSERT INTO ... SELECT ... WHERE NOT EXISTS)
           ensuring the database engine itself rejects concurrent inserts if an active teacher exists.
        """
        with _setup_lock:
            # Check within lock first
            if UserRepository.count_teachers(db) > 0:
                return None

            hashed_pwd = hash_password(password)
            now = datetime.now(timezone.utc)
            teacher_id = str(uuid.uuid4())

            # Atomic conditional insert at the SQL database engine level
            subquery = (
                select(
                    literal(teacher_id).label("id"),
                    literal(username).label("username"),
                    literal(full_name).label("full_name"),
                    literal(phone).label("phone"),
                    literal(hashed_pwd).label("hashed_password"),
                    literal(True).label("is_active"),
                    literal(now).label("created_at"),
                    literal(now).label("updated_at"),
                    literal(False).label("is_deleted"),
                ).where(~select(Teacher.id).where(Teacher.is_deleted == False).exists())
            )
            stmt = insert(Teacher).from_select(
                [
                    "id",
                    "username",
                    "full_name",
                    "phone",
                    "hashed_password",
                    "is_active",
                    "created_at",
                    "updated_at",
                    "is_deleted",
                ],
                subquery,
            )
            res = db.execute(stmt)
            db.commit()

            if res.rowcount != 1:
                return None

            return UserRepository.get_teacher_by_id(db, teacher_id)

    @staticmethod
    def create_teacher(db: Session, username: str, full_name: str, phone: str, password: str) -> Teacher:
        """Create a new teacher account with hashed password."""
        hashed_pwd = hash_password(password)
        teacher = Teacher(
            username=username,
            full_name=full_name,
            phone=phone,
            hashed_password=hashed_pwd,
            is_active=True
        )
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        return teacher

    @staticmethod
    def get_teacher_by_id(db: Session, teacher_id: str) -> Optional[Teacher]:
        """Fetch teacher by ID."""
        return db.query(Teacher).filter(
            Teacher.id == teacher_id,
            Teacher.is_deleted == False
        ).first()

    @staticmethod
    def get_teacher_by_username(db: Session, username: str) -> Optional[Teacher]:
        """Fetch teacher by username."""
        return db.query(Teacher).filter(
            Teacher.username == username,
            Teacher.is_deleted == False
        ).first()

    # --- Assistant Operations (Strictly Scoped to teacher_id) ---
    @staticmethod
    def create_assistant(
        db: Session,
        teacher_id: str,
        username: str,
        full_name: str,
        phone: str,
        password: str,
        permissions: dict
    ) -> Assistant:
        """Create an assistant tied strictly to the given teacher_id."""
        hashed_pwd = hash_password(password)
        assistant = Assistant(
            teacher_id=teacher_id,
            username=username,
            full_name=full_name,
            phone=phone,
            hashed_password=hashed_pwd,
            is_active=True,
            can_mark_attendance=permissions.get("can_mark_attendance", True),
            can_view_attendance=permissions.get("can_view_attendance", True),
            can_manage_students=permissions.get("can_manage_students", False),
            can_view_grades=permissions.get("can_view_grades", False),
            can_manage_exams=permissions.get("can_manage_exams", False),
            can_enter_grades=permissions.get("can_enter_grades", False),
            can_collect_cash=permissions.get("can_collect_cash", False),
            can_view_student_payment_history=permissions.get("can_view_student_payment_history", False),
            can_view_financial_analytics=permissions.get("can_view_financial_analytics", False),
            can_manage_fees=permissions.get("can_manage_fees", False),
            can_request_messages=permissions.get("can_request_messages", True)
        )
        db.add(assistant)
        db.commit()
        db.refresh(assistant)
        return assistant

    @staticmethod
    def get_assistant_by_id(db: Session, teacher_id: str, assistant_id: str) -> Optional[Assistant]:
        """
        Query-level isolation: Always enforce teacher_id when retrieving an assistant.
        Returns None if assistant belongs to another teacher.
        """
        return db.query(Assistant).filter(
            Assistant.id == assistant_id,
            Assistant.teacher_id == teacher_id,
            Assistant.is_deleted == False
        ).first()

    @staticmethod
    def get_assistant_by_username(db: Session, username: str) -> Optional[Assistant]:
        """Find an assistant by username (for login)."""
        return db.query(Assistant).filter(
            Assistant.username == username,
            Assistant.is_deleted == False
        ).first()

    @staticmethod
    def list_assistants_by_teacher(db: Session, teacher_id: str) -> List[Assistant]:
        """List all assistants belonging strictly to teacher_id."""
        return db.query(Assistant).filter(
            Assistant.teacher_id == teacher_id,
            Assistant.is_deleted == False
        ).all()

    @staticmethod
    def update_assistant(
        db: Session,
        teacher_id: str,
        assistant_id: str,
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
        is_active: Optional[bool] = None,
        permissions: Optional[dict] = None
    ) -> Optional[Assistant]:
        """
        Query-level isolation: Update an assistant only if teacher_id matches.
        """
        assistant = UserRepository.get_assistant_by_id(db, teacher_id=teacher_id, assistant_id=assistant_id)
        if not assistant:
            return None

        if full_name is not None:
            assistant.full_name = full_name
        if phone is not None:
            assistant.phone = phone
        if is_active is not None:
            assistant.is_active = is_active
        if permissions is not None:
            for key, val in permissions.items():
                if hasattr(assistant, key) and val is not None:
                    setattr(assistant, key, val)

        db.commit()
        db.refresh(assistant)
        return assistant

    @staticmethod
    def delete_assistant(db: Session, teacher_id: str, assistant_id: str) -> bool:
        """
        Query-level isolation: Soft-delete an assistant only if teacher_id matches.
        """
        assistant = UserRepository.get_assistant_by_id(db, teacher_id=teacher_id, assistant_id=assistant_id)
        if not assistant:
            return False

        assistant.is_deleted = True
        db.commit()

        # Invalidate all active sessions for this deleted assistant immediately
        UserRepository.revoke_all_user_sessions(db, user_id=assistant_id)
        return True

    # --- Session Operations ---
    @staticmethod
    def create_session(
        db: Session,
        session_token: str,
        csrf_token: str,
        user_type: str,
        user_id: str,
        teacher_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UserSession:
        """Create and persist a new user session storing ONLY the SHA-256 token hash."""
        token_hash = session_token if len(session_token) == 64 else hash_token(session_token)
        session = UserSession(
            session_token=token_hash,
            csrf_token=csrf_token,
            user_type=user_type,
            user_id=user_id,
            teacher_id=teacher_id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=calculate_session_expiry(),
            is_revoked=False
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_valid_session(db: Session, session_token: str) -> Optional[UserSession]:
        """
        Retrieve session by verifying the SHA-256 fingerprint of the raw token,
        checking that the session is active and not expired.
        """
        if not session_token:
            return None
        now = datetime.now(timezone.utc)
        token_hash = hash_token(session_token)
        return db.query(UserSession).filter(
            UserSession.session_token == token_hash,
            UserSession.is_revoked == False,
            UserSession.expires_at > now
        ).first()

    @staticmethod
    def revoke_session(db: Session, session_token: str) -> bool:
        """Immediately revoke a session by its token hash or raw token."""
        if not session_token:
            return False
        token_hash = session_token if len(session_token) == 64 else hash_token(session_token)
        session = db.query(UserSession).filter(UserSession.session_token == token_hash).first()
        if session:
            session.is_revoked = True
            db.commit()
            return True
        return False

    @staticmethod
    def revoke_all_user_sessions(db: Session, user_id: str) -> int:
        """Revoke all sessions for a specific user (e.g., when password changes or account disabled)."""
        count = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked == False
        ).update({"is_revoked": True})
        db.commit()
        return count
