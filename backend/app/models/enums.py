from enum import Enum


class Role(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    COMPANY_ADMIN = "COMPANY_ADMIN"
    HR_ADMIN = "HR_ADMIN"
    HR_MANAGER = "HR_MANAGER"
    PAYROLL_ADMIN = "PAYROLL_ADMIN"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class EmployeeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    RESIGNED = "RESIGNED"
    TERMINATED = "TERMINATED"
    ON_NOTICE = "ON_NOTICE"


class EmploymentType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERN = "INTERN"
    PROBATION = "PROBATION"


class DeviceProvider(str, Enum):
    ESSL = "ESSL"
    ORCUS = "ORCUS"
    OTHER = "OTHER"


class DeviceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    SYNCING = "SYNCING"
    ERROR = "ERROR"
    DISABLED = "DISABLED"


class DeviceType(str, Enum):
    FACE_PUNCH = "FACE_PUNCH"
    FINGERPRINT = "FINGERPRINT"
    CARD = "CARD"
    MOBILE = "MOBILE"
    WEB = "WEB"


class MappingSyncStatus(str, Enum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class EventType(str, Enum):
    IN = "IN"
    OUT = "OUT"
    UNKNOWN = "UNKNOWN"


class AttendanceStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LEAVE = "LEAVE"
    HOLIDAY = "HOLIDAY"
    WEEKEND = "WEEKEND"
    HALF_DAY = "HALF_DAY"
    MISSING_PUNCH = "MISSING_PUNCH"
    ON_DUTY = "ON_DUTY"


class LeaveTypeCategory(str, Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"
    SICK = "SICK"
    CASUAL = "CASUAL"
    COMPOFF = "COMPOFF"
    OTHER = "OTHER"


class LeaveStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class OvertimeStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SalaryComponentType(str, Enum):
    EARNING = "EARNING"
    DEDUCTION = "DEDUCTION"


class CalculationType(str, Enum):
    FIXED = "FIXED"
    PERCENTAGE_OF_BASIC = "PERCENTAGE_OF_BASIC"
    PERCENTAGE_OF_GROSS = "PERCENTAGE_OF_GROSS"
    FORMULA = "FORMULA"


class SalaryFrequency(str, Enum):
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    HOURLY = "HOURLY"


class StatutoryRuleType(str, Enum):
    PF = "PF"
    ESI = "ESI"
    PT = "PT"
    TDS = "TDS"
    OTHER = "OTHER"


class PayrollPeriodStatus(str, Enum):
    DRAFT = "DRAFT"
    CALCULATING = "CALCULATING"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    LOCKED = "LOCKED"


class PayrollRecordStatus(str, Enum):
    DRAFT = "DRAFT"
    CALCULATED = "CALCULATED"
    APPROVED = "APPROVED"
    LOCKED = "LOCKED"
    PROCESSED = "PROCESSED"


class LoanStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    DEFAULTED = "DEFAULTED"


class AdvanceStatus(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    PAID = "PAID"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class SyncLogStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class LogSource(str, Enum):
    ESSL = "ESSL"
    DEVICE = "DEVICE"
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    API = "API"


class HolidayType(str, Enum):
    NATIONAL = "NATIONAL"
    STATE = "STATE"
    COMPANY = "COMPANY"
    OPTIONAL = "OPTIONAL"


class PayslipStatus(str, Enum):
    GENERATED = "GENERATED"
    DOWNLOADED = "DOWNLOADED"
    PRINTED = "PRINTED"
    LOCKED = "LOCKED"


class PayrollComponentType(str, Enum):
    EARNING = "EARNING"
    DEDUCTION = "DEDUCTION"


class LOPPolicy(str, Enum):
    CALENDAR_DAYS = "CALENDAR_DAYS"
    WORKING_DAYS = "WORKING_DAYS"
    FIXED_30 = "FIXED_30"