"""Shared strict request model for the local JSON API.

Unknown JSON fields are rejected so misspelled client fields cannot be silently
ignored and mistaken for a successful configuration change.
"""
from pydantic import BaseModel, ConfigDict

class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
