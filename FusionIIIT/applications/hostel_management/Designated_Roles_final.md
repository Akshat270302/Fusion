# Module Name: Hostel Management

## Designated User Roles & Permissions

This document lists the principal roles used across the Hostel Management module and the permissions they require to support implemented features (Leave, Complaints, Room Allotment, Room Change, Fines, Attendance, Inventory, Notices, Guest Rooms, Guard Duty, Extended Stay, Room Vacation, Reports).

### 1. Role Name: Super Admin

* **Description:** System-level administrator with full oversight and configuration authority for the Hostel Management module.

* **Permissions:**

    * Full CRUD on all module data (hostel records, rooms, batches, policies).

    * Create/Update/Delete guard duty schedules and override scheduling policy.

    * Resolve guard duty concerns and close escalations.

    * Perform bulk room allotment and activation/deactivation of hostels.

    * Full visibility to generate and approve reports and access audit logs.

    * Assign/modify Warden and Caretaker assignments for hostels.

### 2. Role Name: Warden

* **Description:** Hostel supervisory staff responsible for security and higher-level decisions for assigned hostels.

* **Permissions:**

    * View schedules, concerns, complaints, attendance, and reports for assigned hostels.

    * Resolve escalated complaints and review major operational workflows (room vacations, extended stay approvals when applicable).

    * Raise guard duty concerns and request schedule changes (cannot create schedules).

    * Generate reports for assigned hostels and submit to Super Admin for approval.

### 3. Role Name: Caretaker

* **Description:** Operational staff responsible for daily hostel operations, inventory checks, and initial handling of student requests.

* **Permissions:**

    * View and manage leave requests (approve/reject for assigned hostels) and update attendance accordingly.

    * Manage complaints (investigate, resolve or escalate to Warden) for assigned hostels.

    * View guard duty schedules and raise guard duty concerns.

    * Manage inventory records, perform inspections, and submit resource requests.

    * Create notices targeted to assigned hostels and manage guest room bookings.

### 4. Role Name: Guard

* **Description:** Security staff assigned to duty shifts.

* **Permissions:**

    * View personal shift schedule and assigned hostel shift coverage.

    * Mark attendance or sign-in for assigned shifts (as implemented by the scheduling workflow).

    * No permissions to create or modify schedules or resolve escalations.

### 5. Role Name: Student (End-User)

* **Description:** Primary consumer of hostel services (room allocation, leave, complaints, bookings).

* **Permissions:**

    * Read-only access to personal hostel records, current room allocation, fines, and notices.

    * Create leave requests, complaints, guest room bookings, room change requests, and extended stay applications.

    * Download or view own history and reports relevant to personal records.

### 6. Role Name: Reporting / Auditor (Optional)

* **Description:** Role for read-only access to cross-hostel reports and audit trails for compliance/review.

* **Permissions:**

    * View generated reports, audit logs and traceability documents; no write permissions.

---

Notes:

- Role enforcement in code uses `authorizeRoles()` and service-layer permission checks. The implemented service functions explicitly restrict actions: only `Super Admin` may create/update/delete guard schedules; `Warden`/`Caretaker` may raise concerns; `Super Admin` resolves concerns; `Caretaker` approves leave for assigned hostel; `Warden` handles escalations, etc.

- For any new sub-role needs, follow the same pattern: define role in this file, and add service-layer checks and unit tests in `applications/hostel_management/tests/`.
