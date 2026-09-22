from fastapi import APIRouter

from api.v1.endpoints import (
    attendance,
    audit,
    auth,
    companies,
    dashboard,
    device_sync,
    devices,
    employees,
    holidays,
    integrations_essl,
    leaves,
    loans,
    organization,
    overtime,
    payroll,
    payslips,
    reports,
    salary,
    shifts,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(companies.router, prefix="/companies", tags=["Companies"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(organization.departments_router, prefix="/departments", tags=["Departments"])
api_router.include_router(organization.designations_router, prefix="/designations", tags=["Designations"])
api_router.include_router(employees.router, prefix="/employees", tags=["Employees"])
api_router.include_router(devices.router, prefix="/devices", tags=["Devices"])
api_router.include_router(integrations_essl.router, prefix="/integrations/essl", tags=["eSSL Integration"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])
api_router.include_router(shifts.router, prefix="/shifts", tags=["Shifts"])
api_router.include_router(leaves.router, prefix="/leaves", tags=["Leaves"])
api_router.include_router(holidays.router, prefix="/holidays", tags=["Holidays"])
api_router.include_router(overtime.router, prefix="/overtime", tags=["Overtime"])
api_router.include_router(loans.router, prefix="/loans", tags=["Loans"])
api_router.include_router(salary.router, prefix="/salary", tags=["Salary"])
api_router.include_router(payroll.router, prefix="/payroll", tags=["Payroll"])
api_router.include_router(payslips.router, prefix="/payslips", tags=["Payslips"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(device_sync.router, prefix="/device-sync", tags=["Device Connector"])