# SPEC.md — Project Specification

> **Status**: `FINALIZED`
> **Project**: Student Progress Tracker
> **Client**: El'Wood International School

## Vision
A comprehensive, full-featured web application for El'Wood International School that enables teachers to track student grades, assignments, attendance, and performance trends. The system supports multiple user roles (admin, teachers, students, parents) with appropriate access levels, provides automated email notifications, generates PDF report cards, supports online exams, in-app messaging, LMS integration, and fee management — all branded to El'Wood International School. Deployable both locally and to the cloud with multi-school support.

## Goals
1. **Multi-role authentication** — Secure login for admins, teachers, students, and parents with role-based access control
2. **Grade management** — Percentage-based (0-100%) grading across multiple subjects, organized by class/section
3. **Assignment tracking** — Teachers create assignments, track submissions, and grade them
4. **Attendance tracking** — Daily attendance recording per class/section with absence reporting
5. **Performance analytics** — Visual trend charts showing student progress over time
6. **Report card generation** — PDF report cards containing grades, attendance records, and teacher comments
7. **Email notifications** — Automated alerts for low grades, missed attendance, and unsubmitted assignments
8. **Admin panel** — Manage teachers, classes, sections, subjects, and academic calendar
9. **Student/parent portals** — Read-only access to view individual progress, grades, and attendance
10. **Mobile-responsive design** — Fully usable on phones and tablets
11. **Configurable academic calendar** — Support for semesters, terms, or quarters
12. **Cloud deployment** — Deployable to cloud infrastructure in addition to local
13. **Multi-school/multi-tenant support** — Support multiple schools within a single instance
14. **Online exam/test-taking** — Students can take exams and tests online within the platform
15. **Chat and messaging** — In-app messaging between teachers, students, and parents
16. **LMS integration** — Integration with external Learning Management Systems
17. **Payment and fee management** — Track and manage student fee payments
18. **Online admission panel** — Admin interface to fill out admission forms and register new students into the database
19. **Downloadable fee receipts** — PDF fee receipts generated and available for download by all relevant users
20. **"Early Warning" Algorithm** — Predictive algorithm to detect at-risk students based on attendance and assignments, triggering automated intervention emails
21. **Unified Parental Weekly Digest** — Automated weekly background job compiling grades, attendance, and missing fees into one parent email
22. **Micro-Credentialing & Extracurriculars** — Verify and generate digital micro-certificates via WeasyPrint for modern soft-skills
23. **Offline/Low-Bandwidth Capability** — Progressive Web App (PWA) architecture with Service Workers to allow offline attendance and grade recording
24. **In-School Digital Micro-Payments Wallet** — Parent wallet system to handle top-ups and micro-fee deductions (field trips, fines) with automated PDF receipts
25. **Timetable Management** — Full scheduling suite with school-scoped collision detection and weekly views
26. **Advanced Analytics** — Role-based Chart.js dashboards (Admin, Teacher, Parent) for data-driven student monitoring

## Non-Goals (Out of Scope)
_None — all proposed features are in scope for v1._

## Users

### Admin (School Principal / Coordinator)
- Manages teacher accounts
- Configures school settings (academic calendar, classes, sections, subjects)
- Has full visibility across all teachers and students
- Single or small number of admin users

### Teachers
- Manage their assigned classes and subjects
- Record grades, attendance, and assignments
- Write report card comments
- One teacher handles multiple subjects
- ~100 students per teacher

### Students
- View their own grades, attendance, and assignments (read-only)
- See performance trends over time
- Access their own report cards

### Parents
- View their child's grades, attendance, and progress (read-only)
- Receive email notifications about academic concerns
- Linked to one or more students

## Technical Stack
- **Backend**: Python (Flask)
- **Frontend**: HTML + CSS (server-rendered templates, mobile-responsive)
- **Database**: SQLite (local) / PostgreSQL (cloud)
- **PDF Generation**: Python library (e.g., ReportLab or WeasyPrint)
- **Email**: SMTP-based email sending
- **Charts**: JavaScript charting library (e.g., Chart.js)
- **Messaging**: WebSocket or polling-based in-app chat
- **Deployment**: Local machine + cloud-ready

## Data Model (High-Level)
- **Users** — id, name, email, password_hash, role (admin/teacher/student/parent)
- **Classes** — id, name (e.g., "Class 10"), academic_year
- **Sections** — id, class_id, name (e.g., "A", "B")
- **Subjects** — id, name (e.g., "Mathematics", "English")
- **Teacher-Subject-Section assignments** — which teacher teaches what subject in which section
- **Students** — user_id, section_id, enrollment details
- **Parent-Student links** — parent_id, student_id
- **Grades** — student_id, subject_id, exam_name, score (0-100), date
- **Assignments** — id, subject_id, section_id, title, due_date, created_by
- **Assignment Submissions** — assignment_id, student_id, submitted_at, grade
- **Attendance** — student_id, date, status (present/absent/late), section_id
- **Academic Calendar** — term/semester/quarter config, start/end dates
- **Report Card Comments** — student_id, teacher_id, term, comment

## Branding
- **School Name**: El'Wood International School
- **Branding**: School name and identity displayed throughout the app (login page, headers, report cards, PDFs)

## Constraints
- Must support both local and cloud deployment
- SQLite for local, PostgreSQL option for cloud/multi-tenant
- Python/Flask — no JavaScript frameworks (vanilla JS only for interactivity)
- Must handle ~100 students per teacher without performance issues
- Email notifications require SMTP configuration
- LMS integration depends on available APIs from target platforms

## Success Criteria
- [x] Admin can create/manage teachers, classes, sections, and subjects
- [x] Teachers can record and update grades (percentage-based) for their students
- [x] Teachers can create assignments and track submissions
- [x] Teachers can record daily attendance per section
- [x] Performance trend charts display correctly for individual students
- [x] PDF report cards generate with grades, attendance, and teacher comments
- [x] Email notifications fire for low grades, absences, and missing assignments
- [x] Students can log in and view their own progress
- [x] Parents can log in and view their child's progress
- [x] App is mobile-responsive and usable on phones
- [x] Academic calendar is configurable (semesters/terms/quarters)
- [x] All pages display El'Wood International School branding
- [x] App can be deployed to cloud infrastructure
- [x] Multi-school tenancy works with isolated data per school
- [x] Students can take online exams/tests within the platform
- [x] Users can send and receive messages in-app
- [x] LMS integration imports/exports data successfully
- [x] Fee payments can be recorded and tracked per student
- [x] Timetable Management allows scheduling with correct school-scoped relation checks
- [x] Advanced Analytics dashboards provide visualizations for Admin, Teacher, and Parent roles
- [x] Admins can use the online admission panel to register new students
- [x] Users can download fee receipts as PDF documents
- [x] Early Warning algorithm correctly identifies at-risk metrics and dispatches counselor/parent emails
- [x] Weekly Digest background worker successfully compiles and sends unified parent reports every Friday
- [x] Micro-certificates for extracurriculars can be generated into verifiable PDFs
- [x] PWA Service Worker caching enables teachers to input attendance/grades while completely offline and syncs upward on reconnection
- [x] Digital wallet successfully accepts top-ups and deducts micro-fees instantly with automated receipt emails
- [x] Gemini AI Academic Assistant provides context-aware progress insights for students and parents
