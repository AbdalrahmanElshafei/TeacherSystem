import datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
import app.models
from app.main import app
from app.config import SESSION_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_serve_frontend_index_html(client):
    """Verify that root endpoint GET / serves the Arabic RTL HTML5 application."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    content = resp.text
    assert 'dir="rtl"' in content
    assert 'lang="ar"' in content
    assert "TeacherSystem" in content
    assert "/static/css/styles.css" in content
    assert "/static/js/main.js" in content

def test_serve_static_assets(client):
    """Verify static CSS and JS files are served with correct headers and colors."""
    # 1. Stylesheet
    css_resp = client.get("/static/css/styles.css")
    assert css_resp.status_code == 200
    assert "text/css" in css_resp.headers.get("content-type", "")
    css_text = css_resp.text
    assert "--primary: #0E4A45;" in css_text
    assert "--secondary: #C25E38;" in css_text
    assert "direction: rtl;" in css_text
    # Offline-friendly typography verification (no blocking external font requests)
    assert "fonts.googleapis.com" not in css_text
    assert "Segoe UI Arabic" in css_text
    # Responsive design breakpoints verification
    assert "@media (max-width: 1024px)" in css_text
    assert "@media (max-width: 768px)" in css_text
    assert ".sidebar-backdrop" in css_text
    assert ".empty-state-card" in css_text
    assert ".tab-nav" in css_text
    assert ".group-cards-grid" in css_text
    assert ".scanner-container" in css_text
    assert ".status-btn-group" in css_text
    assert ".exam-header-card" in css_text
    assert ".badge-pass" in css_text
    assert ".score-input" in css_text
    assert ".badge-unpaid" in css_text
    assert ".badge-paid" in css_text
    assert ".receipt-box" in css_text
    assert ".finance-metric-card" in css_text

    # 2. API client script
    api_resp = client.get("/static/js/api.js")
    assert api_resp.status_code == 200
    assert "javascript" in api_resp.headers.get("content-type", "")
    assert "ApiClient" in api_resp.text
    assert "listStudents" in api_resp.text
    assert "listGroups" in api_resp.text
    assert "enrollStudent" in api_resp.text
    assert "listSessions" in api_resp.text
    assert "scanBarcode" in api_resp.text
    assert "bulkMarkAttendance" in api_resp.text
    assert "listExams" in api_resp.text
    assert "getExamResults" in api_resp.text
    assert "bulkRecordExamResults" in api_resp.text
    assert "getStudentExamHistory" in api_resp.text
    assert "getGroupExamsSummary" in api_resp.text
    assert "getFinanceOverview" in api_resp.text
    assert "createFeeConfig" in api_resp.text
    assert "recordCashPayment" in api_resp.text
    assert "listCashPayments" in api_resp.text
    assert "previewMonthlyDues" in api_resp.text
    assert "generateMonthlyDues" in api_resp.text
    assert "reversePayment" in api_resp.text
    assert "voidStudentDue" in api_resp.text
    # Barcode Distribution API client methods
    assert "getStudentCard" in api_resp.text
    assert "getStudentCardBlob" in api_resp.text
    assert "downloadStudentCardPdf" in api_resp.text
    assert "getGroupDistributionOverview" in api_resp.text
    assert "exportGroupCardsPdf" in api_resp.text
    assert "exportMultiStudentCardsPdf" in api_resp.text
    assert "updateStudentDistributionStatus" in api_resp.text
    assert "triggerBlobDownload" in api_resp.text

    # 3. Main controller script
    main_resp = client.get("/static/js/main.js")
    assert main_resp.status_code == 200
    assert "javascript" in main_resp.headers.get("content-type", "")
    assert "renderSetupView" in main_resp.text
    assert "renderLoginView" in main_resp.text
    assert "renderAssistantsView" in main_resp.text
    assert "renderAcademicView" in main_resp.text
    assert "renderAttendanceView" in main_resp.text
    assert "bindAttendanceEvents" in main_resp.text
    assert "renderExamsView" in main_resp.text
    assert "renderExamSheetView" in main_resp.text
    assert "bindExamEvents" in main_resp.text
    assert "bindExamSheetEvents" in main_resp.text
    assert "renderFinanceView" in main_resp.text
    assert "bindFinanceEvents" in main_resp.text
    assert "renderFinanceOverviewTab" in main_resp.text
    assert "renderFinancePaymentsTab" in main_resp.text
    # Responsive drawer, backdrop, and empty state component verification
    assert "mobile-menu-toggle" in main_resp.text
    assert "sidebar-backdrop" in main_resp.text
    assert "empty-state-card" in main_resp.text
    assert "Escape" in main_resp.text
    assert "tab-btn-students" in main_resp.text
    assert "tab-btn-groups" in main_resp.text
    assert "barcode-input" in main_resp.text

    # Barcode Distribution UI verification
    assert "tab-btn-distribution" in main_resp.text
    assert "student-barcode-card-modal" in main_resp.text
    assert "renderDistributionTabContent" in main_resp.text
    assert "openStudentCardModal" in main_resp.text
    assert "shareStudentCard" in main_resp.text
    assert "open-group-distribution-btn" in main_resp.text
    assert "dist-filter-btn" in main_resp.text

    # Dashboard Command Center verification
    assert ".quick-actions-bar" in css_text
    assert ".dashboard-full-width" in css_text
    assert ".dashboard-finance-grid" in css_text
    assert "bindDashboardEvents" in main_resp.text
    assert "open-session-attendance-btn" in main_resp.text
    assert "open-exam-grades-btn" in main_resp.text
    assert "formatPiastres" in main_resp.text
    assert "formatEGP" in main_resp.text
    # Obsolete Phase 2 roadmap card must be completely removed
    assert "خارطة المرحلة الثانية (Phase 2)" not in main_resp.text
    assert "جاهز للانطلاق فور ربط الموديلات" not in main_resp.text


def test_frontend_javascript_syntax_validity():
    """Verify that static JavaScript files (main.js and api.js) have valid ES module syntax."""
    import shutil
    import subprocess
    from pathlib import Path

    node_paths = [
        shutil.which("node"),
        r"C:\Program Files\Adobe\Adobe Creative Cloud Experience\libs\node.exe",
        r"C:\Program Files\Common Files\Adobe\Creative Cloud Libraries\libs\node.exe",
    ]
    node_bin = next((p for p in node_paths if p and Path(p).is_file()), None)
    if not node_bin:
        pytest.skip("Node.js runtime not found on host to perform ES module syntax checking.")

    js_files = [
        Path(r"C:\TeacherSystem\app\static\js\main.js"),
        Path(r"C:\TeacherSystem\app\static\js\api.js")
    ]
    for js_file in js_files:
        assert js_file.is_file(), f"Missing JavaScript file: {js_file}"
        check_script = (
            "const fs = require('fs'); const vm = require('vm'); "
            f"const code = fs.readFileSync('{js_file.as_posix()}', 'utf8'); "
            f"new vm.SourceTextModule(code, {{ identifier: '{js_file.name}' }});"
        )
        res = subprocess.run(
            [node_bin, "--experimental-vm-modules", "-e", check_script],
            capture_output=True,
            text=True
        )
        assert res.returncode == 0, f"JavaScript SyntaxError in {js_file.name}:\n{res.stderr}"

def test_frontend_full_user_flow_integration(client):
    """
    Simulate the end-to-end user flow executed by the frontend:
    1. Check setup status -> Required
    2. First-run setup -> Created
    3. Login -> Success with HttpOnly cookie & CSRF cookie
    4. Fetch /api/auth/me -> Session restored
    5. List assistants -> Empty
    6. Create assistant with granular permissions -> Created
    7. Update assistant permissions -> Updated
    8. Delete assistant -> Deleted
    9. Logout -> Session revoked
    """
    # 1. Check setup status
    status_resp = client.get("/api/auth/setup-status")
    assert status_resp.status_code == 200
    assert status_resp.json()["setup_required"] is True

    # 2. Setup primary teacher
    setup_payload = {
        "username": "mr_ui_test",
        "full_name": "أستاذ الواجهة التجريبية",
        "phone": "01011119999",
        "password": "StrongPassword2026!"
    }
    setup_resp = client.post("/api/auth/first-run-setup", json=setup_payload)
    assert setup_resp.status_code == 201

    # 3. Login
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_ui_test",
        "password": "StrongPassword2026!"
    })
    assert login_resp.status_code == 200
    csrf_token = login_resp.json()["csrf_token"]
    auth_headers = {CSRF_HEADER_NAME: csrf_token}

    # 4. Restore session via /me
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "mr_ui_test"
    assert me_resp.json()["user_type"] == "teacher"

    # 5. List assistants (initially empty)
    list_resp = client.get("/api/users/assistants")
    assert list_resp.status_code == 200
    assert list_resp.json() == []

    # 6. Create assistant
    ass_payload = {
        "username": "assistant_ui_1",
        "full_name": "مساعد واجهة 1",
        "phone": "01022228888",
        "password": "AssistantPass1!",
        "permissions": {
            "can_mark_attendance": True,
            "can_collect_cash": True,
            "can_enter_grades": False,
            "can_manage_students": False,
            "can_view_financial_analytics": False
        }
    }
    create_resp = client.post("/api/users/assistants", json=ass_payload, headers=auth_headers)
    assert create_resp.status_code == 201
    assistant_id = create_resp.json()["id"]

    # 7. Update assistant permissions (grant can_enter_grades)
    update_payload = {
        "full_name": "مساعد واجهة معدل",
        "permissions": {
            "can_mark_attendance": True,
            "can_collect_cash": True,
            "can_enter_grades": True,
            "can_manage_students": False,
            "can_view_financial_analytics": False
        }
    }
    update_resp = client.put(f"/api/users/assistants/{assistant_id}", json=update_payload, headers=auth_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["full_name"] == "مساعد واجهة معدل"
    assert update_resp.json()["can_enter_grades"] is True

    # 8. Delete assistant
    del_resp = client.delete(f"/api/users/assistants/{assistant_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    # 9. Logout
    logout_resp = client.post("/api/auth/logout", headers=auth_headers)
    assert logout_resp.status_code == 200

    # Subsequent /me must fail with 401
    revoked_me = client.get("/api/auth/me")
    assert revoked_me.status_code == 401


def test_frontend_academic_flow_integration(client):
    """
    Simulate frontend user flow for Students & Groups:
    1. Setup primary teacher & login.
    2. List students (empty initially).
    3. Create student (with 1_sec grade).
    4. List groups (empty initially).
    5. Create group (with 1_sec grade).
    6. Enroll student in group via API.
    7. List group students -> student is enrolled.
    8. Attempt duplicate enrollment -> returns 409 Conflict.
    9. Attempt mismatch grade enrollment -> returns 400 Bad Request.
    10. Unenroll student -> count returns to 0.
    """
    # 1. Setup & login
    setup_payload = {
        "username": "mr_academic_flow",
        "full_name": "أستاذ الأكاديميا",
        "phone": "01055554444",
        "password": "StrongPassword2026!"
    }
    client.post("/api/auth/first-run-setup", json=setup_payload)
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_academic_flow",
        "password": "StrongPassword2026!"
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    auth_headers = {
        CSRF_HEADER_NAME: data["csrf_token"],
        "Authorization": f"Bearer {data['session_token']}"
    }

    # 2. List students (initially empty)
    list_st = client.get("/api/students", headers=auth_headers)
    assert list_st.status_code == 200
    assert list_st.json() == []

    # 3. Create student
    st_payload = {
        "full_name": "أحمد حسام البدري",
        "grade_level": "1_sec",
        "phone": "01099887766",
        "parent_name": "حسام البدري",
        "parent_phone": "01122334455"
    }
    created_st = client.post("/api/students", json=st_payload, headers=auth_headers)
    assert created_st.status_code == 201
    student_id = created_st.json()["id"]

    # 4. List groups (initially empty)
    list_grp = client.get("/api/groups", headers=auth_headers)
    assert list_grp.status_code == 200
    assert list_grp.json() == []

    # 5. Create group
    grp_payload = {
        "name": "مجموعة المتفوقين - السبت 3 عصراً",
        "grade_level": "1_sec",
        "subject": "أحياء",
        "schedule_details": "السبت 3:00 إلى 5:00 م"
    }
    created_grp = client.post("/api/groups", json=grp_payload, headers=auth_headers)
    assert created_grp.status_code == 201
    group_id = created_grp.json()["id"]

    # 6. Enroll student in group
    enroll_resp = client.post(f"/api/groups/{group_id}/students", json={"student_id": student_id}, headers=auth_headers)
    assert enroll_resp.status_code == 201

    # 7. List group students
    grp_students = client.get(f"/api/groups/{group_id}/students", headers=auth_headers)
    assert grp_students.status_code == 200
    assert len(grp_students.json()) == 1
    assert grp_students.json()[0]["student_id"] == student_id

    # 8. Duplicate enrollment returns 409
    dup_resp = client.post(f"/api/groups/{group_id}/students", json={"student_id": student_id}, headers=auth_headers)
    assert dup_resp.status_code == 409

    # 9. Grade mismatch enrollment: create 2_sec group and try to enroll 1_sec student
    grp2_resp = client.post("/api/groups", json={"name": "مجموعة ثانية ثانوي", "grade_level": "2_sec"}, headers=auth_headers)
    assert grp2_resp.status_code == 201
    grp2_id = grp2_resp.json()["id"]

    mismatch_resp = client.post(f"/api/groups/{grp2_id}/students", json={"student_id": student_id}, headers=auth_headers)
    assert mismatch_resp.status_code == 400

    # 10. Unenroll student
    unenroll_resp = client.delete(f"/api/groups/{group_id}/students/{student_id}", headers=auth_headers)
    assert unenroll_resp.status_code == 200

    grp_students_after = client.get(f"/api/groups/{group_id}/students", headers=auth_headers)
    assert grp_students_after.status_code == 200
    assert len(grp_students_after.json()) == 0


def test_frontend_sessions_and_attendance_flow_integration(client):
    """
    Simulate the end-to-end user flow for Sessions & Attendance module:
    1. Setup primary teacher & login.
    2. Create student & group, enroll student in group.
    3. Create a session for the group.
    4. List sessions -> session is listed with correct group and initial 0 present stats.
    5. Fetch attendance sheet -> student appears with unrecorded status.
    6. Process barcode scan for enrolled student -> status changes to present.
    7. Process duplicate barcode scan -> returns already_present gracefully without error.
    8. Mark attendance status to 'late' with notes.
    9. Bulk mark attendance.
    10. Verify student attendance history & group summary report.
    """
    # 1. Setup & Login
    setup_payload = {
        "username": "mr_att_flow",
        "full_name": "أستاذ الحضور",
        "phone": "01077778888",
        "password": "StrongPassword2026!"
    }
    client.post("/api/auth/first-run-setup", json=setup_payload)
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_att_flow",
        "password": "StrongPassword2026!"
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    auth_headers = {
        CSRF_HEADER_NAME: data["csrf_token"],
        "Authorization": f"Bearer {data['session_token']}"
    }

    # 2. Create student and group
    st_resp = client.post("/api/students", json={
        "full_name": "كريم عبد العزيز",
        "grade_level": "3_sec",
        "phone": "01234567890",
        "parent_phone": "01298765432"
    }, headers=auth_headers)
    assert st_resp.status_code == 201
    student_id = st_resp.json()["id"]

    grp_resp = client.post("/api/groups", json={
        "name": "شعبة الأوائل 3ث",
        "grade_level": "3_sec",
        "subject": "كيمياء"
    }, headers=auth_headers)
    assert grp_resp.status_code == 201
    group_id = grp_resp.json()["id"]

    # Enroll student
    enr_resp = client.post(f"/api/groups/{group_id}/students", json={"student_id": student_id}, headers=auth_headers)
    assert enr_resp.status_code == 201

    # 3. Create session
    sess_payload = {
        "group_id": group_id,
        "session_date": "2026-11-01",
        "start_time": "17:00",
        "end_time": "19:00",
        "location": "قاعة 1",
        "notes": "حصة الكيمياء العضوية"
    }
    sess_resp = client.post("/api/sessions", json=sess_payload, headers=auth_headers)
    assert sess_resp.status_code == 201
    session_id = sess_resp.json()["id"]
    assert sess_resp.json()["group_name"] == "شعبة الأوائل 3ث"

    # 4. List sessions
    list_sess = client.get("/api/sessions", headers=auth_headers)
    assert list_sess.status_code == 200
    assert len(list_sess.json()) == 1
    assert list_sess.json()[0]["id"] == session_id
    assert list_sess.json()[0]["stats"]["total_enrolled"] == 1
    assert list_sess.json()[0]["stats"]["unrecorded_count"] == 1

    # 5. Fetch attendance sheet
    sheet_resp = client.get(f"/api/sessions/{session_id}/attendance", headers=auth_headers)
    assert sheet_resp.status_code == 200
    sheet = sheet_resp.json()
    assert len(sheet["students"]) == 1
    assert sheet["students"][0]["student_id"] == student_id
    assert sheet["students"][0]["status"] is None

    # 6. Barcode scan (student_id)
    scan_resp = client.post(f"/api/sessions/{session_id}/scan", json={"barcode": student_id}, headers=auth_headers)
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["success"] is True
    assert scan_data["action"] == "recorded"
    assert scan_data["status"] == "present"

    # 7. Duplicate scan handling
    dup_scan = client.post(f"/api/sessions/{session_id}/scan", json={"barcode": student_id}, headers=auth_headers)
    assert dup_scan.status_code == 200
    assert dup_scan.json()["action"] == "already_present"
    assert dup_scan.json()["status"] == "present"

    # 8. Mark attendance status to 'late' with notes
    mark_resp = client.post(f"/api/sessions/{session_id}/attendance", json={
        "student_id": student_id,
        "status": "late",
        "notes": "تأخر 15 دقيقة بعذر مواصلات"
    }, headers=auth_headers)
    assert mark_resp.status_code == 200
    assert mark_resp.json()["status"] == "late"

    # 9. Verify student attendance history
    hist_resp = client.get(f"/api/sessions/reports/student/{student_id}", headers=auth_headers)
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert hist["total_sessions"] == 1
    assert hist["late_count"] == 1
    assert hist["attendance_rate"] == 100.0

    # 10. Verify group attendance summary
    summary_resp = client.get(f"/api/sessions/reports/group/{group_id}", headers=auth_headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_sessions"] == 1
    assert summary["total_students"] == 1
    assert summary["average_attendance_rate"] == 100.0


def test_exams_and_grades_frontend_flow(client):
    """
    End-to-End User Flow verification for the Exams & Grades frontend:
    1. Authenticate teacher.
    2. Create group and student, enroll student.
    3. Create and schedule an exam.
    4. Fetch exam list with filters.
    5. Fetch exam results sheet.
    6. Record student exam result (single entry).
    7. Update and verify pass/fail and percentages.
    8. Complete the exam.
    9. Fetch student exam history report.
    10. Fetch group exams summary report.
    """
    # 1. Setup & Login
    client.post("/api/auth/first-run-setup", json={
        "username": "mr_frontend_exams",
        "full_name": "الأستاذ طارق إبراهيم",
        "phone": "01088888888",
        "password": "StrongPassword2026!"
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "mr_frontend_exams",
        "password": "StrongPassword2026!"
    })
    auth_headers = {
        CSRF_HEADER_NAME: login_resp.json()["csrf_token"],
        "Authorization": f"Bearer {login_resp.json()['session_token']}"
    }

    # 2. Create Group and Student, enroll
    grp_resp = client.post("/api/groups", json={
        "name": "مجموعة المتفوقين في التاريخ",
        "grade_level": "3_sec"
    }, headers=auth_headers)
    group_id = grp_resp.json()["id"]

    st_resp = client.post("/api/students", json={
        "full_name": "محمود عادل الشريف",
        "phone": "01055554444",
        "grade_level": "3_sec"
    }, headers=auth_headers)
    student_id = st_resp.json()["id"]

    client.post(f"/api/groups/{group_id}/students", json={"student_id": student_id}, headers=auth_headers)

    # 3. Create Exam
    create_exam_resp = client.post("/api/exams", json={
        "group_id": group_id,
        "title": "امتحان التاريخ الحديث",
        "exam_date": "2026-10-28",
        "max_score": 60,
        "passing_score": 30,
        "description": "الفصل الأول والثاني"
    }, headers=auth_headers)
    assert create_exam_resp.status_code == 201
    exam = create_exam_resp.json()
    exam_id = exam["id"]
    assert exam["title"] == "امتحان التاريخ الحديث"
    assert exam["max_score"] == 60.0
    assert exam["passing_score"] == 30.0

    # 4. List Exams
    list_resp = client.get(f"/api/exams?group_id={group_id}", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # 5. Fetch Exam Results Sheet
    sheet_resp = client.get(f"/api/exams/{exam_id}/results", headers=auth_headers)
    assert sheet_resp.status_code == 200
    sheet = sheet_resp.json()
    assert len(sheet["students"]) == 1
    assert sheet["students"][0]["student_id"] == student_id
    assert sheet["students"][0]["score"] is None
    assert sheet["stats"]["results_pending"] == 1

    # 6. Record Student Result (Single)
    rec_resp = client.post(f"/api/exams/{exam_id}/results", json={
        "student_id": student_id,
        "status": "attended",
        "score": 54,
        "notes": "ممتاز جداً"
    }, headers=auth_headers)
    assert rec_resp.status_code == 200
    assert rec_resp.json()["score"] == 54.0

    # 7. Check Sheet stats after recording
    sheet_after = client.get(f"/api/exams/{exam_id}/results", headers=auth_headers).json()
    st_row = sheet_after["students"][0]
    assert st_row["score"] == 54.0
    assert st_row["percentage"] == 90.0
    assert st_row["is_passed"] is True
    assert sheet_after["stats"]["results_recorded"] == 1
    assert sheet_after["stats"]["pass_rate"] == 100.0

    # 8. Complete the Exam
    comp_resp = client.post(f"/api/exams/{exam_id}/complete", headers=auth_headers)
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "completed"

    # 9. Verify Student Exam History Report
    hist_resp = client.get(f"/api/exams/reports/student/{student_id}", headers=auth_headers)
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert hist["total_exams"] == 1
    assert hist["attended_count"] == 1
    assert hist["passed_count"] == 1
    assert hist["average_percentage"] == 90.0

    # 10. Verify Group Exams Summary Report
    group_summary_resp = client.get(f"/api/exams/reports/group/{group_id}", headers=auth_headers)
    assert group_summary_resp.status_code == 200
    grp_summary = group_summary_resp.json()
    assert grp_summary["total_exams"] == 1
    assert grp_summary["total_students"] == 1
    assert grp_summary["average_pass_rate"] == 100.0
    assert grp_summary["average_group_score_percentage"] == 90.0


def test_frontend_cash_and_finance_workflow(client):
    """
    Simulate the end-to-end Payments, Dues, and Cash Collection workflow from the frontend:
    1. Setup and login
    2. Create student & group, enroll student
    3. Configure group monthly fee
    4. Preview and generate monthly dues
    5. List dues and verify unpaid status
    6. Record cash payment with due allocation
    7. Verify receipt issued (RCP-YYYYMM-XXXX) and due status updated to paid
    8. Check finance overview metrics
    9. Fetch student financial profile & ledger
    10. Fetch monthly collection report
    """
    # 1. Setup & Login
    client.post("/api/auth/first-run-setup", json={
        "username": "fin_teacher",
        "full_name": "Finance Master Teacher",
        "phone": "01055554444",
        "password": "StrongPassword2026!"
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "fin_teacher",
        "password": "StrongPassword2026!"
    })
    assert login_resp.status_code == 200
    auth_headers = {
        CSRF_HEADER_NAME: login_resp.json()["csrf_token"],
        "Authorization": f"Bearer {login_resp.json()['session_token']}"
    }

    # 2. Create student & group, enroll student
    st_resp = client.post("/api/students", json={
        "full_name": "Finance Student A",
        "phone": "01033334444",
        "grade_level": "2_sec",
        "parent_name": "Parent A",
        "parent_phone": "01022223333"
    }, headers=auth_headers)
    assert st_resp.status_code == 201
    student_id = st_resp.json()["id"]

    grp_resp = client.post("/api/groups", json={
        "name": "Finance Group 2nd Sec",
        "grade_level": "2_sec"
    }, headers=auth_headers)
    assert grp_resp.status_code == 201
    group_id = grp_resp.json()["id"]

    enroll_resp = client.post(f"/api/groups/{group_id}/students", json={
        "student_id": student_id
    }, headers=auth_headers)
    assert enroll_resp.status_code == 201

    # 3. Configure group fee
    fee_resp = client.post("/api/finance/fees", json={
        "group_id": group_id,
        "fee_model": "monthly",
        "amount_egp": 300.0,
        "effective_from": "2026-10-01"
    }, headers=auth_headers)
    assert fee_resp.status_code == 201
    assert fee_resp.json()["amount_egp"] == 300.0

    # 4. Preview and generate monthly dues
    prev_resp = client.post("/api/finance/dues/monthly/preview", json={
        "group_id": group_id,
        "billing_month": "2026-10",
        "due_date": "2026-10-10"
    }, headers=auth_headers)
    assert prev_resp.status_code == 200
    assert prev_resp.json()["eligible_students_count"] == 1
    assert prev_resp.json()["total_amount_egp"] == 300.0

    gen_resp = client.post("/api/finance/dues/monthly/generate", json={
        "group_id": group_id,
        "billing_month": "2026-10",
        "due_date": "2026-10-10"
    }, headers=auth_headers)
    assert gen_resp.status_code in (200, 201)
    assert gen_resp.json()["generated_count"] == 1

    # 5. List dues
    dues_resp = client.get(f"/api/finance/dues?student_id={student_id}", headers=auth_headers)
    assert dues_resp.status_code == 200
    dues = dues_resp.json()
    assert len(dues) == 1
    due_id = dues[0]["id"]
    assert dues[0]["status"] == "unpaid"
    assert dues[0]["amount_egp"] == 300.0

    # 6. Record cash payment
    pay_resp = client.post("/api/finance/payments", json={
        "student_id": student_id,
        "amount_egp": 300.0,
        "payment_date": "2026-10-12",
        "notes": "Full subscription paid",
        "allocations": [
            {"due_id": due_id, "amount_egp": 300.0}
        ]
    }, headers=auth_headers)
    assert pay_resp.status_code == 201
    payment = pay_resp.json()
    assert payment["receipt_number"].startswith("RCP-")
    assert payment["allocated_amount_egp"] == 300.0
    assert payment["formatted_amount"] == "300.00 ج.م"
    assert payment["created_by_name"] == "المعلم"

    # 7. Check Due status updated to paid
    due_after = client.get(f"/api/finance/dues?student_id={student_id}", headers=auth_headers).json()[0]
    assert due_after["status"] == "paid"
    assert due_after["paid_amount_egp"] == 300.0

    # 8. Check finance overview
    ov_resp = client.get("/api/finance/overview", headers=auth_headers)
    assert ov_resp.status_code == 200
    ov = ov_resp.json()
    assert ov["total_charges_egp"] == 300.0
    assert ov["total_cash_collected_egp"] == 300.0
    assert ov["total_outstanding_balance_egp"] == 0.0

    # 9. Student Financial Profile & Ledger
    prof_resp = client.get(f"/api/finance/reports/student/{student_id}", headers=auth_headers)
    assert prof_resp.status_code == 200
    prof = prof_resp.json()
    assert prof["total_dues_egp"] == 300.0
    assert prof["total_paid_egp"] == 300.0
    assert prof["outstanding_balance_egp"] == 0.0
    assert len(prof["payments"]) == 1

    # 10. Monthly Collection Report
    m_rep_resp = client.get("/api/finance/reports/monthly/2026-10", headers=auth_headers)
    assert m_rep_resp.status_code == 200
    assert m_rep_resp.json()["charges_generated_egp"] == 300.0


def test_dashboard_command_center_integration(client):
    """
    Test the operational command center workflows and APIs:
    - Today's sessions API query
    - Monthly collection report distinguishing cash from billed charges
    - Overview metrics
    - Recent exams query
    - Quick actions URL mapping
    """
    # 1. Setup teacher workspace
    setup_resp = client.post("/api/auth/first-run-setup", json={
        "username": "teacher_dash",
        "full_name": "الأستاذ المشرف",
        "phone": "01099887766",
        "password": "StrongPassword2026!"
    })
    assert setup_resp.status_code == 201

    login_resp = client.post("/api/auth/login", json={
        "username": "teacher_dash",
        "password": "StrongPassword2026!"
    })
    assert login_resp.status_code == 200
    csrf_token = login_resp.cookies.get(CSRF_COOKIE_NAME)
    auth_headers = {CSRF_HEADER_NAME: csrf_token}

    # 2. Create student & group
    stud_resp = client.post("/api/students", json={
        "full_name": "طالب لوحة التحكم",
        "grade_level": "1_sec",
        "phone": "01011112222",
        "is_active": True
    }, headers=auth_headers)
    assert stud_resp.status_code == 201
    student_id = stud_resp.json()["id"]

    grp_resp = client.post("/api/groups", json={
        "name": "مجموعة لوحة العمليات",
        "grade_level": "1_sec",
        "schedule_details": "الأحد والأربعاء",
        "is_active": True
    }, headers=auth_headers)
    assert grp_resp.status_code == 201
    group_id = grp_resp.json()["id"]

    enroll_resp = client.post(f"/api/groups/{group_id}/students", json={"student_id": student_id}, headers=auth_headers)
    assert enroll_resp.status_code == 201

    # 3. Schedule session for today
    today_str = datetime.date.today().isoformat()
    current_month = today_str[:7]

    sess_resp = client.post("/api/sessions", json={
        "group_id": group_id,
        "session_date": today_str,
        "start_time": "15:00",
        "end_time": "17:00",
        "location": "القاعة الرئيسية"
    }, headers=auth_headers)
    assert sess_resp.status_code == 201
    session_id = sess_resp.json()["id"]

    # Mark attendance for today's session
    att_resp = client.post(f"/api/sessions/{session_id}/attendance", json={
        "student_id": student_id,
        "status": "present",
        "notes": "حضور مبكر"
    }, headers=auth_headers)
    assert att_resp.status_code == 200

    # 4. Create an exam
    exam_resp = client.post("/api/exams", json={
        "group_id": group_id,
        "title": "امتحان تجريبي للوحة القيادة",
        "exam_date": today_str,
        "max_score": 100.0,
        "passing_score": 50.0
    }, headers=auth_headers)
    assert exam_resp.status_code == 201
    exam_id = exam_resp.json()["id"]

    # 5. Fee config, dues, and payment
    cfg_resp = client.post("/api/finance/fees", json={
        "group_id": group_id,
        "fee_model": "monthly",
        "amount_egp": 400.0,
        "effective_from": f"{current_month}-01"
    }, headers=auth_headers)
    assert cfg_resp.status_code == 201

    due_gen = client.post("/api/finance/dues/monthly/generate", json={
        "group_id": group_id,
        "billing_month": current_month,
        "due_date": today_str
    }, headers=auth_headers)
    assert due_gen.status_code in (200, 201)
    assert due_gen.json()["generated_count"] == 1

    dues = client.get(f"/api/finance/dues?student_id={student_id}", headers=auth_headers).json()
    assert len(dues) == 1
    due_id = dues[0]["id"]

    # Pay 250 EGP partial payment to have both cash received and remaining balance
    pay_resp = client.post("/api/finance/payments", json={
        "student_id": student_id,
        "amount_egp": 250.0,
        "payment_date": today_str,
        "allocations": [{"due_id": due_id, "amount_egp": 250.0}]
    }, headers=auth_headers)
    assert pay_resp.status_code == 201

    # ==========================================
    # --- Verify Dashboard Endpoint Queries ---
    # ==========================================

    # A. Today's Sessions query
    dash_sess_resp = client.get(f"/api/sessions?session_date={today_str}", headers=auth_headers)
    assert dash_sess_resp.status_code == 200
    dash_sessions = dash_sess_resp.json()
    assert len(dash_sessions) == 1
    sess_obj = dash_sessions[0]
    assert sess_obj["group_name"] == "مجموعة لوحة العمليات"
    assert sess_obj["session_date"] == today_str
    assert sess_obj["stats"]["present_count"] == 1
    assert sess_obj["stats"]["total_enrolled"] == 1

    # B. Monthly Finance Report: strictly distinguishes cash received from billed charges
    dash_fin_resp = client.get(f"/api/finance/reports/monthly/{current_month}", headers=auth_headers)
    assert dash_fin_resp.status_code == 200
    fin_report = dash_fin_resp.json()
    assert fin_report["cash_received_in_month_egp"] == 250.0
    assert fin_report["charges_generated_egp"] == 400.0
    assert fin_report["outstanding_balance_egp"] == 150.0
    assert fin_report["collection_rate_percent"] == 62.5

    # C. Finance Overview query
    dash_ov_resp = client.get("/api/finance/overview", headers=auth_headers)
    assert dash_ov_resp.status_code == 200
    ov_data = dash_ov_resp.json()
    assert ov_data["total_cash_collected_egp"] == 250.0
    assert ov_data["total_charges_egp"] == 400.0
    assert ov_data["total_outstanding_balance_egp"] == 150.0

    # D. Recent Exams query (with limit)
    dash_exams_resp = client.get("/api/exams?limit=5", headers=auth_headers)
    assert dash_exams_resp.status_code == 200
    dash_exams = dash_exams_resp.json()
    assert len(dash_exams) >= 1
    recent_ex = dash_exams[0]
    assert recent_ex["title"] == "امتحان تجريبي للوحة القيادة"
    assert recent_ex["stats"]["total_students"] == 1
    assert recent_ex["stats"]["pending_count"] == 1


def test_dashboard_assistant_rbac_isolation(client):
    """
    Verify fine-grained RBAC on dashboard endpoints for assistants:
    - Attendance assistant can only see sessions
    - Grades assistant can only see exams
    - Cashier assistant can only see finances
    """
    # 1. Setup teacher workspace
    client.post("/api/auth/first-run-setup", json={
        "username": "teacher_rbac",
        "full_name": "الأستاذ العام",
        "phone": "01000000001",
        "password": "StrongPassword2026!"
    })
    t_login = client.post("/api/auth/login", json={
        "username": "teacher_rbac",
        "password": "StrongPassword2026!"
    })
    t_csrf = t_login.cookies.get(CSRF_COOKIE_NAME)
    t_headers = {CSRF_HEADER_NAME: t_csrf}

    # 2. Create assistants
    client.post("/api/users/assistants", json={
        "username": "asst_att_user",
        "full_name": "مساعد الحضور",
        "phone": "01000000002",
        "password": "StrongPassword2026!",
        "permissions": {
            "can_view_attendance": True,
            "can_mark_attendance": True,
            "can_view_grades": False,
            "can_manage_exams": False,
            "can_enter_grades": False,
            "can_collect_cash": False,
            "can_manage_fees": False,
            "can_view_financial_analytics": False
        }
    }, headers=t_headers)

    client.post("/api/users/assistants", json={
        "username": "asst_grades_user",
        "full_name": "مساعد الدرجات",
        "phone": "01000000003",
        "password": "StrongPassword2026!",
        "permissions": {
            "can_view_attendance": False,
            "can_mark_attendance": False,
            "can_view_grades": True,
            "can_manage_exams": True,
            "can_enter_grades": True,
            "can_collect_cash": False,
            "can_manage_fees": False,
            "can_view_financial_analytics": False
        }
    }, headers=t_headers)

    client.post("/api/users/assistants", json={
        "username": "asst_cash_user",
        "full_name": "مساعد الخزينة",
        "phone": "01000000004",
        "password": "StrongPassword2026!",
        "permissions": {
            "can_view_attendance": False,
            "can_mark_attendance": False,
            "can_view_grades": False,
            "can_manage_exams": False,
            "can_enter_grades": False,
            "can_collect_cash": True,
            "can_manage_fees": False,
            "can_view_financial_analytics": False
        }
    }, headers=t_headers)

    today_str = datetime.date.today().isoformat()
    current_month = today_str[:7]

    # 3. Test Attendance Assistant
    att_login = client.post("/api/auth/login", json={
        "username": "asst_att_user",
        "password": "StrongPassword2026!"
    })
    att_headers = {CSRF_HEADER_NAME: att_login.cookies.get(CSRF_COOKIE_NAME)}

    assert client.get(f"/api/sessions?session_date={today_str}", headers=att_headers).status_code == 200
    assert client.get(f"/api/finance/reports/monthly/{current_month}", headers=att_headers).status_code == 403
    assert client.get("/api/finance/overview", headers=att_headers).status_code == 403
    assert client.get("/api/exams?limit=5", headers=att_headers).status_code == 403

    # 4. Test Grades Assistant
    grd_login = client.post("/api/auth/login", json={
        "username": "asst_grades_user",
        "password": "StrongPassword2026!"
    })
    grd_headers = {CSRF_HEADER_NAME: grd_login.cookies.get(CSRF_COOKIE_NAME)}

    assert client.get("/api/exams?limit=5", headers=grd_headers).status_code == 200
    assert client.get(f"/api/sessions?session_date={today_str}", headers=grd_headers).status_code == 403
    assert client.get(f"/api/finance/reports/monthly/{current_month}", headers=grd_headers).status_code == 403
    assert client.get("/api/finance/overview", headers=grd_headers).status_code == 403

    # 5. Test Cash Assistant
    csh_login = client.post("/api/auth/login", json={
        "username": "asst_cash_user",
        "password": "StrongPassword2026!"
    })
    csh_headers = {CSRF_HEADER_NAME: csh_login.cookies.get(CSRF_COOKIE_NAME)}

    assert client.get(f"/api/finance/reports/monthly/{current_month}", headers=csh_headers).status_code == 200
    assert client.get("/api/finance/overview", headers=csh_headers).status_code == 200
    assert client.get(f"/api/sessions?session_date={today_str}", headers=csh_headers).status_code == 403
    assert client.get("/api/exams?limit=5", headers=csh_headers).status_code == 403


def test_system_and_backup_frontend_assets_and_security(client, monkeypatch, tmp_path):
    """
    Verify frontend integration for System & Backup Management:
    1. Static assets include all necessary backup controls and disaster recovery procedures.
    2. JavaScript code includes API bindings and event handlers.
    3. Assistants cannot access backup APIs.
    4. Teacher has full access.
    """
    # 1. Inspect main.js contents
    main_js_path = Path("C:/TeacherSystem/app/static/js/main.js")
    main_js = main_js_path.read_text(encoding="utf-8")
    assert "create-backup-btn" in main_js
    assert "bindSystemEvents" in main_js
    assert "download-backup-btn" in main_js
    assert "إجراءات الاستعادة الآمنة" in main_js

    # 2. Inspect api.js contents
    api_js_path = Path("C:/TeacherSystem/app/static/js/api.js")
    api_js = api_js_path.read_text(encoding="utf-8")
    assert "listBackups" in api_js
    assert "createBackup" in api_js
    assert "downloadBackup" in api_js

    # 3. Setup teacher and assistant
    client.post("/api/auth/first-run-setup", json={
        "username": "sys_teacher",
        "full_name": "Teacher System Admin",
        "phone": "01012341234",
        "password": "StrongPassword2026!"
    })
    t_login = client.post("/api/auth/login", json={
        "username": "sys_teacher",
        "password": "StrongPassword2026!"
    })
    t_token = t_login.json()["session_token"]
    t_headers = {"Authorization": f"Bearer {t_token}"}

    client.post("/api/users/assistants", json={
        "username": "sys_asst",
        "full_name": "System Assistant",
        "phone": "01123452345",
        "password": "StrongPassword2026!",
        "permissions": {"can_collect_cash": True}
    }, headers=t_headers)

    a_login = client.post("/api/auth/login", json={
        "username": "sys_asst",
        "password": "StrongPassword2026!"
    })
    a_headers = {"Authorization": f"Bearer {a_login.json()['session_token']}"}

    # Assistant rejected from backup endpoints
    assert client.get("/api/backups", headers=a_headers).status_code == 403
    assert client.post("/api/backups", headers=a_headers).status_code == 403

    # Teacher accepted
    test_backup_dir = tmp_path / "test_frontend_backups"
    test_backup_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BACKUP_DIR", str(test_backup_dir))

    get_resp = client.get("/api/backups", headers=t_headers)
    assert get_resp.status_code == 200
    assert "backups" in get_resp.json()


def test_frontend_barcode_distribution_user_flow(client):
    """
    Test the complete frontend user flow for Barcode Distribution:
    1. First-run setup & Teacher login
    2. Create group and student, enroll student
    3. Distribution overview loads student with status 'not_sent'
    4. Group PDF export triggers, advancing status to 'generated'
    5. Single card view returns SVG and barcode payload
    6. Update status to 'share_opened', then 'confirmed_sent'
    7. Enroll second student and verify flagged as 'is_new_since_last_export'
    """
    client.post("/api/auth/first-run-setup", json={
        "username": "dist_ui_teacher",
        "full_name": "Teacher Dist UI",
        "phone": "01099887766",
        "password": "StrongPassword2026!"
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "dist_ui_teacher",
        "password": "StrongPassword2026!"
    })
    token = login_resp.json()["session_token"]
    csrf = login_resp.json()["csrf_token"]
    headers = {"Authorization": f"Bearer {token}", CSRF_HEADER_NAME: csrf}

    # 1. Create group and student
    grp_resp = client.post("/api/groups", json={
        "name": "مجموعة واجهة التوزيع",
        "grade_level": "1_sec",
        "subject": "فيزياء"
    }, headers=headers)
    assert grp_resp.status_code == 201
    group_id = grp_resp.json()["id"]

    stu1_resp = client.post("/api/students", json={
        "full_name": "طالب التوزيع 1",
        "grade_level": "1_sec",
        "phone": "01011110001"
    }, headers=headers)
    assert stu1_resp.status_code == 201
    student1_id = stu1_resp.json()["id"]

    client.post(f"/api/groups/{group_id}/students", json={"student_id": student1_id}, headers=headers)

    # 2. Distribution overview loads student with status 'not_sent'
    dist1 = client.get(f"/api/barcodes/distribution/groups/{group_id}", headers=headers)
    assert dist1.status_code == 200
    data1 = dist1.json()
    assert data1["total_students"] == 1
    assert data1["pending_count"] == 1
    assert data1["students"][0]["distribution_status"] == "not_sent"

    # 3. Group PDF export triggers, advancing status to 'generated'
    pdf_resp = client.post(f"/api/barcodes/groups/{group_id}/export-pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")

    dist2 = client.get(f"/api/barcodes/distribution/groups/{group_id}", headers=headers)
    assert dist2.status_code == 200
    data2 = dist2.json()
    assert data2["students"][0]["distribution_status"] == "generated"

    # 4. Single card view returns SVG and barcode payload
    card_resp = client.get(f"/api/barcodes/students/{student1_id}/card", headers=headers)
    assert card_resp.status_code == 200
    assert card_resp.json()["barcode_value"] == student1_id
    assert "<svg" in card_resp.json()["barcode_svg"]

    # 5. Share opened status
    client.post(f"/api/barcodes/distribution/students/{student1_id}/status", json={
        "status": "share_opened"
    }, headers=headers)
    dist3 = client.get(f"/api/barcodes/distribution/groups/{group_id}", headers=headers).json()
    assert dist3["students"][0]["distribution_status"] == "share_opened"

    # 6. Confirmed sent status
    client.post(f"/api/barcodes/distribution/students/{student1_id}/status", json={
        "status": "confirmed_sent"
    }, headers=headers)
    dist4 = client.get(f"/api/barcodes/distribution/groups/{group_id}", headers=headers).json()
    assert dist4["confirmed_sent_count"] == 1
    assert dist4["students"][0]["distribution_status"] == "confirmed_sent"

    # 7. Enroll second student -> flagged as is_new_since_last_export
    # Wait or simulate joined_at after export
    stu2_resp = client.post("/api/students", json={
        "full_name": "طالب حديث 2",
        "grade_level": "1_sec",
        "phone": "01011110002"
    }, headers=headers)
    student2_id = stu2_resp.json()["id"]
    client.post(f"/api/groups/{group_id}/students", json={"student_id": student2_id}, headers=headers)

    dist5 = client.get(f"/api/barcodes/distribution/groups/{group_id}", headers=headers).json()
    assert dist5["total_students"] == 2
    assert dist5["new_since_export_count"] == 1
    stu2_item = next(item for item in dist5["students"] if item["student_id"] == student2_id)
    assert stu2_item["is_new_since_last_export"] is True





