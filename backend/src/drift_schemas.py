from pydantic import BaseModel,Field
class BaselineRebuildInput(BaseModel):
    recipe_id:int=Field(gt=0)
class ProjectInput(BaseModel):
    swatch_id:int=Field(gt=0)
class ConfirmInput(BaseModel):
    verdict:str=Field(pattern='^(normal|anomaly)$')
