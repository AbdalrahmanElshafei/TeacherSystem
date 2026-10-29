/**
 * TeacherSystem — Centralized API Client (api.js)
 * Handles CSRF tokens, session cookies, rate-limit countdowns, and error mapping.
 */

class ApiClient {
  constructor() {
    this.baseUrl = '';
  }

  /**
   * Extract CSRF cookie value for mutation requests
   */
  getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)ts_csrf=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  }

  /**
   * Core HTTP request handler
   */
  async request(path, options = {}) {
    const url = `${this.baseUrl}${path}`;
    const method = (options.method || 'GET').toUpperCase();
    
    const headers = {
      'Accept': 'application/json',
      ...(options.headers || {})
    };

    if (options.body && typeof options.body === 'object') {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }

    // Attach CSRF token on mutating requests
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
      const csrf = this.getCsrfToken();
      if (csrf) {
        headers['X-CSRF-Token'] = csrf;
      }
    }

    const config = {
      ...options,
      method,
      headers,
      credentials: 'include' // Enforce HttpOnly cookie transport
    };

    let response;
    try {
      response = await fetch(url, config);
    } catch (err) {
      console.error('Network request failed:', err);
      throw new Error('تعذر الاتصال بالسيرفر المحلي. تأكد من تشغيل الخدمة.');
    }

    // Rate Limit handling (429 Too Many Requests)
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After') || '60';
      const errorData = await response.json().catch(() => ({}));
      const err = new Error(errorData.detail || `تم تجاوز عدد المحاولات المسموح بها.`);
      err.status = 429;
      err.retryAfter = parseInt(retryAfter, 10);
      throw err;
    }

    // Unauthorized handling (401)
    if (response.status === 401) {
      if (!path.includes('/login') && !path.includes('/first-run-setup')) {
        window.dispatchEvent(new CustomEvent('auth:required'));
      }
      const errorData = await response.json().catch(() => ({}));
      const err = new Error(errorData.detail || 'غير مصرح أو انتهت الجلسة.');
      err.status = 401;
      throw err;
    }

    // Forbidden handling (403)
    if (response.status === 403) {
      const errorData = await response.json().catch(() => ({}));
      const err = new Error(errorData.detail || 'ليس لديك الصلاحية لتنفيذ هذا الإجراء.');
      err.status = 403;
      throw err;
    }

    // Validation Error (422)
    if (response.status === 422) {
      const errorData = await response.json().catch(() => ({}));
      let msg = 'بيانات غير صالحة: ';
      if (Array.isArray(errorData.detail)) {
        msg += errorData.detail.map(d => `${d.loc.slice(-1)}: ${d.msg}`).join(', ');
      } else {
        msg += errorData.detail || 'يرجى مراجعة الحقول.';
      }
      const err = new Error(msg);
      err.status = 422;
      throw err;
    }

    // Other non-OK statuses
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const err = new Error(errorData.detail || `خطأ في المعالجة (${response.status})`);
      err.status = response.status;
      throw err;
    }

    if (response.status === 204) {
      return null;
    }

    return await response.json().catch(() => null);
  }

  // --- Auth Endpoints ---
  async getHealth() {
    return this.request('/api/health');
  }

  async checkSetupStatus() {
    return this.request('/api/auth/setup-status');
  }

  async firstRunSetup(payload) {
    return this.request('/api/auth/first-run-setup', {
      method: 'POST',
      body: payload
    });
  }

  async login(payload) {
    return this.request('/api/auth/login', {
      method: 'POST',
      body: payload
    });
  }

  async logout() {
    return this.request('/api/auth/logout', {
      method: 'POST'
    });
  }

  async getMe() {
    return this.request('/api/auth/me');
  }

  // --- Assistant Management Endpoints ---
  async listAssistants() {
    return this.request('/api/users/assistants');
  }

  async getAssistant(id) {
    return this.request(`/api/users/assistants/${id}`);
  }

  async createAssistant(payload) {
    return this.request('/api/users/assistants', {
      method: 'POST',
      body: payload
    });
  }

  async updateAssistant(id, payload) {
    return this.request(`/api/users/assistants/${id}`, {
      method: 'PUT',
      body: payload
    });
  }

  async deleteAssistant(id) {
    return this.request(`/api/users/assistants/${id}`, {
      method: 'DELETE'
    });
  }

  // --- Students Management Endpoints ---
  async listStudents(params = {}) {
    const query = new URLSearchParams();
    if (params.q) query.append('q', params.q);
    if (params.grade_level) query.append('grade_level', params.grade_level);
    if (params.is_active !== undefined && params.is_active !== '') query.append('is_active', params.is_active);
    if (params.group_id) query.append('group_id', params.group_id);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request(`/api/students${qs}`);
  }

  async getStudent(id) {
    return this.request(`/api/students/${id}`);
  }

  async createStudent(payload) {
    return this.request('/api/students', {
      method: 'POST',
      body: payload
    });
  }

  async updateStudent(id, payload) {
    return this.request(`/api/students/${id}`, {
      method: 'PUT',
      body: payload
    });
  }

  async deleteStudent(id) {
    return this.request(`/api/students/${id}`, {
      method: 'DELETE'
    });
  }

  async getStudentGroups(id) {
    return this.request(`/api/students/${id}/groups`);
  }

  // --- Groups Management Endpoints ---
  async listGroups(params = {}) {
    const query = new URLSearchParams();
    if (params.grade_level) query.append('grade_level', params.grade_level);
    if (params.is_active !== undefined && params.is_active !== '') query.append('is_active', params.is_active);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request(`/api/groups${qs}`);
  }

  async getGroup(id) {
    return this.request(`/api/groups/${id}`);
  }

  async createGroup(payload) {
    return this.request('/api/groups', {
      method: 'POST',
      body: payload
    });
  }

  async updateGroup(id, payload) {
    return this.request(`/api/groups/${id}`, {
      method: 'PUT',
      body: payload
    });
  }

  async deleteGroup(id) {
    return this.request(`/api/groups/${id}`, {
      method: 'DELETE'
    });
  }

  async getGroupStudents(groupId) {
    return this.request(`/api/groups/${groupId}/students`);
  }

  async enrollStudent(groupId, studentId) {
    return this.request(`/api/groups/${groupId}/students`, {
      method: 'POST',
      body: { student_id: studentId }
    });
  }

  async unenrollStudent(groupId, studentId) {
    return this.request(`/api/groups/${groupId}/students/${studentId}`, {
      method: 'DELETE'
    });
  }

  // --- Sessions & Attendance Endpoints ---
  async listSessions(params = {}) {
    const query = new URLSearchParams();
    if (params.group_id) query.append('group_id', params.group_id);
    if (params.session_date) query.append('session_date', params.session_date);
    if (params.start_date) query.append('start_date', params.start_date);
    if (params.end_date) query.append('end_date', params.end_date);
    if (params.status) query.append('status', params.status);
    if (params.limit) query.append('limit', params.limit);
    if (params.offset) query.append('offset', params.offset);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request(`/api/sessions${qs}`);
  }

  async getSession(id) {
    return this.request(`/api/sessions/${id}`);
  }

  async createSession(payload) {
    return this.request('/api/sessions', {
      method: 'POST',
      body: payload
    });
  }

  async updateSession(id, payload) {
    return this.request(`/api/sessions/${id}`, {
      method: 'PUT',
      body: payload
    });
  }

  async cancelSession(id) {
    return this.request(`/api/sessions/${id}/cancel`, {
      method: 'POST'
    });
  }

  async getSessionAttendance(sessionId) {
    return this.request(`/api/sessions/${sessionId}/attendance`);
  }

  async markAttendance(sessionId, payload) {
    return this.request(`/api/sessions/${sessionId}/attendance`, {
      method: 'POST',
      body: payload
    });
  }

  async bulkMarkAttendance(sessionId, records) {
    return this.request(`/api/sessions/${sessionId}/attendance/bulk`, {
      method: 'POST',
      body: { records }
    });
  }

  async scanBarcode(sessionId, barcode, notes = null) {
    return this.request(`/api/sessions/${sessionId}/scan`, {
      method: 'POST',
      body: { barcode, notes }
    });
  }

  async getStudentAttendanceHistory(studentId) {
    return this.request(`/api/sessions/reports/student/${studentId}`);
  }

  async getGroupAttendanceSummary(groupId) {
    return this.request(`/api/sessions/reports/group/${groupId}`);
  }

  // --- Exams & Grades Endpoints ---
  async listExams(params = {}) {
    const query = new URLSearchParams();
    if (params.group_id) query.append('group_id', params.group_id);
    if (params.exam_date) query.append('exam_date', params.exam_date);
    if (params.start_date) query.append('start_date', params.start_date);
    if (params.end_date) query.append('end_date', params.end_date);
    if (params.status) query.append('status', params.status);
    if (params.limit) query.append('limit', params.limit);
    if (params.offset) query.append('offset', params.offset);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request(`/api/exams${qs}`);
  }

  async getExam(id) {
    return this.request(`/api/exams/${id}`);
  }

  async createExam(payload) {
    return this.request('/api/exams', {
      method: 'POST',
      body: payload
    });
  }

  async updateExam(id, payload) {
    return this.request(`/api/exams/${id}`, {
      method: 'PUT',
      body: payload
    });
  }

  async completeExam(id) {
    return this.request(`/api/exams/${id}/complete`, {
      method: 'POST'
    });
  }

  async cancelExam(id) {
    return this.request(`/api/exams/${id}/cancel`, {
      method: 'POST'
    });
  }

  async deleteExam(id) {
    return this.request(`/api/exams/${id}`, {
      method: 'DELETE'
    });
  }

  async getExamResults(examId) {
    return this.request(`/api/exams/${examId}/results`);
  }

  async recordExamResult(examId, payload) {
    return this.request(`/api/exams/${examId}/results`, {
      method: 'POST',
      body: payload
    });
  }

  async bulkRecordExamResults(examId, records) {
    return this.request(`/api/exams/${examId}/results/bulk`, {
      method: 'POST',
      body: { records }
    });
  }

  async getStudentExamHistory(studentId) {
    return this.request(`/api/exams/reports/student/${studentId}`);
  }

  async getGroupExamsSummary(groupId) {
    return this.request(`/api/exams/reports/group/${groupId}`);
  }

  // --- Payments & Finance Endpoints ---
  async getFinanceOverview() {
    return this.request('/api/finance/overview');
  }

  async listFeeConfigs(params = {}) {
    const query = new URLSearchParams();
    if (params.group_id) query.append('group_id', params.group_id);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request(`/api/finance/fees${qs}`);
  }

  async createFeeConfig(payload) {
    return this.request('/api/finance/fees', {
      method: 'POST',
      body: payload
    });
  }

  async getGroupActiveFee(groupId) {
    return this.request(`/api/finance/fees/group/${groupId}`);
  }

  async previewMonthlyDues(payload) {
    return this.request('/api/finance/dues/monthly/preview', {
      method: 'POST',
      body: payload
    });
  }

  async generateMonthlyDues(payload) {
    return this.request('/api/finance/dues/monthly/generate', {
      method: 'POST',
      body: payload
    });
  }

  async previewSessionDues(sessionId) {
    return this.request(`/api/finance/dues/session/${sessionId}/preview`);
  }

  async generateSessionDues(payload) {
    return this.request('/api/finance/dues/session/generate', {
      method: 'POST',
      body: payload
    });
  }

  async listStudentDues(params = {}) {
    const query = new URLSearchParams();
    if (params.student_id) query.append('student_id', params.student_id);
    if (params.group_id) query.append('group_id', params.group_id);
    if (params.status) query.append('status', params.status);
    if (params.charge_type) query.append('charge_type', params.charge_type);
    if (params.billing_month) query.append('billing_month', params.billing_month);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request(`/api/finance/dues${qs}`);
  }

  async voidStudentDue(dueId, payload) {
    return this.request(`/api/finance/dues/${dueId}/void`, {
      method: 'POST',
      body: payload
    });
  }

  async recordCashPayment(payload) {
    return this.request('/api/finance/payments', {
      method: 'POST',
      body: payload
    });
  }

  async listCashPayments(params = {}) {
    const query = new URLSearchParams();
    if (params.student_id) query.append('student_id', params.student_id);
    if (params.start_date) query.append('start_date', params.start_date);
    if (params.end_date) query.append('end_date', params.end_date);
    if (params.is_reversed !== undefined) query.append('is_reversed', params.is_reversed);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request(`/api/finance/payments${qs}`);
  }

  async getPaymentDetails(paymentId) {
    return this.request(`/api/finance/payments/${paymentId}`);
  }

  async reversePayment(paymentId, payload) {
    return this.request(`/api/finance/payments/${paymentId}/reverse`, {
      method: 'POST',
      body: payload
    });
  }

  async getStudentFinancialProfile(studentId) {
    return this.request(`/api/finance/reports/student/${studentId}`);
  }

  async getGroupCollectionSummary(groupId) {
    return this.request(`/api/finance/reports/group/${groupId}`);
  }

  async getMonthlyCollectionReport(billingMonth) {
    return this.request(`/api/finance/reports/monthly/${billingMonth}`);
  }

  async getCashCollectionReport(params = {}) {
    const query = new URLSearchParams();
    if (params.start_date) query.append('start_date', params.start_date);
    if (params.end_date) query.append('end_date', params.end_date);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request(`/api/finance/reports/cash${qs}`);
  }

  // --- Backup Management ---
  async listBackups() {
    return this.request('/api/backups');
  }

  async createBackup() {
    return this.request('/api/backups', {
      method: 'POST'
    });
  }

  /**
   * Safe asynchronous file download helper.
   * Defers object URL revocation to prevent modern browsers from truncating
   * or aborting the download stream before completion.
   */
  triggerBlobDownload(blob, filename) {
    if (!blob || !(blob instanceof Blob)) {
      throw new Error('بيانات الملف غير صالحة للتحميل.');
    }
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      try {
        window.URL.revokeObjectURL(url);
        a.remove();
      } catch (e) {
        // Safe cleanup ignore
      }
    }, 60000);
  }

  async downloadBackup(filename) {
    const res = await fetch(`/api/backups/${encodeURIComponent(filename)}/download`, {
      method: 'GET',
      credentials: 'include'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'تعذر تحميل ملف النسخة الاحتياطية.');
    }
    const buffer = await res.arrayBuffer();
    const blob = new Blob([buffer], { type: 'application/x-sqlite3' });
    this.triggerBlobDownload(blob, filename);
  }

  /**
   * Safe binary PDF fetcher with status inspection, CSRF fallback,
   * content-type verification, and %PDF- header signature validation.
   */
  async fetchPdfBlob(path, options = {}, defaultErrorMsg = 'تعذر تحميل ملف PDF.') {
    const url = `${this.baseUrl}${path}`;
    const method = (options.method || 'GET').toUpperCase();
    const headers = {
      'Accept': 'application/pdf',
      ...(options.headers || {})
    };

    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
      const csrf = this.getCsrfToken();
      if (csrf && !headers['X-CSRF-Token']) {
        headers['X-CSRF-Token'] = csrf;
      }
    }

    let res;
    try {
      res = await fetch(url, {
        ...options,
        method,
        headers,
        credentials: 'include'
      });
    } catch (err) {
      console.error('Network request failed for PDF:', err);
      throw new Error('تعذر الاتصال بالسيرفر المحلي لتحميل ملف PDF.');
    }

    if (!res.ok) {
      if (res.status === 401) {
        window.dispatchEvent(new CustomEvent('auth:required'));
        throw new Error('انتهت صلاحية الجلسة. يرجى تسجيل الدخول مجدداً.');
      }
      if (res.status === 403) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'ليس لديك الصلاحية لتحميل أو تصدير بطاقات الباركود.');
      }
      if (res.status === 404) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'البيانات أو المجموعة المطلوبة غير موجودة.');
      }
      const err = await res.json().catch(() => null);
      if (err && err.detail) {
        const msg = Array.isArray(err.detail)
          ? err.detail.map(d => `${d.loc ? d.loc.slice(-1) + ': ' : ''}${d.msg}`).join(', ')
          : err.detail;
        throw new Error(msg);
      }
      throw new Error(defaultErrorMsg);
    }

    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('application/pdf')) {
      const err = await res.json().catch(() => null);
      if (err && err.detail) {
        const msg = Array.isArray(err.detail)
          ? err.detail.map(d => `${d.loc ? d.loc.slice(-1) + ': ' : ''}${d.msg}`).join(', ')
          : err.detail;
        throw new Error(msg);
      }
      throw new Error('استجابة غير صالحة من السيرفر (الملف المستلم ليس بصيغة PDF).');
    }

    const buffer = await res.arrayBuffer();
    if (buffer.byteLength < 5) {
      throw new Error('ملف PDF المستلم فارغ أو تالف.');
    }

    // Validate PDF signature (%PDF-)
    const headerBytes = new Uint8Array(buffer.slice(0, 5));
    const isPdfSignature = headerBytes[0] === 0x25 && // %
                           headerBytes[1] === 0x50 && // P
                           headerBytes[2] === 0x44 && // D
                           headerBytes[3] === 0x46 && // F
                           headerBytes[4] === 0x2D;   // -
    if (!isPdfSignature) {
      throw new Error('الملف المستلم غير صالح أو تالف (لا يحتوي على توقيع PDF سليم).');
    }

    return new Blob([buffer], { type: 'application/pdf' });
  }

  // --- Student Barcode & Distribution ---
  async getStudentCard(studentId, groupId = null) {
    const qs = groupId ? `?group_id=${encodeURIComponent(groupId)}` : '';
    return this.request(`/api/barcodes/students/${studentId}/card${qs}`);
  }

  async getStudentCardBlob(studentId, groupId = null) {
    const qs = groupId ? `?group_id=${encodeURIComponent(groupId)}` : '';
    return this.fetchPdfBlob(
      `/api/barcodes/students/${studentId}/card.pdf${qs}`,
      { method: 'GET' },
      'تعذر تحميل ملف البطاقة.'
    );
  }

  async downloadStudentCardPdf(studentId, studentName = '', groupId = null) {
    const blob = await this.getStudentCardBlob(studentId, groupId);
    const safeName = studentName ? `بطاقة_${studentName.replace(/\s+/g, '_')}.pdf` : `student_card_${studentId.slice(0, 8)}.pdf`;
    this.triggerBlobDownload(blob, safeName);
  }

  async getGroupDistributionOverview(groupId) {
    return this.request(`/api/barcodes/distribution/groups/${groupId}`);
  }

  async exportGroupCardsPdf(groupId, groupName = '') {
    const blob = await this.fetchPdfBlob(
      `/api/barcodes/groups/${groupId}/export-pdf`,
      { method: 'GET' },
      'تعذر تصدير بطاقات المجموعة.'
    );
    const safeName = groupName ? `بطاقات_${groupName.replace(/\s+/g, '_')}.pdf` : `group_cards_${groupId.slice(0, 8)}.pdf`;
    this.triggerBlobDownload(blob, safeName);
  }

  async exportMultiStudentCardsPdf(studentIds, groupId = null) {
    const blob = await this.fetchPdfBlob(
      `/api/barcodes/multi/export-pdf`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_ids: studentIds, group_id: groupId })
      },
      'تعذر تصدير البطاقات المحددة.'
    );
    this.triggerBlobDownload(blob, `بطاقات_محددة_${studentIds.length}.pdf`);
  }

  async updateStudentDistributionStatus(studentId, payload) {
    return this.request(`/api/barcodes/distribution/students/${studentId}/status`, {
      method: 'POST',
      body: payload
    });
  }
}

export const api = new ApiClient();
