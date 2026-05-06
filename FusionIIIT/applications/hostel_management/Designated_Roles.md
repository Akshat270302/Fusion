# Module Name: Hostel Management - Guard Duty

## Designated User Roles & Permissions

### 1. Role Name: Super Admin

* **Description:** Primary manager for guard duty scheduling, oversight, and concern resolution.

* **Permissions:**

    * Full CRUD operations on guard duty schedules.

    * View guard duty schedules and security coverage across all hostels.

    * Resolve guard duty concerns submitted by hostel staff.

    * Override schedule validation when policy review is required.

### 2. Role Name: Warden

* **Description:** Hostel supervisory user responsible for security oversight for the assigned hostel.

* **Permissions:**

    * View guard duty schedules and security coverage for the assigned hostel.

    * Raise guard duty concerns for hostel-level review.

    * Monitor shift coverage and report operational security issues.

    * No permission to create, update, or delete guard duty schedules.

### 3. Role Name: Caretaker

* **Description:** Operational hostel user responsible for day-to-day coordination and issue reporting.

* **Permissions:**

    * View guard duty schedules for the assigned hostel.

    * Raise guard duty concerns when shifts, coverage, or security conditions need attention.

    * Track duty coverage for the assigned hostel.

    * No permission to create, update, delete, or resolve guard duty schedules and concerns.

---