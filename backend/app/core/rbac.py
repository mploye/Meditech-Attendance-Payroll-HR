from models.enums import Role

# module.action permissions grouped by role
PERMISSIONS: dict[Role, set[str]] = {
    Role.SUPER_ADMIN: {
        "*",
    },
    Role.COMPANY_ADMIN: {
        "companies.view", "companies.edit",
        "users.view", "users.create", "users.edit", "users.delete",
        "dashboard.view",
        "employees.view", "employees.create", "employees.edit", "employees.delete", "employees.sync",
        "departments.view", "departments.create", "departments.edit", "departments.delete",
        "designations.view", "designations.create", "designations.edit", "designations.delete",
        "devices.view", "devices.create", "devices.edit", "devices.delete", "devices.test", "devices.sync",
        "attendance.view", "attendance.edit", "attendance.sync", "attendance.process",
        "shifts.view", "shifts.create", "shifts.edit", "shifts.delete",
        "leaves.view", "leaves.create", "leaves.approve", "leaves.edit",
        "holidays.view", "holidays.create", "holidays.edit", "holidays.delete",
        "overtime.view", "overtime.create", "overtime.approve", "overtime.edit",
        "loans.view", "loans.create", "loans.edit",
        "salary.view", "salary.create", "salary.edit", "salary.delete",
        "payroll.view", "payroll.create", "payroll.calculate", "payroll.review", "payroll.approve", "payroll.lock",
        "payslips.view", "payslips.generate", "payslips.download",
        "reports.view",
        "audit.view",
        "settings.view", "settings.edit",
    },
    Role.HR_ADMIN: {
        "dashboard.view",
        "employees.view", "employees.create", "employees.edit", "employees.sync",
        "departments.view", "departments.create", "departments.edit", "departments.delete",
        "designations.view", "designations.create", "designations.edit", "designations.delete",
        "devices.view", "devices.create", "devices.edit", "devices.test", "devices.sync",
        "attendance.view", "attendance.edit", "attendance.sync", "attendance.process",
        "shifts.view", "shifts.create", "shifts.edit", "shifts.delete",
        "leaves.view", "leaves.create", "leaves.approve", "leaves.edit",
        "holidays.view", "holidays.create", "holidays.edit", "holidays.delete",
        "overtime.view", "overtime.create", "overtime.approve", "overtime.edit",
        "loans.view", "loans.create", "loans.edit",
        "reports.view",
    },
    Role.HR_MANAGER: {
        "dashboard.view",
        "employees.view", "employees.edit",
        "departments.view",
        "designations.view",
        "devices.view", "devices.test", "devices.sync",
        "attendance.view", "attendance.sync", "attendance.process", "attendance.edit",
        "shifts.view",
        "leaves.view", "leaves.create", "leaves.approve", "leaves.edit",
        "holidays.view",
        "overtime.view", "overtime.create", "overtime.approve",
        "reports.view",
    },
    Role.PAYROLL_ADMIN: {
        "dashboard.view",
        "employees.view",
        "attendance.view",
        "salary.view", "salary.create", "salary.edit",
        "payroll.view", "payroll.create", "payroll.calculate", "payroll.review", "payroll.approve", "payroll.lock",
        "payslips.view", "payslips.generate", "payslips.download",
        "reports.view",
        "settings.view", "settings.edit",
    },
    Role.MANAGER: {
        "dashboard.view",
        "employees.view",
        "attendance.view",
        "leaves.view", "leaves.approve",
        "overtime.approve",
        "reports.view",
    },
    Role.EMPLOYEE: {
        "dashboard.view",
        "attendance.view.own",
        "leaves.view.own", "leaves.create",
        "payslips.view.own", "payslips.download.own",
        "employees.view.own",
    },
}


class RBACNotConfigured(Exception):
    pass


def has_permission(role: Role, permission: str) -> bool:
    perms = PERMISSIONS.get(role, set())
    if "*" in perms:
        return True
    return permission in perms


def require_permission(role: Role, permission: str) -> bool:
    return has_permission(role, permission)