from pydantic import BaseModel, ConfigDict, Field


class DetectedObject(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    class_name: str = Field(alias="class", serialization_alias="class")
    confidence: float
    x: int
    y: int
    width: int
    height: int


class DetectionResponse(BaseModel):
    objects: list[DetectedObject]
