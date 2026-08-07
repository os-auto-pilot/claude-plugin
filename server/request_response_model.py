import re
from typing import List, Literal, Optional
import uuid

from pydantic import BaseModel, Field, field_validator

#: Where users are sent for load tests too long to run from here.
AUTOPILOT_PORTAL_URL = "https://www.osautopilot.com"

# Load profile defaults and bounds. These mirror the backend's
# com.oniesoft.util.LoadProfileValidator, which is the source of truth — it applies
# the defaults itself when a field is omitted. They are restated here only so the
# run-tests skill can show the user what will be used before starting a run.
DEFAULT_VIRTUAL_USERS = 100
DEFAULT_DURATION = "1m"
DEFAULT_RAMP_PATTERN = "linear"
MAX_VIRTUAL_USERS = 50000

#: This plugin's own ceiling on load-test duration — stricter than the backend, which
#: accepts hours. Anything longer is redirected to AUTOPILOT_PORTAL_URL.
MAX_DURATION_MINUTES = 3
MAX_DURATION_SECONDS = MAX_DURATION_MINUTES * 60

#: The load profile shown to the user before a Performance run starts.
LOAD_PROFILE_DEFAULTS = {
    "virtualUsers": DEFAULT_VIRTUAL_USERS,
    "rampPattern": DEFAULT_RAMP_PATTERN,
    "duration": DEFAULT_DURATION,
}

ALLOWED_DEFECT_STATES = {"Open", "Inprogress", "Reopened", "Closed", "Rejected"}
ALLOWED_DEFECT_PRIORITIES = {"Minor", "Major", "Blocker", "Critical"}
ALLOWED_DEFECT_STATUSES = {
    "Assigned",
    "Planned",
    "Fix Inprogress",
    "In Review",
    "In Test",
    "Bug Reproduced",
    "Fix Failed",
    "Fixed",
    "Verified",
    "Automated",
    "Done",
    "Duplicate",
    "Not a Bug",
    "Won't Fix",
    "UnAssigned",
}
ALLOWED_TEST_MODES = {"Web", "API", "Mobile", "Performance"}
ALLOWED_TEST_TYPES = {"Automation", "Manual", "AI Automated", "AI Draft"}
ALLOWED_SEVERITIES = {"Minor", "Major", "Blocker", "Critical"}
ALLOWED_TEST_RUN_STATUSES = {
    "New",
    "Completed",
    "Scheduled",
    "Auto Scheduled",
    "Auto Trigger",
    "Skipped",
    "Scheduled Computed",
    "Auto Scheduled Completed",
    "Auto Trigger Completed",
    "In Progress",
    "Aborted",
}
ALLOWED_TEST_TYPES_FOR_TEST_RUN_FILTERS = {"Automation", "Manual", "AI Automated"}


def _normalize_csv_filter(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    parts = [item.strip() for item in value.split(",") if item.strip()]
    if not parts:
        return None
    return ",".join(parts)


class FeatureIdByNameOrUniqueKeyInput(BaseModel):
    projectId: Optional[uuid.UUID] = Field(
        None, description="ID of the project for which to retrieve feature ID"
    )
    identifier: str = Field(
        ..., description="Name or unique key of the feature to retrieve ID for"
    )


class FeatureCreationOutput(BaseModel):
    id: uuid.UUID = Field(..., description="ID of the feature")
    name: str = Field(..., description="Name of the feature")
    uniqueKey: Optional[str] = Field(
        None, description="Unique key generated for the feature"
    )


class FeatureCreationInput(BaseModel):
    name: str = Field(
        ..., description="Name of the feature to be created", max_length=20
    )
    description: str = Field(
        ..., description="Description of the feature to be created", max_length=600
    )
    companyId: uuid.UUID = Field(
        ..., description="ID of the company for which the module is being created"
    )
    projectId: Optional[uuid.UUID] = Field(
        None, description="ID of the project for which the feature is being created"
    )
    moduleId: uuid.UUID = Field(
        ..., description="ID of the module for which the feature is being created"
    )


class ModuleIdByNameOrUniqueKeyInput(BaseModel):
    projectId: Optional[uuid.UUID] = Field(
        None, description="ID of the project for which to retrieve module ID"
    )
    identifier: str = Field(
        ..., description="Name or unique key of the module to retrieve ID for"
    )


class ModuleOutputResponse(BaseModel):
    id: uuid.UUID = Field(..., description="ID of the module")
    moduleName: str = Field(..., description="Name of the module")
    uniqueKey: Optional[str] = Field(
        None, description="Unique key generated for the module"
    )


class ModuleCreationInput(BaseModel):
    moduleName: str = Field(
        ..., description="Name of the module to be created", max_length=20
    )
    description: str = Field(
        ..., description="Description of the module to be created", max_length=600
    )
    companyId: uuid.UUID = Field(
        ..., description="ID of the company for which the module is being created"
    )
    projectId: Optional[uuid.UUID] = Field(
        None, description="ID of the project for which the module is being created"
    )


class ProjectIdByNameInput(BaseModel):
    companyId: uuid.UUID = Field(
        ..., description="ID of the company for which to retrieve admin projects"
    )
    name: str = Field(
        ...,
        description="Name of the project to filter by when retrieving admin projects",
    )


class ProjectIdByNameOutput(BaseModel):
    id: uuid.UUID = Field(..., description="ID of the admin project")
    name: str = Field(..., description="Name of the admin project")


class GetEnvironmentDetailsByNameOrUniqueKeyInput(BaseModel):
    """Model representing the input for retrieving environment details by name or unique key"""

    identifier: str = Field(
        ...,
        description="Name or unique key of the web environment to retrieve details for",
    )
    projectId: Optional[uuid.UUID] = Field(
        None, description="ID of the project for which to retrieve module ID"
    )


class CreateWebEnvironmentOutput(BaseModel):
    """Model representing the output of creating a Web Environment"""

    id: uuid.UUID = Field(..., description="ID of the created web environment")
    uniqueKey: Optional[str] = Field(
        None, description="Unique key generated for the created web environment"
    )
    serverUrl: str = Field(..., description="URL of the created web environment")
    serverName: str = Field(..., description="Name of the created web environment")
    apiBaseURL: str = Field(
        ..., description="API base URL of the created web environment"
    )
    description: str = Field(
        ..., description="Description of the created web environment"
    )
    basicAuth: bool = Field(
        default=False, description="Indicates if basic authentication is enabled"
    )
    enableBook: bool = Field(
        default=False,
        description="Indicates if book is enabled for the web environment",
    )


class GetUserDetailsByIdOrEmailOrUniqueKeyInput(BaseModel):
    """Model representing the input for retrieving user details by ID, email, or unique key"""

    identifier: str = Field(
        ...,
        description="ID, email, or unique key of the user to retrieve details for",
    )
    companyId: uuid.UUID = Field(
        ..., description="ID of the company for which to retrieve user details"
    )


class GetUserDetailsOutput(BaseModel):
    """Model representing the output for retrieving user details by ID, email, or unique key"""

    empId: str = Field(..., description="Unique Key of the user")
    empName: str = Field(
        ...,
        description="Name of the user, can be used in createdBy, author, assignedTo and other user name fields while creating anything",
    )
    empEmail: str = Field(..., description="Email of the user")
    lastName: str = Field(..., description="Last name of the user")
    empRole: str = Field(..., description="Role of the user")
    userId: uuid.UUID = Field(..., description="User ID of the user")
    status: bool = Field(
        ..., description="Status of the user (active/inactive) true means active"
    )
    # deleted: bool = Field(
    #     ...,
    #     description="Indicates if the user is deleted or not, true means not deleted",
    # )
    projectList: list = Field(
        ..., description="List of projects associated with the user"
    )
    serversList: list = Field(
        ..., description="List of web and mobile environments associated with the user"
    )


class TestRunCreationInput(BaseModel):
    """Model representing the input for creating a test run"""

    testRunName: str = Field(..., description="Name of the test run")
    projectId: Optional[uuid.UUID] = Field(
        None, description="ID of the project for which the test run is being created"
    )
    createdBy: str = Field(
        ..., description="Name (EmpName) of the user who created the test run"
    )


class TestRunCreationOutput(BaseModel):
    """Model representing the output for creating a test run"""

    id: str = Field(..., description="ID of the created test run")
    testRunName: str = Field(..., description="Name of the created test run")
    uniqueKey: Optional[str] = Field(
        None, description="Unique key generated for the created test run"
    )


class TestRunDetailsInput(BaseModel):
    """Model representing the input for retrieving test run details"""

    nameOrUniqueKey: Optional[str] = Field(
        None,
        description="Name or unique key of the test run to retrieve details for",
    )
    projectId: Optional[uuid.UUID] = Field(
        None, description="ID of the project for which to retrieve test run details"
    )
    status: Optional[str] = Field(
        None,
        description="Status filter. Supports single or comma-separated values from New, Completed, Scheduled, Auto Scheduled, Auto Trigger, Skipped, Scheduled Computed, Auto Scheduled Completed, Auto Trigger Completed, In Progress, Aborted",
    )
    createdBy: Optional[str] = Field(
        None, description="Name or Emp Name of the user who created the test run"
    )

    @field_validator("status", mode="before")
    @classmethod
    def validate_status_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None

        canonical_map = {
            "new": "New",
            "completed": "Completed",
            "scheduled": "Scheduled",
            "auto scheduled": "Auto Scheduled",
            "auto trigger": "Auto Trigger",
            "skipped": "Skipped",
            "scheduled computed": "Scheduled Computed",
            "auto scheduled completed": "Auto Scheduled Completed",
            "auto trigger completed": "Auto Trigger Completed",
            "in progress": "In Progress",
            "aborted": "Aborted",
        }
        converted: list[str] = []
        invalid: list[str] = []

        for item in normalized.split(","):
            canonical = canonical_map.get(item.lower())
            if canonical is None:
                invalid.append(item)
            else:
                converted.append(canonical)

        if invalid:
            raise ValueError(
                f"Invalid status value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_TEST_RUN_STATUSES))}"
            )

        return ",".join(converted)


class TestRunDetailsOutput(BaseModel):
    """Model representing the output for retrieving test run details"""

    id: str = Field(..., description="ID of the test run")
    testRunName: str = Field(..., description="Name of the test run")
    uniqueKey: Optional[str] = Field(None, description="Unique key of the test run")
    status: Optional[
        Literal[
            "New",
            "Completed",
            "Scheduled",
            "Auto Scheduled",
            "Auto Trigger",
            "Skipped",
            "Scheduled Computed",
            "Auto Scheduled Completed",
            "Auto Trigger Completed",
            "In Progress",
            "Aborted",
        ]
    ] = Field(None, description="Status of the test run")
    createdBy: Optional[str] = Field(
        None, description="Name or Emp Name of the user who created the test run"
    )
    testCaseCount: Optional[int] = Field(
        None, description="Number of test cases in the test run"
    )
    automationStatus: Optional[Literal["Completed", "New", "In Progress"]] = Field(
        None, description="Automation status of the test run"
    )
    scheduleTime: Optional[str] = Field(
        None, description="Scheduled time of the test run"
    )
    scheduleDate: Optional[str] = Field(
        None, description="Scheduled date of the test run"
    )
    executedAt: Optional[str] = Field(
        None, description="Execution date time of the test run"
    )
    executeTimeInMillis: Optional[int] = Field(
        None, description="Execution time in milliseconds of the test run"
    )
    passPercentage: Optional[float | str] = Field(
        None, description="Pass percentage of the test run"
    )


class AddOrRemoveTestCasesFromTestRunInput(BaseModel):
    """Model representing the input for adding or removing test cases from a test run"""

    id: uuid.UUID = Field(
        ...,
        description="ID of the test run to which test cases will be added or removed",
    )
    projectId: Optional[uuid.UUID] = Field(
        None,
        description="ID of the project for which to add or remove test cases from the test run",
    )
    status: Optional[str] = Field(
        None,
        description="Status of the test run. Supports single or comma-separated values from New, Completed, Scheduled, Auto Scheduled, Auto Trigger, Skipped, Scheduled Computed, Auto Scheduled Completed, Auto Trigger Completed, In Progress, Aborted",
    )
    nameOrUniqueKey: Optional[str] = Field(
        None,
        description="Name or unique key of the test case to be added or removed. Supports a single value or a comma-separated list. Unique keys are resolved directly to UUIDs before updating the test run.",
    )
    action: Literal["Add", "Remove"] = Field(
        ..., description="Action to be performed, accepting only 'Add' or 'Remove'"
    )
    testRunName: Optional[str] = Field(
        None,
        description="Name of the test run to which test cases will be added or removed",
    )
    # testCaseId: Optional[list[uuid.UUID]] = Field(
    #     ...,
    #     description="List of test case IDs to be added or removed from the test run. Can get these ids by providing filter criteria like module name, feature name, author, test mode, and test type while adding or removing test cases to the test run.",
    # )
    # testCaseIdsToRemove: Optional[list[uuid.UUID]] = Field(
    #     ..., description="List of test case IDs to be removed from the test run"
    # )
    moduleName: Optional[str] = Field(
        None,
        description="Module name filter for the test cases to be added or removed from the test run. Supports a single value or a comma-separated list of module names.",
    )
    featureName: Optional[str] = Field(
        None,
        description="Feature name filter for the test cases to be added or removed from the test run. Supports a single value or a comma-separated list of feature names.",
    )
    author: Optional[str] = Field(
        None,
        description="Author filter for the test cases to be added or removed from the test run. Supports a single value or a comma-separated list of author names.",
    )
    testMode: Optional[str] = Field(
        None,
        description="Test mode filter for the test cases to be added or removed from the test run. Supports one or more comma-separated values from 'Web', 'Api', 'Mobile', or 'Performance'.",
    )
    testType: Optional[str] = Field(
        None,
        description="Test type filter for the test cases to be added or removed from the test run. Supports one or more comma-separated values from 'Automation', 'Manual', or 'AI Automated'.",
    )
    severity: Optional[str] = Field(
        None,
        description="Severity filter for the test cases to be added or removed from the test run. Supports one or more comma-separated values from 'Minor', 'Major', 'Blocker', or 'Critical'.",
    )

    @field_validator("nameOrUniqueKey", mode="before")
    @classmethod
    def normalize_name_or_unique_key_csv(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_csv_filter(value)

    @field_validator("status", mode="before")
    @classmethod
    def validate_status_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None

        canonical_map = {
            "new": "New",
            "completed": "Completed",
            "scheduled": "Scheduled",
            "auto scheduled": "Auto Scheduled",
            "auto trigger": "Auto Trigger",
            "skipped": "Skipped",
            "scheduled computed": "Scheduled Computed",
            "auto scheduled completed": "Auto Scheduled Completed",
            "auto trigger completed": "Auto Trigger Completed",
            "in progress": "In Progress",
            "aborted": "Aborted",
        }
        converted: list[str] = []
        invalid: list[str] = []

        for item in normalized.split(","):
            canonical = canonical_map.get(item.lower())
            if canonical is None:
                invalid.append(item)
            else:
                converted.append(canonical)

        if invalid:
            raise ValueError(
                f"Invalid status value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_TEST_RUN_STATUSES))}"
            )

        return ",".join(converted)

    @field_validator("testMode", mode="before")
    @classmethod
    def validate_test_mode_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None

        canonical_map = {"web": "Web", "api": "API", "mobile": "Mobile"}
        converted: list[str] = []
        invalid: list[str] = []

        for item in normalized.split(","):
            canonical = canonical_map.get(item.lower())
            if canonical is None:
                invalid.append(item)
            else:
                converted.append(canonical)

        if invalid:
            raise ValueError(
                f"Invalid testMode value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_TEST_MODES))}"
            )

        return ",".join(converted)

    @field_validator("testType", mode="before")
    @classmethod
    def validate_test_type_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None

        canonical_map = {
            "automation": "Automation",
            "ai automated": "AI Automated",
        }
        converted: list[str] = []
        invalid: list[str] = []

        for item in normalized.split(","):
            canonical = canonical_map.get(item.lower())
            if canonical is None:
                invalid.append(item)
            else:
                converted.append(canonical)

        if invalid:
            raise ValueError(
                f"Invalid testType value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_TEST_TYPES_FOR_TEST_RUN_FILTERS))}"
            )

        return ",".join(converted)

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None

        canonical_map = {
            "minor": "Minor",
            "major": "Major",
            "blocker": "Blocker",
            "critical": "Critical",
        }
        converted: list[str] = []
        invalid: list[str] = []

        for item in normalized.split(","):
            canonical = canonical_map.get(item.lower())
            if canonical is None:
                invalid.append(item)
            else:
                converted.append(canonical)

        if invalid:
            raise ValueError(
                f"Invalid severity value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_SEVERITIES))}"
            )

        return ",".join(converted)

    @field_validator("moduleName", "featureName", "author", mode="before")
    @classmethod
    def normalize_text_filters_csv(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_csv_filter(value)


class GetTestCasesUUIDByUniqueKeyInput(BaseModel):
    """Model representing the input for retrieving test case UUIDs by unique keys in a project"""

    uniqueKeys: list[str] = Field(
        ...,
        description="List of test case unique keys to resolve into UUIDs",
        min_length=1,
    )
    active: Optional[bool] = Field(
        False, description="Filter test cases by active status, true means active"
    )
    deleted: Optional[bool] = Field(
        False, description="Filter test cases by deleted status, true means deleted"
    )
    projectId: uuid.UUID = Field(
        ...,
        description="ID of the project for which to retrieve assigned environments for the user",
    )


class GetEnvironmentsAssignedToUserInput(BaseModel):
    """Model representing the input for retrieving environments assigned to a user"""

    userID: uuid.UUID = Field(
        ...,
        description="ID or userId of the user to retrieve assigned environments for",
    )
    projectId: Optional[uuid.UUID] = Field(
        None,
        description="ID of the project for which to retrieve assigned environments for the user",
    )


class GetEnvironmentsAssignedToUserOutput(BaseModel):
    """Model representing the output for retrieving environments assigned to a user"""

    id: uuid.UUID = Field(..., description="ID of the assigned environment")
    uniqueKey: Optional[str] = Field(
        None, description="Unique key of the assigned environment"
    )
    serverName: str = Field(..., description="Name of the assigned environment")
    serverUrl: str = Field(..., description="URL of the assigned environment")
    apiBaseURL: str = Field(..., description="API base URL of the assigned environment")
    description: str = Field(..., description="Description of the assigned environment")
    basicAuth: bool = Field(
        ...,
        description="Indicates if basic authentication is enabled for the assigned environment",
    )
    enableBook: bool = Field(
        ..., description="Indicates if book is enabled for the assigned environment"
    )
    deleted: bool = Field(
        ..., description="Indicates if the assigned environment is deleted or not"
    )


class GetProjectsAssignedToUserInput(BaseModel):
    """Model representing the input for retrieving projects assigned to a user"""

    userID: uuid.UUID = Field(
        ..., description="ID or userId of the user to retrieve assigned projects for"
    )


class GetProjectsAssignedToUserOutput(BaseModel):
    """Model representing the output for retrieving projects assigned to a user"""

    id: uuid.UUID = Field(..., description="ID of the assigned project")
    uniqueKey: Optional[str] = Field(
        None, description="Unique key of the assigned project"
    )
    projectName: str = Field(..., description="Name of the assigned project")
    admin: Optional[str] = Field(
        ..., description="Name of the admin of the assigned project"
    )
    deleted: bool = Field(
        ..., description="Indicates if the assigned project is deleted or not"
    )
    agileAccess: bool = Field(
        ..., description="Indicates if agile access is enabled for the assigned project"
    )


class GetTestCasesWithFiltersInAProjectInput(BaseModel):
    """Model representing the input for retrieving test cases with filters in a project"""

    nameOrUniqueKey: Optional[str] = Field(
        None, description="name or unique key of the test case"
    )
    projectId: Optional[uuid.UUID] = Field(
        default=None,
        description="ID of the project to search test cases in; falls back to the configured default when omitted",
    )
    active: Optional[bool] = Field(
        False, description="Filter test cases by active status, false means active"
    )
    deleted: Optional[bool] = Field(
        False, description="Filter test cases by deleted status, true means deleted"
    )
    testMode: Optional[str] = Field(
        None,
        description="Test mode to filter test cases, accepting only 'Web', 'API', 'Mobile', or 'Performance' or combination of these in comma separated format (e.g. Web,Api) to filter test cases belonging to any of the provided test modes",
    )
    author: Optional[str] = Field(
        None, description="Name of the author to filter test cases by author name"
    )
    severity: Optional[str] = Field(
        None,
        description="Severity to filter test cases, accepting only 'Minor', 'Major', 'Blocker', or 'Critical' or combination of these in comma separated format (e.g. Minor,Major) to filter test cases belonging to any of the provided severity",
    )
    testType: Optional[str] = Field(
        None,
        description="Test type to filter test cases, accepting only 'Automation', 'Manual', 'AI Automated', or 'AI Draft' or combination of these in comma separated format (e.g. Automation,Manual) to filter test cases belonging to any of the provided test types",
    )
    moduleName: Optional[str] = Field(
        None,
        description="Name of the module to filter test cases, can use combination of module names in comma separated format (e.g. Module1,Module2) to filter test cases belonging to any of the provided modules",
    )
    featureName: Optional[str] = Field(
        None,
        description="Name of the feature to filter test cases, can use combination of feature names in comma separated format (e.g. Feature1,Feature2) to filter test cases belonging to any of the provided features",
    )

    @field_validator("testMode", mode="before")
    @classmethod
    def validate_test_mode_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None

        canonical_map = {"web": "Web", "api": "API", "mobile": "Mobile", "performance": "Performance"}
        converted: list[str] = []
        invalid: list[str] = []

        for item in normalized.split(","):
            canonical = canonical_map.get(item.lower())
            if canonical is None:
                invalid.append(item)
            else:
                converted.append(canonical)

        if invalid:
            raise ValueError(
                f"Invalid testMode value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_TEST_MODES))}"
            )

        return ",".join(converted)

    @field_validator("testType", mode="before")
    @classmethod
    def validate_test_type_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None

        canonical_map = {
            "automation": "Automation",
            "manual": "Manual",
            "ai automated": "AI Automated",
            "ai draft": "AI Draft",
        }
        converted: list[str] = []
        invalid: list[str] = []

        for item in normalized.split(","):
            canonical = canonical_map.get(item.lower())
            if canonical is None:
                invalid.append(item)
            else:
                converted.append(canonical)

        if invalid:
            raise ValueError(
                f"Invalid testType value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_TEST_TYPES))}"
            )

        return ",".join(converted)

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None

        canonical_map = {
            "minor": "Minor",
            "major": "Major",
            "blocker": "Blocker",
            "critical": "Critical",
        }
        converted: list[str] = []
        invalid: list[str] = []

        for item in normalized.split(","):
            canonical = canonical_map.get(item.lower())
            if canonical is None:
                invalid.append(item)
            else:
                converted.append(canonical)

        if invalid:
            raise ValueError(
                f"Invalid severity value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_SEVERITIES))}"
            )

        return ",".join(converted)


class GetTestCasesWithFiltersInAProjectOutput(BaseModel):
    """Model representing the output for retrieving test cases with filters in a project"""

    id: uuid.UUID = Field(..., description="ID of the test case")
    uniqueKey: Optional[str] = Field(None, description="Unique key of the test case")
    testCaseName: str = Field(..., description="Title of the test case")
    module: str = Field(..., description="Module of the test case")
    feature: str = Field(..., description="Feature of the test case")
    testType: Literal["Automation", "Manual", "AI Automated", "AI Draft"] = Field(
        ..., description="Test type of the test case"
    )
    testMode: Literal["Web", "API", "Mobile", "Performance"] = Field(
        ..., description="Test mode of the test case"
    )
    author: str = Field(..., description="Author of the test case")
    severity: Literal["Minor", "Major", "Blocker", "Critical"] = Field(
        ..., description="Severity of the test case"
    )
    createdAt: str = Field(..., description="Creation date of the test case")
    updatedAt: str = Field(..., description="Last update date of the test case")
    avgTime: Optional[int] = Field(
        None, description="Average execution time in seconds of the test case"
    )
    jiraDefectId: Optional[str] = Field(
        None, description="Jira defect ID linked to the test case, if any"
    )


class GetTestCasesWithFiltersInAProjectOutputLarge(BaseModel):
    """Model representing the output for retrieving test cases with filters in a project with large data"""

    id: uuid.UUID = Field(..., description="ID of the test case")
    uniqueKey: Optional[str] = Field(None, description="Unique key of the test case")
    testCaseName: str = Field(..., description="Title of the test case")


class RunTestCaseInput(BaseModel):
    """Model representing the input for running a test case"""

    testCaseId: uuid.UUID = Field(..., description="ID of the test case to be executed")
    userId: uuid.UUID = Field(
        ..., description="ID of the test run in which the test case will be executed"
    )
    browserType: Optional[Literal["Chrome", "Firefox", "Edge", "Safari"]] = Field(
        default="Chrome",
        description="Browser type in which to execute the test case, accepting only 'Chrome', 'Firefox', 'Edge', or 'Safari'",
    )
    envId: uuid.UUID = Field(
        ..., description="ID of the environment in which to execute the test case"
    )
    platform: Optional[str] = Field(
        "server,server",
        description="Platform in which to execute the test case, either in server or local. For server 'server, server' and for local 'local, machineId'",
    )
    # Load profile — Performance test cases only. Left as None rather than given
    # defaults here on purpose: the backend's LoadProfileValidator already owns the
    # defaults (100 VUs / "1m" / "linear"), and duplicating them client-side is how
    # they drift. Omitted fields are dropped from the payload so the backend applies
    # its own. See LOAD_PROFILE_DEFAULTS for the values surfaced to the user.
    virtualUsers: Optional[int] = Field(
        None,
        ge=1,
        le=MAX_VIRTUAL_USERS,
        description=(
            "Number of virtual users to simulate. Performance test cases only. "
            f"Omit to use the backend default ({DEFAULT_VIRTUAL_USERS})."
        ),
    )
    rampPattern: Optional[Literal["linear", "incremental", "waved"]] = Field(
        None,
        description=(
            "Ramp pattern: 'linear', 'incremental', or 'waved'. Performance test "
            f"cases only. Omit to use the backend default ('{DEFAULT_RAMP_PATTERN}')."
        ),
    )
    duration: Optional[str] = Field(
        None,
        description=(
            "Load test duration as '<int>[smh]' (e.g. '30s', '2m') or a bare integer "
            "of seconds. Performance test cases only. Capped at "
            f"{MAX_DURATION_MINUTES} minutes from this plugin. Omit to use the "
            f"backend default ('{DEFAULT_DURATION}')."
        ),
    )

    @field_validator("rampPattern", mode="before")
    @classmethod
    def normalize_ramp_pattern(cls, value: Optional[str]) -> Optional[str]:
        """Accept 'Linear'/'LINEAR' etc. — the backend lower-cases these anyway."""
        if value is None or not isinstance(value, str):
            return value
        return value.strip().lower()

    @field_validator("duration", mode="before")
    @classmethod
    def validate_duration(cls, value: Optional[str]) -> Optional[str]:
        """Parse the backend's duration grammar, then enforce this plugin's cap.

        The cap is enforced here rather than only in the run-tests skill so that it
        holds however run_test_case is reached — skill instructions can be skipped,
        a model-level validator cannot. Long-running load tests belong on the
        official portal, which is built to supervise them.
        """
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None

        match = re.fullmatch(r"(\d+)([smh])", raw)
        if match:
            amount, unit = int(match.group(1)), match.group(2)
            seconds = amount * {"s": 1, "m": 60, "h": 3600}[unit]
        elif raw.isdigit():
            # The backend also accepts a bare positive integer of seconds.
            seconds = int(raw)
        else:
            raise ValueError(
                f'duration must be "<int>[smh]" (e.g. "30s", "2m") or a positive '
                f'integer of seconds, but was "{value}"'
            )

        if seconds <= 0:
            raise ValueError(f'duration must be greater than zero, but was "{value}"')

        if seconds > MAX_DURATION_SECONDS:
            raise ValueError(
                f"duration {raw} exceeds the {MAX_DURATION_MINUTES}-minute limit for "
                f"test runs started from this plugin. Run longer load tests from the "
                f"Autopilot portal instead: {AUTOPILOT_PORTAL_URL}"
            )
        return raw


class ScheduleTestRunInput(BaseModel):
    """Model representing the input for scheduling a test run"""

    id: uuid.UUID = Field(
        ...,
        description="ID of the test run to be scheduled",
    )
    projectId: Optional[uuid.UUID] = Field(
        None,
        description="ID of the project for which to schedule the test run",
    )
    scheduledDate: str = Field(
        ...,
        description="Scheduled date for the test run execution in YYYY-MM-DD format (e.g. '2024-12-31')",
    )
    scheduledTime: str = Field(
        description="Scheduled time for the test run execution in HH:mm format (e.g. '23:59'). ",
    )
    userTimezone: str = Field(
        ...,
        description="Timezone of the user scheduling the test run, in IANA format (e.g. 'America/New_York')",
    )
    environment: str = Field(
        ...,
        description="Environment Name in which to run the test (e.g. 'staging', 'production')",
    )
    envID: uuid.UUID = Field(
        ...,
        description="Environment ID in which to run the test",
    )
    userID: uuid.UUID = Field(
        ...,
        description="User ID of the user scheduling the test run",
    )
    userName: str = Field(
        ...,
        description="Name of the user scheduling the test run",
    )


class CloneTestRunInput(BaseModel):
    """Model representing the input for cloning a test run"""

    id: uuid.UUID = Field(
        ...,
        description="ID of the test run to be cloned",
    )
    projectId: Optional[uuid.UUID] = Field(
        None,
        description="ID of the project for which to clone the test run",
    )
    testRunName: str = Field(
        ...,
        description="Name of the test run to be cloned",
    )
    userName: str = Field(
        ...,
        description="Name of the user cloning the test run",
    )
    userId: uuid.UUID = Field(
        ...,
        description="ID of the user cloning the test run",
    )


class ClonedTestRunOutput(BaseModel):
    """Model representing the output for cloning a test run"""

    id: uuid.UUID = Field(
        ...,
        description="ID of the newly cloned test run",
    )
    testRunName: str = Field(
        ...,
        description="Name of the newly cloned test run",
    )
    uniqueKey: Optional[str] = Field(
        None, description="Unique key generated for the newly cloned test run"
    )


class ElementUpdateInput(BaseModel):
    """Model representing the input for updating an element"""

    id: uuid.UUID = Field(
        ...,
        description="ID of the element to be updated",
    )
    createdBy: str = Field(
        ...,
        description="Name of the user who created the element",
    )
    selector: Optional[str] = Field(
        default="selector",
        description="Selector like xpath and css for the element to be updated",
    )
    testMode: Literal["Web", "Mobile"] = Field(
        default="Web",
        description="Test mode for the element, accepting only 'Web', 'API', or 'Mobile'",
    )
    feature: Optional[uuid.UUID] = Field(
        default=None,
        description="Feature UUID to which the element belongs, if any",
    )
    module: Optional[str] = Field(
        default=None,
        description="Module NAME to which the element belongs, if any",
    )
    name: Optional[str] = Field(
        default=None,
        description="Name of the element to be updated",
    )
    projectId: Optional[uuid.UUID] = Field(
        None,
        description="ID of the project to which the element belongs",
    )


class ElementOutputResponse(BaseModel):
    """Model representing the output for an element"""

    id: uuid.UUID = Field(
        ...,
        description="ID of the element",
    )
    name: str = Field(
        ...,
        description="Name of the element",
    )
    uniqueKey: Optional[str] = Field(
        None, description="Unique key generated for the element"
    )
    selector: str = Field(
        ...,
        description="Selector like xpath and css for the element",
    )


class ElementCreationInput(BaseModel):
    """Model representing the input for creating an element"""

    name: str = Field(
        ...,
        description="Name of the element to be created",
    )
    selector: str = Field(
        ...,
        description="Selector like xpath and css for the element to be created",
    )
    testMode: Literal["Web", "Mobile"] = Field(
        default="Web",
        description="Test mode for the element, accepting only 'Web' or 'Mobile'",
    )
    feature: uuid.UUID = Field(
        ...,
        description="Feature UUID to which the element belongs",
    )
    module: str = Field(
        ...,
        description="Module name to which the element belongs",
    )
    projectId: Optional[uuid.UUID] = Field(
        None,
        description="ID of the project to which the element belongs",
    )
    createdBy: str = Field(
        ...,
        description="Name of the user who is creating the element",
    )


class ElementCreationOutput(BaseModel):
    """Model representing the output for creating an element"""

    id: uuid.UUID = Field(
        ...,
        description="ID of the created element",
    )
    name: str = Field(
        ...,
        description="Name of the created element",
    )
    createdBy: str = Field(
        ...,
        description="Name of the user who created the element",
    )
    selector: str = Field(
        ...,
        description="Selector like xpath and css for the created element",
    )


class WaitForCaseExecutionInput(BaseModel):
    """Model representing the input for waiting for execution of a test case"""

    testCaseId: uuid.UUID = Field(
        ..., description="ID of the test case to wait for execution"
    )


class TestCaseResultOutput(BaseModel):
    """Model representing the output for waiting for execution of a test case"""

    testCaseId: uuid.UUID = Field(..., description="ID of the test case")
    status: Literal["Pass", "Fail", "Abort"] = Field(
        ...,
        description="Execution status of the test case, which can be 'Pass', 'Fail', 'Abort'",
    )
    executeTime: str = Field(
        ..., description="Execution date and time of the test case"
    )
    traceStack: str = Field(
        ...,
        description="Complete log of test case with each test step and its execution status",
    )


class TestDataEntry(BaseModel):
    field: str = Field(
        ..., description="Name or placeholder name of the test data field"
    )
    value: str = Field(..., description="Value of the test data field")
    type: str = Field(
        default="text",
        description="Type of the test data field. For every thing it is 'text' when upload file then it is 'file'",
    )


class ClaudeElement(BaseModel):
    """An element with real locators, supplied by the agent (Phase 2 output)."""

    name: str = Field(
        ..., description="Name of the element, e.g., 'email_textbox' — no el: prefix"
    )
    css_selector: Optional[str] = Field(
        default=None, description="Primary CSS selector saved to DB"
    )
    xpath: Optional[str] = Field(
        default=None, description="Fallback XPath selector, stored for reference"
    )


class ClaudeTestCaseInput(BaseModel):
    """A single test case authored by the agent in Phase 1/2."""

    name: str = Field(
        ..., description="Name of the test case, e.g., 'Login with valid credentials'"
    )
    description: str = Field(..., description="Description of the test case")
    type: Literal["Functional +Ve", "Functional -Ve", "Other"] = Field(
        default="Functional +Ve",
        description="Type of the test case, e.g., 'Functional +Ve' or 'Functional -Ve'",
    )
    priority: Literal["Minor", "Major", "Blocker", "Critical"] = Field(
        default="Major",
        description="Priority of the test case, e.g., 'Minor', 'Major', 'Blocker', 'Critical'",
    )
    test_phase: str = Field(
        default="QA", description="Test phase of the test case, e.g., 'QA'"
    )
    steps: List[str] = Field(
        ..., description="Steps of the test case, already in autopilot format"
    )
    elements: List[ClaudeElement] = Field(
        default_factory=list, description="List of elements involved in the test case"
    )
    test_data: List[TestDataEntry] = Field(
        default_factory=list, description="List of test data entries for the test case"
    )
    file_ids: List[str] = Field(
        default_factory=list,
        description=(
            "IDs of uploaded CSV data files this test case references (from "
            "upload_datafile). Empty for non-CSV-driven test cases. Requires a "
            "matching field on the backend's zero-LLM test-case model — see "
            "docs/backend-performance-test-fileids.md."
        ),
    )


class CreateTestCaseFromClaudeRequest(BaseModel):
    """Batch request from the plugin — no server-side LLM re-analysis needed.

    The `Claude` in this class name mirrors the backend route it maps to
    (`/create-from-claude`); it is a wire-contract name, not a host reference.
    """

    test_cases: List[ClaudeTestCaseInput]
    module: str = Field(..., description="Module name for the test cases")
    feature: uuid.UUID = Field(..., description="Feature ID for the test cases")
    test_mode: Literal["Web", "API", "Mobile", "Performance"] = Field(
        ..., description="Test mode, e.g., 'Web', 'API', 'Mobile', 'Performance'"
    )
    project_id: Optional[uuid.UUID] = Field(
        None, description="Project ID for the test cases"
    )
    user_id: Optional[uuid.UUID] = Field(None, description="User ID for the test cases")
    created_by: str = Field(
        ...,
        description="Name of the user creating the test cases, get from get_user_details_by_id_or_email_or_unique_key if not have",
    )
    browser_type: Literal["Chrome", "Firefox", "Safari", "Edge"] = Field(
        default="Chrome", description="Browser type for the test cases, e.g., 'Chrome'"
    )
    platform: str = Field(
        default="",
        description="Platform for the test cases, e.g., 'web', 'mobile', 'api'",
    )
    env_id: str = Field(default="", description="Environment ID for the test cases")
    apk_id: str = Field(default="", description="APK ID for the test cases")


class UploadDataFileInput(BaseModel):
    """Input for uploading a CSV data file to the platform's data-files store (/create-datafile)."""

    file_path: str = Field(
        ...,
        description="Local filesystem path to the CSV file to upload — already generated and validated",
    )
    file_name: str = Field(
        ...,
        max_length=20,
        pattern=r"^[A-Za-z0-9_-]+$",
        description=(
            "Bare identifier to register the file under — NO extension and NO characters "
            "other than letters/numbers/underscore/hyphen (server-validated: this exact "
            "string is the <name> token in {{data.<name>.<column>}} placeholders, which "
            "can't contain a '.'). HARD LIMIT: 20 characters. E.g. 'ord_load1' (9 chars), "
            "not 'ord_load1.csv'."
        ),
    )
    project_id: Optional[uuid.UUID] = Field(
        None, description="Project ID for the upload. Falls back to plugin default when omitted."
    )
    uploaded_by: str = Field(
        ...,
        max_length=40,
        description="Plain human display name of the uploader (empName) — same convention as save_claude_test_cases' created_by. Never an email or UUID.",
    )
    need_to_update: bool = Field(
        default=False,
        description="Set true only when replacing/updating a previously uploaded file with the same identity",
    )


class DataFileUploadOutput(BaseModel):
    """Response from uploading a data file — id is what goes into a test case's file_ids."""

    id: uuid.UUID = Field(..., description="File ID — use this in a test case's file_ids list")
    projectId: Optional[uuid.UUID] = Field(None, description="Project the file belongs to")
    uniqueKey: Optional[str] = Field(None, description="Unique key of the uploaded file")
    fileName: Optional[str] = Field(None, description="Registered file name")
    filePath: Optional[str] = Field(None, description="Server-assigned storage path")
    fileSize: Optional[int] = Field(None, description="File size in bytes")
    uploadedBy: Optional[str] = Field(None, description="Display name of the uploader")
    fileOriginalName: Optional[str] = Field(None, description="Original filename from the multipart upload")
    extension: Optional[str] = Field(None, description="File extension")
    createdAt: Optional[str] = Field(None, description="Creation timestamp")
    needToUpdate: Optional[bool] = Field(None, description="Whether this file is flagged for update")


class GetDefectOrTaskDetailsByNameOrUniqueKeyInput(BaseModel):
    """Model representing the input for retrieving defect or task details by name or unique key"""

    identifier: Optional[str] = Field(
        None,
        description="Name or unique key of the defect or task to retrieve details for",
    )
    projectId: Optional[uuid.UUID] = Field(
        default=None,
        description="ID of the project for which to retrieve defect or task details",
    )
    priority: Optional[str] = Field(
        None,
        description="Priority filter. Supports single or comma-separated values from Minor, Major, Blocker, Critical",
    )
    state: Optional[str] = Field(
        None,
        description="State filter. Supports single or comma-separated values from Open, Inprogress, Reopened, Closed, Rejected",
    )
    status: Optional[str] = Field(
        None,
        description="Status filter. Supports single or comma-separated status values",
    )
    createdBy: Optional[str] = Field(
        None, description="Name of the user who created the defect or task"
    )
    assignedTo: Optional[str] = Field(
        None, description="Name of the user to whom the defect or task is assigned"
    )
    assignedBy: Optional[str] = Field(
        None, description="Name of the user who assigned the defect or task"
    )

    @field_validator("state", mode="before")
    @classmethod
    def validate_state_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None
        invalid = [
            item for item in normalized.split(",") if item not in ALLOWED_DEFECT_STATES
        ]
        if invalid:
            raise ValueError(
                f"Invalid state value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_DEFECT_STATES))}"
            )
        return normalized

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None
        invalid = [
            item
            for item in normalized.split(",")
            if item not in ALLOWED_DEFECT_PRIORITIES
        ]
        if invalid:
            raise ValueError(
                f"Invalid priority value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_DEFECT_PRIORITIES))}"
            )
        return normalized

    @field_validator("status", mode="before")
    @classmethod
    def validate_status_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None
        invalid = [
            item
            for item in normalized.split(",")
            if item not in ALLOWED_DEFECT_STATUSES
        ]
        if invalid:
            raise ValueError(
                f"Invalid status value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_DEFECT_STATUSES))}"
            )
        return normalized

    @field_validator("createdBy", "assignedTo", "assignedBy", mode="before")
    @classmethod
    def normalize_name_filters_csv(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_csv_filter(value)


class GetDefectOrTaskDetailsOutput(BaseModel):
    """Model representing the output for retrieving defect or task details by name or unique key"""

    id: uuid.UUID = Field(..., description="ID of the defect or task")
    title: str = Field(..., description="Title of the defect or task")
    description: str | None = Field(
        None, description="Description of the defect or task"
    )
    priority: Optional[Literal["Minor", "Major", "Blocker", "Critical"]] = Field(
        None, description="Priority of the defect or task"
    )
    uniqueKey: Optional[str] = Field(
        None, description="Unique key of the defect or task"
    )
    state: Optional[Literal["Open", "Inprogress", "Reopened", "Closed", "Rejected"]] = (
        Field(None, description="State of the defect or task")
    )
    status: Optional[
        Literal[
            "Assigned",
            "Planned",
            "Fix Inprogress",
            "In Review",
            "In Test",
            "Bug Reproduced",
            "Fix Failed",
            "Fixed",
            "Verified",
            "Automated",
            "Done",
            "Duplicate",
            "Not a Bug",
            "Won't Fix",
            "UnAssigned",
        ]
    ] = Field(
        None,
        description="Status of the defect or task to filter by when retrieving defect or task details",
    )
    assignedTo: Optional[str] = Field(
        None, description="Name of the user to whom the defect or task is assigned"
    )
    createdBy: Optional[str] = Field(
        None, description="Name of the user who created the defect or task"
    )
    createdAt: Optional[str] = Field(
        None, description="Creation date of the defect or task"
    )
    assignedBy: Optional[str] = Field(
        None, description="Name of the user who assigned the defect or task"
    )
    targetDate: Optional[str] = Field(
        None, description="Target date of the defect or task"
    )


class GetUtilsWithFiltersInput(BaseModel):
    """Input for GET /utils/v1/get-all-utils/{projectId}"""

    projectId: Optional[uuid.UUID] = Field(
        None,
        description="ID of the project to retrieve utils for. Falls back to the plugin default when omitted.",
    )
    query: Optional[str] = Field(
        None, description="Search string to filter utils by name or unique key"
    )
    testMode: Optional[str] = Field(
        None,
        description="Test mode filter. Supports a single value or comma-separated values from 'Web', 'API', 'Mobile'.",
    )
    feature: Optional[str] = Field(
        None,
        description="Feature name filter. Supports a single value or comma-separated feature names.",
    )
    module: Optional[str] = Field(
        None,
        description="Module name filter. Supports a single value or comma-separated module names.",
    )
    page: int = Field(
        default=0, ge=0, description="Zero-based page number for pagination"
    )
    size: int = Field(
        default=10, ge=1, le=200, description="Number of results per page"
    )
    status: Optional[bool] = Field(
        False, description="Filter by active status. false means active (not archived)."
    )
    deleted: Optional[bool] = Field(
        False, description="Filter by deleted status. false means not deleted."
    )

    @field_validator("testMode", mode="before")
    @classmethod
    def validate_test_mode_csv(cls, value: Optional[str]) -> Optional[str]:
        normalized = _normalize_csv_filter(value)
        if normalized is None:
            return None
        canonical_map = {"web": "Web", "api": "API", "mobile": "Mobile", "performance": "Performance"}
        converted: list[str] = []
        invalid: list[str] = []
        for item in normalized.split(","):
            canonical = canonical_map.get(item.lower())
            if canonical is None:
                invalid.append(item)
            else:
                converted.append(canonical)
        if invalid:
            raise ValueError(
                f"Invalid testMode value(s): {', '.join(invalid)}. Allowed values: {', '.join(sorted(ALLOWED_TEST_MODES))}"
            )
        return ",".join(converted)

    @field_validator("feature", "module", mode="before")
    @classmethod
    def normalize_csv_fields(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_csv_filter(value)


class UtilOutput(BaseModel):
    """A single utility item returned by the utils list endpoint."""

    id: uuid.UUID = Field(..., description="ID of the util")
    uniqueKey: Optional[str] = Field(
        None, description="Unique key of the util, e.g. 'Util-01551'"
    )
    utilName: str = Field(..., description="Name of the util")
    testMode: Optional[str] = Field(
        None, description="Test mode of the util: Web, API, or Mobile"
    )
    module: Optional[str] = Field(None, description="Module name the util belongs to")
    feature: Optional[str] = Field(None, description="Feature name the util belongs to")
    featureId: Optional[uuid.UUID] = Field(
        None, description="UUID of the feature the util belongs to"
    )
    testData: Optional[str] = Field(
        None, description="JSON-encoded test data for the util"
    )
    deleted: bool = Field(default=False, description="Whether the util is deleted")
    deletedBy: Optional[str] = Field(
        None, description="Name of the user who deleted the util, if any"
    )
    fileIds: List[str] = Field(
        default_factory=list, description="List of file IDs attached to the util"
    )
    elementIds: List[str] = Field(
        default_factory=list, description="List of element IDs used by the util"
    )


class GetUtilsWithFiltersOutput(BaseModel):
    """Paginated response from the utils list endpoint."""

    content: List[UtilOutput] = Field(
        ..., description="List of utils on the current page"
    )
    totalElements: int = Field(
        ..., description="Total number of utils matching the filters"
    )
    totalPages: int = Field(..., description="Total number of pages")
    page: int = Field(..., description="Current zero-based page number")
    size: int = Field(..., description="Number of results per page")
    last: bool = Field(..., description="Whether this is the last page")


class ClaudeUtilInput(BaseModel):
    """Input model for creating a new util."""

    utilName: str = Field(..., description="Name of the util")
    testMode: Literal["Web", "API", "Mobile", "Performance"] = Field(
        ..., description="Test mode for the util"
    )
    testData: List[TestDataEntry] = Field(
        default_factory=list,
        description="Test data fields for the util. Each field can be overridden by the calling test case using the naming convention: <field>_i<N>_<util-uuid>",
    )
    utilTestCaseSteps: List[str] = Field(
        ..., description="List of test case steps for the util in autopilot format"
    )
    elements: List[ClaudeElement] = Field(
        default_factory=list,
        description="List of elements used by the util with real selectors discovered in Phase 2",
    )
    fileIds: Optional[List[str]] = Field(
        [], description="List of file IDs attached to the util"
    )
    feature: uuid.UUID = Field(..., description="Feature ID associated with the util")


class CreateUtilFromClaudeRequest(BaseModel):
    """Batch request for creating agent-authored utils — no LLM re-analysis."""

    utils: List[ClaudeUtilInput] = Field(..., description="List of utils to create")
    module: str = Field(..., description="Module name for the utils")
    projectId: Optional[uuid.UUID] = Field(
        None,
        description="Project ID for the utils. Falls back to plugin default when omitted.",
    )
    userName: str = Field(..., description="Name of the user creating the utils")
    user_id: Optional[uuid.UUID] = Field(
        None, description="ID of the user creating the utils"
    )
    token: Optional[str] = Field(None, description="Authentication token for the user")


class SavedUtilItem(BaseModel):
    """A single util item returned after creation."""

    id: uuid.UUID = Field(..., description="UUID of the created util")
    utilName: str = Field(..., description="Name of the util")
    uniqueKey: Optional[str] = Field(
        None, description="Unique key of the util, e.g. 'Util-01551'"
    )


class SaveUtilsOutput(BaseModel):
    """Response from the save_claude_utils tool."""

    created: List[SavedUtilItem] = Field(
        ..., description="List of created util items with their UUIDs"
    )
    count: int = Field(..., description="Total number of utils created")
