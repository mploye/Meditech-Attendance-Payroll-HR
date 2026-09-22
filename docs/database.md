# Database Schema Contract

Source of truth for every backend model, migration, service and agent.

## Conventions

- All tables (except `companies`, `users`, `audit_logs`) carry a `company_id` (UUID FK → companies.id) for tenant isolation.
- Primary keys are UUIDs with `server_default=uuid4` behaviour (generated in app code).
- All datetimes are timezone-aware `DateTime(timezone=True)`.
- Enums are Python `enum.Enum` values mapped as strings (data length-safe).
- Raw device data (`attendance_logs.raw_payload`, `device_sync_logs`) is immutable.
- Business timezone: `Asia/Kolkata` (see `core/config.py`, `core/timezone.py`).

## Enum values (authored in `models/base.py`)

| Enum | Values |
|---|---|
| Role | SUPER_ADMIN, COMPANY_ADMIN, HR_ADMIN, HR_MANAGER, PAYROLL_ADMIN, MANAGER, EMPLOYEE |
| EmployeeStatus | ACTIVE, INACTIVE, RESIGNED, TERMINATED, ON_NOTICE |
| EmploymentType | FULL_TIME, PART_TIME, CONTRACT, INTERN, PROBATION |
| DeviceProvider | ESSL, ORCUS, OTHER |
| DeviceStatus | ONLINE, OFFLINE, SYNCING, ERROR, DISABLED |
| DeviceType | FACE_PUNCH, FINGERPRINT, CARD, MOBILE, WEB |
| MappingSyncStatus | PENDING, SYNCED, FAILED, PARTIAL |
| EventType | IN, OUT, UNKNOWN |
| AttendanceStatus | PRESENT, ABSENT, LEAVE, HOLIDAY, WEEKEND, HALF_DAY, MISSING_PUNCH, ON_DUTY |
| LeaveTypeCategory | PAID, UNPAID, SICK, CASUAL, COMPOFF, OTHER |
| LeaveStatus | PENDING, APPROVED, REJECTED, CANCELLED |
| OvertimeStatus | PENDING, APPROVED, REJECTED |
| SalaryComponentType | EARNING, DEDUCTION |
| CalculationType | FIXED, PERCENTAGE_OF_BASIC, PERCENTAGE_OF_GROSS, FORMULA |
| SalaryFrequency | MONTHLY, WEEKLY, HOURLY |
| StatutoryRuleType | PF, ESI, PT, TDS, OTHER |
| PayrollPeriodStatus | DRAFT, CALCULATING, REVIEW, APPROVED, LOCKED |
| PayrollRecordStatus | DRAFT, CALCULATED, APPROVED, LOCKED, PROCESSED |
| LoanStatus | ACTIVE, CLOSED, DEFAULTED |
| AdvanceStatus | REQUESTED, APPROVED, PAID, CLOSED, REJECTED |
| SyncLogStatus | SUCCESS, PARTIAL, FAILED |
| LogSource | ESSL, DEVICE, MANUAL, IMPORT, API |
| HolidayType | NATIONAL, STATE, COMPANY, OPTIONAL |
| PayslipStatus | GENERATED, DOWNLOADED, PRINTED, LOCKED |
| PayrollComponentType | EARNING, DEDUCTION |

## Tables

### companies
id, name, short_name, legal_name, email, phone, address, city, state, country, pincode, logo_url, timezone (default "Asia/Kolkata"), gstin, pan, statutory_state, lop_policy (default "WORKING_DAYS"), grace_minutes_company, overtime_enabled (bool), created_at, updated_at

### users
id, company_id (nullable), email (unique), password_hash, full_name, role (Role), phone, is_active (bool), employee_id (nullable FK), last_login_at, created_at, updated_at

### departments
id, company_id, name, code, manager_id (nullable), description, created_at, updated_at

### designations
id, company_id, name, code, level, description, created_at, updated_at

### employees
id, company_id, employee_code (unique per company), first_name, last_name, email, phone, date_of_birth, gender, joining_date, resignation_date, department_id, designation_id, manager_id, employment_type, work_location, profile_photo_url, status (EmployeeStatus), aadhaar_no, pan, bank_name, account_number, ifsc, account_holder_name, created_at, updated_at

### devices
id, company_id, name, model, serial_number, device_type (DeviceType), location, ip_address, port, protocol, provider (DeviceProvider), status (DeviceStatus), last_sync_at, last_seen_at, created_at, updated_at
Unique: (company_id, serial_number)

### essl_config (per company)
id, company_id (unique), base_url, username, password_encrypted, api_key_encrypted, company_short_name, timeout_sec, sync_interval_sec, capabilities (JSON array string), enabled, created_at, updated_at

### employee_devices
id, company_id, employee_id, device_id, device_user_id, face_registered (bool), fingerprint_registered (bool), sync_status (MappingSyncStatus), last_synced_at, created_at, updated_at
Unique: (company_id, device_id, device_user_id)

### attendance_logs  (immutable)
id, company_id, device_id, employee_id (nullable), device_user_id, event_timestamp, event_type (EventType), source (LogSource), external_event_id, idempotency_key, raw_payload (Text JSON), created_at
Unique: (company_id, idempotency_key)

### attendance_daily
id, company_id, employee_id, attendance_date (Date), shift_id, first_in, last_out, worked_minutes, break_minutes, late_minutes, early_leave_minutes, overtime_minutes, status (AttendanceStatus), remarks, created_at, updated_at
Unique: (company_id, employee_id, attendance_date)

### shifts
id, company_id, name, code, start_time, end_time, grace_period_minutes, minimum_work_minutes, break_minutes, overtime_enabled (bool), overtime_after_minutes, night_shift (bool), weekly_off_days (JSON list int 0-6), is_default (bool), active (bool), created_at, updated_at

### shift_assignments
id, company_id, employee_id, shift_id, effective_from, effective_to, created_at, updated_at

### leave_types
id, company_id, name, code, category (LeaveTypeCategory), days_per_year, carry_forward_days, requires_approval (bool), created_at, updated_at

### leave_balances
id, company_id, employee_id, leave_type_id, year (int), entitled_days, used_days, pending_days, remaining_days, created_at, updated_at
Unique: (company_id, employee_id, leave_type_id, year)

### leave_requests
id, company_id, employee_id, leave_type_id, start_date, end_date, days, reason, status (LeaveStatus), reviewed_by, reviewed_at, review_comment, is_half_day (bool), created_at, updated_at

### holidays
id, company_id, holiday_date (Date), name, holiday_type (HolidayType), created_at, updated_at
Unique: (company_id, holiday_date)

### overtime_records
id, company_id, employee_id, date (Date), minutes, rate, amount, status (OvertimeStatus), approved_by, remarks, created_at, updated_at

### salary_structures
id, company_id, name, code, payment_frequency (SalaryFrequency), effective_from, effective_to, monthly_gross (computed cache), active, created_at, updated_at

### salary_structure_components
id, company_id, salary_structure_id, name, component_type (SalaryComponentType), calculation_type (CalculationType), value (float, amount or percent), formula, value_source_field, sort_order, created_at, updated_at

### employee_salary  (history, never overwrite)
id, company_id, employee_id, salary_structure_id, effective_from, effective_to, basic_salary, gross_salary, payment_frequency, bank_name, account_number, ifsc, account_holder_name, created_at, updated_at

### statutory_rules
id, company_id, rule_type (StatutoryRuleType), region, employee_category, effective_from, effective_to, threshold, rate, maximum, calculation_method, status (bool/active), created_at, updated_at

### payroll_periods
id, company_id, month (int), year (int), start_date, end_date, status (PayrollPeriodStatus), processed_at, approved_at, locked_at, reviewed_at, created_at, updated_at
Unique: (company_id, month, year)

### payroll_records
id, company_id, payroll_period_id, employee_id, working_days, present_days, leave_days, absent_days, lop_days, overtime_minutes, gross_salary, total_deductions, net_salary, status (PayrollRecordStatus), created_at, updated_at
Unique: (company_id, payroll_period_id, employee_id)

### payroll_components  (full calculation breakdown — auditable)
id, company_id, payroll_record_id, name, component_type (PayrollComponentType), amount, is_statutory (bool), reference_type (nullable), reference_id (nullable), created_at, updated_at

### employee_loans
id, company_id, employee_id, loan_amount, start_date, installment_amount, number_of_installments, paid_installments, outstanding_amount, interest_rate, status (LoanStatus), remarks, created_at, updated_at

### loan_installments
id, company_id, loan_id, installment_no, due_date, amount, paid_in_payroll_period_id, status, created_at, updated_at

### salary_advances
id, company_id, employee_id, requested_amount, approved_amount, requested_at, approved_by, approved_at, deduction_installments, deduction_start_month, status (AdvanceStatus), remarks, created_at, updated_at

### payslips
id, company_id, payroll_record_id, employee_id, payroll_period_id, gross, total_deductions, net, pdf_path, status (PayslipStatus), generated_at, created_at, updated_at
Unique: (company_id, payroll_record_id, employee_id)

### audit_logs
id, company_id, user_id, action, entity_type, entity_id, old_value (JSON), new_value (JSON), ip_address, user_agent, created_at

### device_sync_logs
id, company_id, device_id, started_at, completed_at, records_received, records_inserted, records_duplicate, records_failed, status (SyncLogStatus), error_message, created_at

## Canonical indexes (SQLAlchemy model must define)

- attendance_logs: (company_id, device_id, event_timestamp), (company_id, employee_id, event_timestamp), unique (company_id, idempotency_key)
- attendance_daily: unique (company_id, employee_id, attendance_date), (company_id, attendance_date, status)
- attendance_logs composite w/ payroll_periods (company_id, year, month)