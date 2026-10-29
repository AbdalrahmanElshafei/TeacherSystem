/**
 * TeacherSystem — Master Frontend Application Controller (main.js)
 * Modern Zero-Build Single Page Application architecture.
 * Fully compatible with native Python 3.12 / FastAPI runtime.
 */

import { api } from './api.js';

// --- Grade Labels Map ---
const GRADE_LABELS = {
  '1_sec': 'الصف الأول الثانوي',
  '2_sec': 'الصف الثاني الثانوي',
  '3_sec': 'الصف الثالث الثانوي'
};

// --- Global Application State ---
const state = {
  user: null,
  isAuthenticated: false,
  setupRequired: false,
  activeRoute: '',
  assistants: [],
  students: [],
  groups: [],
  sessions: [],
  sessionFilters: { group_id: '', session_date: '', status: '' },
  activeSessionId: null,
  activeSessionSheet: null,
  editingSessionId: null,
  exams: [],
  examFilters: { group_id: '', exam_date: '', status: '' },
  activeExamId: null,
  activeExamSheet: null,
  editingExamId: null,
  activeExamStudentHistory: null,
  activeExamGroupSummary: null,
  audioFeedbackEnabled: true,
  activeStudentHistory: null,
  activeGroupSummary: null,
  activeAcademicTab: 'students',
  studentFilters: { q: '', grade_level: '', is_active: '' },
  groupFilters: { grade_level: '', is_active: '' },
  rateLimitTimer: null,
  rateLimitRemaining: 0,
  editingAssistantId: null,
  editingStudentId: null,
  editingGroupId: null,
  activeModalStudent: null,
  activeModalGroup: null,
  // Dashboard Command Center state
  todaySessions: [],
  recentExams: [],
  dashboardFinanceReport: null,
  dashboardFinanceOverview: null,
  dashboardError: { sessions: null, exams: null, finance: null },
  // Finance & Payments state
  financeTab: 'overview',
  financeOverview: null,
  feeConfigs: [],
  dues: [],
  payments: [],
  dueFilters: { student_id: '', group_id: '', status: '', charge_type: '', billing_month: '' },
  paymentFilters: { student_id: '', start_date: '', end_date: '', include_reversed: 'false' },
  activeStudentProfile: null,
  activeGroupFinanceSummary: null,
  activeMonthlyReport: null,
  activeCashReport: null,
  pendingPaymentStudentDues: [],
  reversingPaymentId: null,
  voidingDueId: null,
  // Backup Management state
  backups: [],
  backupDirectoryHint: '',
  backupTotalCount: 0,
  backupTotalSizeFormatted: '',
  isCreatingBackup: false,
  backupError: null,
  // Barcode Distribution state
  distributionOverview: null,
  selectedDistributionGroupId: null,
  distributionStudentFilter: 'all',
  selectedDistributionStudentIds: [],
  activeStudentCard: null,
};

// --- Toast Notification System ---
export function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${message}</span>
    <button style="background:none;border:none;color:inherit;cursor:pointer;font-size:1.1rem;padding:0 0.4rem;" aria-label="إغلاق">✕</button>
  `;
  
  toast.querySelector('button').addEventListener('click', () => toast.remove());
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4500);
}

// --- Password Strength Helper ---
function evaluatePassword(pwd) {
  if (!pwd) return { valid: false, score: 0, message: 'يرجى إدخال كلمة المرور' };
  const hasLetters = /[a-zA-Z]/.test(pwd);
  const hasNumbers = /\d/.test(pwd);
  const isMinLength = pwd.length >= 8;
  const isBlacklisted = ['password', '12345678', 'admin123', 'qwerty123', 'password123', 'teacher123'].includes(pwd.toLowerCase());

  if (isBlacklisted) {
    return { valid: false, score: 1, message: 'كلمة مرور شائعة وسهلة التخمين. يرجى اختيار كلمة أقوى' };
  }
  if (!isMinLength) {
    return { valid: false, score: 1, message: 'يجب ألا تقل كلمة المرور عن 8 أحرف' };
  }
  if (!hasLetters || !hasNumbers) {
    return { valid: false, score: 2, message: 'يجب أن تحتوي على حروف وأرقام معاً' };
  }
  return { valid: true, score: 3, message: 'كلمة مرور قوية ومطابقة للسياسة المعتمدة' };
}

// --- Currency Formatting Helpers ---
export function formatPiastres(p) {
  if (p === null || p === undefined) return '0.00 ج.م';
  return (p / 100).toFixed(2) + ' ج.م';
}

export function formatEGP(amt) {
  if (amt === null || amt === undefined) return '0.00 ج.م';
  return Number(amt).toFixed(2) + ' ج.م';
}

export function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// --- Icons Helper (Clean inline SVGs) ---
const icons = {
  dashboard: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>`,
  users: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>`,
  assistants: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><line x1="19" y1="8" x2="19" y2="14"></line><line x1="22" y1="11" x2="16" y2="11"></line></svg>`,
  attendance: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>`,
  exams: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>`,
  cash: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"></rect><line x1="2" y1="10" x2="22" y2="10"></line></svg>`,
  analytics: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>`,
  system: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>`,
  logout: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>`,
  search: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>`,
  plus: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>`,
  trash: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`,
  edit: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>`,
  shield: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>`,
  barcode: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 5v14"></path><path d="M8 5v14"></path><path d="M12 5v14"></path><path d="M17 5v14"></path><path d="M21 5v14"></path></svg>`,
  calendar: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>`,
  clock: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>`,
  check: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`,
  volume: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`,
};

// --- Audio Synthesis for USB Barcode Feedback ---
function playFeedbackTone(type = 'success') {
  if (!state.audioFeedbackEnabled) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    if (type === 'success') {
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(1320, ctx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.2);
    } else if (type === 'warning') {
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(580, ctx.currentTime);
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.25);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.25);
    } else {
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(160, ctx.currentTime);
      gain.gain.setValueAtTime(0.25, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.3);
    }
  } catch (e) {
    // Audio context may be restricted before user interaction
  }
}

// --- View 1: First-Run Setup Wizard ---
function renderSetupView() {
  return `
    <div class="auth-wrapper">
      <div class="auth-card">
        <div class="auth-header">
          <div class="auth-logo">TS</div>
          <h1 class="auth-title">تهيئة نظام TeacherSystem</h1>
          <p class="auth-desc">مرحباً بك! يرجى إنشاء حساب المعلم الأساسي للمرة الأولى للبدء في إدارة فصولك ومساعديك.</p>
        </div>

        <form id="setup-form">
          <div class="form-group">
            <label class="form-label required">اسم المعلم بالكامل</label>
            <input type="text" id="setup-fullname" class="form-input" placeholder="مثال: أ. أحمد محمود" required minlength="2">
          </div>

          <div class="form-group">
            <label class="form-label required">اسم المستخدم للنظام</label>
            <input type="text" id="setup-username" class="form-input" placeholder="مثال: mr_ahmed" required pattern="^[a-zA-Z0-9_\\-\\.]+$">
            <span class="form-hint">يُستخدم لتسجيل الدخول (حروف إنجليزية وأرقام ونقاط فقط)</span>
          </div>

          <div class="form-group">
            <label class="form-label required">رقم الهاتف الشخصي</label>
            <input type="tel" id="setup-phone" class="form-input" placeholder="01012345678" required minlength="10">
          </div>

          <div class="form-group">
            <label class="form-label required">كلمة المرور</label>
            <input type="password" id="setup-password" class="form-input" placeholder="••••••••" required minlength="8">
            <div id="password-strength-feedback" class="form-hint" style="margin-top:0.35rem; font-weight:600;"></div>
          </div>

          <button type="submit" id="setup-submit-btn" class="btn btn-primary" style="width:100%; margin-top:1.25rem; padding:0.75rem;">
            إتمام التهيئة وحفظ الحساب
          </button>
        </form>
      </div>
    </div>
  `;
}

// --- View 2: Login Screen ---
function renderLoginView() {
  const isLocked = state.rateLimitRemaining > 0;
  return `
    <div class="auth-wrapper">
      <div class="auth-card">
        <div class="auth-header">
          <div class="auth-logo">TS</div>
          <h1 class="auth-title">تسجيل الدخول</h1>
          <p class="auth-desc">نظام إدارة المعلم التجاري والأكاديمي المتكامل</p>
        </div>

        ${isLocked ? `
          <div style="background-color:var(--danger-bg); border:1px solid var(--danger-border); color:var(--danger-text); padding:0.75rem 1rem; border-radius:var(--radius-md); margin-bottom:1.25rem; font-size:0.85rem; font-weight:600;">
            ⚠️ تم قفل محاولات الدخول مؤقتاً لحماية الحساب من محاولات التخمين.
            <div style="margin-top:0.35rem; font-size:0.95rem; font-weight:800;" id="lockout-timer-display">
              يرجى الانتظار ${state.rateLimitRemaining} ثانية...
            </div>
          </div>
        ` : ''}

        <form id="login-form">
          <div class="form-group">
            <label class="form-label required">اسم المستخدم</label>
            <input type="text" id="login-username" class="form-input" placeholder="اسم المستخدم" required ${isLocked ? 'disabled' : ''}>
          </div>

          <div class="form-group">
            <label class="form-label required">كلمة المرور</label>
            <input type="password" id="login-password" class="form-input" placeholder="••••••••" required ${isLocked ? 'disabled' : ''}>
          </div>

          <button type="submit" id="login-submit-btn" class="btn btn-primary" style="width:100%; margin-top:1.25rem; padding:0.75rem;" ${isLocked ? 'disabled' : ''}>
            دخول إلى النظام
          </button>
        </form>

        <div style="margin-top:1.75rem; text-align:center; font-size:0.75rem; color:var(--slate-400);">
          TeacherSystem v1.0 • تشغيل محلي آمن في شبكة السنتر
        </div>
      </div>
    </div>
  `;
}

// --- Layout: Shell with Sidebar & Header ---
function renderAppShell(contentHtml, activeRoute) {
  const user = state.user || {};
  const isTeacher = user.user_type === 'teacher';
  const todayArabic = new Intl.DateTimeFormat('ar-EG', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date());

  return `
    <div class="app-container">
      <!-- Right-to-Left Master Sidebar Drawer -->
      <aside class="app-sidebar" id="app-sidebar" aria-label="القائمة الجانبية الرئيسية">
        <div class="sidebar-header">
          <div class="brand-icon">TS</div>
          <div class="brand-info">
            <span class="brand-title">TeacherSystem</span>
            <span class="brand-subtitle">${isTeacher ? 'بوابة المعلم الأساسي' : 'بوابة المساعد المعتمد'}</span>
          </div>
          <button type="button" id="close-sidebar-btn" class="sidebar-close-btn" aria-label="إغلاق القائمة">✕</button>
        </div>

        <nav class="sidebar-nav">
          <div class="nav-section-title">نظرة عامة</div>
          <a href="#/dashboard" class="nav-link ${activeRoute === 'dashboard' ? 'active' : ''}">
            ${icons.dashboard}
            <span>الرئيسية والمؤشرات</span>
          </a>

          <div class="nav-section-title">إدارة الفريق</div>
          <a href="#/assistants" class="nav-link ${activeRoute === 'assistants' ? 'active' : ''}">
            ${icons.assistants}
            <span>فريق المساعدين</span>
          </a>

          <div class="nav-section-title">العمليات الأكاديمية</div>
          <a href="#/students" class="nav-link ${activeRoute === 'students' ? 'active' : ''}">
            ${icons.users}
            <span>الطلاب والمجموعات</span>
          </a>
          <a href="#/attendance" class="nav-link ${activeRoute === 'attendance' ? 'active' : ''}">
            ${icons.attendance}
            <span>رصد الحضور والحصص</span>
          </a>
          <a href="#/exams" class="nav-link ${activeRoute === 'exams' ? 'active' : ''}">
            ${icons.exams}
            <span>الامتحانات والدرجات</span>
          </a>
          <a href="#/cash" class="nav-link ${activeRoute === 'cash' ? 'active' : ''}">
            ${icons.cash}
            <span>التحصيل والنقدية</span>
          </a>

          <div class="nav-section-title">التحليلات والنظام</div>
          <a href="#/analytics" class="nav-link" style="opacity:0.55; cursor:not-allowed;" title="قريباً في المرحلة 2">
            ${icons.analytics}
            <span>مركز تحليلات الأستاذ</span>
            <span class="nav-link-badge">المرحلة 2</span>
          </a>
          <a href="#/system" class="nav-link ${activeRoute === 'system' ? 'active' : ''}">
            ${icons.system}
            <span>النسخ الاحتياطي والنظام</span>
          </a>
        </nav>

        <div class="sidebar-footer">
          <div class="user-profile-widget">
            <div class="user-avatar">${(user.full_name || 'U')[0]}</div>
            <div class="user-meta">
              <div class="user-name" title="${user.full_name || ''}">${user.full_name || 'المستخدم'}</div>
              <div class="user-role">${isTeacher ? 'أستاذ المادة (مالك النظام)' : 'مساعد معتمد'}</div>
            </div>
          </div>
          <button id="logout-btn" class="btn btn-secondary btn-sm" style="width:100%; gap:0.4rem;">
            ${icons.logout}
            <span>تسجيل الخروج</span>
          </button>
        </div>
      </aside>

      <!-- Overlay Drawer Backdrop for Smaller Screens -->
      <div id="sidebar-backdrop" class="sidebar-backdrop" aria-hidden="true"></div>

      <!-- Main Canvas Area -->
      <div class="app-main">
        <header class="app-header">
          <div style="display:flex; align-items:center; gap:0.75rem;">
            <button type="button" id="mobile-menu-toggle" class="mobile-menu-btn" aria-label="فتح القائمة الجانبية">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </button>
            <div style="font-size:0.9rem; font-weight:700; color:var(--slate-800);">TeacherSystem</div>
          </div>

          <div class="header-actions">
            <div style="font-size:0.8rem; color:var(--slate-500); font-weight:600;">
              ${todayArabic}
            </div>
            <div class="status-indicator">
              <span class="status-dot"></span>
              <span>سيرفر السنتر متصل محلياً</span>
            </div>
          </div>
        </header>

        <main class="app-content">
          ${contentHtml}
        </main>
      </div>
    </div>
  `;
}

// --- View 3: Dashboard View (Operational Command Center) ---
function renderDashboardView() {
  const user = state.user || {};
  const isTeacher = user.is_teacher || user.user_type === 'teacher';
  const canViewAttendance = isTeacher || user.can_view_attendance;
  const canViewGrades = isTeacher || user.can_view_grades || user.can_manage_exams || user.can_enter_grades;
  const canViewFinances = isTeacher || user.can_view_financial_analytics || user.can_view_student_payment_history || user.can_collect_cash || user.can_manage_fees;
  const canCollectCash = isTeacher || user.can_collect_cash;

  const now = new Date();
  const dateOptions = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  const localizedDate = now.toLocaleDateString('ar-EG', dateOptions);
  const currentBillingMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

  const rep = state.dashboardFinanceReport;
  const ov = state.dashboardFinanceOverview;

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">مركز العمليات والتحكم</h1>
        <p class="page-subtitle">مرحباً بك يا ${user.full_name || 'أستاذنا'}. مساحة عملك معزولة ومحمية بالكامل.</p>
      </div>
      <div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;">
        <span class="badge badge-primary" style="padding:0.45rem 0.85rem; font-size:0.85rem;">
          ${icons.calendar}
          <span>${localizedDate}</span>
        </span>
      </div>
    </div>

    <!-- Quick Actions Toolbar -->
    <div class="quick-actions-bar">
      <div class="quick-actions-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
        <span>إجراءات سريعة:</span>
      </div>
      <a href="#/students?action=add_student" class="btn btn-primary btn-sm">
        ${icons.plus}
        <span>إضافة طالب جديد</span>
      </a>
      <a href="#/students?tab=groups" class="btn btn-secondary btn-sm">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
        <span>المجموعات والشُعب</span>
      </a>
      <a href="#/attendance" class="btn btn-secondary btn-sm">
        ${icons.attendance}
        <span>رصد الحضور</span>
      </a>
      <a href="#/exams?action=create_exam" class="btn btn-secondary btn-sm">
        ${icons.exams}
        <span>إنشاء امتحان</span>
      </a>
      ${canCollectCash ? `
        <a href="#/cash?action=record_payment" class="btn btn-secondary btn-sm">
          ${icons.cash}
          <span>تحصيل نقدية</span>
        </a>
      ` : ''}
      ${isTeacher ? `
        <a href="#/assistants" class="btn btn-secondary btn-sm">
          ${icons.assistants}
          <span>إدارة المساعدين</span>
        </a>
      ` : ''}
    </div>

    <!-- KPI Metric Cards -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-header">
          <span>إجمالي الطلاب المقيدين</span>
          ${icons.users}
        </div>
        <div class="kpi-value">${state.students.length}</div>
        <div class="kpi-meta">طالب مسجل في مساحة عملك</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <span>المجموعات والشُعب</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
        </div>
        <div class="kpi-value">${state.groups.length}</div>
        <div class="kpi-meta">مجموعة دراسية نشطة ومجدولة</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <span>حصص اليوم</span>
          ${icons.attendance}
        </div>
        <div class="kpi-value">${state.todaySessions ? state.todaySessions.length : 0}</div>
        <div class="kpi-meta">${state.todaySessions && state.todaySessions.length > 0 ? 'حصص مجدولة لهذا اليوم' : 'لا توجد حصص مجدولة اليوم'}</div>
      </div>

      <div class="kpi-card">
        ${canViewFinances && rep ? `
          <div class="kpi-header">
            <span>تحصيل نقدية الشهر (${currentBillingMonth})</span>
            ${icons.cash}
          </div>
          <div class="kpi-value" style="color:var(--primary); font-size:1.5rem;">${formatEGP(rep.cash_received_in_month_egp)}</div>
          <div class="kpi-meta">نسبة التحصيل: ${rep.collection_rate_percent}% من المطالبات</div>
        ` : `
          <div class="kpi-header">
            <span>فريق المساعدين</span>
            ${icons.assistants}
          </div>
          <div class="kpi-value">${state.assistants.length}</div>
          <div class="kpi-meta">مساعدين نشطين تحت إشرافك</div>
        `}
      </div>
    </div>

    <!-- Section A: Today's Scheduled Sessions -->
    <div class="card dashboard-full-width">
      <div class="card-header">
        <div style="display:flex; align-items:center; gap:0.5rem;">
          ${icons.attendance}
          <h2 class="card-title">حصص اليوم (${localizedDate})</h2>
        </div>
        <div style="display:flex; gap:0.5rem;">
          <a href="#/attendance?action=add_session" class="btn btn-secondary btn-sm">
            ${icons.plus}
            <span>جدولة حصة جديدة</span>
          </a>
          <a href="#/attendance" class="btn btn-secondary btn-sm">جدول الحصص الكامل ←</a>
        </div>
      </div>

      ${!canViewAttendance ? `
        <div class="dashboard-alert-banner">
          🔒 ليس لديك صلاحية استعراض جدول الحصص وتسجيل الحضور.
        </div>
      ` : (state.dashboardError && state.dashboardError.sessions) ? `
        <div class="dashboard-alert-banner" style="color:var(--danger); border-color:#FCA5A5; background-color:#FEF2F2;">
          ⚠️ ${state.dashboardError.sessions}
        </div>
      ` : (!state.todaySessions || state.todaySessions.length === 0) ? `
        <div class="dashboard-card-empty">
          <div class="empty-icon">📅</div>
          <div class="empty-title">لا توجد حصص مجدولة لليوم</div>
          <div class="empty-sub">لم يتم تسجيل حصص دراسية بتاريخ اليوم (${todayStr}). يمكنك جدولة حصة الآن أو استعراض جدول الحصص الكامل.</div>
          <a href="#/attendance?action=add_session" class="btn btn-primary btn-sm">جدولة حصة الآن</a>
        </div>
      ` : `
        <div class="table-container" style="border:none;">
          <table class="data-table">
            <thead>
              <tr>
                <th>المجموعة الدراسية</th>
                <th>المرحلة</th>
                <th>الموعد</th>
                <th>المكان</th>
                <th>الحالة</th>
                <th>نسبة الحضور</th>
                <th style="text-align:left;">إجراءات</th>
              </tr>
            </thead>
            <tbody>
              ${state.todaySessions.map(s => {
                const stats = s.stats || { total_enrolled: 0, present_count: 0, late_count: 0 };
                const attended = stats.present_count + stats.late_count;
                const total = stats.total_enrolled;
                const rate = total > 0 ? Math.round((attended / total) * 100) : 0;
                
                let badgeClass = 'badge-primary';
                if (s.status === 'completed') badgeClass = 'badge-success';
                else if (s.status === 'cancelled') badgeClass = 'badge-danger';

                return `
                  <tr>
                    <td style="font-weight:700;">${s.group_name || 'مجموعة'}</td>
                    <td><span class="badge badge-neutral">${s.grade_label || s.grade_level || '-'}</span></td>
                    <td class="tabular-nums">
                      <div>${s.start_time || '-'}${s.end_time ? ' - ' + s.end_time : ''}</div>
                    </td>
                    <td>${s.location || 'المقر الرئيسي'}</td>
                    <td><span class="badge ${badgeClass}">${s.status_label || s.status}</span></td>
                    <td>
                      ${total > 0 ? `
                        <span style="font-weight:700; color:#059669;">${attended} / ${total}</span>
                        <span style="font-size:0.75rem; color:var(--slate-500);">(${rate}%)</span>
                      ` : `
                        <span style="color:var(--slate-400); font-size:0.8rem;">لم يُرصد بعد</span>
                      `}
                    </td>
                    <td style="text-align:left;">
                      <a href="#/attendance?session_id=${s.id}" class="btn btn-primary btn-sm open-session-attendance-btn" data-id="${s.id}">
                        ${icons.attendance}
                        <span>فتح سجل الحضور</span>
                      </a>
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      `}
    </div>

    <!-- 2-Column Operational Grid: Finance Summary + Recent Exams -->
    <div class="dashboard-grid">
      
      <!-- Section B: Finance Summary & Collection Health -->
      <div class="card">
        <div class="card-header">
          <div style="display:flex; align-items:center; gap:0.5rem;">
            ${icons.cash}
            <h2 class="card-title">المؤشر المالي لشهر ${currentBillingMonth}</h2>
          </div>
          ${canViewFinances ? `
            <a href="#/cash" class="btn btn-secondary btn-sm">دفتر التحصيل ←</a>
          ` : ''}
        </div>

        ${!canViewFinances ? `
          <div class="dashboard-alert-banner">
            🔒 تقتصر البيانات المالية على المعلم والمساعدين الممنوحين صلاحيات مالية.
          </div>
        ` : (state.dashboardError && state.dashboardError.finance) ? `
          <div class="dashboard-alert-banner" style="color:var(--danger); border-color:#FCA5A5; background-color:#FEF2F2;">
            ⚠️ ${state.dashboardError.finance}
          </div>
        ` : rep ? `
          <div>
            <div class="dashboard-finance-grid">
              <div class="dashboard-finance-box" style="border-right:3px solid #059669;">
                <div class="df-label">نقدية محصلة في الشهر (Cash Received)</div>
                <div class="df-val tabular-nums" style="color:#059669;">${formatEGP(rep.cash_received_in_month_egp)}</div>
              </div>
              <div class="dashboard-finance-box" style="border-right:3px solid var(--secondary);">
                <div class="df-label">مطالبات ورسوم الشهر (Billed Charges)</div>
                <div class="df-val tabular-nums" style="color:var(--secondary);">${formatEGP(rep.charges_generated_egp)}</div>
              </div>
              <div class="dashboard-finance-box" style="border-right:3px solid #DC2626;">
                <div class="df-label">المتبقي غير المحصل (Outstanding)</div>
                <div class="df-val tabular-nums" style="color:#DC2626;">${formatEGP(rep.outstanding_balance_egp)}</div>
              </div>
              <div class="dashboard-finance-box" style="border-right:3px solid var(--primary);">
                <div class="df-label">نسبة التحصيل (Collection Rate)</div>
                <div class="df-val tabular-nums" style="color:var(--primary);">${rep.collection_rate_percent}%</div>
              </div>
            </div>

            ${ov ? `
              <div style="font-size:0.8rem; color:var(--slate-500); display:flex; justify-content:space-between; align-items:center; padding-top:0.5rem; border-top:1px solid var(--border);">
                <span>إجمالي الرصيد المعلق تاريخياً: <strong style="color:#DC2626;">${formatEGP(ov.total_outstanding_balance_egp !== undefined ? ov.total_outstanding_balance_egp : ov.total_outstanding_dues_egp)}</strong></span>
                <span>إجمالي المحصل تاريخياً: <strong style="color:#059669;">${formatEGP(ov.total_cash_collected_egp !== undefined ? ov.total_cash_collected_egp : ov.total_collected_all_time_egp)}</strong></span>
              </div>
            ` : ''}

            <div style="margin-top:1rem; display:flex; gap:0.5rem; flex-wrap:wrap;">
              ${canCollectCash ? `
                <a href="#/cash?action=record_payment" class="btn btn-primary btn-sm">
                  ${icons.plus}
                  <span>تحصيل نقدية جديدة</span>
                </a>
              ` : ''}
              <a href="#/cash?tab=dues" class="btn btn-secondary btn-sm">استعراض المطالبات المعلقة</a>
            </div>
          </div>
        ` : `
          <div class="dashboard-card-empty">
            <div class="empty-icon">💰</div>
            <div class="empty-title">لا توجد بيانات مالية لشهر ${currentBillingMonth}</div>
            <div class="empty-sub">لم يتم توليد مطالبات شهرية أو تحصيل نقدية بعد لهذا الشهر.</div>
            <a href="#/cash" class="btn btn-secondary btn-sm">الانتقال للموديول المالي</a>
          </div>
        `}
      </div>

      <!-- Section C: Recent Exams & Evaluations -->
      <div class="card">
        <div class="card-header">
          <div style="display:flex; align-items:center; gap:0.5rem;">
            ${icons.exams}
            <h2 class="card-title">الامتحانات والتقييمات الأخيرة</h2>
          </div>
          ${canViewGrades ? `
            <a href="#/exams" class="btn btn-secondary btn-sm">سجل الامتحانات ←</a>
          ` : ''}
        </div>

        ${!canViewGrades ? `
          <div class="dashboard-alert-banner">
            🔒 ليس لديك صلاحية استعراض الامتحانات ودرجات الطلاب.
          </div>
        ` : (state.dashboardError && state.dashboardError.exams) ? `
          <div class="dashboard-alert-banner" style="color:var(--danger); border-color:#FCA5A5; background-color:#FEF2F2;">
            ⚠️ ${state.dashboardError.exams}
          </div>
        ` : (!state.recentExams || state.recentExams.length === 0) ? `
          <div class="dashboard-card-empty">
            <div class="empty-icon">📝</div>
            <div class="empty-title">لا توجد امتحانات مسجلة مؤخراً</div>
            <div class="empty-sub">ابدأ بإضافة أول امتحان لتقييم درجات الطلاب ومتابعة مستواهم.</div>
            <a href="#/exams?action=create_exam" class="btn btn-secondary btn-sm">إنشاء امتحان جديد</a>
          </div>
        ` : `
          <div style="display:flex; flex-direction:column; gap:0.75rem;">
            ${state.recentExams.map(ex => {
              const stats = ex.stats || { total_students: 0, graded_count: 0, pending_count: 0, pass_rate_percent: null, average_score: null };
              return `
                <div style="border:1px solid var(--border); border-radius:var(--radius-md); padding:0.75rem 1rem; background-color:var(--surface-hover);">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.4rem;">
                    <div>
                      <div style="font-weight:700; font-size:0.95rem; color:var(--slate-800);">${ex.title}</div>
                      <div style="font-size:0.78rem; color:var(--slate-500);">${ex.group_name || 'المجموعة'} • ${ex.exam_date}</div>
                    </div>
                    <span class="badge ${ex.status === 'completed' ? 'badge-success' : ex.status === 'grading' ? 'badge-primary' : 'badge-neutral'}">
                      ${ex.status_label || ex.status}
                    </span>
                  </div>
                  
                  <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.8rem; margin-top:0.4rem; color:var(--slate-600);">
                    <div>
                      <span>نسبة النجاح: </span>
                      <strong style="color:var(--primary);">${stats.pass_rate_percent != null ? stats.pass_rate_percent + '%' : '-'}</strong>
                    </div>
                    <div>
                      <span>المتوسط: </span>
                      <strong class="tabular-nums">${stats.average_score != null ? stats.average_score.toFixed(1) + ' / ' + ex.max_score : '-'}</strong>
                    </div>
                    <div>
                      <span>رُصد: </span>
                      <strong class="tabular-nums">${stats.graded_count} / ${stats.total_students}</strong>
                    </div>
                  </div>

                  <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.6rem; padding-top:0.5rem; border-top:1px dashed var(--border);">
                    <div>
                      ${stats.pending_count > 0 ? `
                        <span class="badge badge-secondary" style="font-size:0.75rem;">بانتظار رصد ${stats.pending_count}</span>
                      ` : `
                        <span class="badge badge-success" style="font-size:0.75rem;">الرصد مكتمل</span>
                      `}
                    </div>
                    <a href="#/exams?exam_id=${ex.id}" class="btn btn-secondary btn-sm open-exam-grades-btn" data-id="${ex.id}">
                      ${icons.exams}
                      <span>رصد / عرض الدرجات</span>
                    </a>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        `}
      </div>

    </div>

    <!-- Assistants Table (Teacher Workspace View) -->
    ${isTeacher ? `
      <div class="card" style="margin-top:1.25rem;">
        <div class="card-header">
          <div style="display:flex; align-items:center; gap:0.5rem;">
            ${icons.assistants}
            <h2 class="card-title">مساعدو المعلم المسجلون</h2>
          </div>
          <a href="#/assistants" class="btn btn-secondary btn-sm">إدارة الفريق</a>
        </div>
        ${state.assistants.length === 0 ? `
          <div class="dashboard-card-empty">
            <div class="empty-icon">👥</div>
            <div class="empty-title">لا يوجد مساعدين مسجلين حالياً</div>
            <div class="empty-sub">أضف أول مساعد لمنحه صلاحيات تسجيل الحضور أو تحصيل النقدية.</div>
            <a href="#/assistants" class="btn btn-primary btn-sm">إضافة مساعد جديد</a>
          </div>
        ` : `
          <div class="table-container" style="border:none;">
            <table class="data-table">
              <thead>
                <tr>
                  <th>الاسم الكامل</th>
                  <th>اسم الدخول</th>
                  <th>رقم الهاتف</th>
                  <th>الحالة</th>
                </tr>
              </thead>
              <tbody>
                ${state.assistants.slice(0, 5).map(a => `
                  <tr>
                    <td style="font-weight:700;">${a.full_name}</td>
                    <td class="tabular-nums" style="color:var(--slate-500); font-family:monospace;">${a.username}</td>
                    <td class="tabular-nums">${a.phone}</td>
                    <td><span class="badge ${a.is_active ? 'badge-success' : 'badge-danger'}">${a.is_active ? 'نشط' : 'معطل'}</span></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    ` : ''}
  `;
}

// --- Dashboard Event Handlers ---
function bindDashboardEvents() {
  // One-click attendance sheet trigger
  document.querySelectorAll('.open-session-attendance-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      if (id) {
        state.activeSessionId = isNaN(id) ? id : parseInt(id, 10);
      }
    });
  });

  // One-click exam results sheet trigger
  document.querySelectorAll('.open-exam-grades-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      if (id) {
        state.activeExamId = isNaN(id) ? id : parseInt(id, 10);
      }
    });
  });
}

// --- View 4: Assistant Management View ---
function renderAssistantsView() {
  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">فريق المساعدين والصلاحيات</h1>
        <p class="page-subtitle">إدارة مساعدي المدرس وتعيين الصلاحيات التفصيلية بدقة وأمان.</p>
      </div>
      <div>
        <button id="open-add-assistant-modal" class="btn btn-primary">
          ${icons.plus}
          <span>إضافة مساعد جديد</span>
        </button>
      </div>
    </div>

    <div class="table-container">
      <div class="table-header-bar">
        <div style="font-weight:700; color:var(--slate-800);">قائمة المساعدين (${state.assistants.length})</div>
        <div style="font-size:0.8rem; color:var(--slate-500);">البيانات معزولة إجبارياً لمساحة عملك ولا يراها أي مدرس آخر</div>
      </div>

      ${state.assistants.length === 0 ? `
        <div class="empty-state-card">
          <div class="empty-state-icon">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <line x1="19" y1="8" x2="19" y2="14"></line>
              <line x1="22" y1="11" x2="16" y2="11"></line>
            </svg>
          </div>
          <h3 class="empty-state-title">لا يوجد مساعدون مسجلون في مساحة عملك</h3>
          <p class="empty-state-desc">
            أضف أعضاء فريقك لمساعدتك في رصد حضور الحصص، أو تحصيل المصروفات، أو إدخال الدرجات مع التحكم الكامل في صلاحيات كل مساعد وتأمين سرية إيراداتك.
          </p>
          <button type="button" id="open-add-assistant-empty" class="btn btn-primary empty-state-btn">
            ${icons.plus}
            <span>إضافة أول مساعد</span>
          </button>
        </div>
      ` : `
        <table class="data-table">
          <thead>
            <tr>
              <th>المساعد</th>
              <th>اسم الدخول</th>
              <th>رقم الهاتف</th>
              <th>الصلاحيات الممنوحة</th>
              <th>الحالة</th>
              <th style="text-align:center;">إجراءات</th>
            </tr>
          </thead>
          <tbody>
            ${state.assistants.map(a => `
              <tr>
                <td>
                  <div style="font-weight:700; color:var(--slate-900);">${a.full_name}</div>
                  <div style="font-size:0.75rem; color:var(--slate-400);">انضم: ${new Date(a.created_at).toLocaleDateString('ar-EG')}</div>
                </td>
                <td class="tabular-nums" style="font-family:monospace; font-weight:600; color:var(--primary);">${a.username}</td>
                <td class="tabular-nums">${a.phone}</td>
                <td>
                  <div style="display:flex; flex-wrap:wrap; gap:0.25rem; max-width:320px;">
                    ${a.can_mark_attendance ? `<span class="badge badge-primary">تسجيل حضور</span>` : ''}
                    ${a.can_collect_cash ? `<span class="badge badge-secondary">تحصيل نقدية</span>` : ''}
                    ${a.can_manage_fees ? `<span class="badge badge-warning">إدارة رسوم</span>` : ''}
                    ${a.can_enter_grades ? `<span class="badge badge-neutral">رصد درجات</span>` : ''}
                    ${a.can_manage_students ? `<span class="badge badge-neutral">إدارة طلاب</span>` : ''}
                    ${a.can_view_financial_analytics ? `<span class="badge badge-danger">تحليلات مالية</span>` : ''}
                    ${a.can_request_messages ? `<span class="badge badge-neutral">طلب رسائل</span>` : ''}
                  </div>
                </td>
                <td>
                  <span class="badge ${a.is_active ? 'badge-success' : 'badge-danger'}">
                    ${a.is_active ? 'نشط' : 'معطل'}
                  </span>
                </td>
                <td style="text-align:center;">
                  <div style="display:flex; justify-content:center; gap:0.4rem;">
                    <button class="btn btn-secondary btn-sm edit-assistant-btn" data-id="${a.id}" title="تعديل البيانات والصلاحيات">
                      ${icons.edit}
                    </button>
                    <button class="btn btn-secondary btn-sm delete-assistant-btn" data-id="${a.id}" data-name="${a.full_name}" title="حذف المساعد وإلغاء جلساته">
                      ${icons.trash}
                    </button>
                  </div>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `}
    </div>

    <!-- Modal: Add / Edit Assistant -->
    <div id="assistant-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title" id="assistant-modal-title">إضافة مساعد جديد</h3>
          <button type="button" class="modal-close" id="close-assistant-modal">✕</button>
        </div>
        <form id="assistant-form">
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label required">الاسم بالكامل</label>
              <input type="text" id="ass-fullname" class="form-input" placeholder="مثال: محمد علي" required minlength="2">
            </div>

            <div class="form-group" id="ass-username-group">
              <label class="form-label required">اسم المستخدم للدخول</label>
              <input type="text" id="ass-username" class="form-input" placeholder="مثال: ass_mohamed" required pattern="^[a-zA-Z0-9_\\-\\.]+$">
              <span class="form-hint">حروف إنجليزية وأرقام بدون مسافات (لا يمكن تغييره لاحقاً)</span>
            </div>

            <div class="form-group">
              <label class="form-label required">رقم الهاتف</label>
              <input type="tel" id="ass-phone" class="form-input" placeholder="010XXXXXXXX" required minlength="10">
            </div>

            <div class="form-group" id="ass-password-group">
              <label class="form-label required">كلمة المرور المؤقتة</label>
              <input type="password" id="ass-password" class="form-input" placeholder="••••••••" minlength="8">
              <div id="ass-password-feedback" class="form-hint" style="margin-top:0.35rem; font-weight:600;"></div>
            </div>

            <div style="margin-top:1.25rem;">
              <label class="form-label" style="margin-bottom:0.5rem; display:block;">مصفوفة الصلاحيات الممنوحة</label>
              
              <div style="display:grid; grid-template-columns: 1fr; gap:0.5rem;">
                <label class="checkbox-group">
                  <input type="checkbox" id="perm-mark-attendance" checked>
                  <div>
                    <div style="font-weight:700; font-size:0.85rem;">تسجيل الحضور والغياب</div>
                    <div style="font-size:0.75rem; color:var(--slate-500);">السماح برصد غياب الحصص ومسح بطاقات الطلاب</div>
                  </div>
                </label>

                <label class="checkbox-group">
                  <input type="checkbox" id="perm-collect-cash">
                  <div>
                    <div style="font-weight:700; font-size:0.85rem;">تحصيل الرسوم والنقدية</div>
                    <div style="font-size:0.75rem; color:var(--slate-500);">السماح باستلام أموال الاشتراكات وإصدار إيصالات (مفصولة عن رؤية أرباح المدرس)</div>
                  </div>
                </label>

                <label class="checkbox-group">
                  <input type="checkbox" id="perm-manage-fees">
                  <div>
                    <div style="font-weight:700; font-size:0.85rem;">إدارة وضبط الرسوم والمستحقات</div>
                    <div style="font-size:0.75rem; color:var(--slate-500);">السماح بتحديد قيمة رسوم المجموعات وتوليد وإلغاء الرسوم الشهرية ورسوم الحصص</div>
                  </div>
                </label>

                <label class="checkbox-group">
                  <input type="checkbox" id="perm-enter-grades">
                  <div>
                    <div style="font-weight:700; font-size:0.85rem;">إدخال ورصد الدرجات</div>
                    <div style="font-size:0.75rem; color:var(--slate-500);">إدخال نتائج الامتحانات والتسميع الدوري</div>
                  </div>
                </label>

                <label class="checkbox-group">
                  <input type="checkbox" id="perm-manage-students">
                  <div>
                    <div style="font-weight:700; font-size:0.85rem;">إدارة وتعديل بيانات الطلاب</div>
                    <div style="font-size:0.75rem; color:var(--slate-500);">تسجيل طالب جديد أو تحديث أرقام أولياء الأمور</div>
                  </div>
                </label>

                <label class="checkbox-group" style="border-color:#FDE68A; background-color:#FFFBEB;">
                  <input type="checkbox" id="perm-financial-analytics">
                  <div>
                    <div style="font-weight:700; font-size:0.85rem; color:#92400E;">الاطلاع على التحليلات المالية (حساس للمدرس فقط)</div>
                    <div style="font-size:0.75rem; color:#B45309;">تنبيه: تمكن المساعد من رؤية دخل السنتر وإيرادات المعلم. يُفضل تركها غير مفعلة.</div>
                  </div>
                </label>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="cancel-assistant-btn">إلغاء</button>
            <button type="submit" class="btn btn-primary" id="save-assistant-btn">حفظ المساعد وتأكيد الصلاحيات</button>
          </div>
        </form>
      </div>
    </div>
  `;
}

// --- View 4.5: Academic View (Students & Groups) ---
function renderAcademicView() {
  const isStudentsTab = state.activeAcademicTab === 'students';

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">إدارة الطلاب والمجموعات</h1>
        <p class="page-subtitle">سجل الطلاب وشُعب الحصص مع التوزيع الأكاديمي والتحكم في الاشتراكات.</p>
      </div>
      <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
        <button type="button" id="open-add-student-modal" class="btn btn-primary">
          ${icons.plus}
          <span>إضافة طالب جديد</span>
        </button>
        <button type="button" id="open-add-group-modal" class="btn btn-secondary">
          ${icons.plus}
          <span>إضافة مجموعة جديدة</span>
        </button>
      </div>
    </div>

    <!-- Segmented Navigation Tabs -->
    <div class="tab-nav">
      <button type="button" class="tab-btn ${state.activeAcademicTab === 'students' ? 'active' : ''}" id="tab-btn-students">
        ${icons.users}
        <span>سجل الطلاب (${state.students.length})</span>
      </button>
      <button type="button" class="tab-btn ${state.activeAcademicTab === 'groups' ? 'active' : ''}" id="tab-btn-groups">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
        <span>المجموعات والشُعب (${state.groups.length})</span>
      </button>
      <button type="button" class="tab-btn ${state.activeAcademicTab === 'distribution' ? 'active' : ''}" id="tab-btn-distribution">
        ${icons.barcode}
        <span>توزيع بطاقات الباركود 💳</span>
      </button>
    </div>

    ${state.activeAcademicTab === 'students' ? renderStudentsTabContent() : (state.activeAcademicTab === 'groups' ? renderGroupsTabContent() : renderDistributionTabContent())}

    <!-- Modal: Add / Edit Student -->
    <div id="student-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title" id="student-modal-title">إضافة طالب جديد</h3>
          <button type="button" class="modal-close" id="close-student-modal">✕</button>
        </div>
        <form id="student-form">
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label required">اسم الطالب بالكامل</label>
              <input type="text" id="stud-fullname" class="form-input" placeholder="مثال: يوسف محمود حسن" required minlength="2">
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.75rem;">
              <div class="form-group">
                <label class="form-label required">الصف الدراسي</label>
                <select id="stud-grade" class="form-input" required>
                  <option value="1_sec">الصف الأول الثانوي</option>
                  <option value="2_sec">الصف الثاني الثانوي</option>
                  <option value="3_sec">الصف الثالث الثانوي</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label required">هاتف الطالب</label>
                <input type="tel" id="stud-phone" class="form-input tabular-nums" placeholder="010XXXXXXXX" required minlength="7">
              </div>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.75rem;">
              <div class="form-group">
                <label class="form-label">اسم ولي الأمر</label>
                <input type="text" id="stud-parent-name" class="form-input" placeholder="مثال: أ. محمود حسن">
              </div>

              <div class="form-group">
                <label class="form-label">هاتف ولي الأمر</label>
                <input type="tel" id="stud-parent-phone" class="form-input tabular-nums" placeholder="011XXXXXXXX">
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">العنوان أو المنطقة</label>
              <input type="text" id="stud-address" class="form-input" placeholder="مثال: الدقي، الجيزة">
            </div>

            <div class="form-group">
              <label class="form-label">ملاحظات إضافية</label>
              <textarea id="stud-notes" class="form-input" rows="2" placeholder="ملاحظات حول مستوى الطالب أو خصومات..."></textarea>
            </div>

            <label class="checkbox-group">
              <input type="checkbox" id="stud-active" checked>
              <div>
                <div style="font-weight:700; font-size:0.85rem;">حساب الطالب نشط</div>
                <div style="font-size:0.75rem; color:var(--slate-500);">الطلاب غير النشطين يتم إيقافهم دون حذف سجلاتهم التاريخية.</div>
              </div>
            </label>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="cancel-student-btn">إلغاء</button>
            <button type="submit" class="btn btn-primary" id="save-student-btn">حفظ بيانات الطالب</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Modal: Add / Edit Group -->
    <div id="group-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title" id="group-modal-title">إضافة مجموعة جديدة</h3>
          <button type="button" class="modal-close" id="close-group-modal">✕</button>
        </div>
        <form id="group-form">
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label required">اسم المجموعة</label>
              <input type="text" id="grp-name" class="form-input" placeholder="مثال: سنتر الأوائل - السبت والثلاثاء 4 عصراً" required minlength="2">
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.75rem;">
              <div class="form-group">
                <label class="form-label required">الصف الدراسي</label>
                <select id="grp-grade" class="form-input" required>
                  <option value="1_sec">الصف الأول الثانوي</option>
                  <option value="2_sec">الصف الثاني الثانوي</option>
                  <option value="3_sec">الصف الثالث الثانوي</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">المادة أو الفرع</label>
                <input type="text" id="grp-subject" class="form-input" placeholder="مثال: فيزياء عامة، جبر وهندسة">
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">مواعيد ومكان الحصة</label>
              <input type="text" id="grp-schedule" class="form-input" placeholder="مثال: الأحد والأربعاء 5:00 - 7:00 م (قاعة 1)">
            </div>

            <label class="checkbox-group">
              <input type="checkbox" id="grp-active" checked>
              <div>
                <div style="font-weight:700; font-size:0.85rem;">المجموعة نشطة وتستقبل حصصاً</div>
                <div style="font-size:0.75rem; color:var(--slate-500);">يمكن إيقاف المجموعة مؤقتاً عند انتهاء الفصل الدراسي.</div>
              </div>
            </label>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="cancel-group-btn">إلغاء</button>
            <button type="submit" class="btn btn-primary" id="save-group-btn">حفظ المجموعة</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Modal: Manage Student Groups -->
    <div id="student-groups-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content" style="max-width:580px;">
        <div class="modal-header">
          <h3 class="modal-title" id="student-groups-title">مجموعات الطالب</h3>
          <button type="button" class="modal-close" id="close-student-groups-modal">✕</button>
        </div>
        <div class="modal-body">
          <div style="margin-bottom:1.25rem; padding-bottom:1rem; border-bottom:1px solid var(--border);">
            <div style="font-size:0.85rem; font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">إلحاق بمجموعة جديدة:</div>
            <div style="display:flex; gap:0.5rem;">
              <select id="enroll-group-select" class="form-input" style="flex:1;">
                <option value="">اختر المجموعة...</option>
              </select>
              <button type="button" id="confirm-enroll-group-btn" class="btn btn-primary btn-sm">إلحاق بالمجموعة</button>
            </div>
          </div>

          <div style="font-size:0.85rem; font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">المجموعات المقيد بها الطالب حالياً:</div>
          <div id="student-groups-list-container" style="max-height:260px; overflow-y:auto;">
            <!-- Rendered dynamically -->
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="close-student-groups-btn">إغلاق</button>
        </div>
      </div>
    </div>

    <!-- Modal: Manage Group Students -->
    <div id="group-students-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content" style="max-width:640px;">
        <div class="modal-header">
          <h3 class="modal-title" id="group-students-title">طلاب المجموعة</h3>
          <button type="button" class="modal-close" id="close-group-students-modal">✕</button>
        </div>
        <div class="modal-body">
          <div style="margin-bottom:1.25rem; padding-bottom:1rem; border-bottom:1px solid var(--border);">
            <div style="font-size:0.85rem; font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">إضافة طالب إلى هذه المجموعة:</div>
            <div style="display:flex; gap:0.5rem;">
              <select id="enroll-student-select" class="form-input" style="flex:1;">
                <option value="">اختر طالباً لإضافته...</option>
              </select>
              <button type="button" id="confirm-enroll-student-btn" class="btn btn-primary btn-sm">إضافة للمجموعة</button>
            </div>
          </div>

          <div style="font-size:0.85rem; font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">قائمة الطلاب المسجلين بالمجموعة:</div>
          <div id="group-students-list-container" style="max-height:300px; overflow-y:auto;">
            <!-- Rendered dynamically -->
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="close-group-students-btn">إغلاق</button>
        </div>
      </div>
    </div>

    <!-- Modal: View & Share Single Student Barcode Card -->
    <div id="student-barcode-card-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content" style="max-width:440px;">
        <div class="modal-header">
          <h3 class="modal-title">بطاقة الطالب الذكية</h3>
          <button type="button" class="modal-close" id="close-barcode-card-modal">✕</button>
        </div>
        <div class="modal-body" id="barcode-card-modal-body" style="padding:1.25rem;">
          <!-- Rendered dynamically -->
        </div>
        <div class="modal-footer" style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:0.5rem;">
          <div style="display:flex; gap:0.5rem;">
            <button type="button" class="btn btn-outline btn-sm" id="download-card-modal-btn">📥 تحميل PDF</button>
            <button type="button" class="btn btn-secondary btn-sm" id="share-card-modal-btn">📤 مشاركة</button>
          </div>
          <button type="button" class="btn btn-primary btn-sm" id="confirm-card-delivery-btn">✔ تأكيد التسليم</button>
        </div>
      </div>
    </div>
  `;
}

function renderStudentsTabContent() {
  return `
    <div class="filter-bar">
      <input type="text" id="student-search-input" class="filter-input" style="flex:1; min-width:240px;" placeholder="بحث باسم الطالب، هاتف الطالب، أو هاتف ولي الأمر..." value="${state.studentFilters.q || ''}">
      
      <select id="student-grade-filter" class="filter-select">
        <option value="">جميع الصفوف الدراسية</option>
        <option value="1_sec" ${state.studentFilters.grade_level === '1_sec' ? 'selected' : ''}>الصف الأول الثانوي</option>
        <option value="2_sec" ${state.studentFilters.grade_level === '2_sec' ? 'selected' : ''}>الصف الثاني الثانوي</option>
        <option value="3_sec" ${state.studentFilters.grade_level === '3_sec' ? 'selected' : ''}>الصف الثالث الثانوي</option>
      </select>

      <select id="student-status-filter" class="filter-select">
        <option value="">جميع الحالات</option>
        <option value="true" ${state.studentFilters.is_active === 'true' ? 'selected' : ''}>نشط فقط</option>
        <option value="false" ${state.studentFilters.is_active === 'false' ? 'selected' : ''}>معطل فقط</option>
      </select>

      <button type="button" id="search-student-btn" class="btn btn-primary btn-sm">بحث</button>
      <button type="button" id="reset-student-filters-btn" class="btn btn-secondary btn-sm">إلغاء الفلتر</button>
    </div>

    ${state.students.length === 0 ? `
      <div class="empty-state-card">
        <div class="empty-state-icon">${icons.users}</div>
        <h3 class="empty-state-title">لا يوجد طلاب يطابقون شروط العرض</h3>
        <p class="empty-state-desc">أضف طلابك الجدد وحدد صفوفهم وأرقام أولياء الأمور للبدء في توزيعهم على المجموعات.</p>
        <button type="button" id="open-add-student-empty" class="btn btn-primary empty-state-btn">إضافة طالب الآن</button>
      </div>
    ` : `
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>الطالب</th>
              <th>الصف الدراسي</th>
              <th>هاتف الطالب</th>
              <th>ولي الأمر</th>
              <th>المجموعات المقيد بها</th>
              <th>الحالة</th>
              <th style="text-align:center;">إجراءات</th>
            </tr>
          </thead>
          <tbody>
            ${state.students.map(s => `
              <tr>
                <td>
                  <div style="font-weight:700; color:var(--slate-900);">${s.full_name}</div>
                  <div style="font-size:0.75rem; color:var(--slate-400);">${s.address || 'بدون عنوان مسجل'}</div>
                </td>
                <td>
                  <span class="badge badge-primary">${s.grade_label}</span>
                </td>
                <td class="tabular-nums" style="font-weight:600; color:var(--slate-800);">${s.phone}</td>
                <td>
                  <div style="font-size:0.85rem; font-weight:600;">${s.parent_name || '—'}</div>
                  <div class="tabular-nums" style="font-size:0.75rem; color:var(--slate-500);">${s.parent_phone || 'بدون هاتف'}</div>
                </td>
                <td>
                  <button type="button" class="pill-count manage-student-groups-btn" data-id="${s.id}" data-name="${s.full_name}" data-grade="${s.grade_level}" title="إدارة وتعديل مجموعات الطالب">
                    ${s.group_count} مجموعات ⚙️
                  </button>
                </td>
                <td>
                  <span class="badge ${s.is_active ? 'badge-success' : 'badge-danger'}">
                    ${s.is_active ? 'نشط' : 'معطل'}
                  </span>
                </td>
                <td style="text-align:center;">
                  <div style="display:flex; justify-content:center; gap:0.4rem;">
                    <button class="btn btn-secondary btn-sm view-student-barcode-card-btn" data-id="${s.id}" data-name="${escapeHtml(s.full_name)}" title="عرض ومشاركة بطاقة الباركود">
                      💳
                    </button>
                    <button class="btn btn-secondary btn-sm edit-student-btn" data-id="${s.id}" title="تعديل بيانات الطالب">
                      ${icons.edit}
                    </button>
                    <button class="btn btn-secondary btn-sm delete-student-btn" data-id="${s.id}" data-name="${s.full_name}" title="حذف الطالب">
                      ${icons.trash}
                    </button>
                  </div>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `}
  `;
}

function renderGroupsTabContent() {
  return `
    <div class="filter-bar">
      <select id="group-grade-filter" class="filter-select">
        <option value="">جميع الصفوف الدراسية</option>
        <option value="1_sec" ${state.groupFilters.grade_level === '1_sec' ? 'selected' : ''}>الصف الأول الثانوي</option>
        <option value="2_sec" ${state.groupFilters.grade_level === '2_sec' ? 'selected' : ''}>الصف الثاني الثانوي</option>
        <option value="3_sec" ${state.groupFilters.grade_level === '3_sec' ? 'selected' : ''}>الصف الثالث الثانوي</option>
      </select>

      <select id="group-status-filter" class="filter-select">
        <option value="">جميع الحالات</option>
        <option value="true" ${state.groupFilters.is_active === 'true' ? 'selected' : ''}>نشط فقط</option>
        <option value="false" ${state.groupFilters.is_active === 'false' ? 'selected' : ''}>معطل فقط</option>
      </select>

      <button type="button" id="reset-group-filters-btn" class="btn btn-secondary btn-sm">إلغاء الفلتر</button>
    </div>

    ${state.groups.length === 0 ? `
      <div class="empty-state-card">
        <div class="empty-state-icon">${icons.dashboard}</div>
        <h3 class="empty-state-title">لا توجد مجموعات دراسية حالياً</h3>
        <p class="empty-state-desc">أنشئ مجموعاتك حسب الصف والمواعيد للبدء في تنظيم الحصص وقيد الطلاب.</p>
        <button type="button" id="open-add-group-empty" class="btn btn-primary empty-state-btn">إضافة أول مجموعة</button>
      </div>
    ` : `
      <div class="group-cards-grid">
        ${state.groups.map(g => `
          <div class="group-card">
            <div>
              <div class="group-card-header">
                <div>
                  <div class="group-card-title">${g.name}</div>
                  <div class="group-card-meta">${g.subject || 'المنهج الدراسي العام'}</div>
                </div>
                <span class="badge ${g.is_active ? 'badge-success' : 'badge-danger'}">
                  ${g.is_active ? 'نشطة' : 'معطلة'}
                </span>
              </div>
              <div style="margin-bottom:0.75rem;">
                <span class="badge badge-primary">${g.grade_label}</span>
              </div>
              <div class="group-card-body">
                <div>📍 <strong>المواعيد:</strong> ${g.schedule_details || 'لم تُحدد مواعيد'}</div>
              </div>
            </div>

            <div class="group-card-footer" style="flex-wrap:wrap; gap:0.5rem;">
              <button type="button" class="pill-count manage-group-students-btn" data-id="${g.id}" data-name="${g.name}" data-grade="${g.grade_level}" title="عرض وإدارة طلاب المجموعة">
                👥 ${g.student_count} طالب
              </button>
              <button type="button" class="btn btn-outline btn-sm open-group-distribution-btn" data-id="${g.id}" data-name="${g.name}" title="توزيع بطاقات الباركود وتصدير PDF">
                💳 بطاقات الباركود
              </button>
              <div style="display:flex; gap:0.4rem;">
                <button class="btn btn-secondary btn-sm edit-group-btn" data-id="${g.id}" title="تعديل بيانات المجموعة">
                  ${icons.edit}
                </button>
                <button class="btn btn-secondary btn-sm delete-group-btn" data-id="${g.id}" data-name="${g.name}" title="حذف المجموعة">
                  ${icons.trash}
                </button>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `}
  `;
}

function renderDistributionTabContent() {
  const selectedGroupId = state.selectedDistributionGroupId || (state.groups.length > 0 ? state.groups[0].id : '');
  const overview = state.distributionOverview;

  let studentsList = overview ? overview.students || [] : [];
  if (state.distributionStudentFilter === 'pending') {
    studentsList = studentsList.filter(s => s.distribution_status !== 'confirmed_sent');
  } else if (state.distributionStudentFilter === 'new') {
    studentsList = studentsList.filter(s => s.is_new_since_last_export);
  } else if (state.distributionStudentFilter === 'confirmed') {
    studentsList = studentsList.filter(s => s.distribution_status === 'confirmed_sent');
  }

  const newCount = overview ? overview.new_since_export_count : 0;
  const totalCount = overview ? overview.total_students : 0;
  const confirmedCount = overview ? overview.confirmed_sent_count : 0;
  const pendingCount = overview ? overview.pending_count : 0;
  const lastExportText = overview && overview.last_exported_at
    ? `آخر تصدير: ${new Date(overview.last_exported_at).toLocaleString('ar-EG')} (بواسطة: ${escapeHtml(overview.last_exported_by_name || 'المعلم')})`
    : 'لم يتم تصدير بطاقات هذه المجموعة من قبل';

  return `
    <div class="card" style="margin-bottom:1.25rem; padding:1.25rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem;">
        <div style="display:flex; align-items:center; gap:0.75rem; flex-wrap:wrap;">
          <label class="form-label" style="margin:0; font-weight:700;">اختر المجموعة الدراسية:</label>
          <select id="dist-group-select" class="form-input" style="min-width:240px; margin:0;">
            ${state.groups.map(g => `
              <option value="${g.id}" ${g.id === selectedGroupId ? 'selected' : ''}>
                ${escapeHtml(g.name)} (${GRADE_LABELS[g.grade_level] || g.grade_level})
              </option>
            `).join('')}
          </select>
        </div>
        <div style="font-size:0.8rem; color:var(--slate-500);">${lastExportText}</div>
      </div>
    </div>

    <!-- Overview Stat Cards -->
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:1rem; margin-bottom:1.25rem;">
      <div class="card" style="padding:1rem; text-align:center;">
        <div style="font-size:0.8rem; color:var(--slate-500);">إجمالي طلاب المجموعة</div>
        <div class="tabular-nums" style="font-size:1.75rem; font-weight:700; color:var(--slate-800);">${totalCount}</div>
      </div>
      <div class="card" style="padding:1rem; text-align:center; border-top:3px solid #059669;">
        <div style="font-size:0.8rem; color:var(--slate-500);">تم تأكيد التسليم</div>
        <div class="tabular-nums" style="font-size:1.75rem; font-weight:700; color:#059669;">${confirmedCount}</div>
      </div>
      <div class="card" style="padding:1rem; text-align:center; border-top:3px solid #d97706;">
        <div style="font-size:0.8rem; color:var(--slate-500);">بانتظار التسليم</div>
        <div class="tabular-nums" style="font-size:1.75rem; font-weight:700; color:#d97706;">${pendingCount}</div>
      </div>
      <div class="card" style="padding:1rem; text-align:center; ${newCount > 0 ? 'background:#fffbeb; border:1px solid #fde68a; border-top:3px solid #b45309;' : ''}">
        <div style="font-size:0.8rem; color:${newCount > 0 ? '#92400e' : 'var(--slate-500)'};">جدد بعد آخر تصدير</div>
        <div class="tabular-nums" style="font-size:1.75rem; font-weight:700; color:${newCount > 0 ? '#b45309' : 'var(--slate-800)'};">
          ${newCount} ${newCount > 0 ? '✨' : ''}
        </div>
      </div>
    </div>

    ${newCount > 0 ? `
      <div class="card" style="margin-bottom:1.25rem; background:#fffbeb; border:1px solid #fde68a; padding:1rem;">
        <div style="display:flex; align-items:center; gap:0.75rem;">
          <span style="font-size:1.5rem;">🔔</span>
          <div style="font-size:0.85rem; color:#92400e; line-height:1.5;">
            <strong>يوجد ${newCount} طلاب انضموا للمجموعة بعد تاريخ آخر تصدير.</strong><br>
            يمكنك فلترة الطلاب الجدد لتصدير بطاقاتهم فقط، أو الضغط على "تصدير بطاقات المجموعة (PDF)" لتحديث وتصدير المجموعة كاملة.
          </div>
        </div>
      </div>
    ` : ''}

    <!-- Action Toolbar & Filters -->
    <div class="card" style="padding:1rem; margin-bottom:1.25rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.75rem;">
      <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
        <button type="button" class="btn btn-primary btn-sm" id="export-group-cards-pdf-btn" ${totalCount === 0 ? 'disabled' : ''}>
          📥 تصدير بطاقات المجموعة كاملة (A4 PDF)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" id="export-selected-cards-pdf-btn" ${state.selectedDistributionStudentIds.length === 0 ? 'disabled' : ''}>
          📥 تصدير المحددة (${state.selectedDistributionStudentIds.length})
        </button>
      </div>

      <div class="tab-nav" style="margin:0; border:none;">
        <button type="button" class="tab-btn dist-filter-btn ${state.distributionStudentFilter === 'all' ? 'active' : ''}" data-filter="all">الكل (${totalCount})</button>
        <button type="button" class="tab-btn dist-filter-btn ${state.distributionStudentFilter === 'pending' ? 'active' : ''}" data-filter="pending">بانتظار التسليم (${pendingCount})</button>
        <button type="button" class="tab-btn dist-filter-btn ${state.distributionStudentFilter === 'new' ? 'active' : ''}" data-filter="new">جدد بعد التصدير (${newCount})</button>
        <button type="button" class="tab-btn dist-filter-btn ${state.distributionStudentFilter === 'confirmed' ? 'active' : ''}" data-filter="confirmed">تم التسليم (${confirmedCount})</button>
      </div>
    </div>

    <!-- Distribution Students Table -->
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th style="width:40px; text-align:center;">
              <input type="checkbox" id="dist-master-checkbox" ${studentsList.length > 0 && state.selectedDistributionStudentIds.length === studentsList.length ? 'checked' : ''}>
            </th>
            <th>اسم الطالب</th>
            <th>الصف الدراسي</th>
            <th>رقم الهاتف</th>
            <th>تاريخ الانضمام</th>
            <th>حالة التوزيع</th>
            <th style="text-align:center;">إجراءات</th>
          </tr>
        </thead>
        <tbody>
          ${studentsList.length === 0 ? `
            <tr>
              <td colspan="7" style="text-align:center; padding:2rem; color:var(--slate-400);">
                لا يوجد طلاب يطابقون شروط العرض في هذه المجموعة.
              </td>
            </tr>
          ` : studentsList.map(s => {
            const isSelected = state.selectedDistributionStudentIds.includes(s.student_id);
            const joinedDisplay = s.joined_at ? new Date(s.joined_at).toLocaleDateString('ar-EG') : '—';
            let statusBadge = '<span class="badge badge-secondary">بانتظار التسليم</span>';
            if (s.distribution_status === 'confirmed_sent') {
              statusBadge = `<span class="badge badge-success" title="تم التأكيد بواسطة: ${escapeHtml(s.confirmed_by_name || 'المعلم')}">✔ تم التسليم</span>`;
            } else if (s.distribution_status === 'share_opened') {
              statusBadge = '<span class="badge badge-primary" title="تم فتح نافذة المشاركة أو تحميل البطاقة">📤 فُتحت المشاركة</span>';
            } else if (s.distribution_status === 'generated') {
              statusBadge = '<span class="badge badge-secondary" title="تم تجهيز ملف PDF">📄 تم التصدير</span>';
            }

            return `
              <tr style="${s.is_new_since_last_export ? 'background:#fffdf5;' : ''}">
                <td style="text-align:center;">
                  <input type="checkbox" class="dist-student-checkbox" data-id="${s.student_id}" ${isSelected ? 'checked' : ''}>
                </td>
                <td>
                  <div style="font-weight:700; color:var(--slate-900); display:flex; align-items:center; gap:0.4rem;">
                    <span>${escapeHtml(s.full_name)}</span>
                    ${s.is_new_since_last_export ? '<span class="badge badge-warning" style="font-size:0.7rem; padding:0.1rem 0.4rem;">✨ جديد</span>' : ''}
                  </div>
                  <div style="font-size:0.75rem; color:var(--slate-400); font-family:monospace; direction:ltr; text-align:right;">
                    ID: ${escapeHtml(s.barcode_value.slice(0, 13))}...
                  </div>
                </td>
                <td><span class="badge badge-primary">${escapeHtml(s.grade_label)}</span></td>
                <td class="tabular-nums" style="font-weight:600;">${escapeHtml(s.phone)}</td>
                <td style="font-size:0.85rem; color:var(--slate-600);">${joinedDisplay}</td>
                <td>${statusBadge}</td>
                <td style="text-align:center;">
                  <div style="display:flex; justify-content:center; gap:0.3rem;">
                    <button type="button" class="btn btn-secondary btn-sm view-single-dist-card-btn" data-id="${s.student_id}" data-name="${escapeHtml(s.full_name)}" data-group-id="${selectedGroupId}" title="معاينة البطاقة">
                      👁 عرض
                    </button>
                    <button type="button" class="btn btn-outline btn-sm share-single-dist-card-btn" data-id="${s.student_id}" data-name="${escapeHtml(s.full_name)}" data-group-id="${selectedGroupId}" title="مشاركة أو تحميل البطاقة">
                      📤 مشاركة
                    </button>
                    <button type="button" class="btn btn-sm ${s.distribution_status === 'confirmed_sent' ? 'btn-secondary' : 'btn-primary'} confirm-single-dist-delivery-btn" data-id="${s.student_id}" data-name="${escapeHtml(s.full_name)}" data-group-id="${selectedGroupId}" data-current="${s.distribution_status}" title="${s.distribution_status === 'confirmed_sent' ? 'إعادة التعيين لبانتظار التسليم' : 'تأكيد التسليم يدويًا'}">
                      ${s.distribution_status === 'confirmed_sent' ? 'إلغاء التأكيد' : '✔ تأكيد'}
                    </button>
                  </div>
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// --- View 4.7: Sessions & Attendance Management ---
function renderAttendanceView() {
  if (state.activeSessionId && state.activeSessionSheet) {
    return renderSessionSheetView(state.activeSessionSheet);
  }
  return renderSessionsListView();
}

function renderSessionsListView() {
  const today = new Date().toISOString().split('T')[0];

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">إدارة الحصص ورصد الحضور</h1>
        <p class="page-subtitle">جدولة مواعيد الحصص، رصد الحضور السريع بماسح الباركود، ومتابعة انضباط المجموعات.</p>
      </div>
      <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
        <button type="button" id="open-add-session-modal" class="btn btn-primary">
          ${icons.plus}
          <span>جدولة حصة جديدة</span>
        </button>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="card" style="padding:1rem; margin-bottom:1.25rem;">
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)) auto; gap:0.75rem; align-items:end;">
        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">تصفية بالمجموعة</label>
          <select id="filter-session-group" class="form-input">
            <option value="">جميع المجموعات</option>
            ${state.groups.map(g => `
              <option value="${g.id}" ${state.sessionFilters.group_id === g.id ? 'selected' : ''}>${g.name} (${g.grade_label})</option>
            `).join('')}
          </select>
        </div>

        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">تاريخ الحصة</label>
          <input type="date" id="filter-session-date" class="form-input" value="${state.sessionFilters.session_date || ''}">
        </div>

        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">الحالة</label>
          <select id="filter-session-status" class="form-input">
            <option value="">جميع الحالات</option>
            <option value="scheduled" ${state.sessionFilters.status === 'scheduled' ? 'selected' : ''}>مجدولة</option>
            <option value="completed" ${state.sessionFilters.status === 'completed' ? 'selected' : ''}>مكتملة</option>
            <option value="cancelled" ${state.sessionFilters.status === 'cancelled' ? 'selected' : ''}>ملغاة</option>
          </select>
        </div>

        <div style="display:flex; gap:0.4rem;">
          <button type="button" id="filter-sessions-btn" class="btn btn-primary btn-sm" style="height:38px;">
            ${icons.search}
            <span>تصفية</span>
          </button>
          <button type="button" id="reset-sessions-btn" class="btn btn-secondary btn-sm" style="height:38px;" title="إلغاء التصفية">
            ✕
          </button>
        </div>
      </div>
    </div>

    <!-- Sessions List -->
    <div class="table-container">
      <div class="table-header-bar">
        <div style="font-weight:700; color:var(--slate-800);">قائمة الحصص الدراسية (${state.sessions.length})</div>
        <div style="font-size:0.8rem; color:var(--slate-500);">رصد الحضور الفوري متاح للحصص المجدولة والمكتملة</div>
      </div>

      ${state.sessions.length === 0 ? `
        <div class="empty-state-card">
          <div class="empty-state-icon">${icons.calendar}</div>
          <h3 class="empty-state-title">لا توجد حصص مسجلة</h3>
          <p class="empty-state-desc">ابدأ بجدولة أول حصة لأي مجموعة للبدء في رصد الحضور وطباعة وتوزيع دفاتر الحصص.</p>
          <button type="button" id="open-add-session-empty" class="btn btn-primary empty-state-btn">جدولة أول حصة</button>
        </div>
      ` : `
        <table class="data-table">
          <thead>
            <tr>
              <th>المجموعة والصف</th>
              <th>موعد الحصة</th>
              <th>المكان</th>
              <th>الحالة</th>
              <th>إحصائيات الحضور</th>
              <th style="text-align:center;">إجراءات</th>
            </tr>
          </thead>
          <tbody>
            ${state.sessions.map(s => {
              const stats = s.stats || { total_enrolled: 0, present_count: 0, late_count: 0, absent_count: 0, excused_count: 0, unrecorded_count: 0 };
              const attended = stats.present_count + stats.late_count;
              const rate = stats.total_enrolled > 0 ? Math.round((attended / stats.total_enrolled) * 100) : 0;
              const statusBadgeClass = s.status === 'completed' ? 'badge-success' : (s.status === 'cancelled' ? 'badge-danger' : 'badge-primary');

              return `
                <tr>
                  <td>
                    <div style="font-weight:700; color:var(--slate-900);">${s.group_name}</div>
                    <div style="font-size:0.75rem; color:var(--slate-500);">${s.grade_label}</div>
                  </td>
                  <td>
                    <div style="font-weight:700; color:var(--slate-800);">${s.session_date}</div>
                    <div style="font-size:0.75rem; color:var(--slate-500); font-family:monospace;">
                      ${s.start_time} ${s.end_time ? ' - ' + s.end_time : ''}
                    </div>
                  </td>
                  <td>
                    <div style="font-size:0.85rem; color:var(--slate-700);">${s.location || 'غير محدد'}</div>
                  </td>
                  <td>
                    <span class="badge ${statusBadgeClass}">${s.status_label}</span>
                  </td>
                  <td style="min-width:180px;">
                    <div style="display:flex; justify-content:space-between; font-size:0.75rem; font-weight:700; margin-bottom:0.25rem;">
                      <span style="color:#059669;">حضور: ${attended} / ${stats.total_enrolled}</span>
                      <span class="tabular-nums" style="color:var(--slate-600);">${rate}%</span>
                    </div>
                    <div class="att-progress-bar">
                      <div class="att-progress-segment att-seg-present" style="width:${stats.total_enrolled ? (stats.present_count / stats.total_enrolled * 100) : 0}%;"></div>
                      <div class="att-progress-segment att-seg-late" style="width:${stats.total_enrolled ? (stats.late_count / stats.total_enrolled * 100) : 0}%;"></div>
                      <div class="att-progress-segment att-seg-absent" style="width:${stats.total_enrolled ? (stats.absent_count / stats.total_enrolled * 100) : 0}%;"></div>
                      <div class="att-progress-segment att-seg-excused" style="width:${stats.total_enrolled ? (stats.excused_count / stats.total_enrolled * 100) : 0}%;"></div>
                    </div>
                  </td>
                  <td style="text-align:center;">
                    <div style="display:flex; justify-content:center; gap:0.4rem; flex-wrap:wrap;">
                      <button type="button" class="btn btn-primary btn-sm open-session-sheet-btn" data-id="${s.id}" title="فتح دفتر رصد الحضور وماسح الباركود">
                        ${icons.barcode}
                        <span>رصد الحضور</span>
                      </button>
                      <button type="button" class="btn btn-secondary btn-sm view-group-summary-btn" data-group-id="${s.group_id}" title="عرض تقرير المجموعة">
                        📊
                      </button>
                      <button type="button" class="btn btn-secondary btn-sm edit-session-btn" data-id="${s.id}" title="تعديل الحصة">
                        ${icons.edit}
                      </button>
                      ${s.status !== 'cancelled' ? `
                        <button type="button" class="btn btn-secondary btn-sm cancel-session-btn" data-id="${s.id}" data-date="${s.session_date}" title="إلغاء الحصة">
                          ${icons.trash}
                        </button>
                      ` : ''}
                    </div>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      `}
    </div>

    <!-- Modal: Add / Edit Session -->
    <div id="session-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title" id="session-modal-title">جدولة حصة جديدة</h3>
          <button type="button" class="modal-close" id="close-session-modal">✕</button>
        </div>
        <form id="session-form">
          <div class="modal-body">
            <div class="form-group" id="sess-group-container">
              <label class="form-label required">المجموعة الدراسية</label>
              <select id="sess-group-id" class="form-input" required>
                <option value="">اختر المجموعة...</option>
                ${state.groups.map(g => `
                  <option value="${g.id}">${g.name} — ${g.grade_label}</option>
                `).join('')}
              </select>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.75rem;">
              <div class="form-group">
                <label class="form-label required">تاريخ الحصة</label>
                <input type="date" id="sess-date" class="form-input" required value="${today}">
              </div>

              <div class="form-group">
                <label class="form-label required">وقت البدء</label>
                <input type="time" id="sess-start-time" class="form-input tabular-nums" required value="16:00">
              </div>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.75rem;">
              <div class="form-group">
                <label class="form-label">وقت الانتهاء (اختياري)</label>
                <input type="time" id="sess-end-time" class="form-input tabular-nums">
              </div>

              <div class="form-group">
                <label class="form-label">مكان الحصة أو القاعة</label>
                <input type="text" id="sess-location" class="form-input" placeholder="مثال: قاعة 1، سنتر الأوائل">
              </div>
            </div>

            <div class="form-group" id="sess-status-container" style="display:none;">
              <label class="form-label">حالة الحصة</label>
              <select id="sess-status" class="form-input">
                <option value="scheduled">مجدولة</option>
                <option value="completed">مكتملة</option>
                <option value="cancelled">ملغاة</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">ملاحظات الحصة</label>
              <textarea id="sess-notes" class="form-input" rows="2" placeholder="مثال: تسميع شامل، مراجعة الباب الثاني..."></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="cancel-session-btn">إلغاء</button>
            <button type="submit" class="btn btn-primary" id="save-session-btn">حفظ الحصة</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Modal: Group Summary Report -->
    <div id="group-summary-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content" style="max-width:700px;">
        <div class="modal-header">
          <h3 class="modal-title" id="group-summary-modal-title">تقرير حضور المجموعة</h3>
          <button type="button" class="modal-close" id="close-group-summary-modal">✕</button>
        </div>
        <div class="modal-body" id="group-summary-modal-body">
          <!-- Dynamic Content -->
        </div>
      </div>
    </div>
  `;
}

function renderSessionSheetView(sheet) {
  const sess = sheet.session;
  const stats = sheet.stats;
  const attended = stats.present_count + stats.late_count;
  const rate = stats.total_enrolled > 0 ? Math.round((attended / stats.total_enrolled) * 100) : 0;

  return `
    <div style="margin-bottom:1rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
      <button type="button" id="back-to-sessions-list" class="btn btn-secondary">
        ← العودة لقائمة الحصص
      </button>
      <div style="display:flex; gap:0.5rem;">
        <button type="button" class="btn btn-secondary view-group-summary-btn" data-group-id="${sess.group_id}">
          📊 تقرير المجموعة
        </button>
      </div>
    </div>

    <!-- Session Info Card -->
    <div class="session-header-card">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:0.75rem;">
        <div>
          <h1 style="font-size:1.35rem; font-weight:800; color:var(--slate-900); margin-bottom:0.25rem;">
            ${sess.group_name}
          </h1>
          <div style="font-size:0.85rem; color:var(--slate-500); display:flex; gap:0.75rem; flex-wrap:wrap;">
            <span>${sess.grade_label}</span>
            <span>•</span>
            <span>📅 ${sess.session_date}</span>
            <span>•</span>
            <span>⏰ ${sess.start_time} ${sess.end_time ? ' - ' + sess.end_time : ''}</span>
            <span>•</span>
            <span>📍 ${sess.location || 'غير محدد'}</span>
          </div>
        </div>
        <div>
          <span class="badge ${sess.status === 'completed' ? 'badge-success' : (sess.status === 'cancelled' ? 'badge-danger' : 'badge-primary')}">
            ${sess.status_label}
          </span>
        </div>
      </div>

      <!-- Live Counters Grid -->
      <div class="session-info-grid">
        <div class="session-stat-box">
          <span class="session-stat-label">إجمالي المقيدين</span>
          <span class="session-stat-val" style="color:var(--slate-800);">${stats.total_enrolled}</span>
        </div>
        <div class="session-stat-box">
          <span class="session-stat-label">حاضر</span>
          <span class="session-stat-val" style="color:#059669;" id="counter-present">${stats.present_count}</span>
        </div>
        <div class="session-stat-box">
          <span class="session-stat-label">متأخر</span>
          <span class="session-stat-val" style="color:#D97706;" id="counter-late">${stats.late_count}</span>
        </div>
        <div class="session-stat-box">
          <span class="session-stat-label">غياب</span>
          <span class="session-stat-val" style="color:#DC2626;" id="counter-absent">${stats.absent_count}</span>
        </div>
        <div class="session-stat-box">
          <span class="session-stat-label">بعذر</span>
          <span class="session-stat-val" style="color:#2563EB;" id="counter-excused">${stats.excused_count}</span>
        </div>
        <div class="session-stat-box">
          <span class="session-stat-label">لم يُرصد بعد</span>
          <span class="session-stat-val" style="color:var(--slate-500);" id="counter-unrecorded">${stats.unrecorded_count}</span>
        </div>
      </div>

      <!-- Attendance Progress -->
      <div>
        <div style="display:flex; justify-content:space-between; font-size:0.8rem; font-weight:700; margin-bottom:0.35rem;">
          <span>نسبة الحضور الفعلية: ${rate}%</span>
          <span class="tabular-nums">${attended} من ${stats.total_enrolled} طالب</span>
        </div>
        <div class="att-progress-bar" style="height:10px;">
          <div id="prog-present" class="att-progress-segment att-seg-present" style="width:${stats.total_enrolled ? (stats.present_count / stats.total_enrolled * 100) : 0}%;"></div>
          <div id="prog-late" class="att-progress-segment att-seg-late" style="width:${stats.total_enrolled ? (stats.late_count / stats.total_enrolled * 100) : 0}%;"></div>
          <div id="prog-absent" class="att-progress-segment att-seg-absent" style="width:${stats.total_enrolled ? (stats.absent_count / stats.total_enrolled * 100) : 0}%;"></div>
          <div id="prog-excused" class="att-progress-segment att-seg-excused" style="width:${stats.total_enrolled ? (stats.excused_count / stats.total_enrolled * 100) : 0}%;"></div>
        </div>
      </div>
    </div>

    <!-- USB Barcode Scanner Component -->
    <div class="scanner-container">
      <div class="scanner-header">
        <div class="scanner-title">
          ${icons.barcode}
          <span>ماسح الباركود السريع (USB Scanner Ready)</span>
        </div>
        <label style="display:flex; align-items:center; gap:0.4rem; font-size:0.8rem; cursor:pointer;">
          <input type="checkbox" id="toggle-audio-feedback" ${state.audioFeedbackEnabled ? 'checked' : ''}>
          <span>${icons.volume} تنبيه صوتي فوري</span>
        </label>
      </div>

      <div class="scanner-input-wrapper">
        <input type="text" id="barcode-input" class="scanner-input" placeholder="امسح باركود الطالب بجهاز الـ USB أو اكتب المعرف واضغط Enter..." autofocus autocomplete="off">
        <button type="button" id="submit-barcode-btn" class="btn" style="background:#059669; color:#fff; font-weight:700;">
          ${icons.check}
          <span>تسجيل حضور</span>
        </button>
      </div>

      <div id="scanner-feedback" class="scanner-feedback"></div>
    </div>

    <!-- Actions & Sheet Table -->
    <div class="table-container">
      <div class="table-header-bar" style="flex-wrap:wrap; gap:0.75rem;">
        <div style="display:flex; align-items:center; gap:0.5rem; flex:1; min-width:240px;">
          <input type="text" id="sheet-student-search" class="form-input" placeholder="بحث باسم الطالب أو الهاتف في الحصة..." style="max-width:300px; padding:0.4rem 0.75rem; font-size:0.85rem;">
        </div>
        <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
          <button type="button" id="bulk-mark-remaining-absent" class="btn btn-secondary btn-sm" style="color:#DC2626; border-color:#FECACA;" title="تسجيل غياب لكافة الطلاب الذين لم يمسحوا باركود الحضور">
            تعليم المتبقين غياب (${stats.unrecorded_count})
          </button>
          <button type="button" id="bulk-mark-all-present" class="btn btn-secondary btn-sm" style="color:#059669; border-color:#A7F3D0;" title="تسجيل جميع طلاب المجموعة حاضر دفعة واحدة">
            تعليم الكل حضور
          </button>
        </div>
      </div>

      ${sheet.students.length === 0 ? `
        <div class="empty-state-card">
          <div class="empty-state-icon">${icons.users}</div>
          <h3 class="empty-state-title">لا يوجد طلاب مقيدون في هذه المجموعة</h3>
          <p class="empty-state-desc">توجه إلى صفحة المجموعات وأضف الطلاب إلى هذه المجموعة للبدء في رصد حضورهم.</p>
          <a href="#/students" class="btn btn-primary empty-state-btn">الذهاب لسجل الطلاب والمجموعات</a>
        </div>
      ` : `
        <table class="data-table" id="attendance-sheet-table">
          <thead>
            <tr>
              <th style="width:50px;">#</th>
              <th>الطالب</th>
              <th>هاتف الطالب</th>
              <th>هاتف ولي الأمر</th>
              <th style="min-width:260px;">حالة الحضور</th>
              <th>ملاحظات الحصة</th>
              <th>وقت التسجيل</th>
            </tr>
          </thead>
          <tbody>
            ${sheet.students.map((s, idx) => `
              <tr id="row-student-${s.student_id}" data-name="${s.student_name.toLowerCase()}" data-phone="${s.student_phone || ''}" data-parent-phone="${s.parent_phone || ''}">
                <td class="tabular-nums" style="color:var(--slate-400);">${idx + 1}</td>
                <td>
                  <a href="javascript:void(0)" class="view-student-history-btn" data-student-id="${s.student_id}" style="font-weight:700; color:var(--primary); text-decoration:none;">
                    ${s.student_name}
                  </a>
                </td>
                <td class="tabular-nums">${s.student_phone || '-'}</td>
                <td class="tabular-nums">${s.parent_phone || '-'}</td>
                <td>
                  <div class="status-btn-group" data-student-id="${s.student_id}">
                    <button type="button" class="status-btn mark-status-btn ${s.status === 'present' ? 'active-present' : ''}" data-status="present">حاضر</button>
                    <button type="button" class="status-btn mark-status-btn ${s.status === 'late' ? 'active-late' : ''}" data-status="late">متأخر</button>
                    <button type="button" class="status-btn mark-status-btn ${s.status === 'absent' ? 'active-absent' : ''}" data-status="absent">غائب</button>
                    <button type="button" class="status-btn mark-status-btn ${s.status === 'excused' ? 'active-excused' : ''}" data-status="excused">عذر</button>
                  </div>
                </td>
                <td>
                  <input type="text" class="form-input student-att-note" data-student-id="${s.student_id}" value="${s.notes || ''}" placeholder="ملاحظة..." style="padding:0.25rem 0.5rem; font-size:0.8rem; max-width:160px;">
                </td>
                <td class="tabular-nums student-att-time" style="font-size:0.75rem; color:var(--slate-500); font-family:monospace;">
                  ${s.updated_at ? new Date(s.updated_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }) : '-'}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `}
    </div>

    <!-- Modal: Student Attendance History -->
    <div id="student-history-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content" style="max-width:700px;">
        <div class="modal-header">
          <h3 class="modal-title" id="student-history-modal-title">سجل حضور الطالب</h3>
          <button type="button" class="modal-close" id="close-student-history-modal">✕</button>
        </div>
        <div class="modal-body" id="student-history-modal-body">
          <!-- Dynamic Content -->
        </div>
      </div>
    </div>
  `;
}

// --- View 5: Exams & Grades Views ---
function renderExamsView() {
  if (state.activeExamId && state.activeExamSheet) {
    return renderExamSheetView(state.activeExamSheet);
  }
  return renderExamsListView();
}

function renderExamsListView() {
  const today = new Date().toISOString().split('T')[0];

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">إدارة الامتحانات ورصد الدرجات</h1>
        <p class="page-subtitle">جدولة وتعديل الامتحانات، رصد الدرجات وحساب نسب النجاح، والتقارير الإحصائية للمجموعات والطلاب.</p>
      </div>
      <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
        <button type="button" id="open-add-exam-modal" class="btn btn-primary">
          ${icons.plus}
          <span>إنشاء امتحان جديد</span>
        </button>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="card" style="padding:1rem; margin-bottom:1.25rem;">
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)) auto; gap:0.75rem; align-items:end;">
        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">تصفية بالمجموعة</label>
          <select id="filter-exam-group" class="form-input">
            <option value="">جميع المجموعات</option>
            ${state.groups.map(g => `
              <option value="${g.id}" ${state.examFilters.group_id === g.id ? 'selected' : ''}>${g.name} (${g.grade_label})</option>
            `).join('')}
          </select>
        </div>

        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">تاريخ الامتحان</label>
          <input type="date" id="filter-exam-date" class="form-input" value="${state.examFilters.exam_date || ''}">
        </div>

        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">الحالة</label>
          <select id="filter-exam-status" class="form-input">
            <option value="">جميع الحالات</option>
            <option value="scheduled" ${state.examFilters.status === 'scheduled' ? 'selected' : ''}>مجدول</option>
            <option value="completed" ${state.examFilters.status === 'completed' ? 'selected' : ''}>مكتمل</option>
            <option value="cancelled" ${state.examFilters.status === 'cancelled' ? 'selected' : ''}>ملغى</option>
          </select>
        </div>

        <div style="display:flex; gap:0.4rem;">
          <button type="button" id="filter-exams-btn" class="btn btn-primary btn-sm" style="height:38px;">
            ${icons.search}
            <span>تصفية</span>
          </button>
          <button type="button" id="reset-exams-btn" class="btn btn-secondary btn-sm" style="height:38px;" title="إلغاء التصفية">
            ✕
          </button>
        </div>
      </div>
    </div>

    <!-- Exams List -->
    <div class="table-container">
      <div class="table-header-bar">
        <div style="font-weight:700; color:var(--slate-800);">قائمة الامتحانات والتقييمات (${state.exams.length})</div>
        <div style="font-size:0.8rem; color:var(--slate-500);">رصد الدرجات متاح للامتحانات المجدولة والمكتملة</div>
      </div>

      ${state.exams.length === 0 ? `
        <div class="empty-state-card">
          <div class="empty-state-icon">${icons.exams}</div>
          <h3 class="empty-state-title">لا توجد امتحانات مسجلة</h3>
          <p class="empty-state-desc">أنشئ أول امتحان لأي مجموعة لبدء رصد درجات الطلاب وحساب نسب النجاح والإحصائيات.</p>
          <button type="button" id="open-add-exam-empty" class="btn btn-primary empty-state-btn">إنشاء أول امتحان</button>
        </div>
      ` : `
        <table class="data-table">
          <thead>
            <tr>
              <th>الامتحان والمجموعة</th>
              <th>تاريخ الامتحان</th>
              <th>الدرجة العظمى / النجاح</th>
              <th>الحالة</th>
              <th>مؤشرات الأداء</th>
              <th style="text-align:center;">إجراءات</th>
            </tr>
          </thead>
          <tbody>
            ${state.exams.map(e => {
              const stats = e.stats || {
                total_enrolled: 0,
                results_recorded: 0,
                results_pending: 0,
                attended_count: 0,
                absent_count: 0,
                excused_count: 0,
                pass_count: 0,
                fail_count: 0,
                pass_rate: 0,
                average_score: 0,
                average_percentage: 0
              };
              const statusBadgeClass = e.status === 'completed' ? 'badge-success' : (e.status === 'cancelled' ? 'badge-danger' : 'badge-primary');

              return `
                <tr>
                  <td>
                    <div style="font-weight:700; color:var(--slate-900);">${e.title}</div>
                    <div style="font-size:0.75rem; color:var(--slate-500);">${e.group_name} (${e.grade_label})</div>
                  </td>
                  <td>
                    <div style="font-weight:700; color:var(--slate-800);">${e.exam_date}</div>
                    ${e.description ? `<div style="font-size:0.72rem; color:var(--slate-500); max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${e.description}">${e.description}</div>` : ''}
                  </td>
                  <td>
                    <div style="font-weight:700; color:var(--slate-900);">
                      <span class="tabular-nums">${e.max_score}</span> <span style="font-size:0.75rem; color:var(--slate-500);">درجة</span>
                    </div>
                    <div style="font-size:0.75rem; color:var(--slate-500);">
                      النجاح: <span class="tabular-nums" style="font-weight:600; color:#059669;">${e.passing_score}</span>
                    </div>
                  </td>
                  <td>
                    <span class="badge ${statusBadgeClass}">${e.status_label}</span>
                  </td>
                  <td style="min-width:180px;">
                    <div style="display:flex; justify-content:space-between; font-size:0.75rem; font-weight:700; margin-bottom:0.25rem;">
                      <span style="color:#059669;">نجاح: ${stats.pass_rate}%</span>
                      <span class="tabular-nums" style="color:var(--slate-600); font-size:0.72rem;">متوسط: ${stats.average_score} (${stats.average_percentage}%)</span>
                    </div>
                    <div class="exam-progress-bar">
                      <div class="exam-progress-segment exam-seg-pass" style="width:${stats.total_enrolled ? (stats.pass_count / stats.total_enrolled * 100) : 0}%;" title="ناجح: ${stats.pass_count}"></div>
                      <div class="exam-progress-segment exam-seg-fail" style="width:${stats.total_enrolled ? (stats.fail_count / stats.total_enrolled * 100) : 0}%;" title="راسب: ${stats.fail_count}"></div>
                      <div class="exam-progress-segment exam-seg-absent" style="width:${stats.total_enrolled ? (stats.absent_count / stats.total_enrolled * 100) : 0}%;" title="غائب: ${stats.absent_count}"></div>
                      <div class="exam-progress-segment exam-seg-excused" style="width:${stats.total_enrolled ? (stats.excused_count / stats.total_enrolled * 100) : 0}%;" title="معتذر: ${stats.excused_count}"></div>
                    </div>
                    <div style="font-size:0.7rem; color:var(--slate-400); margin-top:0.2rem; display:flex; justify-content:space-between;">
                      <span>تم الرصد: ${stats.results_recorded} / ${stats.total_enrolled}</span>
                      <span>حضر: ${stats.attended_count}</span>
                    </div>
                  </td>
                  <td style="text-align:center;">
                    <div style="display:flex; justify-content:center; gap:0.4rem; flex-wrap:wrap;">
                      <button type="button" class="btn btn-primary btn-sm open-exam-sheet-btn" data-id="${e.id}" title="فتح كشف رصد الدرجات">
                        ${icons.exams}
                        <span>رصد الدرجات</span>
                      </button>
                      <button type="button" class="btn btn-secondary btn-sm view-group-exams-summary-btn" data-group-id="${e.group_id}" title="عرض تقرير المجموعة الشامل">
                        📊
                      </button>
                      <button type="button" class="btn btn-secondary btn-sm edit-exam-btn" data-id="${e.id}" title="تعديل بيانات الامتحان">
                        ${icons.edit}
                      </button>
                      ${e.status === 'scheduled' ? `
                        <button type="button" class="btn btn-secondary btn-sm complete-exam-btn" data-id="${e.id}" title="تعيين الامتحان كمكتمل">
                          ✓
                        </button>
                      ` : ''}
                      ${e.status !== 'cancelled' ? `
                        <button type="button" class="btn btn-secondary btn-sm cancel-exam-btn" data-id="${e.id}" title="إلغاء الامتحان">
                          ✕
                        </button>
                      ` : ''}
                      <button type="button" class="btn btn-secondary btn-sm delete-exam-btn" data-id="${e.id}" title="حذف الامتحان">
                        ${icons.trash}
                      </button>
                    </div>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      `}
    </div>

    <!-- Modal: Add / Edit Exam -->
    <div id="exam-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title" id="exam-modal-title">إنشاء امتحان جديد</h3>
          <button type="button" class="modal-close" id="close-exam-modal">✕</button>
        </div>
        <form id="exam-form">
          <div class="modal-body">
            <div class="form-group" id="exam-group-container">
              <label class="form-label required">المجموعة الدراسية</label>
              <select id="exam-group-id" class="form-input" required>
                <option value="">اختر المجموعة...</option>
                ${state.groups.map(g => `
                  <option value="${g.id}">${g.name} — ${g.grade_label}</option>
                `).join('')}
              </select>
            </div>

            <div class="form-group">
              <label class="form-label required">عنوان أو موضوع الامتحان</label>
              <input type="text" id="exam-title" class="form-input" required placeholder="مثال: امتحان شامل الباب الأول في الكيمياء">
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:0.75rem;">
              <div class="form-group">
                <label class="form-label required">تاريخ الامتحان</label>
                <input type="date" id="exam-date" class="form-input" required value="${today}">
              </div>

              <div class="form-group">
                <label class="form-label required">الدرجة العظمى</label>
                <input type="number" id="exam-max-score" class="form-input tabular-nums" required step="0.5" min="0.5" value="50">
              </div>

              <div class="form-group">
                <label class="form-label required">درجة النجاح</label>
                <input type="number" id="exam-passing-score" class="form-input tabular-nums" required step="0.5" min="0" value="25">
              </div>
            </div>

            <div class="form-group" id="exam-status-container" style="display:none;">
              <label class="form-label">حالة الامتحان</label>
              <select id="exam-status" class="form-input">
                <option value="scheduled">مجدول</option>
                <option value="completed">مكتمل</option>
                <option value="cancelled">ملغى</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">وصف وملاحظات الامتحان (اختياري)</label>
              <textarea id="exam-description" class="form-input" rows="2" placeholder="مثال: يشمل أسئلة مقالية واختيار من متعدد..."></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="cancel-exam-modal-btn">إلغاء</button>
            <button type="submit" class="btn btn-primary" id="save-exam-btn">حفظ الامتحان</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Modal: Group Exams Summary Report -->
    <div id="group-exams-summary-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content" style="max-width:750px;">
        <div class="modal-header">
          <h3 class="modal-title" id="group-exams-summary-modal-title">تقرير أداء امتحانات المجموعة</h3>
          <button type="button" class="modal-close" id="close-group-exams-summary-modal">✕</button>
        </div>
        <div class="modal-body" id="group-exams-summary-modal-body">
          <!-- Dynamic Content -->
        </div>
      </div>
    </div>

    <!-- Modal: Student Exam History Report -->
    <div id="student-exam-history-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content" style="max-width:750px;">
        <div class="modal-header">
          <h3 class="modal-title" id="student-exam-history-modal-title">سجل درجات وامتحانات الطالب</h3>
          <button type="button" class="modal-close" id="close-student-exam-history-modal">✕</button>
        </div>
        <div class="modal-body" id="student-exam-history-modal-body">
          <!-- Dynamic Content -->
        </div>
      </div>
    </div>
  `;
}

function renderExamSheetView(sheet) {
  const exam = sheet.exam;
  const stats = sheet.stats;
  const isCancelled = exam.status === 'cancelled';
  const statusBadgeClass = exam.status === 'completed' ? 'badge-success' : (exam.status === 'cancelled' ? 'badge-danger' : 'badge-primary');

  return `
    <div style="margin-bottom:1rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
      <button type="button" id="back-to-exams-list" class="btn btn-secondary">
        ← العودة لقائمة الامتحانات
      </button>
      <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
        <button type="button" class="btn btn-secondary view-group-exams-summary-btn" data-group-id="${exam.group_id}">
          📊 تقرير المجموعة
        </button>
        ${exam.status === 'scheduled' ? `
          <button type="button" class="btn btn-secondary complete-exam-btn" data-id="${exam.id}">
            ✓ تعيين كمكتمل
          </button>
        ` : ''}
      </div>
    </div>

    <!-- Exam Info Card -->
    <div class="exam-header-card">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:0.75rem;">
        <div>
          <h1 style="font-size:1.35rem; font-weight:800; color:var(--slate-900); margin-bottom:0.25rem;">
            ${exam.title}
          </h1>
          <div style="font-size:0.85rem; color:var(--slate-500); display:flex; gap:0.75rem; flex-wrap:wrap;">
            <span>👥 ${exam.group_name} (${exam.grade_label})</span>
            <span>•</span>
            <span>📅 ${exam.exam_date}</span>
            <span>•</span>
            <span>🎯 الدرجة العظمى: <b style="color:var(--slate-800);">${exam.max_score}</b></span>
            <span>•</span>
            <span>🏆 درجة النجاح: <b style="color:#059669;">${exam.passing_score}</b></span>
          </div>
          ${exam.description ? `<p style="font-size:0.8rem; color:var(--slate-600); margin-top:0.4rem;">${exam.description}</p>` : ''}
        </div>
        <div>
          <span class="badge ${statusBadgeClass}">
            ${exam.status_label}
          </span>
        </div>
      </div>

      <!-- Live Counters Grid -->
      <div class="exam-info-grid">
        <div class="exam-stat-box">
          <span class="exam-stat-label">إجمالي المقيدين</span>
          <span class="exam-stat-val" style="color:var(--slate-800);">${stats.total_enrolled}</span>
        </div>
        <div class="exam-stat-box">
          <span class="exam-stat-label">تم الرصد</span>
          <span class="exam-stat-val" style="color:var(--primary);" id="exam-counter-recorded">${stats.results_recorded}</span>
        </div>
        <div class="exam-stat-box">
          <span class="exam-stat-label">قيد الانتظار</span>
          <span class="exam-stat-val" style="color:var(--slate-500);" id="exam-counter-pending">${stats.results_pending}</span>
        </div>
        <div class="exam-stat-box">
          <span class="exam-stat-label">حضر الامتحان</span>
          <span class="exam-stat-val" style="color:#059669;" id="exam-counter-attended">${stats.attended_count}</span>
        </div>
        <div class="exam-stat-box">
          <span class="exam-stat-label">غائب</span>
          <span class="exam-stat-val" style="color:#DC2626;" id="exam-counter-absent">${stats.absent_count}</span>
        </div>
        <div class="exam-stat-box">
          <span class="exam-stat-label">معتذر</span>
          <span class="exam-stat-val" style="color:#2563EB;" id="exam-counter-excused">${stats.excused_count}</span>
        </div>
        <div class="exam-stat-box">
          <span class="exam-stat-label">نسبة النجاح</span>
          <span class="exam-stat-val" style="color:#059669;" id="exam-counter-pass-rate">${stats.pass_rate}%</span>
        </div>
        <div class="exam-stat-box">
          <span class="exam-stat-label">متوسط الدرجات</span>
          <span class="exam-stat-val" style="color:var(--slate-800);" id="exam-counter-avg-score">${stats.average_score}</span>
        </div>
      </div>

      <!-- Performance Progress Bar -->
      <div>
        <div style="display:flex; justify-content:space-between; font-size:0.8rem; font-weight:700; margin-bottom:0.35rem;">
          <span id="exam-prog-label">الطلاب الناجحون: ${stats.pass_count} من ${stats.attended_count} حضروا (${stats.pass_rate}%)</span>
          <span class="tabular-nums">أعلى درجة: ${stats.highest_score !== null ? stats.highest_score : '-'} | أدنى: ${stats.lowest_score !== null ? stats.lowest_score : '-'}</span>
        </div>
        <div class="exam-progress-bar" style="height:10px;">
          <div id="prog-pass" class="exam-progress-segment exam-seg-pass" style="width:${stats.total_enrolled ? (stats.pass_count / stats.total_enrolled * 100) : 0}%;" title="ناجح"></div>
          <div id="prog-fail" class="exam-progress-segment exam-seg-fail" style="width:${stats.total_enrolled ? (stats.fail_count / stats.total_enrolled * 100) : 0}%;" title="راسب"></div>
          <div id="prog-absent" class="exam-progress-segment exam-seg-absent" style="width:${stats.total_enrolled ? (stats.absent_count / stats.total_enrolled * 100) : 0}%;" title="غائب"></div>
          <div id="prog-excused" class="exam-progress-segment exam-seg-excused" style="width:${stats.total_enrolled ? (stats.excused_count / stats.total_enrolled * 100) : 0}%;" title="معتذر"></div>
        </div>
      </div>
    </div>

    <!-- Sheet Action Toolbar -->
    <div class="sheet-toolbar">
      <div style="display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap; flex:1;">
        <input type="text" id="sheet-student-search" class="form-input" style="max-width:240px; height:36px; font-size:0.85rem;" placeholder="بحث باسم الطالب أو الهاتف...">
        <select id="sheet-filter-status" class="form-input" style="max-width:160px; height:36px; font-size:0.85rem;">
          <option value="">جميع الطلاب (${sheet.students.length})</option>
          <option value="attended">حضر الامتحان</option>
          <option value="absent">غائب</option>
          <option value="excused">معتذر</option>
          <option value="pending">قيد الانتظار</option>
        </select>
      </div>

      <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
        ${!isCancelled ? `
          <button type="button" id="mark-remaining-absent-grades-btn" class="btn btn-secondary btn-sm" title="تعيين كل طالب لم يرصد له درجة حتى الآن كـ 'غائب'">
            تعيين المتبقين غياب
          </button>
          <button type="button" id="save-all-grades-btn" class="btn btn-primary btn-sm">
            ${icons.check}
            <span>حفظ الكشف بالكامل</span>
          </button>
        ` : `
          <span class="badge badge-danger">الامتحان ملغى — لا يمكن تعديل الدرجات</span>
        `}
      </div>
    </div>

    <!-- Results Table -->
    <div class="table-container">
      <table class="data-table" id="exam-results-table">
        <thead>
          <tr>
            <th style="width:40px;">#</th>
            <th>اسم الطالب</th>
            <th>بيانات الاتصال</th>
            <th>حالة الحضور</th>
            <th>الدرجة (من ${exam.max_score})</th>
            <th>النسبة المئوية</th>
            <th>النتيجة</th>
            <th>ملاحظات</th>
            <th style="text-align:center;">إجراء</th>
          </tr>
        </thead>
        <tbody>
          ${sheet.students.map((st, idx) => {
            const isAttended = st.status === 'attended';
            const isAbsent = st.status === 'absent';
            const isExcused = st.status === 'excused';
            const isPending = !st.status;

            let resultBadge = '';
            if (isPending) {
              resultBadge = '<span class="badge badge-pending">قيد الانتظار</span>';
            } else if (isAbsent) {
              resultBadge = '<span class="badge badge-danger">غائب</span>';
            } else if (isExcused) {
              resultBadge = '<span class="badge badge-primary">معتذر</span>';
            } else if (st.is_passed) {
              resultBadge = '<span class="badge badge-pass">ناجح</span>';
            } else {
              resultBadge = '<span class="badge badge-fail">راسب</span>';
            }

            return `
              <tr class="student-result-row" data-student-id="${st.student_id}" data-status="${st.status || 'pending'}">
                <td style="color:var(--slate-400); font-size:0.8rem; font-family:monospace;">${idx + 1}</td>
                <td>
                  <div style="font-weight:700; color:var(--slate-900);">${st.student_name}</div>
                </td>
                <td>
                  <div class="tabular-nums" style="font-size:0.8rem; color:var(--slate-700);">${st.student_phone}</div>
                  ${st.parent_phone ? `<div class="tabular-nums" style="font-size:0.75rem; color:var(--slate-500);">ولي الأمر: ${st.parent_phone}</div>` : ''}
                </td>
                <td>
                  <select class="form-input row-status-select" style="height:34px; font-size:0.82rem; padding:0 0.5rem; min-width:95px;" ${isCancelled ? 'disabled' : ''}>
                    <option value="" ${isPending ? 'selected' : ''}>قيد الانتظار</option>
                    <option value="attended" ${isAttended ? 'selected' : ''}>حاضر</option>
                    <option value="absent" ${isAbsent ? 'selected' : ''}>غائب</option>
                    <option value="excused" ${isExcused ? 'selected' : ''}>بعذر</option>
                  </select>
                </td>
                <td>
                  <input type="number"
                         class="score-input row-score-input tabular-nums"
                         step="0.5"
                         min="0"
                         max="${exam.max_score}"
                         placeholder="—"
                         value="${st.score !== null && st.score !== undefined ? st.score : ''}"
                         ${isCancelled || !isAttended ? 'disabled' : ''}>
                </td>
                <td>
                  <span class="row-pct tabular-nums" style="font-weight:700; font-size:0.85rem; color:var(--slate-700);">
                    ${st.percentage !== null && st.percentage !== undefined ? st.percentage + '%' : '—'}
                  </span>
                </td>
                <td>
                  <span class="row-result-badge">${resultBadge}</span>
                </td>
                <td>
                  <input type="text"
                         class="form-input row-notes-input"
                         style="height:34px; font-size:0.8rem; min-width:110px;"
                         placeholder="ملاحظات..."
                         value="${st.notes || ''}"
                         ${isCancelled ? 'disabled' : ''}>
                </td>
                <td style="text-align:center;">
                  <div style="display:flex; justify-content:center; gap:0.3rem;">
                    ${!isCancelled ? `
                      <button type="button" class="btn btn-primary btn-sm save-single-result-btn" title="حفظ نتيجة هذا الطالب فقط">
                        ${icons.check}
                      </button>
                    ` : ''}
                    <button type="button" class="btn btn-secondary btn-sm view-student-exam-history-btn" data-student-id="${st.student_id}" title="عرض سجل امتحانات الطالب">
                      📜
                    </button>
                  </div>
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>

    <!-- Modal: Group Exams Summary Report -->
    <div id="group-exams-summary-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content" style="max-width:750px;">
        <div class="modal-header">
          <h3 class="modal-title" id="group-exams-summary-modal-title">تقرير أداء امتحانات المجموعة</h3>
          <button type="button" class="modal-close" id="close-group-exams-summary-modal">✕</button>
        </div>
        <div class="modal-body" id="group-exams-summary-modal-body">
          <!-- Dynamic Content -->
        </div>
      </div>
    </div>

    <!-- Modal: Student Exam History Report -->
    <div id="student-exam-history-modal" class="modal-overlay" style="display:none;">
      <div class="modal-content" style="max-width:750px;">
        <div class="modal-header">
          <h3 class="modal-title" id="student-exam-history-modal-title">سجل درجات وامتحانات الطالب</h3>
          <button type="button" class="modal-close" id="close-student-exam-history-modal">✕</button>
        </div>
        <div class="modal-body" id="student-exam-history-modal-body">
          <!-- Dynamic Content -->
        </div>
      </div>
    </div>
  `;
}

// --- View 6: System & Backups View ---
function renderSystemView() {
  const isTeacher = state.user && (state.user.is_teacher || state.user.user_type === 'teacher');

  const backupsListHtml = () => {
    if (!state.backups || state.backups.length === 0) {
      return `
        <div class="empty-state" style="padding: 2.5rem 1rem; text-align: center; color: var(--slate-500);">
          <div style="font-size: 2rem; margin-bottom: 0.5rem;">💾</div>
          <p style="margin: 0; font-weight: 500;">لا توجد نسخ احتياطية مسجلة حتى الآن.</p>
          <p style="margin: 0.25rem 0 0; font-size: 0.8rem; color: var(--slate-400);">
            اضغط على زر "إنشاء نسخة احتياطية فورية" لإنشاء أول نسخة مشفرة ومفحوصة السلامة.
          </p>
        </div>
      `;
    }

    return `
      <div class="table-responsive" style="margin-top: 1rem;">
        <table class="table" style="width: 100%; border-collapse: collapse;">
          <thead>
            <tr>
              <th style="text-align: right;">اسم ملف النسخة</th>
              <th style="text-align: right;">تاريخ ووقت الإنشاء</th>
              <th style="text-align: right;">حجم الملف</th>
              <th style="text-align: right;">حالة الفحص (Integrity)</th>
              <th style="text-align: center;">إجراءات</th>
            </tr>
          </thead>
          <tbody>
            ${state.backups.map(b => {
              const dateDisplay = b.created_at ? new Date(b.created_at).toLocaleString('ar-EG') : '—';
              const isVerifiedBadge = b.is_verified
                ? `<span class="badge badge-success" title="تم التحقق من سلامة ملف SQLite">✔ سليم ومفحوص</span>`
                : `<span class="badge badge-danger" title="${escapeHtml(b.integrity_status)}">⚠ خطأ بالفحص</span>`;
              return `
                <tr>
                  <td class="tabular-nums" style="font-family: monospace; font-size: 0.85rem; font-weight: 600; direction: ltr; text-align: right;">
                    ${escapeHtml(b.filename)}
                  </td>
                  <td style="font-size: 0.85rem; color: var(--slate-600);">${dateDisplay}</td>
                  <td class="tabular-nums" style="font-size: 0.85rem; font-weight: 600;">${escapeHtml(b.size_formatted)}</td>
                  <td>${isVerifiedBadge}</td>
                  <td style="text-align: center;">
                    <button class="btn btn-sm btn-outline download-backup-btn" data-filename="${escapeHtml(b.filename)}" title="تحميل النسخة الاحتياطية إلى جهازك">
                      📥 تحميل
                    </button>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    `;
  };

  const backupSectionHtml = isTeacher ? `
    <div class="card" style="margin-top: 1.5rem;">
      <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
        <div>
          <h2 class="card-title" style="margin: 0;">إدارة النسخ الاحتياطي لقاعدة البيانات</h2>
          <p class="card-subtitle" style="margin: 0.25rem 0 0; font-size: 0.8rem; color: var(--slate-500);">
            حماية بيانات الطلاب والماليات بواسطة SQLite Online Backup API المفحوص تلقائياً.
          </p>
        </div>
        <button id="create-backup-btn" class="btn btn-primary" ${state.isCreatingBackup ? 'disabled' : ''}>
          ${state.isCreatingBackup ? '<span class="spinner-sm"></span> جاري النسخ والفحص...' : '📥 إنشاء نسخة احتياطية فورية'}
        </button>
      </div>

      <div style="padding: 1rem 1.25rem; background: var(--slate-50); border-bottom: 1px solid var(--border); display: flex; flex-wrap: wrap; gap: 1.5rem; justify-content: space-between; align-items: center; font-size: 0.85rem;">
        <div>
          <span style="color: var(--slate-500);">مسار التخزين النشط:</span>
          <span class="badge badge-secondary" style="font-family: monospace; direction: ltr; margin-right: 0.5rem;">
            ${escapeHtml(state.backupDirectoryHint || 'جاري الفحص...')}
          </span>
        </div>
        <div style="display: flex; gap: 1.5rem;">
          <div>
            <span style="color: var(--slate-500);">إجمالي النسخ:</span>
            <span class="tabular-nums" style="font-weight: 700; color: var(--primary);">${state.backupTotalCount || (state.backups ? state.backups.length : 0)}</span>
          </div>
          <div>
            <span style="color: var(--slate-500);">إجمالي الحجم:</span>
            <span class="tabular-nums" style="font-weight: 700;">${escapeHtml(state.backupTotalSizeFormatted || '0 B')}</span>
          </div>
        </div>
      </div>

      ${backupsListHtml()}
    </div>

    <!-- Safe Disaster Recovery Procedures Callout -->
    <div class="card" style="margin-top: 1.5rem; border-left: 4px solid var(--primary); background: #f8fafc;">
      <div class="card-header">
        <h3 class="card-title" style="font-size: 1rem; color: var(--slate-800);">🛡 إجراءات الاستعادة الآمنة من الكوارث (Disaster Recovery Guide)</h3>
      </div>
      <div style="padding: 0 1.25rem 1.25rem; font-size: 0.85rem; color: var(--slate-700); line-height: 1.6;">
        <p style="margin: 0 0 0.5rem; font-weight: 600;">
          لضمان عدم تلف البيانات ومنع قفل الملفات المفتوحة أثناء وضع الـ WAL، تتم الاستعادة يدوياً دون اتصال (Offline Restoration):
        </p>
        <ol style="margin: 0; padding-right: 1.25rem;">
          <li><strong>إيقاف تشغيل الخدمة:</strong> قم بإيقاف سيرفر TeacherSystem تماماً.</li>
          <li><strong>أخذ نسخة أمان:</strong> انسخ ملف قاعدة البيانات الحالي من <code>data/teachersystem.db</code> إلى مجلد أمان خارجي.</li>
          <li><strong>استبدال الملف:</strong> حمّل ملف النسخة الاحتياطية المطلوبة، وأعد تسميته إلى <code>teachersystem.db</code>، وضعه في مجلد <code>data/</code>.</li>
          <li><strong>مسح مخلفات WAL:</strong> احذف ملفات الـ WAL المؤقتة إن وُجدت (<code>teachersystem.db-wal</code> و <code>teachersystem.db-shm</code>).</li>
          <li><strong>إعادة التشغيل:</strong> شغّل سيرفر TeacherSystem مجدداً وتأكد من سلامة الجداول وسجلات الحضور والماليات.</li>
        </ol>
      </div>
    </div>
  ` : `
    <div class="card" style="margin-top: 1.5rem; background: #fffbeb; border: 1px solid #fde68a;">
      <div style="padding: 1.25rem; display: flex; align-items: center; gap: 0.75rem;">
        <span style="font-size: 1.5rem;">🔒</span>
        <div>
          <h3 style="margin: 0; font-size: 0.95rem; font-weight: 700; color: #92400e;">صلاحية مقيدة</h3>
          <p style="margin: 0.25rem 0 0; font-size: 0.85rem; color: #b45309;">
            إدارة وتحميل النسخ الاحتياطية لقاعدة البيانات مقتصرة حصرياً على حساب المعلم الرئيسي (Teacher) لحماية أمان النظام والبيانات المالية.
          </p>
        </div>
      </div>
    </div>
  `;

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">حالة النظام والنسخ الاحتياطي</h1>
        <p class="page-subtitle">فحص إعدادات SQLite، وتفعيل وضع الـ WAL، وأمان السيرفر المحلي.</p>
      </div>
    </div>

    <div class="system-grid">
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">قاعدة البيانات المحلية</h2>
        </div>
        <div style="display:flex; flex-direction:column; gap:0.75rem; font-size:0.85rem;">
          <div style="display:flex; justify-content:space-between; padding-bottom:0.5rem; border-bottom:1px solid var(--border);">
            <span style="color:var(--slate-500);">المسار المحلي:</span>
            <span class="tabular-nums" style="font-weight:600; direction:ltr;">data/teachersystem.db</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:0.5rem; border-bottom:1px solid var(--border);">
            <span style="color:var(--slate-500);">وضع التشغيل:</span>
            <span class="badge badge-success">WAL Mode (Write-Ahead Logging)</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:0.5rem; border-bottom:1px solid var(--border);">
            <span style="color:var(--slate-500);">مهلة القفل (Busy Timeout):</span>
            <span class="tabular-nums" style="font-weight:600;">5000 ms</span>
          </div>
          <div style="display:flex; justify-content:space-between;">
            <span style="color:var(--slate-500);">التوافقية مع النسخ الاحتياطي:</span>
            <span class="badge badge-primary">Online Safe Backup API</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h2 class="card-title">حماية الجلسات والأمان</h2>
        </div>
        <div style="display:flex; flex-direction:column; gap:0.75rem; font-size:0.85rem;">
          <div style="display:flex; justify-content:space-between; padding-bottom:0.5rem; border-bottom:1px solid var(--border);">
            <span style="color:var(--slate-500);">تشفير كلمات المرور:</span>
            <span style="font-weight:700; color:var(--primary);">Argon2id (64MB RAM, 3 Iterations)</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:0.5rem; border-bottom:1px solid var(--border);">
            <span style="color:var(--slate-500);">تخزين التوكن في القاعدة:</span>
            <span class="badge badge-success">SHA-256 Digest Only</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:0.5rem; border-bottom:1px solid var(--border);">
            <span style="color:var(--slate-500);">حماية الكوكيز:</span>
            <span style="font-weight:600;">HttpOnly=True, SameSite=Lax</span>
          </div>
          <div style="display:flex; justify-content:space-between;">
            <span style="color:var(--slate-500);">حماية تخمين كلمات المرور:</span>
            <span class="badge badge-secondary">Rate Limiter (5 محاولات / 5 دقائق)</span>
          </div>
        </div>
      </div>
    </div>

    ${backupSectionHtml}
  `;
}

// --- Main Router & Controller ---
export async function navigate() {
  const hash = window.location.hash || '';
  const [cleanRoutePart, queryString] = hash.replace(/^#\/?/, '').split('?');
  const cleanRoute = cleanRoutePart || '';
  const queryParams = new URLSearchParams(queryString || '');
  const appContainer = document.getElementById('app');

  // 1. Check First-run setup status if unknown
  try {
    const statusResp = await api.checkSetupStatus();
    state.setupRequired = statusResp.setup_required;
  } catch (err) {
    console.error('Setup status check failed:', err);
  }

  // If system requires setup, force #/setup
  if (state.setupRequired && cleanRoute !== 'setup') {
    window.location.hash = '#/setup';
    return;
  }

  // 2. Check Auth Status if on protected route
  if (!state.setupRequired && cleanRoute !== 'login' && cleanRoute !== 'setup') {
    try {
      const me = await api.getMe();
      state.user = me;
      state.isAuthenticated = true;
    } catch (err) {
      state.user = null;
      state.isAuthenticated = false;
      window.location.hash = '#/login';
      return;
    }
  }

  // 3. Render appropriate View
  state.activeRoute = cleanRoute || (state.isAuthenticated ? 'dashboard' : 'login');

  if (state.activeRoute === 'attendance') {
    const sid = queryParams.get('session_id');
    if (sid) {
      state.activeSessionId = isNaN(sid) ? sid : parseInt(sid, 10);
    }
  } else {
    state.activeSessionId = null;
    state.activeSessionSheet = null;
  }

  if (state.activeRoute === 'exams') {
    const eid = queryParams.get('exam_id');
    if (eid) {
      state.activeExamId = isNaN(eid) ? eid : parseInt(eid, 10);
    }
  } else {
    state.activeExamId = null;
    state.activeExamSheet = null;
  }

  if (state.activeRoute === 'students') {
    const tab = queryParams.get('tab');
    if (tab === 'groups') {
      state.activeAcademicTab = 'groups';
    } else if (tab === 'distribution') {
      state.activeAcademicTab = 'distribution';
      const gid = queryParams.get('group_id');
      if (gid) state.selectedDistributionGroupId = gid;
    } else if (tab === 'students') {
      state.activeAcademicTab = 'students';
    }
  }

  if (state.activeRoute === 'cash') {
    const tab = queryParams.get('tab');
    if (tab && ['overview', 'payments', 'dues', 'configs', 'reports'].includes(tab)) {
      state.financeTab = tab;
    }
  }

  if (state.activeRoute === 'setup') {
    appContainer.innerHTML = renderSetupView();
    bindSetupEvents();
  } else if (state.activeRoute === 'login') {
    appContainer.innerHTML = renderLoginView();
    bindLoginEvents();
  } else {
    // Protected App Shell Routes
    let viewContent = '';
    if (state.activeRoute === 'dashboard') {
      const user = state.user || {};
      const isTeacher = user.is_teacher || user.user_type === 'teacher';
      const canViewAttendance = isTeacher || user.can_view_attendance;
      const canViewGrades = isTeacher || user.can_view_grades || user.can_manage_exams || user.can_enter_grades;
      const canViewFinances = isTeacher || user.can_view_financial_analytics || user.can_view_student_payment_history || user.can_collect_cash || user.can_manage_fees;

      state.dashboardError = { sessions: null, exams: null, finance: null };

      try {
        state.assistants = isTeacher ? await api.listAssistants() : [];
      } catch (e) {
        state.assistants = [];
      }
      try {
        state.students = await api.listStudents({ is_active: 'true' });
        state.groups = await api.listGroups({ is_active: 'true' });
      } catch (e) {
        state.students = [];
        state.groups = [];
      }

      // Today's sessions
      if (canViewAttendance) {
        try {
          const d = new Date();
          const todayStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
          state.todaySessions = await api.listSessions({ session_date: todayStr });
        } catch (e) {
          state.todaySessions = [];
          state.dashboardError.sessions = e.message || 'تعذر تحميل حصص اليوم';
        }
      } else {
        state.todaySessions = [];
      }

      // Recent exams
      if (canViewGrades) {
        try {
          state.recentExams = await api.listExams({ limit: 5 });
        } catch (e) {
          state.recentExams = [];
          state.dashboardError.exams = e.message || 'تعذر تحميل الامتحانات الأخيرة';
        }
      } else {
        state.recentExams = [];
      }

      // Finance overview & monthly collection report
      if (canViewFinances) {
        try {
          const d = new Date();
          const billingMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
          const [repRes, ovRes] = await Promise.allSettled([
            api.getMonthlyCollectionReport(billingMonth),
            api.getFinanceOverview()
          ]);
          state.dashboardFinanceReport = repRes.status === 'fulfilled' ? repRes.value : null;
          state.dashboardFinanceOverview = ovRes.status === 'fulfilled' ? ovRes.value : null;
          if (repRes.status === 'rejected' && ovRes.status === 'rejected') {
            state.dashboardError.finance = repRes.reason?.message || ovRes.reason?.message || 'تعذر تحميل البيانات المالية';
          }
        } catch (e) {
          state.dashboardFinanceReport = null;
          state.dashboardFinanceOverview = null;
          state.dashboardError.finance = e.message || 'تعذر تحميل البيانات المالية';
        }
      } else {
        state.dashboardFinanceReport = null;
        state.dashboardFinanceOverview = null;
      }

      viewContent = renderDashboardView();
    } else if (state.activeRoute === 'assistants') {
      try {
        state.assistants = await api.listAssistants();
      } catch (e) {
        state.assistants = [];
      }
      viewContent = renderAssistantsView();
    } else if (state.activeRoute === 'students') {
      try {
        state.students = await api.listStudents(state.studentFilters);
        state.groups = await api.listGroups(state.groupFilters);
        if (state.activeAcademicTab === 'distribution') {
          const targetGid = state.selectedDistributionGroupId || (state.groups.length > 0 ? state.groups[0].id : null);
          if (targetGid) {
            state.selectedDistributionGroupId = targetGid;
            try {
              state.distributionOverview = await api.getGroupDistributionOverview(targetGid);
            } catch (err) {
              state.distributionOverview = null;
            }
          }
        }
      } catch (e) {
        showToast(e.message, 'error');
        state.students = [];
        state.groups = [];
      }
      viewContent = renderAcademicView();
    } else if (state.activeRoute === 'attendance') {
      try {
        state.groups = await api.listGroups();
        if (state.activeSessionId) {
          state.activeSessionSheet = await api.getSessionAttendance(state.activeSessionId);
        } else {
          state.sessions = await api.listSessions(state.sessionFilters);
        }
      } catch (e) {
        showToast(e.message, 'error');
        state.sessions = [];
        state.activeSessionSheet = null;
      }
      viewContent = renderAttendanceView();
    } else if (state.activeRoute === 'exams') {
      try {
        state.groups = await api.listGroups();
        if (state.activeExamId) {
          state.activeExamSheet = await api.getExamResults(state.activeExamId);
        } else {
          state.exams = await api.listExams(state.examFilters);
        }
      } catch (e) {
        showToast(e.message, 'error');
        state.exams = [];
        state.activeExamSheet = null;
      }
      viewContent = renderExamsView();
    } else if (state.activeRoute === 'cash') {
      try {
        state.groups = await api.listGroups();
        state.students = await api.listStudents({ is_active: 'true' });
        try {
          state.financeOverview = await api.getFinanceOverview();
        } catch (e) {
          state.financeOverview = null;
        }

        if (state.financeTab === 'payments') {
          state.payments = await api.listCashPayments(state.paymentFilters);
        } else if (state.financeTab === 'dues') {
          state.dues = await api.listStudentDues(state.dueFilters);
        } else if (state.financeTab === 'configs') {
          state.feeConfigs = await api.listFeeConfigs();
        } else if (state.financeTab === 'overview') {
          state.payments = await api.listCashPayments({ include_reversed: 'true' });
        }
      } catch (e) {
        showToast(e.message, 'error');
      }
      viewContent = renderFinanceView();
    } else if (state.activeRoute === 'system') {
      const isTeacher = state.user && (state.user.is_teacher || state.user.user_type === 'teacher');
      if (isTeacher) {
        try {
          const res = await api.listBackups();
          state.backups = res.backups || [];
          state.backupDirectoryHint = res.backup_directory_hint || '';
          state.backupTotalCount = res.total_count || 0;
          state.backupTotalSizeFormatted = res.total_size_formatted || '0 B';
        } catch (e) {
          console.error('Failed to load backups:', e);
          state.backups = [];
          state.backupDirectoryHint = '';
          state.backupTotalCount = 0;
          state.backupTotalSizeFormatted = '0 B';
        }
      } else {
        state.backups = [];
        state.backupDirectoryHint = '';
        state.backupTotalCount = 0;
        state.backupTotalSizeFormatted = '0 B';
      }
      viewContent = renderSystemView();
    } else {
      window.location.hash = '#/dashboard';
      return;
    }

    appContainer.innerHTML = renderAppShell(viewContent, state.activeRoute);
    bindShellEvents();
    if (state.activeRoute === 'dashboard') {
      bindDashboardEvents();
    } else if (state.activeRoute === 'assistants') {
      bindAssistantEvents();
    } else if (state.activeRoute === 'students') {
      bindAcademicEvents(queryParams);
    } else if (state.activeRoute === 'attendance') {
      bindAttendanceEvents(queryParams);
    } else if (state.activeRoute === 'exams') {
      bindExamEvents(queryParams);
    } else if (state.activeRoute === 'cash') {
      bindFinanceEvents(queryParams);
    } else if (state.activeRoute === 'system') {
      bindSystemEvents();
    }
  }
}

// --- Event Handlers ---
function bindSetupEvents() {
  const pwdInput = document.getElementById('setup-password');
  const feedback = document.getElementById('password-strength-feedback');
  const form = document.getElementById('setup-form');

  if (pwdInput && feedback) {
    pwdInput.addEventListener('input', () => {
      const res = evaluatePassword(pwdInput.value);
      feedback.textContent = res.message;
      feedback.style.color = res.valid ? '#059669' : '#DC2626';
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const pwd = pwdInput.value;
      const res = evaluatePassword(pwd);
      if (!res.valid) {
        showToast(res.message, 'error');
        return;
      }

      const submitBtn = document.getElementById('setup-submit-btn');
      submitBtn.disabled = true;
      submitBtn.textContent = 'جارٍ إتمام التهيئة...';

      try {
        await api.firstRunSetup({
          username: document.getElementById('setup-username').value.trim(),
          full_name: document.getElementById('setup-fullname').value.trim(),
          phone: document.getElementById('setup-phone').value.trim(),
          password: pwd
        });
        showToast('تمت تهيئة حساب المعلم بنجاح! يمكنك الآن تسجيل الدخول.', 'success');
        state.setupRequired = false;
        setTimeout(() => {
          window.location.hash = '#/login';
        }, 1200);
      } catch (err) {
        showToast(err.message, 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = 'إتمام التهيئة وبدء الاستخدام';
      }
    });
  }
}

function bindLoginEvents() {
  const form = document.getElementById('login-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('login-submit-btn');
    btn.disabled = true;
    btn.textContent = 'جارٍ التحقق...';

    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    try {
      await api.login({ username, password });
      showToast('مرحباً بك! تم تسجيل الدخول بنجاح.', 'success');
      setTimeout(() => {
        window.location.hash = '#/dashboard';
      }, 500);
    } catch (err) {
      if (err.status === 429) {
        state.rateLimitRemaining = err.retryAfter || 60;
        startRateLimitCountdown();
        const appContainer = document.getElementById('app');
        appContainer.innerHTML = renderLoginView();
        bindLoginEvents();
      } else {
        showToast(err.message, 'error');
        btn.disabled = false;
        btn.textContent = 'تسجيل الدخول';
      }
    }
  });
}

function startRateLimitCountdown() {
  if (state.rateLimitTimer) clearInterval(state.rateLimitTimer);
  state.rateLimitTimer = setInterval(() => {
    state.rateLimitRemaining -= 1;
    const display = document.getElementById('lockout-timer-display');
    if (display) {
      display.textContent = `يرجى الانتظار ${state.rateLimitRemaining} ثانية...`;
    }
    if (state.rateLimitRemaining <= 0) {
      clearInterval(state.rateLimitTimer);
      state.rateLimitRemaining = 0;
      navigate(); // Re-render unlocked form
    }
  }, 1000);
}

function bindShellEvents() {
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      try {
        await api.logout();
      } catch (e) {
        console.error('Logout request failed:', e);
      }
      state.user = null;
      state.isAuthenticated = false;
      showToast('تم تسجيل الخروج بنجاح.', 'success');
      window.location.hash = '#/login';
    });
  }

  // Mobile Drawer Toggle and Backdrop Handling
  const sidebar = document.getElementById('app-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  const menuToggle = document.getElementById('mobile-menu-toggle');
  const closeSidebarBtn = document.getElementById('close-sidebar-btn');

  const openSidebar = () => {
    if (sidebar) sidebar.classList.add('open');
    if (backdrop) backdrop.classList.add('active');
  };

  const closeSidebar = () => {
    if (sidebar) sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('active');
  };

  if (menuToggle) menuToggle.addEventListener('click', openSidebar);
  if (closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebar);
  if (backdrop) backdrop.addEventListener('click', closeSidebar);

  // Auto-close drawer on small screens when user clicks any navigation link
  document.querySelectorAll('.app-sidebar .nav-link').forEach(link => {
    link.addEventListener('click', closeSidebar);
  });
}

function bindAssistantEvents() {
  const modal = document.getElementById('assistant-modal');
  const modalTitle = document.getElementById('assistant-modal-title');
  const openBtn = document.getElementById('open-add-assistant-modal');
  const openEmptyBtn = document.getElementById('open-add-assistant-empty');
  const closeBtn = document.getElementById('close-assistant-modal');
  const cancelBtn = document.getElementById('cancel-assistant-btn');
  const form = document.getElementById('assistant-form');
  const pwdInput = document.getElementById('ass-password');
  const pwdFeedback = document.getElementById('ass-password-feedback');
  const pwdGroup = document.getElementById('ass-password-group');
  const usernameGroup = document.getElementById('ass-username-group');

  const openAddModal = () => {
    state.editingAssistantId = null;
    if (form) form.reset();
    if (pwdFeedback) pwdFeedback.textContent = '';
    if (modalTitle) modalTitle.textContent = 'إضافة مساعد جديد';
    if (usernameGroup) usernameGroup.style.display = 'block';
    if (pwdGroup) pwdGroup.style.display = 'block';
    if (pwdInput) pwdInput.setAttribute('required', 'required');
    if (modal) modal.style.display = 'flex';
  };

  const openEditModal = (assistant) => {
    state.editingAssistantId = assistant.id;
    if (form) form.reset();
    if (modalTitle) modalTitle.textContent = `تعديل صلاحيات المساعد: ${assistant.full_name}`;
    document.getElementById('ass-fullname').value = assistant.full_name;
    document.getElementById('ass-phone').value = assistant.phone;
    
    // Hide username and password during edit
    if (usernameGroup) usernameGroup.style.display = 'none';
    if (pwdGroup) pwdGroup.style.display = 'none';
    if (pwdInput) pwdInput.removeAttribute('required');

    // Populate permissions checkboxes
    document.getElementById('perm-mark-attendance').checked = !!assistant.can_mark_attendance;
    document.getElementById('perm-collect-cash').checked = !!assistant.can_collect_cash;
    const permManageFeesEl = document.getElementById('perm-manage-fees');
    if (permManageFeesEl) permManageFeesEl.checked = !!assistant.can_manage_fees;
    document.getElementById('perm-enter-grades').checked = !!assistant.can_enter_grades;
    document.getElementById('perm-manage-students').checked = !!assistant.can_manage_students;
    document.getElementById('perm-financial-analytics').checked = !!assistant.can_view_financial_analytics;

    if (modal) modal.style.display = 'flex';
  };

  const closeModal = () => {
    if (modal) modal.style.display = 'none';
    state.editingAssistantId = null;
  };

  if (openBtn) openBtn.addEventListener('click', openAddModal);
  if (openEmptyBtn) openEmptyBtn.addEventListener('click', openAddModal);
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

  // Close modal when clicking directly on backdrop overlay
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeModal();
      }
    });
  }

  if (pwdInput && pwdFeedback) {
    pwdInput.addEventListener('input', () => {
      if (!pwdInput.value) {
        pwdFeedback.textContent = '';
        return;
      }
      const res = evaluatePassword(pwdInput.value);
      pwdFeedback.textContent = res.message;
      pwdFeedback.style.color = res.valid ? '#059669' : '#DC2626';
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const saveBtn = document.getElementById('save-assistant-btn');
      saveBtn.disabled = true;
      saveBtn.textContent = 'جارٍ الحفظ...';

      const permissions = {
        can_mark_attendance: document.getElementById('perm-mark-attendance').checked,
        can_collect_cash: document.getElementById('perm-collect-cash').checked,
        can_manage_fees: document.getElementById('perm-manage-fees') ? document.getElementById('perm-manage-fees').checked : false,
        can_enter_grades: document.getElementById('perm-enter-grades').checked,
        can_manage_students: document.getElementById('perm-manage-students').checked,
        can_view_financial_analytics: document.getElementById('perm-financial-analytics').checked,
      };

      try {
        if (state.editingAssistantId) {
          // Update existing assistant
          await api.updateAssistant(state.editingAssistantId, {
            full_name: document.getElementById('ass-fullname').value.trim(),
            phone: document.getElementById('ass-phone').value.trim(),
            permissions: permissions
          });
          showToast('تم تحديث بيانات وصلاحيات المساعد بنجاح!', 'success');
        } else {
          // Create new assistant
          const pwd = pwdInput.value;
          const evalRes = evaluatePassword(pwd);
          if (!evalRes.valid) {
            showToast(evalRes.message, 'error');
            saveBtn.disabled = false;
            saveBtn.textContent = 'حفظ المساعد وتأكيد الصلاحيات';
            return;
          }

          await api.createAssistant({
            username: document.getElementById('ass-username').value.trim(),
            full_name: document.getElementById('ass-fullname').value.trim(),
            phone: document.getElementById('ass-phone').value.trim(),
            password: pwd,
            permissions: permissions
          });
          showToast('تمت إضافة المساعد بنجاح!', 'success');
        }

        closeModal();
        state.assistants = await api.listAssistants();
        navigate();
      } catch (err) {
        showToast(err.message, 'error');
        saveBtn.disabled = false;
        saveBtn.textContent = 'حفظ المساعد وتأكيد الصلاحيات';
      }
    });
  }

  // Edit buttons
  document.querySelectorAll('.edit-assistant-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      const assistant = state.assistants.find(a => a.id === id);
      if (assistant) {
        openEditModal(assistant);
      }
    });
  });

  // Delete buttons
  document.querySelectorAll('.delete-assistant-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      const name = btn.getAttribute('data-name');
      if (confirm(`هل أنت متأكد من حذف المساعد "${name}"؟\nسيتم إيقاف صلاحياته وإلغاء كافة جلسات دخوله فوراً.`)) {
        try {
          await api.deleteAssistant(id);
          showToast(`تم حذف المساعد "${name}" بنجاح وإلغاء صلاحياته.`, 'success');
          state.assistants = await api.listAssistants();
          navigate();
        } catch (err) {
          showToast(err.message, 'error');
        }
      }
    });
  });
}

// --- Shared Barcode Distribution Helpers ---
async function shareStudentCard(studentId, studentName, groupId) {
  try {
    const blob = await api.getStudentCardBlob(studentId, groupId);
    const filename = `بطاقة_${studentName.replace(/\s+/g, '_')}.pdf`;
    let file = null;
    try {
      file = new File([blob], filename, { type: 'application/pdf' });
    } catch (e) {
      file = null;
    }

    let shared = false;
    if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({
          title: `بطاقة الطالب - ${studentName}`,
          text: `بطاقة الباركود الذكية الخاصة بالطالب: ${studentName}`,
          files: [file]
        });
        shared = true;
      } catch (err) {
        if (err.name === 'AbortError') return;
      }
    }

    if (!shared) {
      await api.downloadStudentCardPdf(studentId, studentName, groupId);
    }

    await api.updateStudentDistributionStatus(studentId, {
      status: 'share_opened',
      group_id: groupId
    });
    showToast('تم فتح نافذة المشاركة / تحميل البطاقة بنجاح. يرجى تأكيد التسليم بعد إتمام الإرسال.', 'info');
  } catch (err) {
    showToast(err.message || 'تعذر مشاركة البطاقة.', 'error');
  }
}

function bindAcademicEvents(queryParams) {
  // Tab switching
  const tabStudentsBtn = document.getElementById('tab-btn-students');
  const tabGroupsBtn = document.getElementById('tab-btn-groups');
  if (tabStudentsBtn) {
    tabStudentsBtn.addEventListener('click', () => {
      state.activeAcademicTab = 'students';
      navigate();
    });
  }
  if (tabGroupsBtn) {
    tabGroupsBtn.addEventListener('click', () => {
      state.activeAcademicTab = 'groups';
      navigate();
    });
  }
  const tabDistributionBtn = document.getElementById('tab-btn-distribution');
  if (tabDistributionBtn) {
    tabDistributionBtn.addEventListener('click', async () => {
      state.activeAcademicTab = 'distribution';
      const gid = state.selectedDistributionGroupId || (state.groups.length > 0 ? state.groups[0].id : null);
      if (gid) {
        state.selectedDistributionGroupId = gid;
        try {
          state.distributionOverview = await api.getGroupDistributionOverview(gid);
        } catch (e) {
          state.distributionOverview = null;
        }
      }
      navigate();
    });
  }

  // --- Student Filters ---
  const searchInput = document.getElementById('student-search-input');
  const searchBtn = document.getElementById('search-student-btn');
  const gradeFilter = document.getElementById('student-grade-filter');
  const statusFilter = document.getElementById('student-status-filter');
  const resetFiltersBtn = document.getElementById('reset-student-filters-btn');

  const applyStudentFilters = async () => {
    state.studentFilters.q = searchInput ? searchInput.value.trim() : '';
    state.studentFilters.grade_level = gradeFilter ? gradeFilter.value : '';
    state.studentFilters.is_active = statusFilter ? statusFilter.value : '';
    try {
      state.students = await api.listStudents(state.studentFilters);
      navigate();
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  if (searchBtn) searchBtn.addEventListener('click', applyStudentFilters);
  if (searchInput) {
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        applyStudentFilters();
      }
    });
  }
  if (gradeFilter) gradeFilter.addEventListener('change', applyStudentFilters);
  if (statusFilter) statusFilter.addEventListener('change', applyStudentFilters);
  if (resetFiltersBtn) {
    resetFiltersBtn.addEventListener('click', async () => {
      state.studentFilters = { q: '', grade_level: '', is_active: '' };
      state.students = await api.listStudents();
      navigate();
    });
  }

  // --- Group Filters ---
  const groupGradeFilter = document.getElementById('group-grade-filter');
  const groupStatusFilter = document.getElementById('group-status-filter');
  const resetGroupFiltersBtn = document.getElementById('reset-group-filters-btn');

  const applyGroupFilters = async () => {
    state.groupFilters.grade_level = groupGradeFilter ? groupGradeFilter.value : '';
    state.groupFilters.is_active = groupStatusFilter ? groupStatusFilter.value : '';
    try {
      state.groups = await api.listGroups(state.groupFilters);
      navigate();
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  if (groupGradeFilter) groupGradeFilter.addEventListener('change', applyGroupFilters);
  if (groupStatusFilter) groupStatusFilter.addEventListener('change', applyGroupFilters);
  if (resetGroupFiltersBtn) {
    resetGroupFiltersBtn.addEventListener('click', async () => {
      state.groupFilters = { grade_level: '', is_active: '' };
      state.groups = await api.listGroups();
      navigate();
    });
  }

  // --- Student Add / Edit Modal ---
  const studentModal = document.getElementById('student-modal');
  const studentForm = document.getElementById('student-form');
  const studentModalTitle = document.getElementById('student-modal-title');
  const openAddStudentBtn = document.getElementById('open-add-student-modal');
  const openAddStudentEmpty = document.getElementById('open-add-student-empty');
  const closeStudentModalBtn = document.getElementById('close-student-modal');
  const cancelStudentBtn = document.getElementById('cancel-student-btn');

  const openStudentAdd = () => {
    state.editingStudentId = null;
    if (studentForm) studentForm.reset();
    if (studentModalTitle) studentModalTitle.textContent = 'إضافة طالب جديد';
    const activeCb = document.getElementById('stud-active');
    if (activeCb) activeCb.checked = true;
    if (studentModal) studentModal.style.display = 'flex';
  };

  const openStudentEdit = (student) => {
    state.editingStudentId = student.id;
    if (studentForm) studentForm.reset();
    if (studentModalTitle) studentModalTitle.textContent = `تعديل بيانات الطالب: ${student.full_name}`;
    document.getElementById('stud-fullname').value = student.full_name || '';
    document.getElementById('stud-grade').value = student.grade_level || '1_sec';
    document.getElementById('stud-phone').value = student.phone || '';
    document.getElementById('stud-parent-name').value = student.parent_name || '';
    document.getElementById('stud-parent-phone').value = student.parent_phone || '';
    document.getElementById('stud-address').value = student.address || '';
    document.getElementById('stud-notes').value = student.notes || '';
    const activeCb = document.getElementById('stud-active');
    if (activeCb) activeCb.checked = student.is_active;
    if (studentModal) studentModal.style.display = 'flex';
  };

  const closeStudentModal = () => {
    if (studentModal) studentModal.style.display = 'none';
    state.editingStudentId = null;
  };

  if (openAddStudentBtn) openAddStudentBtn.addEventListener('click', openStudentAdd);
  if (openAddStudentEmpty) openAddStudentEmpty.addEventListener('click', openStudentAdd);
  if (closeStudentModalBtn) closeStudentModalBtn.addEventListener('click', closeStudentModal);
  if (cancelStudentBtn) cancelStudentBtn.addEventListener('click', closeStudentModal);
  if (studentModal) {
    studentModal.addEventListener('click', (e) => {
      if (e.target === studentModal) closeStudentModal();
    });
  }

  if (studentForm) {
    studentForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const saveBtn = document.getElementById('save-student-btn');
      saveBtn.disabled = true;
      saveBtn.textContent = 'جارٍ الحفظ...';

      const payload = {
        full_name: document.getElementById('stud-fullname').value.trim(),
        grade_level: document.getElementById('stud-grade').value,
        phone: document.getElementById('stud-phone').value.trim(),
        parent_name: document.getElementById('stud-parent-name').value.trim() || null,
        parent_phone: document.getElementById('stud-parent-phone').value.trim() || null,
        address: document.getElementById('stud-address').value.trim() || null,
        notes: document.getElementById('stud-notes').value.trim() || null,
        is_active: document.getElementById('stud-active').checked
      };

      try {
        if (state.editingStudentId) {
          await api.updateStudent(state.editingStudentId, payload);
          showToast('تم تحديث بيانات الطالب بنجاح!', 'success');
        } else {
          await api.createStudent(payload);
          showToast('تم تسجيل الطالب بنجاح!', 'success');
        }
        closeStudentModal();
        state.students = await api.listStudents(state.studentFilters);
        navigate();
      } catch (err) {
        showToast(err.message, 'error');
        saveBtn.disabled = false;
        saveBtn.textContent = 'حفظ بيانات الطالب';
      }
    });
  }

  // --- Group Add / Edit Modal ---
  const groupModal = document.getElementById('group-modal');
  const groupForm = document.getElementById('group-form');
  const groupModalTitle = document.getElementById('group-modal-title');
  const openAddGroupBtn = document.getElementById('open-add-group-modal');
  const openAddGroupEmpty = document.getElementById('open-add-group-empty');
  const closeGroupModalBtn = document.getElementById('close-group-modal');
  const cancelGroupBtn = document.getElementById('cancel-group-btn');

  const openGroupAdd = () => {
    state.editingGroupId = null;
    if (groupForm) groupForm.reset();
    if (groupModalTitle) groupModalTitle.textContent = 'إضافة مجموعة جديدة';
    const activeCb = document.getElementById('grp-active');
    if (activeCb) activeCb.checked = true;
    if (groupModal) groupModal.style.display = 'flex';
  };

  const openGroupEdit = (group) => {
    state.editingGroupId = group.id;
    if (groupForm) groupForm.reset();
    if (groupModalTitle) groupModalTitle.textContent = `تعديل المجموعة: ${group.name}`;
    document.getElementById('grp-name').value = group.name || '';
    document.getElementById('grp-grade').value = group.grade_level || '1_sec';
    document.getElementById('grp-subject').value = group.subject || '';
    document.getElementById('grp-schedule').value = group.schedule_details || '';
    const activeCb = document.getElementById('grp-active');
    if (activeCb) activeCb.checked = group.is_active;
    if (groupModal) groupModal.style.display = 'flex';
  };

  const closeGroupModal = () => {
    if (groupModal) groupModal.style.display = 'none';
    state.editingGroupId = null;
  };

  if (openAddGroupBtn) openAddGroupBtn.addEventListener('click', openGroupAdd);
  if (openAddGroupEmpty) openAddGroupEmpty.addEventListener('click', openGroupAdd);
  if (closeGroupModalBtn) closeGroupModalBtn.addEventListener('click', closeGroupModal);
  if (cancelGroupBtn) cancelGroupBtn.addEventListener('click', closeGroupModal);
  if (groupModal) {
    groupModal.addEventListener('click', (e) => {
      if (e.target === groupModal) closeGroupModal();
    });
  }

  if (groupForm) {
    groupForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const saveBtn = document.getElementById('save-group-btn');
      saveBtn.disabled = true;
      saveBtn.textContent = 'جارٍ الحفظ...';

      const payload = {
        name: document.getElementById('grp-name').value.trim(),
        grade_level: document.getElementById('grp-grade').value,
        subject: document.getElementById('grp-subject').value.trim() || null,
        schedule_details: document.getElementById('grp-schedule').value.trim() || null,
        is_active: document.getElementById('grp-active').checked
      };

      try {
        if (state.editingGroupId) {
          await api.updateGroup(state.editingGroupId, payload);
          showToast('تم تحديث المجموعة بنجاح!', 'success');
        } else {
          await api.createGroup(payload);
          showToast('تم إنشاء المجموعة بنجاح!', 'success');
        }
        closeGroupModal();
        state.groups = await api.listGroups(state.groupFilters);
        navigate();
      } catch (err) {
        showToast(err.message, 'error');
        saveBtn.disabled = false;
        saveBtn.textContent = 'حفظ المجموعة';
      }
    });
  }

  // --- Student Groups Modal (Manage Groups of a Student) ---
  const studentGroupsModal = document.getElementById('student-groups-modal');
  const closeStudentGroupsModalBtn = document.getElementById('close-student-groups-modal');
  const closeStudentGroupsBtn = document.getElementById('close-student-groups-btn');

  const closeStudentGroupsModal = () => {
    if (studentGroupsModal) studentGroupsModal.style.display = 'none';
    state.activeModalStudent = null;
  };

  if (closeStudentGroupsModalBtn) closeStudentGroupsModalBtn.addEventListener('click', closeStudentGroupsModal);
  if (closeStudentGroupsBtn) closeStudentGroupsBtn.addEventListener('click', closeStudentGroupsModal);
  if (studentGroupsModal) {
    studentGroupsModal.addEventListener('click', (e) => {
      if (e.target === studentGroupsModal) closeStudentGroupsModal();
    });
  }

  const refreshStudentGroupsModal = async (studentId, studentName, studentGrade) => {
    state.activeModalStudent = { id: studentId, name: studentName, grade: studentGrade };
    document.getElementById('student-groups-title').textContent = `مجموعات الطالب: ${studentName}`;
    const container = document.getElementById('student-groups-list-container');
    const select = document.getElementById('enroll-group-select');

    container.innerHTML = '<div style="padding:1rem; text-align:center; color:var(--slate-400);">جارٍ التحميل...</div>';

    try {
      const studentGroups = await api.getStudentGroups(studentId);
      const enrolledGroupIds = new Set(studentGroups.map(g => g.id));

      if (studentGroups.length === 0) {
        container.innerHTML = '<div style="padding:1.5rem; text-align:center; color:var(--slate-500); background:var(--slate-50); border-radius:var(--radius-md);">الطالب غير مقيد في أي مجموعة حالياً.</div>';
      } else {
        container.innerHTML = studentGroups.map(g => `
          <div style="display:flex; justify-content:space-between; align-items:center; padding:0.6rem 0.75rem; border-bottom:1px solid var(--border);">
            <div>
              <div style="font-weight:700; font-size:0.9rem;">${g.name}</div>
              <div style="font-size:0.75rem; color:var(--slate-500);">${g.grade_label} • ${g.schedule_details || 'بدون مواعيد'}</div>
            </div>
            <button type="button" class="btn btn-danger btn-sm unenroll-from-group-btn" data-group-id="${g.id}">
              إلغاء الاشتراك
            </button>
          </div>
        `).join('');

        // Bind unenroll buttons
        container.querySelectorAll('.unenroll-from-group-btn').forEach(btn => {
          btn.addEventListener('click', async () => {
            const grpId = btn.getAttribute('data-group-id');
            try {
              await api.unenrollStudent(grpId, studentId);
              showToast('تم إلغاء اشتراك الطالب من المجموعة.', 'success');
              state.students = await api.listStudents(state.studentFilters);
              await refreshStudentGroupsModal(studentId, studentName, studentGrade);
            } catch (err) {
              showToast(err.message, 'error');
            }
          });
        });
      }

      // Populate available groups (same grade level, not yet enrolled)
      const allGroups = await api.listGroups({ grade_level: studentGrade, is_active: 'true' });
      const available = allGroups.filter(g => !enrolledGroupIds.has(g.id));

      select.innerHTML = '<option value="">اختر المجموعة...</option>' + available.map(g => `
        <option value="${g.id}">${g.name} (${g.schedule_details || 'مواعيد عامة'})</option>
      `).join('');

      if (studentGroupsModal) studentGroupsModal.style.display = 'flex';
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const confirmEnrollGroupBtn = document.getElementById('confirm-enroll-group-btn');
  if (confirmEnrollGroupBtn) {
    confirmEnrollGroupBtn.addEventListener('click', async () => {
      const select = document.getElementById('enroll-group-select');
      const groupId = select ? select.value : '';
      if (!groupId || !state.activeModalStudent) {
        showToast('يرجى اختيار مجموعة أولاً.', 'error');
        return;
      }
      try {
        await api.enrollStudent(groupId, state.activeModalStudent.id);
        showToast('تم إلحاق الطالب بالمجموعة بنجاح!', 'success');
        state.students = await api.listStudents(state.studentFilters);
        await refreshStudentGroupsModal(
          state.activeModalStudent.id,
          state.activeModalStudent.name,
          state.activeModalStudent.grade
        );
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // --- Group Students Modal (Manage Enrolled Students of a Group) ---
  const groupStudentsModal = document.getElementById('group-students-modal');
  const closeGroupStudentsModalBtn = document.getElementById('close-group-students-modal');
  const closeGroupStudentsBtn = document.getElementById('close-group-students-btn');

  const closeGroupStudentsModal = () => {
    if (groupStudentsModal) groupStudentsModal.style.display = 'none';
    state.activeModalGroup = null;
  };

  if (closeGroupStudentsModalBtn) closeGroupStudentsModalBtn.addEventListener('click', closeGroupStudentsModal);
  if (closeGroupStudentsBtn) closeGroupStudentsBtn.addEventListener('click', closeGroupStudentsModal);
  if (groupStudentsModal) {
    groupStudentsModal.addEventListener('click', (e) => {
      if (e.target === groupStudentsModal) closeGroupStudentsModal();
    });
  }

  const refreshGroupStudentsModal = async (groupId, groupName, groupGrade) => {
    state.activeModalGroup = { id: groupId, name: groupName, grade: groupGrade };
    document.getElementById('group-students-title').textContent = `طلاب المجموعة: ${groupName}`;
    const container = document.getElementById('group-students-list-container');
    const select = document.getElementById('enroll-student-select');

    container.innerHTML = '<div style="padding:1rem; text-align:center; color:var(--slate-400);">جارٍ التحميل...</div>';

    try {
      const enrolledStudents = await api.getGroupStudents(groupId);
      const enrolledStudentIds = new Set(enrolledStudents.map(s => s.student_id));

      if (enrolledStudents.length === 0) {
        container.innerHTML = '<div style="padding:1.5rem; text-align:center; color:var(--slate-500); background:var(--slate-50); border-radius:var(--radius-md);">لا يوجد طلاب مسجلون في هذه المجموعة بعد.</div>';
      } else {
        container.innerHTML = enrolledStudents.map(s => `
          <div style="display:flex; justify-content:space-between; align-items:center; padding:0.6rem 0.75rem; border-bottom:1px solid var(--border);">
            <div>
              <div style="font-weight:700; font-size:0.9rem;">${s.full_name}</div>
              <div style="font-size:0.75rem; color:var(--slate-500); font-variant-numeric:tabular-nums;">هاتف: ${s.phone} • ولي الأمر: ${s.parent_phone || 'لا يوجد'}</div>
            </div>
            <button type="button" class="btn btn-danger btn-sm unenroll-student-from-grp-btn" data-student-id="${s.student_id}">
              إزالة من المجموعة
            </button>
          </div>
        `).join('');

        // Bind unenroll buttons
        container.querySelectorAll('.unenroll-student-from-grp-btn').forEach(btn => {
          btn.addEventListener('click', async () => {
            const stId = btn.getAttribute('data-student-id');
            try {
              await api.unenrollStudent(groupId, stId);
              showToast('تم إخراج الطالب من المجموعة.', 'success');
              state.groups = await api.listGroups(state.groupFilters);
              await refreshGroupStudentsModal(groupId, groupName, groupGrade);
            } catch (err) {
              showToast(err.message, 'error');
            }
          });
        });
      }

      // Populate available students (same grade level, not yet in group)
      const allGradeStudents = await api.listStudents({ grade_level: groupGrade, is_active: 'true' });
      const availableStudents = allGradeStudents.filter(s => !enrolledStudentIds.has(s.id));

      select.innerHTML = '<option value="">اختر طالباً لإضافته...</option>' + availableStudents.map(s => `
        <option value="${s.id}">${s.full_name} (${s.phone})</option>
      `).join('');

      if (groupStudentsModal) groupStudentsModal.style.display = 'flex';
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const confirmEnrollStudentBtn = document.getElementById('confirm-enroll-student-btn');
  if (confirmEnrollStudentBtn) {
    confirmEnrollStudentBtn.addEventListener('click', async () => {
      const select = document.getElementById('enroll-student-select');
      const studentId = select ? select.value : '';
      if (!studentId || !state.activeModalGroup) {
        showToast('يرجى اختيار طالب أولاً.', 'error');
        return;
      }
      try {
        await api.enrollStudent(state.activeModalGroup.id, studentId);
        showToast('تمت إضافة الطالب للمجموعة بنجاح!', 'success');
        state.groups = await api.listGroups(state.groupFilters);
        await refreshGroupStudentsModal(
          state.activeModalGroup.id,
          state.activeModalGroup.name,
          state.activeModalGroup.grade
        );
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // --- Attach Table & Grid Event Listeners ---

  // Edit student
  document.querySelectorAll('.edit-student-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      const student = state.students.find(s => s.id === id);
      if (student) openStudentEdit(student);
    });
  });

  // Delete student
  document.querySelectorAll('.delete-student-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      const name = btn.getAttribute('data-name');
      if (confirm(`هل أنت متأكد من حذف الطالب "${name}"؟\nسيتم إيقاف اشتراكاته في المجموعات مع الاحتفاظ بسجلاته.`)) {
        try {
          await api.deleteStudent(id);
          showToast(`تم حذف الطالب "${name}" بنجاح.`, 'success');
          state.students = await api.listStudents(state.studentFilters);
          navigate();
        } catch (err) {
          showToast(err.message, 'error');
        }
      }
    });
  });

  // Manage student's groups button
  document.querySelectorAll('.manage-student-groups-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      const name = btn.getAttribute('data-name');
      const grade = btn.getAttribute('data-grade');
      refreshStudentGroupsModal(id, name, grade);
    });
  });

  // Edit group
  document.querySelectorAll('.edit-group-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      const group = state.groups.find(g => g.id === id);
      if (group) openGroupEdit(group);
    });
  });

  // Delete group
  document.querySelectorAll('.delete-group-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      const name = btn.getAttribute('data-name');
      if (confirm(`هل أنت متأكد من حذف المجموعة "${name}"؟\nسيتم فك ارتباط طلاب المجموعة مع الحفاظ على سجلاتهم.`)) {
        try {
          await api.deleteGroup(id);
          showToast(`تم حذف المجموعة "${name}" بنجاح.`, 'success');
          state.groups = await api.listGroups(state.groupFilters);
          navigate();
        } catch (err) {
          showToast(err.message, 'error');
        }
      }
    });
  });

  // --- Barcode Distribution Events ---
  document.querySelectorAll('.open-group-distribution-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const gid = btn.getAttribute('data-id');
      if (gid) {
        state.selectedDistributionGroupId = gid;
        state.activeAcademicTab = 'distribution';
        try {
          state.distributionOverview = await api.getGroupDistributionOverview(gid);
        } catch (e) {
          state.distributionOverview = null;
        }
        navigate();
      }
    });
  });

  const distGroupSelect = document.getElementById('dist-group-select');
  if (distGroupSelect) {
    distGroupSelect.addEventListener('change', async () => {
      const gid = distGroupSelect.value;
      state.selectedDistributionGroupId = gid;
      state.selectedDistributionStudentIds = [];
      try {
        state.distributionOverview = await api.getGroupDistributionOverview(gid);
      } catch (e) {
        state.distributionOverview = null;
        showToast(e.message, 'error');
      }
      navigate();
    });
  }

  document.querySelectorAll('.dist-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      state.distributionStudentFilter = btn.getAttribute('data-filter') || 'all';
      const container = document.getElementById('app');
      if (container && state.activeRoute === 'students' && state.activeAcademicTab === 'distribution') {
        container.innerHTML = renderAppShell(renderAcademicView(), state.activeRoute);
        bindShellEvents();
        bindAcademicEvents(queryParams);
      }
    });
  });

  const masterCb = document.getElementById('dist-master-checkbox');
  const studentCbs = document.querySelectorAll('.dist-student-checkbox');
  const updateSelectedExportBtn = () => {
    const btn = document.getElementById('export-selected-cards-pdf-btn');
    if (btn) {
      btn.disabled = state.selectedDistributionStudentIds.length === 0;
      btn.textContent = `📥 تصدير المحددة (${state.selectedDistributionStudentIds.length})`;
    }
  };

  if (masterCb) {
    masterCb.addEventListener('change', () => {
      const isChecked = masterCb.checked;
      studentCbs.forEach(cb => {
        cb.checked = isChecked;
        const sid = cb.getAttribute('data-id');
        if (isChecked) {
          if (!state.selectedDistributionStudentIds.includes(sid)) {
            state.selectedDistributionStudentIds.push(sid);
          }
        }
      });
      if (!isChecked) {
        state.selectedDistributionStudentIds = [];
      }
      updateSelectedExportBtn();
    });
  }

  studentCbs.forEach(cb => {
    cb.addEventListener('change', () => {
      const sid = cb.getAttribute('data-id');
      if (cb.checked) {
        if (!state.selectedDistributionStudentIds.includes(sid)) {
          state.selectedDistributionStudentIds.push(sid);
        }
      } else {
        state.selectedDistributionStudentIds = state.selectedDistributionStudentIds.filter(id => id !== sid);
      }
      if (masterCb) {
        masterCb.checked = studentCbs.length > 0 && state.selectedDistributionStudentIds.length === studentCbs.length;
      }
      updateSelectedExportBtn();
    });
  });

  const exportGroupBtn = document.getElementById('export-group-cards-pdf-btn');
  if (exportGroupBtn) {
    exportGroupBtn.addEventListener('click', async () => {
      const gid = state.selectedDistributionGroupId || (state.groups.length > 0 ? state.groups[0].id : null);
      if (!gid) return;
      const group = state.groups.find(g => g.id === gid);
      const origHtml = exportGroupBtn.innerHTML;
      exportGroupBtn.disabled = true;
      exportGroupBtn.innerHTML = '<span class="spinner-sm"></span> جاري تجميع ملف A4...';
      try {
        await api.exportGroupCardsPdf(gid, group ? group.name : '');
        showToast('تم تصدير بطاقات المجموعة بنجاح وتحديث تاريخ التصدير.', 'success');
        state.distributionOverview = await api.getGroupDistributionOverview(gid);
        navigate();
      } catch (err) {
        showToast(err.message || 'تعذر تصدير بطاقات المجموعة.', 'error');
      } finally {
        exportGroupBtn.disabled = false;
        exportGroupBtn.innerHTML = origHtml;
      }
    });
  }

  const exportSelectedBtn = document.getElementById('export-selected-cards-pdf-btn');
  if (exportSelectedBtn) {
    exportSelectedBtn.addEventListener('click', async () => {
      if (state.selectedDistributionStudentIds.length === 0) return;
      const gid = state.selectedDistributionGroupId;
      const origHtml = exportSelectedBtn.innerHTML;
      exportSelectedBtn.disabled = true;
      exportSelectedBtn.innerHTML = '<span class="spinner-sm"></span> جاري التجميع...';
      try {
        await api.exportMultiStudentCardsPdf(state.selectedDistributionStudentIds, gid);
        showToast(`تم تصدير ${state.selectedDistributionStudentIds.length} بطاقة بنجاح.`, 'success');
        if (gid) {
          state.distributionOverview = await api.getGroupDistributionOverview(gid);
          navigate();
        }
      } catch (err) {
        showToast(err.message || 'تعذر تصدير البطاقات المحددة.', 'error');
      } finally {
        exportSelectedBtn.disabled = false;
        exportSelectedBtn.innerHTML = origHtml;
      }
    });
  }

  const cardModal = document.getElementById('student-barcode-card-modal');
  const closeCardModalBtn = document.getElementById('close-barcode-card-modal');
  const cardModalBody = document.getElementById('barcode-card-modal-body');
  const downloadCardModalBtn = document.getElementById('download-card-modal-btn');
  const shareCardModalBtn = document.getElementById('share-card-modal-btn');
  const confirmCardDeliveryBtn = document.getElementById('confirm-card-delivery-btn');

  const openStudentCardModal = async (studentId, studentName = '', groupId = null) => {
    if (!cardModal || !cardModalBody) return;
    cardModalBody.innerHTML = '<div style="text-align:center; padding:2rem;"><span class="spinner-sm"></span> جاري تحميل بيانات البطاقة...</div>';
    cardModal.style.display = 'flex';
    try {
      const card = await api.getStudentCard(studentId, groupId);
      state.activeStudentCard = card;

      let statusBadge = '<span class="badge badge-secondary">بانتظار التسليم</span>';
      if (card.distribution_status === 'confirmed_sent') {
        statusBadge = `<span class="badge badge-success">✔ تم تأكيد التسليم (${escapeHtml(card.confirmed_by_name || 'المعلم')})</span>`;
      } else if (card.distribution_status === 'share_opened') {
        statusBadge = '<span class="badge badge-primary">📤 فُتحت المشاركة / تم التحميل</span>';
      }

      cardModalBody.innerHTML = `
        <div style="border:1.5px solid var(--border); border-radius:10px; overflow:hidden; background:#fff; box-shadow:0 2px 8px rgba(0,0,0,0.06);">
          <div style="background:var(--primary); color:#fff; padding:0.75rem 1rem; display:flex; justify-content:space-between; align-items:center;">
            <div style="font-size:0.85rem; font-weight:700;">TeacherSystem | بطاقة الطالب</div>
            <div style="font-size:0.75rem; opacity:0.9;">${escapeHtml(card.grade_label)}</div>
          </div>
          <div style="padding:1rem; text-align:center;">
            <div style="font-size:1.15rem; font-weight:800; color:var(--slate-900); margin-bottom:0.25rem;">
              ${escapeHtml(card.full_name)}
            </div>
            <div style="font-size:0.8rem; color:var(--slate-500); margin-bottom:0.75rem;">
              ${escapeHtml(card.primary_group_name || 'طالب مسجل')}
            </div>
            <div style="background:#fff; padding:0.5rem; display:flex; justify-content:center; align-items:center; overflow-x:auto;">
              ${card.barcode_svg}
            </div>
            <div style="font-family:monospace; font-size:0.75rem; color:var(--slate-400); margin-top:0.25rem; direction:ltr;">
              ${escapeHtml(card.barcode_value)}
            </div>
          </div>
          <div style="background:var(--slate-50); padding:0.5rem 1rem; border-top:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; font-size:0.8rem;">
            <span style="color:var(--slate-500);">حالة التسليم:</span>
            ${statusBadge}
          </div>
        </div>
      `;

      if (downloadCardModalBtn) {
        downloadCardModalBtn.onclick = async () => {
          await api.downloadStudentCardPdf(studentId, card.full_name, groupId);
          showToast('تم تحميل بطاقة الطالب بنجاح.', 'success');
        };
      }
      if (shareCardModalBtn) {
        shareCardModalBtn.onclick = async () => {
          await shareStudentCard(studentId, card.full_name, groupId);
        };
      }
      if (confirmCardDeliveryBtn) {
        const isConfirmed = card.distribution_status === 'confirmed_sent';
        confirmCardDeliveryBtn.textContent = isConfirmed ? 'إلغاء التأكيد' : '✔ تأكيد التسليم';
        confirmCardDeliveryBtn.onclick = async () => {
          const newStatus = isConfirmed ? 'not_sent' : 'confirmed_sent';
          await api.updateStudentDistributionStatus(studentId, { status: newStatus, group_id: groupId });
          showToast(isConfirmed ? 'تمت إعادة تعيين حالة البطاقة.' : 'تم تأكيد تسليم البطاقة بنجاح.', 'success');
          openStudentCardModal(studentId, card.full_name, groupId);
          if (state.selectedDistributionGroupId) {
            state.distributionOverview = await api.getGroupDistributionOverview(state.selectedDistributionGroupId);
          }
        };
      }
    } catch (err) {
      cardModalBody.innerHTML = `<div style="color:#DC2626; padding:1rem; text-align:center;">تعذر تحميل البطاقة: ${err.message}</div>`;
    }
  };

  if (closeCardModalBtn && cardModal) {
    closeCardModalBtn.addEventListener('click', () => {
      cardModal.style.display = 'none';
      if (state.activeAcademicTab === 'distribution' && state.selectedDistributionGroupId) {
        navigate();
      }
    });
  }

  document.querySelectorAll('.view-student-barcode-card-btn, .view-single-dist-card-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const sid = btn.getAttribute('data-id');
      const sname = btn.getAttribute('data-name');
      const gid = btn.getAttribute('data-group-id') || null;
      openStudentCardModal(sid, sname, gid);
    });
  });

  document.querySelectorAll('.share-single-dist-card-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const sid = btn.getAttribute('data-id');
      const sname = btn.getAttribute('data-name');
      const gid = btn.getAttribute('data-group-id') || null;
      await shareStudentCard(sid, sname, gid);
      if (state.selectedDistributionGroupId) {
        state.distributionOverview = await api.getGroupDistributionOverview(state.selectedDistributionGroupId);
        navigate();
      }
    });
  });

  document.querySelectorAll('.confirm-single-dist-delivery-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const sid = btn.getAttribute('data-id');
      const sname = btn.getAttribute('data-name');
      const gid = btn.getAttribute('data-group-id') || null;
      const current = btn.getAttribute('data-current');
      const newStatus = current === 'confirmed_sent' ? 'not_sent' : 'confirmed_sent';
      try {
        await api.updateStudentDistributionStatus(sid, { status: newStatus, group_id: gid });
        showToast(newStatus === 'confirmed_sent' ? `تم تأكيد تسليم بطاقة ${sname}` : `تم إلغاء تأكيد ${sname}`, 'success');
        if (state.selectedDistributionGroupId) {
          state.distributionOverview = await api.getGroupDistributionOverview(state.selectedDistributionGroupId);
          navigate();
        }
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  // Action query parameter handling
  if (queryParams && queryParams.get('action') === 'add_student') {
    openStudentAdd();
  } else if (queryParams && queryParams.get('action') === 'add_group') {
    openGroupAdd();
  }
}

function bindAttendanceEvents(queryParams) {
  // If activeSessionId is set, bind attendance taking sheet events
  if (state.activeSessionId && state.activeSessionSheet) {
    bindAttendanceSheetEvents();
    return;
  }

  // --- Sessions List Events ---
  const filterBtn = document.getElementById('filter-sessions-btn');
  const resetBtn = document.getElementById('reset-sessions-btn');
  const groupSelect = document.getElementById('filter-session-group');
  const dateInput = document.getElementById('filter-session-date');
  const statusSelect = document.getElementById('filter-session-status');

  if (filterBtn) {
    filterBtn.addEventListener('click', async () => {
      state.sessionFilters.group_id = groupSelect ? groupSelect.value : '';
      state.sessionFilters.session_date = dateInput ? dateInput.value : '';
      state.sessionFilters.status = statusSelect ? statusSelect.value : '';
      navigate();
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener('click', async () => {
      state.sessionFilters = { group_id: '', session_date: '', status: '' };
      navigate();
    });
  }

  // Add / Edit Session Modal
  const modal = document.getElementById('session-modal');
  const modalTitle = document.getElementById('session-modal-title');
  const openAddBtn = document.getElementById('open-add-session-modal');
  const openEmptyBtn = document.getElementById('open-add-session-empty');
  const closeBtn = document.getElementById('close-session-modal');
  const cancelBtn = document.getElementById('cancel-session-btn');
  const form = document.getElementById('session-form');
  const statusContainer = document.getElementById('sess-status-container');
  const today = new Date().toISOString().split('T')[0];

  const openAddSessionModal = () => {
    state.editingSessionId = null;
    if (form) form.reset();
    if (modalTitle) modalTitle.textContent = 'جدولة حصة جديدة';
    const dInput = document.getElementById('sess-date');
    if (dInput) dInput.value = today;
    const tInput = document.getElementById('sess-start-time');
    if (tInput) tInput.value = '16:00';
    if (statusContainer) statusContainer.style.display = 'none';
    if (modal) modal.style.display = 'flex';
  };

  const openEditSessionModal = (s) => {
    state.editingSessionId = s.id;
    if (form) form.reset();
    if (modalTitle) modalTitle.textContent = `تعديل بيانات الحصة: ${s.group_name}`;
    document.getElementById('sess-group-id').value = s.group_id;
    document.getElementById('sess-date').value = s.session_date;
    document.getElementById('sess-start-time').value = s.start_time;
    if (document.getElementById('sess-end-time')) document.getElementById('sess-end-time').value = s.end_time || '';
    if (document.getElementById('sess-location')) document.getElementById('sess-location').value = s.location || '';
    if (document.getElementById('sess-notes')) document.getElementById('sess-notes').value = s.notes || '';
    if (document.getElementById('sess-status')) document.getElementById('sess-status').value = s.status;
    if (statusContainer) statusContainer.style.display = 'block';
    if (modal) modal.style.display = 'flex';
  };

  const closeModal = () => {
    if (modal) modal.style.display = 'none';
    state.editingSessionId = null;
  };

  if (openAddBtn) openAddBtn.addEventListener('click', openAddSessionModal);
  if (openEmptyBtn) openEmptyBtn.addEventListener('click', openAddSessionModal);
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const saveBtn = document.getElementById('save-session-btn');
      saveBtn.disabled = true;
      saveBtn.textContent = 'جارٍ الحفظ...';

      const payload = {
        group_id: document.getElementById('sess-group-id').value,
        session_date: document.getElementById('sess-date').value,
        start_time: document.getElementById('sess-start-time').value,
        end_time: document.getElementById('sess-end-time').value || null,
        location: document.getElementById('sess-location').value.trim() || null,
        notes: document.getElementById('sess-notes').value.trim() || null,
      };

      try {
        if (state.editingSessionId) {
          payload.status = document.getElementById('sess-status').value;
          await api.updateSession(state.editingSessionId, payload);
          showToast('تم تحديث بيانات الحصة بنجاح!', 'success');
        } else {
          await api.createSession(payload);
          showToast('تمت جدولة الحصة بنجاح!', 'success');
        }
        closeModal();
        navigate();
      } catch (err) {
        showToast(err.message, 'error');
        saveBtn.disabled = false;
        saveBtn.textContent = 'حفظ الحصة';
      }
    });
  }

  // Open Attendance Sheet
  document.querySelectorAll('.open-session-sheet-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      state.activeSessionId = id;
      navigate();
    });
  });

  // Edit Session
  document.querySelectorAll('.edit-session-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      const s = state.sessions.find(x => x.id === id);
      if (s) openEditSessionModal(s);
    });
  });

  // Cancel Session
  document.querySelectorAll('.cancel-session-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      const date = btn.getAttribute('data-date');
      if (confirm(`هل أنت متأكد من إلغاء حصة يوم ${date}؟`)) {
        try {
          await api.cancelSession(id);
          showToast('تم إلغاء الحصة بنجاح.', 'success');
          navigate();
        } catch (err) {
          showToast(err.message, 'error');
        }
      }
    });
  });

  // Group summary report trigger
  bindGroupSummaryModal();

  // Action query parameter handling
  if (queryParams && queryParams.get('action') === 'add_session') {
    openAddSessionModal();
  }
}

function bindAttendanceSheetEvents() {
  const backBtn = document.getElementById('back-to-sessions-list');
  if (backBtn) {
    backBtn.addEventListener('click', () => {
      state.activeSessionId = null;
      state.activeSessionSheet = null;
      navigate();
    });
  }

  // Audio feedback toggle
  const audioToggle = document.getElementById('toggle-audio-feedback');
  if (audioToggle) {
    audioToggle.addEventListener('change', (e) => {
      state.audioFeedbackEnabled = e.target.checked;
    });
  }

  // Barcode input and USB Scanner handling
  const barcodeInput = document.getElementById('barcode-input');
  const submitBarcodeBtn = document.getElementById('submit-barcode-btn');
  const feedbackEl = document.getElementById('scanner-feedback');

  if (barcodeInput) {
    setTimeout(() => barcodeInput.focus(), 150);
  }

  const handleScan = async () => {
    if (!barcodeInput) return;
    const barcode = barcodeInput.value.trim();
    if (!barcode) return;

    try {
      const res = await api.scanBarcode(state.activeSessionId, barcode);
      if (res.action === 'already_present') {
        playFeedbackTone('warning');
        if (feedbackEl) {
          feedbackEl.className = 'scanner-feedback active scanner-feedback-warning';
          feedbackEl.innerHTML = `⚠️ ${res.message}`;
        }
      } else {
        playFeedbackTone('success');
        if (feedbackEl) {
          feedbackEl.className = 'scanner-feedback active scanner-feedback-success';
          feedbackEl.innerHTML = `✅ ${res.message}`;
        }
      }

      // Update student row in DOM
      const row = document.getElementById(`row-student-${res.student.id}`);
      if (row) {
        row.classList.remove('row-highlight');
        void row.offsetWidth; // Trigger reflow to restart animation
        row.classList.add('row-highlight');
        row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        const btnGroup = row.querySelector('.status-btn-group');
        if (btnGroup) {
          btnGroup.querySelectorAll('.status-btn').forEach(b => {
            b.classList.remove('active-present', 'active-late', 'active-absent', 'active-excused');
            if (b.getAttribute('data-status') === 'present') {
              b.classList.add('active-present');
            }
          });
        }
        const timeCell = row.querySelector('.student-att-time');
        if (timeCell) {
          timeCell.textContent = res.timestamp;
        }
      }

      // Refresh sheet stats
      refreshSheetCounters();
    } catch (err) {
      playFeedbackTone('error');
      if (feedbackEl) {
        feedbackEl.className = 'scanner-feedback active scanner-feedback-error';
        feedbackEl.innerHTML = `❌ ${err.message}`;
      }
    } finally {
      barcodeInput.value = '';
      barcodeInput.focus();
    }
  };

  if (barcodeInput) {
    barcodeInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleScan();
      }
    });
  }

  if (submitBarcodeBtn) {
    submitBarcodeBtn.addEventListener('click', handleScan);
  }

  // Single student status button click
  document.querySelectorAll('.mark-status-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const group = btn.closest('.status-btn-group');
      if (!group) return;
      const studentId = group.getAttribute('data-student-id');
      const status = btn.getAttribute('data-status');
      const row = document.getElementById(`row-student-${studentId}`);
      const noteInput = row ? row.querySelector('.student-att-note') : null;
      const notes = noteInput ? noteInput.value.trim() : null;

      try {
        await api.markAttendance(state.activeSessionId, {
          student_id: studentId,
          status: status,
          notes: notes
        });

        // Update active class
        group.querySelectorAll('.status-btn').forEach(b => {
          b.classList.remove('active-present', 'active-late', 'active-absent', 'active-excused');
        });
        btn.classList.add(`active-${status}`);

        const timeCell = row ? row.querySelector('.student-att-time') : null;
        if (timeCell) {
          timeCell.textContent = new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });
        }

        refreshSheetCounters();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  // Student notes update
  document.querySelectorAll('.student-att-note').forEach(input => {
    input.addEventListener('change', async () => {
      const studentId = input.getAttribute('data-student-id');
      const row = document.getElementById(`row-student-${studentId}`);
      const activeBtn = row ? row.querySelector('.status-btn[class*="active-"]') : null;
      if (!activeBtn) return; // Don't record note without status
      const status = activeBtn.getAttribute('data-status');

      try {
        await api.markAttendance(state.activeSessionId, {
          student_id: studentId,
          status: status,
          notes: input.value.trim()
        });
        showToast('تم حفظ ملاحظة الحصة.', 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  // Bulk mark remaining absent
  const bulkAbsentBtn = document.getElementById('bulk-mark-remaining-absent');
  if (bulkAbsentBtn) {
    bulkAbsentBtn.addEventListener('click', async () => {
      if (!state.activeSessionSheet) return;
      // Identify rows without active status
      const unrecordedStudents = [];
      document.querySelectorAll('#attendance-sheet-table tbody tr').forEach(row => {
        const hasActive = row.querySelector('.status-btn[class*="active-"]');
        if (!hasActive) {
          const sId = row.id.replace('row-student-', '');
          unrecordedStudents.push(sId);
        }
      });

      if (unrecordedStudents.length === 0) {
        showToast('تم رصد حالة جميع الطلاب المقيدين بالفعل.', 'info');
        return;
      }

      if (confirm(`هل أنت متأكد من تسجيل غياب لكافة الطلاب المتبقين وعددهم (${unrecordedStudents.length})؟`)) {
        try {
          const records = unrecordedStudents.map(id => ({ student_id: id, status: 'absent' }));
          await api.bulkMarkAttendance(state.activeSessionId, records);
          showToast(`تم تسجيل غياب لـ ${records.length} طالب بنجاح!`, 'success');
          state.activeSessionSheet = await api.getSessionAttendance(state.activeSessionId);
          navigate();
        } catch (err) {
          showToast(err.message, 'error');
        }
      }
    });
  }

  // Bulk mark all present
  const bulkPresentBtn = document.getElementById('bulk-mark-all-present');
  if (bulkPresentBtn) {
    bulkPresentBtn.addEventListener('click', async () => {
      if (!state.activeSessionSheet || !state.activeSessionSheet.students.length) return;
      if (confirm(`هل أنت متأكد من تسجيل حضور لجميع طلاب المجموعة (${state.activeSessionSheet.students.length} طالب)؟`)) {
        try {
          const records = state.activeSessionSheet.students.map(s => ({ student_id: s.student_id, status: 'present' }));
          await api.bulkMarkAttendance(state.activeSessionId, records);
          showToast('تم تسجيل الحضور للجميع بنجاح!', 'success');
          state.activeSessionSheet = await api.getSessionAttendance(state.activeSessionId);
          navigate();
        } catch (err) {
          showToast(err.message, 'error');
        }
      }
    });
  }

  // Sheet in-page student search filter
  const sheetSearchInput = document.getElementById('sheet-student-search');
  if (sheetSearchInput) {
    sheetSearchInput.addEventListener('input', () => {
      const q = sheetSearchInput.value.toLowerCase().trim();
      document.querySelectorAll('#attendance-sheet-table tbody tr').forEach(row => {
        const name = row.getAttribute('data-name') || '';
        const phone = row.getAttribute('data-phone') || '';
        const parentPhone = row.getAttribute('data-parent-phone') || '';
        if (!q || name.includes(q) || phone.includes(q) || parentPhone.includes(q)) {
          row.style.display = '';
        } else {
          row.style.display = 'none';
        }
      });
    });
  }

  // Student history modal trigger
  bindStudentHistoryModal();

  // Group summary modal trigger
  bindGroupSummaryModal();
}

async function refreshSheetCounters() {
  if (!state.activeSessionId) return;
  try {
    const updated = await api.getSessionAttendance(state.activeSessionId);
    state.activeSessionSheet = updated;
    const stats = updated.stats;

    const elP = document.getElementById('counter-present');
    const elL = document.getElementById('counter-late');
    const elA = document.getElementById('counter-absent');
    const elE = document.getElementById('counter-excused');
    const elU = document.getElementById('counter-unrecorded');

    if (elP) elP.textContent = stats.present_count;
    if (elL) elL.textContent = stats.late_count;
    if (elA) elA.textContent = stats.absent_count;
    if (elE) elE.textContent = stats.excused_count;
    if (elU) elU.textContent = stats.unrecorded_count;

    const progP = document.getElementById('prog-present');
    const progL = document.getElementById('prog-late');
    const progA = document.getElementById('prog-absent');
    const progE = document.getElementById('prog-excused');

    if (stats.total_enrolled > 0) {
      if (progP) progP.style.width = `${(stats.present_count / stats.total_enrolled) * 100}%`;
      if (progL) progL.style.width = `${(stats.late_count / stats.total_enrolled) * 100}%`;
      if (progA) progA.style.width = `${(stats.absent_count / stats.total_enrolled) * 100}%`;
      if (progE) progE.style.width = `${(stats.excused_count / stats.total_enrolled) * 100}%`;
    }
  } catch (e) {
    console.error('Failed to refresh stats:', e);
  }
}

function bindStudentHistoryModal() {
  const modal = document.getElementById('student-history-modal');
  const modalTitle = document.getElementById('student-history-modal-title');
  const modalBody = document.getElementById('student-history-modal-body');
  const closeBtn = document.getElementById('close-student-history-modal');

  const closeModal = () => {
    if (modal) modal.style.display = 'none';
  };

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  document.querySelectorAll('.view-student-history-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const sId = btn.getAttribute('data-student-id');
      if (!sId) return;

      try {
        const hist = await api.getStudentAttendanceHistory(sId);
        if (modalTitle) modalTitle.textContent = `سجل حضور الطالب: ${hist.student_name}`;
        if (modalBody) {
          modalBody.innerHTML = `
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:0.75rem; margin-bottom:1.25rem;">
              <div class="session-stat-box">
                <span class="session-stat-label">نسبة الانضباط</span>
                <span class="session-stat-val" style="color:var(--primary);">${hist.attendance_rate}%</span>
              </div>
              <div class="session-stat-box">
                <span class="session-stat-label">إجمالي الحصص</span>
                <span class="session-stat-val" style="color:var(--slate-800);">${hist.total_sessions}</span>
              </div>
              <div class="session-stat-box">
                <span class="session-stat-label">حاضر</span>
                <span class="session-stat-val" style="color:#059669;">${hist.present_count}</span>
              </div>
              <div class="session-stat-box">
                <span class="session-stat-label">متأخر</span>
                <span class="session-stat-val" style="color:#D97706;">${hist.late_count}</span>
              </div>
              <div class="session-stat-box">
                <span class="session-stat-label">غياب</span>
                <span class="session-stat-val" style="color:#DC2626;">${hist.absent_count}</span>
              </div>
              <div class="session-stat-box">
                <span class="session-stat-label">بعذر</span>
                <span class="session-stat-val" style="color:#2563EB;">${hist.excused_count}</span>
              </div>
            </div>

            <div class="table-container" style="max-height:350px; overflow-y:auto;">
              ${hist.history.length === 0 ? `
                <div style="padding:2rem; text-align:center; color:var(--slate-500);">لا توجد حصص مسجلة لهذا الطالب حتى الآن.</div>
              ` : `
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>التاريخ</th>
                      <th>المجموعة</th>
                      <th>الحالة</th>
                      <th>ملاحظات</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${hist.history.map(h => {
                      const badgeClass = h.status === 'present' ? 'badge-success' : (h.status === 'late' ? 'badge-secondary' : (h.status === 'absent' ? 'badge-danger' : 'badge-primary'));
                      return `
                        <tr>
                          <td>
                            <div style="font-weight:700;">${h.session_date}</div>
                            <div style="font-size:0.75rem; color:var(--slate-500);">${h.start_time}</div>
                          </td>
                          <td>${h.group_name}</td>
                          <td><span class="badge ${badgeClass}">${h.status_label}</span></td>
                          <td style="font-size:0.8rem; color:var(--slate-600);">${h.notes || '-'}</td>
                        </tr>
                      `;
                    }).join('')}
                  </tbody>
                </table>
              `}
            </div>
          `;
        }
        if (modal) modal.style.display = 'flex';
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });
}

function bindGroupSummaryModal() {
  const modal = document.getElementById('group-summary-modal');
  const modalTitle = document.getElementById('group-summary-modal-title');
  const modalBody = document.getElementById('group-summary-modal-body');
  const closeBtn = document.getElementById('close-group-summary-modal');

  const closeModal = () => {
    if (modal) modal.style.display = 'none';
  };

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  document.querySelectorAll('.view-group-summary-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const gId = btn.getAttribute('data-group-id');
      if (!gId) return;

      try {
        const sum = await api.getGroupAttendanceSummary(gId);
        if (modalTitle) modalTitle.textContent = `تقرير حضور المجموعة: ${sum.group_name} (${sum.grade_label})`;
        if (modalBody) {
          modalBody.innerHTML = `
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:0.75rem; margin-bottom:1.25rem;">
              <div class="session-stat-box">
                <span class="session-stat-label">متوسط نسبة الحضور</span>
                <span class="session-stat-val" style="color:var(--primary);">${sum.average_attendance_rate}%</span>
              </div>
              <div class="session-stat-box">
                <span class="session-stat-label">عدد الطلاب المقيدين</span>
                <span class="session-stat-val" style="color:var(--slate-800);">${sum.total_students}</span>
              </div>
              <div class="session-stat-box">
                <span class="session-stat-label">إجمالي الحصص المنعقدة</span>
                <span class="session-stat-val" style="color:var(--slate-800);">${sum.total_sessions}</span>
              </div>
            </div>

            <div class="table-container" style="max-height:350px; overflow-y:auto;">
              <div class="table-header-bar">
                <div style="font-weight:700;">سجل الحصص الأخيرة</div>
              </div>
              ${sum.recent_sessions.length === 0 ? `
                <div style="padding:2rem; text-align:center; color:var(--slate-500);">لا توجد حصص مسجلة لهذه المجموعة.</div>
              ` : `
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>التاريخ</th>
                      <th>المكان</th>
                      <th>الحالة</th>
                      <th>الحضور</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${sum.recent_sessions.map(s => {
                      const stats = s.stats || { total_enrolled: 0, present_count: 0, late_count: 0 };
                      const attended = stats.present_count + stats.late_count;
                      const rate = stats.total_enrolled > 0 ? Math.round((attended / stats.total_enrolled) * 100) : 0;
                      return `
                        <tr>
                          <td>
                            <div style="font-weight:700;">${s.session_date}</div>
                            <div style="font-size:0.75rem; color:var(--slate-500);">${s.start_time}</div>
                          </td>
                          <td>${s.location || 'غير محدد'}</td>
                          <td><span class="badge ${s.status === 'completed' ? 'badge-success' : 'badge-primary'}">${s.status_label}</span></td>
                          <td>
                            <span style="font-weight:700; color:#059669;">${attended} / ${stats.total_enrolled}</span>
                            <span style="font-size:0.75rem; color:var(--slate-500);">(${rate}%)</span>
                          </td>
                        </tr>
                      `;
                    }).join('')}
                  </tbody>
                </table>
              `}
            </div>
          `;
        }
        if (modal) modal.style.display = 'flex';
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });
}


// --- Exams & Grades Event Binders ---
function bindExamEvents(queryParams) {
  if (state.activeExamId && state.activeExamSheet) {
    bindExamSheetEvents(state.activeExamSheet);
    return;
  }

  // --- Exams List Events ---
  const filterBtn = document.getElementById('filter-exams-btn');
  const resetBtn = document.getElementById('reset-exams-btn');
  const groupSelect = document.getElementById('filter-exam-group');
  const dateInput = document.getElementById('filter-exam-date');
  const statusSelect = document.getElementById('filter-exam-status');

  if (filterBtn) {
    filterBtn.addEventListener('click', async () => {
      state.examFilters = {
        group_id: groupSelect ? groupSelect.value : '',
        exam_date: dateInput ? dateInput.value : '',
        status: statusSelect ? statusSelect.value : ''
      };
      await navigate();
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener('click', async () => {
      state.examFilters = { group_id: '', exam_date: '', status: '' };
      await navigate();
    });
  }

  // Open Exam Sheet
  document.querySelectorAll('.open-exam-sheet-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      if (id) {
        state.activeExamId = id;
        await navigate();
      }
    });
  });

  // Modal: Add / Edit Exam
  const examModal = document.getElementById('exam-modal');
  const openAddBtn = document.getElementById('open-add-exam-modal');
  const openEmptyBtn = document.getElementById('open-add-exam-empty');
  const closeExamModalBtn = document.getElementById('close-exam-modal');
  const cancelExamModalBtn = document.getElementById('cancel-exam-modal-btn');
  const examForm = document.getElementById('exam-form');
  const examModalTitle = document.getElementById('exam-modal-title');
  const groupContainer = document.getElementById('exam-group-container');
  const statusContainer = document.getElementById('exam-status-container');

  const openModalForNew = () => {
    state.editingExamId = null;
    if (examModalTitle) examModalTitle.textContent = 'إنشاء امتحان جديد';
    if (groupContainer) groupContainer.style.display = 'block';
    if (statusContainer) statusContainer.style.display = 'none';
    if (examForm) examForm.reset();
    const today = new Date().toISOString().split('T')[0];
    const dateField = document.getElementById('exam-date');
    if (dateField) dateField.value = today;
    const maxScoreField = document.getElementById('exam-max-score');
    if (maxScoreField) maxScoreField.value = '50';
    const passingScoreField = document.getElementById('exam-passing-score');
    if (passingScoreField) passingScoreField.value = '25';
    if (examModal) examModal.style.display = 'flex';
  };

  const closeExamModal = () => {
    if (examModal) examModal.style.display = 'none';
    state.editingExamId = null;
  };

  if (openAddBtn) openAddBtn.addEventListener('click', openModalForNew);
  if (openEmptyBtn) openEmptyBtn.addEventListener('click', openModalForNew);
  if (closeExamModalBtn) closeExamModalBtn.addEventListener('click', closeExamModal);
  if (cancelExamModalBtn) cancelExamModalBtn.addEventListener('click', closeExamModal);

  if (examModal) {
    examModal.addEventListener('click', (e) => {
      if (e.target === examModal) closeExamModal();
    });
  }

  // Save Exam Form Submit
  if (examForm) {
    examForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const groupId = document.getElementById('exam-group-id').value;
      const title = document.getElementById('exam-title').value.trim();
      const examDate = document.getElementById('exam-date').value;
      const maxScore = parseFloat(document.getElementById('exam-max-score').value);
      const passingScore = parseFloat(document.getElementById('exam-passing-score').value);
      const description = document.getElementById('exam-description').value.trim();
      const status = document.getElementById('exam-status') ? document.getElementById('exam-status').value : 'scheduled';

      if (!title) {
        showToast('يرجى إدخال عنوان الامتحان', 'error');
        return;
      }
      if (isNaN(maxScore) || maxScore <= 0) {
        showToast('الدرجة العظمى يجب أن تكون أكبر من الصفر', 'error');
        return;
      }
      if (isNaN(passingScore) || passingScore < 0 || passingScore > maxScore) {
        showToast('درجة النجاح يجب أن تكون بين الصفر والدرجة العظمى', 'error');
        return;
      }

      const saveBtn = document.getElementById('save-exam-btn');
      if (saveBtn) saveBtn.disabled = true;

      try {
        if (state.editingExamId) {
          await api.updateExam(state.editingExamId, {
            title,
            exam_date: examDate,
            max_score: maxScore,
            passing_score: passingScore,
            description: description || null,
            status
          });
          showToast('تم تحديث بيانات الامتحان بنجاح');
        } else {
          if (!groupId) {
            showToast('يرجى اختيار المجموعة الدراسية', 'error');
            if (saveBtn) saveBtn.disabled = false;
            return;
          }
          await api.createExam({
            group_id: groupId,
            title,
            exam_date: examDate,
            max_score: maxScore,
            passing_score: passingScore,
            description: description || null,
            status: 'scheduled'
          });
          showToast('تم إنشاء وجدولة الامتحان بنجاح');
        }
        closeExamModal();
        await navigate();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        if (saveBtn) saveBtn.disabled = false;
      }
    });
  }

  // Edit Exam Buttons
  document.querySelectorAll('.edit-exam-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      if (!id) return;

      try {
        const ex = await api.getExam(id);
        state.editingExamId = id;
        if (examModalTitle) examModalTitle.textContent = 'تعديل بيانات الامتحان';
        if (groupContainer) groupContainer.style.display = 'none';
        if (statusContainer) statusContainer.style.display = 'block';

        const titleField = document.getElementById('exam-title');
        const dateField = document.getElementById('exam-date');
        const maxScoreField = document.getElementById('exam-max-score');
        const passingScoreField = document.getElementById('exam-passing-score');
        const descField = document.getElementById('exam-description');
        const statusField = document.getElementById('exam-status');

        if (titleField) titleField.value = ex.title;
        if (dateField) dateField.value = ex.exam_date;
        if (maxScoreField) maxScoreField.value = ex.max_score;
        if (passingScoreField) passingScoreField.value = ex.passing_score;
        if (descField) descField.value = ex.description || '';
        if (statusField) statusField.value = ex.status;

        if (examModal) examModal.style.display = 'flex';
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  // Complete Exam
  document.querySelectorAll('.complete-exam-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      if (!id) return;
      if (!confirm('هل أنت متأكد من تعيين هذا الامتحان كمكتمل؟')) return;
      try {
        await api.completeExam(id);
        showToast('تم تعيين الامتحان كمكتمل بنجاح');
        await navigate();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  // Cancel Exam
  document.querySelectorAll('.cancel-exam-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      if (!id) return;
      if (!confirm('هل أنت متأكد من إلغاء هذا الامتحان؟ لن يمكن رصد درجات جديدة له.')) return;
      try {
        await api.cancelExam(id);
        showToast('تم إلغاء الامتحان بنجاح');
        await navigate();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  // Delete Exam
  document.querySelectorAll('.delete-exam-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      if (!id) return;
      if (!confirm('هل أنت متأكد من حذف هذا الامتحان نهائياً؟')) return;
      try {
        await api.deleteExam(id);
        showToast('تم حذف الامتحان بنجاح');
        await navigate();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  bindGroupExamsSummaryModal();
  bindStudentExamHistoryModal();

  // Action query parameter handling
  if (queryParams && queryParams.get('action') === 'create_exam') {
    openModalForNew();
  }
}

function bindExamSheetEvents(sheet) {
  const exam = sheet.exam;

  // Back to list
  const backBtn = document.getElementById('back-to-exams-list');
  if (backBtn) {
    backBtn.addEventListener('click', async () => {
      state.activeExamId = null;
      state.activeExamSheet = null;
      await navigate();
    });
  }

  // Complete exam from sheet
  document.querySelectorAll('.complete-exam-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      if (!id) return;
      if (!confirm('هل أنت متأكد من تعيين هذا الامتحان كمكتمل؟')) return;
      try {
        await api.completeExam(id);
        showToast('تم تعيين الامتحان كمكتمل');
        state.activeExamSheet = await api.getExamResults(id);
        await navigate();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  // Local Table Search & Status Filter
  const searchInput = document.getElementById('sheet-student-search');
  const statusFilter = document.getElementById('sheet-filter-status');

  const filterRows = () => {
    const q = (searchInput ? searchInput.value : '').trim().toLowerCase();
    const st = (statusFilter ? statusFilter.value : '');

    document.querySelectorAll('#exam-results-table tbody tr.student-result-row').forEach(row => {
      const text = row.textContent.toLowerCase();
      const rowStatus = row.getAttribute('data-status') || 'pending';

      const matchesSearch = !q || text.includes(q);
      const matchesStatus = !st || rowStatus === st;

      row.style.display = (matchesSearch && matchesStatus) ? '' : 'none';
    });
  };

  if (searchInput) searchInput.addEventListener('input', filterRows);
  if (statusFilter) statusFilter.addEventListener('change', filterRows);

  // Status Change for each row
  document.querySelectorAll('.row-status-select').forEach(sel => {
    sel.addEventListener('change', () => {
      const row = sel.closest('tr');
      if (!row) return;
      const scoreInput = row.querySelector('.row-score-input');
      const pctSpan = row.querySelector('.row-pct');
      const badgeSpan = row.querySelector('.row-result-badge');
      const val = sel.value;

      row.setAttribute('data-status', val || 'pending');

      if (val === 'attended') {
        if (scoreInput) {
          scoreInput.disabled = false;
          scoreInput.focus();
        }
      } else {
        if (scoreInput) {
          scoreInput.value = '';
          scoreInput.disabled = true;
          scoreInput.classList.remove('is-invalid');
        }
        if (pctSpan) pctSpan.textContent = '—';
        if (badgeSpan) {
          if (val === 'absent') {
            badgeSpan.innerHTML = '<span class="badge badge-danger">غائب</span>';
          } else if (val === 'excused') {
            badgeSpan.innerHTML = '<span class="badge badge-primary">معتذر</span>';
          } else {
            badgeSpan.innerHTML = '<span class="badge badge-pending">قيد الانتظار</span>';
          }
        }
      }
    });
  });

  // Score Input Change for each row
  document.querySelectorAll('.row-score-input').forEach(inp => {
    inp.addEventListener('input', () => {
      const row = inp.closest('tr');
      if (!row) return;
      const pctSpan = row.querySelector('.row-pct');
      const badgeSpan = row.querySelector('.row-result-badge');
      const statusSelect = row.querySelector('.row-status-select');

      const raw = inp.value;
      if (raw === '' || isNaN(parseFloat(raw))) {
        inp.classList.remove('is-invalid');
        if (pctSpan) pctSpan.textContent = '—';
        if (badgeSpan) badgeSpan.innerHTML = '<span class="badge badge-pending">قيد الانتظار</span>';
        return;
      }

      const score = parseFloat(raw);
      if (score < 0 || score > exam.max_score) {
        inp.classList.add('is-invalid');
        if (pctSpan) pctSpan.textContent = 'غير صالح';
        if (badgeSpan) badgeSpan.innerHTML = '<span class="badge badge-danger">تجاوز الحد</span>';
        return;
      }

      inp.classList.remove('is-invalid');
      if (statusSelect && statusSelect.value !== 'attended') {
        statusSelect.value = 'attended';
        row.setAttribute('data-status', 'attended');
      }

      const pct = Math.round((score / exam.max_score) * 1000) / 10;
      if (pctSpan) pctSpan.textContent = `${pct}%`;

      const isPassed = score >= exam.passing_score;
      if (badgeSpan) {
        badgeSpan.innerHTML = isPassed
          ? '<span class="badge badge-pass">ناجح</span>'
          : '<span class="badge badge-fail">راسب</span>';
      }
    });
  });

  // Single Student Result Save
  document.querySelectorAll('.save-single-result-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const row = btn.closest('tr');
      if (!row) return;
      const studentId = row.getAttribute('data-student-id');
      const statusSelect = row.querySelector('.row-status-select');
      const scoreInput = row.querySelector('.row-score-input');
      const notesInput = row.querySelector('.row-notes-input');

      const status = statusSelect ? statusSelect.value : '';
      if (!status) {
        showToast('يرجى تحديد حالة الطالب (حاضر / غائب / بعذر)', 'error');
        return;
      }

      let score = null;
      if (status === 'attended') {
        const rawScore = scoreInput ? scoreInput.value : '';
        if (rawScore === '' || isNaN(parseFloat(rawScore))) {
          showToast('الدرجة مطلوبة عند تسجيل حضور الطالب في الامتحان', 'error');
          if (scoreInput) scoreInput.focus();
          return;
        }
        score = parseFloat(rawScore);
        if (score < 0 || score > exam.max_score) {
          showToast(`الدرجة يجب أن تكون بين 0 و ${exam.max_score}`, 'error');
          if (scoreInput) scoreInput.focus();
          return;
        }
      }

      btn.disabled = true;
      try {
        await api.recordExamResult(exam.id, {
          student_id: studentId,
          status,
          score,
          notes: notesInput ? notesInput.value.trim() : null
        });

        row.classList.add('row-highlight');
        setTimeout(() => row.classList.remove('row-highlight'), 2000);
        showToast('تم حفظ نتيجة الطالب بنجاح');
        await refreshExamSheetStats(exam.id, exam.max_score, exam.passing_score);
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        btn.disabled = false;
      }
    });
  });

  // Mark Remaining Absent
  const markAbsentBtn = document.getElementById('mark-remaining-absent-grades-btn');
  if (markAbsentBtn) {
    markAbsentBtn.addEventListener('click', () => {
      let count = 0;
      document.querySelectorAll('#exam-results-table tbody tr.student-result-row').forEach(row => {
        const statusSelect = row.querySelector('.row-status-select');
        const currentStatus = statusSelect ? statusSelect.value : '';
        if (!currentStatus) {
          if (statusSelect) statusSelect.value = 'absent';
          row.setAttribute('data-status', 'absent');
          const scoreInput = row.querySelector('.row-score-input');
          if (scoreInput) {
            scoreInput.value = '';
            scoreInput.disabled = true;
          }
          const pctSpan = row.querySelector('.row-pct');
          if (pctSpan) pctSpan.textContent = '—';
          const badgeSpan = row.querySelector('.row-result-badge');
          if (badgeSpan) badgeSpan.innerHTML = '<span class="badge badge-danger">غائب</span>';
          count++;
        }
      });
      if (count > 0) {
        showToast(`تم تعيين ${count} طالب كغائب. اضغط "حفظ الكشف بالكامل" لتثبيت التغييرات.`);
      } else {
        showToast('تم رصد جميع الطلاب بالفعل، لا يوجد طلاب في الانتظار.');
      }
    });
  }

  // Bulk Save All Grades
  const saveAllBtn = document.getElementById('save-all-grades-btn');
  if (saveAllBtn) {
    saveAllBtn.addEventListener('click', async () => {
      const rows = document.querySelectorAll('#exam-results-table tbody tr.student-result-row');
      const records = [];

      for (const row of rows) {
        const studentId = row.getAttribute('data-student-id');
        const statusSelect = row.querySelector('.row-status-select');
        const scoreInput = row.querySelector('.row-score-input');
        const notesInput = row.querySelector('.row-notes-input');

        const status = statusSelect ? statusSelect.value : '';
        if (!status) continue; // Skip unrecorded / pending

        let score = null;
        if (status === 'attended') {
          const rawScore = scoreInput ? scoreInput.value : '';
          if (rawScore === '' || isNaN(parseFloat(rawScore))) {
            const studentName = row.querySelector('td:nth-child(2)')?.textContent.trim();
            showToast(`الدرجة مطلوبة للطالب: ${studentName}`, 'error');
            if (scoreInput) scoreInput.focus();
            return;
          }
          score = parseFloat(rawScore);
          if (score < 0 || score > exam.max_score) {
            showToast(`الدرجة (${score}) يجب أن تكون بين 0 و ${exam.max_score}`, 'error');
            if (scoreInput) scoreInput.focus();
            return;
          }
        }

        records.push({
          student_id: studentId,
          status,
          score,
          notes: notesInput ? notesInput.value.trim() : null
        });
      }

      if (records.length === 0) {
        showToast('لم يتم رصد درجات أو حالات لأي طالب حتى الآن.', 'error');
        return;
      }

      saveAllBtn.disabled = true;
      try {
        const res = await api.bulkRecordExamResults(exam.id, records);
        showToast(res.message || 'تم حفظ كشف الدرجات بالكامل بنجاح');
        await refreshExamSheetStats(exam.id, exam.max_score, exam.passing_score);
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        saveAllBtn.disabled = false;
      }
    });
  }

  bindGroupExamsSummaryModal();
  bindStudentExamHistoryModal();
}

async function refreshExamSheetStats(examId, maxScore, passingScore) {
  try {
    const updatedSheet = await api.getExamResults(examId);
    state.activeExamSheet = updatedSheet;
    const stats = updatedSheet.stats;

    const elRec = document.getElementById('exam-counter-recorded');
    const elPend = document.getElementById('exam-counter-pending');
    const elAtt = document.getElementById('exam-counter-attended');
    const elAbs = document.getElementById('exam-counter-absent');
    const elExc = document.getElementById('exam-counter-excused');
    const elRate = document.getElementById('exam-counter-pass-rate');
    const elAvg = document.getElementById('exam-counter-avg-score');

    if (elRec) elRec.textContent = stats.results_recorded;
    if (elPend) elPend.textContent = stats.results_pending;
    if (elAtt) elAtt.textContent = stats.attended_count;
    if (elAbs) elAbs.textContent = stats.absent_count;
    if (elExc) elExc.textContent = stats.excused_count;
    if (elRate) elRate.textContent = `${stats.pass_rate}%`;
    if (elAvg) elAvg.textContent = stats.average_score;

    const progPass = document.getElementById('prog-pass');
    const progFail = document.getElementById('prog-fail');
    const progAbsent = document.getElementById('prog-absent');
    const progExcused = document.getElementById('prog-excused');
    const progLabel = document.getElementById('exam-prog-label');

    if (stats.total_enrolled > 0) {
      if (progPass) progPass.style.width = `${(stats.pass_count / stats.total_enrolled) * 100}%`;
      if (progFail) progFail.style.width = `${(stats.fail_count / stats.total_enrolled) * 100}%`;
      if (progAbsent) progAbsent.style.width = `${(stats.absent_count / stats.total_enrolled) * 100}%`;
      if (progExcused) progExcused.style.width = `${(stats.excused_count / stats.total_enrolled) * 100}%`;
    }
    if (progLabel) {
      progLabel.textContent = `الطلاب الناجحون: ${stats.pass_count} من ${stats.attended_count} حضروا (${stats.pass_rate}%)`;
    }
  } catch (err) {
    console.error('Failed to refresh exam stats:', err);
  }
}

function bindGroupExamsSummaryModal() {
  const modal = document.getElementById('group-exams-summary-modal');
  const modalTitle = document.getElementById('group-exams-summary-modal-title');
  const modalBody = document.getElementById('group-exams-summary-modal-body');
  const closeBtn = document.getElementById('close-group-exams-summary-modal');

  const closeModal = () => {
    if (modal) modal.style.display = 'none';
  };

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  document.querySelectorAll('.view-group-exams-summary-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const gId = btn.getAttribute('data-group-id');
      if (!gId) return;

      try {
        const sum = await api.getGroupExamsSummary(gId);
        if (modalTitle) modalTitle.textContent = `تقرير أداء المجموعة: ${sum.group_name} (${sum.grade_label})`;
        if (modalBody) {
          modalBody.innerHTML = `
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:0.75rem; margin-bottom:1.25rem;">
              <div class="exam-stat-box">
                <span class="exam-stat-label">متوسط نسبة النجاح</span>
                <span class="exam-stat-val" style="color:#059669;">${sum.average_pass_rate}%</span>
              </div>
              <div class="exam-stat-box">
                <span class="exam-stat-label">متوسط تحصيل المجموعة</span>
                <span class="exam-stat-val" style="color:var(--primary);">${sum.average_group_score_percentage}%</span>
              </div>
              <div class="exam-stat-box">
                <span class="exam-stat-label">عدد الطلاب المقيدين</span>
                <span class="exam-stat-val" style="color:var(--slate-800);">${sum.total_students}</span>
              </div>
              <div class="exam-stat-box">
                <span class="exam-stat-label">إجمالي الامتحانات</span>
                <span class="exam-stat-val" style="color:var(--slate-800);">${sum.total_exams}</span>
              </div>
            </div>

            <div class="table-container" style="max-height:350px; overflow-y:auto;">
              <div class="table-header-bar">
                <div style="font-weight:700;">سجل الامتحانات الأخيرة</div>
              </div>
              ${sum.recent_exams.length === 0 ? `
                <div style="padding:2rem; text-align:center; color:var(--slate-500);">لا توجد امتحانات مسجلة لهذه المجموعة.</div>
              ` : `
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>الامتحان</th>
                      <th>التاريخ</th>
                      <th>العظمى</th>
                      <th>نسبة النجاح</th>
                      <th>متوسط الدرجات</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${sum.recent_exams.map(e => {
                      const stats = e.stats || { pass_rate: 0, average_score: 0, average_percentage: 0 };
                      return `
                        <tr>
                          <td>
                            <div style="font-weight:700;">${e.title}</div>
                            <span class="badge ${e.status === 'completed' ? 'badge-success' : 'badge-primary'}">${e.status_label}</span>
                          </td>
                          <td>${e.exam_date}</td>
                          <td class="tabular-nums">${e.max_score}</td>
                          <td>
                            <span style="font-weight:700; color:#059669;">${stats.pass_rate}%</span>
                          </td>
                          <td>
                            <span class="tabular-nums" style="font-weight:700;">${stats.average_score}</span>
                            <span style="font-size:0.75rem; color:var(--slate-500);">(${stats.average_percentage}%)</span>
                          </td>
                        </tr>
                      `;
                    }).join('')}
                  </tbody>
                </table>
              `}
            </div>
          `;
        }
        if (modal) modal.style.display = 'flex';
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });
}

function bindStudentExamHistoryModal() {
  const modal = document.getElementById('student-exam-history-modal');
  const modalTitle = document.getElementById('student-exam-history-modal-title');
  const modalBody = document.getElementById('student-exam-history-modal-body');
  const closeBtn = document.getElementById('close-student-exam-history-modal');

  const closeModal = () => {
    if (modal) modal.style.display = 'none';
  };

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  document.querySelectorAll('.view-student-exam-history-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const sId = btn.getAttribute('data-student-id');
      if (!sId) return;

      try {
        const hist = await api.getStudentExamHistory(sId);
        if (modalTitle) modalTitle.textContent = `سجل امتحانات الطالب: ${hist.student_name}`;
        if (modalBody) {
          modalBody.innerHTML = `
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap:0.75rem; margin-bottom:1.25rem;">
              <div class="exam-stat-box">
                <span class="exam-stat-label">نسبة النجاح العامة</span>
                <span class="exam-stat-val" style="color:#059669;">${hist.overall_pass_rate}%</span>
              </div>
              <div class="exam-stat-box">
                <span class="exam-stat-label">متوسط النسبة المئوية</span>
                <span class="exam-stat-val" style="color:var(--primary);">${hist.average_percentage}%</span>
              </div>
              <div class="exam-stat-box">
                <span class="exam-stat-label">إجمالي الامتحانات</span>
                <span class="exam-stat-val" style="color:var(--slate-800);">${hist.total_exams}</span>
              </div>
              <div class="exam-stat-box">
                <span class="exam-stat-label">ناجح</span>
                <span class="exam-stat-val" style="color:#059669;">${hist.passed_count}</span>
              </div>
              <div class="exam-stat-box">
                <span class="exam-stat-label">راسب</span>
                <span class="exam-stat-val" style="color:#DC2626;">${hist.failed_count}</span>
              </div>
              <div class="exam-stat-box">
                <span class="exam-stat-label">غائب</span>
                <span class="exam-stat-val" style="color:#94A3B8;">${hist.absent_count}</span>
              </div>
              <div class="exam-stat-box">
                <span class="exam-stat-label">معتذر</span>
                <span class="exam-stat-val" style="color:#2563EB;">${hist.excused_count}</span>
              </div>
            </div>

            <div class="table-container" style="max-height:350px; overflow-y:auto;">
              ${hist.history.length === 0 ? `
                <div style="padding:2rem; text-align:center; color:var(--slate-500);">لا توجد امتحانات مسجلة لهذا الطالب حتى الآن.</div>
              ` : `
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>الامتحان</th>
                      <th>التاريخ</th>
                      <th>المجموعة</th>
                      <th>الدرجة</th>
                      <th>النسبة</th>
                      <th>النتيجة</th>
                      <th>ملاحظات</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${hist.history.map(h => {
                      let resBadge = '';
                      if (h.status === 'attended') {
                        resBadge = h.is_passed
                          ? '<span class="badge badge-pass">ناجح</span>'
                          : '<span class="badge badge-fail">راسب</span>';
                      } else if (h.status === 'absent') {
                        resBadge = '<span class="badge badge-danger">غائب</span>';
                      } else if (h.status === 'excused') {
                        resBadge = '<span class="badge badge-primary">معتذر</span>';
                      } else if (h.status === 'cancelled') {
                        resBadge = '<span class="badge badge-danger">ملغى</span>';
                      }

                      return `
                        <tr>
                          <td>
                            <div style="font-weight:700;">${h.exam_title}</div>
                          </td>
                          <td>${h.exam_date}</td>
                          <td>${h.group_name}</td>
                          <td>
                            ${h.score !== null ? `<span class="tabular-nums" style="font-weight:700;">${h.score}</span> / <span class="tabular-nums" style="font-size:0.8rem; color:var(--slate-500);">${h.max_score}</span>` : '—'}
                          </td>
                          <td>
                            ${h.percentage !== null ? `<span class="tabular-nums" style="font-weight:700;">${h.percentage}%</span>` : '—'}
                          </td>
                          <td>${resBadge}</td>
                          <td style="font-size:0.8rem; color:var(--slate-600);">${h.notes || '-'}</td>
                        </tr>
                      `;
                    }).join('')}
                  </tbody>
                </table>
              `}
            </div>
          `;
        }
        if (modal) modal.style.display = 'flex';
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });
}

// ==========================================================================
// --- Payments & Finance Views & Components ---
// ==========================================================================

// (formatPiastres and formatEGP are defined in the currency helpers section near top)

function getDueStatusBadge(status) {
  if (status === 'paid') return '<span class="badge badge-paid">مسدد بالكامل</span>';
  if (status === 'partially_paid') return '<span class="badge badge-partially-paid">مسدد جزئياً</span>';
  if (status === 'unpaid') return '<span class="badge badge-unpaid">غير مسدد</span>';
  if (status === 'void') return '<span class="badge badge-void">ملغي</span>';
  return `<span class="badge badge-neutral">${status}</span>`;
}

function getChargeTypeBadge(chargeType) {
  if (chargeType === 'monthly_fee') return '<span class="badge badge-primary">اشتراك شهري</span>';
  if (chargeType === 'session_fee') return '<span class="badge badge-secondary">رسم بالحصة</span>';
  return `<span class="badge badge-neutral">${chargeType}</span>`;
}

function renderFinanceView() {
  const user = state.user || {};
  const isTeacher = user.is_teacher;
  const canCollectCash = isTeacher || user.can_collect_cash;
  const canManageFees = isTeacher || user.can_manage_fees;
  const canViewFinances = isTeacher || user.can_view_financial_analytics || user.can_view_student_payment_history || canCollectCash || canManageFees;

  if (!canViewFinances) {
    return `
      <div class="card" style="padding:2.5rem; text-align:center; max-width:600px; margin:2rem auto;">
        <div style="font-size:3rem; margin-bottom:1rem;">🔒</div>
        <h2 style="font-size:1.25rem; font-weight:800; color:var(--slate-800); margin-bottom:0.5rem;">عفواً، لا تملك صلاحية الوصول لقسم المالية</h2>
        <p style="color:var(--slate-500); font-size:0.9rem;">هذا القسم مخصص للمعلم والمساعدين المصرح لهم بتحصيل النقدية أو إدارة الرسوم.</p>
      </div>
    `;
  }

  let tabContent = '';
  if (state.financeTab === 'overview') {
    tabContent = renderFinanceOverviewTab();
  } else if (state.financeTab === 'payments') {
    tabContent = renderFinancePaymentsTab();
  } else if (state.financeTab === 'dues') {
    tabContent = renderFinanceDuesTab();
  } else if (state.financeTab === 'configs') {
    tabContent = renderFinanceFeeConfigsTab();
  } else if (state.financeTab === 'reports') {
    tabContent = renderFinanceReportsTab();
  }

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">إدارة التحصيل والنقدية والرسوم</h1>
        <p class="page-subtitle">إدارة رسوم المجموعات، توليد المطالبات، تحصيل النقدية بإيصالات معتمدة، ومتابعة أرصدة الطلاب والخزينة.</p>
      </div>
      <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
        ${canCollectCash ? `
          <button type="button" id="open-record-payment-btn" class="btn btn-primary">
            ${icons.plus}
            <span>تسجيل تحصيل نقدي</span>
          </button>
        ` : ''}
        ${canManageFees ? `
          <button type="button" id="open-monthly-dues-btn" class="btn btn-secondary">
            ${icons.calendar}
            <span>توليد اشتراكات شهرية</span>
          </button>
          <button type="button" id="open-session-dues-btn" class="btn btn-secondary">
            ${icons.attendance}
            <span>توليد رسوم الحصص</span>
          </button>
        ` : ''}
      </div>
    </div>

    <!-- Segmented Tab Navigation -->
    <div class="tab-nav" style="margin-bottom:1.25rem;">
      <button type="button" class="tab-btn ${state.financeTab === 'overview' ? 'active' : ''}" id="f-tab-overview">
        ${icons.dashboard}
        <span>نظرة عامة والمؤشرات</span>
      </button>
      <button type="button" class="tab-btn ${state.financeTab === 'payments' ? 'active' : ''}" id="f-tab-payments">
        ${icons.cash}
        <span>سجل الإيصالات والتحصيل (${state.payments.length})</span>
      </button>
      <button type="button" class="tab-btn ${state.financeTab === 'dues' ? 'active' : ''}" id="f-tab-dues">
        ${icons.attendance}
        <span>المستحقات والمطالبات</span>
      </button>
      <button type="button" class="tab-btn ${state.financeTab === 'configs' ? 'active' : ''}" id="f-tab-configs">
        ${icons.system}
        <span>إعدادات رسوم المجموعات</span>
      </button>
      <button type="button" class="tab-btn ${state.financeTab === 'reports' ? 'active' : ''}" id="f-tab-reports">
        ${icons.analytics}
        <span>التقارير وكشوف الحساب</span>
      </button>
    </div>

    <!-- Tab Content -->
    ${tabContent}

    <!-- Modals Section -->
    ${renderFinanceModals()}
  `;
}

// --- Tab 1: Overview ---
function renderFinanceOverviewTab() {
  const ov = state.financeOverview || {
    total_dues_piastres: 0,
    total_collected_piastres: 0,
    total_outstanding_piastres: 0,
    collection_rate_percent: 0.0,
    active_students_count: state.students.length,
    active_groups_count: state.groups.length
  };

  const user = state.user || {};
  const canCollectCash = user.is_teacher || user.can_collect_cash;
  const canManageFees = user.is_teacher || user.can_manage_fees;

  return `
    <div class="finance-metrics-grid">
      <div class="finance-metric-card">
        <div class="metric-header">
          <span>إجمالي المطالبات والرسوم</span>
          ${icons.cash}
        </div>
        <div class="metric-val money-accent">${formatPiastres(ov.total_dues_piastres)}</div>
        <div class="metric-sub">إجمالي قيمة المستحقات المقيدة على الطلاب</div>
      </div>

      <div class="finance-metric-card">
        <div class="metric-header">
          <span>إجمالي المحصل نقداً</span>
          ${icons.check}
        </div>
        <div class="metric-val money-rate">${formatPiastres(ov.total_collected_piastres)}</div>
        <div class="metric-sub">إجمالي النقدية المقبوضة والمعتمدة</div>
      </div>

      <div class="finance-metric-card">
        <div class="metric-header">
          <span>المتبقي قيد التحصيل</span>
          ${icons.clock}
        </div>
        <div class="metric-val money-due">${formatPiastres(ov.total_outstanding_piastres)}</div>
        <div class="metric-sub">أرصدة مستحقة معلقة على الطلاب</div>
      </div>

      <div class="finance-metric-card">
        <div class="metric-header">
          <span>نسبة التحصيل الكلية</span>
          ${icons.analytics}
        </div>
        <div class="metric-val money-rate">${ov.collection_rate_percent.toFixed(1)}%</div>
        <div class="metric-sub">نسبة السداد الفعلي من إجمالي الرسوم</div>
      </div>
    </div>

    <!-- Quick Action Bar -->
    <div class="card" style="padding:1.25rem; margin-bottom:1.5rem;">
      <div style="font-weight:700; color:var(--slate-800); margin-bottom:0.75rem;">إجراءات سريعة للخزينة</div>
      <div style="display:flex; gap:0.75rem; flex-wrap:wrap;">
        ${canCollectCash ? `
          <button type="button" id="quick-record-payment-btn" class="btn btn-primary">
            ${icons.plus}
            <span>تسجيل تحصيل نقدي فوري</span>
          </button>
        ` : ''}
        ${canManageFees ? `
          <button type="button" id="quick-gen-monthly-btn" class="btn btn-secondary">
            ${icons.calendar}
            <span>توليد اشتراكات شهرية</span>
          </button>
          <button type="button" id="quick-gen-session-btn" class="btn btn-secondary">
            ${icons.attendance}
            <span>توليد رسوم حصة منتهية</span>
          </button>
          <button type="button" id="quick-set-fee-btn" class="btn btn-secondary">
            ${icons.system}
            <span>ضبط رسوم مجموعة</span>
          </button>
        ` : ''}
      </div>
    </div>

    <!-- Recent Payments Table -->
    <div class="card" style="padding:1.25rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
        <h2 class="card-title" style="margin:0;">أحدث عمليات التحصيل والإيصالات النقدية</h2>
        <button type="button" id="btn-see-all-payments" class="btn btn-secondary btn-sm">عرض كل الإيصالات</button>
      </div>

      ${state.payments.length === 0 ? `
        <div style="text-align:center; padding:2rem; color:var(--slate-400);">
          <div style="font-size:2rem; margin-bottom:0.5rem;">🧾</div>
          <div style="font-weight:700; color:var(--slate-700);">لا توجد عمليات تحصيل مسجلة حتى الآن</div>
          <p style="font-size:0.85rem; margin-top:0.25rem;">سجل أول تحصيل نقدي بالضغط على زر "تسجيل تحصيل نقدي" أعلاه.</p>
        </div>
      ` : `
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>رقم الإيصال</th>
                <th>اسم الطالب</th>
                <th>تاريخ التحصيل</th>
                <th>المبلغ المحصل</th>
                <th>المسؤول</th>
                <th>الحالة</th>
                <th style="text-align:center;">إجراءات</th>
              </tr>
            </thead>
            <tbody>
              ${state.payments.slice(0, 10).map(p => `
                <tr>
                  <td class="tabular-nums" style="font-family:monospace; font-weight:700; color:var(--primary);">${p.receipt_number}</td>
                  <td style="font-weight:700;">${p.student_name}</td>
                  <td class="tabular-nums">${p.payment_date}</td>
                  <td class="tabular-nums" style="font-weight:700; color:var(--slate-900);">${p.formatted_amount}</td>
                  <td style="font-size:0.85rem; color:var(--slate-600);">${p.created_by_name}</td>
                  <td>
                    ${p.is_reversed ? '<span class="badge badge-reversed">ملغي ومسترد</span>' : '<span class="badge badge-paid">معتمد</span>'}
                  </td>
                  <td style="text-align:center;">
                    <div style="display:flex; justify-content:center; gap:0.4rem;">
                      <button type="button" class="btn btn-secondary btn-sm view-receipt-btn" data-id="${p.id}" title="عرض وطباعة الإيصال">
                        📄 عرض الإيصال
                      </button>
                      ${!p.is_reversed && canCollectCash ? `
                        <button type="button" class="btn btn-secondary btn-sm reverse-payment-btn" data-id="${p.id}" data-rec="${p.receipt_number}" title="استرداد وإلغاء الإيصال">
                          ↩ استرداد
                        </button>
                      ` : ''}
                    </div>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;
}

// --- Tab 2: Cash Payments ---
function renderFinancePaymentsTab() {
  const user = state.user || {};
  const canCollectCash = user.is_teacher || user.can_collect_cash;

  return `
    <!-- Filter Bar -->
    <div class="card" style="padding:1rem; margin-bottom:1.25rem;">
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)) auto; gap:0.75rem; align-items:end;">
        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">تصفية بالطالب</label>
          <select id="filter-pay-student" class="form-input">
            <option value="">جميع الطلاب</option>
            ${state.students.map(s => `
              <option value="${s.id}" ${state.paymentFilters.student_id == s.id ? 'selected' : ''}>${s.full_name} (${s.phone})</option>
            `).join('')}
          </select>
        </div>

        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">من تاريخ</label>
          <input type="date" id="filter-pay-start-date" class="form-input" value="${state.paymentFilters.start_date || ''}">
        </div>

        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">إلى تاريخ</label>
          <input type="date" id="filter-pay-end-date" class="form-input" value="${state.paymentFilters.end_date || ''}">
        </div>

        <div class="form-group" style="margin:0; display:flex; align-items:center; gap:0.5rem; height:38px;">
          <label class="checkbox-group" style="border:none; padding:0; background:none;">
            <input type="checkbox" id="filter-pay-reversed" ${state.paymentFilters.include_reversed === 'true' ? 'checked' : ''}>
            <span style="font-size:0.85rem; font-weight:600;">إظهار الإيصالات المستردة</span>
          </label>
        </div>

        <div style="display:flex; gap:0.4rem;">
          <button type="button" id="filter-payments-btn" class="btn btn-primary btn-sm" style="height:38px;">
            ${icons.search}
            <span>تصفية</span>
          </button>
          <button type="button" id="reset-payments-btn" class="btn btn-secondary btn-sm" style="height:38px;">إعادة تعيين</button>
        </div>
      </div>
    </div>

    <!-- Payments List Table -->
    <div class="card" style="padding:1.25rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
        <h2 class="card-title" style="margin:0;">سجل إيصالات النقدية (${state.payments.length})</h2>
        ${canCollectCash ? `
          <button type="button" id="open-record-payment-btn-tab" class="btn btn-primary btn-sm">
            ${icons.plus}
            <span>تسجيل إيصال جديد</span>
          </button>
        ` : ''}
      </div>

      ${state.payments.length === 0 ? `
        <div style="text-align:center; padding:2.5rem; color:var(--slate-400);">
          <div style="font-size:2.5rem; margin-bottom:0.5rem;">🧾</div>
          <div style="font-weight:700; color:var(--slate-700);">لا توجد إيصالات نقدية مطابقة لمعايير البحث</div>
        </div>
      ` : `
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>رقم الإيصال</th>
                <th>الطالب</th>
                <th>التاريخ</th>
                <th>المبلغ المحصل</th>
                <th>الموزع للمستحقات</th>
                <th>المسؤول</th>
                <th>الحالة</th>
                <th>ملاحظات</th>
                <th style="text-align:center;">إجراءات</th>
              </tr>
            </thead>
            <tbody>
              ${state.payments.map(p => `
                <tr style="${p.is_reversed ? 'opacity:0.65; background:#FEF2F2;' : ''}">
                  <td class="tabular-nums" style="font-family:monospace; font-weight:700; color:var(--primary);">${p.receipt_number}</td>
                  <td style="font-weight:700;">${p.student_name}</td>
                  <td class="tabular-nums">${p.payment_date}</td>
                  <td class="tabular-nums" style="font-weight:800; color:var(--slate-900);">${p.formatted_amount}</td>
                  <td class="tabular-nums" style="font-weight:600; color:var(--slate-600);">${p.allocated_amount_egp.toFixed(2)} ج.م</td>
                  <td style="font-size:0.85rem;">${p.created_by_name}</td>
                  <td>
                    ${p.is_reversed ? '<span class="badge badge-reversed">ملغي ومسترد</span>' : '<span class="badge badge-paid">معتمد</span>'}
                  </td>
                  <td style="font-size:0.8rem; color:var(--slate-500); max-width:180px;">${p.notes || '-'}</td>
                  <td style="text-align:center;">
                    <div style="display:flex; justify-content:center; gap:0.4rem;">
                      <button type="button" class="btn btn-secondary btn-sm view-receipt-btn" data-id="${p.id}" title="عرض وطباعة الإيصال">
                        📄 الإيصال
                      </button>
                      ${!p.is_reversed && canCollectCash ? `
                        <button type="button" class="btn btn-secondary btn-sm reverse-payment-btn" data-id="${p.id}" data-rec="${p.receipt_number}" title="استرداد وإلغاء الإيصال">
                          ↩ استرداد
                        </button>
                      ` : ''}
                    </div>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;
}

// --- Tab 3: Dues & Billing ---
function renderFinanceDuesTab() {
  const user = state.user || {};
  const canManageFees = user.is_teacher || user.can_manage_fees;

  return `
    <!-- Top Action Cards for Generation -->
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:1rem; margin-bottom:1.25rem;">
      <div class="card" style="padding:1.25rem; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-weight:800; color:var(--slate-800); font-size:1rem;">توليد اشتراكات شهرية</div>
          <div style="font-size:0.8rem; color:var(--slate-500); margin-top:0.25rem;">توليد مطالبات الاشتراكات لطلاب مجموعة عن شهر محدد</div>
        </div>
        ${canManageFees ? `
          <button type="button" id="open-gen-monthly-btn" class="btn btn-primary btn-sm">
            ${icons.plus}
            <span>توليد</span>
          </button>
        ` : ''}
      </div>

      <div class="card" style="padding:1.25rem; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-weight:800; color:var(--slate-800); font-size:1rem;">توليد رسوم حصة دراسية</div>
          <div style="font-size:0.8rem; color:var(--slate-500); margin-top:0.25rem;">توليد رسوم الحصص للطلاب الحاضرين في حصة منتهية</div>
        </div>
        ${canManageFees ? `
          <button type="button" id="open-gen-session-btn" class="btn btn-secondary btn-sm">
            ${icons.attendance}
            <span>توليد</span>
          </button>
        ` : ''}
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="card" style="padding:1rem; margin-bottom:1.25rem;">
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)) auto; gap:0.75rem; align-items:end;">
        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">المجموعة</label>
          <select id="filter-due-group" class="form-input">
            <option value="">جميع المجموعات</option>
            ${state.groups.map(g => `
              <option value="${g.id}" ${state.dueFilters.group_id == g.id ? 'selected' : ''}>${g.name}</option>
            `).join('')}
          </select>
        </div>

        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">الطالب</label>
          <select id="filter-due-student" class="form-input">
            <option value="">جميع الطلاب</option>
            ${state.students.map(s => `
              <option value="${s.id}" ${state.dueFilters.student_id == s.id ? 'selected' : ''}>${s.full_name}</option>
            `).join('')}
          </select>
        </div>

        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">نوع الرسم</label>
          <select id="filter-due-charge-type" class="form-input">
            <option value="">جميع الأنواع</option>
            <option value="monthly_fee" ${state.dueFilters.charge_type === 'monthly_fee' ? 'selected' : ''}>اشتراك شهري</option>
            <option value="session_fee" ${state.dueFilters.charge_type === 'session_fee' ? 'selected' : ''}>رسم بالحصة</option>
          </select>
        </div>

        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">حالة السداد</label>
          <select id="filter-due-status" class="form-input">
            <option value="">جميع الحالات</option>
            <option value="unpaid" ${state.dueFilters.status === 'unpaid' ? 'selected' : ''}>غير مسدد</option>
            <option value="partially_paid" ${state.dueFilters.status === 'partially_paid' ? 'selected' : ''}>مسدد جزئياً</option>
            <option value="paid" ${state.dueFilters.status === 'paid' ? 'selected' : ''}>مسدد بالكامل</option>
            <option value="void" ${state.dueFilters.status === 'void' ? 'selected' : ''}>ملغي</option>
          </select>
        </div>

        <div class="form-group" style="margin:0;">
          <label class="form-label" style="font-size:0.8rem;">الشهر المستحق (YYYY-MM)</label>
          <input type="month" id="filter-due-month" class="form-input" value="${state.dueFilters.billing_month || ''}">
        </div>

        <div style="display:flex; gap:0.4rem;">
          <button type="button" id="filter-dues-btn" class="btn btn-primary btn-sm" style="height:38px;">
            ${icons.search}
            <span>تصفية</span>
          </button>
          <button type="button" id="reset-dues-btn" class="btn btn-secondary btn-sm" style="height:38px;">إعادة تعيين</button>
        </div>
      </div>
    </div>

    <!-- Dues Table -->
    <div class="card" style="padding:1.25rem;">
      <h2 class="card-title" style="margin-bottom:1rem;">سجل المستحقات والمطالبات المالية (${state.dues.length})</h2>

      ${state.dues.length === 0 ? `
        <div style="text-align:center; padding:2.5rem; color:var(--slate-400);">
          <div style="font-size:2.5rem; margin-bottom:0.5rem;">📋</div>
          <div style="font-weight:700; color:var(--slate-700);">لا توجد مطالبات مالية مسجلة مطابقة لمعايير البحث</div>
        </div>
      ` : `
        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>الطالب</th>
                <th>المجموعة</th>
                <th>نوع الرسم</th>
                <th>البيان / الشهر</th>
                <th>القيمة المستحقة</th>
                <th>المسدد</th>
                <th>المتبقي</th>
                <th>تاريخ الاستحقاق</th>
                <th>الحالة</th>
                <th style="text-align:center;">إجراءات</th>
              </tr>
            </thead>
            <tbody>
              ${state.dues.map(d => `
                <tr style="${d.status === 'void' ? 'opacity:0.6; text-decoration:line-through;' : ''}">
                  <td style="font-weight:700;">${d.student_name}</td>
                  <td>${d.group_name}</td>
                  <td>${getChargeTypeBadge(d.charge_type)}</td>
                  <td class="tabular-nums" style="font-size:0.85rem;">${d.billing_month || (d.session_topic ? `حصة: ${d.session_topic}` : 'حصة دراسية')}</td>
                  <td class="tabular-nums" style="font-weight:700;">${d.amount_egp.toFixed(2)} ج.م</td>
                  <td class="tabular-nums" style="color:var(--slate-600);">${d.paid_amount_egp.toFixed(2)} ج.م</td>
                  <td class="tabular-nums" style="font-weight:800; color:${d.remaining_egp > 0 ? '#DC2626' : '#059669'};">
                    ${d.remaining_egp.toFixed(2)} ج.م
                  </td>
                  <td class="tabular-nums" style="font-size:0.85rem;">${d.due_date || '-'}</td>
                  <td>${getDueStatusBadge(d.status)}</td>
                  <td style="text-align:center;">
                    ${d.status === 'unpaid' && canManageFees ? `
                      <button type="button" class="btn btn-secondary btn-sm void-due-btn" data-id="${d.id}" title="إلغاء المطالبة">
                        ❌ إلغاء
                      </button>
                    ` : '—'}
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;
}

// --- Tab 4: Group Fee Configs ---
function renderFinanceFeeConfigsTab() {
  const user = state.user || {};
  const canManageFees = user.is_teacher || user.can_manage_fees;

  return `
    <div class="card" style="padding:1.25rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
        <div>
          <h2 class="card-title" style="margin:0;">إعدادات رسوم المجموعات الدراسية</h2>
          <p style="font-size:0.85rem; color:var(--slate-500); margin-top:0.25rem;">تحديد نظام الرسوم المعتمد لكل مجموعة (اشتراك شهري محدد أو رسم لكل حصة منفصلة).</p>
        </div>
        ${canManageFees ? `
          <button type="button" id="open-group-fee-modal-btn" class="btn btn-primary">
            ${icons.plus}
            <span>ضبط رسوم مجموعة</span>
          </button>
        ` : ''}
      </div>

      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>اسم المجموعة</th>
              <th>المرحلة الدراسية</th>
              <th>نظام الرسوم المعتمد</th>
              <th>قيمة الرسم</th>
              <th>تاريخ السريان</th>
              <th>الحالة</th>
              <th style="text-align:center;">إجراءات</th>
            </tr>
          </thead>
          <tbody>
            ${state.groups.map(g => {
              const activeCfg = state.feeConfigs.find(c => c.group_id === g.id && c.is_active);
              return `
                <tr>
                  <td style="font-weight:700;">${g.name}</td>
                  <td>${g.grade_label}</td>
                  <td>
                    ${activeCfg ? (activeCfg.fee_model === 'monthly' ? '<span class="badge badge-primary">اشتراك شهري</span>' : '<span class="badge badge-secondary">رسم بالحصة</span>') : '<span class="badge badge-neutral">لم يتم التحديد</span>'}
                  </td>
                  <td class="tabular-nums" style="font-weight:800; font-size:1.05rem; color:var(--primary);">
                    ${activeCfg ? `${activeCfg.amount_egp.toFixed(2)} ج.م` : '—'}
                  </td>
                  <td class="tabular-nums">${activeCfg ? activeCfg.effective_from : '—'}</td>
                  <td>
                    ${activeCfg ? '<span class="badge badge-success">نشط</span>' : '<span class="badge badge-neutral">غير مضبوط</span>'}
                  </td>
                  <td style="text-align:center;">
                    ${canManageFees ? `
                      <button type="button" class="btn btn-secondary btn-sm edit-group-fee-btn" data-group-id="${g.id}" data-group-name="${g.name}">
                        ⚙️ ضبط / تعديل
                      </button>
                    ` : '—'}
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// --- Tab 5: Financial Reports & Ledgers ---
function renderFinanceReportsTab() {
  const currentMonth = new Date().toISOString().slice(0, 7);
  const today = new Date().toISOString().split('T')[0];

  return `
    <div style="display:grid; grid-template-columns: 1fr; gap:1.5rem;">
      <!-- Report 1: Student Financial Ledger -->
      <div class="card" style="padding:1.25rem;">
        <h2 class="card-title" style="margin-bottom:0.75rem;">1. كشف حساب الطالب المالي (Student Ledger)</h2>
        <div style="display:flex; gap:0.75rem; align-items:center; flex-wrap:wrap; margin-bottom:1rem;">
          <div style="flex:1; min-width:240px;">
            <select id="report-student-select" class="form-input">
              <option value="">-- اختر طالباً لعرض كشف حسابه --</option>
              ${state.students.map(s => `
                <option value="${s.id}">${s.full_name} (${s.phone})</option>
              `).join('')}
            </select>
          </div>
        </div>
        <div id="student-ledger-result" style="display:none;"></div>
      </div>

      <!-- Report 2: Group Collection Summary -->
      <div class="card" style="padding:1.25rem;">
        <h2 class="card-title" style="margin-bottom:0.75rem;">2. ملخص تحصيل المجموعة (Group Collection Summary)</h2>
        <div style="display:flex; gap:0.75rem; align-items:center; flex-wrap:wrap; margin-bottom:1rem;">
          <div style="flex:1; min-width:240px;">
            <select id="report-group-select" class="form-input">
              <option value="">-- اختر مجموعة دراسية لعرض ملخص التحصيل --</option>
              ${state.groups.map(g => `
                <option value="${g.id}">${g.name} (${g.grade_label})</option>
              `).join('')}
            </select>
          </div>
        </div>
        <div id="group-summary-result" style="display:none;"></div>
      </div>

      <!-- Report 3: Monthly Collection Report -->
      <div class="card" style="padding:1.25rem;">
        <h2 class="card-title" style="margin-bottom:0.75rem;">3. التقرير المالي الشهري (Monthly Report)</h2>
        <div style="display:flex; gap:0.75rem; align-items:center; flex-wrap:wrap; margin-bottom:1rem;">
          <input type="month" id="report-month-input" class="form-input" style="width:200px;" value="${currentMonth}">
          <button type="button" id="btn-load-monthly-report" class="btn btn-primary btn-sm">عرض تقرير الشهر</button>
        </div>
        <div id="monthly-report-result" style="display:none;"></div>
      </div>

      <!-- Report 4: Cash Collection Audit -->
      <div class="card" style="padding:1.25rem;">
        <h2 class="card-title" style="margin-bottom:0.75rem;">4. تقرير حركة الخزينة النقدية (Cash Collection Audit)</h2>
        <div style="display:flex; gap:0.75rem; align-items:center; flex-wrap:wrap; margin-bottom:1rem;">
          <div style="display:flex; align-items:center; gap:0.4rem;">
            <label style="font-size:0.8rem; font-weight:600;">من:</label>
            <input type="date" id="report-cash-start" class="form-input" style="width:160px;" value="${today}">
          </div>
          <div style="display:flex; align-items:center; gap:0.4rem;">
            <label style="font-size:0.8rem; font-weight:600;">إلى:</label>
            <input type="date" id="report-cash-end" class="form-input" style="width:160px;" value="${today}">
          </div>
          <button type="button" id="btn-load-cash-report" class="btn btn-primary btn-sm">عرض حركة الخزينة</button>
        </div>
        <div id="cash-report-result" style="display:none;"></div>
      </div>
    </div>
  `;
}

// --- Modals Render Helper ---
function renderFinanceModals() {
  const today = new Date().toISOString().split('T')[0];
  const currentMonth = today.slice(0, 7);

  return `
    <!-- Record Payment Modal -->
    <div id="record-payment-modal" class="modal-overlay" style="display:none;">
      <div class="modal" style="max-width:700px; max-height:90vh; overflow-y:auto;">
        <div class="modal-header">
          <h3 class="modal-title">تسجيل تحصيل نقدي وإصدار إيصال</h3>
          <button type="button" class="modal-close" id="close-record-payment-modal">✕</button>
        </div>
        <form id="record-payment-form">
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label required">الطالب المسدد</label>
              <select id="pay-student-select" class="form-input" required>
                <option value="">-- اختر الطالب --</option>
                ${state.students.map(s => `
                  <option value="${s.id}">${s.full_name} (${s.phone})</option>
                `).join('')}
              </select>
            </div>

            <!-- Student Outstanding Dues Container -->
            <div id="pay-dues-wrapper" style="margin-top:1rem; display:none;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                <label class="form-label" style="margin:0;">المستحقات المعلقة على الطالب</label>
                <button type="button" id="btn-auto-allocate" class="btn btn-secondary btn-sm" style="font-size:0.75rem;">توزيع تلقائي للمبلغ</button>
              </div>
              <div id="pay-dues-list" style="max-height:220px; overflow-y:auto; border:1px solid var(--border); border-radius:var(--radius-sm); padding:0.5rem; background:#F8FAFC;">
              </div>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.75rem; margin-top:1rem;">
              <div class="form-group" style="margin:0;">
                <label class="form-label required">إجمالي المبلغ المحصل نقداً (ج.م)</label>
                <input type="number" step="0.01" min="0.01" id="pay-total-amount" class="form-input" placeholder="0.00" required>
              </div>

              <div class="form-group" style="margin:0;">
                <label class="form-label required">تاريخ التحصيل</label>
                <input type="date" id="pay-date" class="form-input" value="${today}" required>
              </div>
            </div>

            <div class="form-group" style="margin-top:0.75rem;">
              <label class="form-label">ملاحظات الإيصال (اختياري)</label>
              <input type="text" id="pay-notes" class="form-input" placeholder="مثال: سداد يدوي مع المساعد، دفعة مقدمة...">
            </div>

            <div id="pay-allocation-summary" style="margin-top:0.75rem; font-size:0.85rem; font-weight:600; color:var(--slate-600); display:flex; justify-content:space-between;">
              <span>المبلغ المخصص للمطالبات: <span id="pay-allocated-sum" style="color:var(--primary); font-weight:800;">0.00 ج.م</span></span>
              <span>المتبقي كرصيد غير مخصص: <span id="pay-unallocated-sum" style="color:#059669; font-weight:800;">0.00 ج.م</span></span>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="cancel-record-payment-btn">إلغاء</button>
            <button type="submit" class="btn btn-primary" id="submit-record-payment-btn">إصدار الإيصال وتأكيد الاستلام</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Receipt Voucher Modal -->
    <div id="receipt-modal" class="modal-overlay" style="display:none;">
      <div class="modal" style="max-width:550px;">
        <div class="modal-header">
          <h3 class="modal-title">إيصال استلام نقدية</h3>
          <button type="button" class="modal-close" id="close-receipt-modal">✕</button>
        </div>
        <div class="modal-body">
          <div class="receipt-box" id="printable-receipt">
            <div class="receipt-header">
              <div>
                <div style="font-weight:800; font-size:1.1rem; color:var(--slate-900);">نظام TeacherSystem</div>
                <div style="font-size:0.75rem; color:var(--slate-500);">إيصال تحصيل نقدية معتمد</div>
              </div>
              <div class="receipt-number" id="rec-number-val">RCP-202610-0000</div>
            </div>

            <div class="receipt-row">
              <span style="color:var(--slate-500);">اسم الطالب:</span>
              <span style="font-weight:700;" id="rec-student-val">—</span>
            </div>
            <div class="receipt-row">
              <span style="color:var(--slate-500);">تاريخ السداد:</span>
              <span class="tabular-nums" id="rec-date-val">—</span>
            </div>
            <div class="receipt-row">
              <span style="color:var(--slate-500);">المستلم:</span>
              <span id="rec-receiver-val">—</span>
            </div>
            <div class="receipt-row">
              <span style="color:var(--slate-500);">حالة الإيصال:</span>
              <span id="rec-status-val">—</span>
            </div>

            <div class="receipt-allocations" id="rec-allocations-wrapper">
              <div style="font-weight:700; margin-bottom:0.35rem; color:var(--slate-700);">توزيع المبلغ على المطالبات:</div>
              <table id="rec-allocations-table">
                <thead>
                  <tr>
                    <th>المطالبة</th>
                    <th>البيان</th>
                    <th style="text-align:left;">المبلغ</th>
                  </tr>
                </thead>
                <tbody id="rec-allocations-tbody"></tbody>
              </table>
            </div>

            <div class="receipt-total receipt-row">
              <span>إجمالي المبلغ المستلم:</span>
              <span id="rec-total-val" class="tabular-nums">0.00 ج.م</span>
            </div>

            <div id="rec-notes-wrapper" style="margin-top:0.75rem; font-size:0.8rem; color:var(--slate-500); display:none;">
              <span>ملاحظات: </span><span id="rec-notes-val"></span>
            </div>
          </div>
        </div>
        <div class="modal-footer" style="justify-content:space-between;">
          <button type="button" class="btn btn-secondary" id="btn-print-receipt">🖨️ طباعة الإيصال</button>
          <button type="button" class="btn btn-primary" id="btn-done-receipt">إغلاق ومتابعة</button>
        </div>
      </div>
    </div>

    <!-- Monthly Dues Generation Modal -->
    <div id="monthly-dues-modal" class="modal-overlay" style="display:none;">
      <div class="modal" style="max-width:550px;">
        <div class="modal-header">
          <h3 class="modal-title">توليد اشتراكات شهرية للمجموعة</h3>
          <button type="button" class="modal-close" id="close-monthly-dues-modal">✕</button>
        </div>
        <form id="monthly-dues-form">
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label required">المجموعة الدراسية</label>
              <select id="m-due-group-id" class="form-input" required>
                <option value="">-- اختر المجموعة --</option>
                ${state.groups.map(g => `
                  <option value="${g.id}">${g.name} (${g.grade_label})</option>
                `).join('')}
              </select>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.75rem;">
              <div class="form-group" style="margin:0;">
                <label class="form-label required">الشهر المستحق</label>
                <input type="month" id="m-due-month" class="form-input" value="${currentMonth}" required>
              </div>
              <div class="form-group" style="margin:0;">
                <label class="form-label required">تاريخ الاستحقاق</label>
                <input type="date" id="m-due-date" class="form-input" value="${today}" required>
              </div>
            </div>

            <!-- Preview Card -->
            <div id="m-due-preview-box" style="display:none; margin-top:1rem; padding:1rem; background:#F8FAFC; border:1px solid var(--border); border-radius:var(--radius-md);">
              <div style="font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">نتائج المعاينة الحسابية:</div>
              <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.5rem; font-size:0.85rem;">
                <div>الرسوم المعتمدة: <strong id="m-prev-fee" class="tabular-nums">—</strong></div>
                <div>الطلاب المؤهلون: <strong id="m-prev-eligible" class="tabular-nums">—</strong></div>
                <div>تم التوليد سابقاً: <strong id="m-prev-already" class="tabular-nums">—</strong></div>
                <div>سيتم توليدهم الآن: <strong id="m-prev-togen" class="tabular-nums" style="color:var(--primary);">—</strong></div>
              </div>
              <div style="margin-top:0.5rem; font-weight:800; color:var(--primary); font-size:0.95rem;">
                إجمالي قيمة المطالبات الجديدة: <span id="m-prev-total" class="tabular-nums">—</span>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="btn-preview-monthly">🔍 معاينة المستحقين</button>
            <button type="submit" class="btn btn-primary" id="btn-confirm-monthly" disabled>تأكيد وتوليد المطالبات</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Session Dues Generation Modal -->
    <div id="session-dues-modal" class="modal-overlay" style="display:none;">
      <div class="modal" style="max-width:550px;">
        <div class="modal-header">
          <h3 class="modal-title">توليد رسوم حصة دراسية منتهية</h3>
          <button type="button" class="modal-close" id="close-session-dues-modal">✕</button>
        </div>
        <form id="session-dues-form">
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label required">المجموعة الدراسية</label>
              <select id="s-due-group-id" class="form-input" required>
                <option value="">-- اختر المجموعة أولاً --</option>
                ${state.groups.map(g => `
                  <option value="${g.id}">${g.name} (${g.grade_label})</option>
                `).join('')}
              </select>
            </div>

            <div class="form-group">
              <label class="form-label required">الحصة المنتهية</label>
              <select id="s-due-session-id" class="form-input" required disabled>
                <option value="">-- اختر الحصة المنتهية --</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label required">تاريخ الاستحقاق</label>
              <input type="date" id="s-due-date" class="form-input" value="${today}" required>
            </div>

            <!-- Preview Card -->
            <div id="s-due-preview-box" style="display:none; margin-top:1rem; padding:1rem; background:#F8FAFC; border:1px solid var(--border); border-radius:var(--radius-md);">
              <div style="font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">نتائج المعاينة للحصة:</div>
              <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.5rem; font-size:0.85rem;">
                <div>الطلاب الحاضرون: <strong id="s-prev-attended" class="tabular-nums">—</strong></div>
                <div>تمت المطالبة سابقاً: <strong id="s-prev-already" class="tabular-nums">—</strong></div>
                <div>سيتم توليدهم الآن: <strong id="s-prev-togen" class="tabular-nums" style="color:var(--primary);">—</strong></div>
                <div>رسم الحصة للطالب: <strong id="s-prev-fee" class="tabular-nums">—</strong></div>
              </div>
              <div style="margin-top:0.5rem; font-weight:800; color:var(--primary); font-size:0.95rem;">
                إجمالي قيمة المطالبات الجديدة: <span id="s-prev-total" class="tabular-nums">—</span>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="btn-preview-session">🔍 معاينة الحضور</button>
            <button type="submit" class="btn btn-primary" id="btn-confirm-session" disabled>تأكيد وتوليد رسوم الحصة</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Group Fee Config Modal -->
    <div id="group-fee-modal" class="modal-overlay" style="display:none;">
      <div class="modal" style="max-width:500px;">
        <div class="modal-header">
          <h3 class="modal-title" id="group-fee-modal-title">ضبط رسوم المجموعة الدراسية</h3>
          <button type="button" class="modal-close" id="close-group-fee-modal">✕</button>
        </div>
        <form id="group-fee-form">
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label required">المجموعة الدراسية</label>
              <select id="fee-cfg-group-id" class="form-input" required>
                <option value="">-- اختر المجموعة --</option>
                ${state.groups.map(g => `
                  <option value="${g.id}">${g.name} (${g.grade_label})</option>
                `).join('')}
              </select>
            </div>

            <div class="form-group">
              <label class="form-label required">نظام المحاسبة والرسوم</label>
              <select id="fee-cfg-model" class="form-input" required>
                <option value="monthly">اشتراك شهري محدد (Monthly Subscription)</option>
                <option value="per_session">رسم بالحصة المنفردة (Per-Session Fee)</option>
              </select>
              <span class="form-hint">يحدد طريقة احتساب المستحقات للطلاب المقيدين في هذه المجموعة</span>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.75rem;">
              <div class="form-group" style="margin:0;">
                <label class="form-label required">قيمة الرسم (ج.م)</label>
                <input type="number" step="0.01" min="0.01" id="fee-cfg-amount" class="form-input" placeholder="مثال: 250.00" required>
              </div>
              <div class="form-group" style="margin:0;">
                <label class="form-label required">تاريخ السريان</label>
                <input type="date" id="fee-cfg-effective" class="form-input" value="${today}" required>
              </div>
            </div>

            <div class="form-group" style="margin-top:0.75rem;">
              <label class="form-label">ملاحظات (اختياري)</label>
              <input type="text" id="fee-cfg-notes" class="form-input" placeholder="مثال: رسوم الفصل الدراسي الأول...">
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="cancel-group-fee-btn">إلغاء</button>
            <button type="submit" class="btn btn-primary" id="save-group-fee-btn">حفظ وتفعيل الرسوم</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Reverse Payment Modal -->
    <div id="reverse-payment-modal" class="modal-overlay" style="display:none;">
      <div class="modal" style="max-width:480px;">
        <div class="modal-header">
          <h3 class="modal-title">استرداد وإلغاء إيصال نقدية</h3>
          <button type="button" class="modal-close" id="close-reverse-modal">✕</button>
        </div>
        <form id="reverse-payment-form">
          <div class="modal-body">
            <div style="padding:0.75rem; background:#FEF2F2; border:1px solid #FECACA; border-radius:var(--radius-sm); margin-bottom:1rem; font-size:0.85rem; color:#991B1B;">
              <strong>تنبيه مالي مهم:</strong> سيتم إلغاء الإيصال المالي رقم (<span id="reverse-rec-num" style="font-family:monospace; font-weight:800;"></span>) واسترداد النقدية، وإرجاع المبالغ المخصصة للمستحقات لتعود غير مسددة، مع توثيق العملية في سجل التدقيق المالي.
            </div>

            <div class="form-group">
              <label class="form-label required">سبب الاسترداد / الإلغاء</label>
              <textarea id="reverse-reason" class="form-input" rows="3" placeholder="يرجى كتابة سبب الإلغاء بدقة (مثل: إدخال بالخطأ، استرداد الطالب للمبلغ...)" required minlength="3"></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="cancel-reverse-btn">إلغاء</button>
            <button type="submit" class="btn btn-primary" style="background:#DC2626; border-color:#DC2626;" id="confirm-reverse-btn">تأكيد الاسترداد والإلغاء</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Void Due Modal -->
    <div id="void-due-modal" class="modal-overlay" style="display:none;">
      <div class="modal" style="max-width:480px;">
        <div class="modal-header">
          <h3 class="modal-title">إلغاء مطالبة مالية (Void Due)</h3>
          <button type="button" class="modal-close" id="close-void-due-modal">✕</button>
        </div>
        <form id="void-due-form">
          <div class="modal-body">
            <div style="padding:0.75rem; background:#FFFBEB; border:1px solid #FDE68A; border-radius:var(--radius-sm); margin-bottom:1rem; font-size:0.85rem; color:#92400E;">
              <strong>تنبيه:</strong> لا يمكن إلغاء المطالبة إلا إذا كانت غير مسددة بالكامل. سيتم إسقاط المطالبة من حساب الطالب وتسجيل سبب الإلغاء في سجل التدقيق.
            </div>

            <div class="form-group">
              <label class="form-label required">سبب إلغاء المطالبة</label>
              <textarea id="void-due-reason" class="form-input" rows="3" placeholder="يرجى كتابة سبب الإلغاء (مثل: إعفاء الطالب بقرار من الأستاذ، خطأ في التوليد...)" required minlength="3"></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="cancel-void-due-btn">تراجع</button>
            <button type="submit" class="btn btn-primary" style="background:#DC2626; border-color:#DC2626;" id="confirm-void-due-btn">تأكيد إلغاء المطالبة</button>
          </div>
        </form>
      </div>
    </div>
  `;
}

// ==========================================================================
// --- Finance Event Binding ---
// ==========================================================================

function bindFinanceEvents(queryParams) {
  // Tab switching
  ['overview', 'payments', 'dues', 'configs', 'reports'].forEach(tab => {
    const btn = document.getElementById(`f-tab-${tab}`);
    if (btn) {
      btn.addEventListener('click', () => {
        state.financeTab = tab;
        navigate();
      });
    }
  });

  const btnSeeAll = document.getElementById('btn-see-all-payments');
  if (btnSeeAll) {
    btnSeeAll.addEventListener('click', () => {
      state.financeTab = 'payments';
      navigate();
    });
  }

  // --- Modal Openers ---
  const openPayBtn = document.getElementById('open-record-payment-btn');
  const openPayBtnTab = document.getElementById('open-record-payment-btn-tab');
  const quickPayBtn = document.getElementById('quick-record-payment-btn');
  const payModal = document.getElementById('record-payment-modal');

  const openPaymentModal = () => {
    if (payModal) {
      document.getElementById('record-payment-form').reset();
      document.getElementById('pay-dues-wrapper').style.display = 'none';
      document.getElementById('pay-allocated-sum').textContent = '0.00 ج.م';
      document.getElementById('pay-unallocated-sum').textContent = '0.00 ج.م';
      payModal.style.display = 'flex';
    }
  };

  if (openPayBtn) openPayBtn.addEventListener('click', openPaymentModal);
  if (openPayBtnTab) openPayBtnTab.addEventListener('click', openPaymentModal);
  if (quickPayBtn) quickPayBtn.addEventListener('click', openPaymentModal);

  const closePayModal = () => {
    if (payModal) payModal.style.display = 'none';
  };
  const closePayBtn = document.getElementById('close-record-payment-modal');
  const cancelPayBtn = document.getElementById('cancel-record-payment-btn');
  if (closePayBtn) closePayBtn.addEventListener('click', closePayModal);
  if (cancelPayBtn) cancelPayBtn.addEventListener('click', closePayModal);

  // Student selection in payment modal -> load outstanding dues
  const payStudentSelect = document.getElementById('pay-student-select');
  if (payStudentSelect) {
    payStudentSelect.addEventListener('change', async (e) => {
      const studentId = e.target.value;
      const duesWrapper = document.getElementById('pay-dues-wrapper');
      const duesList = document.getElementById('pay-dues-list');
      if (!studentId) {
        duesWrapper.style.display = 'none';
        return;
      }

      duesList.innerHTML = '<div style="text-align:center; padding:1rem; color:var(--slate-400);">جارٍ تحميل المستحقات...</div>';
      duesWrapper.style.display = 'block';

      try {
        const allDues = await api.listStudentDues({ student_id: studentId });
        state.pendingPaymentStudentDues = allDues.filter(d => d.status === 'unpaid' || d.status === 'partially_paid');

        if (state.pendingPaymentStudentDues.length === 0) {
          duesList.innerHTML = `
            <div style="text-align:center; padding:1rem; color:var(--slate-500); font-size:0.85rem;">
              لا توجد مستحقات معلقة على هذا الطالب. يمكنك تحصيل دفعة مقدمة بالكامل.
            </div>
          `;
        } else {
          duesList.innerHTML = state.pendingPaymentStudentDues.map(d => `
            <div class="allocation-item" data-due-id="${d.id}">
              <div style="flex:1;">
                <div style="font-weight:700; font-size:0.85rem;">${d.group_name} — ${getChargeTypeBadge(d.charge_type)}</div>
                <div style="font-size:0.75rem; color:var(--slate-500);">${d.billing_month || 'حصة دراسية'} | الإجمالي: ${d.amount_egp.toFixed(2)} ج.م | المسدد: ${d.paid_amount_egp.toFixed(2)} ج.م</div>
              </div>
              <div style="display:flex; align-items:center; gap:0.5rem;">
                <span style="font-size:0.78rem; font-weight:700; color:#DC2626;">المتبقي: ${d.remaining_egp.toFixed(2)} ج.م</span>
                <input type="number" step="0.01" min="0" max="${d.remaining_egp}" class="allocation-input alloc-field" data-due-id="${d.id}" data-remaining="${d.remaining_egp}" value="0.00">
              </div>
            </div>
          `).join('');

          // Bind change on allocation inputs
          document.querySelectorAll('.alloc-field').forEach(inp => {
            inp.addEventListener('input', updateAllocationSummary);
          });
        }
        updateAllocationSummary();
      } catch (err) {
        duesList.innerHTML = `<div style="color:#DC2626; padding:0.5rem;">تعذر تحميل المستحقات: ${err.message}</div>`;
      }
    });
  }

  // Auto-allocate button
  const autoAllocBtn = document.getElementById('btn-auto-allocate');
  if (autoAllocBtn) {
    autoAllocBtn.addEventListener('click', () => {
      const totalAmount = parseFloat(document.getElementById('pay-total-amount').value) || 0;
      let remainingToAlloc = totalAmount;

      document.querySelectorAll('.alloc-field').forEach(inp => {
        const remainingOnDue = parseFloat(inp.dataset.remaining) || 0;
        if (remainingToAlloc <= 0) {
          inp.value = '0.00';
        } else if (remainingToAlloc >= remainingOnDue) {
          inp.value = remainingOnDue.toFixed(2);
          remainingToAlloc -= remainingOnDue;
        } else {
          inp.value = remainingToAlloc.toFixed(2);
          remainingToAlloc = 0;
        }
      });
      updateAllocationSummary();
    });
  }

  const payTotalInput = document.getElementById('pay-total-amount');
  if (payTotalInput) {
    payTotalInput.addEventListener('input', updateAllocationSummary);
  }

  function updateAllocationSummary() {
    let totalAlloc = 0;
    document.querySelectorAll('.alloc-field').forEach(inp => {
      totalAlloc += (parseFloat(inp.value) || 0);
    });
    const totalAmount = parseFloat(document.getElementById('pay-total-amount')?.value) || 0;
    const unalloc = Math.max(0, totalAmount - totalAlloc);

    const allocSumEl = document.getElementById('pay-allocated-sum');
    const unallocSumEl = document.getElementById('pay-unallocated-sum');
    if (allocSumEl) allocSumEl.textContent = `${totalAlloc.toFixed(2)} ج.م`;
    if (unallocSumEl) unallocSumEl.textContent = `${unalloc.toFixed(2)} ج.م`;
  }

  // Payment Form Submit
  const payForm = document.getElementById('record-payment-form');
  if (payForm) {
    payForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const studentId = parseInt(document.getElementById('pay-student-select').value);
      const totalAmount = parseFloat(document.getElementById('pay-total-amount').value);
      const paymentDate = document.getElementById('pay-date').value;
      const notes = document.getElementById('pay-notes').value.trim();

      if (!studentId || !totalAmount || totalAmount <= 0) {
        showToast('يرجى تحديد الطالب وإدخال مبلغ تحصيل صحيح.', 'error');
        return;
      }

      // Collect allocations
      const allocations = [];
      let allocSum = 0;
      document.querySelectorAll('.alloc-field').forEach(inp => {
        const val = parseFloat(inp.value) || 0;
        if (val > 0) {
          allocSum += val;
          allocations.push({
            due_id: parseInt(inp.dataset.dueId),
            amount_egp: val
          });
        }
      });

      if (allocSum > totalAmount + 0.001) {
        showToast('مجموع المبالغ الموزعة يتجاوز إجمالي المبلغ المحصل!', 'error');
        return;
      }

      const submitBtn = document.getElementById('submit-record-payment-btn');
      submitBtn.disabled = true;
      submitBtn.textContent = 'جارٍ تسجيل النقدية وإصدار الإيصال...';

      try {
        const receipt = await api.recordCashPayment({
          student_id: studentId,
          amount_egp: totalAmount,
          payment_date: paymentDate,
          notes: notes || null,
          allocations: allocations
        });

        showToast(`تم تسجيل التحصيل بنجاح! رقم الإيصال: ${receipt.receipt_number}`, 'success');
        closePayModal();
        displayReceiptModal(receipt);
        // Refresh overview and tables in background
        state.financeOverview = await api.getFinanceOverview();
        state.payments = await api.listCashPayments(state.paymentFilters);
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'إصدار الإيصال وتأكيد الاستلام';
      }
    });
  }

  // --- Receipt Modal Display Helper ---
  function displayReceiptModal(p) {
    const rModal = document.getElementById('receipt-modal');
    if (!rModal) return;

    document.getElementById('rec-number-val').textContent = p.receipt_number;
    document.getElementById('rec-student-val').textContent = p.student_name;
    document.getElementById('rec-date-val').textContent = p.payment_date;
    document.getElementById('rec-receiver-val').textContent = p.created_by_name;
    document.getElementById('rec-status-val').innerHTML = p.is_reversed ? '<span class="badge badge-reversed">ملغي ومسترد</span>' : '<span class="badge badge-paid">معتمد</span>';
    document.getElementById('rec-total-val').textContent = p.formatted_amount;

    const notesWrapper = document.getElementById('rec-notes-wrapper');
    if (p.notes) {
      notesWrapper.style.display = 'block';
      document.getElementById('rec-notes-val').textContent = p.notes;
    } else {
      notesWrapper.style.display = 'none';
    }

    const tbody = document.getElementById('rec-allocations-tbody');
    if (p.allocations && p.allocations.length > 0) {
      document.getElementById('rec-allocations-wrapper').style.display = 'block';
      tbody.innerHTML = p.allocations.map(a => `
        <tr>
          <td>${a.charge_type === 'monthly_fee' ? 'اشتراك شهري' : 'رسم بالحصة'}</td>
          <td>${a.billing_month || 'حصة'}</td>
          <td class="tabular-nums" style="text-align:left; font-weight:700;">${a.allocated_amount_egp.toFixed(2)} ج.م</td>
        </tr>
      `).join('');
    } else {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:var(--slate-400);">دفعة رصيد غير مخصصة لمطالبات معينة</td></tr>';
    }

    rModal.style.display = 'flex';
  }

  const closeReceiptBtn = document.getElementById('close-receipt-modal');
  const doneReceiptBtn = document.getElementById('btn-done-receipt');
  const printReceiptBtn = document.getElementById('btn-print-receipt');
  const receiptModal = document.getElementById('receipt-modal');

  if (closeReceiptBtn) closeReceiptBtn.addEventListener('click', () => { if (receiptModal) receiptModal.style.display = 'none'; navigate(); });
  if (doneReceiptBtn) doneReceiptBtn.addEventListener('click', () => { if (receiptModal) receiptModal.style.display = 'none'; navigate(); });
  if (printReceiptBtn) printReceiptBtn.addEventListener('click', () => { window.print(); });

  // View Receipt from table
  document.querySelectorAll('.view-receipt-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = parseInt(e.currentTarget.dataset.id);
      try {
        const p = await api.getPaymentDetails(id);
        displayReceiptModal(p);
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  // Reverse Payment Modal
  const revModal = document.getElementById('reverse-payment-modal');
  const closeRevBtn = document.getElementById('close-reverse-modal');
  const cancelRevBtn = document.getElementById('cancel-reverse-btn');
  const closeRevModal = () => { if (revModal) revModal.style.display = 'none'; state.reversingPaymentId = null; };
  if (closeRevBtn) closeRevBtn.addEventListener('click', closeRevModal);
  if (cancelRevBtn) cancelRevBtn.addEventListener('click', closeRevModal);

  document.querySelectorAll('.reverse-payment-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const id = parseInt(e.currentTarget.dataset.id);
      const rec = e.currentTarget.dataset.rec;
      state.reversingPaymentId = id;
      document.getElementById('reverse-rec-num').textContent = rec;
      document.getElementById('reverse-payment-form').reset();
      if (revModal) revModal.style.display = 'flex';
    });
  });

  const revForm = document.getElementById('reverse-payment-form');
  if (revForm) {
    revForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!state.reversingPaymentId) return;
      const reason = document.getElementById('reverse-reason').value.trim();
      const confirmBtn = document.getElementById('confirm-reverse-btn');
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'جارٍ إلغاء الإيصال...';

      try {
        await api.reversePayment(state.reversingPaymentId, { reason });
        showToast('تم استرداد وإلغاء الإيصال بنجاح وإرجاع أرصدة المستحقات.', 'success');
        closeRevModal();
        navigate();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'تأكيد الاسترداد والإلغاء';
      }
    });
  }

  // --- Monthly Dues Generation ---
  const mModal = document.getElementById('monthly-dues-modal');
  const openMBtn = document.getElementById('open-monthly-dues-btn');
  const openMBtn2 = document.getElementById('open-gen-monthly-btn');
  const quickMBtn = document.getElementById('quick-gen-monthly-btn');
  const openMonthlyModal = () => {
    if (mModal) {
      document.getElementById('monthly-dues-form').reset();
      document.getElementById('m-due-preview-box').style.display = 'none';
      document.getElementById('btn-confirm-monthly').disabled = true;
      mModal.style.display = 'flex';
    }
  };
  if (openMBtn) openMBtn.addEventListener('click', openMonthlyModal);
  if (openMBtn2) openMBtn2.addEventListener('click', openMonthlyModal);
  if (quickMBtn) quickMBtn.addEventListener('click', openMonthlyModal);

  const closeMBtn = document.getElementById('close-monthly-dues-modal');
  if (closeMBtn) closeMBtn.addEventListener('click', () => { if (mModal) mModal.style.display = 'none'; });

  const btnPreviewMonthly = document.getElementById('btn-preview-monthly');
  if (btnPreviewMonthly) {
    btnPreviewMonthly.addEventListener('click', async () => {
      const groupId = parseInt(document.getElementById('m-due-group-id').value);
      const billingMonth = document.getElementById('m-due-month').value;
      const dueDate = document.getElementById('m-due-date').value;

      if (!groupId || !billingMonth) {
        showToast('يرجى اختيار المجموعة وتحديد شهر الاستحقاق.', 'warning');
        return;
      }

      btnPreviewMonthly.disabled = true;
      btnPreviewMonthly.textContent = 'جارٍ الحساب...';

      try {
        const prev = await api.previewMonthlyDues({
          group_id: groupId,
          billing_month: billingMonth,
          due_date: dueDate || null
        });

        document.getElementById('m-prev-fee').textContent = `${prev.fee_amount_egp.toFixed(2)} ج.م`;
        document.getElementById('m-prev-eligible').textContent = prev.eligible_students_count;
        document.getElementById('m-prev-already').textContent = prev.already_generated_count;
        document.getElementById('m-prev-togen').textContent = prev.to_be_generated_count;
        document.getElementById('m-prev-total').textContent = `${prev.total_amount_egp.toFixed(2)} ج.م`;
        document.getElementById('m-due-preview-box').style.display = 'block';

        const confirmBtn = document.getElementById('btn-confirm-monthly');
        confirmBtn.disabled = prev.to_be_generated_count === 0;
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        btnPreviewMonthly.disabled = false;
        btnPreviewMonthly.textContent = '🔍 معاينة المستحقين';
      }
    });
  }

  const mForm = document.getElementById('monthly-dues-form');
  if (mForm) {
    mForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const groupId = parseInt(document.getElementById('m-due-group-id').value);
      const billingMonth = document.getElementById('m-due-month').value;
      const dueDate = document.getElementById('m-due-date').value;

      const confirmBtn = document.getElementById('btn-confirm-monthly');
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'جارٍ توليد المطالبات...';

      try {
        const res = await api.generateMonthlyDues({
          group_id: groupId,
          billing_month: billingMonth,
          due_date: dueDate || null
        });

        showToast(`تم توليد ${res.generated_count} مطالبة بنجاح بإجمالي ${res.total_amount_egp.toFixed(2)} ج.م!`, 'success');
        if (mModal) mModal.style.display = 'none';
        navigate();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'تأكيد وتوليد المطالبات';
      }
    });
  }

  // --- Session Dues Generation ---
  const sModal = document.getElementById('session-dues-modal');
  const openSBtn = document.getElementById('open-session-dues-btn');
  const openSBtn2 = document.getElementById('open-gen-session-btn');
  const quickSBtn = document.getElementById('quick-gen-session-btn');
  const openSessionModal = () => {
    if (sModal) {
      document.getElementById('session-dues-form').reset();
      document.getElementById('s-due-session-id').innerHTML = '<option value="">-- اختر الحصة المنتهية --</option>';
      document.getElementById('s-due-session-id').disabled = true;
      document.getElementById('s-due-preview-box').style.display = 'none';
      document.getElementById('btn-confirm-session').disabled = true;
      sModal.style.display = 'flex';
    }
  };
  if (openSBtn) openSBtn.addEventListener('click', openSessionModal);
  if (openSBtn2) openSBtn2.addEventListener('click', openSessionModal);
  if (quickSBtn) quickSBtn.addEventListener('click', openSessionModal);

  const closeSBtn = document.getElementById('close-session-dues-modal');
  if (closeSBtn) closeSBtn.addEventListener('click', () => { if (sModal) sModal.style.display = 'none'; });

  // When group changes in session dues modal, fetch completed sessions
  const sGroupSelect = document.getElementById('s-due-group-id');
  if (sGroupSelect) {
    sGroupSelect.addEventListener('change', async (e) => {
      const gid = e.target.value;
      const sSelect = document.getElementById('s-due-session-id');
      if (!gid) {
        sSelect.disabled = true;
        sSelect.innerHTML = '<option value="">-- اختر الحصة المنتهية --</option>';
        return;
      }
      sSelect.disabled = true;
      sSelect.innerHTML = '<option value="">جارٍ تحميل الحصص المنتهية...</option>';

      try {
        const sessList = await api.listSessions({ group_id: gid, status: 'completed' });
        if (sessList.length === 0) {
          sSelect.innerHTML = '<option value="">لا توجد حصص منتهية مسجلة لهذه المجموعة</option>';
        } else {
          sSelect.innerHTML = '<option value="">-- اختر الحصة المنتهية --</option>' +
            sessList.map(s => `
              <option value="${s.id}">حصة ${s.session_date} — ${s.topic || 'بدون عنوان'}</option>
            `).join('');
          sSelect.disabled = false;
        }
      } catch (err) {
        sSelect.innerHTML = `<option value="">خطأ: ${err.message}</option>`;
      }
    });
  }

  const btnPreviewSession = document.getElementById('btn-preview-session');
  if (btnPreviewSession) {
    btnPreviewSession.addEventListener('click', async () => {
      const sessionId = parseInt(document.getElementById('s-due-session-id').value);
      const dueDate = document.getElementById('s-due-date').value;

      if (!sessionId) {
        showToast('يرجى اختيار حصة دراسية منتهية أولاً.', 'warning');
        return;
      }

      btnPreviewSession.disabled = true;
      btnPreviewSession.textContent = 'جارٍ الحساب...';

      try {
        const prev = await api.previewSessionDues(sessionId);

        document.getElementById('s-prev-attended').textContent = prev.attended_students_count;
        document.getElementById('s-prev-already').textContent = prev.already_generated_count;
        document.getElementById('s-prev-togen').textContent = prev.to_be_generated_count;
        document.getElementById('s-prev-fee').textContent = `${prev.fee_amount_egp.toFixed(2)} ج.م`;
        document.getElementById('s-prev-total').textContent = `${prev.total_amount_egp.toFixed(2)} ج.م`;
        document.getElementById('s-due-preview-box').style.display = 'block';

        const confirmBtn = document.getElementById('btn-confirm-session');
        confirmBtn.disabled = prev.to_be_generated_count === 0;
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        btnPreviewSession.disabled = false;
        btnPreviewSession.textContent = '🔍 معاينة الحضور';
      }
    });
  }

  const sForm = document.getElementById('session-dues-form');
  if (sForm) {
    sForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const sessionId = parseInt(document.getElementById('s-due-session-id').value);
      const dueDate = document.getElementById('s-due-date').value;

      const confirmBtn = document.getElementById('btn-confirm-session');
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'جارٍ توليد رسوم الحصة...';

      try {
        const res = await api.generateSessionDues({
          session_id: sessionId,
          due_date: dueDate || null
        });

        showToast(`تم توليد ${res.generated_count} مطالبة بنجاح بإجمالي ${res.total_amount_egp.toFixed(2)} ج.م!`, 'success');
        if (sModal) sModal.style.display = 'none';
        navigate();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'تأكيد وتوليد رسوم الحصة';
      }
    });
  }

  // --- Group Fee Config Modal ---
  const feeModal = document.getElementById('group-fee-modal');
  const openFeeBtn = document.getElementById('open-group-fee-modal-btn');
  const quickFeeBtn = document.getElementById('quick-set-fee-btn');
  const closeFeeBtn = document.getElementById('close-group-fee-modal');
  const cancelFeeBtn = document.getElementById('cancel-group-fee-btn');

  const openFeeConfigModal = (groupId = null) => {
    if (feeModal) {
      document.getElementById('group-fee-form').reset();
      if (groupId) {
        document.getElementById('fee-cfg-group-id').value = groupId;
      }
      feeModal.style.display = 'flex';
    }
  };
  if (openFeeBtn) openFeeBtn.addEventListener('click', () => openFeeConfigModal());
  if (quickFeeBtn) quickFeeBtn.addEventListener('click', () => openFeeConfigModal());
  if (closeFeeBtn) closeFeeBtn.addEventListener('click', () => { if (feeModal) feeModal.style.display = 'none'; });
  if (cancelFeeBtn) cancelFeeBtn.addEventListener('click', () => { if (feeModal) feeModal.style.display = 'none'; });

  document.querySelectorAll('.edit-group-fee-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const gid = parseInt(e.currentTarget.dataset.groupId);
      openFeeConfigModal(gid);
    });
  });

  const feeForm = document.getElementById('group-fee-form');
  if (feeForm) {
    feeForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const groupId = parseInt(document.getElementById('fee-cfg-group-id').value);
      const feeModel = document.getElementById('fee-cfg-model').value;
      const amount = parseFloat(document.getElementById('fee-cfg-amount').value);
      const effectiveFrom = document.getElementById('fee-cfg-effective').value;
      const notes = document.getElementById('fee-cfg-notes').value.trim();

      const saveBtn = document.getElementById('save-group-fee-btn');
      saveBtn.disabled = true;
      saveBtn.textContent = 'جارٍ الحفظ...';

      try {
        await api.createFeeConfig({
          group_id: groupId,
          fee_model: feeModel,
          amount_egp: amount,
          effective_from: effectiveFrom,
          notes: notes || null
        });

        showToast('تم ضبط رسوم المجموعة بنجاح وتفعيلها للنظام!', 'success');
        if (feeModal) feeModal.style.display = 'none';
        navigate();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'حفظ وتفعيل الرسوم';
      }
    });
  }

  // --- Void Due Modal ---
  const voidModal = document.getElementById('void-due-modal');
  const closeVoidBtn = document.getElementById('close-void-due-modal');
  const cancelVoidBtn = document.getElementById('cancel-void-due-btn');
  const closeVoidModal = () => { if (voidModal) voidModal.style.display = 'none'; state.voidingDueId = null; };
  if (closeVoidBtn) closeVoidBtn.addEventListener('click', closeVoidModal);
  if (cancelVoidBtn) cancelVoidBtn.addEventListener('click', closeVoidModal);

  document.querySelectorAll('.void-due-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const id = parseInt(e.currentTarget.dataset.id);
      state.voidingDueId = id;
      document.getElementById('void-due-form').reset();
      if (voidModal) voidModal.style.display = 'flex';
    });
  });

  const voidForm = document.getElementById('void-due-form');
  if (voidForm) {
    voidForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!state.voidingDueId) return;
      const reason = document.getElementById('void-due-reason').value.trim();
      const confirmBtn = document.getElementById('confirm-void-due-btn');
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'جارٍ إلغاء المطالبة...';

      try {
        await api.voidStudentDue(state.voidingDueId, { reason });
        showToast('تم إلغاء المطالبة المالية بنجاح.', 'success');
        closeVoidModal();
        navigate();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'تأكيد إلغاء المطالبة';
      }
    });
  }

  // --- Filters in Payments Tab ---
  const filterPayBtn = document.getElementById('filter-payments-btn');
  if (filterPayBtn) {
    filterPayBtn.addEventListener('click', () => {
      state.paymentFilters = {
        student_id: document.getElementById('filter-pay-student')?.value || '',
        start_date: document.getElementById('filter-pay-start-date')?.value || '',
        end_date: document.getElementById('filter-pay-end-date')?.value || '',
        include_reversed: document.getElementById('filter-pay-reversed')?.checked ? 'true' : 'false'
      };
      navigate();
    });
  }

  const resetPayBtn = document.getElementById('reset-payments-btn');
  if (resetPayBtn) {
    resetPayBtn.addEventListener('click', () => {
      state.paymentFilters = { student_id: '', start_date: '', end_date: '', include_reversed: 'false' };
      navigate();
    });
  }

  // --- Filters in Dues Tab ---
  const filterDuesBtn = document.getElementById('filter-dues-btn');
  if (filterDuesBtn) {
    filterDuesBtn.addEventListener('click', () => {
      state.dueFilters = {
        group_id: document.getElementById('filter-due-group')?.value || '',
        student_id: document.getElementById('filter-due-student')?.value || '',
        charge_type: document.getElementById('filter-due-charge-type')?.value || '',
        status: document.getElementById('filter-due-status')?.value || '',
        billing_month: document.getElementById('filter-due-month')?.value || ''
      };
      navigate();
    });
  }

  const resetDuesBtn = document.getElementById('reset-dues-btn');
  if (resetDuesBtn) {
    resetDuesBtn.addEventListener('click', () => {
      state.dueFilters = { student_id: '', group_id: '', status: '', charge_type: '', billing_month: '' };
      navigate();
    });
  }

  // --- Reports Tab Handlers ---
  // 1. Student Ledger
  const repStudentSelect = document.getElementById('report-student-select');
  if (repStudentSelect) {
    repStudentSelect.addEventListener('change', async (e) => {
      const sid = e.target.value;
      const resContainer = document.getElementById('student-ledger-result');
      if (!sid) {
        resContainer.style.display = 'none';
        return;
      }
      resContainer.innerHTML = '<div style="text-align:center; padding:1.5rem; color:var(--slate-400);">جارٍ استخراج كشف الحساب...</div>';
      resContainer.style.display = 'block';

      try {
        const prof = await api.getStudentFinancialProfile(sid);
        resContainer.innerHTML = `
          <div style="background:#F8FAFC; border:1px solid var(--border); border-radius:var(--radius-md); padding:1rem; margin-bottom:1rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
              <div>
                <div style="font-weight:800; font-size:1.1rem; color:var(--slate-900);">${prof.student_name}</div>
                <div style="font-size:0.8rem; color:var(--slate-500);">${prof.grade_label} | هاتف الطالب: ${prof.student_phone || '-'} | ولي الأمر: ${prof.parent_phone || '-'}</div>
              </div>
              <div style="display:flex; gap:1rem; text-align:center;">
                <div style="background:#FFF; padding:0.5rem 0.75rem; border-radius:var(--radius-sm); border:1px solid var(--border);">
                  <div style="font-size:0.75rem; color:var(--slate-400);">إجمالي المطالبات</div>
                  <div style="font-weight:800; color:var(--primary);" class="tabular-nums">${prof.total_dues_egp.toFixed(2)} ج.م</div>
                </div>
                <div style="background:#FFF; padding:0.5rem 0.75rem; border-radius:var(--radius-sm); border:1px solid var(--border);">
                  <div style="font-size:0.75rem; color:var(--slate-400);">إجمالي المسدد</div>
                  <div style="font-weight:800; color:#059669;" class="tabular-nums">${prof.total_paid_egp.toFixed(2)} ج.م</div>
                </div>
                <div style="background:#FFF; padding:0.5rem 0.75rem; border-radius:var(--radius-sm); border:1px solid var(--border);">
                  <div style="font-size:0.75rem; color:var(--slate-400);">الرصيد المتبقي</div>
                  <div style="font-weight:800; color:${prof.current_balance_egp > 0 ? '#DC2626' : '#059669'};" class="tabular-nums">
                    ${prof.current_balance_egp.toFixed(2)} ج.م
                  </div>
                </div>
              </div>
            </div>
          </div>

          <h3 style="font-size:0.95rem; font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">سجل المطالبات المالية:</h3>
          <div class="table-responsive" style="margin-bottom:1rem;">
            <table class="data-table">
              <thead>
                <tr>
                  <th>المجموعة</th>
                  <th>نوع الرسم</th>
                  <th>الشهر / الحصة</th>
                  <th>القيمة</th>
                  <th>المسدد</th>
                  <th>المتبقي</th>
                  <th>الحالة</th>
                </tr>
              </thead>
              <tbody>
                ${prof.dues.length === 0 ? '<tr><td colspan="7" style="text-align:center; color:var(--slate-400);">لا توجد مطالبات</td></tr>' : prof.dues.map(d => `
                  <tr>
                    <td>${d.group_name}</td>
                    <td>${getChargeTypeBadge(d.charge_type)}</td>
                    <td>${d.billing_month || 'حصة دراسية'}</td>
                    <td class="tabular-nums">${d.amount_egp.toFixed(2)} ج.م</td>
                    <td class="tabular-nums">${d.paid_amount_egp.toFixed(2)} ج.م</td>
                    <td class="tabular-nums" style="font-weight:700; color:${d.remaining_egp > 0 ? '#DC2626' : '#059669'};">${d.remaining_egp.toFixed(2)} ج.م</td>
                    <td>${getDueStatusBadge(d.status)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>

          <h3 style="font-size:0.95rem; font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">سجل الإيصالات والمدفوعات:</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>رقم الإيصال</th>
                  <th>التاريخ</th>
                  <th>المبلغ</th>
                  <th>الحالة</th>
                  <th>ملاحظات</th>
                </tr>
              </thead>
              <tbody>
                ${prof.payments.length === 0 ? '<tr><td colspan="5" style="text-align:center; color:var(--slate-400);">لا توجد مدفوعات</td></tr>' : prof.payments.map(p => `
                  <tr>
                    <td class="tabular-nums" style="font-family:monospace; font-weight:700; color:var(--primary);">${p.receipt_number}</td>
                    <td class="tabular-nums">${p.payment_date}</td>
                    <td class="tabular-nums" style="font-weight:700;">${p.formatted_amount}</td>
                    <td>${p.is_reversed ? '<span class="badge badge-reversed">ملغي ومسترد</span>' : '<span class="badge badge-paid">معتمد</span>'}</td>
                    <td style="font-size:0.8rem; color:var(--slate-500);">${p.notes || '-'}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
      } catch (err) {
        resContainer.innerHTML = `<div style="color:#DC2626; padding:1rem;">تعذر استخراج كشف الحساب: ${err.message}</div>`;
      }
    });
  }

  // 2. Group Summary
  const repGroupSelect = document.getElementById('report-group-select');
  if (repGroupSelect) {
    repGroupSelect.addEventListener('change', async (e) => {
      const gid = e.target.value;
      const resContainer = document.getElementById('group-summary-result');
      if (!gid) {
        resContainer.style.display = 'none';
        return;
      }
      resContainer.innerHTML = '<div style="text-align:center; padding:1.5rem; color:var(--slate-400);">جارٍ استخراج ملخص المجموعة...</div>';
      resContainer.style.display = 'block';

      try {
        const sum = await api.getGroupCollectionSummary(gid);
        resContainer.innerHTML = `
          <div class="finance-metrics-grid" style="margin-bottom:1rem;">
            <div class="finance-metric-card">
              <div class="metric-header"><span>الطلاب المسجلون</span>${icons.users}</div>
              <div class="metric-val">${sum.enrolled_students_count}</div>
            </div>
            <div class="finance-metric-card">
              <div class="metric-header"><span>إجمالي المطالبات</span>${icons.cash}</div>
              <div class="metric-val money-accent">${sum.total_billed_egp.toFixed(2)} ج.م</div>
            </div>
            <div class="finance-metric-card">
              <div class="metric-header"><span>إجمالي المحصل</span>${icons.check}</div>
              <div class="metric-val money-rate">${sum.total_collected_egp.toFixed(2)} ج.م</div>
            </div>
            <div class="finance-metric-card">
              <div class="metric-header"><span>المتبقي ونسبة التحصيل</span>${icons.analytics}</div>
              <div class="metric-val money-due">${sum.total_outstanding_egp.toFixed(2)} ج.م</div>
              <div class="metric-sub">نسبة التحصيل: ${sum.collection_rate_percent.toFixed(1)}%</div>
            </div>
          </div>

          <h3 style="font-size:0.95rem; font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">تفاصيل أرصدة طلاب المجموعة:</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>اسم الطالب</th>
                  <th>الهاتف</th>
                  <th>إجمالي المطالبات</th>
                  <th>المسدد</th>
                  <th>المتبقي</th>
                  <th>الحالة</th>
                </tr>
              </thead>
              <tbody>
                ${sum.students_summary.length === 0 ? '<tr><td colspan="6" style="text-align:center; color:var(--slate-400);">لا يوجد طلاب مسجلون</td></tr>' : sum.students_summary.map(s => `
                  <tr>
                    <td style="font-weight:700;">${s.student_name}</td>
                    <td class="tabular-nums">${s.student_phone || '-'}</td>
                    <td class="tabular-nums">${s.total_dues_egp.toFixed(2)} ج.م</td>
                    <td class="tabular-nums">${s.total_paid_egp.toFixed(2)} ج.م</td>
                    <td class="tabular-nums" style="font-weight:700; color:${s.balance_egp > 0 ? '#DC2626' : '#059669'};">${s.balance_egp.toFixed(2)} ج.م</td>
                    <td>
                      ${s.balance_egp <= 0 ? '<span class="badge badge-paid">مسدد بالكامل</span>' : (s.total_paid_egp > 0 ? '<span class="badge badge-partially-paid">مسدد جزئياً</span>' : '<span class="badge badge-unpaid">غير مسدد</span>')}
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
      } catch (err) {
        resContainer.innerHTML = `<div style="color:#DC2626; padding:1rem;">تعذر استخراج ملخص المجموعة: ${err.message}</div>`;
      }
    });
  }

  // 3. Monthly Report
  const btnMonthlyRep = document.getElementById('btn-load-monthly-report');
  if (btnMonthlyRep) {
    btnMonthlyRep.addEventListener('click', async () => {
      const month = document.getElementById('report-month-input').value;
      const resContainer = document.getElementById('monthly-report-result');
      if (!month) {
        showToast('يرجى تحديد الشهر.', 'warning');
        return;
      }
      resContainer.innerHTML = '<div style="text-align:center; padding:1.5rem; color:var(--slate-400);">جارٍ تجميع التقرير الشهري...</div>';
      resContainer.style.display = 'block';

      try {
        const rep = await api.getMonthlyCollectionReport(month);
        resContainer.innerHTML = `
          <div class="finance-metrics-grid" style="margin-bottom:1rem;">
            <div class="finance-metric-card">
              <div class="metric-header"><span>اشتراكات شهرية</span>${icons.calendar}</div>
              <div class="metric-val">${rep.total_monthly_dues_egp.toFixed(2)} ج.م</div>
            </div>
            <div class="finance-metric-card">
              <div class="metric-header"><span>رسوم حصص</span>${icons.attendance}</div>
              <div class="metric-val">${rep.total_session_dues_egp.toFixed(2)} ج.م</div>
            </div>
            <div class="finance-metric-card">
              <div class="metric-header"><span>المحصل للشهر</span>${icons.check}</div>
              <div class="metric-val money-rate">${rep.total_collected_egp.toFixed(2)} ج.م</div>
            </div>
            <div class="finance-metric-card">
              <div class="metric-header"><span>المتبقي للشهر</span>${icons.clock}</div>
              <div class="metric-val money-due">${rep.total_outstanding_egp.toFixed(2)} ج.م</div>
              <div class="metric-sub">نسبة التحصيل: ${rep.collection_rate_percent.toFixed(1)}%</div>
            </div>
          </div>

          <h3 style="font-size:0.95rem; font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">توزيع التحصيل حسب المجموعات الدراسية لشهر (${rep.billing_month}):</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>المجموعة الدراسية</th>
                  <th>إجمالي المطالبات</th>
                  <th>المحصل</th>
                  <th>المتبقي</th>
                  <th>نسبة التحصيل</th>
                </tr>
              </thead>
              <tbody>
                ${rep.groups_breakdown.length === 0 ? '<tr><td colspan="5" style="text-align:center; color:var(--slate-400);">لا توجد مطالبات مسجلة في هذا الشهر</td></tr>' : rep.groups_breakdown.map(g => `
                  <tr>
                    <td style="font-weight:700;">${g.group_name}</td>
                    <td class="tabular-nums">${g.total_billed_egp.toFixed(2)} ج.م</td>
                    <td class="tabular-nums" style="color:#059669; font-weight:700;">${g.total_collected_egp.toFixed(2)} ج.م</td>
                    <td class="tabular-nums" style="color:#DC2626; font-weight:700;">${g.total_outstanding_egp.toFixed(2)} ج.م</td>
                    <td class="tabular-nums">${g.collection_rate_percent.toFixed(1)}%</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
      } catch (err) {
        resContainer.innerHTML = `<div style="color:#DC2626; padding:1rem;">تعذر استخراج التقرير الشهري: ${err.message}</div>`;
      }
    });
  }

  // 4. Cash Collection Audit
  const btnCashRep = document.getElementById('btn-load-cash-report');
  if (btnCashRep) {
    btnCashRep.addEventListener('click', async () => {
      const sDate = document.getElementById('report-cash-start').value;
      const eDate = document.getElementById('report-cash-end').value;
      const resContainer = document.getElementById('cash-report-result');
      resContainer.innerHTML = '<div style="text-align:center; padding:1.5rem; color:var(--slate-400);">جارٍ فحص حركة الخزينة...</div>';
      resContainer.style.display = 'block';

      try {
        const audit = await api.getCashCollectionReport({ start_date: sDate, end_date: eDate });
        resContainer.innerHTML = `
          <div class="finance-metrics-grid" style="margin-bottom:1rem;">
            <div class="finance-metric-card">
              <div class="metric-header"><span>إجمالي المقبوض نقدياً</span>${icons.cash}</div>
              <div class="metric-val money-accent">${audit.total_collected_egp.toFixed(2)} ج.م</div>
              <div class="metric-sub">عدد الإيصالات: ${audit.payments_count}</div>
            </div>
            <div class="finance-metric-card">
              <div class="metric-header"><span>إجمالي المسترد والملغي</span>${icons.clock}</div>
              <div class="metric-val money-due">${audit.total_reversed_egp.toFixed(2)} ج.م</div>
              <div class="metric-sub">عدد العمليات المستردة: ${audit.reversals_count}</div>
            </div>
            <div class="finance-metric-card">
              <div class="metric-header"><span>صافي النقدية بالخزينة</span>${icons.check}</div>
              <div class="metric-val money-rate" style="font-size:1.9rem;">${audit.net_collected_egp.toFixed(2)} ج.م</div>
              <div class="metric-sub">الرصيد الفعلي بعد خصم الاستردادات</div>
            </div>
          </div>

          <h3 style="font-size:0.95rem; font-weight:700; color:var(--slate-800); margin-bottom:0.5rem;">تفاصيل حركة المقبوضات في الفترة المحددة:</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>رقم الإيصال</th>
                  <th>الطالب</th>
                  <th>التاريخ</th>
                  <th>المبلغ</th>
                  <th>المسؤول</th>
                  <th>الحالة</th>
                </tr>
              </thead>
              <tbody>
                ${audit.payments.length === 0 ? '<tr><td colspan="6" style="text-align:center; color:var(--slate-400);">لا توجد حركات في هذه الفترة</td></tr>' : audit.payments.map(p => `
                  <tr style="${p.is_reversed ? 'opacity:0.6; text-decoration:line-through;' : ''}">
                    <td class="tabular-nums" style="font-family:monospace; font-weight:700; color:var(--primary);">${p.receipt_number}</td>
                    <td style="font-weight:700;">${p.student_name}</td>
                    <td class="tabular-nums">${p.payment_date}</td>
                    <td class="tabular-nums" style="font-weight:700;">${p.formatted_amount}</td>
                    <td style="font-size:0.85rem;">${p.created_by_name}</td>
                    <td>${p.is_reversed ? '<span class="badge badge-reversed">ملغي ومسترد</span>' : '<span class="badge badge-paid">معتمد</span>'}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
      } catch (err) {
        resContainer.innerHTML = `<div style="color:#DC2626; padding:1rem;">تعذر فحص حركة الخزينة: ${err.message}</div>`;
      }
    });
  }

  // Action query parameter handling
  if (queryParams && queryParams.get('action') === 'record_payment') {
    openPaymentModal();
  }
}

// --- View 6: System & Backups Controller ---
function bindSystemEvents() {
  const isTeacher = state.user && (state.user.is_teacher || state.user.user_type === 'teacher');
  if (!isTeacher) return;

  const createBtn = document.getElementById('create-backup-btn');
  if (createBtn) {
    createBtn.addEventListener('click', async () => {
      if (state.isCreatingBackup) return;
      state.isCreatingBackup = true;
      createBtn.disabled = true;
      createBtn.innerHTML = '<span class="spinner-sm"></span> جاري إنشاء النسخة وفحص السلامة...';

      try {
        const newBackup = await api.createBackup();
        showToast(`تم إنشاء النسخة الاحتياطية (${newBackup.filename}) والتحقق من سلامتها بنجاح.`, 'success');

        const res = await api.listBackups();
        state.backups = res.backups || [];
        state.backupDirectoryHint = res.backup_directory_hint || '';
        state.backupTotalCount = res.total_count || 0;
        state.backupTotalSizeFormatted = res.total_size_formatted || '0 B';
      } catch (err) {
        showToast(err.message || 'فشل في إنشاء النسخة الاحتياطية.', 'error');
      } finally {
        state.isCreatingBackup = false;
        const appContainer = document.getElementById('app');
        if (appContainer && state.activeRoute === 'system') {
          appContainer.innerHTML = renderAppShell(renderSystemView(), state.activeRoute);
          bindShellEvents();
          bindSystemEvents();
        }
      }
    });
  }

  // Bind download buttons
  document.querySelectorAll('.download-backup-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const filename = btn.getAttribute('data-filename');
      if (!filename) return;

      const origHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '⏳ جاري التحميل...';

      try {
        await api.downloadBackup(filename);
        showToast(`بدأ تحميل ملف النسخة الاحتياطية: ${filename}`, 'success');
      } catch (err) {
        showToast(err.message || 'تعذر تحميل النسخة الاحتياطية.', 'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = origHtml;
      }
    });
  });
}

// --- Initialization & Global Keyboard Shortcuts ---
window.addEventListener('hashchange', navigate);
window.addEventListener('DOMContentLoaded', navigate);
window.addEventListener('auth:required', () => {
  window.location.hash = '#/login';
});

// Escape key to dismiss modals and mobile drawer
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    // Dismiss all active modals
    document.querySelectorAll('.modal-overlay').forEach(m => {
      m.style.display = 'none';
    });
    state.editingAssistantId = null;
    state.editingStudentId = null;
    state.editingGroupId = null;
    state.editingSessionId = null;
    state.editingExamId = null;
    state.activeModalStudent = null;
    state.activeModalGroup = null;
    state.activeStudentHistory = null;
    state.activeGroupSummary = null;
    state.activeExamStudentHistory = null;
    state.activeExamGroupSummary = null;
    state.reversingPaymentId = null;
    state.voidingDueId = null;

    // Dismiss active mobile sidebar drawer if open
    const sidebar = document.getElementById('app-sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (sidebar && sidebar.classList.contains('open')) {
      sidebar.classList.remove('open');
      if (backdrop) backdrop.classList.remove('active');
    }
  }
});
