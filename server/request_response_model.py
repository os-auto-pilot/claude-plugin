
from typing import Optional
import uuid

from pydantic import BaseModel, Field


class ModuleIdByNameOrUniqueKeyInput(BaseModel):
    token: str = Field(..., description="Authentication token for retrieving module ID")
    projectId: uuid.UUID = Field(
        ..., description="ID of the project for which to retrieve module ID"
    )
    identifier: str = Field(
        ..., description="Name or unique key of the module to retrieve ID for"
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
    projectId: uuid.UUID = Field(
        ..., description="ID of the project for which the feature is being created"
    )
    moduleId: uuid.UUID = Field(
        ..., description="ID of the module for which the feature is being created"
    )
    token: str = Field(..., description="Authentication token for feature creation")