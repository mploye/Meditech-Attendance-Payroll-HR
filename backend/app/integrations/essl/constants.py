ESSL_OPERATIONS: dict[str, str] = {
    "AddEmployee": "AddEmployee",
    "AddEmployeeByCompanyShortName": "AddEmployeeByCompanyShortName",
    "AddMultipleEmployees": "AddMultipleEmployees",
    "DeleteUser": "DeleteUser",
    "DeleteMultipleEmployees": "DeleteMultipleEmployees",
    "EnrollUserFace": "EnrollUserFace",
    "EnrollUserFP": "EnrollUserFP",
    "BlockUnblockUser": "BlockUnblockUser",
    "GetTransactionsLog": "GetTransactionsLog",
    "GetCommandStatus": "GetCommandStatus",
}

DEFAULT_CAPABILITIES: list[str] = [
    "add_employee",
    "add_multiple",
    "delete_user",
    "enroll_face",
    "get_transactions",
]

ESSL_TRANSACTION_ACTIONS: dict[str, str] = {
    "IN": "CHECK_IN",
    "OUT": "CHECK_OUT",
}