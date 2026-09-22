# API Contract (v1)

Base path: `/api/v1`. All endpoints require `Authorization: Bearer <JWT>` unless noted.
Every business endpoint resolves the tenant from the authenticated user's `company_id`.
Response envelope: success `{"success": true, "data": ...}` / error `{"success": false, "error": {"code","message"}}`.
List endpoints: query params `page` (default 1), `page_size` (default 20), `search`, `status`, `from_date`, `to_date`, `company_id` (SUPER_ADMIN only).

## Auth
| Method | Path | Description |
|---|---|---|
| POST | /auth/register-super-admin | Bootstrap SUPER_ADMIN (first run only). Body: email, password, full_name |
| POST | /auth/login | Body: email, password → {access_token, user} |
| GET | /auth/me | Current user |
| POST | /auth/change-password | Body: old_password, new_password |
| POST | /auth/companies | SUPER_ADMIN creates a company + COMPANY_ADMIN user. Body: company{...}, admin_user{email,password,full_name} → company, admin_user |

## Companies (`/companies`, SUPER_ADMIN/admin)
GET /companies, GET /companies/{id}, PATCH /companies/{id}, PATCH /companies/{id}/settings (lop_policy, statutory_state, timezone, overtime_enabled)

## Users (`/users`)
GET /users, POST /users (create user w/ role), PATCH /users/{id}, POST /users/{id}/reset-password

## Dashboard (`/dashboard`)
GET /dashboard/summary → cards (total_employees, present_today, absent_today, on_leave, late_today, overtime_employees, pending_leaves, pending_payroll, payroll_amount, devices_online, devices_offline)
GET /dashboard/attendance-trend?days=14
GET /dashboard/payroll-trend?months=6
GET /dashboard/department-attendance?start_date&end_date

## Departments (`/departments`) and Designations (`/designations`)
Standard CRUD: GET (list, req `departments.view`), POST, GET /{id}, PATCH /{id}, DELETE /{id}

## Employees (`/employees`)
GET /employees → paginated; filters: department_id, designation_id, status, search
POST /employees → creates employee (body per employee model incl. department_id, designation_id) + optional `device_user_id` + `essl_sync: bool`
GET /employees/{id} → full detail
PATCH /employees/{id}
POST /employees/{id}/salary → create employee_salary (effective_from, salary_structure_id, basic_salary, gross_salary, bank fields)
GET /employees/{id}/salary → active + history
POST /employees/{id}/devices → map employee-device {device_id, device_user_id}
GET /employees/{id}/devices
POST /employees/{id}/devices/sync → trigger eSSL sync for this employee
POST /employees/{id}/associate-user → {email} links an employee to an existing user

## Devices (`/devices`)
GET /devices, POST /devices, GET /devices/{id}, PATCH /devices/{id}, DELETE /devices/{id}
POST /devices/{id}/test → eSSL connection test (or simulated)
POST /devices/{id}/sync → sync now (creates DeviceSyncLog)
GET /devices/{id}/sync-logs
GET /devices/{id}/logs → attendance_logs for device
GET /integrations/essl/config, PATCH /integrations/essl/config (effreq SUPERVISOR) — secret fields write-only
POST /integrations/essl/test → {success, provider, status, message}
POST /integrations/essl/sync → full eSSL sync across enabled devices

## Attendance (`/attendance`)
GET /attendance/daily?date&employee_id&department_id&status&page&page_size
GET /attendance/monthly?month&year&employee_id
GET /attendance/logs?from_date&to_date&device_id&employee_id&page&page_size
POST /attendance/sync → {sync results}
POST /attendance/process?date → runs daily attendance engine for a date (or range from_date,to_date)
POST /attendance/manual → manual IN/OUT log {employee_id, event_type, timestamp, remarks}
PATCH /attendance/daily/{id} → correct daily record (audit)
GET /attendance/daily/{id}
GET /attendance/summary?from_date&to_date&employee_id|department_id → aggregated summary rows

## Shifts (`/shifts`)
CRUD + POST /shifts/{id}/assign {employee_ids[], effective_from}
GET /employees/{id}/shifts → active assignment
POST /shifts/default {shift_id}

## Leaves (`/leaves`)
GET /leaves/types, POST /leaves/types, PATCH /leaves/types/{id}
POST /leaves/apply {employee_id, leave_type_id, start_date, end_date, reason, is_half_day}
GET /leaves/requests?status
POST /leaves/{id}/approve /reject {comment}
GET /leaves/balances?year&employee_id
POST /leaves/balances/init?year → initialize balances for all employees

## Holidays (`/holidays`)
CRUD; GET /holidays?from_date&to_date

## Overtime (`/overtime`)
GET /overtime (filters status, employee_id, from/to) 
POST /overtime {employee_id, date, minutes, rate|null}
POST /overtime/{id}/approve
POST /overtime/{id}/reject

## Salary (`/salary`)
GET /salary/structures, POST /salary/structures {name, code, payment_frequency, effective_from, effective_to, components[]}
GET /salary/structures/{id}
PATCH /salary/structures/{id}
GET /salary/statutory-rules, POST /salary/statutory-rules
PATCH /salary/statutory-rules/{id}
POST /salary/structures/{id}/simulate {basic_salary} → computed gross/deductions breakdown

## Payroll (`/payroll`)
GET /payroll/periods
POST /payroll/periods {month, year}
GET /payroll/periods/{id}
POST /payroll/periods/{id}/calculate → full engine run (transactional). Returns summary {employees_processed, gross, deductions, net, failures[]}
POST /payroll/periods/{id}/review
POST /payroll/periods/{id}/approve
POST /payroll/periods/{id}/lock
GET /payroll/periods/{id}/records
GET /payroll/records/{id} → record + full payroll_components breakdown
GET /payroll/summary?month&year

## Payslips (`/payslips`)
POST /payslips/generate?payroll_period_id → generate payslips for all records in period
GET /payslips?payroll_period_id&employee_id
GET /payslips/{id}/pdf → application/pdf
GET /payslips/mine?month&year (EMPLOYEE own payslips)
POST /payslips/mine/{id}/download → mark DOWNLOADED

## Reports (`/reports`)
GET /reports/attendance/daily?from_date&to_date&format=csv|xlsx|pdf
GET /reports/attendance/monthly?month&year&format
GET /reports/attendance/employee?employee_id&from_date&to_date
GET /reports/attendance/late?from_date&to_date
GET /reports/attendance/missing-punch?from_date&to_date
GET /reports/payroll/monthly?payroll_period_id&format
GET /reports/payroll/salary-register?payroll_period_id&format
GET /reports/payroll/deductions?payroll_period_id
GET /reports/loans?employee_id
CSV/TXT for csv; XLSX for xlsx; PDF for pdf formats.

## Audit (`/audit`)
GET /audit/logs?entity_type&entity_id&action&from_date&to_date&page&page_size (SUPER_ADMIN/COMPANY_ADMIN)
GET /audit/stats

## Connector (`/device-sync`)
POST /device-sync/transactions (auth: X-API-Key = DEVICE_CONNECTOR_API_KEY)
Body: {device_id (serial or uuid), transactions: [{device_user_id, timestamp, event_type}]}
Response: {success, received, inserted, duplicates, failed}
GET /device-sync/status → connectivity/health summary